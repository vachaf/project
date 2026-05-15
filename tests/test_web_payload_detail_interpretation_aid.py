from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "web" / "templates" / "payload_detail.html"
CSS_FILE = REPO_ROOT / "web" / "static" / "payload-dashboard.css"


def test_payload_detail_has_interpretation_aid_targets():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="pd-observability-badges"' in text
    assert 'id="pd-interpretation-notes"' in text


def test_payload_detail_maps_observability_hints():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "observability:reverse_proxy_candidate" in text
    assert "observability:fallback_200_candidate" in text
    assert "traversal:html_fallback_like_response" in text


def test_payload_dashboard_has_observability_badge_styles():
    text = CSS_FILE.read_text(encoding="utf-8")
    assert ".payload-badge-observability" in text
    assert ".payload-badge-observability-fallback" in text
    assert ".payload-badge-observability-boundary" in text
