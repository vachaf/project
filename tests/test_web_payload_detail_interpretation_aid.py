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
    assert "관찰된 패턴과 보안 표준 매핑은 취약점이나 성공적인 악용을 입증하지 않습니다" in text
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
        "파일 노출 성공",
        "로그인 성공",
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
    assert "분류별 건수를 전체 incident 수로 합산하지 않습니다" in text
    assert text.index("Report Summary") < text.index("Event Timeline")
    assert text.index("Event Timeline") < text.index('id="security-standards-summary"')


def test_payload_detail_has_approved_presentation_hierarchy_and_role_guide():
    text = TEMPLATE.read_text(encoding="utf-8")
    report_index = text.index("Report Summary")
    metrics_index = text.index('class="payload-summary-cards"')
    roles_index = text.index('id="payload-role-guide-title"')
    findings_index = text.index('id="payload-key-findings-title"')
    timeline_index = text.index("Event Timeline")
    standards_index = text.index('id="security-standards-summary"')
    contexts_index = text.index("해석 정보 미리보기")

    assert report_index < metrics_index < roles_index < findings_index
    assert findings_index < timeline_index < standards_index < contexts_index
    assert "주요 탐지 요청, 해석 정보, 주변 참고 요청은 서로 다른 역할입니다" in text
    assert "직접 검토 대상으로 선택한 개별 요청" in text
    assert "맥락·집계 정보" in text
    assert "Finding으로 승격하여 표시하지 않습니다" in text


def test_payload_detail_prioritizes_artifact_text_without_rewriting_report_conclusion():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "{{ overall_assessment }}" in text
    assert "{{ presentation_takeaway }}" in text
    assert "{{ item.get('title') or '제목 없는 Finding' }}" in text
    assert "{{ item.get('detail') }}" in text
    assert "safe_report_text(overall_assessment)" not in text
    assert "safe_report_text(presentation_takeaway)" not in text
    assert "safe_report_text(item.get('title')" not in text
    assert "safe_report_text(item.get('detail'))" not in text


def test_payload_detail_has_projector_readable_selected_finding_fields_and_boundary():
    template = TEMPLATE.read_text(encoding="utf-8")
    css = CSS_FILE.read_text(encoding="utf-8")
    assert "선택한 탐지 요청 상세" in template
    assert 'class="payload-detail-status-grid"' in template
    assert 'class="payload-request-grid"' in template
    assert "Apache logs-only evidence boundary" in template
    assert "성공적인 악용이나 침해의 증거가 아닙니다" in template
    assert ".payload-report-lead-grid" in css
    assert ".payload-role-grid" in css
    assert ".payload-detail-status-grid" in css
    assert ".payload-request-grid" in css


def test_payload_detail_is_korean_first_with_canonical_terms_secondary():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Apache 로그 기반 보안 분석 보고서" in text
    assert "보고서 요약" in text and "Report Summary" in text
    assert "종합 평가" in text and "Overall Assessment" in text
    assert "핵심 결론" in text and "Presentation Takeaway" in text
    assert "분석 요청 흐름" in text and "Event Timeline" in text
    assert "보안 표준 연계" in text and "Security Standards" in text
    assert "읽기 전용" in text and "read-only" in text
    assert "성공 여부 추론 안 함" in text and "no success inferred" in text
    assert "해석 전용" in text and "context-only" in text
    assert 'class="payload-label-secondary"' in text


def test_payload_dashboard_uses_normal_flow_detail_and_separated_timeline_columns():
    css = CSS_FILE.read_text(encoding="utf-8")
    assert ".payload-detail-content" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert ".payload-detail-status-item:nth-child(3)" in css
    assert ".payload-detail-status-item:nth-child(4)" in css
    assert "max-height: none" in css
    assert "overflow: visible" in css
    assert "min-width: 980px" in css
    assert ".payload-event-table th + th" in css


def test_payload_dashboard_has_responsive_light_and_dark_summary_styles():
    css = CSS_FILE.read_text(encoding="utf-8")
    dark_css = DARK_CSS_FILE.read_text(encoding="utf-8")
    assert ".security-standards-summary" in css
    assert ".security-standard-row-list" in css
    assert ".security-standard-row-name" in css
    assert "overflow-wrap: anywhere" in css
    assert "@media (max-width:" in css
    assert "var(--pd-surface-soft)" in css
    assert '[data-theme="dark"] .security-standards-summary.card' in dark_css
    assert '[data-theme="dark"] .security-standard-relationship' in dark_css
