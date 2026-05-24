# 99_sliding_window_operator_queue_design

- 문서 상태: v1 구현 기준 명세
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

## 2. v1 결정 사항

Operator Queue v1에서 확정한 결정은 다음과 같다.

```text
- queue artifact는 data/operator_queue/<date>/ 아래에 생성한다.
- queue_items.json은 하루치 rollup item list다.
- queue_summary.json은 하루치 queue aggregate summary다.
- queue는 LLM을 실행하지 않는다.
- queue는 Stage1/Stage2를 실행하지 않는다.
- queue는 Web UI를 수정하지 않는다.
- queue는 보안 verdict를 만들지 않는다.
- queue는 사람에게 보여줄 review routing artifact다.
```

v1에서 생성하는 파일:

```text
data/operator_queue/<date>/queue_items.json
data/operator_queue/<date>/queue_summary.json
```

v1에서 읽는 파일:

```text
data/rollups/<date>/rollup_*/rollup_input.json
data/rollups/<date>/rollup_*/rollup_summary.json
```

## 3. 왜 Stage1/Stage2를 기본값으로 두지 않는가

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

## 4. 사람은 무엇을 먼저 봐야 하는가

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

## 5. Artifact layout

v1 layout:

```text
data/operator_queue/
  2026-05-24/
    queue_summary.json
    queue_items.json
```

rollup directory 안에 `operator_item.json`을 두는 대안은 v1에서 채택하지 않는다.

이유:

- 사람은 rollup별 디렉터리를 직접 탐색하지 않는다.
- 하루치 queue를 한 파일로 정렬/필터링하기 쉽다.
- Web UI가 나중에 읽기 쉽다.
- rollup artifact와 operator review routing artifact를 분리할 수 있다.

## 6. Queue items file schema

`queue_items.json`은 top-level object로 저장한다. 단순 list로 저장하지 않는다.

```json
{
  "schema": "sliding_window_operator_queue_items_v1",
  "queue_date": "2026-05-24",
  "generated_at": "2026-05-24T23:59:00+09:00",
  "source_rollup_root": "data/rollups/2026-05-24",
  "items": []
}
```

`items`의 각 항목은 `sliding_window_operator_queue_item_v1` 구조를 따른다.

## 7. Queue item v1 schema

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
  "operator_state": "unreviewed",
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
    "has_possible_duplicates": false,
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

### 필드 설명

```text
schema
  - 항상 sliding_window_operator_queue_item_v1

queue_date
  - KST 기준 YYYY-MM-DD

rollup_id
  - source rollup id

rollup_path
  - repo root 기준 rollup_input.json 상대경로

rollup_summary_path
  - repo root 기준 rollup_summary.json 상대경로

time_range
  - rollup_summary.rollup에서 복사

data_quality_status
  - data completeness 상태
  - 보안 verdict가 아님

review_status
  - queue routing 상태
  - 보안 verdict가 아님

operator_state
  - 사람 review workflow 상태
  - v1 생성 시 기본 unreviewed

llm_eligible
  - optional LLM briefing에 넘길 수 있는 입력 상태인지 표시
  - 공격/침해 가능성을 뜻하지 않음

llm_required
  - v1에서는 항상 false

recommended_action
  - 운영 routing action
  - 보안 verdict가 아님

counts
  - rollup_summary.counts 기반

top_observed
  - rollup_input.distributions 기반 observed distribution
  - anomaly/success 판단이 아님
```

## 8. Queue summary v1 schema

```json
{
  "schema": "sliding_window_operator_queue_summary_v1",
  "queue_date": "2026-05-24",
  "generated_at": "2026-05-24T23:59:00+09:00",
  "source_rollup_root": "data/rollups/2026-05-24",
  "counts": {
    "rollup_items_total": 6,
    "quiet": 3,
    "needs_review": 2,
    "data_quality_check": 1,
    "complete": 5,
    "incomplete_missing_window": 1,
    "degraded_invalid_window": 0,
    "missing_rollup_artifact": 0,
    "llm_eligible": 2,
    "llm_required": 0,
    "unreviewed": 6,
    "reviewed": 0,
    "deferred": 0
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

## 9. Status taxonomy

### data_quality_status enum

v1 허용값:

```text
complete
incomplete_missing_window
degraded_invalid_window
missing_rollup_artifact
```

파생 규칙:

```text
missing_rollup_artifact
  - rollup_input.json 또는 rollup_summary.json이 없음

