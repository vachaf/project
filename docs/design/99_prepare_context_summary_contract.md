# 99_prepare_context_summary_contract

- 문서 상태: contract / 분리 전 검토
- 기준 시점: 2026-05-04
- 목적: `prepare_llm_input.py`의 context summary builder를 나중에 분리할 때 유지해야 할 입력, 출력, 불변조건을 정의한다.

이 문서는 `prepare/context_summaries.py` 구현 문서가 아니다. 현재 단계에서는 코드 분리 전에 summary별 계약을 고정해 회귀 위험을 줄이는 것이 목적이다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md)
- [99_stage_dryrun_regression_설계.md](./99_stage_dryrun_regression_설계.md)

## 1. 현재 결론

다음 코드 분리 후보를 바로 `context_summaries.py`로 확정하지 않는다.

먼저 아래 summary 계열의 contract를 유지한다.

```text
probing_sequence_summaries
ip_behavior_aggregates
auth_behavior_summaries
method_behavior_summaries
protocol_anomaly_summaries
static_baseline_summaries
crawler_baseline_summaries
sensitive_path_probe_summaries
mixed_baseline_scanner_summaries
```

핵심 원칙:

```text
- summary는 context-only 문맥이다.
- summary가 candidate 수를 늘리는 방향으로 작동하면 안 된다.
- summary count, policy, interpretation_hint, sample request 구조가 Stage2 입력에서 유지되어야 한다.
- Apache logs-only 한계와 성공 단정 금지 원칙을 깨면 안 된다.
```

## 2. 공통 입력 계약

summary builder는 일반적으로 아래 입력 범주를 소비한다.

```text
- normalized row 목록
- candidate 목록
- filtered_out rows
- source table 정보
- src_ip
- method
- uri / request path
- query_string / raw_request_target
- status_code
- response_body_bytes
- resp_content_type
- duration_us / ttfb_us
- user_agent
- referer
- log_time
- request_id / error_link_id
- reason_hints
- verdict_hint
```

입력 해석 원칙:

- raw POST body는 없다고 본다.
- response body 원문은 없다고 본다.
- DB 결과, 브라우저 실행, 파일 내용은 보지 않는다.
- `status_code`, `bytes`, `content_type`은 보조 표면 신호다.
- `lab-*` / experiment-like UA는 trace aid이며 공격 근거가 아니다.

## 3. 공통 출력 계약

summary 객체는 Stage2 report input에서 사람이 읽을 수 있는 context-only 문맥으로 사용된다.

공통적으로 지켜야 할 출력 성격:

```text
- category 또는 summary type
- policy: context_only 계열
- request_count 또는 count
- sample requests 또는 representative requests
- status distribution
- path/method/user_agent family 등 aggregate 정보
- interpretation_hint
- reason_hints 또는 summary reason
```

출력 금지:

```text
- confirmed compromise
- successful exploit
- data exfiltration confirmed
- file exposure confirmed
- browser execution confirmed
- credential stuffing success confirmed
- account takeover confirmed
```

## 4. summary별 계약

### 4.1 `probing_sequence_summaries`

목적:

- 동일 IP / 짧은 time window 안에서 여러 민감 경로를 순차 탐색하는 흐름을 context-only로 보존한다.

대표 입력:

```text
- src_ip
- request path / uri
- status_code
- response_body_bytes
- resp_content_type
- log_time
- reason_hints
```

대표 출력:

```text
- category: low_signal_dir_probe_burst 계열
- policy: context_only
- request_count
- distinct_path_count
- status_counts
- sample_paths
- interpretation_hint
```

불변조건:

- 200 OK 다수를 민감 파일 노출 성공으로 단정하지 않는다.
- SPA fallback HTML 가능성을 배제하지 않는다.
- candidate를 늘리지 않고 burst 흐름만 전달하는 구조를 유지한다.

### 4.2 `ip_behavior_aggregates`

목적:

- 동일 IP의 여러 신호를 묶어 전반적 행동 문맥을 제공한다.

대표 입력:

```text
- src_ip
- time window
- request_count
- candidate count
- filtered/context count
- sensitive path count
- method/status distribution
```

대표 출력:

```text
- src_ip
- window_start / window_end
- request_count
- candidate_count
- supporting/context count
- sensitive_path_samples
- interpretation_hint
```

불변조건:

- IP 자체를 공격자로 단정하지 않는다.
- known asset 또는 내부 테스트 가능성을 지워서는 안 된다.
- 여러 저신호가 있다고 해서 자동 high severity로 올리지 않는다.

### 4.3 `auth_behavior_summaries`

목적:

- 반복 auth/login endpoint interaction을 context-only로 요약한다.

대표 입력:

```text
- auth/login URI family
- method
- status_code
- response_body_bytes
- src_ip
- user_agent
- request count
- time window
```

대표 출력:

```text
- category: auth behavior context
- policy: context_only
- request_count
- status_counts
- representative_requests
- interpretation_hint
```

불변조건:

- 로그인 성공, credential stuffing 성공, 계정 탈취, lockout 발동을 단정하지 않는다.
- POST body가 없으므로 계정 존재 여부나 password content를 말하지 않는다.
- repeated 401을 high severity incident로 과승격하지 않는다.

### 4.4 `method_behavior_summaries`

목적:

- OPTIONS / TRACE / PUT / DELETE / PATCH 등 method behavior를 context-only로 요약한다.

대표 입력:

```text
- method
- uri
- status_code
- response_body_bytes
- resp_content_type
- src_ip
- time window
```

대표 출력:

```text
- method_counts
- risky_method_counts
- baseline_method_counts
- representative_requests
- interpretation_hint
```

불변조건:

