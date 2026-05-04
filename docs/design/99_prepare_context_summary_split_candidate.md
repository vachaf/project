# 99_prepare_context_summary_split_candidate

- 문서 상태: split candidate review
- 기준 시점: 2026-05-04
- 목적: `prepare/context_summaries.py`를 바로 만들기 전에, `prepare_llm_input.py` 안의 context summary 계열 중 어떤 builder가 가장 먼저 분리 가능한지 판단한다.

관련 문서:

- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_llm_input_inventory.md](./99_prepare_llm_input_inventory.md)

## 1. 결론

다음 코드 분리 후보는 아직 확정하지 않는다.

다만 후보 우선순위는 아래와 같이 둔다.

```text
1. method_behavior_summaries 계열
2. protocol_anomaly_summaries 계열
3. auth_behavior_summaries 계열
4. static_baseline_summaries 계열
5. crawler_baseline_summaries 계열
```

당장 분리하지 않는 후보:

```text
- ip_behavior_aggregates
- probing_sequence_summaries
- sensitive_path_probe_summaries
- mixed_baseline_scanner_summaries
```

현재 판단:

```text
가장 먼저 실제 코드 분리를 검토할 후보는 method_behavior_summaries 계열이다.
```

단, 다음 단계는 바로 코드 이동이 아니라 `method_behavior_summaries` 관련 실제 함수와 호출 위치를 좁히는 검토다.

## 2. 판단 기준

후보 선정 기준은 아래 순서로 본다.

```text
1. Stage2 report input 구조와 결합도가 낮은가
2. candidate / filtered_out / supporting_events 수를 바꾸지 않는가
3. summary count와 policy를 유지하기 쉬운가
4. Apache logs-only 해석 한계를 깨지 않는가
5. 회귀 fixture가 명확히 존재하는가
6. 다른 summary와 공유하는 helper가 적은가
```

금지:

```text
- summary 분리와 behavior 변경을 같은 커밋에 섞지 않는다.
- summary field 이름을 바꾸지 않는다.
- sample limit, window, policy, interpretation_hint 의미를 바꾸지 않는다.
- candidate 수를 늘리거나 줄이지 않는다.
- Stage2가 context-only summary를 incident처럼 읽게 만들지 않는다.
```

## 3. 후보별 검토

### 3.1 `method_behavior_summaries` — 1순위 후보

성격:

- HTTP method 분포와 risky method surface를 요약한다.
- OPTIONS / TRACE / PUT / DELETE / PATCH 같은 method family를 context-only로 전달한다.

장점:

- 입력이 비교적 단순하다.
  - method
  - uri/path
  - status_code
  - response_body_bytes
  - resp_content_type
  - src_ip
  - time window
- G R1 method behavior fixture로 회귀 확인이 가능하다.
- file disclosure, SQLi, XSS, sensitive path와 직접 결합도가 낮다.
- “method가 unusual하다”와 “exploit이 성공했다”를 분리하는 contract가 명확하다.

위험:

- method summary가 Stage2에서 severity 상향 근거처럼 읽히면 안 된다.
- PUT/DELETE/TRACE/OPTIONS 성공 단정 금지 문구가 유지되어야 한다.
- method baseline family와 risky family 상수는 아직 `prepare_llm_input.py` 안에 남아 있으므로, 상수 이동은 같이 하지 않는 편이 안전하다.

현재 판단:

```text
가장 유력한 첫 코드 분리 후보.
단, 1차 분리는 method summary builder 함수와 그 보조 helper 중 method 전용인 것만 대상으로 제한한다.
```

코드 분리 전 확인할 것:

```text
- method summary builder 함수명
- 호출 위치
- 입력으로 받는 row/candidate/filtered 구조
- 출력 key 목록
- METHOD_RISKY_FAMILIES / METHOD_BASELINE_FAMILIES / METHOD_DESTRUCTIVE_FAMILIES / STANDARD_HTTP_METHODS 사용 여부
- expected fixture에서 고정하는 summary count와 policy
```

