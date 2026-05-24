# 99_sliding_window_rollup_quick_reference

- 문서 상태: 빠른 참조 / v1 정렬본
- 기준 시점: 2026-05-24
- 기준 문서: `docs/design/99_sliding_window_rollup_input_review.md`

## 한 줄 설명

`sliding_window_rollup.py`는 여러 `window_summary.json`을 합쳐 request_id 중복을 제거하고 cross-window hint를 요약해 `sliding_window_rollup_input_v1` artifact를 만든다.

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

## v1에서 하는 일

```text
- window_summary.json 로드
- window 상태 기록
- request_id 기준 dedup
- request_id 없는 후보 보존
- candidate_index merge
- distributions 합산
- uri_family_hints 생성
- low_and_slow_hints 생성
- guardrails 기록
```

## v1에서 하지 않는 일

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
```

## candidate_index 규칙

`candidate_index`에는 기존 window candidate만 들어간다.

허용:

```text
single_window_existing_candidate
cross_window_same_request_id
```

v1에서 candidate_index에 넣지 않음:

```text
cross_window_uri_family
low_and_slow_pattern
cross_window_ip_behavior
```

이 값들은 `rollup_context` hint로만 둔다.

## request_id dedup

```text
1차 key: request_id
동일 request_id가 여러 window에 있으면 하나로 merge
source_window_ids에 모든 window 기록
first_seen/last_seen은 가능한 경우 확장
```

`request_id`가 비어 있으면 버리지 않는다.

```text
fallback key:
src_ip + method + uri + status_code + reason_hint_prefixes
```

fallback은 충돌 가능성이 있으므로 기본적으로 제거하지 않고 `possible_duplicate`로 표시한다.

## uri_family_hints

```json
{
  "src_ip": "192.168.56.1",
  "uri_prefix": "/api/v1/admin/*",
  "uri_variants": [
    "/api/v1/admin/users",
    "/api/v1/admin/roles"
  ],
  "occurrences": 3,
  "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
  "derived_from_request_ids": ["req_1", "req_2", "req_3"],
  "hint_only": true
}
```

Stage1 후보로 승격하지 않는다.

## low_and_slow_hints

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
  "inter_request_gaps_seconds": [1800, 1800],
  "derived_from_request_ids": ["req_a", "req_b", "req_c"],
  "hint_only": true
}
```

Stage1 후보로 승격하지 않는다.

## Stage1/Stage2

v1 표현:

```text
Stage1/Stage2 호환성은 목표다.
기존 코드 무수정은 아직 보장하지 않는다.
```

필요하면 `candidate_index`에서 `analysis_candidates` projection을 생성한다.

제한:

```text
- projection은 기존 candidate의 형태 변환만 수행
- 새 score/verdict_hint 생성 금지
- uri_family/low_and_slow hint 승격 금지
```

## CLI 예시

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

## 구현 체크리스트

```text
[ ] schema = sliding_window_rollup_input_v1
[ ] module = src/sliding_window_rollup.py
[ ] tests = tests/test_sliding_window_rollup.py
[ ] request_id 없는 후보 보존
[ ] fallback duplicate는 marked_only_not_removed
[ ] score/verdict_hint 새 생성 없음
[ ] low_and_slow는 rollup_context hint only
[ ] uri_family는 rollup_context hint only
[ ] guardrails 포함
[ ] missing window 상태 기록
[ ] Stage1 compatibility는 별도 테스트
```

## 권장 커밋 메시지

```text
docs: align sliding window rollup input design
```
