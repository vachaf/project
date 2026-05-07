# 99_prepare_ssrf_log4shell_fixture_plan

- 문서 상태: SSRF / metadata endpoint attempt / Log4Shell JNDI lookup fixture plan
- 기준 시점: 2026-05-07
- 목적: coverage plan 이후 실제 fixture/regression 추가 여부를 판단하기 위한 설계 기준을 고정한다.

관련 문서:

- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "log4shell\|jndi\|ssrf\|metadata\|169.254.169.254\|metadata.google.internal\|ldap://" src tests docs
grep -RIn "l3_log4shell\|l3_ssrf\|l3_ssti" tests/fixtures tests/expected docs
```

확인 요약:

```text
- src/prepare/l3_hints.py 에 detect_log4shell_hints / detect_ssrf_hints / classify_ssrf_target가 이미 존재한다.
- 현재 fixture/expected는 l3_log4shell_ssrf_context 1세트가 중심이다.
- prepare expected는 Log4Shell(ldap) + SSRF(metadata ip) candidate/hint 보존을 이미 검증한다.
- stage dry-run expected는 후보 보존과 성공 단정 금지(RCE 성공/SSRF 성공/침해 성공)를 이미 검증한다.
- l3_ssti_webshell_context fixture는 별도로 존재하지만, l3_ssrf 또는 l3_log4shell 명시 fixture는 추가로 보이지 않는다.
```

## 1. 목적

- coverage plan에서 정한 후보를 fixture/regression 관점으로 좁힌다.
- 바로 구현하지 않고 fixture 설계와 expected 확인 포인트를 먼저 고정한다.
- Apache logs-only evidence boundary를 유지한 채 candidate/context 경계를 명확히 한다.

## 2. 현재 coverage 확인 결과

기존 `l3_hints.py` 관련 coverage 요약:

- Log4Shell: `${jndi:(ldap|rmi|dns)://...}` 패턴을 감지해 `l3:log4shell`, `log4shell:jndi_lookup`, callback 계열 hint를 부여한다.
- SSRF: URL 파라미터(`url`, `target`, `redirect`, `callback` 등) 값이 `http/https`이고 metadata/localhost/internal target이면 `l3:ssrf`와 세부 hint를 부여한다.

기존 fixture 여부:

- 존재: `tests/fixtures/prepare_regression/l3_log4shell_ssrf_context.json`
- 존재: `tests/expected/prepare_regression/l3_log4shell_ssrf_context.expected.json`
- 존재: `tests/expected/stage_dryrun_regression/l3_log4shell_ssrf_context.expected.json`

이미 있는 coverage:

- Log4Shell basic payload(ldap) 1건의 candidate 보존
- SSRF metadata IP(`169.254.169.254`) 1건의 candidate 보존
- stage dry-run 입력(Stage1 payload, Stage2 top_incidents) 보존
- 성공 단정 문구 일부 금지

부족한 coverage:

- obfuscated JNDI payload
- `metadata.google.internal` hostname 케이스
- `127.0.0.1` / `localhost` internal URL parameter 케이스
- external URL parameter 케이스와 benign URL baseline 분리 검증
- status/bytes/timing만으로 성공을 유추하지 않도록 fixture별 expected를 더 촘촘히 고정하는 부분

## 3. fixture 후보 비교

### 3.1 Log4Shell basic JNDI payload

- 형태: query/path/header-like field에 `${jndi:ldap://...}`
- 판단: 기존 fixture가 일부 커버하므로 “유지/분리 여부”가 쟁점
- 용도: 고신호 payload의 candidate preserved 기준점

### 3.2 obfuscated JNDI payload

- 형태: `${${::-j}${::-n}${::-d}${::-i}:ldap://...}` 계열
- 판단: 이번 단계에서는 “필요 여부 검토”를 우선, 과한 변형 확장은 보류 가능
- 용도: regex 경계(직접 jndi만 허용 중)와 기대 동작(현재는 context-only 가능성) 확인

### 3.3 SSRF external URL parameter

- 형태: `url=http://example-attacker.test/callback`
- 판단: 단독으로 metadata/internal target이 아니면 low-signal일 수 있음
- 용도: external callback-like 값의 candidate 승격 기준 확인

### 3.4 SSRF internal URL parameter

- 형태: `url=http://127.0.0.1/admin`, `url=http://localhost:8080/`
- 판단: 현재 `classify_ssrf_target` 범위에 직접 매핑됨
- 용도: `ssrf:localhost_target`, `ssrf:internal_ip_target` 검증

### 3.5 metadata endpoint attempt

- 형태: `url=http://169.254.169.254/latest/meta-data/`, `url=http://metadata.google.internal/...`
- 판단: 기존 metadata IP는 커버되며 hostname 케이스는 추가 필요
- 용도: cloud metadata target 분류 일관성 검증

### 3.6 benign URL parameter baseline

- 형태: 정상 redirect/search/link 파라미터
- 판단: false positive 억제 경계 확인에 필수
- 용도: candidate 과승격 방지 및 context-only/reference 확인

## 4. 후보별 expected 검증 포인트

각 fixture에서 공통 확인:

- candidate preserved 여부
- L3 hint found 여부
- `reason_hints`에 SSRF/Log4Shell signal 포함 여부
- Stage2 report input(`top_incidents`/context)에 candidate/context 유지 여부
- 성공 단정 문구 없음
- `status_code=200`/`response_body_bytes`만으로 성공 확정하지 않음
- source IP/tool identity 단정 없음

fixture별 최소 확인 예시:

- Log4Shell basic: `l3:log4shell`, `log4shell:jndi_lookup` 유지
- obfuscated JNDI: candidate 또는 context-only 의도 중 하나를 명시 고정
- SSRF internal: `l3:ssrf` + `ssrf:url_parameter` + 내부 target hint
- metadata hostname: `ssrf:cloud_metadata_target` 포함
- benign baseline: 공격 계열로 과승격되지 않음을 확인

## 5. candidate vs context-only 기준

- 강한 payload 구조는 analysis candidate 가능
- 반복적/저신호 URL probing은 context-only 가능
- benign URL baseline은 filtered 또는 reference context 가능
- missing response body / raw POST body 한계는 그대로 유지

판단 메모:

- `${jndi:ldap://...}` 및 metadata/internal URL은 고신호이므로 candidate 우선
- obfuscation 변형은 현재 regex와의 간극을 고려해 1차에서는 context-only 고정도 가능
- external URL parameter 단독 케이스는 baseline/패턴 결합 여부에 따라 candidate 여부를 분리

## 6. Stage dry-run regression 추가 여부

선택지:

- prepare regression만 추가
- prepare + stage dry-run regression 동시 추가
- 필요 시 actual LLM spot check까지 수행

권장:

- 1차는 `prepare + stage dry-run regression` 동시 추가를 기준으로 계획한다.
- 이유: candidate/hint 보존뿐 아니라 Stage2 문구 단정 금지까지 함께 고정해야 재해석 drift를 줄일 수 있다.
- actual LLM spot check는 필수는 아니지만, obfuscation/benign baseline이 포함되면 샘플 1~2건 확인을 권장한다.

## 7. 구현 범위 후보

- 우선순위: 기존 `src/prepare/l3_hints.py` 확장으로 충분한지 검토
- 새 module 생성은 보류
- 아래 항목은 이번 작업 범위에서 제외:
  - `detect_decoded_attack_hints`
  - shared attack/search policy
  - `supporting_events`
  - scoring/filtering

범위 통제 이유:

- `99_prepare_hints_split_summary.md`, `99_prepare_deferred_split_items.md`에서 위 영역은 behavior risk가 큰 보류 대상으로 이미 고정돼 있다.
- fixture/expected로 경계를 먼저 고정한 뒤 최소 변경으로 접근해야 한다.

## 8. 권장 1차 fixture

권장 후보:

- `l3_ssrf_metadata_endpoint_context`
- `l3_log4shell_obfuscated_payload_context`

naming convention 메모:

- 기존 `l3_log4shell_ssrf_context`, `l3_ssti_webshell_context` 패턴과 맞춰 `l3_<family>_<focus>_context` 형태를 권장한다.
- internal URL 분리 시 대안 이름:
  - `l3_ssrf_internal_target_context`
  - `l3_ssrf_url_baseline_context`

## 9. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python3 -m pytest tests/test_stage2_report_quality.py
```

## 10. 결론

- 첫 구현 후보는 `metadata endpoint hostname 케이스 + obfuscated JNDI 케이스`를 분리 fixture로 추가하는 방향이 가장 합리적이다.
- fixture 추가 전 확인할 것:
  - obfuscated JNDI를 candidate로 볼지 context-only로 볼지 기대동작을 먼저 고정
  - benign URL baseline을 함께 넣어 false positive 경계를 동시 확인
  - Stage2 문구에서 성공/침해/유출/RCE/internal access 단정 금지 expected를 강화
- 코드 수정(구현)은 다음 작업으로 분리한다.
