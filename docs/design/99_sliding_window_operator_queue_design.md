# 99_sliding_window_operator_queue_design

- 문서 상태: 설계 초안
- 기준 시점: 2026-05-24
- 목적: Sliding Window / Rollup 이후 사람이 먼저 봐야 할 운영 queue 모델을 정의한다.
- 배경: Rollup v1.0이 완료된 뒤, 기존 Stage1/Stage2를 모든 rollup에 기본 실행하는 구조가 적절한지 재검토한다.

관련 문서:

- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_sliding_window_adoption_review.md](./99_sliding_window_adoption_review.md)
- [99_sliding_window_rollup_input_review.md](./99_sliding_window_rollup_input_review.md)
- [99_sliding_window_rollup_input_format.md](./99_sliding_window_rollup_input_format.md)
- [99_sliding_window_rollup_pipeline_integration.md](./99_sliding_window_rollup_pipeline_integration.md)
- [99_sliding_window_rollup_quick_reference.md](./99_sliding_window_rollup_quick_reference.md)
- [99_sliding_window_rollup_implementation_guide.md](./99_sliding_window_rollup_implementation_guide.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

Rollup 이후의 기본 운영 흐름은 Stage1/Stage2 자동 실행이 아니다.

사람이 먼저 봐야 하는 것은 Stage2 report list가 아니라 Rollup Operator Queue다.

권장 구조:

```text
[1] Window Layer
    export + prepare + window_summary
    LLM 없음

[2] Rollup Layer
    dedup + merge + rollup_summary
    LLM 없음

[3] Operator Queue Layer
    사람이 먼저 볼 review queue 생성
    LLM 없음

[4] Optional LLM Briefing Layer
    선택된 rollup 또는 daily bundle만 LLM 요약

[5] Human Drilldown Layer
    Web UI에서 근거 후보/원본 artifact 확인
```

기존 Stage1/Stage2는 제거하지 않는다. 다만 기본 실행 경로가 아니라 optional deep-analysis 또는 legacy analysis path로 둔다.

## 2. 왜 Stage1/Stage2를 기본값으로 두지 않는가

기존 Stage1/Stage2 구조는 단일 큰 `export.json` 또는 큰 prepare output을 LLM에 직접 넣기 어렵던 제약에서 나온 구조다.

현재는 전단에 다음 레이어가 생겼다.

```text
window prepare
  -> window_summary.json
  -> rollup_input.json
  -> dedup_candidates.json
  -> rollup_summary.json
```

따라서 모든 rollup에 대해 자동으로 다음을 수행할 필요는 없다.

```text
rollup_input.json
  -> projection
  -> Stage1
  -> Stage2
```

이 방식은 다음 문제를 만든다.

- 하루에 여러 Stage2 report가 생성되어 운영자 review 대상이 늘어난다.
- LLM 비용이 rollup 수에 비례해 증가한다.
- 사람이 먼저 확인해야 할 data quality 상태, missing window, quiet window가 LLM report 뒤에 묻힌다.
- Projection 설계를 서두르면 모든 rollup을 LLM에 넣는 구조로 끌려갈 수 있다.

따라서 먼저 사람이 볼 queue를 정의하고, 그 queue에서 필요한 항목만 optional LLM briefing 또는 deep analysis로 올린다.

## 3. 사람은 무엇을 먼저 봐야 하는가

운영자가 매일 먼저 볼 것은 다음 세 가지다.

1. Timeline / Queue
   - 어떤 시간대가 조용했는가
   - 어떤 시간대가 review 대상인가
   - 어떤 시간대가 missing/incomplete 상태인가

2. Compact Situation Board
   - candidate 수
   - dedup 후 후보 수
   - repeated src_ip / uri / reason_hint_prefix 여부
   - payload-like 후보 존재 여부
   - noise/context-heavy 여부

3. Evidence Drilldown
   - rollup_input -> source_windows -> window_summary -> analysis_candidates/export로 내려가는 read-only 경로

이 기본 화면은 Stage2 report list가 아니다.

## 4. Artifact layout

초기 설계에서는 queue artifact를 `data/operator_queue/`에 둘 수 있다.

```text
data/operator_queue/
  2026-05-24/
    queue_summary.json
    queue_items.json
```

대안으로 rollup directory에 operator item을 둘 수도 있다.

```text
data/rollups/2026-05-24/rollup_20260524_0200_0600/
  rollup_input.json
  dedup_candidates.json
  rollup_summary.json
  operator_item.json
```

초기 구현 후보는 둘 중 하나를 선택해야 한다.

권장:

```text
data/operator_queue/<date>/queue_items.json
```

이유:

- 사람은 rollup별 디렉터리를 직접 탐색하지 않는다.
- 하루치 queue를 한 파일로 정렬/필터링하기 쉽다.
- Web UI가 나중에 읽기 쉽다.
- rollup artifact와 operator review state를 분리할 수 있다.

단, v1 구현 전에는 문서로만 유지한다.

## 5. Queue item v1 후보 schema

```json
{
  "schema": "sliding_window_operator_queue_item_v1",
  "queue_date": "2026-05-24",
  "rollup_id": "rollup_20260524_0200_0600",
  "rollup_path": "data/rollups/2026-05-24/rollup_20260524_0200_0600/rollup_input.json",
  "rollup_summary_path": "data/rollups/2026-05-24/rollup_20260524_0200_0600/rollup_summary.json",
  "time_range": {
    "start": "2026-05-24T02:00:00+09:00",
    "end_exclusive": "2026-05-24T06:00:00+09:00",
    "timezone": "Asia/Seoul",
    "duration_minutes": 240
  },
  "data_quality_status": "complete",
  "review_status": "needs_review",
  "llm_eligible": true,
  "llm_required": false,
  "recommended_action": "review_before_optional_briefing",
  "counts": {
    "window_count": 4,
    "windows_successfully_loaded": 4,
    "windows_missing_or_failed": 0,
    "candidate_rows_total": 18,
    "candidate_index_count": 15,
    "dedup_removed_by_request_id": 3,
    "possible_duplicate_count": 0,
    "noise_group_count_total": 2
  },
  "signals": {
    "has_candidates": true,
    "has_missing_windows": false,
    "has_repeated_src_ip": true,
    "has_repeated_uri": true,
    "has_repeated_reason_hint_prefix": true,
    "has_payload_like_reason_hint": true,
    "is_quiet": false
  },
  "top_observed": {
    "src_ip": [
      {"value": "192.168.56.114", "count": 8}
    ],
    "uri": [
      {"value": "/search.php", "count": 4}
    ],
    "reason_hint_prefix": [
      {"value": "sqli_hint", "count": 3}
    ],
    "status_code": [
      {"value": "403", "count": 5}
    ]
  },
  "guardrails": {
    "summary_only": true,
    "apache_logs_only": true,
    "no_success_inference": true,
    "no_body_inference": true,
    "no_context_promotion": true,
    "no_new_security_verdict": true
  }
}
```

## 6. Queue summary v1 후보 schema

```json
{
  "schema": "sliding_window_operator_queue_summary_v1",
  "queue_date": "2026-05-24",
  "generated_at": "2026-05-24T23:59:00+09:00",
  "source_rollup_root": "data/rollups/2026-05-24",
  "counts": {
    "rollup_items_total": 6,
    "needs_review": 2,
    "quiet": 3,
    "incomplete": 1,
    "llm_eligible": 2,
    "llm_required": 0
  },
  "items_path": "data/operator_queue/2026-05-24/queue_items.json",
  "guardrails": {
    "summary_only": true,
    "apache_logs_only": true,
    "no_success_inference": true,
    "no_body_inference": true,
    "no_context_promotion": true,
    "no_new_security_verdict": true
  }
}
```

## 7. Status taxonomy

### data_quality_status

```text
complete
  - source windows loaded
  - rollup_summary incomplete_analysis=false

incomplete_missing_window
  - one or more source windows missing
  - rollup_summary incomplete_analysis=true

degraded_invalid_window
  - one or more source window_summary failed schema/json validation

empty_no_rollup
  - expected rollup artifact not found
```

이 상태는 보안 판단이 아니라 데이터 품질 상태다.

### review_status

```text
quiet
  - candidate_index_count=0
  - missing/invalid window 없음

needs_review
  - candidate_index_count>0
  - operator should inspect queue item or rollup_summary

data_quality_check
  - missing/invalid window 있음
  - LLM보다 data completeness 확인 우선

deferred
  - operator intentionally postponed review

reviewed
  - operator reviewed item
```

`review_status`는 보안 verdict가 아니다.

### recommended_action

허용 후보:

```text
skip_no_candidates
review_rollup_summary
review_before_optional_briefing
data_quality_check
optional_llm_briefing
optional_deep_analysis
```

금지 후보:

```text
confirmed_attack
confirmed_intrusion
critical_incident
exploit_success
data_leak
account_takeover
```

## 8. LLM eligibility

Operator Queue는 LLM 실행 여부를 강제하지 않는다.

권장 표현:

```text
llm_eligible: true/false
llm_required: false
```

`llm_required=true`는 v1에서 사용하지 않는다.

이유:

- Apache logs-only artifact만으로 LLM 실행이 필수라고 단정하지 않는다.
- LLM 비용과 운영 피로를 줄인다.
- 사람이 먼저 queue를 보고 escalation 여부를 결정할 수 있다.

초기 `llm_eligible=true` 후보:

```text
- candidate_index_count > 0
- data_quality_status == complete
- has_payload_like_reason_hint == true
- repeated src_ip/uri/reason_hint_prefix가 관찰됨
```

초기 `llm_eligible=false` 후보:

```text
- quiet rollup
- incomplete_missing_window
- empty_no_rollup
```

단, `llm_eligible=true`는 공격/침해 가능성을 뜻하지 않는다. 단지 LLM briefing을 요청할 수 있는 입력 품질과 신호량이 있다는 뜻이다.

## 9. Single Rollup Reporter 위치

팀원 제안의 Single Rollup Reporter 방향은 유효하다.

다만 v1 operator queue 설계에서는 바로 구현하지 않는다.

가능한 다음 단계:

```text
Operator Queue
  -> selected queue item
  -> llm_rollup_briefing.py
  -> rollup_observation_brief.md
```

이 reporter는 detection engine이 아니다.

권장 이름:

```text
llm_rollup_briefing.py
llm_rollup_observation_reporter.py
llm_rollup_review_brief.py
```

권장 출력명:

```text
rollup_observation_brief.md
rollup_observation_brief.json
```

금지 출력명:

```text
confirmed_incident_report.md
attack_success_report.md
breach_report.md
```

## 10. 기존 Stage1/Stage2 위치

기존 Stage1/Stage2는 다음 위치로 재정의한다.

```text
legacy/deep-analysis path
```

즉, 기본 scheduler path가 아니다.

가능한 향후 경로:

```text
selected queue item
  -> projection/adapter
  -> existing Stage1
  -> existing Stage2
```

그러나 projection은 v1 operator queue 범위 밖이다.

Stage1/Stage2를 유지하는 이유:

- 기존 fixture/test 자산이 있다.
- 상세 후보별 LLM 평가가 필요한 경우 사용할 수 있다.
- 기존 Web UI viewer_payload 흐름과 연결되어 있다.

기본 운영에서 내려놓는 이유:

- 모든 rollup에 Stage1/Stage2를 돌리면 비용과 review 대상이 증가한다.
- 사람이 먼저 봐야 할 queue/data quality 상태가 Stage2 report 뒤에 묻힌다.
- Rollup이 이미 dedup/merge/summary를 수행하므로 Stage1의 역할을 재검토할 수 있다.

## 11. Web UI 관점

초기 구현은 file artifact만 만든다.

향후 Web UI 후보:

```text
Operator Queue list
  - date
  - time range
  - data_quality_status
  - review_status
  - candidate_index_count
  - dedup_removed_by_request_id
  - missing window count
  - llm_eligible
  - recommended_action

Operator Queue detail
  - top src_ip / uri / reason_hint_prefix / status_code
  - source rollup links
  - source window links
  - candidate drilldown
```

Web UI 원칙:

```text
- read-only
- queue status는 보안 verdict가 아님
- severity/category/verdict 재계산 금지
- context-only 승격 금지
```

## 12. Daily summary와의 관계

Daily summary는 raw log를 다시 분석하지 않는다.

권장 입력:

```text
queue_summary.json
queue_items.json
selected rollup_observation_brief.md/json
optional Stage2 report metadata
```

Daily summary의 역할:

- 하루의 rollup queue 상태 요약
- quiet/incomplete/review 대상 개수 요약
- 사람이 검토한 항목과 남은 항목 요약
- LLM briefing을 실행한 경우 그 결과에 대한 짧은 색인

Daily summary도 success/intrusion/data exposure를 새로 단정하지 않는다.

## 13. Non-goals

Operator Queue v1은 다음을 하지 않는다.

```text
- Stage1 실행
- Stage2 실행
- Single Rollup Reporter 실행
- Web UI 변경
- DB/API integration
- severity/category/final verdict 계산
- confidence_score/threat_level 계산
- attack success 판단
- exploit success 판단
- data exposure 판단
- account takeover 판단
- upload saved 판단
- context-only 승격
```

## 14. 구현 후보

문서 확정 후 구현 후보:

```text
src/sliding_window_operator_queue.py
tests/test_sliding_window_operator_queue.py
```

입력 후보:

```text
data/rollups/<date>/rollup_*/rollup_summary.json
data/rollups/<date>/rollup_*/rollup_input.json
```

출력 후보:

```text
data/operator_queue/<date>/queue_items.json
data/operator_queue/<date>/queue_summary.json
```

초기 CLI 후보:

```bash
python3 src/sliding_window_operator_queue.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-root data/rollups \
  --out-root data/operator_queue \
  --pretty
```

output reuse policy는 Rollup과 같은 보수적 정책을 따른다.

```text
output 2종 모두 없음 -> written
output 2종 모두 있음 + --overwrite 없음 -> skipped_existing
output 일부만 있음 + --overwrite 없음 -> partial existing error
--overwrite -> 재생성
```

## 15. 테스트 후보

```text
test_queue_loads_rollup_summaries
test_queue_marks_quiet_rollup
test_queue_marks_needs_review_when_candidates_exist
test_queue_marks_data_quality_check_for_incomplete_rollup
test_queue_sets_llm_eligible_without_llm_required
test_queue_does_not_create_security_verdict
test_queue_top_observed_is_distribution_only
test_queue_output_reuse_policy
```

## 16. 다음 판단

다음 단계는 바로 LLM reporter 구현이 아니라 다음 중 하나를 선택한다.

1. Operator Queue 문서 보강
   - status taxonomy 확정
   - item schema 확정
   - queue summary schema 확정

2. Operator Queue v1 최소 구현
   - rollup_summary 기반 queue item 생성
   - LLM 없음
   - Web UI 없음

3. Single Rollup Reporter 설계
   - operator queue 이후 optional briefing으로 설계
   - detection engine이 아니라 observation briefing으로 제한

권장 순서:

```text
Operator Queue 문서 확정
  -> Operator Queue v1 구현
  -> Single Rollup Reporter 설계
  -> projection/Stage1/Stage2 deep-analysis path 재검토
```

## 17. Guardrail

이 문서는 [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

특히 다음 원칙을 유지한다.

```text
- Apache access/security/error log만으로 공격 성공, 침해 성공, 노출 성공, 인증 성공, 서버 내부 상태를 단정하지 않는다.
- summary와 rollup은 원본 evidence보다 강한 보안 판정을 만들면 안 된다.
- operator queue는 보안 verdict가 아니라 review routing artifact다.
- LLM briefing은 optional이며, detection engine이 아니다.
```
