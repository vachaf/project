# 99_sliding_window_operator_queue_item_detail

- 문서 상태: 설계 초안 / 구현 전 판단 문서
- 기준 시점: 2026-05-25
- 목적: Operator Queue item 하나를 사람이 어떻게 읽고 drilldown할지 정의한다.
- 관련 구현: `src/sliding_window_operator_queue.py`
- 관련 테스트: `tests/test_sliding_window_operator_queue.py`

관련 문서:

- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
- [99_sliding_window_rollup_input_format.md](./99_sliding_window_rollup_input_format.md)
- [99_sliding_window_rollup_pipeline_integration.md](./99_sliding_window_rollup_pipeline_integration.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

Operator Queue item detail의 1차 목표는 새 보안 판단을 만드는 것이 아니다.

목표는 사람이 `queue_items.json`의 각 item을 보고 다음을 빠르게 판단할 수 있게 하는 것이다.

```text
- 이 rollup은 조용한가?
- 검토 대상인가?
- 먼저 data quality를 확인해야 하는가?
- LLM briefing을 선택적으로 요청할 만한 입력인가?
- 어디로 drilldown해야 하는가?
```

따라서 다음 구현은 큰 schema 변경보다 **표시/정리 관점의 view 또는 projection**으로 시작하는 것이 적절하다.

권장 방향:

```text
- queue item 원본 schema는 당장 크게 확장하지 않는다.
- 기존 queue item의 counts/signals/top_observed/source paths를 사람이 읽기 쉬운 detail view로 정리한다.
- 필요하면 별도 builder나 Web UI projection에서 detail view를 만든다.
- 보안 verdict, success 판단, threat score는 추가하지 않는다.
```

## 2. 현재 queue item v1 상태

현재 `sliding_window_operator_queue_item_v1`은 다음 정보를 가진다.

```text
identity
  - rollup_id
  - rollup_path
  - rollup_summary_path
  - queue_date
  - generated_at

time_range
  - start
  - end_exclusive
  - timezone
  - duration_minutes

routing
  - data_quality_status
  - review_status
  - operator_state
  - llm_eligible
  - llm_required
  - recommended_action

counts
  - window_count
  - windows_successfully_loaded
  - windows_missing_or_failed
  - candidate_rows_total
  - candidate_index_count
  - dedup_removed_by_request_id
  - possible_duplicate_count
  - noise_group_count_total

signals
  - has_candidates
  - has_missing_windows
  - has_possible_duplicates
  - has_repeated_src_ip
  - has_repeated_uri
  - has_repeated_reason_hint_prefix
  - has_payload_like_reason_hint
  - is_quiet

top_observed
  - src_ip
  - uri
  - reason_hint_prefix
  - status_code

guardrails
  - summary_only
  - apache_logs_only
  - no_success_inference
  - no_body_inference
  - no_context_promotion
  - no_new_security_verdict
```

이 정보는 machine-readable routing에는 충분하다. 하지만 사람이 읽기에는 다음이 부족하다.

```text
- 어떤 순서로 읽어야 하는지
- 어떤 상태를 먼저 확인해야 하는지
- 어떤 항목이 drilldown entrypoint인지
- Apache logs-only 한계를 어디서 확인해야 하는지
- empty queue와 quiet item을 어떻게 구분해야 하는지
```

## 3. Operator가 item detail에서 먼저 봐야 하는 것

사람이 detail에서 보는 순서는 다음이 적절하다.

```text
1. Data quality
2. Review routing
3. Counts
4. Observed signals
5. Top observed distributions
6. Drilldown paths
7. Apache logs-only notes
```

이 순서는 보안 판단 순서가 아니라 운영 검토 순서다.

## 4. Detail view 권장 구조

Queue item detail은 다음 섹션으로 표현한다.

```json
{
  "schema": "sliding_window_operator_queue_item_detail_view_v1",
  "rollup_id": "rollup_20260524_0200_0400",
  "summary": {},
  "quality_assessment": {},
  "routing": {},
  "observed_signals": {},
  "top_observed": {},
  "drilldown": {},
  "apache_logs_only_notes": [],
  "guardrails": {}
}
```

주의:

```text
- 이 view는 원본 evidence가 아니다.
- queue item과 rollup artifact를 사람이 읽기 쉽게 재배열한 projection이다.
- 원본 확인은 rollup_input.json, rollup_summary.json, source window_summary, analysis_candidates, export에서 한다.
```

## 5. summary 섹션

예시:

```json
{
  "summary": {
    "time_range_label": "2026-05-24 02:00-04:00 Asia/Seoul",
    "review_status": "needs_review",
    "data_quality_status": "complete",
    "recommended_action": "review_before_optional_briefing",
    "llm_eligible": true,
    "llm_required": false
  }
}
```

의미:

```text
review_status
  - 사람이 볼 queue routing 상태
  - 보안 verdict가 아님

data_quality_status
  - 입력 artifact 품질/완전성 상태
  - 공격/침해 판단이 아님

recommended_action
  - 다음 운영 행동 힌트
  - 보안 결론이 아님

llm_eligible
  - optional LLM briefing을 요청할 수 있는 입력 상태
  - LLM 필수 또는 위험 판단이 아님

llm_required
  - v1에서는 항상 false
```

## 6. quality_assessment 섹션

예시:

```json
{
  "quality_assessment": {
    "status": "complete",
    "missing_or_failed_windows": 0,
    "possible_duplicates_marked": 0,
    "dedup_removed_by_request_id": 0,
    "notes": [
      "All expected windows were loaded for this rollup.",
      "No request_id dedup removals were observed."
    ]
  }
}
```

상태별 해석:

```text
complete
  - rollup_input/rollup_summary 로드 성공
  - windows_missing_or_failed == 0
  - incomplete_analysis == false

incomplete_missing_window
  - 일부 window_summary가 없거나 실패함
  - 먼저 source window 상태 확인 필요

degraded_invalid_window
  - schema mismatch 또는 failed source window 존재
  - 보안 검토보다 artifact 품질 확인 우선

missing_rollup_artifact
  - rollup_input.json 또는 rollup_summary.json 누락
  - queue routing보다 rollup 생성 상태 확인 우선
```

주의:

```text
complete는 보안적으로 안전하다는 뜻이 아니다.
incomplete는 공격이 있다는 뜻이 아니다.
```

## 7. routing 섹션

예시:

```json
{
  "routing": {
    "review_status": "needs_review",
    "operator_state": "unreviewed",
    "recommended_action": "review_before_optional_briefing",
    "llm_eligible": true,
    "llm_required": false
  }
}
```

허용 review_status:

```text
quiet
needs_review
data_quality_check
```

해석:

```text
quiet
  - candidate_index_count == 0인 complete rollup
  - 보안적으로 안전하다는 뜻이 아니라 현재 candidate가 없다는 뜻

needs_review
  - complete rollup이고 candidate_index_count > 0
  - 사람이 볼 필요가 있다는 routing 상태
  - 공격 성공/침해 판단이 아님

data_quality_check
  - 먼저 artifact 품질/누락/실패 상태 확인 필요
```

## 8. observed_signals 섹션

예시:

```json
{
  "observed_signals": {
    "has_candidates": true,
    "has_payload_like_reason_hint": true,
    "has_repeated_src_ip": true,
    "has_repeated_uri": true,
    "has_repeated_reason_hint_prefix": true,
    "has_missing_windows": false,
    "has_possible_duplicates": false
  }
}
```

해석:

```text
has_payload_like_reason_hint
  - payload-like observation group이 있음
  - 공격 성공 판단이 아님

has_repeated_src_ip / uri / reason_hint_prefix
  - 같은 값이 distribution에서 반복 관찰됨
  - attribution, campaign, compromise 판단이 아님

has_possible_duplicates
  - request_id 없는 fallback duplicate 후보가 표시됨
  - 제거하지 않고 사람이 참고할 수 있게 표시
```

## 9. top_observed 섹션

현재 queue item은 이미 다음을 포함한다.

```text
top_observed.src_ip
top_observed.uri
top_observed.reason_hint_prefix
top_observed.status_code
```

표시 예시:

```json
{
  "top_observed": {
    "src_ip": [
      {"value": "192.168.56.114", "count": 5}
    ],
    "uri": [
      {"value": "/search.php", "count": 5}
    ],
    "reason_hint_prefix": [
      {"value": "xss", "count": 5},
      {"value": "sqli", "count": 1}
    ],
    "status_code": [
      {"value": "500", "count": 5}
    ]
  }
}
```

주의:

```text
- top_observed는 분포 요약이다.
- ranking이나 severity가 아니다.
- status_code 분포는 성공/실패 판단이 아니다.
- src_ip 분포는 공격자 식별이 아니다.
```

## 10. drilldown 섹션

Detail view는 사람이 원본으로 내려갈 수 있는 경로를 제공해야 한다.

예시:

```json
{
  "drilldown": {
    "rollup_input_path": "data/rollups/2026-05-24/rollup_20260524_0200_0400/rollup_input.json",
    "rollup_summary_path": "data/rollups/2026-05-24/rollup_20260524_0200_0400/rollup_summary.json",
    "source_window_summary_paths": [
      "data/windowed/2026-05-24/sw_0200_0300/window_summary.json",
      "data/windowed/2026-05-24/sw_0300_0400/window_summary.json"
    ],
    "candidate_source": "rollup_input.candidate_index"
  }
}
```

권장 drilldown 순서:

```text
queue item
  -> rollup_summary.json
  -> rollup_input.json
  -> source window_summary.json
  -> analysis_candidates.json
  -> export.json
```

## 11. apache_logs_only_notes 섹션

예시:

```json
{
  "apache_logs_only_notes": [
    "This detail view is derived from Apache log artifacts only.",
    "It does not include raw POST body, response body, DB result, or browser execution evidence.",
    "HTTP 200, text/html, or response_body_bytes are not success evidence by themselves.",
    "Review status and LLM eligibility are routing signals, not security verdicts."
  ]
}
```

이 notes는 detail view에서 항상 보이거나 접을 수 있는 형태로 제공하는 것이 좋다.

## 12. empty queue와 quiet item 구분

중요 구분:

```text
empty queue
  - pattern에 매칭되는 rollup item이 0개
  - rollup_items_total == 0
  - quiet == 0
  - quiet day가 아님

quiet item
  - rollup item은 존재함
  - data_quality_status == complete
  - candidate_index_count == 0
  - review_status == quiet
```

Web UI나 CLI detail에서 이 둘을 섞으면 안 된다.

## 13. 구현 선택지

### 선택지 A: queue item schema 확장

`queue_items.json`에 `quality_assessment`, `apache_logs_only_notes`, `drilldown` 등을 직접 추가한다.

장점:

```text
- item 하나만 읽어도 detail에 필요한 정보가 많다.
```

단점:

```text
- queue item artifact가 점점 UI projection에 가까워진다.
- schema 변경이 잦아질 수 있다.
- 원본과 view의 경계가 흐려질 수 있다.
```

### 선택지 B: 별도 detail view builder

예:

```text
src/sliding_window_operator_queue_detail.py
```

출력 후보:

```text
data/operator_queue/<date>/details/<rollup_id>.json
```

장점:

```text
- queue item 원본은 간결하게 유지한다.
- 사람이 보는 detail view를 별도 schema로 관리할 수 있다.
```

단점:

```text
- 파일 수가 늘어난다.
- 아직 Web UI가 없으면 활용도가 낮을 수 있다.
```

### 선택지 C: Web UI / CLI view projection

queue item 원본은 유지하고, UI/CLI에서 읽기 좋게 재배열한다.

장점:

```text
- artifact schema 변경이 적다.
- 사람용 표시와 원본 artifact를 분리할 수 있다.
```

단점:

```text
- Web UI/CLI 구현 전까지 문서상의 설계에 머문다.
```

## 14. 권장 판단

현재는 선택지 C를 우선한다.

```text
결정 후보:
  - queue item schema를 즉시 확장하지 않는다.
  - 별도 detail artifact도 아직 만들지 않는다.
  - 먼저 detail view projection 설계를 문서로 고정한다.
  - 다음 구현은 Web UI 또는 CLI 출력 개선이 필요해질 때 최소 범위로 진행한다.
```

이유:

```text
- 현재 queue item에는 이미 counts/signals/top_observed/path가 있다.
- 즉시 schema를 확장하지 않아도 사람이 볼 detail view를 구성할 수 있다.
- 구현보다 먼저 사람이 어떤 순서로 읽는지 확정하는 것이 더 중요하다.
- rollup naming generation처럼 CLI 옵션을 더 늘리는 것을 피해야 한다.
```

## 15. 구현 판단

이 문서 기준의 구현 판단:

```text
지금 즉시 queue item schema 확장 구현은 보류한다.
```

다음에 구현한다면 우선순위는 다음과 같다.

```text
1. CLI detail preview
   - queue_items.json을 읽어 사람이 보는 순서로 출력
   - 새 artifact 생성 없음

2. Web UI detail projection
   - queue item list/detail 화면에서 기존 fields를 재배열
   - 새 보안 판단 생성 없음

3. 필요 시 detail artifact
   - data/operator_queue/<date>/details/<rollup_id>.json
   - Web UI 또는 daily summary가 실제로 필요로 할 때만 추가
```

## 16. Non-goals

Queue item detail 설계는 다음을 하지 않는다.

```text
- 보안 verdict 생성
- severity/category/final verdict 재계산
- confidence_score/threat_level 계산
- attack success 판단
- exploit success 판단
- data exposure 판단
- account takeover 판단
- upload saved 판단
- context-only 승격
- llm_required=true 생성
- Stage1/Stage2 자동 실행
- LLM briefing 자동 실행
```

## 17. 다음 단계

다음 문서:

```text
docs/design/99_sliding_window_single_rollup_observation_brief.md
```

그 문서에서 queue item detail 이후의 optional observation brief가 어떤 역할인지 정의한다.