### 3.2 `protocol_anomaly_summaries` — 2순위 후보

성격:

- malformed request, unusual method/protocol surface, long path 등을 요약한다.

장점:

- G R2 protocol anomaly fixture로 회귀 확인이 가능하다.
- method behavior와 구조가 가까울 가능성이 있다.
- request surface 중심이라 file disclosure / SQLi / XSS보다 결합도가 낮다.

위험:

- error table / access table / security table surface를 섞어 해석할 수 있다.
- malformed request를 protocol bypass나 compromise로 단정하면 안 된다.
- long path threshold 같은 상수는 output에 영향을 줄 수 있으므로 함께 변경하면 안 된다.

현재 판단:

```text
method summary 분리 후 다음 후보로 검토한다.
method와 공통 helper가 많으면 둘을 동시에 옮기지 말고 helper contract를 먼저 정의한다.
```

### 3.3 `auth_behavior_summaries` — 3순위 후보

성격:

- 반복 login/auth endpoint interaction을 context-only로 요약한다.

장점:

- F set에서 실제 LLM 샘플 검증과 dry-run regression으로 품질 기준이 비교적 명확하다.
- repeated 401, response delta, auth endpoint interaction을 보수적으로 설명하는 목적이 뚜렷하다.

위험:

- auth endpoint family 판단과 연결되어 있다.
- POST body가 없다는 한계를 강하게 유지해야 한다.
- 계정 존재 여부, lockout, credential stuffing success 단정 금지 원칙이 매우 중요하다.
- representative candidate limit과 supporting_events가 연결될 수 있다.

현재 판단:

```text
독립 후보로는 가능하지만 method/protocol보다 위험하다.
method/protocol 이후에 검토한다.
```

### 3.4 `static_baseline_summaries` — 4순위 후보

성격:

- static resource, health/status, normal browse baseline을 요약한다.

장점:

- 공격 후보보다 baseline context에 가까워 candidate scoring과 직접 결합도가 낮을 수 있다.
- H R1 fixture로 회귀 확인이 가능하다.

위험:

- static path/fallback/browser UA/crawler-like 해석과 일부 겹칠 수 있다.
- health-like path의 “정상 여부”를 단정하면 안 된다.
- static file 존재/내용 정상 여부를 말하지 않아야 한다.

현재 판단:

```text
method/protocol/auth 이후 후보.
baseline 계열을 분리할 때 crawler summary와 경계가 명확해야 한다.
```

### 3.5 `crawler_baseline_summaries` — 5순위 후보

성격:

- crawler-like UA 또는 product/category/list/browse path를 context-only로 요약한다.

장점:

- H R2 fixture로 회귀 확인이 가능하다.
- crawler-like baseline context는 summary 목적이 분명하다.

위험:

- UA 해석과 연결된다.
- lab-* / experiment-like UA guard, browser-like UA, crawler-like UA의 경계를 조심해야 한다.
- 실제 crawler 여부나 site structure를 단정하면 안 된다.

현재 판단:

```text
UA 관련 guard와 연결되므로 method/protocol/auth/static 이후로 늦춘다.
```

### 3.6 `ip_behavior_aggregates` — 보류

성격:

- 동일 IP의 여러 signal을 집계한다.

보류 이유:

- 다른 summary와 candidate/supporting/filtering 구조를 가로지른다.
- 여러 저신호를 조합하는 과정에서 severity 상향처럼 해석될 위험이 있다.
- known asset / internal test possibility를 잃으면 안 된다.

현재 판단:

```text
초기 분리 대상 아님.
다른 summary builder가 안정화된 뒤 검토한다.
```

### 3.7 `probing_sequence_summaries` — 보류

성격:

- 동일 IP의 민감 경로 burst probing 흐름을 context-only로 보존한다.

보류 이유:

- D/H 계열 sensitive path, fallback HTML, candidate 과승격 방지와 연결된다.
- sample paths, distinct path count, status counts가 Stage2 해석과 직접 연결된다.
- candidate를 늘리지 않고 context만 전달하는 핵심 구조이므로 위험하다.

