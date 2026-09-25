from __future__ import annotations

from src import prepare_llm_input as prepare
from src import viewer_payload_builder as viewer
from src.prepare.decoders import decode_url_path
import src.llm_stage2_reporter as stage2

def candidate_f_row() -> dict:
    return {
        "id": 1152,
        "log_schema": "apache_security_io_v2",
        "log_time": "2026-09-22T20:26:23.497+09:00",
        "request_id": "arJl303GoPjXB9MWh2OIywAAAAE",
        "error_link_id": "arJl303GoPjXB9MWh2OIywAAAAE",
        "src_ip": "192.168.56.120",
        "peer_ip": "192.168.56.120",
        "method": "GET",
        "raw_request": "GET /index.php?q=select%20shoes HTTP/1.1",
        "request_target": "/index.php?q=select%20shoes",
        "uri": "/index.php",
        "query_string": "?q=select%20shoes",
        "status_code": 200,
        "response_body_bytes": 1564,
        "duration_us": 267487,
        "ttfb_us": 252357,
        "handler": "application/x-httpd-php",
        "resp_content_type": "text/html",
        "referer": None,
        "user_agent": "presentation-candidate/2.0",
        "raw_log": "",
    }


def test_prepare_preserves_timestamp_offset_and_keeps_url_form_decoding() -> None:
    assert prepare.normalize_text("2026-09-22T16:00:08+09:00") == "2026-09-22T16:00:08+09:00"

    variants = prepare.build_decoded_variants("%2e%2e%2f")
    assert [item["text"] for item in variants] == ["%2e%2e%2f", "../"]
    assert prepare.extract_query_pairs("q=select+shoes") == [("q", "select shoes")]


def test_path_only_decoding_preserves_literal_plus_and_restores_encoded_path_semantics() -> None:
    assert decode_url_path("/C++/guide?ignored=query+value") == "/C++/guide"
    assert prepare.normalize_text("2026-09-22T16:00:08+09:00") == "2026-09-22T16:00:08+09:00"

    auth_rows = [
        {
            "src_ip": "192.0.2.1",
            "log_time": "2026-09-22T16:00:08+09:00",
            "method": "POST",
            "uri": "/%6cogin",
            "raw_request": "POST /%6cogin HTTP/1.1",
            "status_code": 200,
            "request_id": "encoded-login",
            "user_agent": "Mozilla/5.0",
        }
    ]
    auth_summaries = prepare.build_auth_behavior_summaries(auth_rows)
    assert auth_summaries[0]["endpoint_family"] == "auth_login"
    assert auth_summaries[0]["window_start"] == "2026-09-22T16:00:08+09:00"

    assert prepare.classify_crawler_baseline_path_category("/pro%64ucts/1", "GET") == "product_browse"
    assert prepare.classify_sensitive_path_probe_category("/%2eenv", "GET") == "env_file"
    assert prepare.classify_static_baseline_asset_category("/robots%2etxt", "GET") == "robots_txt"
    static_rows = [
        {
            "src_ip": "192.0.2.1",
            "log_time": f"2026-09-22T16:00:0{index}+09:00",
            "method": "GET",
            "uri": "/robots%2etxt",
            "raw_request": "GET /robots%2etxt HTTP/1.1",
            "status_code": 200,
            "request_id": f"encoded-robots-{index}",
        }
        for index in range(3)
    ]
    static_summaries = prepare.build_static_baseline_summaries(static_rows)
    assert static_summaries[0]["path_counts"] == {"/robots.txt": 3}

    long_row = {
        "src_ip": "192.0.2.1",
        "log_time": "2026-09-22T16:00:08+09:00",
        "method": "GET",
        "uri": "/" + "%41" * 200,
        "raw_request": "GET /" + "%41" * 200 + " HTTP/1.1",
        "protocol": "HTTP/1.1",
        "host": "example.test",
        "status_code": 414,
    }
    assert "protocol_anomaly:long_path" not in prepare.build_protocol_anomaly_reason_hints_for_row(long_row)


