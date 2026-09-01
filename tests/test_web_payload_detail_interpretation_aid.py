from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "web" / "templates" / "payload_detail.html"
CSS_FILE = REPO_ROOT / "web" / "static" / "payload-dashboard.css"
DARK_CSS_FILE = REPO_ROOT / "web" / "static" / "theme-dark.css"


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


def test_payload_detail_has_security_standards_targets():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="pd-standards-section"' in text
    assert "Security Standards" in text
    assert "Related WSTG Tests" in text
    assert "Evidence Scope" in text
    assert "Observed attack patterns and standards mappings do not confirm" in text
    assert "standardsMappingItems" in text
    assert "renderStandardsMapping" in text
    assert "relationshipLabel" in text
    assert "evidenceScopeLabel" in text
    assert "payload-standards is-hidden" in text
    assert "textContent" in text
    assert "|safe" not in text


def test_payload_detail_security_standards_avoids_confirmed_vulnerability_wording():
    text = TEMPLATE.read_text(encoding="utf-8")
    forbidden = [
        "Detected Vulnerability",
        "Confirmed Vulnerability",
        "Confirmed OWASP Vulnerability",
        "Successful Exploit",
        "Vulnerability Found",
        "취약점 발견",
        "취약점 확인",
        "공격 성공",
        "침해 성공",
        "익스플로잇 성공",
    ]
    for phrase in forbidden:
        assert phrase not in text


def test_payload_dashboard_has_security_standards_styles():
    text = CSS_FILE.read_text(encoding="utf-8")
    assert ".payload-standards" in text
    assert ".payload-standard-group" in text
    assert ".payload-standard-item" in text
    assert ".payload-badge-standard-relationship" in text
    assert ".payload-badge-standard-scope" in text
    assert ".payload-standards-boundary" in text


def test_payload_detail_has_aggregate_security_standards_summary_structure():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="security-standards-summary"' in text
    assert "Security Standards Summary" in text
    assert "Mapped findings" in text
    assert "OWASP-related Observed Categories" in text
    assert "CWE Mapping Breakdown" in text
    assert "Related WSTG Test Scenarios" in text
    assert "Other Standards Mappings" in text
    assert "Category counts should not be summed as a total incident count" in text
    assert text.index('id="security-standards-summary"') < text.index("Report Summary")


def test_payload_dashboard_has_responsive_light_and_dark_summary_styles():
    css = CSS_FILE.read_text(encoding="utf-8")
    dark_css = DARK_CSS_FILE.read_text(encoding="utf-8")
    assert ".security-standards-summary" in css
    assert ".security-standard-row-list" in css
    assert ".security-standard-row-name" in css
    assert "overflow-wrap: anywhere" in css
    assert "@media (max-width:" in css
    assert '[data-theme="dark"] .security-standards-summary.card' in dark_css
    assert '[data-theme="dark"] .security-standard-relationship' in dark_css
