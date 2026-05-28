# 99_sliding_window_operator_queue_item_detail

- 문서 상태: 구현 완료 / CLI preview v1
- 기준 시점: 2026-05-25
- 목적: Operator Queue item 하나를 사람이 어떻게 읽고 drilldown할지 정의한다.
- 구현: `src/sliding_window_operator_queue_detail.py`
- 테스트: `tests/test_sliding_window_operator_queue_detail.py`

관련 문서:

- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
- [99_sliding_window_single_rollup_observation_brief.md](./99_sliding_window_single_rollup_observation_brief.md)
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

v1 구현 결론:

```text
- queue item 원본 schema를 확장하지 않는다.
- 새 detail artifact를 생성하지 않는다.
- queue_items.json과 rollup_input.json을 읽어 stdout으로 deterministic preview를 출력한다.
- Stage1/Stage2/LLM을 호출하지 않는다.
- 보안 verdict, success 판단, threat score를 만들지 않는다.
```

## 2. 구현 상태

구현 파일:

```text
src/sliding_window_operator_queue_detail.py
```

입력:

```text
data/operator_queue/<date>/queue_items.json
data/rollups/<date>/<rollup_id>/rollup_input.json  # payload-like prefix 보강용, optional fallback 있음
```

출력:

```text
stdout
```

지원 포맷:

```text
--format text      # 기본값, plain text heading
--format markdown  # markdown heading
--format json      # detail view JSON stdout
```

새로 만들지 않는 것:

```text
- detail artifact file
- Stage1 result
- Stage2 report
- viewer_payload
- LLM output
- security verdict
- severity/category/final verdict
- confidence_score/threat_level
```

## 3. CLI 사용법

기본 text preview:

```bash
python3 src/sliding_window_operator_queue_detail.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-id rollup_20260524_0200_0400
```

Markdown preview:

```bash
python3 src/sliding_window_operator_queue_detail.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-id rollup_20260524_0200_0400 \
  --format markdown
```

JSON preview:

```bash
python3 src/sliding_window_operator_queue_detail.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-id rollup_20260524_0200_0400 \
  --format json
```

주의:

```text
- preview는 파일을 저장하지 않는다.
- queue가 먼저 생성되어 있어야 한다.
- 최근 queue를 rollup_ops_*로 overwrite해 empty queue가 된 경우, rollup_* 등 원하는 pattern으로 queue를 다시 생성한 뒤 실행한다.
```

## 4. 출력 순서

기본 text 출력 순서:

```text
Operator Queue Item Detail
==========================
Rollup ID: ...
Queue date: ...

1. Data quality
2. Review routing
3. Scope
4. Counts
5. Observed signals
6. Top observed distributions
7. Drilldown
8. Source selection
9. Apache logs-only notes
10. Non-conclusions
```

기본 `--format text`에서는 `##` markdown heading을 쓰지 않는다.

`--format markdown`에서만 다음처럼 markdown heading을 쓴다.

```text
# Operator Queue Item Detail
## 1. Data quality
## 2. Review routing
...
```

## 5. Detail view schema

JSON 출력의 schema:

```json
{
  "schema": "sliding_window_operator_queue_item_detail_view_v1",
  "queue_date": "2026-05-24",
  "rollup_id": "rollup_20260524_0200_0400",
  "summary": {},
  "quality_assessment": {},
  "routing": {},
  "counts": {},
  "observed_signals": {},
  "top_observed": {},
  "drilldown": {},
  "source_selection": {},
  "apache_logs_only_notes": [],
  "non_conclusions": [],
  "guardrails": {}
}
```

이 view는 원본 evidence가 아니다.

```text
- queue item과 rollup artifact를 사람이 읽기 쉽게 재배열한 projection이다.
- 원본 확인은 rollup_input.json, rollup_summary.json, source window_summary, analysis_candidates, export에서 한다.
```

## 6. Data quality

표시 항목:

```text
- status
- missing_or_failed_windows
- possible_duplicates_marked
- dedup_removed_by_request_id
```

해석:

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

## 7. Review routing

표시 항목:

```text
- review_status
- operator_state
- recommended_action
- llm_eligible
- llm_required
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

`llm_required`는 v1에서 `false`를 유지한다.

## 8. Counts

표시 항목:

```text
- window_count
- windows_successfully_loaded
- windows_missing_or_failed
- candidate_rows_total
- candidate_index_count
- dedup_removed_by_request_id
- possible_duplicate_count
- noise_group_count_total
```

주의:

```text
candidate_index_count는 confirmed finding 수가 아니다.
noise_group_count_total은 안전 판단이 아니다.
dedup_removed_by_request_id는 overlap window 중복 제거 수다.
```

## 9. Observed signals

표시 항목:

```text
- has_candidates
- has_payload_like_reason_hint
- has_repeated_src_ip
- has_repeated_uri
- has_repeated_reason_hint_prefix
- has_missing_windows
- has_possible_duplicates
- is_quiet
- matched_payload_like_reason_prefixes
```

`matched_payload_like_reason_prefixes`는 detail CLI에서 추가 표시한다.

예시:

```text
- matched_payload_like_reason_prefixes: xss (5), sqli (1)
```

필요성:

```text
- top_observed.reason_hint_prefix는 top limit 때문에 일부 prefix가 가려질 수 있다.
- has_payload_like_reason_hint=yes인데 어떤 prefix 때문인지 사람이 확인하기 어려울 수 있다.
- 따라서 rollup_input.json의 distributions.candidate_reason_hint_prefix 전체를 읽어 payload-like prefix를 별도로 표시한다.
```

fallback:

```text
- rollup_input.json을 읽을 수 있으면 전체 distribution에서 계산한다.
- rollup_input.json을 읽을 수 없으면 queue item의 top_observed.reason_hint_prefix에서 계산한다.
```

주의:

```text
has_payload_like_reason_hint
  - payload-like observation group이 있음
  - 공격 성공 판단이 아님

