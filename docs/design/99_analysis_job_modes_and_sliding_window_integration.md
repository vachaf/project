# Analysis Job Modes and Sliding Window Integration

- 문서 상태: 설계 기준 / Web UI MVP와 Sliding Window 통합 판단
- 기준 시점: 2026-05-31
- 목적: DB-backed `analysis_jobs` 실행 큐와 Sliding Window / Rollup / Operator Queue 계층의 관계를 정리하고, 짧은 구간과 긴 구간 분석을 어떤 mode로 분리할지 고정한다.

관련 문서:

- [00_current_architecture.md](../00_current_architecture.md)
- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_db_backed_log_collection_and_analysis_job_design.md](./99_db_backed_log_collection_and_analysis_job_design.md)
- [99_db_backed_web_ui_api_safety_addendum.md](./99_db_backed_web_ui_api_safety_addendum.md)
- [99_run_analysis_pipeline_user_runner_ux_review.md](./99_run_analysis_pipeline_user_runner_ux_review.md)
- [99_sliding_window_adoption_review.md](./99_sliding_window_adoption_review.md)
- [99_sliding_window_rollup_pipeline_integration.md](./99_sliding_window_rollup_pipeline_integration.md)
- [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
- [99_sliding_window_operator_queue_item_detail.md](./99_sliding_window_operator_queue_item_detail.md)
- [99_sliding_window_single_rollup_observation_brief.md](./99_sliding_window_single_rollup_observation_brief.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

---

## 1. 결론

Sliding Window는 버리지 않는다.

다만 Web UI MVP의 기본 `full_report` 실행 경로에 자동으로 끼워 넣지 않는다.

현재 기준 운영 구조는 다음처럼 분리한다.

```text
짧은 구간 / 명시적 report 요청:
  analysis_mode=full_report
  direct export -> prepare -> Stage1 -> Stage2 -> viewer_payload

긴 구간 / 하루치 훑기 / 운영 triage:
  analysis_mode=windowed_triage  # 후속 mode
  window export -> window prepare -> window_summary -> rollup -> operator_queue
  Stage1/Stage2 기본 실행 없음

operator_queue에서 사람이 선택한 rollup:
  selected_rollup_brief       # deterministic observation brief 우선
  selected_rollup_full_report # projection + Stage1/Stage2는 후순위
```

따라서 현재 Web UI MVP는 `full_report`만 노출한다.

`windowed_triage`, `selected_rollup_brief`, `selected_rollup_full_report`는 후속 mode로 문서화하되, 즉시 Web UI 입력 폼에 노출하지 않는다.

2026-05-31 실제 smoke 기준으로 `full_report` direct pipeline은 DB-backed job 등록, worker claim, export, prepare, Stage1, Stage2, viewer_payload, `analysis_reports` 저장, `/job/{id}/viewer` 표시까지 확인했다. 이 smoke에는 sliding_window, rollup, operator_queue를 삽입하지 않았다.

---

## 2. 두 종류의 queue 구분

### 2.1 `analysis_jobs` queue

`analysis_jobs`는 실행 큐다.

```text
Web UI에서 사용자가 분석 작업 등록
  -> DB analysis_jobs row 생성
  -> Analysis Agent가 PENDING 작업 claim
  -> 작업 mode에 맞는 pipeline 실행
  -> artifact 저장
  -> analysis_reports / job_events 갱신
  -> Web UI에서 상태와 결과 확인
```

특징:

```text
- DB table 기반
- source of truth는 analysis_jobs.status
- Web UI가 작업을 등록한다
- Analysis Agent가 claim/execute/update한다
- 작업 lifecycle 추적 대상이다
```

### 2.2 `operator_queue`

`operator_queue`는 실행 큐가 아니라 검토 큐다.

```text
window prepare
  -> window_summary
  -> rollup
  -> operator_queue
  -> 사람이 먼저 볼 rollup 목록
```

특징:

```text
- file artifact 기반
- data/operator_queue/<date>/queue_items.json
- data/operator_queue/<date>/queue_summary.json
- rollup 이후 사람이 먼저 볼 검토 목록
- 보안 verdict가 아니다
- Stage1/Stage2 실행 요청이 아니다
```

### 2.3 혼동 금지

```text
analysis_jobs queue
  = 어떤 분석 작업을 실행할지 정하는 DB-backed execution queue

operator_queue
  = 긴 구간 triage 결과 중 사람이 어떤 rollup을 볼지 정리한 review queue
```

둘은 이름은 모두 queue지만 서로 다른 계층이다.

---

## 3. Mode 목록

### 3.1 `full_report`

현재 Web UI MVP의 기본 mode다.

목적:

```text
짧은 구간 또는 명시적으로 LLM report가 필요한 구간을 기존 pipeline으로 분석한다.
```

흐름:

```text
DB logs
  -> export.json
  -> prepare_llm_input.py
  -> llm_input.json / analysis_candidates.json / noise_summary.json
  -> llm_stage1_classifier.py
  -> stage1_results.json
  -> llm_stage2_reporter.py
  -> stage2_report.json / stage2_report.md
  -> viewer_payload.json
```

Stage1/Stage2 입력:

```text
기존 prepare output
- llm_input.json
- analysis_candidates.json
```

Web UI 결과:

```text
- job detail
- analysis_reports path metadata
- Stage2 report viewer
- viewer_payload display
```

원칙:

```text
- Sliding Window 자동 삽입 없음
- rollup/operator_queue 생성 필수 아님
- 기존 run_analysis_pipeline.py 호환 유지
```

### 3.2 `windowed_triage`

후속 mode다. Web UI MVP에서 즉시 노출하지 않는다.

목적:

```text
긴 구간을 한 번에 Stage1/Stage2에 태우지 않고, 시간 단위로 prepare한 뒤 rollup/operator_queue로 사람이 먼저 볼 요약 목록을 만든다.
```

흐름:

```text
DB logs
  -> window export
  -> window prepare
  -> window_summary.json
  -> rollup_input.json / dedup_candidates.json / rollup_summary.json
  -> queue_items.json / queue_summary.json
```

Stage1/Stage2 입력:

```text
없음.
```

중요 원칙:

```text
- windowed_triage는 Stage2 report 생성 job이 아니다.
- windowed_triage는 selected rollup을 고르기 위한 triage job이다.
- llm_required는 기본 false다.
- Web UI는 queue 결과를 read-only로 표시한다.
```

### 3.3 `selected_rollup_brief`

후속 mode다.

목적:

```text
operator_queue에서 사람이 선택한 rollup 하나를 deterministic observation brief로 요약한다.
```

초기 구현 후보:

```text
src/sliding_window_rollup_observation_brief.py
```

입력:

```text
- queue_items.json
- selected rollup_id
- rollup_input.json
- rollup_summary.json
```

출력 후보:

```text
stdout markdown/text preview 우선
artifact 저장은 후속 판단
```

금지:

```text
- LLM 호출 기본 없음
- Stage1/Stage2 호출 없음
- 공격 성공/침해/노출 단정 없음
- severity/category/verdict 재계산 없음
```

### 3.4 `selected_rollup_full_report`

가장 후순위 mode다.

목적:

```text
operator_queue에서 사람이 선택한 rollup에 대해서만 deep-analysis를 실행한다.
```

필요한 연결:

```text
selected rollup
  -> Stage1-compatible projection
  -> Stage1
  -> Stage2
  -> viewer_payload
```

아직 구현하지 않는다.

보류 이유:

```text
- 기존 Stage1/Stage2는 rollup_input schema를 직접 모른다.
- projection contract가 필요하다.
- projection 과정에서 score/verdict_hint/severity/confidence를 새로 만들면 안 된다.
- context-only를 candidate/finding/incident로 승격하면 안 된다.
```

---

## 4. 분석 구간 길이별 기본 정책

### 4.1 짧은 구간

운영 권장 예시:

```text
2~30분
1시간
보수적으로 2시간 이하 권장
```

기본 정책:

```text
full_report direct pipeline
```

이유:

```text
- Sliding Window를 적용하면 오히려 run/artifact 구조가 복잡해진다.
- 사용자는 Stage2/viewer_payload 결과를 기대한다.
- 기존 pipeline이 가장 단순하다.
```

### 4.2 중간~긴 구간

허용 상한 범위:

```text
2시간 초과 ~ 24시간
```

MVP 정책:

```text
Web UI full_report 등록은 코드/UI 기준 24시간까지 허용한다.
다만 24시간은 권장값이 아니라 허용 상한이다.
```

후속 정책:

```text
windowed_triage mode 후보
```

이유:

```text
- 큰 구간을 한 번에 prepare/Stage1/Stage2에 넣는 것은 candidate 수, token 비용, report 품질 측면에서 부담이 크다.
- window별 prepare와 rollup은 긴 구간에서 burst/반복/누락을 분리해 볼 수 있게 한다.
- Stage2 report를 window마다 만들면 report가 과도하게 증가한다.
```

### 4.3 24시간 초과

기본 정책:

```text
MVP에서는 등록 거부 또는 여러 job으로 분할 안내
```

후속 정책:

```text
periodic windowed_triage + daily summary 후보
```

---

## 5. Web UI MVP 적용 기준

현재 Web UI는 `analysis_mode=full_report` 고정으로 두는 것이 맞다.

`/new-job` 화면은 다음만 노출한다.

```text
- time_from
- time_to
- requested_timezone=Asia/Seoul
- analysis_mode=full_report 고정
```

사용자에게 여러 mode를 즉시 선택하게 하지 않는다.

이유:

```text
- full_report와 windowed_triage는 산출물이 다르다.
- full_report는 Stage2/viewer_payload를 만든다.
- windowed_triage는 operator_queue를 만든다.
- 두 mode를 같은 UI 기대값으로 다루면 사용자가 혼동한다.
```

따라서 Web UI MVP 문구는 다음 의미를 유지한다.

```text
새 분석 작업 = full_report 작업 등록
```

후속 UI에서만 다음을 추가한다.

```text
- Long range triage job
- Operator Queue list
- Queue item detail
- Observation Brief panel
- Selected rollup deep-analysis action
```

---

## 6. Analysis Agent 적용 기준

Analysis Agent는 `analysis_jobs.analysis_mode`에 따라 분기할 수 있어야 한다.

### 6.1 현재 MVP

```text
analysis_mode=full_report
```

실행:

```text
export_db_logs_cli.py
prepare_llm_input.py
llm_stage1_classifier.py
llm_stage2_reporter.py
viewer_payload_builder.py
```

성공 조건:

```text
- Stage2 report artifact 생성
- viewer_payload artifact 생성
- analysis_reports row 저장
- analysis_jobs.status=SUCCEEDED
```

### 6.2 후속 mode

```text
analysis_mode=windowed_triage
```

실행:

```text
sliding_window_scheduler.py --mode export
sliding_window_scheduler.py --mode prepare
sliding_window_rollup.py
sliding_window_operator_queue.py
```

성공 조건 후보:

```text
- queue_items.json 생성
- queue_summary.json 생성
- analysis_reports 또는 별도 job artifact metadata에 queue path 저장
- analysis_jobs.status=SUCCEEDED
```

주의:

```text
windowed_triage의 SUCCEEDED는 Stage2 report 생성을 의미하지 않는다.
```

---

## 7. Stage1/Stage2 연결 정책

### 7.1 `full_report`

Stage1/Stage2는 기본 실행한다.

```text
full_report
  -> prepare output
  -> Stage1
  -> Stage2
```

### 7.2 `windowed_triage`

Stage1/Stage2는 기본 실행하지 않는다.

```text
windowed_triage
  -> operator_queue
  -> 사람이 선택
```

### 7.3 selected rollup

Stage1/Stage2는 selected rollup에 대해서만 후속 후보로 검토한다.

```text
operator_queue item selected
  -> selected_rollup_brief
  -> 필요 시 selected_rollup_full_report
```

아직 다음은 구현하지 않는다.

```text
rollup_input.json -> direct Stage1
rollup_input.json -> direct Stage2
window마다 Stage2 자동 생성
```

---

## 8. Sliding Window를 full_report에 자동 삽입하지 않는 이유

`full_report`에 내부적으로 Sliding Window를 자동 삽입하면 사용자의 기대값이 깨질 수 있다.

문제:

```text
사용자는 Stage2 report 하나와 viewer_payload를 기대한다.
내부에서 windowed_triage만 수행하면 Stage2 report가 없다.
window마다 Stage2를 만들면 report가 너무 많다.
rollup을 Stage2에 넣으려면 projection contract가 필요하다.
```

따라서 `full_report`는 direct pipeline으로 유지한다.

긴 구간은 `windowed_triage`라는 별도 mode로 분리한다.

---

## 9. prepare를 항상 한 번에 수행하지 않는 이유

긴 구간을 한 번에 prepare한 뒤 나중에 분석만 나누는 방식은 현재 기준에서는 권장하지 않는다.

이유:

```text
- prepare는 단순 JSON 변환이 아니다.
- prepare는 candidate selection, context summary, noise aggregation, dedup, ranking에 관여한다.
- 긴 구간을 한 번에 prepare하면 시간대별 burst나 짧은 반복이 전체 구간 안에서 약화될 수 있다.
- 이후에 나누더라도 이미 prepare 판단이 전역 기준으로 끝난 상태가 된다.
```

따라서 긴 구간은 prepare 전에 window로 나누는 것이 맞다.

```text
긴 구간:
  window export -> window prepare -> rollup

짧은 구간:
  direct export -> direct prepare -> Stage1/Stage2
```

---

## 10. Apache logs-only guardrail

모든 mode에서 다음 원칙을 유지한다.

```text
- status_code=200으로 공격 성공/침해 성공 단정 금지
- status_code=403/404/500/503만으로 취약점/공격 성공/침해 단정 금지
- response_body_bytes/content_type/text/html로 파일 노출/정보 유출 단정 금지
- POST만으로 로그인 성공/업로드 저장 성공 단정 금지
- raw POST body, response body, DB 결과, 브라우저 실행 여부 추론 금지
- X-Forwarded-For / X-Real-IP / Forwarded는 관찰 header일 뿐 attacker identity 확정 근거가 아님
- context-only를 finding/incident로 승격 금지
- Web UI에서 severity/category/verdict 재계산 금지
- summary/rollup/operator_queue는 원본 evidence보다 강한 보안 판정을 만들면 안 됨
```

---

## 11. 현재 결정 사항

```text
[확정]
- Web UI MVP는 full_report 작업 등록을 기본으로 한다.
- full_report는 direct pipeline이다.
- full_report에 Sliding Window를 자동 삽입하지 않는다.
- windowed_triage는 후속 analysis_mode로 보존한다.
- windowed_triage는 Stage1/Stage2를 기본 실행하지 않는다.
- operator_queue는 analysis_jobs queue와 다른 검토 큐다.
- selected rollup에 대해서만 brief/deep-analysis를 후속 후보로 둔다.

[보류]
- Web UI에 windowed_triage mode 노출
- selected_rollup_brief artifact 저장
- selected_rollup_full_report projection
- rollup_input 직접 Stage1/Stage2 입력 지원
- window마다 Stage2 자동 생성
- full_report 시간 상한 자동 전환 정책
```

---

## 12. 다음 작업 후보

### 12.1 문서/UX

```text
- Web UI 새 작업 등록 화면의 full_report 고정 설명 보강
- long range 입력 시 MVP 정책 문구 결정
- windowed_triage 후속 UI 후보 문서화
```

### 12.2 Analysis Agent

```text
- analysis_mode=full_report claim/execute/update path 구현 또는 검증
- job_events 단계별 기록
- analysis_reports artifact path 저장
```

### 12.3 Sliding Window 후속

```text
- selected rollup observation brief CLI preview 구현
- windowed_triage job output contract 설계
- operator_queue Web UI list/detail 후보 설계
```

### 12.4 보류 유지

```text
- --rollup-id-prefix 추가
- Stage1/Stage2 projection
- LLM 기반 Single Rollup Reporter
```