- PUT 업로드 성공, DELETE 삭제 성공, TRACE/XST 성공, OPTIONS/CORS 취약점 성공을 단정하지 않는다.
- method가 unusual하다는 사실과 exploit success를 분리한다.

### 4.5 `protocol_anomaly_summaries`

목적:

- malformed request, unusual protocol surface, long path 같은 protocol anomaly 문맥을 보존한다.

대표 입력:

```text
- raw_request
- raw_request_target
- method
- uri
- status_code
- response_body_bytes
- error/source table context
```

대표 출력:

```text
- anomaly count
- anomaly type distribution
- representative requests
- interpretation_hint
```

불변조건:

- protocol bypass, server compromise, malformed request exploit success를 단정하지 않는다.
- error log surface와 access/security surface를 혼동하지 않는다.

### 4.6 `static_baseline_summaries`

목적:

- 정적 리소스, health/status, normal browse 계열 baseline을 context-only로 보존한다.

대표 입력:

```text
- static extension / static prefix
- health-like path
- method
- status_code
- response_body_bytes
- resp_content_type
- user_agent
```

대표 출력:

```text
- static_path_count
- health_like_count
- status_counts
- sample_requests
- interpretation_hint
```

불변조건:

- static file 존재 여부나 내용 정상 여부를 단정하지 않는다.
- baseline을 공격 incident로 과승격하지 않는다.

### 4.7 `crawler_baseline_summaries`

목적:

- crawler-like 또는 browse-like baseline traffic을 context-only로 보존한다.

대표 입력:

```text
- user_agent family
- product/category/list/browse path segment
- method/status distribution
- request count
- time window
```

대표 출력:

```text
- crawler_like_user_agent_families
- browse_path_samples
- request_count
- status_counts
- interpretation_hint
```

불변조건:

- 실제 crawler 여부를 단정하지 않는다.
- product/category page 존재 여부를 단정하지 않는다.
- UA는 보조 문맥이며 공격 근거가 아니다.

### 4.8 `sensitive_path_probe_summaries`

목적:

- `.env`, `.git`, `phpinfo`, `server-status`, backup/admin/config 계열 경로 탐색을 context-only로 요약한다.

대표 입력:

```text
- sensitive path markers
- status_code
- response_body_bytes
- resp_content_type
- source table
- src_ip / time window
```

대표 출력:

```text
- sensitive_path_count
- distinct_path_count
- status_counts
- sample_paths
- interpretation_hint
```

불변조건:

- WordPress 존재, admin 접근 성공, `.env`/backup/config 노출 성공을 단정하지 않는다.
- 200/text/html + 큰 bytes가 있더라도 response body 원문 없이는 노출 성공으로 쓰지 않는다.
- sensitive path probe는 기본적으로 context-only다.

### 4.9 `mixed_baseline_scanner_summaries`

목적:

- benign baseline traffic과 scanner-like traffic이 섞인 경우를 단일 공격 성공으로 과장하지 않고 요약한다.

대표 입력:

```text
- benign/static/browse request markers
- scanner/sensitive path markers
- method/status distribution
- src_ip
- time window
```

대표 출력:

```text
- baseline_count
- scanner_like_count
- mixed_policy
- representative_requests
- interpretation_hint
```

불변조건:

- mixed traffic을 단일 incident success로 단정하지 않는다.
- benign baseline과 scanner-like context를 분리해서 설명한다.
- Stage2에서 severity를 올리는 단독 근거가 되어서는 안 된다.

## 5. 분리 전 필수 불변조건

`prepare/context_summaries.py`를 만들기 전 아래 조건을 지켜야 한다.

```text
- summary field 이름 변경 금지
- summary count 의미 변경 금지
- policy / interpretation_hint 의미 변경 금지
- representative sample limit 변경 금지
- candidate 수 변화 금지
- filtered_out 수 변화 금지
- supporting_events 수 변화 금지
- Stage2 report input key 구조 변경 금지
```

## 6. 검증 계획

context summary 관련 변경 전후에는 아래를 확인한다.

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

중점 fixture:

```text
f_r1_auth_behavior_context
g_r1_method_behavior_context
g_r2_protocol_anomaly_context
h_r1_static_baseline_context
h_r2_crawler_baseline_context
h_r3_sensitive_path_probe_context
h_r4_mixed_baseline_scanner_context
ip_behavior_multi_signal_context
```

성공 기준:

```text
prepare regression: 18 fixtures, warn=0 fail=0
stage dry-run regression: 12 fixtures, warn=0 fail=0
각 summary count와 policy가 기존 expected와 동일
Stage2에서 context-only 정책 유지
```

## 7. 다음 후보 판단

현 시점에서 다음 코드 분리를 바로 진행하지 않는다.

권장 순서:

```text
1. 이 contract를 기준으로 summary builder별 실제 함수 위치를 확인한다.
2. 가장 작은 summary 하나만 분리 가능한지 검토한다.
3. 분리 후보는 auth/method/protocol처럼 독립성이 높은 summary부터 비교한다.
4. mixed_baseline_scanner, sensitive_path_probe, supporting_events 연동 summary는 늦춘다.
```

가능한 다음 문서:

```text
docs/design/99_prepare_context_summary_split_candidate.md
```

이 문서는 실제 함수 단위 inventory를 통해 어떤 summary builder를 먼저 옮길지 판단하는 용도로 둔다.

## 8. 현재 결론

- `context_summaries.py`는 장기적으로 효과가 크다.
- 하지만 Stage2 input, context-only policy, expected fixture와 강하게 연결되어 있으므로 바로 분리하지 않는다.
- 이번 단계에서는 summary contract만 고정한다.
- 다음 단계는 실제 함수 단위 inventory를 보고 가장 작은 summary builder 후보를 고르는 것이다.
