# Web UI Report Viewer Phase 1B Plan

- 작성일: 2026-05-05
- 문서 역할: Phase 1B 모델 비교 화면 설계
- 전제: Phase 1A report list/detail + Stage2 quality lint display 구현 완료
- 범위: OpenAI / Anthropic Stage2 report 비교 화면 설계. 실제 `web/` 구현은 별도 커밋에서 수행

---

## 1. 목적

Phase 1B의 목적은 같은 timeframe에 생성된 OpenAI / Anthropic Stage2 보고서를 한 화면에서 비교하는 것이다.

Phase 1A가 해결한 문제:

- Stage2 report JSON 목록 조회
- report detail 표시
- Stage2 quality lint verdict/count 표시
- report_id 기반 안전 URL
- repo-relative path 기반 report 식별

Phase 1B가 해결할 문제:

- 같은 시간대의 두 provider report를 나란히 읽어야 하는 불편
- severity / verdict / key finding / recommended action 차이를 수동으로 찾아야 하는 불편
- 모델별 경향을 사람이 빠르게 파악하기 어려운 문제

---

## 2. 비목표

Phase 1B에서 하지 않는다.

- React / npm / webpack 도입
- hardcoded `REPORTS` 데이터 사용
- UI가 새 security verdict 생성
- UI가 모델 성향 분석 문장을 새로 생성
- pipeline 실행 버튼
- regression 실행 버튼
- report upload
- search/filter
- DB/SQLite
- alert/dashboard
- 외부 네트워크 노출
- 모바일 전용 UX 고도화
- 화려한 애니메이션
- 다크모드/라이트모드 전환
- `src/`, `scripts/`, `tests/`, `lab/` 수정

Phase 1B는 기존 Stage2 report JSON과 quality lint 결과를 **비교·시각화**할 뿐이다.

---

## 3. 디자인 참고 원칙

팀원 mockup은 Phase 1B visual reference로 사용한다.

참고할 요소:

- dark dashboard 스타일
- 좌측 timeframe sidebar
- provider별 색상 구분
  - OpenAI: blue 계열
  - Anthropic/Claude: orange 계열
- 좌우 provider card
- severity badge
- incident count / high severity / verdict type / key finding count 비교 bar
- compact metric summary
- missing provider panel을 흐리게 처리하는 시각적 표현
- 좁은 화면에서 좌우 panel이 위아래로 쌓이는 responsive stack

가져오지 않을 요소:

- React component 구조
- inline style 대량 사용
- hardcoded `REPORTS` 배열
- source IP 원문 표시
- UI가 자체 작성한 “모델 성향 분석” 문장
- UI가 `공격 성공`, `confirmed exposure`, `attacker IP` 같은 새 판정 badge 생성

---

## 4. Phase 1B 포함 범위

포함:

- `/compare/{timeframe_id}` HTML route
- 선택 사항: `/api/compare/{timeframe_id}` sanitized JSON route
- timeframe group list에서 compare link 표시
- OpenAI / Anthropic report pair 탐색
- provider별 report summary card
- incident count 비교
- severity distribution 비교
- verdict distribution 비교
- key findings count/severity 비교
- recommended actions 비교
- Stage2 quality lint verdict/count 비교
- missing pair 처리
- narrow viewport에서 compare panel stack 처리

제외:

- incident semantic matching 고도화
- natural language diff 생성
- LLM을 이용한 report comparison
- report rewrite
- quality lint rule tuning
- Phase 2 pipeline execution

---

## 5. Data contract

Phase 1B는 Phase 1A의 `ReportLoader` 결과를 확장해 사용한다.

### 5.1 timeframe_id

`timeframe_id`는 report path가 아니라 group identifier다.

권장 생성 기준:

```python
make_timeframe_id(timeframe: str, scenario: str) -> str
```

- repo path를 노출하지 않는다.
- URL-safe해야 한다.
- 같은 timeframe/scenario group을 안정적으로 찾을 수 있어야 한다.
- 구현은 hash 또는 slug 중 하나로 선택한다.

