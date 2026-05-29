# Web UI Report Viewer Phase 2 Candidate Review

- 작성일: 2026-05-06
- 문서 역할: Web UI Report Viewer Phase 2 후보 비교 및 scope 판단 문서
- 기준 상태: Phase 1A/1B 핵심 구현 및 Phase 1B polish 마감 가능 상태
- 당시 결론 요약: execution console로 바로 확장하지 않고, read-only viewer 범위를 유지하는 Phase 2A 후보부터 검토한다.

---

## 0. 현재 기준 상태 업데이트

- 이 문서의 기존 판단은 2026-05-06 당시 Phase 2A/report viewer 표시 경로 기준으로 보존한다.
- 2026-05-28 이후 현재 상위 운영 방향은 [../00_current_architecture.md](../00_current_architecture.md)의 DB-backed MVP다.
- Web UI read-only 원칙은 보안 결과 해석 read-only로 재정의한다.
- Web UI는 `analysis_jobs` 등록/조회와 job lifecycle 표시를 위해 DB read/write를 수행할 수 있다.
- pipeline stage 실행은 Web UI가 직접 하지 않고 Analysis Agent가 `analysis_jobs`를 claim해 수행한다.
- arbitrary pipeline run button, arbitrary path input, regression run button, scheduling, alerting, destructive cleanup은 여전히 제외한다.

---

## 1. 목적

이 문서는 Web UI Report Viewer의 Phase 2 후보를 비교한다.

핵심 질문은 다음이다.

```text
Phase 2에서 read-only report viewer를 유지할 것인가,
아니면 pipeline 실행/운영 기능을 포함한 execution console로 확장할 것인가?
```

이 문서는 구현 지시서가 아니다. Phase 2를 바로 착수하기 전에 후보의 가치, 위험, 구현 난이도, 기존 원칙과의 충돌 여부를 비교하기 위한 판단 문서다.

---

## 2. 현재 상태

### 2.1 Phase 1A 완료 상태

Phase 1A는 Stage2 report viewer의 기본 흐름을 제공한다.

완료된 범위:

- Stage2 report list page
- Stage2 report detail page
- Stage2 quality lint display
- report_id 기반 detail navigation
- report file read-only 조회
- metadata / known asset / source IP 노출 제한 원칙 유지

### 2.2 Phase 1B 완료 상태

Phase 1B는 OpenAI / Anthropic report comparison을 제공한다.

완료된 범위:

- `/compare/{timeframe_id}` HTML route
- `/api/compare/{timeframe_id}` JSON route
- timeframe/scenario 기반 report grouping
- provider detection
- Compare / Compare partial link
- OpenAI / Anthropic provider panels
- missing provider placeholder
- `Missing report` / `N/A` / detail link 없음 정책
- Compare Metrics 상단 배치
- provider panel 긴 section `<details>` 접기
- severity / verdict distribution table
- narrow viewport stack
- small viewport overflow 확인

### 2.3 QA / 검증 상태

현재 공식 검증 축:

```text
scripts/check_prepare_regression.py
scripts/check_stage_dryrun_regression.py
scripts/check_stage2_report_quality.py
```

