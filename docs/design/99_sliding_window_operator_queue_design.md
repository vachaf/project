# 99_sliding_window_operator_queue_design

- 문서 상태: v1 구현 기준 명세 / v1 최소 구현 완료
- 기준 시점: 2026-05-25
- 목적: Sliding Window / Rollup 이후 사람이 먼저 봐야 할 운영 queue 모델을 정의한다.
- 구현 상태: `src/sliding_window_operator_queue.py` / `tests/test_sliding_window_operator_queue.py` 추가 완료

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

Operator Queue v1 결정:

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

생성 파일:

```text
data/operator_queue/<date>/queue_items.json
data/operator_queue/<date>/queue_summary.json
```

입력 파일:

```text
data/rollups/<date>/rollup_*/rollup_input.json
data/rollups/<date>/rollup_*/rollup_summary.json
```

v1의 입력 선택은 단순하다. 지정한 날짜의 `data/rollups/<date>/rollup_*` 디렉터리를 모두 읽는다.

v1.1에서는 운영용 rollup과 smoke/실험 rollup을 분리하기 위해 `--rollup-pattern`과 rollup naming convention을 추가 검토한다.

## 3. v1 구현 상태

구현 파일:

```text
src/sliding_window_operator_queue.py
tests/test_sliding_window_operator_queue.py
```

구현 범위:

```text
- rollup_input.json / rollup_summary.json 로드
- queue_items.json / queue_summary.json 생성
- quiet / needs_review / data_quality_check routing
- data_quality_status 파생
- llm_eligible 파생
- llm_required=false 고정
- top_observed distribution 생성
- payload-like reason hint allowlist 상수화
- atomic write 적용
- output reuse policy 적용
```

명시적 제외 범위:

```text
- Stage1 실행
- Stage2 실행
- Single Rollup Reporter 실행
- Web UI 변경
- DB/API integration
- 보안 verdict 생성
- confidence_score / threat_level 생성
- attack success / exploit success / data leak / account takeover 판단
- context-only 승격
```

## 4. 검증 상태

Unit 검증:

```text
python3 -m py_compile src/sliding_window_operator_queue.py
python3 -m pytest -q tests/test_sliding_window_operator_queue.py
# 13 passed
```

Sliding Window / Rollup / Operator Queue quick bundle:

```text
python3 -m pytest -q \
  tests/test_sliding_window_operator_queue.py \
  tests/test_sliding_window_rollup.py \
  tests/test_sliding_window_summary.py \
  tests/test_sliding_window_scheduler_summary.py \
  tests/test_sliding_window_scheduler.py \
  tests/test_prepare_llm_input_output_names.py \
  tests/test_explain_prepare_candidates.py \
  tests/test_prepare_status_error_only_candidate_policy.py \
  tests/test_prepare_scanner_probe_candidate_policy.py
# 69 passed
```

Actual smoke:

```text
python3 src/sliding_window_operator_queue.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --overwrite \
  --pretty
```

Smoke 결과:

```text
status=written
out_dir=data/operator_queue/2026-05-24
rollup_items_total=2
quiet=0
needs_review=2
data_quality_check=0
llm_eligible=2
llm_required=0
```

생성 artifact:

```text
data/operator_queue/2026-05-24/queue_items.json
data/operator_queue/2026-05-24/queue_summary.json
```

Allowlist 보정 smoke:

```text
rollup_20260524_0200_0300: has_payload_like_reason_hint=true, llm_eligible=true, recommended_action=review_before_optional_briefing
rollup_20260524_0200_0400: has_payload_like_reason_hint=true, llm_eligible=true, recommended_action=review_before_optional_briefing
```

## 5. 왜 Stage1/Stage2를 기본값으로 두지 않는가

기존 Stage1/Stage2 구조는 단일 큰 `export.json` 또는 큰 prepare output을 LLM에 직접 넣기 어렵던 제약에서 나온 구조다.

현재는 전단에 다음 레이어가 생겼다.

```text
window prepare
  -> window_summary.json
  -> rollup_input.json
  -> dedup_candidates.json
  -> rollup_summary.json
  -> operator queue
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

## 6. 사람이 먼저 보는 것

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

## 7. Artifact layout

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

## 8. Queue source selection / cadence 분리

Operator Queue가 무엇을 대표하는지 명확해야 한다.

운영 queue의 기본 의미는 다음과 같다.

```text
Operator Queue = 운영자가 먼저 볼 운영용 rollup 목록
```

따라서 smoke/실험 rollup은 기본 운영 queue에 섞지 않는다.

문제 예시:

```text
data/rollups/2026-05-24/
  rollup_20260524_0200_0300/
  rollup_20260524_0200_0400/
