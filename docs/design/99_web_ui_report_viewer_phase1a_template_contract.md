# Web UI Report Viewer Phase 1A Template Contract

- 작성일: 2026-05-05
- 문서 역할: Phase 1A 구현 전 `index.html`, `detail.html`, `style.css`의 최소 계약 정의
- 범위: 문서 계약만 정의. 실제 `web/` 구현 파일은 생성하지 않음

---

## 1. 목적

이 문서는 `docs/design/99_web_ui_report_viewer_phase1a_plan.md`의 구현 상세를 보완한다.

Phase 1A 구현 전에 아래를 고정한다.

- report list 화면에서 반드시 보여줄 정보
- report detail 화면에서 반드시 보여줄 정보
- Stage2 quality lint 결과 표시 방식
- severity / verdict / provider badge class 계약
- IP / known asset / raw JSON 표시 원칙
- Jinja2 template 변수 계약
- `style.css` 최소 class 목록

이 문서는 HTML/CSS 구현 코드가 아니라 **template contract**다.

---

## 2. Phase 1A 화면 범위

Phase 1A 포함:

- report list 화면: `/`
- report detail 화면: `/report/{report_id}`
- Stage2 quality lint 결과 표시
- defensive JSON parsing 결과 표시
- localhost-only/read-only viewer

Phase 1A 제외:

- model compare 화면
- pipeline 실행 버튼
- regression 실행 버튼
- report upload
- 검색/필터 UI
- DB/SQLite
- alert/dashboard
- raw JSON full viewer 기본 노출

---

## 3. 공통 UI 원칙

### 3.1 보고서 해석 원칙

UI는 Stage2 report를 새로 해석하지 않는다.

- Stage2 report 본문 문장은 원문을 유지한다.
- UI가 `success`, `confirmed exposure`, `attacker IP`, `real crawler` 같은 새 판정을 만들지 않는다.
- UI badge는 report의 기존 severity/verdict/lint 결과를 시각화할 뿐이다.
- Apache logs-only 한계 문구를 생략하거나 반대로 단정형으로 바꾸지 않는다.

### 3.2 마스킹 원칙

원문 report text와 metadata display는 분리한다.

- report body text: 원문 유지
- source IP summary / known asset list / metadata table: IP 마스킹 적용
- raw JSON full preview: Phase 1A 기본 제외 또는 debug-only 영역으로 제한
- `meta.response_id`, API key, config path, raw secret-like 값은 표시하지 않음

IP 마스킹 기본:

```text
192.168.56.109 -> 192.168.56.***
10.0.1.24 -> 10.0.1.***
```

### 3.3 금지 badge/label

UI에서 새로 만들지 말 것:

```text
Confirmed Exposure
Attacker IP
Real Crawler
Successful Exploit
DB Leak
XSS Executed
Compromised Host
Auth Bypass Success
```

권장 badge/label:

```text
Reported Verdict
Source IP
Known Asset
Crawler-like UA
Attempt Pattern
Needs Review
Lint PASS/WARN/FAIL
Context Only
```

---

## 4. Template data contract

Phase 1A template는 아래 객체를 받는다고 가정한다.

### 4.1 index.html context

```python
{
    "summary": {
        "total_count": int,
        "timeframe_count": int,
        "groups": Dict[str, Dict[str, Any]],
    }
}
```

`summary.groups`의 각 group:

```python
{
    "timeframe": str,
    "reports": List[ReportSummary],
    "openai": Optional[ReportSummary],
    "anthropic": Optional[ReportSummary],
    "has_both": bool,
}
```

`ReportSummary` 최소 필드:

```python
{
    "report_id": str,
    "filename": str,
    "repo_relative_path": str,
    "provider": "openai" | "anthropic" | "unknown",
    "model": str,
    "scenario": str,
    "timeframe": str,
    "generated_at": str,
    "incident_count": int,
    "severity_counts": Dict[str, int],
    "verdict_counts": Dict[str, int],
    "lint": LintSummary,
    "is_valid": bool,
    "error": Optional[str],
}
```

`LintSummary` 최소 필드:

```python
{
    "verdict": "PASS" | "WARN" | "FAIL" | "ERROR" | "UNKNOWN",
    "checked_fields": int,
    "blocker_count": int,
    "warning_count": int,
    "info_count": int,
    "is_error": bool,
}
```

### 4.2 detail.html context

```python
{
    "report": ReportDetail,
    "qa_result": LintResult,
    "incidents": List[Dict[str, Any]],
    "actions": List[Dict[str, Any]],
    "key_findings": List[Dict[str, Any]],
    "source_ips": List[Dict[str, Any]],
}
```

`ReportDetail` 최소 필드:

```python
{
    "report_id": str,
    "filename": str,
    "repo_relative_path": str,
    "provider": str,
    "model": str,
    "generated_at": str,
    "scenario": str,
    "timeframe": str,
    "meta": Dict[str, Any],
    "report": Dict[str, Any],
    "is_valid": bool,
    "error": Optional[str],
}
```

`LintResult`는 현재 `scripts/check_stage2_report_quality.py` output schema를 정규화한 형태다.

```python
{
    "verdict": "PASS" | "WARN" | "FAIL" | "ERROR" | "UNKNOWN",
    "checked_fields": int,
    "blocker_count": int,
    "warning_count": int,
    "info_count": int,
    "blockers": List[Dict[str, Any]],
    "warnings": List[Dict[str, Any]],
    "info": List[Dict[str, Any]],
    "is_error": bool,
}
```

각 lint issue:

```python
{
    "rule": str,
    "path": str,
    "excerpt": str,
    "suggestion": str,
}
```

---

## 5. index.html 계약

### 5.1 반드시 표시할 항목

페이지 상단:

- 제목: `Security Intelligence Console`
- 부제: `Stage2 report viewer / Phase 1A`
- total report count
- timeframe group count
- lint summary aggregate
  - PASS count
  - WARN count
  - FAIL count
  - ERROR count

보고서 그룹 카드:

- timeframe
- scenario
- provider badge
- model
- generated_at
- incident count
- severity mini summary
- lint verdict badge
- detail link by `report_id`
- invalid JSON이면 error badge와 error message 요약

### 5.2 표시 예시

```text
Reports: 42 | Timeframes: 18 | Lint: PASS 12 / WARN 3 / FAIL 1

2026-05-03_19-59-11_to_19-59-39
  [OpenAI] gpt-5.4-mini | incidents: 1 | severity: low=1 | lint: PASS
  path: lab/05-03_H세트R4_산출물/reports/openai-h_r4-check_stage2_report.json
  [상세보기]
```

### 5.3 금지

- filename만으로 detail URL 구성 금지
- absolute filesystem path 노출 금지
- known asset IP 전체 목록 표시 금지
- report content를 요약/재해석해서 새 conclusion 생성 금지

---

## 6. detail.html 계약

### 6.1 반드시 표시할 항목

Header:

- filename
- repo-relative path
- provider
- model
- generated_at
- report_id
- lint verdict badge

Report body:

- overall_assessment
- executive_summary
- key_findings
- notable_incidents table
- notable_source_ips table 또는 summary
- recommended_actions
- confidence_and_limitations
- presentation_takeaway

Quality lint:

- verdict
- checked_fields
- blocker_count
- warning_count
- info_count
- issue list by severity
  - blockers
  - warnings
  - info

### 6.2 notable_incidents table columns

최소 columns:

```text
severity | verdict | title/summary | why_it_matters
```

있으면 표시:

```text
incident_ref | source_ip | request_count | recommended_action
```

단, source_ip는 마스킹한다.

### 6.3 recommended_actions 표시

최소 fields:

```text
priority | action | why
```

priority가 없으면 `P?` 또는 `unknown`으로 표시한다.

### 6.4 lint issue 표시

lint issue는 아래와 같이 표시한다.

```text
[rule] path
excerpt
suggestion
```

`excerpt`는 lint tool이 제공한 값을 그대로 표시하되, HTML escape를 적용한다.

### 6.5 금지

- lint warning을 자동 실패로 표현하지 않음
- blocker가 있어도 “실제 공격 성공”이라고 표현하지 않음
- lint는 wording risk review tool임을 명시
- report 본문의 보수 표현을 삭제하거나 축약하지 않음