def test_candidate_f_terminal_fallback_is_neutral_and_not_stage2_recon() -> None:
    row = candidate_f_row()
    payload = {
        "meta": {"total_count": 1},
        "data": {"security": [row]},
    }
    llm_input, candidates, _noise, filtered_reasons, _filtered_rows = prepare.build_outputs(
        payload,
        min_score=4,
        min_repeat_aggregate=3,
        source_tables=["security"],
    )

    assert candidates == []
    assert llm_input["meta"]["filtered_out_breakdown"] == {"low_signal_request": 1}
    assert filtered_reasons["excluded_summary"] == {"low_signal_request": 1}
    assert filtered_reasons["excluded"][0]["log_time"] == "2026-09-22T20:26:23.497+09:00"

    report_input = stage2.build_report_input(
        stage1_payload={"meta": {"success_count": 0, "error_count": 0}, "results": []},
        llm_input_payload=llm_input,
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )
    assert report_input["top_out_of_candidate_recon"] == []
    assert stage2.is_low_signal_only_neutral_mode(report_input)
    assert "low_signal_request != reconnaissance" in stage2.build_messages(report_input)[0]["content"]


def test_single_neutral_low_signal_aggregate_note_does_not_claim_repetition() -> None:
    payload = {
        "meta": {"total_count": 1},
        "data": {"security": [candidate_f_row()]},
    }
    llm_input, _candidates, _noise, _filtered_reasons, _filtered_rows = prepare.build_outputs(
        payload,
        min_score=4,
        min_repeat_aggregate=1,
        source_tables=["security"],
    )

    assert llm_input["noise_summary"][0]["category"] == "low_signal_request"
    assert "반복" not in llm_input["noise_summary"][0]["note"]


def test_explicit_low_signal_fuzzing_remains_fuzzing() -> None:
    row = candidate_f_row()
    row.update(
        {
            "error_link_id": "",
            "query_string": "q=one!two!three!four",
            "raw_request": "GET /index.php?q=one!two!three!four HTTP/1.1",
            "request_target": "/index.php?q=one!two!three!four",
            "raw_log": "",
        }
    )

    candidate, category = prepare.evaluate_row(row, source_table="security", min_score=4)
    assert candidate is None
    assert category == "low_signal_fuzzing"


def test_non_browser_ua_alone_does_not_change_terminal_low_signal_meaning() -> None:
    categories = []
    for user_agent in ("Mozilla/5.0", "presentation-candidate/2.0"):
        row = candidate_f_row()
        row["user_agent"] = user_agent
        candidate, category = prepare.evaluate_row(row, source_table="security", min_score=4)
        assert candidate is None
        categories.append(category)

    assert categories == ["low_signal_request", "low_signal_request"]


def test_known_asset_placeholder_is_not_treated_as_an_asset_ip(monkeypatch) -> None:
    assert stage2.parse_known_asset_ips("OPTIONAL_ASSET_IP_LIST") == []
    assert stage2.parse_known_asset_ips("") == []
    assert stage2.parse_known_asset_ips("192.0.2.10, 2001:db8::10") == ["192.0.2.10", "2001:db8::10"]
    assert stage2.parse_known_asset_ips("not-an-ip") == ["not-an-ip"]
    monkeypatch.setenv("KNOWN_ASSET_IPS", "OPTIONAL_ASSET_IP_LIST")
    assert stage2.resolve_known_asset_ips(None) == []


def test_single_request_multiple_categories_prompt_disallows_multiple_request_wording() -> None:
    report_input = {
        "ip_behavior_aggregates": [
            {
                "request_count": 1,
                "attack_categories_attempted": ["path_traversal", "file_disclosure", "dir_probe"],
            }
        ]
    }
    prompt = stage2.build_messages(report_input)[0]["content"]
    assert "request_count=1 이고 attack_categories_attempted가 복수이면 한 요청에서 복수의 탐지 성격이 파생된 것으로만" in prompt

    single_summary = stage2.build_dry_run_markdown(report_input, selected_model="test", mode="routine")
    assert "한 요청에서 복수의 탐지 성격이 파생된 문맥" in single_summary

    report_input["ip_behavior_aggregates"][0]["request_count"] = 2
    multiple_summary = stage2.build_dry_run_markdown(report_input, selected_model="test", mode="routine")
    assert "한 요청에서 복수의 탐지 성격이 파생된 문맥" not in multiple_summary