```

두 rollup은 모두 같은 날짜 아래 있고 둘 다 `needs_review`가 될 수 있다. 그러나 첫 번째는 1시간 smoke이고, 두 번째는 2시간 overlap/missing-window smoke일 수 있다. 이 상태에서 queue가 둘 다 읽으면 운영자가 보는 queue가 운영 현황이 아니라 실험 artifact 목록처럼 보일 수 있다.

따라서 v1.1에서는 다음 두 가지를 함께 검토한다.

```text
B. --rollup-pattern 옵션
C. rollup naming convention
```

B + C 조합을 우선 검토한다.

```text
B 단독
  - pattern은 있으나 naming이 약하면 의미가 흔들릴 수 있다.

C 단독
  - naming은 있으나 queue 입력을 강제하지 못한다.

B + C
  - naming으로 의미를 부여하고 pattern으로 입력을 제한한다.
```

### v1.1 후보: --rollup-pattern

CLI 후보:

```bash
python3 src/sliding_window_operator_queue.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-pattern "rollup_ops_*" \
  --pretty
```

동작 후보:

```text
- 기본값은 현재와 호환되도록 rollup_* 로 둔다.
- pattern은 rollup directory name에만 적용한다.
- path 전체가 아니라 directory basename에 적용한다.
- Python fnmatch 기준 glob pattern을 사용한다.
- pattern에 매칭되는 rollup만 queue item 후보가 된다.
```

### v1.1 후보: rollup naming convention

운영용 rollup 후보:

```text
rollup_ops_<cadence>_<HHMM>_<HHMM>
rollup_ops_4h_0200_0600
rollup_ops_1h_0200_0300
```

smoke/실험용 rollup 후보:

```text
rollup_smoke_<purpose>_<HHMM>_<HHMM>
rollup_smoke_single_0200_0300
rollup_smoke_overlap_0200_0400
rollup_smoke_missing_0200_0400
```

주의:

```text
- naming convention은 보안 의미를 만들지 않는다.
- ops/smoke는 운영 artifact와 실험 artifact의 source selection을 구분하기 위한 label이다.
- rollup_id label만으로 공격/침해/성공 여부를 표현하지 않는다.
```

### v1.1 후보: empty queue semantics

`--rollup-pattern`을 지정했는데 매칭되는 rollup이 0개일 수 있다.

예:

```bash
python3 src/sliding_window_operator_queue.py \
  --date 2026-05-24 \
  --rollup-pattern "rollup_ops_*" \
  --pretty
```

아직 운영 rollup이 생성되지 않았으면 매칭 결과는 0개다.

이 경우는 오류가 아니다.

권장 동작:

```text
status=written
rollup_items_total=0
quiet=0
needs_review=0
data_quality_check=0
llm_eligible=0
llm_required=0
```

`queue_summary.json`에는 입력 source selection metadata를 남긴다.

```json
{
  "source_selection": {
    "rollup_root": "data/rollups/2026-05-24",
    "rollup_pattern": "rollup_ops_*",
    "matched_rollup_count": 0
  }
}
```

이 상태는 다음 중 하나로 해석한다.

```text
- 해당 날짜에 운영 rollup이 아직 생성되지 않았다.
- pattern이 너무 좁다.
- smoke/실험 rollup만 존재한다.
```

하지만 이것은 보안적으로 quiet하다는 뜻은 아니다.

```text
empty queue != quiet day
```

`quiet`은 rollup이 존재하고 `candidate_index_count=0`인 상태다. 매칭된 rollup이 0개인 상태는 관찰 대상 자체가 없는 것이므로 `quiet`으로 계산하지 않는다.

### v1.1 테스트 후보

```text
test_rollup_pattern_includes_matching_rollups_only
test_rollup_pattern_excludes_smoke_rollups
test_default_rollup_pattern_keeps_existing_rollup_star_behavior
test_empty_rollup_pattern_match_writes_empty_queue_not_quiet
test_source_selection_metadata_records_pattern_and_match_count
```

## 9. Queue items file schema

`queue_items.json`은 top-level object로 저장한다. 단순 list로 저장하지 않는다.

```json
{
  "schema": "sliding_window_operator_queue_items_v1",
  "queue_date": "2026-05-24",
  "generated_at": "2026-05-24T23:59:00+09:00",
  "source_rollup_root": "data/rollups/2026-05-24",
  "items": [],
  "guardrails": {}
}
```

v1.1에서 `--rollup-pattern`을 추가하면 `queue_items.json`에도 `source_selection` metadata를 추가한다.

```json
{
  "source_selection": {
    "rollup_root": "data/rollups/2026-05-24",
    "rollup_pattern": "rollup_ops_*",
    "matched_rollup_count": 0
  }
}
```

`items`의 각 항목은 `sliding_window_operator_queue_item_v1` 구조를 따른다.

## 10. Queue item v1 schema

```json
{
  "schema": "sliding_window_operator_queue_item_v1",
  "queue_date": "2026-05-24",
  "generated_at": "2026-05-24T23:59:00+09:00",
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
  "counts": {},
  "signals": {},
  "top_observed": {},
  "guardrails": {}
}
```

## 11. Queue summary v1 schema

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
  "guardrails": {}
}
```

