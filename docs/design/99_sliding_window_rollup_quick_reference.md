# 99_sliding_window_rollup_quick_reference

- 문서 상태: 빠른 참조 / v1.0 정렬본
- 기준 시점: 2026-05-24
- 기준 문서: `docs/design/99_sliding_window_rollup_input_review.md`

## 한 줄 설명

`sliding_window_rollup.py`는 여러 `window_summary.json`을 합쳐 request_id 중복을 제거하고 `sliding_window_rollup_input_v1` artifact를 만든다.

v1.0은 최소 rollup이다. `uri_family_hints`, `low_and_slow_hints`, Stage1 호환 projection은 만들지 않는다.

## 파일 흐름

```text
data/windowed/<date>/sw_*/window_summary.json
  ↓
src/sliding_window_rollup.py
  ↓
data/rollups/<date>/<rollup_id>/
  ├── rollup_input.json
  ├── dedup_candidates.json
  └── rollup_summary.json
```

## 핵심 스키마

```json
{
  "schema": "sliding_window_rollup_input_v1",
  "rollup": {},
  "source_windows": [],
  "counts": {},
  "dedup": {},
  "distributions": {},
  "candidate_index": [],
  "rollup_context": {},
  "guardrails": {}
}
```

## v1.0에서 하는 일

```text
- window_summary.json 로드
- window 상태 기록
- request_id 기준 dedup
- request_id 없는 후보 보존
- fallback duplicate는 표시만 하고 제거하지 않음
- candidate_index merge
- distributions 합산
- counts 계산
- dedup report 생성
- guardrails 기록
- rollup_input.json 생성
- dedup_candidates.json 생성
- rollup_summary.json 생성
```

## v1.0에서 하지 않는 일

```text
- raw log 재분석
- raw_request/raw query string 복제
- response body, DB result, browser execution 추론
- status_code=200을 성공으로 판단
- confidence_score 계산
- threat_level 계산
- final verdict 계산
- prepare score 변경
- filtering logic 변경
- false_positive_review_candidates 자동 필터링
- context-only 항목을 analysis candidate로 승격
- uri_family_hints 생성
- low_and_slow_hints 생성
- Stage1 analysis_candidates projection 생성
```

## candidate_index 규칙

`candidate_index`에는 기존 window candidate만 들어간다.

허용:

```text
single_window_existing_candidate
cross_window_same_request_id
preserved_missing_request_id
```

v1.0에서 candidate_index에 넣지 않음:

```text
cross_window_uri_family
low_and_slow_pattern
cross_window_ip_behavior
```

이 값들은 v1.1 이후 hint로만 검토한다.

## request_id dedup

```text
1차 key: request_id
동일 request_id가 여러 window에 있으면 하나로 merge
source_window_ids에 모든 window 기록
```

`request_id`가 비어 있으면 버리지 않는다.

```text
fallback key:
src_ip + method + uri + status_code + reason_hint_prefixes
```

fallback은 충돌 가능성이 있으므로 제거하지 않고 `possible_duplicate`로 표시한다.

## source_windows path

`source_windows.path`는 repo root 기준 상대경로로 기록한다.

```json
{
  "window_id": "sw_0200_0300",
  "path": "data/windowed/2026-05-24/sw_0200_0300/window_summary.json",
  "status": "loaded"
}
```

rollup directory 기준 상대경로는 v1.0에서 사용하지 않는다.

## rollup_context

v1.0의 `rollup_context`는 최소 notes만 담는다.

```json
{
  "rollup_context": {
    "notes": [
      "rollup_context is informational only",
      "v1.0 does not generate uri_family_hints or low_and_slow_hints",
      "rollup does not promote context to candidate"
    ]
  }
}
```

## v1.1 후보: uri_family_hints

```json
{
  "src_ip": "192.168.56.1",
  "uri_prefix": "/api/v1/admin/*",
  "uri_variants": [
    "/api/v1/admin/users",
    "/api/v1/admin/roles"
  ],
  "occurrences": 2,
  "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
  "derived_from_request_ids": ["req_1", "req_2"],
  "hint_only": true
}
```

Stage1 후보로 승격하지 않는다.

## v1.1 후보: low_and_slow_hints

```json
{
  "src_ip": "192.168.56.2",
  "reason_hint_prefix": "sqli_hint",
  "source_window_ids": [
    "sw_0200_0300",
    "sw_0300_0400",
    "sw_0400_0500"
  ],
  "occurrences": 3,
  "derived_from_request_ids": ["req_a", "req_b", "req_c"],
  "hint_only": true
}
```

Stage1 후보로 승격하지 않는다.

## Stage1/Stage2

v1.0 표현:

```text
Stage1/Stage2 호환성은 목표다.
기존 코드 무수정은 아직 보장하지 않는다.
v1.0에서는 analysis_candidates projection을 생성하지 않는다.
```

필요하면 v1.5에서 `candidate_index`를 `analysis_candidates`로 projection한다.

제한:

```text
- projection은 기존 candidate의 형태 변환만 수행
- 새 score/verdict_hint 생성 금지
- uri_family/low_and_slow hint 승격 금지
```

## CLI 예시

기본 output 후보:

```text
data/rollups/<date>/rollup_YYYYMMDD_HHMM_HHMM
```

명시적으로 지정할 수도 있다.

```bash
python3 src/sliding_window_rollup.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-24 02:00:00" \
  --analysis-end "2026-05-24 06:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --out-dir data/rollups/2026-05-24/rollup_20260524_0200_0600 \
  --pretty
```

## v1.0 구현 체크리스트

```text
[ ] schema = sliding_window_rollup_input_v1
[ ] module = src/sliding_window_rollup.py
[ ] tests = tests/test_sliding_window_rollup.py
[ ] source_windows.path = repo root 기준 relative path
[ ] request_id 없는 후보 보존
[ ] fallback duplicate는 marked_only_not_removed
[ ] score/verdict_hint 새 생성 없음
[ ] low_and_slow는 v1.0에서 미생성
[ ] uri_family는 v1.0에서 미생성
[ ] guardrails 포함
[ ] missing window 상태 기록
[ ] Stage1 compatibility는 v1.5 별도 테스트
```

## v1.1 후보 체크리스트

```text
[ ] uri_family_hints hint-only 생성
[ ] low_and_slow_hints hint-only 생성
[ ] inter_request_gaps_seconds 계산
[ ] hint를 candidate_index 또는 analysis_candidates로 승격하지 않음
```

## 권장 커밋 메시지

```text
docs: align sliding window rollup input design
```