def single_request_multi_signal_row() -> dict:
    return {
        "id": 9001,
        "log_schema": "apache_security_io_v2",
        "log_time": "2026-09-23T11:30:57.980+09:00",
        "request_id": "single-multi-signal",
        "src_ip": "192.0.2.44",
        "method": "GET",
        "raw_request": "GET /download.php?file=../../../etc/passwd HTTP/1.1",
        "request_target": "/download.php?file=../../../etc/passwd",
        "uri": "/download.php",
        "query_string": "?file=../../../etc/passwd",
        "status_code": 403,
        "response_body_bytes": 10,
        "duration_us": 5693,
        "ttfb_us": 5032,
        "handler": "application/x-httpd-php",
        "resp_content_type": "text/plain",
        "referer": None,
        "user_agent": "test-agent/1.0",
        "raw_log": "",
    }


def test_single_request_multi_signal_stays_finding_evidence_not_ip_behavior() -> None:
    row = single_request_multi_signal_row()
    payload = {"meta": {"total_count": 1}, "data": {"security": [row]}}

    llm_input, candidates, _noise, _filtered_reasons, _filtered_rows = prepare.build_outputs(
        payload,
        min_score=4,
        min_repeat_aggregate=3,
        source_tables=["security"],
    )

    assert len(candidates) == 1
    assert candidates[0]["verdict_hint"] == "path_traversal"
    assert "traversal:dotdot_slash(+4)" in candidates[0]["reason_hints"]
    assert "file_disclosure:sensitive_resource:os_file" in candidates[0]["reason_hints"]
    context_hints = prepare.build_row_context_reason_hints(row)
    assert "dir_probe:burst" in context_hints
    assert prepare.get_attack_categories_from_reason_hints(context_hints) == [
        "path_traversal",
        "file_disclosure",
        "dir_probe",
    ]
    assert llm_input["ip_behavior_aggregates"] == []

    report_input = stage2.build_report_input(
        stage1_payload={"meta": {"success_count": 1, "error_count": 0}, "results": candidates},
        llm_input_payload=llm_input,
        stage1_errors_payload=None,
        top_incidents=3,
        top_noise_groups=8,
        top_ips=3,
        known_asset_ips=[],
    )
    assert report_input["top_incidents"]
    assert report_input["ip_behavior_aggregates"] == []


def test_multi_request_multiple_categories_keeps_ip_behavior_context() -> None:
    traversal_row = single_request_multi_signal_row()
    sqli_row = dict(traversal_row)
    sqli_row.update(
        {
            "id": 9002,
            "request_id": "multi-request-sqli",
            "log_time": "2026-09-23T11:30:58.980+09:00",
            "raw_request": "GET /search.php?q=%27%20OR%201%3D1-- HTTP/1.1",
            "request_target": "/search.php?q=%27%20OR%201%3D1--",
            "uri": "/search.php",
            "query_string": "?q=%27%20OR%201%3D1--",
            "status_code": 200,
        }
    )
    payload = {"meta": {"total_count": 2}, "data": {"security": [traversal_row, sqli_row]}}

    llm_input, candidates, _noise, _filtered_reasons, _filtered_rows = prepare.build_outputs(
        payload,
        min_score=4,
        min_repeat_aggregate=3,
        source_tables=["security"],
    )

    assert len(candidates) == 2
    assert len(llm_input["ip_behavior_aggregates"]) == 1
    aggregate = llm_input["ip_behavior_aggregates"][0]
    assert aggregate["request_count"] == 2
    assert "path_traversal" in aggregate["attack_categories_attempted"]
    assert "sqli" in aggregate["attack_categories_attempted"]
    assert "ip_behavior:multiple_attack_categories" in aggregate["reason_hints"]


def test_viewer_cmdi_uses_existing_generic_category_without_affecting_other_categories() -> None:
    assert viewer.normalize_finding_category(
        {"reason_hints": ["cmdi:semicolon_exec(+4)"], "verdict": "suspicious_command_injection"}
    ) == "generic_candidate"
    assert viewer.normalize_finding_category(
        {"reason_hints": ["cmdi:semicolon_exec(+4)", "traversal:dotdot_slash(+4)"]}
    ) == "generic_candidate"
    assert viewer.normalize_finding_category({"reason_hints": ["traversal:dotdot_slash(+4)"]}) == "path_traversal_candidate"
    assert viewer.normalize_finding_category({"reason_hints": ["sqli:boolean_true_condition"]}) == "sqli_candidate"
    assert viewer.normalize_finding_category({"reason_hints": ["xss:script_tag(+4)"]}) == "xss_candidate"
