# Web UI Report Viewer UI Polish Plan

- 작성일: 2026-05-05
- 문서 역할: Web UI Report Viewer의 UI polish 방향과 프레임워크 선택 기준 정리
- 전제: Phase 1A report list/detail + Stage2 quality lint display 구현, Phase 1B comparison view 구현 또는 구현 후보 검토 중
- 범위: 지금 당장 구현할 코드가 아니라, 어떤 UI 접근이 가장 적절한지 판단을 고정한다.

---

## 1. 목적

이 문서는 Web UI Report Viewer의 다음 UI 개선 방향을 정리한다.

핵심 질문은 “어떤 프레임워크를 쓸까?”가 아니라 다음이다.

```text
현재 프로젝트의 성격과 안정화 단계에서, 어느 정도의 UI 복잡도가 가장 적절한가?
```

현재 viewer는 내부 실험/검증용 콘솔이다. SaaS 제품이나 외부 공개 서비스가 아니다. 따라서 프레임워크 선택과 UI polish는 아래 조건을 우선한다.

- pipeline core를 건드리지 않음
- Stage2 report JSON과 quality lint 결과를 정확히 표시
- Apache logs-only 해석 원칙을 UI에서도 유지
- 외부 네트워크/CDN/빌드 체인 의존 최소화
- 작고 검증 가능한 변경 단위 유지

---

## 2. 현재 UI의 역할

현재 Web UI Report Viewer가 해야 하는 일:

- Stage2 report JSON 목록 표시
- report detail 표시
- Stage2 quality lint 결과 표시
- 같은 timeframe/scenario의 OpenAI / Anthropic report 비교
- missing provider 상태 표시
- report path/ID/metadata를 안전하게 표시

하지 말아야 하는 일:

- UI가 새 보안 판정 생성
- UI가 success/exposure/compromise를 새로 단정
- LLM을 다시 호출해 비교 요약 생성
- report JSON을 rewrite
- pipeline 실행/운영 자동화까지 즉시 확장

---

## 3. 프레임워크 후보 판단

### 3.1 현재 가장 적절한 선택

현재 기준으로 가장 적절한 선택은 다음이다.

```text
FastAPI + Jinja2 + Plain CSS
```

이유:

- Python pipeline과 같은 언어라 연동 부담이 낮다.
- Stage2 report JSON을 파일 기반으로 읽는 현재 구조와 잘 맞다.
- report viewer/list/detail/compare 정도는 서버 사이드 렌더링으로 충분하다.
- React/Vue/Svelte 같은 프론트엔드 빌드 체인이 아직 필요하지 않다.
- 외부 CDN 없이 내부망/오프라인 환경에서 동작 가능하다.
- 검증 범위를 `web/`으로 제한하기 쉽다.

### 3.2 보류 후보

#### React / Vue / Svelte / Angular

현재는 보류한다.

장점:

- 복잡한 상호작용과 대시보드에는 유리하다.
- client-side filtering, chart, stateful comparison에는 강하다.

보류 이유:

- npm/빌드 도구가 필요하다.
- 현재 Phase 1A/1B 범위에는 과하다.
- pipeline viewer보다 frontend project가 커질 위험이 있다.
- 기존 FastAPI/Jinja 구조와 중복된다.

#### Streamlit

prototype으로는 가능하지만 공식 viewer로는 보류한다.

장점:

- 빠른 table/chart prototype 작성이 쉽다.

보류 이유:

- URL route/report_id 설계가 약하다.
- 현재 `web/`의 route 기반 viewer와 결이 다르다.
- Phase 1B comparison URL 공유와 report_id 기반 접근에 FastAPI가 더 적합하다.

#### Tailwind CSS / Bootstrap

지금은 보류한다.

장점:

- 빠른 스타일링 가능.

보류 이유:

- Tailwind CDN은 오프라인/내부망 기준과 충돌한다.
- npm build를 도입하면 Phase 1의 단순성이 깨진다.
- Bootstrap은 빠르지만 현재 badge/class contract와 시각 체계가 섞일 수 있다.

#### htmx / Alpine.js

후속 후보로 유지한다.

적합한 시점:

- report list filter
- details section toggle
- lint refresh button
- compare panel partial update

현재 Phase 1A/1B polish에서는 없어도 된다.

#### Docker

배포/격리 단계에서 검토한다.

현재는 로컬/SSH tunnel 기반이면 충분하다.

---