---

## 7. style.css class contract

### 7.1 layout

```css
.page
.header
.nav
.container
.section
.card
.card-grid
.table
.table-compact
.meta-grid
```

### 7.2 badges

```css
.badge
.badge-muted
.badge-provider-openai
.badge-provider-anthropic
.badge-provider-unknown
.badge-lint-pass
.badge-lint-warn
.badge-lint-fail
.badge-lint-error
.badge-severity-high
.badge-severity-medium
.badge-severity-low
.badge-severity-info
.badge-context-only
```

### 7.3 issue lists

```css
.issue-list
.issue-blocker
.issue-warning
.issue-info
.issue-rule
.issue-path
.issue-excerpt
.issue-suggestion
```

### 7.4 state

```css
.is-invalid
.is-empty
.is-muted
.is-hidden
```

### 7.5 responsive minimum

Phase 1A는 mobile-first까지 요구하지 않는다. 다만 좁은 화면에서 table이 깨지지 않게 한다.

권장:

```css
.table-wrapper {
  overflow-x: auto;
}
```

---

## 8. Jinja2 rendering rules

- 모든 report text는 HTML escape 대상이다.
- `|safe` 사용 금지. 단, 사전에 sanitize한 내부 static HTML fragment가 있을 때만 별도 검토.
- 없는 field는 `N/A`, `-`, `unknown`으로 표시한다.
- `report.report`가 null이면 empty report로 처리하고 error card를 표시한다.
- `qa_result.is_error`가 true면 report detail 자체는 계속 표시하고 QA 영역만 error로 표시한다.

예시:

```jinja2
{{ report.report.get('overall_assessment') or 'N/A' }}
```

---

## 9. QA lint display contract

현재 lint CLI:

```bash
python3 scripts/check_stage2_report_quality.py \
  --input path/to/stage2_report.json \
  --output /tmp/stage2_quality_lint/<report_id>.json
```

UI는 output JSON을 읽어서 표시한다.

현재 output schema:

```json
{
  "verdict": "PASS",
  "blockers": [],
  "warnings": [],
  "info": [],
  "summary": {
    "checked_fields": 28,
    "blocker_count": 0,
    "warning_count": 0,
    "info_count": 6
  }
}
```

표시 규칙:

- `PASS`: green badge
- `WARN`: amber badge
- `FAIL`: red badge
- `ERROR`: gray badge
- blocker/warning/info counts는 항상 표시
- issue detail은 접을 수 있는 영역으로 둘 수 있음
- Phase 1A에서는 lint 재실행 버튼은 만들지 않음. detail page load 시 read-through/cache 방식으로 실행 가능

---

## 10. Security and privacy contract

Phase 1A는 localhost-only viewer다.

- FastAPI bind: `127.0.0.1`
- external network exposure 금지
- `config/llm.env` 읽기 금지
- report file read-only
- write는 `/tmp/stage2_quality_lint` 같은 lint cache/output에만 허용
- raw report JSON full view는 기본 제외
- repo-relative path는 표시 가능
- absolute path는 표시하지 않음

---

## 11. Phase 1B로 넘길 항목

아래는 template contract에 포함하지 않는다.

- compare.html
- severity delta algorithm
- verdict consensus algorithm
- OpenAI/Anthropic side-by-side rendering
- model agreement/disagreement chart
- search/filter UI

이 항목은 `99_web_ui_report_viewer_plan.md`의 Phase 1B 또는 별도 Phase 1B 문서에서 다룬다.

---

## 12. 완료 기준

Phase 1A 구현 후 아래를 만족해야 한다.

- `/`에서 report list가 보인다.
- `/report/{report_id}`에서 detail page가 보인다.
- lint verdict/count가 표시된다.
- invalid/missing field report도 page 전체를 깨뜨리지 않는다.
- IP metadata는 마스킹된다.
- report body text는 원문 의미를 유지한다.
- UI는 새 보안 판정을 만들지 않는다.
- localhost-only로 실행된다.
- `src/`, `scripts/`, `tests/`, `lab/`는 Phase 1A viewer 구현 때문에 변경하지 않는다.
