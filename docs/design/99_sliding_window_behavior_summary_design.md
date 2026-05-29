# Sliding Window Behavior Summary Design

- 문서 상태: 설계 초안 / 구현 전 판단 문서
- 기준 시점: 2026-05-29
- 목적: candidate 단위 dedup 이후에도 남는 다수의 관련 후보를 사람이 이해하기 쉬운 behavior-like summary로 묶는 후속 레이어의 위치, 범위, 금지사항을 정의한다.

관련 문서:

- [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
- [99_analysis_job_modes_and_sliding_window_integration.md](./99_analysis_job_modes_and_sliding_window_integration.md)
- [99_sliding_window_adoption_review.md](./99_sliding_window_adoption_review.md)
- [99_sliding_window_rollup_input_format.md](./99_sliding_window_rollup_input_format.md)
- [99_sliding_window_rollup_pipeline_integration.md](./99_sliding_window_rollup_pipeline_integration.md)
- [99_sliding_window_operator_queue_design.md](./99_sliding_window_operator_queue_design.md)
- [99_sliding_window_operator_queue_item_detail.md](./99_sliding_window_operator_queue_item_detail.md)
- [99_sliding_window_single_rollup_observation_brief.md](./99_sliding_window_single_rollup_observation_brief.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

---

## 1. 결론

Behavior summary 레이어는 필요하다.

다만 지금은 `src/prepare_llm_input.py` 내부에 넣지 않는다.

초기 위치는 다음 중 하나로 둔다.

```text
권장 v1 위치:
  rollup_input.json
    -> behavior_summary.json
    -> operator_queue / observation brief

더 보수적인 v0 위치:
  selected rollup observation brief 내부에서만 deterministic grouping 표시
```

이 레이어는 candidate/scoring/filtering을 바꾸지 않는다.

```text
- candidate 생성 없음
- finding 생성 없음
- incident 생성 없음
- score 생성/변경 없음
- verdict_hint 생성/변경 없음
- severity/category/confidence 생성 없음
- context-only 항목 승격 없음
- 공격 성공/침해/노출 단정 없음
```

Behavior summary는 `hint-only`, `read-only`, `non-verdict` 요약이다.

---

## 2. 배경

현재 pipeline은 단순한 로그 나열형 구조가 아니다.

이미 다음 방향을 갖고 있다.

```text
row
  -> candidate
  -> candidate dedup
  -> supporting_event
  -> representative candidate
  -> noise aggregate
  -> window_summary
  -> rollup_input
  -> operator_queue
```

이 구조는 같은 요청, 반복 요청, supporting context, 대표 candidate 보존에는 강하다.

그러나 아직 다음 계층은 약하다.

```text
candidate groups
  -> behavior-like summary
```

예를 들어 다음 URI들은 서로 다르다.

```text
/wp-login.php
/xmlrpc.php
/wp-admin/install.php
/wp-content/debug.log
```

candidate 단위에서는 각각 별도로 보일 수 있다.

하지만 운영자가 보고 싶은 상위 관찰은 다음에 가깝다.

```text
wordpress_probe_like behavior
```

따라서 긴 구간 triage, operator queue, observation brief에서 사람의 인지 부담을 낮추려면 candidate를 한 번 더 behavior-like summary로 묶는 레이어가 필요하다.

---

## 3. 용어

### 3.1 behavior summary

`behavior_summary`는 여러 candidate/context 관찰을 사람이 읽기 쉬운 단위로 묶은 요약이다.

```text
behavior_summary != security verdict
behavior_summary != finding
behavior_summary != incident
behavior_summary != exploit success
```

### 3.2 observed_family

`attack_family`라는 이름은 사용하지 않는다.

대신 다음 표현을 사용한다.

```text
observed_family
behavior_family
*_like
```

예:

```text
wordpress_probe_like
phpmyadmin_probe_like
laravel_env_probe_like
sqli_payload_like
xss_payload_like
auth_repetition_like
scanner_probe_like
sensitive_path_probe_like
```

### 3.3 endpoint_family

`endpoint_family`는 URI를 사람이 이해 가능한 endpoint group으로 정규화한 값이다.

예:

```text
/api/user/123
/api/user/456
  -> /api/user/{id}

/wp-login.php
/xmlrpc.php
/wp-admin/install.php
  -> wordpress_common_paths
```

endpoint family는 behavior를 단정하지 않는다.

---

## 4. 왜 prepare 내부가 아닌가

`prepare_llm_input.py`는 이미 다음 책임을 갖는다.

```text
- source table 선택
- candidate selection
- candidate scoring
- context summary
- noise aggregation
- dedup
- LLM input shaping
```

Behavior summary를 prepare 내부에 바로 넣으면 다음 위험이 생긴다.

```text
- prepare/scoring/filtering 의미가 변할 수 있다.
- full_report direct pipeline에도 영향을 준다.
- regression 범위가 커진다.
- behavior label이 verdict처럼 오해될 수 있다.
- candidate visibility나 ranking에 간접 영향을 줄 수 있다.
```

따라서 v1에서는 prepare 내부 변경을 피한다.

Behavior summary는 rollup 이후의 별도 단계로 둔다.

---

## 5. 파이프라인 내 위치

### 5.1 권장 v1

```text
window export
  -> window prepare
  -> window_summary.json
  -> rollup_input.json
  -> behavior_summary.json
  -> operator_queue
  -> queue item detail / observation brief
```

이 위치의 장점:

```text
- 긴 구간 / multi-window 관찰에 적합하다.
- prepare/scoring/filtering 변경이 없다.
- full_report direct pipeline과 분리된다.
- operator_queue와 observation brief에서 사람이 읽기 쉬운 hint로 사용할 수 있다.
```

### 5.2 보수적 v0

```text
operator_queue item selected
  -> observation brief CLI preview
  -> rollup_input/rollup_summary에서 behavior-like grouping을 즉석 표시
```

이 위치의 장점:

```text
- 새 artifact가 없다.
- Web UI/DB integration 전에 출력 형태를 검증할 수 있다.
- 보안 판단 경계가 가장 작다.
```

### 5.3 비추천

```text
prepare_llm_input.py 내부에서 candidate 생성 단계에 behavior clustering 삽입
```

비추천 이유:

```text
- candidate semantics가 흔들릴 수 있다.
- context-only 항목 승격 위험이 생긴다.
- 기존 full_report 경로와 DB-backed MVP 안정화에 영향을 줄 수 있다.
```

---

## 6. 입력

v1 입력 후보:

```text
rollup_input.json
rollup_summary.json
operator_queue item  # 선택 사항
```

주요 사용 필드:

```text
rollup:
  rollup_id
  start
  end_exclusive
  timezone

source_windows:
  window_id
  status
  start
  end_exclusive

candidate_index:
  request_id
  src_ip
  method
  uri
  status_code
  score
  verdict_hint
  reason_hint_prefixes

distributions:
  src_ip
  uri
  reason_hint_prefix
  status_code
```

사용하지 않는 것:

```text
- raw POST body
- response body
- DB query result
- browser execution
- raw_log full text
- provider secrets
```

---

## 7. Behavior key 후보

v1 key는 deterministic allowlist 기반으로 제한한다.

```python
behavior_key = (
    src_ip,
    observed_family,
    endpoint_family,
    time_bucket_or_rollup_id,
)
```

각 항목 의미:

```text
src_ip:
  Apache log에서 관찰된 src_ip. attacker identity 확정 근거가 아니다.

observed_family:
  allowlist 기반 *_like family.

endpoint_family:
  URI를 endpoint group으로 정규화한 값.

time_bucket_or_rollup_id:
  v1에서는 rollup_id 사용을 우선한다.
  장기/일일 summary에서는 time bucket을 별도로 검토한다.
```

주의:

```text
credential_stuffing 같은 단정적 family명은 v1에서 사용하지 않는다.
대신 auth_repetition_like, login_probe_like처럼 관찰 기반 표현을 사용한다.
```

---

## 8. observed_family v1 후보

v1은 명확한 family만 다룬다.

```text
wordpress_probe_like
phpmyadmin_probe_like
laravel_env_probe_like
admin_probe_like
sensitive_path_probe_like
sqli_payload_like
xss_payload_like
auth_repetition_like
scanner_probe_like
```

### 8.1 WordPress probe-like

후보 URI:

```text
/wp-login.php
/xmlrpc.php
/wp-admin
/wp-admin/install.php
/wp-content/
/wp-includes/
```

출력:

```text
observed_family=wordpress_probe_like
```

금지:

```text
wordpress_exploit
wordpress_compromise
wordpress_vulnerability_confirmed
```

### 8.2 phpMyAdmin probe-like

후보 URI:

```text
/phpmyadmin
/pma
/phpMyAdmin
```

출력:

```text
observed_family=phpmyadmin_probe_like
```

### 8.3 Laravel/env probe-like

후보 URI:

```text
/.env
/.env.bak
/vendor/.env
/storage/logs/laravel.log
```

출력:

```text
observed_family=laravel_env_probe_like
```

주의:

```text
파일 노출 또는 정보 유출로 단정하지 않는다.
```

### 8.4 Payload-like

reason_hint_prefix 기반:

```text
sqli
sqli_hint
xss
xss_hint
```

출력:

```text
sqli_payload_like
xss_payload_like
```

주의:

```text
SQL injection success나 browser execution으로 단정하지 않는다.
```

### 8.5 Auth repetition-like

후보 신호:

```text
login endpoint 반복
401/403 반복
auth-related reason_hint_prefix 반복
```

출력:

```text
auth_repetition_like
```

금지:

```text
credential_stuffing_confirmed
account_takeover
login_success
```

---

## 9. 출력 schema 후보

```json
{
  "schema": "sliding_window_behavior_summary_v1",
  "rollup_id": "rollup_20260524_0200_0400",
  "generated_at": "2026-05-29T00:00:00+09:00",
  "source": {
    "rollup_input_path": "data/rollups/2026-05-24/rollup_20260524_0200_0400/rollup_input.json",
    "rollup_summary_path": "data/rollups/2026-05-24/rollup_20260524_0200_0400/rollup_summary.json"
  },
  "summary_counts": {
    "behavior_group_count": 1,
    "candidate_index_count": 5,
    "source_window_count": 3
  },
  "behavior_groups": [
    {
      "behavior_key": "192.168.56.1|wordpress_probe_like|wordpress_common_paths|rollup_20260524_0200_0400",
      "observed_family": "wordpress_probe_like",
      "src_ip": "192.168.56.1",
      "endpoint_family": "wordpress_common_paths",
      "request_count": 441,
      "candidate_count": 12,
      "source_window_count": 7,
      "sample_targets": [
        "/wp-login.php",
        "/xmlrpc.php",
        "/wp-admin"
      ],
      "reason_hint_prefixes": [
        "error_status",
        "sensitive_path_probe"
      ],
      "status_codes": {
        "404": 320,
        "403": 121
      },
      "representative_request_ids": [
        "..."
      ],
      "guardrails": {
        "is_security_verdict": false,
        "does_not_conclude_success": true,
        "does_not_promote_context_only": true
      }
    }
  ]
}
```

---

## 10. Operator Queue와의 관계

Behavior summary는 operator queue의 routing을 보조할 수 있다.

다만 v1에서는 operator queue status를 바꾸지 않는다.

```text
- review_status 변경 없음
- llm_eligible 변경 없음
- llm_required 변경 없음
- recommended_action 변경 없음
```

초기 사용 방식:

```text
queue item detail:
  behavior_summary_path가 있으면 표시 후보

observation brief:
  observed behavior groups 섹션에 표시
```

후속 검토:

```text
behavior_group_count가 매우 큰 경우 review hint를 줄 수 있는지 검토
```

단, 이것도 routing hint일 뿐 보안 verdict가 아니다.

---

## 11. Observation Brief와의 관계

Observation Brief에서는 behavior summary를 사람이 읽는 문장으로 표시할 수 있다.

예:

```text
Observed behavior groups
- wordpress_probe_like
  - observed src_ip: 1.2.3.4
  - sample targets: /wp-login.php, /xmlrpc.php, /wp-admin
  - request_count: 441
  - source_window_count: 7
  - note: Apache logs-only observation; not exploit success evidence.
```

Observation Brief는 다음을 하지 않는다.

```text
- threat level 산정
- compromise 판단
- exploit success 판단
- vulnerability confirmed 판단
```

---

## 12. Stage1/Stage2와의 관계

Behavior summary는 Stage1/Stage2 입력으로 직접 사용하지 않는다.

후속 `selected_rollup_full_report`에서 projection을 설계할 때 context로 포함할 수 있다.

조건:

```text
- context-only
- hint-only
- non-verdict
- source candidate/request_id trace 보존
```

금지:

```text
behavior_summary group을 Stage1 candidate로 승격하지 않는다.
behavior_summary group을 Stage2 incident로 승격하지 않는다.
```

---

## 13. 구현 후보

### 13.1 보수적 v0

```text
src/sliding_window_rollup_observation_brief.py
```

Observation Brief CLI 안에서 behavior-like grouping을 계산해 stdout에 표시한다.

장점:

```text
- 새 artifact 없음
- risk 작음
- 사람이 읽는 형태를 먼저 검증 가능
```

### 13.2 v1 artifact builder

```text
src/sliding_window_behavior_summary.py
```

입력:

```text
--work-dir /opt/web_log_analysis
--rollup-id rollup_20260524_0200_0400
--rollup-dir data/rollups/2026-05-24/rollup_20260524_0200_0400
```

출력:

```text
data/rollups/<date>/<rollup_id>/behavior_summary.json
```

테스트 후보:

```text
tests/test_sliding_window_behavior_summary.py
```

### 13.3 비추천 v1

```text
src/prepare_llm_input.py 내부에 behavior_cluster_builder 추가
```

보류한다.

---

## 14. 테스트 기준

필수 테스트:

```text
- WordPress common paths가 wordpress_probe_like로 묶이는지
- phpMyAdmin paths가 phpmyadmin_probe_like로 묶이는지
- .env 계열이 laravel_env_probe_like로 묶이는지
- sqli/xss reason prefix가 payload_like family로 묶이는지
- auth repetition이 login success/account takeover로 표현되지 않는지
- behavior summary가 candidate/finding/incident/verdict/severity 필드를 만들지 않는지
- context-only 항목을 candidate로 승격하지 않는지
- representative_request_ids가 trace 용도로 보존되는지
```

금지어 테스트 후보:

```text
confirmed
compromised
success
exploit_success
data_leak
account_takeover
credential_stuffing_confirmed
```

단, `does_not_conclude_success` 같은 guardrail 문구는 허용한다.

---

## 15. 현재 결정 사항

```text
[확정]
- Behavior summary는 필요하다.
- prepare 내부에 지금 넣지 않는다.
- rollup 이후 hint-only summary로 설계한다.
- observed_family / *_like 표현을 사용한다.
- behavior summary는 보안 verdict가 아니다.
- operator_queue / observation brief의 가독성 개선 용도로 우선 사용한다.

[보류]
- prepare_llm_input.py 내부 편입
- Stage1/Stage2 direct input 편입
- behavior group을 candidate/finding/incident로 승격
- LLM 기반 behavior clustering
- ML/embedding clustering
```

---

## 16. 다음 작업 후보

```text
1. selected rollup observation brief CLI preview 구현
2. Observation Brief 안에서 behavior-like grouping v0 표시 여부 판단
3. behavior_summary.json artifact builder 필요성 재검토
4. 필요 시 src/sliding_window_behavior_summary.py 설계/구현
```