matched_payload_like_reason_prefixes
  - allowlist와 매칭된 reason prefix 관찰값
  - severity/ranking/성공 판단이 아님
```

## 10. Top observed distributions

현재 queue item은 다음을 포함한다.

```text
top_observed.src_ip
top_observed.uri
top_observed.reason_hint_prefix
top_observed.status_code
```

실제 smoke 예시:

```text
- src_ip: 192.168.56.1 (5)
- uri: /error.php (2), /login.php (1), /private/secret.txt (1), /upload.php (1)
- reason_hint_prefix: error_linked (5), error_status (5), xss (5), auth_payload_content_type (1), login_endpoint (1)
- status_code: 403 (2), 400 (1), 401 (1), 500 (1)
```

주의:

```text
- top_observed는 분포 요약이다.
- ranking이나 severity가 아니다.
- status_code 분포는 성공/실패 판단이 아니다.
- src_ip 분포는 공격자 식별이 아니다.
```

## 11. Drilldown

표시 항목:

```text
- rollup_input_path
- rollup_summary_path
- candidate_source
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

## 12. Source selection

표시 항목:

```text
- rollup_root
- rollup_pattern
- matched_rollup_count
```

이 정보는 현재 queue가 어떤 rollup 집합을 대상으로 생성됐는지 확인하기 위한 것이다.

주의:

```text
rollup_pattern은 보안 의미가 아니다.
matched_rollup_count=0은 quiet day가 아니다.
```

## 13. Apache logs-only notes

detail CLI는 다음 notes를 포함한다.

```text
- This detail view is derived from Apache log artifacts only.
- It does not include raw POST body, response body, DB result, browser execution, or server-side application state.
- HTTP 200, text/html, response_body_bytes, or repeated requests are not success evidence by themselves.
- Review status, LLM eligibility, and recommended action are routing signals, not security verdicts.
```

## 14. Non-conclusions

detail CLI는 다음 non-conclusion을 포함한다.

```text
This detail view does not conclude attack success, intrusion, data exposure, account takeover, upload persistence, browser execution, DB impact, or server compromise.
```

## 15. Empty queue와 quiet item 구분

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

## 16. 검증 결과

로컬 검증:

```bash
python3 -m py_compile src/sliding_window_operator_queue_detail.py
python3 -m pytest -q tests/test_sliding_window_operator_queue_detail.py
```

결과:

```text
7 passed
```

quick bundle:

```bash
python3 -m pytest -q \
  tests/test_sliding_window_operator_queue_detail.py \
  tests/test_sliding_window_operator_queue.py \
  tests/test_sliding_window_rollup.py \
  tests/test_sliding_window_summary.py \
  tests/test_sliding_window_scheduler_summary.py \
  tests/test_sliding_window_scheduler.py \
  tests/test_prepare_llm_input_output_names.py \
  tests/test_explain_prepare_candidates.py \
  tests/test_prepare_status_error_only_candidate_policy.py \
  tests/test_prepare_scanner_probe_candidate_policy.py
```

결과:

```text
80 passed
```

테스트 범위:

```text
- detail view 생성 확인
- text 출력 섹션 순서 확인
- markdown heading 확인
- 없는 rollup_id 오류 확인
- verdict/success/threat 관련 금지 필드 미생성 확인
- CLI json 출력 확인
- CLI missing rollup 오류 확인
- matched_payload_like_reason_prefixes 출력 확인
```

## 17. Actual smoke 결과

Queue 재생성:

```bash
python3 src/sliding_window_operator_queue.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-pattern "rollup_*" \
  --overwrite \
  --pretty
```

결과:

```text
matched_rollup_count=2
rollup_items_total=2
quiet=0
needs_review=2
data_quality_check=0
llm_eligible=2
llm_required=0
```

Detail preview:

```bash
python3 src/sliding_window_operator_queue_detail.py \
  --work-dir /opt/web_log_analysis \
  --date 2026-05-24 \
  --rollup-id rollup_20260524_0200_0400
```

확인:

```text
- 기본 text 출력에서 markdown ## heading이 제거됨.
- matched_payload_like_reason_prefixes: xss (5), sqli (1) 표시됨.
- top_observed.reason_hint_prefix에서는 top limit 때문에 sqli가 보이지 않지만, observed_signals에서 별도로 확인 가능함.
- llm_required: no 유지.
- Apache logs-only notes / Non-conclusions 포함.
```

## 18. Non-goals

Queue item detail CLI preview는 다음을 하지 않는다.

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
- artifact 저장
```

## 19. 다음 단계

다음 구현 후보:

```text
src/sliding_window_rollup_observation_brief.py
```

범위:

```text
- selected rollup 하나를 markdown/text로 stdout 출력
- 새 artifact 생성 없음
- Stage1/Stage2/LLM 호출 없음
- 보안 verdict/success/threat score 생성 없음
```