최근 기준:

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
Stage2 report quality lint tests: 14 passed
```

QA v4 `scripts/run_qa_check_production_v4.py`는 공식 regression/lint 대체가 아니라 보조/실험 스크립트로 관리한다.

---

## 3. 유지해야 할 원칙

Phase 2에서도 아래 원칙은 기본값으로 유지한다.

- FastAPI + Jinja2 + Plain CSS 유지
- localhost-only 기본
- 외부 CDN 사용 금지
- React/npm/webpack 도입 보류
- report files / `viewer_payload` display는 read-only projection 기본
- UI가 새 보안 판정을 생성하지 않음
- Stage2 report 본문 의미 변경 금지
- Apache logs-only 해석 한계 유지
- metadata/source IP/known asset/raw preview 노출 제한 유지
- API key / config secret 노출 금지
- `status_code`, `response_body_bytes`, `content-type`만으로 성공/침해/유출 단정 금지
- DB-backed MVP의 `analysis_jobs` 등록/조회 DB read/write는 허용
- pipeline stage 실행은 Web UI가 직접 하지 않고 Analysis Agent가 수행

Phase 2에서 위 원칙을 바꿔야 한다면, 해당 기능은 별도 설계 문서와 승인 조건이 필요하다.

---

## 4. Phase 2 후보 분류

Phase 2 후보는 세 갈래로 나눈다.

### 4.1 Read-only viewer 확장

기존 read-only report viewer 원칙을 유지하는 확장이다.

후보:

- report search/filter
- provider filter
- scenario filter
- timeframe filter
- lint verdict filter
- has_both / partial group filter
- report title / filename / scenario text search
- compare group navigation 개선
- lint issue navigation 개선

특징:

- report 파일을 수정하지 않는다.
- pipeline을 실행하지 않는다.
- 당시 Phase 2A viewer-only display path는 DB 없이 파일 scan 결과만으로 시작할 수 있다.
- 현재 DB-backed MVP의 job lifecycle DB 사용과 충돌하지 않는다.
- Phase 1A/1B 구조와 가장 자연스럽게 이어진다.

### 4.2 Execution console 확장

UI에서 pipeline, regression, dry-run 같은 실행 기능을 제공하는 확장이다.

후보:

- pipeline run button
- dry-run toggle
- live progress
- regression run button
- Stage2 report regeneration
- output cleanup integration

특징:

- 보안 결과 해석 read-only와 artifact overwrite/path 제한 원칙을 깨거나 완화할 수 있다.
- output write, long-running process, 실패 로그, 권한, API key, overwrite 방지 문제가 생긴다.
- 별도 보안/운영 설계가 필요하다.
- Phase 2A가 아니라 후속 Phase 2C 이상으로 분리하는 것이 안전하다.
- 현재 DB-backed MVP의 `analysis_jobs` 등록/조회는 이 arbitrary execution console 보류와 별개로 허용된다.

### 4.3 Storage / dashboard 확장

조회 이력, trend, dashboard, alert 등을 제공하는 확장이다.

후보:

- SQLite history
- comparison history trend
- lint trend dashboard
- alert/dashboard
- notification
- cached report index

특징:

- DB 또는 cache 파일이 필요할 수 있다.
- 당시 viewer-only display path에서는 stateful application으로 이동한다.
- 현재 DB-backed MVP의 MariaDB job lifecycle 저장은 별도 상위 운영 기준으로 허용된다.
- 현재 report 수와 사용 빈도를 보고 필요성을 판단해야 한다.

---

## 5. 후보별 비교

| 후보 | 사용자 가치 | 구현 난이도 | 정책/운영 리스크 | 표시 read-only 유지 | 추천 |
|---|---:|---:|---:|---:|---|
| report search/filter | 높음 | 낮음~중간 | 낮음 | 유지 가능 | 1순위 |
| provider/scenario/timeframe filter | 높음 | 낮음 | 낮음 | 유지 가능 | 1순위 |
| lint verdict filter | 중간~높음 | 낮음 | 낮음 | 유지 가능 | 1순위 |
| compare group navigation 개선 | 중간 | 낮음~중간 | 낮음 | 유지 가능 | 2순위 |
| comparison history trend | 중간 | 중간 | 중간 | 파일 기반이면 가능 | 2~3순위 |
| SQLite history | 중간 | 중간~높음 | 중간 | 부분 변경 | 보류 |
| pipeline run button | 높을 수 있음 | 높음 | 높음 | 유지 불가 | 보류 |
| dry-run toggle | 중간~높음 | 높음 | 높음 | 유지 불가 | 보류 |
| live progress | 중간 | 높음 | 높음 | 유지 불가 | 보류 |
| regression run button | 중간 | 높음 | 높음 | 유지 불가 | 보류 |
| alert/dashboard | 낮음~미정 | 높음 | 높음 | 변경 필요 | 장기 후보 |
| dark/light theme toggle | 낮음 | 중간 | 낮음 | 가능 | 비우선 |
| 모바일 전용 UX | 낮음 | 중간 | 낮음 | 가능 | 비우선 |

---

## 6. 추천 방향

### 6.1 현재 추천

현재 추천은 다음이다.

```text
Phase 2 전체 착수는 보류한다.
Phase 2A 후보로 read-only search/filter/navigation 개선을 우선 검토한다.
```

이유:

- Phase 1B는 내부 검증 콘솔로 충분히 동작한다.
- report 수가 늘어날수록 탐색/필터의 효용이 가장 먼저 커진다.
- 보안 결과 해석 read-only 원칙을 유지하면서 개선할 수 있다.
- arbitrary pipeline execution은 보안/운영 위험이 크고 별도 범위 합의가 필요하다.
- SQLite/dashboard/alert는 당시 viewer-only path에서는 필요성이 확정되지 않았다.

### 6.2 Phase 2A 권장 범위

Phase 2A는 아래로 제한한다.

포함:

- report list search
- provider filter
- scenario filter
- timeframe filter
- lint verdict filter
- has_both / partial group filter
- compare group navigation 개선

제외:

- pipeline run button
- regression run button
- dry-run toggle
- live progress
- report rewrite/regeneration
- SQLite history
- alert/dashboard
- external deployment
- Docker

---

## 7. Phase 2A 설계 방향

### 7.1 기본 구현 방향

Phase 2A viewer-only display path는 DB 없이 시작한다.

이는 현재 DB-backed MVP의 `analysis_jobs`, `job_events`, `analysis_reports` DB 사용을 금지한다는 뜻이 아니다.

가능한 구현 방식:

```text
ReportLoader.scan_reports()
→ group metadata 생성
→ query parameter 기반 filter
→ Jinja2 render
```

예상 URL:

```text
/?provider=openai
/?provider=anthropic
/?scenario=h_r4
/?lint=pass
/?pair=partial
/?q=file_disclosure
```

### 7.2 예상 수정 범위

예상 수정:

```text
web/app.py
web/services/report_loader.py
web/templates/index.html
web/static/style.css
```

가능하면 수정하지 않음:

```text
src/
scripts/
tests/fixtures
tests/expected
lab/
reports/
config/
```

### 7.3 데이터 계약 후보

Filter state는 query parameter로 관리한다.

예시:

```python
{
    "q": str | None,
    "provider": "openai" | "anthropic" | "unknown" | None,
    "scenario": str | None,
    "lint": "pass" | "warn" | "fail" | "error" | None,
    "pair": "both" | "partial" | None,
}
```

서버는 filter 결과와 함께 현재 filter state를 template에 전달한다.

```python
{
    "groups": list,
    "reports": list,
    "filters": dict,
    "filter_options": dict,
    "result_count": int,
}
```

---

## 8. Execution console 확장 보류 이유

pipeline run button, dry-run toggle, live progress, regression run button은 단순 UI 추가가 아니다.

필요한 추가 판단:

- 누가 실행 권한을 가지는가?
- 입력 파일 경로를 어떻게 제한할 것인가?
- output overwrite를 어떻게 막을 것인가?
- API key / env / config를 어떻게 숨길 것인가?
- long-running process를 어떻게 관리할 것인가?
- 실패 로그를 어느 수준까지 보여줄 것인가?
- 실행 중복을 어떻게 막을 것인가?
- 실행 결과를 어디에 저장할 것인가?
- 보안 결과 해석 read-only 원칙과 artifact overwrite/path 제한을 어떻게 유지할 것인가?

따라서 arbitrary execution console은 Phase 2A에 포함하지 않는다. 별도 문서가 필요하다.

현재 DB-backed MVP에서는 Web UI가 `analysis_jobs`를 등록하고 Analysis Agent가 pipeline stage를 실행하는 구조를 사용한다.

---

## 9. SQLite / dashboard 보류 이유

SQLite history, comparison trend, alert/dashboard는 stateful 기능이다.

보류 이유:

- 현재는 report 파일 scan 기반으로 충분하다.
- 별도 viewer history DB schema를 만들면 migration/cleanup 문제가 생긴다.
- trend가 필요한지 아직 확인되지 않았다.
- alert/dashboard는 운영 기능에 가까워 Phase 1B viewer의 목적과 다르다.

단, report 수가 늘어나 scan 성능이나 trend 요구가 커지면 Phase 2B 후보로 재검토한다.

---

## 10. Decision Questions

Phase 2A 착수 전 아래 질문에 답한다.

1. 현재 report 수가 많아서 탐색이 실제로 불편한가?
2. 가장 자주 찾는 기준은 provider, scenario, timeframe, lint verdict 중 무엇인가?
3. compare group을 찾는 데 search/filter가 얼마나 필요한가?
4. Phase 2에서 pipeline을 실행해야 하는가, 아니면 기존 report 탐색이면 충분한가?
5. execution 기능을 넣는다면 output overwrite와 API key 노출을 어떻게 막을 것인가?
6. SQLite가 필요한가, 아니면 파일 scan과 query parameter filter로 충분한가?
7. Phase 2A도 FastAPI + Jinja2 + Plain CSS만으로 충분한가?

---

## 11. Phase 2A 착수 조건

Phase 2A를 시작하려면 아래 조건을 만족해야 한다.

- 보안 결과 해석 read-only 원칙을 유지한다.
- Web UI 직접 pipeline 실행 기능을 포함하지 않는다.
- Phase 2A viewer-only display path에는 별도 DB/SQLite를 도입하지 않는다.
- search/filter의 실제 필요성이 확인된다.
- filter 기준과 URL query contract를 먼저 문서화한다.
- 기존 Phase 1A/1B route를 깨지 않는다.
- Web UI가 새 보안 판정을 생성하지 않는다.

---

## 12. 검증 기준

Phase 2A 작업 시 최소 검증:

```bash
python3 -m py_compile web/config.py web/app.py web/services/report_loader.py web/services/qa_runner.py web/services/report_comparator.py
```

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
python -m uvicorn web.app:app --host 127.0.0.1 --port 8768
```