권장:

```python
hashlib.sha256(f"{scenario}|{timeframe}".encode("utf-8")).hexdigest()[:16]
```

### 5.2 CompareGroup

```python
{
    "timeframe_id": str,
    "timeframe": str,
    "scenario": str,
    "openai": Optional[ReportSummary],
    "anthropic": Optional[ReportSummary],
    "has_both": bool,
}
```

### 5.3 CompareResult

```python
{
    "timeframe_id": str,
    "timeframe": str,
    "scenario": str,
    "openai": Optional[ReportDetail],
    "anthropic": Optional[ReportDetail],
    "metrics": {
        "incident_count": {"openai": Optional[int], "anthropic": Optional[int]},
        "high_severity_count": {"openai": Optional[int], "anthropic": Optional[int]},
        "severity_counts": {"openai": Optional[dict], "anthropic": Optional[dict]},
        "verdict_counts": {"openai": Optional[dict], "anthropic": Optional[dict]},
        "key_finding_count": {"openai": Optional[int], "anthropic": Optional[int]},
        "recommended_action_count": {"openai": Optional[int], "anthropic": Optional[int]},
        "lint": {"openai": Optional[LintSummary], "anthropic": Optional[LintSummary]},
    },
    "differences": {
        "severity_delta": list,
        "verdict_delta": list,
        "lint_delta": list,
        "missing_provider": list,
    }
}
```

Missing provider의 metric은 `0`이 아니라 `None`/`N/A`로 취급한다. 보고서 부재는 incident 0건이 아니라 **해당 provider report가 없는 상태**다.

---

## 6. Compare route design

### 6.1 HTML route

```text
GET /compare/{timeframe_id}
```

동작:

1. `timeframe_id`로 group 조회
2. OpenAI / Anthropic report pair 로드
3. Stage2 quality lint result를 각 report에 대해 로드 또는 실행
4. compare metrics 생성
5. `compare.html` 렌더링

pair가 없을 때:

- 한쪽 provider만 있어도 page는 렌더링한다.
- 없는 provider panel은 삭제하지 않고 비어 있는 panel로 유지한다.
- 없는 provider panel에는 `Missing report` 또는 `No report for this provider`를 표시한다.
- panel은 muted/grayscale/opacity/dashed border 스타일을 사용한다.
- `has_both=false` badge를 표시한다.
- missing provider를 incident 0건, severity 0건, verdict 0건으로 해석하지 않는다.
- 비교 bar에서는 missing provider 값을 `N/A`로 표시한다.

### 6.2 Optional JSON route

```text
GET /api/compare/{timeframe_id}
```

반환은 sanitized summary만 포함한다.

- raw full report JSON 그대로 반환하지 않음
- absolute filesystem path 미노출
- IP metadata 마스킹
- missing provider는 `null` 또는 명시적 `missing=true`로 표현

---

## 7. Comparison metrics

### 7.1 Incident count

```text
openai.notable_incidents count
anthropic.notable_incidents count
```

주의:

- count 차이는 모델 출력 차이일 뿐, 실제 사건 수 차이로 단정하지 않는다.
- UI label은 `Reported incident count` 또는 `Report incident count`로 둔다.
- provider report가 없으면 `0`이 아니라 `N/A`로 표시한다.

### 7.2 Severity distribution

Severity count buckets:

```text
critical / high / medium / low / info / unknown
```

표시:

- provider별 bar
- badge summary
- high severity count highlight

주의:

- severity 차이를 “어느 모델이 맞다”로 표현하지 않는다.
- label은 `Severity distribution in report`를 사용한다.
- provider report가 없으면 빈 bar가 아니라 muted `N/A` 상태로 표시한다.

### 7.3 Verdict distribution

표시:

- provider별 verdict count
- provider별 unique verdict type count
- 양쪽에만 있는 verdict / 한쪽에만 있는 verdict 구분

