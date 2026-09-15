from web.app import (
    _apply_src_ip_display_mode,
    _is_mask_src_ip_enabled,
    sanitize_payload_contexts,
    sanitize_payload_findings,
    sanitize_viewer_payload_summary,
)


def test_sanitize_payload_findings_preserves_raw_src_ip():
    rows = [{"src_ip": "192.168.56.110", "uri": "/view"}]
    out = sanitize_payload_findings(rows)
    assert out[0]["src_ip"] == "192.168.56.110"


def test_sanitize_payload_contexts_preserves_raw_src_ip():
    rows = [{"src_ip": "192.168.56.110", "context_type": "probing_sequence"}]
    out = sanitize_payload_contexts(rows)
    assert out[0]["src_ip"] == "192.168.56.110"


def test_sanitize_viewer_payload_summary_preserves_preview_src_ip():
    summary = {
        "findings_preview": [{"src_ip": "192.168.56.110"}],
        "contexts_preview": [{"src_ip": "192.168.56.110"}],
    }
    out = sanitize_viewer_payload_summary(summary)
    assert out["findings_preview"][0]["src_ip"] == "192.168.56.110"
    assert out["contexts_preview"][0]["src_ip"] == "192.168.56.110"


def test_mask_src_ip_query_flag_parser():
    assert _is_mask_src_ip_enabled("1") is True
    assert _is_mask_src_ip_enabled("true") is True
    assert _is_mask_src_ip_enabled("yes") is True
    assert _is_mask_src_ip_enabled("0") is False
    assert _is_mask_src_ip_enabled(None) is False


def test_apply_src_ip_display_mode_masks_only_display_copy():
    rows = [{"src_ip": "192.168.56.110", "uri": "/view"}]
    masked = _apply_src_ip_display_mode(rows, True)
    assert masked[0]["src_ip"] == "192.168.56.***"
    assert rows[0]["src_ip"] == "192.168.56.110"

    raw = _apply_src_ip_display_mode(rows, False)
    assert raw[0]["src_ip"] == "192.168.56.110"
