from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "explain_prepare_candidates.py"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "prepare_scanner_probe_candidate_sample.json"


def load_module():
    spec = importlib.util.spec_from_file_location("sliding_window_scheduler", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    
    # dataclasses 등이 모듈의 네임스페이스를 참조할 수 있도록 sys.modules에 등록
    sys.modules["sliding_window_scheduler"] = module
    
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


def test_extracts_scanner_probe_fixture_candidates():
    source, explanations = build_explanations()

    assert source == "analysis_candidates"
    assert len(explanations) == 6


def test_env_file_probe_is_context_candidate_not_exposure_proof():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-env-file-404-probe"]

    assert item["scenario"] == "S12"
    assert item["policy_class"] == "context_candidate_probe"
    assert "sensitive_path:env_file" in item["reason_groups"]["probe_context"]
    assert "sensitive_path:no_file_exposure_inference" in item["reason_groups"]["probe_context"]
    assert "attack_payload" not in item["reason_groups"]


def test_wordpress_scanner_probe_is_context_candidate():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-wp-login-scanner-probe"]

    assert item["scenario"] == "S12"
    assert item["policy_class"] == "context_candidate_probe"
    assert "sensitive_path:wordpress_login" in item["reason_groups"]["probe_context"]
    assert "scanner:known_scanner_user_agent" in item["reason_groups"]["probe_context"]
    assert "error_status:404(+2)" in item["reason_groups"]["status_error"]


def test_admin_dir_scanner_probe_is_context_candidate():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-admin-dir-scanner-probe"]

    assert item["scenario"] == "S12"
    assert item["policy_class"] == "context_candidate_probe"
    assert "dir_probe:admin_path" in item["reason_groups"]["probe_context"]
    assert "scanner:known_scanner_user_agent" in item["reason_groups"]["probe_context"]


def test_server_status_is_context_only_bucket():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-server-status-context"]

    assert item["scenario"] == "S13"
    assert item["policy_class"] == "context_only_server_status"
    assert "error_status:403(+2)" in item["reason_groups"]["status_error"]
    assert "attack_payload" not in item["reason_groups"]


def test_probe_with_explicit_traversal_payload_remains_payload_candidate():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-probe-with-traversal-payload"]

    assert item["scenario"] == "S15"
    assert item["policy_class"] == "keep_candidate_payload"
    assert "traversal:dotdot_slash(+4)" in item["reason_groups"]["attack_payload"]
    assert "traversal:etc_passwd(+5)" in item["reason_groups"]["attack_payload"]
    assert "scanner:known_scanner_user_agent" in item["reason_groups"]["probe_context"]


def test_scanner_with_explicit_sqli_payload_remains_payload_candidate():
    _, explanations = build_explanations()
    item = by_request_id(explanations)["req-scanner-sqli-payload"]

    assert item["scenario"] == "S03"
    assert item["policy_class"] == "keep_candidate_payload"
    assert "sqli:or_true(+4)" in item["reason_groups"]["attack_payload"]
    assert "sqli:quote_termination(+4)" in item["reason_groups"]["attack_payload"]
    assert "scanner:known_scanner_user_agent" in item["reason_groups"]["probe_context"]


def test_scanner_probe_policy_counts_match_expected_shape():
    module = load_module()
    _, explanations = build_explanations()
    summary = module.summarize(explanations)

    assert summary["candidate_count"] == 6
    assert summary["policy_counts"] == {
        "context_candidate_probe": 3,
        "context_only_server_status": 1,
        "keep_candidate_payload": 2,
    }