주의:

- verdict name은 report JSON 원문 기준으로 표시한다.
- UI가 verdict taxonomy를 새로 변환하지 않는다.

### 7.4 Key findings

비교 항목:

- key_findings count
- key_findings severity distribution
- title list

주의:

- key finding text는 원문 유지.
- UI가 key finding을 새로 요약하지 않는다.

### 7.5 Recommended actions

비교 항목:

- action count
- priority distribution if priority exists
- action text list

주의:

- UI가 권고 조치 우선순위를 새로 매기지 않는다.
- 없는 priority는 `unknown`으로 표시한다.

### 7.6 Stage2 quality lint

비교 항목:

- lint verdict
- blocker_count
- warning_count
- info_count
- top issue rules

주의:

- lint warning은 자동 실패가 아니다.
- blocker도 wording risk review 대상이지 실제 공격 성공 판정이 아니다.

---

## 8. compare.html template contract

### 8.1 Context

```python
{
    "group": CompareGroup,
    "comparison": CompareResult,
}
```

### 8.2 Page layout

상단:

- timeframe
- scenario
- has_both badge
- OpenAI / Anthropic provider availability
- link back to `/`

좌측/우측 provider panels:

- provider badge
- model
- generated_at
- report_id
- detail link
- lint badge
- incident count
- severity badges
- verdict badges
- overall_assessment
- key findings list
- recommended actions list

Missing provider panel:

- panel 자체는 유지한다.
- provider 색상 테마는 유지하되 opacity를 낮춘다.
- dashed border 또는 muted background를 사용한다.
- `Missing report` badge를 표시한다.
- detail link는 표시하지 않는다.
- metrics는 `N/A`로 표시한다.

중앙/하단 compare area:

- incident count compare bar
- high severity compare bar
- verdict type count compare bar
- key finding count compare bar
- lint blocker/warning/info compare bar
- verdict distribution table
- severity distribution table

### 8.3 Visual style

디자인 참고:

- dark theme는 선택 가능하되 Phase 1A style과 충돌하지 않게 한다.
- provider 색상:
  - OpenAI: blue
  - Anthropic: orange
- severity badge는 Phase 1A class를 재사용한다.
- lint badge도 Phase 1A class를 재사용한다.
- missing provider panel은 opacity/dashed border/muted tone으로 처리한다.

새 class 후보:

```css
.compare-layout
.compare-panel
.compare-panel-openai
.compare-panel-anthropic
.compare-panel-missing
.compare-metrics
.compare-bar
.compare-bar-row
.compare-bar-label
.compare-bar-track
.compare-bar-fill-openai
.compare-bar-fill-anthropic
.compare-bar-value-na
.compare-delta-table
.compare-empty-panel
.badge-missing-report
```

---

## 9. Responsive / narrow viewport behavior

Phase 1B는 완전한 모바일 전용 UX를 목표로 하지 않는다. 하지만 좁은 브라우저에서 좌우 비교 layout이 깨지지 않도록 기본 responsive stack은 포함한다.

기본 CSS contract:

```css
.compare-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.compare-panel {
  min-width: 0;
}

@media (max-width: 900px) {
  .compare-layout {
    grid-template-columns: 1fr;
  }
}

.compare-metrics,
.compare-table,
.compare-bar {
  min-width: 0;
}

.table-wrapper,
.compare-table-wrapper {
  overflow-x: auto;
}
```

후순위:

- 모바일 전용 navigation
- touch gesture
- animation-heavy transitions
- dark/light theme toggle

---

## 10. Sidebar / navigation

Phase 1B에서는 목록 화면에서 compare link를 추가한다.

`index.html` group card에 표시:

- `Detail` link for each report
- `Compare` link if `has_both=true`
- `Compare unavailable` 또는 `Missing pair` if pair missing

선택 사항:

- compare page 안에 timeframe sidebar를 추가할 수 있다.
- 단, Phase 1B 최소 구현에서는 `index.html`의 compare link만으로 충분하다.

