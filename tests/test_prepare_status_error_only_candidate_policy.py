from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "explain_prepare_candidates.py"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "prepare_status_error_only_candidate_sample.json"


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


def test_extracts_status_error_fixture_candidates():
    source, explanations = build_explanations()

    assert source == "analysis_candidates"
    assert len(explanations) == 5


def test_isolated_500_status_error_candidate_is_marked_for_demotion_review():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-isolated-500-error"]

    assert item["scenario"] == "S11"
    assert item["policy_class"] == "demotion_candidate_status_error_only"
    assert "error_status:500(+2)" in item["reason_groups"]["status_error"]
    assert "error_linked(+2)" in item["reason_groups"]["status_error"]
    assert "attack_payload" not in item["reason_groups"]


def test_forbidden_private_path_status_error_candidate_is_marked_for_review():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-forbidden-private-path"]

    assert item["scenario"] == "S06"
    assert item["policy_class"] == "demotion_candidate_status_error_only"
    assert "error_status:403(+2)" in item["reason_groups"]["status_error"]
    assert "error_linked(+2)" in item["reason_groups"]["status_error"]


def test_500_with_explicit_traversal_payload_remains_payload_candidate():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-500-with-traversal-payload"]

    assert item["scenario"] == "S15"
    assert item["policy_class"] == "keep_candidate_payload"
    assert "traversal:dotdot_slash(+4)" in item["reason_groups"]["attack_payload"]
    assert "traversal:etc_passwd(+5)" in item["reason_groups"]["attack_payload"]


def test_login_get_context_row_is_status_error_review_not_auth_success():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-login-get-context"]

    assert item["scenario"] == "S07"
    assert item["policy_class"] == "demotion_candidate_status_error_only"
    assert "login_endpoint(+1)" in item["reason_groups"]["auth"]
    assert "error_linked(+2)" in item["reason_groups"]["status_error"]


def test_probe_env_context_stays_in_probe_bucket_not_status_error_only():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-probe-env-context"]

    assert item["scenario"] == "S12"
    assert item["policy_class"] == "context_candidate_probe"
    assert "sensitive_path:env_file" in item["reason_groups"]["probe_context"]
    assert "error_status:404(+2)" in item["reason_groups"]["status_error"]


def test_status_error_policy_counts_match_expected_shape():
    module = load_module()
    _, explanations = build_explanations()
    summary = module.summarize(explanations)

    assert summary["candidate_count"] == 5
    assert summary["policy_counts"] == {
        "context_candidate_probe": 1,
        "demotion_candidate_status_error_only": 3,
        "keep_candidate_payload": 1,
    }