현재 판단:

```text
초기 분리 대상 아님.
```

### 3.8 `sensitive_path_probe_summaries` — 보류

성격:

- `.env`, `.git`, phpinfo, server-status, backup/admin/config path probe를 요약한다.

보류 이유:

- H R3와 file exposure 단정 금지 원칙에 직접 연결된다.
- 200/text/html + bytes를 노출 성공으로 해석하지 않는 guard가 중요하다.
- sensitive path category 세분화 검토와도 연결된다.

현재 판단:

```text
초기 분리 대상 아님.
```

### 3.9 `mixed_baseline_scanner_summaries` — 보류

성격:

- benign baseline과 scanner-like request가 섞인 흐름을 요약한다.

보류 이유:

- 가장 복합적인 context summary다.
- benign/scanner 경계, severity, Stage2 wording이 함께 움직인다.
- H R4 wording 품질 검토와 연결되어 있다.

현재 판단:

```text
가장 나중에 검토한다.
```

## 4. 우선순위 표

| 후보 | 우선순위 | 분리 판단 | 이유 |
|---|---:|---|---|
| `method_behavior_summaries` | 1 | 다음 후보 | 입력 단순, fixture 명확, 결합도 낮음 |
| `protocol_anomaly_summaries` | 2 | method 이후 | method와 비슷하지만 error/protocol 해석 주의 |
| `auth_behavior_summaries` | 3 | 보수 검토 | POST body 한계와 auth endpoint family 연결 |
| `static_baseline_summaries` | 4 | 나중 | baseline/crawler 경계 주의 |
| `crawler_baseline_summaries` | 5 | 나중 | UA 해석 guard와 연결 |
| `ip_behavior_aggregates` | 보류 | 초기 제외 | 여러 summary와 candidate 구조를 가로지름 |
| `probing_sequence_summaries` | 보류 | 초기 제외 | sensitive path/fallback/candidate 과승격 방지와 연결 |
| `sensitive_path_probe_summaries` | 보류 | 초기 제외 | file exposure 단정 금지와 연결 |
| `mixed_baseline_scanner_summaries` | 보류 | 초기 제외 | 복합 summary라 위험 높음 |

## 5. 다음 실제 작업

다음 작업은 코드 분리가 아니라 method summary에 대한 좁은 함수 inventory다.

추천 문서:

```text
docs/design/99_prepare_method_summary_split_plan.md
```

작성 내용:

```text
- method summary builder 함수명
- 호출 위치
- 입력 row/candidate 구조
- 출력 key 목록
- 사용하는 constants
- 사용하는 helper
- expected fixture와 stage dry-run fixture
- 분리 가능 범위
```

그다음 실제 코드 분리를 검토한다.

## 6. 실제 코드 분리 조건

`prepare/method_summaries.py` 또는 `prepare/context_summaries.py` 일부를 만들려면 아래 조건을 만족해야 한다.

```text
- method summary 관련 함수와 helper가 명확히 분리됨
- constants 이동 없이 기존 상수를 import해서 사용하거나, 상수 이동 범위를 별도 커밋으로 분리함
- output key와 summary count 변화 없음
- G R1 method behavior fixture 통과
- stage dry-run G R1 policy/count 유지
```

검증:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

성공 기준:

```text
prepare regression: 18 fixtures, warn=0 fail=0
stage dry-run regression: 12 fixtures, warn=0 fail=0
method_behavior_summaries count/policy/representative_requests 변화 없음
candidate / filtered_out / supporting_events 수 변화 없음
```

## 7. 현재 결론

- 다음 코드는 아직 분리하지 않는다.
- 다음 후보는 `method_behavior_summaries` 계열로 본다.
- 다음 작업은 `docs/design/99_prepare_method_summary_split_plan.md` 작성이다.
- 그 문서에서 실제 함수명/호출 위치/출력 key를 확정한 뒤 코드 분리를 진행한다.