---

## 11. Apache logs-only UI guard

Phase 1B도 새 분석기가 아니다.

금지:

- “OpenAI가 맞음 / Claude가 틀림” 식 판정
- “confirmed exploit” badge
- “attacker IP” badge
- “real crawler” badge
- `200`, `bytes`, `content-type` 기반 success badge
- 모델 간 차이를 실제 사건 차이로 단정
- missing provider를 `0 incidents`로 단정

허용:

- “OpenAI report uses higher severity”
- “Anthropic report has fewer notable incidents”
- “Verdict labels differ”
- “Lint warning count differs”
- “Provider report missing”
- “Needs manual review”

---

## 12. Implementation touch points

예상 수정 파일:

```text
web/app.py
web/services/report_loader.py
web/services/report_comparator.py
web/templates/index.html
web/templates/compare.html
web/static/style.css
```

예상 생성 파일:

```text
web/services/report_comparator.py
web/templates/compare.html
```

수정 금지:

```text
src/
scripts/
tests/
lab/
reports/
config/
```

---

## 13. Verification plan

문법/기본 검증:

```bash
python3 -m py_compile web/config.py web/app.py web/services/report_loader.py web/services/qa_runner.py web/services/report_comparator.py
```

Jinja2 template 검증:

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

route sanity:

```bash
python3 << 'PY'
from web.app import app
for route in app.routes:
    print(getattr(route, "path", None))
PY
```

기존 regression:

```bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python3 -m pytest tests/test_stage2_report_quality.py
```

수동 확인:

```bash
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

확인 URL:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/compare/{timeframe_id}
```

---

## 14. Completion criteria

Phase 1B 완료 기준:

- `index.html`에서 pair가 있는 timeframe에 compare link가 표시된다.
- pair가 없는 timeframe은 missing pair 상태가 직관적으로 보인다.
- `/compare/{timeframe_id}`가 렌더링된다.
- OpenAI / Anthropic report가 좌우 또는 명확한 두 panel로 표시된다.
- 한쪽 provider가 없어도 muted missing panel로 표시되고 page가 깨지지 않는다.
- incident count / severity / verdict / key finding / recommended action / lint count 차이가 보인다.
- missing provider metric은 `0`이 아니라 `N/A`로 표시된다.
- 좁은 화면에서 compare panel이 위아래로 stack된다.
- UI가 새 security conclusion을 만들지 않는다.
- IP/metadata 마스킹 원칙을 유지한다.
- `src/`, `scripts/`, `tests/`, `lab/`는 변경하지 않는다.

---

## 15. 2026-05-06 브라우저 점검 결과 반영

### 확인된 정상 항목
- `/` list page 기본 표시 정상
- `/report/{report_id}` detail page 기본 표시 정상
- `/compare/{timeframe_id}` compare metrics 표시 정상
- Known Asset masking 유지
- Compare Metrics가 provider panels보다 위에 표시됨
- Pair ready / Compare link 동작 확인

### 추가 polish 필요 항목
- provider가 하나뿐인 timeframe group에서 오른쪽 카드 영역이 비어 보여 partial 상태가 시각적으로 어색함
- list page에서도 missing provider 상태를 명확히 보여줄 필요가 있음
- 해결 후보:
  1. partial group에서는 missing provider placeholder card를 표시
  2. 또는 single-provider group은 single-column/full-width card로 표시
- 권장안: missing provider placeholder card 표시
  - compare page의 `Missing report` / `N/A` 원칙과 일관됨
  - missing을 `0 incidents`로 오해하지 않게 할 수 있음

---

## 16. Phase 2로 넘길 항목

Phase 1B 이후로 넘긴다.

- pipeline run button
- provider selection
- dry-run toggle
- live progress
- regression run button
- report search/filter
- SQLite history
- alert/dashboard
- comparison history trend
- 모바일 전용 UX
- 화려한 애니메이션
- dark/light theme toggle
