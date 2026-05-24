# 99_sliding_window_rollup_input_review

- 문서 상태: 팀원 작성 Rollup Input 포맷 문서 intake / repo 기준 review
- 기준 시점: 2026-05-24
- 검토 대상: `rollup_input_format_design.md`
- 작성자 원문: 안수홍
- 목적: 팀원 문서의 Rollup Input 설계를 현재 Apache logs-only LLM pipeline과 Sliding Window artifact 구조에 맞게 수용/보류/수정할 범위를 정리한다.

관련 repo 문서:

- [99_sliding_window_adoption_review.md](./99_sliding_window_adoption_review.md)
- [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md)
- [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)
- [99_observability_run_summary_index.md](./99_observability_run_summary_index.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 현재 결론

팀원 작성 문서는 Rollup의 필요성, window/grouping/status/request_id 참조, 원본 복제 최소화 같은 방향성은 유효하다.

다만 현재 repo에 그대로 반영하지 않는다.

원문은 raw Apache event list를 받아 `sqli_attack`, `brute_force`, `path_scan` 같은 공격 단위 rollup을 만들고, `confidence_score`, `threat_level`, DB 저장, FastAPI endpoint까지 제안하는 구조다. 현재 repo의 Sliding Window 구조는 이보다 보수적이어야 한다.

현재 repo 기준 Rollup Input v1은 다음 방향으로 재정의한다.

```text
window_summary.json 여러 개
  -> request_id dedup
  -> candidate_index merge
  -> src_ip / uri / reason_hint_prefix 장기 aggregation
  -> data/rollups/<date>/<rollup_id>/rollup_input.json
```

즉, rollup v1은 탐지 엔진이 아니라 summary/dedup/aggregation artifact다.

## 2. 현재 repo의 실제 구조

0524 기준 Sliding Window artifact 구조는 다음과 같다.

```text
data/windowed/
  2026-05-24/
    sw_0200_0300/
      export.json
      llm_input.json
      analysis_candidates.json
      noise_summary.json
      window_summary.json

data/rollups/
  2026-05-24/
    rollup_0200_0600/
      rollup_input.json
      dedup_candidates.json
      rollup_summary.json

runs/
  rollup_20260524_0200_0600/
    manifest.json
    stage1_results.json
    stage2_report_input.json
    stage2_report.json
    stage2_report.md
    viewer_payload.json
```

구현 완료 상태:

```text
- src/sliding_window_scheduler.py --mode planner
- src/sliding_window_scheduler.py --mode export
- src/sliding_window_scheduler.py --mode prepare
- src/prepare_llm_input.py --flat-output-names
- src/sliding_window_summary.py
- window_summary.json v1 생성
```

`window_summary.json` v1은 rollup을 위한 summary-only index artifact다.

주요 필드:

```text
schema: sliding_window_summary_v1
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

`candidate_index`는 다음 최소 필드만 포함한다.

```text
request_id
src_ip
method
uri
status_code
score
verdict_hint
reason_hint_prefixes
```

`raw_log`, `raw_request`, `user_agent`, `referer`는 복제하지 않는다.

## 3. 팀원 문서에서 수용할 부분

### 3.1 Rollup 필요성

수용한다.

긴 시간 범위 로그를 한 번에 LLM pipeline에 넣으면 Web UI list, 운영자 검토, 중복 incident, token/cost 측면에서 부담이 커진다. 따라서 window별 prepare artifact를 만들고, 여러 window를 rollup하는 구조는 필요하다.

다만 원문처럼 raw event 전체를 바로 공격 단위로 묶는 방식이 아니라, 현재 repo에서는 `window_summary.json`을 먼저 만들고 그 summary들을 묶는다.

### 3.2 Window 개념

수용한다.

다만 원문의 `rollup_window.start_time/end_time/window_size_seconds`는 현재 repo에서는 다음처럼 KST/Asia-Seoul 기준으로 관리한다.

```json
{
  "rollup": {
    "start": "2026-05-24T02:00:00+09:00",
    "end_exclusive": "2026-05-24T06:00:00+09:00",
    "timezone": "Asia/Seoul",
    "duration_minutes": 240
  }
}
```

UTC 고정은 현재 repo의 export/prepare artifact와 맞지 않는다. 기존 artifact가 KST 기준 window를 사용하므로 rollup v1도 KST 기준을 유지한다.

### 3.3 Grouping key 개념

부분 수용한다.

원문의 `grouping_key`는 유용하지만, v1에서 공격 유형을 확정하는 grouping key는 두지 않는다.

수용 가능한 grouping/aggregation 후보:

```text
request_id
src_ip
method
uri
status_code
verdict_hint
reason_hint_prefixes
source_window_id
```

보류할 grouping 후보:

```text
attack_type=sqli_like
rollup_type=sqli_attack
threat_level
confidence_score
```

### 3.4 Status distribution

수용한다.

`status_distribution`은 새 판단이 아니라 관찰 분포이므로 rollup v1에 포함할 수 있다.

현재 명칭 후보:

```json
{
  "distributions": {
    "candidate_status_code": {
      "401": 3,
      "403": 2,
      "500": 1
    }
  }
}
```

단, status code 분포는 공격 성공/침해 성공 판단에 사용하지 않는다.

### 3.5 Related request IDs

수용한다.

원문의 `related_logs.request_ids` 개념은 현재 `window_summary.json`의 `candidate_index.request_id`와 맞는다.

rollup v1에서는 다음처럼 유지한다.

```json
{
  "dedup": {
    "primary_key": "request_id",
    "duplicate_request_ids": []
  },
  "candidate_index": [
    {
      "request_id": "...",
      "source_window_id": "sw_0200_0300"
    }
  ]
}
```

### 3.6 원본 데이터 보존 원칙

부분 수용한다.

원문은 원본 데이터 보존을 강조하지만, 현재 repo의 rollup input은 원본 로그를 복제하지 않는다.

원칙:

```text
- rollup_input.json에는 raw_log/raw_request/raw query string을 복제하지 않는다.
- 상세 분석이 필요하면 source window의 analysis_candidates.json 또는 export.json을 참조한다.
- rollup_input.json은 summary/index 역할에 제한한다.
```

## 4. 현재 repo에서 보류/제외할 부분

### 4.1 Raw event 기반 RollupEngine

보류한다.

원문은 `LogEvent` 리스트를 직접 받아 `create_sqli_rollup`, `create_brute_force_rollup`을 만드는 구조다. 현재 repo에서는 이 방식이 적절하지 않다.

이유:

- 이미 prepare 단계가 candidate/context/noise를 분리한다.
- `window_summary.json` v1이 rollup용 최소 index를 제공한다.
- rollup 단계가 raw event를 다시 직접 해석하면 prepare policy를 우회하거나 중복 구현할 수 있다.
- raw event 기반 confidence 계산은 Apache logs-only guardrail과 충돌할 가능성이 높다.

현재 repo 기준 rollup v1 입력은 raw event list가 아니라 `window_summary.json` list다.

### 4.2 확정적 rollup_type

보류한다.

원문에는 다음과 같은 값이 있다.

```text
sqli_attack
brute_force
path_scan
```

현재 repo에서는 이런 이름을 v1에 사용하지 않는다.

이유:

- `sqli_attack`은 공격 유형 확정처럼 읽힌다.
- `brute_force`는 로그인 성공/실패나 계정 상태를 Apache 로그만으로 확정하는 방향으로 흐를 수 있다.
- `path_scan`은 후보명으로는 가능하지만, v1에서는 single rollup type으로 확정하지 않는 편이 안전하다.

필요하면 나중에 약한 명칭을 검토한다.

```text
sqli_like_activity
xss_like_activity
path_probe_activity
auth_failure_activity
mixed_candidate_activity
```

단, v1에서는 rollup type 분류보다 `reason_hint_prefixes`와 distribution 기반 aggregation을 우선한다.

### 4.3 confidence_score / threat_level

제외한다.

원문은 `confidence_score`, `threat_level=likely`, `evidence_fields`를 제안한다. 현재 repo의 rollup v1에서는 넣지 않는다.

이유:

- confidence 계산은 사실상 새 보안 판단이다.
- Stage1/Stage2 이전에 threat level을 부여하면 LLM 입력이 과도하게 유도될 수 있다.
- Apache logs-only boundary에서는 공격 성공/침해 성공을 직접 단정하지 않아야 한다.

rollup v1의 guardrail:

```json
{
  "guardrails": {
    "summary_only": true,
    "no_new_security_verdict": true,
    "no_success_inference": true,
    "no_body_inference": true,
    "no_context_promotion": true,
    "no_policy_recalculation": true
  }
}
```

### 4.4 response_size_baseline_ratio / response_size_anomaly

제외한다.

원문은 `response_size_baseline_ratio`, `response_size_anomaly`, `avg_response_bytes > baseline * 3` 같은 기준을 제안한다.

현재 repo에서는 v1에 넣지 않는다.

이유:

- `response_body_bytes`는 Apache 로그 표면의 크기 정보일 뿐이다.
- 크기 변화만으로 정보 유출, 취약점 성공, 쿼리 결과 반환을 단정할 수 없다.
- baseline ratio 계산은 별도 baseline 설계와 검증이 필요하다.

나중에 필요하면 다음처럼 관찰 분포로만 추가할 수 있다.

```text
observed_response_body_bytes_distribution
```

단, anomaly/confidence 계산에는 사용하지 않는다.

### 4.5 DB schema / FastAPI endpoint

보류한다.

원문은 MariaDB 테이블과 FastAPI endpoint를 제안한다. 현재 단계에서는 범위 밖이다.

현재 repo는 파일 artifact 기반으로 진행한다.

```text
data/windowed/
data/rollups/
runs/
```

DB/API는 다음 조건이 충족된 뒤 별도 검토한다.

```text
- rollup_input.json 포맷 안정화
- dedup 기준 안정화
- Stage1/Stage2 rollup 단위 실행 구조 확정
- Web UI에서 rollup artifact를 읽어야 할 필요성 확인
```

### 4.6 IP masking 기본 적용

보류한다.

원문은 `src_ip_masked`를 기본으로 제안한다. 현재 repo에서는 분석/aggregation key로 `src_ip`를 그대로 사용한다.

v1에서는 원본 `src_ip`를 유지한다.

```json
{
  "src_ip": "192.168.56.1"
}
```

외부 공유용 report 또는 UI export 단계에서 masking을 검토한다.

## 5. 현재 repo 기준 Rollup Input v1 후보

현재 구조에 맞는 v1 후보는 다음과 같다.

```json
{
  "schema": "sliding_window_rollup_input_v1",
  "rollup": {
    "rollup_id": "rollup_0200_0600",
    "start": "2026-05-24T02:00:00+09:00",
    "end_exclusive": "2026-05-24T06:00:00+09:00",
    "timezone": "Asia/Seoul",
    "duration_minutes": 240
  },
  "source_windows": [
    {
      "window_id": "sw_0200_0300",
      "path": "../../windowed/2026-05-24/sw_0200_0300/window_summary.json",
      "start": "2026-05-24T02:00:00+09:00",
      "end_exclusive": "2026-05-24T03:00:00+09:00"
    }
  ],
  "counts": {
    "window_count": 1,
    "export_total": 14,
    "candidate_rows_total": 5,
    "candidate_request_ids_total": 5,
    "candidate_request_ids_distinct": 5,
    "dedup_removed": 0,
    "noise_group_count_total": 0
  },
  "dedup": {
    "primary_key": "request_id",
    "fallback_key": [
      "src_ip",
      "method",
      "uri",
      "status_code",
      "reason_hint_prefixes"
    ],
    "duplicate_request_ids": []
  },
  "distributions": {
    "candidate_status_code": {},
    "candidate_method": {},
    "candidate_src_ip": {},
    "candidate_uri": {},
    "candidate_reason_hint_prefix": {}
  },
  "candidate_index": [
    {
      "request_id": "...",
      "src_ip": "192.168.56.1",
      "method": "POST",
      "uri": "/login.php",
      "status_code": 401,
      "score": 6,
      "verdict_hint": "suspicious",
      "reason_hint_prefixes": [
        "xss",
        "error_status",
        "error_linked"
      ],
      "source_window_id": "sw_0200_0300"
    }
  ],
  "rollup_hints": {
    "has_candidates": true,
    "has_noise_groups": false,
    "has_repeated_src_ip": true,
    "has_repeated_uri": true,
    "has_repeated_reason_hint_prefix": true
  },
  "guardrails": {
    "summary_only": true,
    "no_new_security_verdict": true,
    "no_success_inference": true,
    "no_body_inference": true,
    "no_context_promotion": true,
    "no_policy_recalculation": true
  }
}
```

## 6. Rollup Input v1에서 반드시 지킬 제한

v1은 다음을 하지 않는다.

```text
- raw log 재분석
- raw_request/raw query string 복제
- response body 추론
- DB 결과 추론
- browser execution 추론
- attack success 판단
- exploit success 판단
- data exposure 판단
- account takeover 판단
- upload saved 판단
- severity/category/final verdict 계산
- confidence_score 계산
- threat_level 계산
- policy bucket 재계산
- context-only를 finding/incident로 승격
```

v1은 다음만 한다.

```text
- window_summary.json 목록 수집
- request_id 기반 dedup
- candidate_index merge
- src_ip/method/uri/status/reason_hint_prefix 분포 합산
- rollup 단위 Stage1/Stage2 입력 후보 생성 전 단계의 summary artifact 생성
```

## 7. Dedup 기준 후보

1차 기준:

```text
request_id
```

이유:

- Sliding Window overlap이 생기면 같은 request_id가 여러 window에 나타날 수 있다.
- 같은 request_id는 같은 Apache request transaction으로 보는 것이 가장 안전하다.
- 현재 `window_summary.json`의 `candidate_index`에 request_id가 포함된다.

fallback 기준:

```text
src_ip
method
uri
status_code
reason_hint_prefixes
```

fallback은 request_id가 없거나 비어 있을 때만 사용한다. fallback dedup은 충돌 가능성이 있으므로 제거보다는 `possible_duplicate` 표시에 가깝게 다룬다.

## 8. Low-and-slow 후보화 기준

단일 window summary에서는 low-and-slow 여부를 판단하지 않는다.

후보화는 rollup 단계에서만 가능하다.

초기 후보 신호:

```text
- 여러 window에 걸친 동일 src_ip 반복
- 여러 window에 걸친 유사 uri family 반복
- 여러 window에 걸친 동일 reason_hint_prefix 반복
- window별 candidate count는 낮지만 rollup 전체에서 반복성이 관찰됨
```

다만 v1에서는 `low_and_slow_candidate=true` 같은 필드를 바로 넣지 않는다. 먼저 장기 aggregation 값을 만들고, 별도 review 후 후보화 필드를 검토한다.

## 9. 문서 원문 항목별 처리표

| 원문 항목 | 현재 repo 처리 |
|---|---|
| Rollup 필요성 | 수용 |
| rollup_window | 수용. KST/Asia-Seoul 기준으로 조정 |
| grouping_key | 부분 수용. attack_type 확정은 제외 |
| metrics.event_count | counts로 수용 |
| status_distribution | distributions로 수용 |
| patterns_observed | reason_hint_prefix distribution 중심으로 축소 |
| confidence | v1 제외 |
| threat_level | v1 제외 |
| response_size_baseline_ratio | v1 제외 |
| related_logs.request_ids | candidate_index/dedup로 수용 |
| raw event RollupEngine | 보류 |
| MariaDB schema | 보류 |
| FastAPI endpoint | 보류 |
| IP masking | v1 기본값에서는 보류. 외부 공유/UI export 단계에서 재검토 |

## 10. 다음 작업

다음 단계는 코드 구현 전, `sliding_window_rollup_input_v1` 포맷을 조금 더 구체화하는 것이다.

우선 문서화할 항목:

```text
- rollup_id naming: rollup_HHMM_HHMM 또는 rollup_YYYYMMDD_HHMM_HHMM
- source_windows path 기준: rollup dir 기준 relative path 또는 repo root relative path
- request_id dedup 결과 표현 방식
- duplicate_request_ids 구조
- fallback duplicate 후보 표현 방식
- candidate_index merge 순서
- distributions merge 방식
- rollup_summary.json과 rollup_input.json 역할 분리
```

그 다음 구현 후보:

```text
src/sliding_window_rollup.py
tests/test_sliding_window_rollup.py
```

초기 구현 범위:

```text
- data/windowed/<date>/sw_*/window_summary.json 탐색
- rollup 시간 범위에 포함되는 summary만 선택
- request_id dedup
- candidate_index merge
- distributions 합산
- data/rollups/<date>/<rollup_id>/rollup_input.json 생성
- stage1/stage2/viewer_payload 실행 없음
- runs/ 생성 없음
```
