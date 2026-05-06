# Web UI Report Viewer Phase 2A Filter Plan

- 작성일: 2026-05-06
- 문서 역할: Web UI Report Viewer Phase 2A read-only search/filter/navigation 설계
- 기준 상태: Phase 1B 마감 가능 상태, Phase 2 후보 비교 완료
- 결론 요약: Phase 2A는 execution console이 아니라 read-only report 탐색성 개선으로 제한한다.

---

## 1. 목적

Phase 2A의 목적은 report 수가 늘어났을 때 Web UI Report Viewer의 목록 탐색성을 높이는 것이다.

Phase 2A는 다음 범위로 제한한다.

```text
read-only search/filter/navigation 개선
```

Phase 2A는 다음이 아니다.

```text
pipeline execution integration
execution console
stateful dashboard
external deployment
```

즉, 이 문서는 `/` list page에서 report/group을 더 빨리 찾기 위한 filter contract와 UI/data 설계를 정의한다.

---

## 2. 전제

현재 전제:

- Phase 1A list/detail viewer 구현 완료
- Phase 1B OpenAI/Anthropic compare view 구현 완료
- Compare / Compare partial UX 구현 완료
- missing provider placeholder / `Missing report` / `N/A` 처리 완료
- Compare Metrics 상단 배치 완료
- provider panel `key_findings` / `recommended_actions` `<details>` 접기 완료
- small viewport overflow 기본 확인 완료
- 공식 검증 축 정리 완료

공식 검증 축:

```text
scripts/check_prepare_regression.py
scripts/check_stage_dryrun_regression.py
scripts/check_stage2_report_quality.py
```

QA v4 `scripts/run_qa_check_production_v4.py`는 공식 regression/lint 대체가 아니라 보조/실험 스크립트로 관리한다.

---

## 3. 비목표

Phase 2A에서 하지 않는다.

- pipeline run button
- provider execution selection
- dry-run toggle
- live progress
- regression run button
- report rewrite/regeneration
- output cleanup button
- SQLite history
- alert/dashboard
- comparison history trend
- external deployment
- Docker
- raw JSON full search
- report body full-text search
- source IP 원문 검색
- UI가 새 보안 판정 생성
- React/npm/webpack 도입
- 외부 CDN 도입

Phase 2A는 기존 report 파일을 읽고 필터링할 뿐이다.

---

## 4. Phase 2A Filter 우선순위

수홍님 제안 기준으로 Phase 2A filter 우선순위는 다음과 같다.

| 순위 | 필터 | 분류 | 난이도 | 이유 |
|---:|---|---|---|---|
| 1 | lint verdict | MVP | low | 검증 콘솔에서 `FAIL`/`WARN` report만 빠르게 찾는 요구가 크다. 기존 lint verdict 필드를 사용할 수 있다. |
| 2 | pair status | MVP | low | compare 가능한 group과 partial group을 구분하는 핵심 탐색 기준이다. 기존 `has_both` 성격의 group field를 활용할 수 있다. |
| 3 | free text `q` | MVP | medium | `h_r4`, `c_set`, report id 일부, filename 일부로 빠르게 찾는 요구를 충족한다. |
| 4 | provider | 선택 | low | OpenAI / Anthropic / unknown만 보고 싶을 때 유용하다. 다만 compare view에서도 provider 구분이 가능하므로 MVP 이후 추가 가능하다. |
| 5 | scenario select | 보류 | low~medium | option 수가 많아질 경우 dropdown UX가 나빠질 수 있다. Phase 2A에서는 `q` 검색으로 대체하고, option 수 확인 후 Phase 2B 후보로 검토한다. |

---

## 5. Minimal Viable Filter Set

Phase 2A MVP는 아래 3개로 제한한다.

```text
MVP:
- lint verdict
- pair status
- free text q
```

선택 후보:

```text
Optional:
- provider
```

보류 후보:

```text
Deferred:
- scenario select
```

이유:

- MVP 3개만으로 “검토해야 할 report 찾기”, “compare 가능한 group 찾기”, “특정 scenario/report id 찾기”를 대부분 해결할 수 있다.
- provider filter는 낮은 난이도지만 MVP 구현 이후 추가해도 된다.
- scenario select는 scenario option 수를 먼저 확인해야 한다.

---

## 6. Query Parameter Contract

Phase 2A는 서버-side filtering을 query parameter 기반으로 구현한다.

### 6.1 MVP parameters

| Parameter | Values | 설명 |
|---|---|---|
| `q` | free text | filename / scenario / report_id 대상 부분 문자열 검색 |
| `lint` | `pass` / `warn` / `fail` / `error` | Stage2 quality lint verdict filter |
| `pair` | `both` / `partial` | both-provider group 또는 partial group filter |

### 6.2 Optional parameter

| Parameter | Values | 설명 |
|---|---|---|
| `provider` | `openai` / `anthropic` / `unknown` | 특정 provider report가 포함된 group/report filter |

### 6.3 Deferred parameter

| Parameter | Values | 설명 |
|---|---|---|
| `scenario` | scenario key | scenario option 수 확인 후 추가 여부 판단 |

