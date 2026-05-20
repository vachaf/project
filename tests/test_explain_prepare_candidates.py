from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "explain_prepare_candidates.py"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "prepare_candidate_explain_sample.json"


def load_module():
    spec = importlib.util.spec_from_file_location("explain_prepare_candidates", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_explanations():
    module = load_module()
    payload = module.read_json(FIXTURE_PATH)
    source, candidates = module.extract_candidates(payload)
    explanations = [
        module.explain_candidate(candidate, idx + 1, module.DEFAULT_MIN_SCORE)
        for idx, candidate in enumerate(candidates)
    ]
    return source, explanations


def by_request_id(explanations):
    return {item["request_id"]: item for item in explanations}


def test_extracts_analysis_candidates_from_fixture():
    source, explanations = build_explanations()

    assert source == "analysis_candidates"
    assert len(explanations) == 4


def test_upload_sql_comment_only_is_context_candidate_upload_failure():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-upload-only-sql-comment"]

    assert item["scenario"] == "S09"
    assert item["policy_class"] == "context_candidate_upload_failure"
    assert "sqli:sql_comment(+2)" in item["reason_groups"]["attack_payload"]
    assert "multipart boundary/comment-marker false positive" in item["policy_note"]


def test_strong_sqli_payload_remains_keep_candidate_payload():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-sqli-strong"]

    assert item["scenario"] == "S13"
    assert item["policy_class"] == "keep_candidate_payload"
    assert "sqli:or_true(+4)" in item["reason_groups"]["attack_payload"]
    assert "sqli:quote_termination(+4)" in item["reason_groups"]["attack_payload"]


def test_status_error_only_candidate_is_marked_for_demotion_review():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-status-error-only"]

    assert item["scenario"] == "S11"
    assert item["policy_class"] == "demotion_candidate_status_error_only"
    assert "error_status:500(+2)" in item["reason_groups"]["status_error"]
    assert "error_linked(+2)" in item["reason_groups"]["status_error"]


def test_sensitive_probe_candidate_is_context_candidate_probe():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-probe-env"]

    assert item["scenario"] == "S12"
    assert item["policy_class"] == "context_candidate_probe"
    assert "sensitive_path:env_file" in item["reason_groups"]["probe_context"]


def test_summary_policy_counts_match_expected_shape():
    module = load_module()
    _, explanations = build_explanations()
    summary = module.summarize(explanations)

    assert summary["candidate_count"] == 4
    assert summary["policy_counts"] == {
        "context_candidate_probe": 1,
        "context_candidate_upload_failure": 1,
        "demotion_candidate_status_error_only": 1,
        "keep_candidate_payload": 1,
    }
