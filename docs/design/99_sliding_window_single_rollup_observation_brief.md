# 99_sliding_window_single_rollup_observation_brief

- 문서 상태: 설계 초안 / 구현 전 판단 문서
- 기준 시점: 2026-05-25
- 목적: Operator Queue 이후 선택된 rollup 하나를 사람이 읽기 쉬운 observation brief로 정리하는 방식을 정의한다.
- 관련 구현 후보: 미정
- 관련 입력 후보: `queue_items.json`, `rollup_input.json`, `rollup_summary.json`

관련 문서:

- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
- [99_sliding_window_operator_queue_item_detail.md](./99_sliding_window_operator_queue_item_detail.md)
- [99_sliding_window_rollup_input_format.md](./99_sliding_window_rollup_input_format.md)
- [99_sliding_window_rollup_pipeline_integration.md](./99_sliding_window_rollup_pipeline_integration.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

Single Rollup Observation Brief는 Stage2 report가 아니다.

역할은 다음과 같다.

```text
Operator Queue에서 선택한 rollup 하나를 사람이 빠르게 읽을 수 있게 정리하는 관찰 요약
```

따라서 이름도 `Single Rollup Reporter`보다 `Single Rollup Observation Brief`가 적절하다.

이 brief는 detection engine이 아니다.

```text
- 공격 성공 판단을 하지 않는다.
- 침해 판단을 하지 않는다.
- 파일 유출 판단을 하지 않는다.
- 계정 탈취 판단을 하지 않는다.
- DB 영향이나 브라우저 실행 결과를 추론하지 않는다.
- severity/category/final verdict를 새로 만들지 않는다.
```

## 2. 기존 Stage2와의 차이

기존 Stage2:

```text
prepare output
  -> Stage1
  -> Stage2
  -> viewer_payload
  -> 사람이 report 확인
```

Observation Brief:

```text
operator queue item
  -> rollup_input / rollup_summary
  -> observation brief
  -> 사람이 drilldown 여부 판단
```

차이:

```text
Stage2
  - LLM 분석 report
  - 기존 finding/report 중심
  - viewer_payload로 Web UI 표시

Observation Brief
  - rollup 관찰 요약
  - queue item 하나의 운영 검토 보조
  - detection/report가 아니라 briefing
```

Observation Brief가 Stage2를 대체하지 않는다.

가능한 위치:

```text
Operator Queue
  -> selected queue item
  -> Observation Brief
  -> optional human drilldown
  -> optional Stage1/Stage2 deep-analysis
```

## 3. 사용자 관점

운영자가 먼저 보는 것은 queue다.

```text
queue_summary.json
queue_items.json
```

사용자는 queue item 하나를 선택한 뒤 다음을 알고 싶다.

```text
- 이 rollup은 왜 needs_review인가?
- 데이터 품질은 complete인가?
- 후보는 몇 개인가?
- 반복 관찰된 src_ip/uri/reason prefix가 있는가?
- 어떤 source window로 내려가야 하는가?
- Apache logs-only 기준으로 어떤 한계가 있는가?
- LLM deep-analysis가 아니라 사람이 먼저 확인할 포인트는 무엇인가?
```

Observation Brief는 이 질문에 답하는 짧은 문서다.

## 4. 입력 artifact

필수 입력 후보:

```text
data/operator_queue/<date>/queue_items.json
data/rollups/<date>/<rollup_id>/rollup_input.json
data/rollups/<date>/<rollup_id>/rollup_summary.json
```

선택 입력 후보:

```text
data/windowed/<date>/<window_id>/window_summary.json
```

v1 brief는 window_summary를 직접 열지 않아도 작성 가능해야 한다.

권장 입력 원칙:

```text
- rollup_input.json과 rollup_summary.json의 summary/index 정보만 사용한다.
- raw log, raw_request, POST body, response body를 복제하지 않는다.
- candidate_index의 축약 필드만 사용한다.
```

## 5. 출력 후보

파일 출력 후보:

```text
data/operator_queue/<date>/briefs/<rollup_id>_observation_brief.md
data/operator_queue/<date>/briefs/<rollup_id>_observation_brief.json
```

하지만 지금 즉시 파일 artifact를 만들 필요는 없다.

초기 구현이 필요하다면 우선순위는 다음과 같다.

```text
1. CLI preview
   - 선택한 rollup_id에 대해 stdout으로 brief 출력
   - 새 artifact 생성 없음

2. Markdown artifact
   - 사람이 읽기 쉬운 .md 저장

3. JSON artifact
   - Web UI나 daily summary가 구조화 입력을 필요로 할 때 추가
```

## 6. Brief 섹션 구조

권장 Markdown 구조:

```markdown
# Rollup Observation Brief

## 1. Scope
## 2. Data quality
## 3. Queue routing
## 4. Candidate overview
## 5. Top observed distributions
## 6. Dedup / duplicate notes
## 7. Source windows
## 8. Apache logs-only limitations
## 9. Suggested human checks
## 10. Non-conclusions
```

JSON 구조 후보:

```json
{
  "schema": "sliding_window_rollup_observation_brief_v1",
  "rollup_id": "rollup_20260524_0200_0400",
  "generated_at": "2026-05-25T12:00:00+09:00",
  "scope": {},
  "data_quality": {},
  "queue_routing": {},
  "candidate_overview": {},
  "top_observed": {},
  "dedup_notes": {},
  "source_windows": [],
  "apache_logs_only_limitations": [],
  "suggested_human_checks": [],
  "non_conclusions": [],
  "guardrails": {}
}
```

## 7. Scope 섹션

예시:

```text
Rollup: rollup_20260524_0200_0400
Range: 2026-05-24 02:00:00+09:00 ~ 2026-05-24 04:00:00+09:00
Timezone: Asia/Seoul
Source windows: 2 expected, 1 loaded, 1 missing/failed
```

목적:

```text
- 어떤 시간 범위를 보는지 명확히 한다.
- source window 완전성을 먼저 드러낸다.
```

## 8. Data quality 섹션

예시:

```text
Data quality: incomplete_missing_window
- windows_successfully_loaded: 1
- windows_missing_or_failed: 1
- incomplete_analysis: true

Interpretation:
- This rollup is incomplete because at least one source window summary is missing.
- Review data completeness before drawing operational conclusions.
```

주의:

```text
- complete는 안전하다는 뜻이 아니다.
- incomplete는 공격이 있다는 뜻이 아니다.
- data quality는 artifact 품질 상태다.
```

## 9. Queue routing 섹션

예시:

```text
Review status: needs_review
Recommended action: review_before_optional_briefing
LLM eligible: true
LLM required: false
```

해석:

```text
needs_review
  - 사람이 검토할 후보가 있다는 routing 상태
  - 공격/침해 판단이 아님

review_before_optional_briefing
  - optional brief 또는 drilldown 전에 사람이 queue item을 확인하라는 의미

llm_eligible
  - optional LLM briefing 가능
  - LLM 필수 또는 고위험 판단이 아님

llm_required
  - v1에서는 false 유지
```

## 10. Candidate overview 섹션

예시:

```text
Candidate overview:
- candidate_rows_total: 5
- candidate_index_count: 5
- noise_group_count_total: 0
- dedup_removed_by_request_id: 0
- possible_duplicate_count: 0
```

해석:

```text
candidate_index_count
  - rollup candidate index에 포함된 후보 수
  - confirmed finding 수가 아님

noise_group_count_total
  - prepare 단계의 noise/context group 집계
  - 안전 판단이 아님

dedup_removed_by_request_id
  - overlap window에서 동일 request_id 중복이 제거된 수
```

## 11. Top observed distributions 섹션

예시:

```text
Top observed:
- src_ip: 192.168.56.114 (5)
- uri: /search.php (5)
- reason_hint_prefix: xss (5), sqli (1), error_status (5)
- status_code: 500 (5)
```

주의:

```text
- top_observed는 분포 요약이다.
- ranking이나 severity가 아니다.
- src_ip 반복은 공격자 attribution이 아니다.
- uri 반복은 취약점 성공이 아니다.
- status_code는 성공/실패 판단이 아니다.
```

## 12. Dedup / duplicate notes 섹션

예시:

```text
Dedup notes:
- request_id based dedup removed 0 candidates.
- possible duplicate candidates without request_id: 0.
```

해석:

```text
- request_id가 있으면 request_id 기준 dedup이 가능하다.
- request_id 없는 fallback duplicate는 제거하지 않고 possible duplicate로 표시한다.
- duplicate 정보는 운영 검토용이며 보안 verdict가 아니다.
```

## 13. Source windows 섹션

예시:

```text
Source windows:
- sw_0200_0300: loaded
- sw_0300_0400: missing, reason=window_summary_not_found
```

목적:

```text
- 사람이 어떤 window_summary를 확인해야 하는지 알려준다.
- missing window가 있으면 먼저 artifact 생성 상태를 확인하게 한다.
```

## 14. Apache logs-only limitations 섹션

항상 포함할 문구 후보:

```text
This brief is derived from Apache log artifacts only.
It does not include raw POST body, response body, DB result, browser execution, or server-side application state.
HTTP 200, text/html, response_body_bytes, or repeated requests are not success evidence by themselves.
Review status, LLM eligibility, and recommended action are routing signals, not security verdicts.
```

한국어 표시 후보:

```text
이 brief는 Apache 로그 기반 artifact에서만 파생된다.
raw POST body, response body, DB 결과, 브라우저 실행 결과, 서버 내부 애플리케이션 상태는 포함하지 않는다.
HTTP 200, text/html, response_body_bytes, 반복 요청은 그 자체로 공격 성공/침해/유출 증거가 아니다.
review_status, llm_eligible, recommended_action은 운영 라우팅 신호이며 보안 verdict가 아니다.
```

## 15. Suggested human checks 섹션

예시:

```text
Suggested human checks:
1. Check data_quality_status before interpreting candidate counts.
2. Review top reason_hint_prefix and repeated uri/src_ip as observations.
3. Drill down to rollup_input.candidate_index for candidate rows.
4. Drill down to source window_summary for window-level context.
5. Do not infer success, compromise, or data exposure from this brief alone.
```

주의:

```text
- suggested checks는 사람이 확인할 순서다.
- 자동 incident 판단이 아니다.
```

## 16. Non-conclusions 섹션

Observation Brief는 명시적으로 다음을 말하지 않아야 한다.

```text
- 공격 성공
- 침해 성공
- exploit 성공
- 파일 유출
- 계정 탈취
- 업로드 저장 성공
- DB 영향
- 브라우저 실행 성공
- 서버 compromise
- admin access 성공
```

권장 문구:

```text
This brief does not conclude attack success, intrusion, data exposure, account takeover, upload persistence, browser execution, DB impact, or server compromise.
```

## 17. LLM 사용 여부

Observation Brief를 LLM 없이 만들 수 있는가?

```text
가능하다.
```

v1에서는 LLM 없이 deterministic brief를 만들 수 있다.

입력 artifact에 이미 다음이 있기 때문이다.

```text
- counts
- data_quality_status
- review_status
- signals
- top_observed
- source_windows
- candidate_index summary
```

LLM은 다음 단계의 optional 설명 보강에만 사용할 수 있다.

```text
Observation Brief deterministic builder
  -> optional LLM wording pass
```

다만 optional LLM wording pass도 detection engine이 아니다.

## 18. 구현 선택지

### 선택지 A: deterministic CLI brief builder

후보:

```text
src/sliding_window_rollup_observation_brief.py
```

입력:

```text
--work-dir
--date
--rollup-id
```

출력:

```text
stdout markdown
```

장점:

```text
- LLM 비용 없음
- 재현성 높음
- Apache logs-only guardrail 유지 쉬움
- 구현 범위 작음
```

단점:

```text
- 자연어 설명은 제한적
- Web UI 연동은 별도 작업
```

### 선택지 B: deterministic artifact builder

출력:

```text
data/operator_queue/<date>/briefs/<rollup_id>_observation_brief.md
```

장점:

```text
- Web UI나 daily summary에서 읽기 쉬움
```

단점:

```text
- artifact 수가 늘어남
- output reuse policy를 또 정의해야 함
```

### 선택지 C: optional LLM briefing

입력:

```text
rollup_observation_brief_input.json
```

출력:

```text
rollup_observation_brief_llm.md
```

장점:

```text
- 사람이 읽기 쉬운 문장으로 정리 가능
```

단점:

```text
- 비용 발생
- guardrail lint 필요
- Stage2 report와 혼동될 수 있음
```

## 19. 권장 판단

현재 권장 순서:

```text
1. deterministic CLI preview 설계
2. 필요하면 deterministic markdown artifact
3. Web UI detail tab에서 brief 표시
4. optional LLM wording pass는 마지막에 재검토
```

즉, 지금 바로 LLM reporter를 구현하지 않는다.

가장 작은 다음 구현 후보:

```text
src/sliding_window_rollup_observation_brief.py
  --work-dir /opt/web_log_analysis
  --date 2026-05-24
  --rollup-id rollup_20260524_0200_0400
  --format markdown
```

이 구현은 Stage1/Stage2/LLM을 호출하지 않는다.

## 20. Output reuse policy 후보

artifact를 저장하는 단계가 되면 다음 정책을 따른다.

```text
output 없음 -> written
output 있음 + --overwrite 없음 -> skipped_existing
partial output 있음 -> 실패
--overwrite -> 재생성
```

그러나 CLI preview-only 단계에서는 output reuse policy가 필요 없다.

## 21. 테스트 후보

```text
test_observation_brief_renders_complete_rollup
test_observation_brief_renders_incomplete_rollup_warning
test_observation_brief_does_not_claim_success_or_intrusion
test_observation_brief_includes_apache_logs_only_limitations
test_observation_brief_includes_source_windows
test_observation_brief_handles_empty_candidate_index
test_observation_brief_handles_missing_queue_item
```

## 22. Non-goals

Observation Brief 설계는 다음을 하지 않는다.

```text
- Stage1 실행
- Stage2 실행
- LLM 자동 실행
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
```

## 23. 구현 여부 판단

이 문서 기준 판단:

```text
LLM 기반 Single Rollup Reporter는 지금 구현하지 않는다.
```

대신 구현한다면 다음이 적절하다.

```text
1. deterministic CLI preview-only brief builder
2. markdown artifact 저장은 필요성이 확인된 뒤
3. optional LLM wording pass는 가장 나중
```

## 24. 다음 단계

다음에 할 일:

```text
1. Queue item detail 설계와 Observation Brief 설계 문서를 TODO/진행상황/작업일지에 반영한다.
2. deterministic CLI preview builder를 구현할지 판단한다.
3. 구현한다면 LLM/Stage1/Stage2 호출 없이 시작한다.
```