### 6.4 URL examples

```text
/?q=xss
/?q=h_r4
/?q=afbtqV9
/?lint=fail
/?lint=warn
/?pair=both
/?pair=partial
/?provider=openai
/?q=xss&lint=warn&pair=partial
```

### 6.5 Query semantics

- 여러 filter가 동시에 지정되면 AND 조건으로 처리한다.
- 값이 비어 있으면 해당 filter는 적용하지 않는다.
- unknown/invalid value는 무시하거나 safe default로 처리한다.
- filter result count는 report/group 수이지 실제 incident 수가 아니다.

---

## 7. Free Text Search Target Fields

### 7.1 포함 대상

Phase 2A `q` 검색 대상은 아래 3개로 제한한다.

```text
filename
scenario
report_id
```

이유:

- `filename`: `openai-h_r4_scanner`, 날짜/timeframe, provider 단서가 포함되어 있어 사용자가 가장 직관적으로 검색할 수 있다.
- `scenario`: `h_r4`, `c_set`, `e_r2b` 같은 실험/공격 유형 탐색에 유용하다.
- `report_id`: detail/compare URL에서 보이는 hash 기반 id 일부로 재탐색할 수 있다.

### 7.2 제외 대상

Phase 2A에서는 아래를 검색하지 않는다.

```text
raw JSON 전체
report body 전체
source IP 원문
absolute filesystem path
report_title
model
timeframe 단독 field
provider field
```

제외 이유:

- raw JSON/report body full search는 성능과 노출 범위가 커진다.
- source IP 원문 검색은 metadata 노출 제한 원칙과 충돌할 수 있다.
- report_title은 Stage2 report JSON에 항상 안정적으로 존재한다고 가정하지 않는다.
- model/provider는 dropdown 또는 card 표시로 충분하다.
- timeframe은 filename에 이미 포함되는 경우가 많아 MVP에서는 중복이다.

---

## 8. UI Layout

Phase 2A UI는 `/` list page 상단에 compact filter form을 추가하는 방식으로 시작한다.

### 8.1 Form controls

MVP controls:

```text
q input
lint select
pair select
Apply button
Reset link
```

Optional controls:

```text
provider select
```

Deferred controls:

```text
scenario select
```

### 8.2 Result count

필수로 표시한다.

예시:

```text
Showing 23 of 116 reports
Showing 8 of 40 groups
```

표현 주의:

- result count는 UI에 표시되는 report/group 개수다.
- 실제 공격/incident 수로 해석하지 않는다.

### 8.3 Active filter chips

필수로 표시한다.

예시:

```text
[Lint: FAIL ×] [Pair: partial ×] [Q: "h_r4" ×] [Clear all]
```

각 chip은 해당 filter만 제거한 URL로 연결할 수 있다.

### 8.4 No-result state

filter 결과가 없을 때 명확히 표시한다.

예시:

```text
No reports match the current filters.
Try clearing filters or changing the search text.
```

No-result 상태에서도 기존 page layout이 깨지지 않아야 한다.

---

## 9. Data / Template Contract

Phase 2A에서 index template에 전달할 context 후보는 다음과 같다.

```python
{
    "groups": list,
    "reports": list,
    "filters": {
        "q": str | None,
        "lint": str | None,
        "pair": str | None,
        "provider": str | None,
    },
    "filter_options": {
        "lint": ["pass", "warn", "fail", "error"],
        "pair": ["both", "partial"],
        "provider": ["openai", "anthropic", "unknown"],
    },
    "result_count": int,
    "unfiltered_count": int,
    "active_filter_chips": list,
}
```

`scenario`는 Phase 2A MVP에서 제외한다. 이후 option 수가 관리 가능한 수준이면 아래처럼 확장할 수 있다.

```python
"scenario": str | None
"filter_options": {"scenario": [...]} 
```

---

## 10. Implementation Touch Points

예상 수정 파일:

```text
web/app.py
web/services/report_loader.py
web/templates/index.html
web/static/style.css
```

가능하면 수정하지 않는다.

```text
src/
scripts/
tests/fixtures/
tests/expected/
lab/
reports/
config/
```

### 10.1 App layer

`web/app.py`에서 query parameter를 parse하고, filter state를 template에 전달한다.

확인할 점:

- 기존 `/` route 동작 유지
- 기존 report group generation 유지
- existing `Detail`, `Compare`, `Compare partial` link 유지
- filter 적용 후에도 `timeframe_id` 안정성 유지

### 10.2 Report loader / filtering helper

필터 로직은 별도 helper로 두는 것이 좋다.

후보:

```python
normalize_filter_value(value: str | None) -> str | None
report_matches_query(report, q: str) -> bool
group_matches_filters(group, filters) -> bool
build_filter_options(groups, reports) -> dict
build_active_filter_chips(filters) -> list
```

단, Phase 2A에서 과도한 abstraction은 피한다.

### 10.3 Template

`index.html` 상단에 filter form을 추가한다.

필수:

- 현재 query parameter value 보존
- selected option 유지
- result count 표시
- active filter chips 표시
- no-result state 표시

### 10.4 CSS

Plain CSS만 사용한다.