v1.1에서 `--rollup-pattern`을 추가하면 `queue_summary.json`에도 `source_selection` metadata를 추가한다.

## 12. Status taxonomy

### data_quality_status

v1 허용값:

```text
complete
incomplete_missing_window
degraded_invalid_window
missing_rollup_artifact
```

파생 우선순위:

```text
missing_rollup_artifact
  > degraded_invalid_window
  > incomplete_missing_window
  > complete
```

규칙:

```text
missing_rollup_artifact
  - rollup_input.json 또는 rollup_summary.json이 없음

degraded_invalid_window
  - rollup_input/rollup_summary schema가 기대값과 다름
  - 또는 source_windows 중 status == failed 존재

incomplete_missing_window
  - rollup_summary.incomplete_analysis == true
  - 또는 counts.windows_missing_or_failed > 0

complete
  - rollup_input/rollup_summary 둘 다 로드 성공
  - windows_missing_or_failed == 0
  - incomplete_analysis == false
```

### review_status

v1 허용값:

```text
quiet
needs_review
data_quality_check
```

규칙:

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

### operator_state

v1 generator는 항상 다음 값을 쓴다.

```text
unreviewed
```

향후 UI나 별도 state file에서 다음 값을 사용할 수 있다.

```text
deferred
reviewed
```

### recommended_action

v1 허용값:

```text
skip_no_candidates
review_rollup_summary
data_quality_check
review_before_optional_briefing
```

v1 generator는 다음 값을 만들지 않는다.

```text
optional_llm_briefing
optional_deep_analysis
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

## 13. LLM eligibility

Operator Queue는 LLM 실행 여부를 강제하지 않는다.

v1 규칙:

```text
llm_required == false
```

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

## 14. Signal derivation rules

```text
has_candidates
  - candidate_index_count > 0

has_missing_windows
  - windows_missing_or_failed > 0

has_possible_duplicates
  - possible_duplicate_count > 0

has_repeated_src_ip
  - candidate_src_ip distribution 중 count >= 2인 값이 있음

has_repeated_uri
  - candidate_uri distribution 중 count >= 2인 값이 있음

has_repeated_reason_hint_prefix
  - candidate_reason_hint_prefix distribution 중 count >= 2인 값이 있음

is_quiet
  - candidate_index_count == 0 and data_quality_status == complete
```

### has_payload_like_reason_hint

Allowlist는 코드에서 `PAYLOAD_LIKE_REASON_HINTS` set 상수로 관리한다.

현재 allowlist:

```text
sqli
sqli_hint
xss
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

Allowlist에 넣지 않는 현재 관찰 prefix:

```text
upload
login_endpoint
auth_payload_content_type
error_linked
error_status
```

주의:

```text
- allowlist는 payload-like observation group일 뿐이다.
- 성공/침해 판단이 아니다.
- sqli/xss 추가는 실제 prepare/rollup reason prefix에 맞춘 routing signal 정렬이다.
- score/verdict_hint/candidate visibility는 변경하지 않는다.
- LLM required로 승격하지 않는다.
```

## 15. top_observed derivation rules

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

## 16. Output reuse / atomic write

Operator Queue v1은 Rollup과 같은 보수적 output reuse policy를 따른다.

```text
output 2종 모두 없음 -> written
output 2종 모두 있음 + --overwrite 없음 -> skipped_existing
output 일부만 있음 + --overwrite 없음 -> partial existing error
--overwrite -> 재생성
```

쓰기 작업은 atomic write를 사용한다.