incomplete_missing_window
  - rollup_summary.incomplete_analysis == true
  - 또는 counts.windows_missing_or_failed > 0

degraded_invalid_window
  - rollup_summary.source_windows 중 status == failed 존재
  - 또는 rollup_input/rollup_summary schema가 기대값과 다름

complete
  - rollup_input/rollup_summary 둘 다 로드 성공
  - windows_missing_or_failed == 0
  - incomplete_analysis == false
```

우선순위:

```text
missing_rollup_artifact
  > degraded_invalid_window
  > incomplete_missing_window
  > complete
```

이 상태는 보안 판단이 아니라 데이터 품질 상태다.

### review_status enum

v1 허용값:

```text
quiet
needs_review
data_quality_check
```

파생 규칙:

```text
data_quality_check
  - data_quality_status != complete

quiet
  - data_quality_status == complete
  - candidate_index_count == 0

needs_review
  - data_quality_status == complete
  - candidate_index_count > 0
```

`review_status`는 보안 verdict가 아니다. 이것은 사람이 어떤 queue item을 먼저 열어볼지 정하는 routing field다.

### operator_state enum

v1 생성 시 허용값:

```text
unreviewed
```

향후 UI나 별도 state file에서 허용할 수 있는 값:

```text
deferred
reviewed
```

v1 generator는 `deferred`나 `reviewed`를 만들지 않는다. 이 값들은 사람의 후속 workflow 상태다.

### recommended_action enum

v1 허용값:

```text
skip_no_candidates
review_rollup_summary
data_quality_check
review_before_optional_briefing
```

향후 후보:

```text
optional_llm_briefing
optional_deep_analysis
```

v1 generator는 `optional_llm_briefing`, `optional_deep_analysis`를 만들지 않는다. 이 둘은 operator queue 이후 escalation 설계에서 검토한다.

파생 규칙:

```text
data_quality_status != complete
  -> data_quality_check

review_status == quiet
  -> skip_no_candidates

review_status == needs_review and llm_eligible == true
  -> review_before_optional_briefing

review_status == needs_review and llm_eligible == false
  -> review_rollup_summary
```

금지 값:

```text
confirmed_attack
confirmed_intrusion
critical_incident
exploit_success
data_leak
account_takeover
breach
compromise
```

## 10. LLM eligibility

Operator Queue는 LLM 실행 여부를 강제하지 않는다.

v1 규칙:

```text
llm_required == false
```

항상 false다.

`llm_eligible=true`는 공격/침해 가능성을 뜻하지 않는다. 단지 optional LLM briefing을 요청할 수 있는 입력 품질과 관찰 신호량이 있다는 뜻이다.

v1 `llm_eligible=true` 조건:

```text
data_quality_status == complete
and candidate_index_count > 0
and (
  has_payload_like_reason_hint == true
  or has_repeated_src_ip == true
  or has_repeated_uri == true
  or has_repeated_reason_hint_prefix == true
)
```

v1 `llm_eligible=false` 조건:

```text
data_quality_status != complete
or candidate_index_count == 0
or no observed eligibility signal
```

## 11. Signal derivation rules

### has_candidates

```text
candidate_index_count > 0
```

### has_missing_windows

```text
windows_missing_or_failed > 0
```

### has_possible_duplicates

```text
possible_duplicate_count > 0
```

### has_repeated_src_ip

```text
candidate_src_ip distribution 중 count >= 2인 값이 있음
```

### has_repeated_uri

```text
candidate_uri distribution 중 count >= 2인 값이 있음
```

### has_repeated_reason_hint_prefix

```text
candidate_reason_hint_prefix distribution 중 count >= 2인 값이 있음
```

### has_payload_like_reason_hint

초기 allowlist:

```text
sqli_hint
xss_hint
path_traversal_candidate
cmdi_hint
hpp_hint
php_wrapper_hint
file_disclosure_hint
log4shell_jndi_hint
ssrf_like_target
ssti_hint
xxe_hint
webshell_like
```

이 allowlist는 payload-like observation group일 뿐이다. 성공/침해 판단이 아니다.

### is_quiet

```text
candidate_index_count == 0
and data_quality_status == complete
```

## 12. top_observed derivation rules

`top_observed`는 `rollup_input.distributions`에서 가져온다.

매핑:

```text
top_observed.src_ip
  <- distributions.candidate_src_ip