확인 화면:

```text
/
/report/{report_id}
/compare/{timeframe_id}
```

Phase 2A filter가 추가된다면 query parameter 조합도 확인한다.

---

## 13. 현재 결론

현재 결론은 다음이다.

```text
Phase 1B는 마감 가능 상태다.
Phase 2 문서화는 가능하지만, 구현 착수는 아직 보류한다.
Phase 2A 후보로는 read-only search/filter/navigation 개선이 가장 안전하다.
Execution console 확장은 별도 scope review 없이는 진행하지 않는다.
SQLite/dashboard/alert는 장기 후보로 둔다.
```

단, 이 결론은 당시 viewer-only Phase 2A 판단이다. 현재 DB-backed MVP의 time range 기반 `analysis_jobs` 등록/조회와 Analysis Agent 실행 경로는 상위 운영 방향으로 허용된다.

따라서 다음 실제 후보는 둘 중 하나다.

1. Phase 2A search/filter/navigation 설계 문서 작성
2. Phase 2 전체 착수를 보류하고 선택적 polish만 유지

---

## 14. 후속 문서 후보

Phase 2A를 실제로 진행하기로 결정하면 아래 문서를 별도로 작성한다.

```text
docs/design/99_web_ui_report_viewer_phase2a_filter_plan.md
```

그 문서에서 다룰 내용:

- filter query parameter contract
- filter options generation
- result count display
- no-result UX
- pair/both/partial filter
- provider/scenario/lint filter
- search target fields
- verification commands

Execution console을 검토하기로 결정하면 아래 문서를 별도로 작성한다.

```text
docs/design/99_web_ui_report_viewer_execution_console_risk_review.md
```

그 문서에서 다룰 내용:

- 보안 결과 해석 read-only 원칙 유지 여부
- allowed input path
- output overwrite 방지
- process management
- logging and error display
- API key / config exposure risk
- rollback / cleanup

---

## 15. 참고 문서

- `docs/design/99_web_ui_report_viewer_plan.md`
- `docs/design/99_web_ui_report_viewer_phase1a_plan.md`
- `docs/design/99_web_ui_report_viewer_phase1a_template_contract.md`
- `docs/design/99_web_ui_report_viewer_phase1b_plan.md`
- `docs/design/99_web_ui_report_viewer_ui_polish_plan.md`
- `docs/planning/99_비교실험_후속개선_TODO.md`
- `scripts/README.md`