필요 class 후보:

```css
.filter-panel
.filter-form
.filter-row
.filter-field
.filter-actions
.filter-chip-list
.filter-chip
.result-count
.no-result-card
```

900px 이하에서는 form controls가 자연스럽게 wrap 또는 stack되어야 한다.

---

## 11. Safety / Apache Logs-Only Guard

Phase 2A filter는 report 탐색 도구다. 새 분석기나 새 판정 엔진이 아니다.

금지:

- filter result를 “실제 공격 수”로 표현
- provider별 결과 차이를 실제 사건 차이로 단정
- lint verdict를 공격 성공/실패 판정으로 표현
- source IP 원문 검색/노출
- raw JSON 전체 검색
- report text rewrite
- model comparison summary를 새로 생성
- `Confirmed Exposure`, `Attacker IP`, `XSS Executed`, `Successful Exploit` 같은 새 badge 생성

허용:

- `Showing N of M reports`
- `Lint: FAIL`
- `Pair: both`
- `Provider: openai`
- `Q: h_r4`
- `No reports match the current filters`

---

## 12. Verification Plan

문법/기본 검증:

```bash
python3 -m py_compile web/config.py web/app.py web/services/report_loader.py web/services/qa_runner.py web/services/report_comparator.py
```

Jinja2 template load:

```bash
python3 << 'PY'
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader(Path("web/templates")))
for name in ["base.html", "index.html", "detail.html", "compare.html"]:
    env.get_template(name)
    print(f"OK {name}")
PY
```

기존 regression:

```bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python3 -m pytest tests/test_stage2_report_quality.py
```

브라우저 확인:

```bash
python -m uvicorn web.app:app --host 127.0.0.1 --port 8768
```

확인 URL:

```text
/
/?q=xss
/?q=h_r4
/?lint=pass
/?lint=warn
/?lint=fail
/?pair=both
/?pair=partial
/?provider=openai
/?q=xss&lint=warn&pair=partial
/report/{report_id}
/compare/{timeframe_id}
```

---

## 13. Completion Criteria

Phase 2A 완료 기준:

- `q` filter가 filename / scenario / report_id 대상으로 동작한다.
- `lint` filter가 pass / warn / fail / error 기준으로 동작한다.
- `pair` filter가 both / partial 기준으로 동작한다.
- provider filter를 포함할 경우 openai / anthropic / unknown 기준으로 동작한다.
- 여러 filter를 조합하면 AND 조건으로 적용된다.
- Apply button이 현재 filter state를 반영한다.
- Reset link가 모든 filter를 제거한다.
- active filter chips가 표시된다.
- 개별 chip 제거가 가능하거나, 최소한 Clear all이 제공된다.
- result count가 표시된다.
- no-result state가 깨지지 않는다.
- 기존 `Detail`, `Compare`, `Compare partial` link가 유지된다.
- pair ready / missing pair 표시가 유지된다.
- missing provider를 `0 incidents`로 해석하지 않는다.
- 900px 이하에서 filter form이 깨지지 않는다.
- report files read-only 원칙이 유지된다.
- UI가 새 보안 판정을 생성하지 않는다.

---

## 14. Open Questions

Phase 2A 구현 전 또는 구현 중 확인할 질문:

1. provider filter를 MVP에 포함할 것인가, 아니면 1차 구현 후 추가할 것인가?
2. scenario option 수는 몇 개인가?
3. scenario select가 dropdown으로 관리 가능한가, 아니면 q 검색으로 충분한가?
4. result count 기준은 report 수인가 group 수인가, 둘 다 표시할 것인가?
5. active filter chip에서 개별 제거까지 구현할 것인가, Clear all만 제공할 것인가?
6. no-result 상태에서 전체 filter reset만 제공할 것인가, 추천 filter 완화 문구를 추가할 것인가?

현재 추천:

```text
MVP에서는 lint + pair + q를 먼저 구현한다.
provider는 구현 난이도가 낮으므로 시간이 되면 함께 포함한다.
scenario select는 option 수 확인 전까지 보류한다.
```

---

## 15. 후속 후보

Phase 2A 이후 필요성이 확인되면 아래를 검토한다.

### Phase 2B 후보

- scenario select
- comparison history trend
- file-scan 기반 lightweight trend
- saved filter preset
- lint issue navigation 고도화

### Phase 2C 후보

- pipeline run button
- dry-run toggle
- live progress
- regression run button
- report regeneration

Phase 2C는 read-only viewer 원칙을 변경하므로 별도 risk review가 필요하다.

---

## 16. 참고 문서

- `docs/design/99_web_ui_report_viewer_plan.md`
- `docs/design/99_web_ui_report_viewer_phase1a_plan.md`
- `docs/design/99_web_ui_report_viewer_phase1a_template_contract.md`
- `docs/design/99_web_ui_report_viewer_phase1b_plan.md`
- `docs/design/99_web_ui_report_viewer_ui_polish_plan.md`
- `docs/design/99_web_ui_report_viewer_phase2_candidate_review.md`
- `docs/planning/99_비교실험_후속개선_TODO.md`
- `scripts/README.md`
