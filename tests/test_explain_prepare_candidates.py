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


def test_detects_error_heavy_scenario_from_query_string():
    module = load_module()
    candidate = {
        "request_id": "req-error-heavy-query",
        "method": "GET",
        "uri": "/error.php",
        "query_string": "?scenario=EH01&run=obs_php_sample_v2_error_heavy_001",
        "status_code": 500,
        "score": 6,
        "verdict_hint": "suspicious",
        "reason_hints": [
            "error_status:500(+2)",
            "error_linked(+2)",
            "no_referer_non_browser_error(+1)",
            "long_query(+1)",
        ],
        "user_agent": "obs-error-heavy/EH01 run=obs_php_sample_v2_error_heavy_001",
    }

    item = module.explain_candidate(candidate, 1, module.DEFAULT_MIN_SCORE)

    assert item["scenario"] == "EH01"
    assert item["policy_class"] == "demotion_candidate_status_error_only"


def test_detects_error_heavy_scenario_from_user_agent():
    module = load_module()
    candidate = {
        "request_id": "req-error-heavy-ua",
        "method": "POST",
        "uri": "/login.php",
        "query_string": "?run=obs_php_sample_v2_error_heavy_001",
        "status_code": 401,
        "score": 8,
        "verdict_hint": "suspicious",
        "reason_hints": [
            "error_status:401(+2)",
            "error_linked(+2)",
            "no_referer_non_browser_error(+1)",
            "long_query(+1)",
            "login_endpoint(+1)",
            "auth_payload_content_type(+1)",
        ],
        "user_agent": "obs-error-heavy/EH04 run=obs_php_sample_v2_error_heavy_001",
    }

    item = module.explain_candidate(candidate, 1, module.DEFAULT_MIN_SCORE)

    assert item["scenario"] == "EH04"
    assert item["policy_class"] == "context_candidate_auth_failure"


def test_detects_direct_error_heavy_scenario_field():
    module = load_module()
    candidate = {
        "scenario": "eh10",
        "request_id": "req-error-heavy-direct",
        "method": "GET",
        "uri": "/download.php",
        "query_string": "?file=..%2F..%2F..%2Fetc%2Fpasswd&run=obs_php_sample_v2_error_heavy_001",
        "status_code": 404,
        "score": 15,
        "verdict_hint": "path_traversal",
        "reason_hints": [
            "traversal:dotdot_slash(+4)",
            "traversal:etc_passwd(+5)",
            "error_status:404(+2)",
            "error_linked(+2)",
            "no_referer_non_browser_error(+1)",
            "long_query(+1)",
        ],
        "user_agent": "obs-error-heavy/EH10 run=obs_php_sample_v2_error_heavy_001",
    }

    item = module.explain_candidate(candidate, 1, module.DEFAULT_MIN_SCORE)

    assert item["scenario"] == "EH10"
    assert item["policy_class"] == "keep_candidate_payload"


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