top_observed.uri
  <- distributions.candidate_uri

top_observed.reason_hint_prefix
  <- distributions.candidate_reason_hint_prefix

top_observed.status_code
  <- distributions.candidate_status_code
```

정렬:

```text
count desc
value asc
```

v1 기본 limit:

```text
5
```

주의:

```text
- top_observed는 관찰 분포다.
- anomaly ranking이 아니다.
- 공격자 attribution이 아니다.
- status_code 분포는 성공/실패 판단이 아니다.
```

## 13. Single Rollup Reporter 위치

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

## 14. 기존 Stage1/Stage2 위치

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

## 15. Web UI 관점

초기 구현은 file artifact만 만든다.

향후 Web UI 후보:

```text
Operator Queue list
  - date
  - time range
  - data_quality_status
  - review_status
  - operator_state
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

## 16. Daily summary와의 관계

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

## 17. Non-goals

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
- llm_required=true 생성
- optional_llm_briefing action 생성
```

## 18. 구현 후보

문서 확정 후 구현 후보:

```text
src/sliding_window_operator_queue.py
tests/test_sliding_window_operator_queue.py
```

입력:

```text
data/rollups/<date>/rollup_*/rollup_summary.json
data/rollups/<date>/rollup_*/rollup_input.json
```

출력:

```text
data/operator_queue/<date>/queue_items.json
data/operator_queue/<date>/queue_summary.json
```

초기 CLI:

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

## 19. 테스트 기준

v1 구현 시 필요한 테스트:

```text
test_queue_loads_rollup_summaries
test_queue_marks_quiet_rollup
test_queue_marks_needs_review_when_candidates_exist
test_queue_marks_data_quality_check_for_incomplete_rollup
test_queue_marks_missing_rollup_artifact
test_queue_sets_llm_eligible_without_llm_required
test_queue_does_not_create_security_verdict
test_queue_top_observed_is_distribution_only
test_queue_payload_like_reason_hint_allowlist
test_queue_status_derivation_precedence
test_queue_output_reuse_policy
```

## 20. 다음 판단

다음 단계는 바로 LLM reporter 구현이 아니라 다음 중 하나를 선택한다.

1. Operator Queue v1 최소 구현
   - rollup_summary/rollup_input 기반 queue item 생성
   - LLM 없음
   - Web UI 없음

2. Operator Queue 문서 추가 검토
   - enum/status/action 명칭을 팀 내에서 확정
   - payload-like allowlist 보정

3. Single Rollup Reporter 설계
   - operator queue 이후 optional briefing으로 설계
   - detection engine이 아니라 observation briefing으로 제한

권장 순서:

```text
Operator Queue v1 구현
  -> Operator Queue smoke
  -> Single Rollup Reporter 설계
  -> projection/Stage1/Stage2 deep-analysis path 재검토
```

## 21. Guardrail

이 문서는 [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

특히 다음 원칙을 유지한다.

```text
- Apache access/security/error log만으로 공격 성공, 침해 성공, 노출 성공, 인증 성공, 서버 내부 상태를 단정하지 않는다.
- summary와 rollup은 원본 evidence보다 강한 보안 판정을 만들면 안 된다.
- operator queue는 보안 verdict가 아니라 review routing artifact다.
- LLM briefing은 optional이며, detection engine이 아니다.
```
