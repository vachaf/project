# 99_sliding_window_rollup_input_format

- 문서 상태: 채택 후보 / v1.0 포맷 정렬본
- 기준 시점: 2026-05-24
- 작성 배경: 안수홍님 작성 Rollup Input 포맷 초안을 `docs/design/99_sliding_window_rollup_input_review.md` 기준으로 축소/정렬
- 적용 범위: Apache logs-only LLM pipeline의 Sliding Window summary artifact rollup

## 1. 결론

Rollup Input v1.0은 탐지 엔진이 아니다.

```text
window_summary.json 여러 개
  -> request_id dedup
  -> candidate_index merge
  -> src_ip / uri / method / status_code / reason_hint_prefix 분포 합산
  -> data/rollups/<date>/<rollup_id>/rollup_input.json
```

v1.0의 역할은 Stage1/Stage2가 더 긴 기간의 후보와 context를 볼 수 있도록 summary/index artifact를 만드는 것이다.

v1.0은 다음을 하지 않는다.

```text
- raw Apache event 재해석
- raw_request/raw query string 복제
- response body / DB 결과 / browser execution 추론
- status_code=200을 성공으로 해석
- confidence_score / threat_level / final verdict 계산
- context-only 항목을 finding/incident로 승격
- prepare score/filtering/policy 재계산
- uri_family/low_and_slow hint 생성
- Stage1 analysis_candidates projection 생성
```

`uri_family_hints`, `low_and_slow_hints`는 v1.1 후보로 분리한다. Stage1 호환 `analysis_candidates` projection은 v1.5 후보로 분리한다.

## 2. 스키마 이름

```json
{
  "schema": "sliding_window_rollup_input_v1"
}
```

스키마 이름은 `v1`로 유지하되, 구현 범위 문서에서는 `v1.0`, `v1.1`, `v1.5`를 구분한다.

기존 초안의 `rollup_input_v1` 명칭은 repo의 Sliding Window 계열 artifact와 맞추기 위해 사용하지 않는다.

## 3. 입력

입력은 raw event list가 아니라 `window_summary.json` 목록이다.

```text
data/windowed/<date>/sw_*/window_summary.json
```

각 window summary에서 v1.0이 사용하는 필드는 다음으로 제한한다.

```text
schema
window
artifact_status
source
counts.export
counts.prepare
distributions
candidate_index
rollup_hints
guardrails
```

`raw_log`, `raw_request`, `user_agent`, `referer`는 rollup input에 복제하지 않는다.

## 4. 출력 위치

```text
data/rollups/<date>/<rollup_id>/rollup_input.json
data/rollups/<date>/<rollup_id>/dedup_candidates.json
data/rollups/<date>/<rollup_id>/rollup_summary.json
```

`rollup_input.json`은 LLM 단계에 넘길 수 있는 summary/index artifact다.  
`dedup_candidates.json`은 dedup 과정 검토용이다.  
`rollup_summary.json`은 운영자/UI 검토용 compact summary다.

v1.0에서는 세 파일 모두 파일 artifact로만 생성한다. DB 저장, FastAPI endpoint, Web UI 통합은 포함하지 않는다.

## 5. 최상위 구조

```json
{
  "schema": "sliding_window_rollup_input_v1",
  "rollup": {
    "rollup_id": "rollup_20260524_0200_0600",
    "start": "2026-05-24T02:00:00+09:00",
    "end_exclusive": "2026-05-24T06:00:00+09:00",
    "timezone": "Asia/Seoul",
    "duration_minutes": 240
  },
  "source_windows": [],
  "counts": {},
  "dedup": {},
  "distributions": {},
  "candidate_index": [],
  "rollup_context": {},
  "guardrails": {}
}
```

## 6. rollup

```json
{
  "rollup": {
    "rollup_id": "rollup_20260524_0200_0600",
    "start": "2026-05-24T02:00:00+09:00",
    "end_exclusive": "2026-05-24T06:00:00+09:00",
    "timezone": "Asia/Seoul",
    "duration_minutes": 240
  }
}
```

시간대는 현재 repo artifact와 맞춰 `Asia/Seoul`을 기본으로 둔다.

## 7. source_windows

`source_windows.path`는 repo root 기준 상대경로로 기록한다. rollup directory 기준 상대경로는 깊이가 달라질 때 혼동될 수 있으므로 v1.0에서는 사용하지 않는다.

```json
{
  "source_windows": [
    {
      "window_id": "sw_0200_0300",
      "path": "data/windowed/2026-05-24/sw_0200_0300/window_summary.json",
      "start": "2026-05-24T02:00:00+09:00",
      "end_exclusive": "2026-05-24T03:00:00+09:00",
      "artifact_status": {
        "llm_input": true,
        "analysis_candidates": true,
        "noise_summary": true,
        "window_summary": true
      },
      "status": "loaded"
    }
  ]
}
```

불완전한 window가 있으면 제외하지 않고 상태를 남긴다.

```json
{
  "window_id": "sw_0300_0400",
  "path": "data/windowed/2026-05-24/sw_0300_0400/window_summary.json",
  "status": "missing",
  "reason": "window_summary_not_found"
}
```

## 8. counts

```json
{
  "counts": {
    "window_count": 4,
    "windows_successfully_loaded": 3,
    "windows_missing_or_failed": 1,
    "export_total": 1200,
    "prepare_total_exported_rows": 1200,
    "candidate_rows_total": 87,
    "candidate_request_ids_total": 87,
    "candidate_request_ids_distinct": 82,
    "dedup_removed_by_request_id": 5,
    "possible_duplicate_count": 2,
    "noise_group_count_total": 11,
    "candidate_index_count": 82
  }
}
```