## 4. 권장 UI 방향

현재 viewer는 “화려한 dashboard”보다 “정확하고 빠르게 읽히는 내부 console”이 맞다.

권장 방향:

```text
Functional console > visual dashboard
```

우선순위:

1. 정보 계층 정리
2. 비교 지표 접근성 개선
3. 긴 report text 처리
4. badge/spacing/typography 일관성
5. narrow viewport 안정성
6. 필요한 경우에만 인터랙션 추가

비우선순위:

- 애니메이션
- theme toggle
- chart 고도화
- 모바일 전용 UX
- frontend framework 전환

---

## 5. 현재 UI에서 개선할 점

### 5.1 Header compacting

현재 header가 화면 높이를 많이 차지할 수 있다.

개선 방향:

- header padding 축소
- subtitle 간결화
- report count 같은 통계는 summary card로 이동
- navigation은 최소화

권장 header:

```text
Security Intelligence Console
Stage2 Report Viewer · Quality Lint · Model Comparison
```

### 5.2 Compare page 정보 순서

Compare page에서는 provider report 본문보다 metrics가 먼저 보여야 한다.

권장 순서:

```text
1. Compare header
2. Mini summary row
3. Compare Metrics
4. Provider panels
5. Severity/Verdict distribution tables
6. Notes / limitations
```

이유:

- 사용자는 먼저 두 모델의 차이를 보고 싶다.
- 긴 `overall_assessment`, `key_findings`, `recommended_actions`는 후순위로 읽어도 된다.

### 5.3 Provider panel text handling

Provider panel은 긴 보고서 텍스트 때문에 화면을 과하게 늘릴 수 있다.

추천:

- `overall_assessment`는 기본 표시
- `key_findings`와 `recommended_actions`는 `<details>` 접기 사용
- 또는 panel 내부 max-height + overflow-y 적용

우선 추천은 `<details>`다.

이유:

- JavaScript가 필요 없다.
- report text 원문 유지가 쉽다.
- 사용자 선택으로 펼쳐 볼 수 있다.

### 5.4 Compare metrics 강조

Phase 1B의 핵심은 comparison이다.

강조할 지표:

- reported incident count
- high/critical severity count
- verdict type count
- key finding count
- recommended action count
- lint blocker/warning/info count

주의:

- count 차이는 report output 차이다.
- 실제 사건 수 차이로 단정하지 않는다.

### 5.5 Badge 정리

권장 badge group:

- provider: OpenAI / Anthropic / Unknown
- lint: PASS / WARN / FAIL / ERROR
- severity: critical / high / medium / low / info / unknown
- state: Missing report / N/A / Context only / Needs review

금지 badge:

- Confirmed Exposure
- Attacker IP
- Real Crawler
- Successful Exploit
- DB Leak
- XSS Executed
- Compromised Host
- Auth Bypass Success

---

## 6. Light theme 기준

첨부 스크린샷이 검은색으로 보인 것은 Chrome Dark Reader 영향으로 본다.

따라서 기본 polish는 light theme 기준으로 진행한다.

- dark theme 신규 설계 없음
- dark/light toggle 없음
- Dark Reader 색 왜곡 대응은 목표가 아님
- 기본 브라우저에서 가독성 좋은 light theme를 우선한다.

권장 palette:

```text
background: #f5f7fb 또는 #f8fafc
surface: #ffffff
border: #d7dde6
text: #172033
muted text: #5e6e85
OpenAI: blue 계열
Anthropic: orange 계열
PASS: green
WARN: amber
FAIL: red
INFO/unknown: gray
```

---

## 7. Missing provider UX

한쪽 provider report가 없을 수 있다.

원칙:

- missing provider panel은 삭제하지 않는다.
- panel은 유지하되 muted/dashed/opacity 스타일로 표현한다.
- `Missing report` badge를 표시한다.
- metrics는 `N/A`로 표시한다.
- missing을 `0 incidents`로 해석하지 않는다.

권장 class:

```css
.compare-panel-missing
.badge-missing-report
.compare-bar-value-na
```

---

## 8. Narrow viewport

Phase 1B는 mobile-first는 아니지만, 좁은 화면에서 깨지면 안 된다.

최소 기준:

```css
.compare-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 900px) {
  .compare-layout {
    grid-template-columns: 1fr;
  }
}
```

추가:

- table wrapper에 `overflow-x: auto`
- panel에 `min-width: 0`
- 긴 filename/path는 `overflow-wrap:anywhere`