```text
.<filename>.tmp 작성
os.replace(tmp, final)
```

테스트에서 `.tmp` 파일이 남지 않는지 확인한다.

## 17. Single Rollup Reporter 위치

팀원 제안의 Single Rollup Reporter 방향은 유효하다.

다만 v1 operator queue 설계에서는 구현하지 않는다.

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

## 18. 기존 Stage1/Stage2 위치

기존 Stage1/Stage2는 다음 위치로 재정의한다.

```text
legacy/deep-analysis path
```

가능한 향후 경로:

```text
selected queue item
  -> projection/adapter
  -> existing Stage1
  -> existing Stage2
```

그러나 projection은 v1 operator queue 범위 밖이다.

## 19. Web UI 관점

초기 구현은 file artifact만 만든다.

향후 Web UI 후보:

```text
Operator Queue list
Operator Queue detail
source rollup/window drilldown
```

Web UI 원칙:

```text
- read-only
- queue status는 보안 verdict가 아님
- severity/category/verdict 재계산 금지
- context-only 승격 금지
```

## 20. Daily summary와의 관계

Daily summary는 raw log를 다시 분석하지 않는다.

권장 입력:

```text
queue_summary.json
queue_items.json
selected rollup_observation_brief.md/json
optional Stage2 report metadata
```

Daily summary도 success/intrusion/data exposure를 새로 단정하지 않는다.

## 21. Non-goals

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

Operator Queue v1.1 source selection도 다음을 하지 않는다.

```text
- pattern name으로 보안 의미 생성
- ops/smoke label로 보안 verdict 생성
- empty pattern match를 quiet day로 해석
```

## 22. 테스트 기준 및 현황

구현된 테스트:

```text
test_queue_marks_quiet_rollup
test_queue_marks_needs_review_and_llm_eligible_for_payload_like_candidate
test_queue_treats_sqli_and_xss_prefix_variants_as_payload_like
test_queue_does_not_treat_context_prefixes_as_payload_like_by_themselves
test_queue_marks_data_quality_check_for_incomplete_rollup
test_queue_marks_degraded_invalid_window_for_failed_source_window
test_queue_marks_missing_rollup_artifact
test_queue_summary_counts_statuses
test_queue_does_not_create_security_verdict_fields
test_queue_output_reuse_policy_skips_existing
test_queue_output_reuse_policy_fails_partial_existing
test_queue_output_reuse_policy_overwrite_recreates
test_atomic_write_does_not_leave_tmp_files
```

검증 상태:

```text
tests/test_sliding_window_operator_queue.py -> 13 passed
sliding window/operator/rollup/scheduler/candidate policy quick bundle -> 69 passed
```

v1.1 source selection 테스트 후보:

```text
test_rollup_pattern_includes_matching_rollups_only
test_rollup_pattern_excludes_smoke_rollups
test_default_rollup_pattern_keeps_existing_rollup_star_behavior
test_empty_rollup_pattern_match_writes_empty_queue_not_quiet
test_source_selection_metadata_records_pattern_and_match_count
```

## 23. 다음 판단

다음 단계는 바로 LLM reporter 구현이 아니라 다음 중 하나를 선택한다.

1. Operator Queue source selection 구현
   - `--rollup-pattern` 추가
   - 기본값은 `rollup_*`
   - source_selection metadata 추가
   - empty match는 오류가 아닌 empty queue로 처리

2. Single Rollup Reporter 설계
   - operator queue 이후 optional briefing으로 설계
   - detection engine이 아니라 observation briefing으로 제한

3. Rollup v1.1 hint 설계
   - uri_family_hints / low_and_slow_hints는 hint-only로 유지
   - candidate_index 또는 Stage1 후보로 승격하지 않는다.

권장 순서:

```text
Operator Queue allowlist 보정 완료
  -> source selection / cadence 분리 구현
  -> Single Rollup Reporter 설계
  -> projection/Stage1/Stage2 deep-analysis path 재검토
```

## 24. Guardrail

이 문서는 [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

특히 다음 원칙을 유지한다.

```text
- Apache access/security/error log만으로 공격 성공, 침해 성공, 노출 성공, 인증 성공, 서버 내부 상태를 단정하지 않는다.
- summary와 rollup은 원본 evidence보다 강한 보안 판정을 만들면 안 된다.
- operator queue는 보안 verdict가 아니라 review routing artifact다.
- LLM briefing은 optional이며, detection engine이 아니다.
```