`candidate_index_count`는 v1.0에서 Stage1 후보로 투영 가능한 dedup 후 기존 후보 수를 의미한다. Rollup-derived hint는 여기에 포함하지 않는다.

## 9. dedup

1차 dedup key는 `request_id`다.

```json
{
  "dedup": {
    "primary_key": "request_id",
    "fallback_key": [
      "src_ip",
      "method",
      "uri",
      "status_code",
      "reason_hint_prefixes"
    ],
    "duplicate_request_ids": [
      {
        "request_id": "req_abc",
        "source_window_ids": ["sw_0200_0300", "sw_0230_0330"],
        "kept_source_window_id": "sw_0200_0300",
        "removed_count": 1,
        "action": "merged_by_request_id"
      }
    ],
    "possible_duplicates": [
      {
        "fallback_key": "192.168.56.1|GET|/admin|404|sensitive_path_probe",
        "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
        "action": "marked_only_not_removed"
      }
    ]
  }
}
```

`request_id`가 없는 후보는 버리지 않는다. fallback key는 충돌 가능성이 있으므로 기본 동작은 제거가 아니라 `possible_duplicate` 표시다.

## 10. candidate_index

`candidate_index`는 여러 window의 후보를 request_id 기준으로 dedup한 결과다.

```json
{
  "candidate_index": [
    {
      "request_id": "req_abc",
      "src_ip": "192.168.56.1",
      "method": "GET",
      "uri": "/admin/config.php",
      "status_code": 403,
      "score": 6,
      "verdict_hint": "suspicious",
      "reason_hint_prefixes": [
        "sensitive_path_probe",
        "static_baseline_anomaly"
      ],
      "source_window_ids": ["sw_0200_0300"],
      "aggregation_type": "single_window_existing_candidate"
    }
  ]
}
```

허용되는 `aggregation_type`은 v1.0에서 다음으로 제한한다.

```text
single_window_existing_candidate
cross_window_same_request_id
preserved_missing_request_id
```

다음 값은 v1.0에서 `candidate_index`에 넣지 않는다.

```text
cross_window_uri_family
low_and_slow_pattern
cross_window_ip_behavior
```

이 값들은 v1.1에서 `rollup_context`의 hint로만 검토한다.

## 11. Stage1 호환 투영

Stage1 호환 `analysis_candidates` projection은 v1.0 구현 범위에서 제외한다.

v1.5 후보로 별도 검토한다.

중요 제한:

```text
- projection은 dedup된 기존 candidate_index의 형태 변환만 수행해야 한다.
- uri_family / low_and_slow / false_positive_review 항목을 analysis_candidates에 새로 넣지 않는다.
- projection 과정에서 score, verdict_hint, severity, confidence를 새로 만들지 않는다.
- Stage1/Stage2 호환성은 별도 fixture test로 확인해야 한다.
```

## 12. distributions

```json
{
  "distributions": {
    "candidate_status_code": {
      "200": 12,
      "403": 7,
      "404": 18
    },
    "candidate_method": {
      "GET": 31,
      "POST": 6
    },
    "candidate_src_ip": {
      "192.168.56.1": 20
    },
    "candidate_uri": {
      "/admin/config.php": 4
    },
    "candidate_reason_hint_prefix": {
      "sensitive_path_probe": 9,
      "sqli_hint": 3
    }
  }
}
```

분포는 관찰값이다. 성공/침해 판단에 사용하지 않는다.

## 13. rollup_context

v1.0의 `rollup_context`는 최소 notes만 담는다.

```json
{
  "rollup_context": {
    "notes": [
      "rollup_context is informational only",
      "v1.0 does not generate uri_family_hints or low_and_slow_hints",
      "stage1/stage2 may use rollup_input later, but rollup does not promote context"
    ]
  }
}
```

`uri_family_hints`와 `low_and_slow_hints`는 v1.1 후보로 분리한다.

v1.1 후보 예시는 다음과 같다.

```json
{
  "uri_family_hints": [
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
  ],
  "low_and_slow_hints": [
    {
      "src_ip": "192.168.56.2",
      "reason_hint_prefix": "sqli_hint",
      "source_window_ids": ["sw_0200_0300", "sw_0300_0400", "sw_0400_0500"],
      "occurrences": 3,
      "derived_from_request_ids": ["req_a", "req_b", "req_c"],
      "hint_only": true
    }
  ]
}
```

v1.1에서도 이 hint들은 Stage1 후보로 승격하지 않는다.

## 14. guardrails

```json
{
  "guardrails": {
    "summary_only": true,
    "apache_logs_only": true,
    "no_new_security_verdict": true,
    "no_success_inference": true,
    "no_body_inference": true,
    "no_context_promotion": true,
    "no_policy_recalculation": true,
    "preserve_prepare_scores": true
  }
}
```

## 15. v1.0 / v1.1 / v1.5 / v2 범위

### v1.0

```text
- window_summary 수집
- missing/invalid window 상태 기록
- request_id dedup
- request_id 없는 후보 보존
- fallback duplicate는 marked_only_not_removed
- candidate_index merge
- distribution merge
- rollup_input.json 생성
- dedup_candidates.json 생성
- rollup_summary.json 생성
```

### v1.1 후보

```text
- uri_family_hints
- low_and_slow_hints
- repeated src_ip / repeated uri / repeated reason_hint_prefix hint
- inter_request_gaps_seconds
```

### v1.5 후보

```text
- Stage1 호환 analysis_candidates projection
- Stage1/Stage2 rollup input 호환성 테스트
```

### v2 후보

```text
- derived candidate promotion 정책
- derived candidate 전용 score/verdict_hint 금지 규칙
- Web UI rollup view
- DB/API integration
```

v2에서도 raw body/DB/browser/success inference 금지는 유지한다.