---

## 9. Apache logs-only UI guard

UI polish 중에도 아래는 바꾸지 않는다.

- Stage2 report body text 의미
- Stage2 quality lint verdict/count 의미
- severity/verdict label 의미
- missing provider는 missing이지 0건 incident가 아님
- IP/source metadata masking
- raw JSON full view 기본 제외
- report files read-only

UI는 새로 단정하지 않는다.

- 공격 성공
- 침해 성공
- 파일 노출 성공
- 브라우저 실행 성공
- DB 결과 반환
- 실제 crawler identity
- attacker IP

---

## 10. 작업 우선순위

### 10.1 2026-05-06 브라우저 점검 결과 (Phase 1B)

점검 일자: 2026-05-06

정상 확인 항목:

- list/detail/compare page 기본 표시 정상
- compare metrics 위치 정상
- known asset masking 유지
- pair ready compare group 표시 정상 (openai/anthropic 나란히 표시)

추가 polish 필요 항목:

- provider가 하나뿐인 timeframe group에서 오른쪽 카드 영역이 비어 보임
- partial group의 missing provider 상태를 더 명확히 보여줄 필요 있음

권장 해결:

- list page partial group에도 missing provider placeholder card를 표시
- placeholder는 muted/dashed style을 사용
- `Missing report` badge 표시
- `N/A` 표시
- detail link는 표시하지 않음
- missing을 `0 incidents`로 해석하지 않음

대안:

- single-provider group을 full-width card로 표시
- 단, missing provider 상태가 덜 명확하므로 우선순위는 낮음

판단:

- 위 항목은 Phase 2 기능 확장이 아니라 Phase 1B UI polish 범위다.
- Phase 2 문서는 신규 생성하지 않고 본 문서에서 계속 관리한다.

### P1

- Compare Metrics를 provider panels보다 위로 이동
- Provider panel의 긴 section 접기
- Header compacting
- Missing provider panel 시각 일관성

### P2

- Badge color/spacing 정리
- Table/card border contrast 개선
- List page card compacting
- meta-grid spacing 조정

### P3

- hover/focus state 개선
- section collapse styling 개선
- small viewport polish

보류:

- animation-heavy transition
- dark/light theme toggle
- frontend framework 전환
- chart library 도입

---

## 11. 예상 수정 범위

가능하면 CSS/template만 수정한다.

예상 수정:

```text
web/templates/index.html
web/templates/compare.html
web/templates/detail.html
web/static/style.css
```

가능하면 Python logic은 수정하지 않는다.

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

## 12. 검증 기준

문법 검증:

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

기존 regression:

```bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python3 -m pytest tests/test_stage2_report_quality.py
```

수동 확인:

```bash
python -m uvicorn web.app:app --host 127.0.0.1 --port 8766
```

확인 화면:

```text
/
/report/{report_id}
/compare/{timeframe_id}
```

브라우저 확인 항목:

- compare metrics가 초반에 보이는가?
- provider panel이 너무 길게 밀리지 않는가?
- missing provider panel이 명확히 보이는가?
- narrow width에서 stack이 깨지지 않는가?
- filename/path가 card 밖으로 넘치지 않는가?
- report text 원문 의미가 바뀌지 않았는가?

---

## 13. 완료 기준

UI polish 완료 기준:

- 기존 Phase 1A/1B routes가 모두 유지된다.
- compare metrics 접근성이 개선된다.
- 긴 provider report text가 화면을 과도하게 밀지 않는다.
- badge/spacing/typography가 일관된다.
- missing provider/N/A 상태가 명확하다.
- narrow viewport에서 비교 panel이 깨지지 않는다.
- Apache logs-only UI guard가 유지된다.
- pipeline core, quality lint, report schema는 수정하지 않는다.

---

## 14. 결론

현재 가장 적절한 방향은 framework 전환이 아니다.

```text
FastAPI + Jinja2 + Plain CSS 유지
```

지금 필요한 것은 React/Vue/Tailwind/Streamlit로 갈아타는 것이 아니라, 이미 구현된 내부 viewer의 정보 구조와 가독성을 다듬는 것이다.

Phase 1A/1B가 더 복잡한 interaction을 요구하게 되면 그때 `htmx` 또는 `Alpine.js` 같은 작은 보조 도구를 검토한다. React/Vue/Svelte 계열은 대시보드가 훨씬 복잡해질 때까지 보류한다.
