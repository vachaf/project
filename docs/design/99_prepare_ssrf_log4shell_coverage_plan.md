# 99_prepare_ssrf_log4shell_coverage_plan

- 문서 상태: SSRF / metadata endpoint attempt / Log4Shell JNDI lookup coverage plan
- 기준 시점: 2026-05-07
- 목적: 새 공격 coverage 후보 중 첫 단기 후보로 SSRF / metadata endpoint attempt / Log4Shell JNDI lookup 계열을 검토하고, Apache logs-only evidence boundary를 먼저 고정한 뒤 fixture/regression 추가 여부와 구현 범위를 판단한다.

관련 문서:

- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [99_prepare_deferred_split_reentry_review.md](./99_prepare_deferred_split_reentry_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "log4shell\|jndi\|ssrf\|metadata\|169.254.169.254\|callback\|ldap://" src tests docs
grep -RIn "l3_log4shell\|l3_ssrf\|l3_ssti" tests/fixtures tests/expected docs
```

확인 요약:

```text
- src/prepare/l3_hints.py에 detect_log4shell_hints, detect_ssrf_hints, classify_ssrf_target가 이미 존재한다.
- 현재 L3 hint는 JNDI lookup regex, SSRF URL parameter, metadata IP/hostname 분류를 이미 다룬다.
- tests/fixtures/prepare_regression/l3_log4shell_ssrf_context.json 과 prepare/stage dry-run expected가 이미 존재한다.
- stage dry-run expected는 RCE 성공, SSRF 성공, 침해 성공 단정을 금지하는 guard를 이미 포함한다.
```

## 1. 목적

- SSRF / metadata endpoint attempt / Log4Shell JNDI lookup coverage 후보를 첫 단기 검토 대상으로 고정한다.
- Apache access/security log 표면에 남는 요청 신호만 근거로 삼는다.
- outbound request, RCE, internal access, metadata retrieval, callback 발생을 단정하지 않는 기준을 먼저 고정한다.
- 이번 문서는 구현 코드 작성이 아니라 coverage plan과 fixture/regression 판단 기준을 정리하는 문서다.

## 2. 현재 상태

현재 repo에는 이 계열을 위한 최소 L3 hints와 regression 바닥면이 이미 있다.

- `src/prepare/l3_hints.py`
  - `detect_log4shell_hints()`
  - `detect_ssrf_hints()`
  - `classify_ssrf_target()`
- 현재 JNDI 계열 signal
  - `${jndi:ldap://...}`
  - `${jndi:rmi://...}`
  - `${jndi:dns://...}`
- 현재 SSRF 계열 signal
  - `url`, `uri`, `target`, `next`, `redirect`, `callback`, `webhook`, `image`, `fetch`, `resource`
  - `169.254.169.254`
  - `metadata.google.internal`
  - `localhost`, loopback, private IP

기존 fixture/regression 상태:

- `tests/fixtures/prepare_regression/l3_log4shell_ssrf_context.json`
- `tests/expected/prepare_regression/l3_log4shell_ssrf_context.expected.json`
- `tests/expected/stage_dryrun_regression/l3_log4shell_ssrf_context.expected.json`

현재 fixture가 고정하는 사실:

- `${jndi:ldap://...}` 요청은 `analysis_candidates`에 남는다.
- `reason_hints`에는 `l3:log4shell`, `log4shell:jndi_lookup`, `log4shell:ldap_callback`이 포함된다.
- metadata target URL parameter 요청은 `analysis_candidates`에 남는다.
- `reason_hints`에는 `l3:ssrf`, `ssrf:url_parameter`, `ssrf:metadata_ip`, `ssrf:cloud_metadata_target`이 포함된다.
- stage dry-run expected는 Stage2 markdown에서 `RCE 성공`, `SSRF 성공`, `침해 성공` 단정을 금지한다.

안정 상태 요약:

```text
- prepare regression: pass=18 warn=0 fail=0
- stage dry-run regression: pass=12 warn=0 fail=0
- Stage2 report quality tests: 14 passed
- prepare split / hints split / Stage2 wording lint는 stable 상태로 유지 중
```

즉, 이번 후보는 완전한 신규 축이라기보다 기존 L3 바닥면 위에서 coverage boundary를 확장할지 검토하는 작업이다.

## 3. 관찰 가능한 signal

Apache logs-only 기준에서 이 계열은 아래 요청 표면 신호까지를 관찰 가능한 범위로 본다.

- `${jndi:ldap://...}`
- `${jndi:rmi://...}`
- query/path/header-like 위치의 JNDI marker
- case variation, delimiter variation, 단순 obfuscation이 있는 JNDI-like payload
- URL parameter에 external URL 또는 internal URL이 직접 들어간 값
- metadata endpoint 후보
  - `169.254.169.254`
  - `metadata.google.internal`
  - cloud metadata style path 예: `/latest/meta-data/`, `/computeMetadata/`
- callback URL / redirect-like parameter
- internal URL probing, localhost probe, RFC1918 target probe
- repeated probing pattern
- status/bytes/timing metadata

해석 규칙:

```text
- payload marker는 request surface signal이다.
- status_code, response_body_bytes, duration_us, ttfb_us는 보조 metadata다.
- 반복 패턴은 sequence/context summary 보조 신호일 뿐 단독 확정 근거가 아니다.
```

## 4. Apache logs-only로 단정 금지

이 계열은 아래 항목을 Apache logs만으로 단정하지 않는다.

- outbound request success
- DNS/LDAP/RMI callback 발생
- cloud metadata credential 탈취
- internal network access success
- JNDI lookup success
- RCE success
- server compromise
- vulnerability existence
- exploit success

보수적 해석 원칙:

```text
- request에 JNDI-like payload가 있어도 lookup resolution이나 callback 발생을 뜻하지 않는다.
- metadata URL이 parameter에 있어도 metadata retrieval이나 credential exposure를 뜻하지 않는다.
- status_code=200, response_body_bytes, timing 변화만으로 exploit success를 뜻하지 않는다.
```

## 5. 기존 module과의 관계

현재 관계의 중심은 `src/prepare/l3_hints.py`다.

- `detect_log4shell_hints`
  - JNDI lookup-like string을 L3 hint로 보존하는 경계다.
- `detect_ssrf_hints`
  - URL parameter와 SSRF target classification을 L3 hint로 보존하는 경계다.
- `classify_ssrf_target`
  - metadata/localhost/internal target을 분류하되, 요청 성공 여부는 다루지 않는다.

경계 유지 원칙:

- `detect_decoded_attack_hints`와는 분리해서 본다.
  - decoded reconstruction은 payload 재구성이지 execution proof가 아니다.
  - 이번 계획에서도 decoded shared logic을 새로 흡수하거나 ownership을 바꾸지 않는다.
- shared attack/search policy와도 분리해서 본다.
  - normal search false-positive suppression과 candidate preservation 경계를 흔들지 않는다.
- `supporting_events`, scoring, filtering은 건드리지 않는다.
  - 이번 후보는 hint/candidate boundary와 wording guard 검토가 먼저다.

## 6. candidate vs context-only 판단

이 계열은 모든 신호를 candidate로 올리기보다 직접성에 따라 나눈다.

analysis candidate로 둘 수 있는 경우:

- `${jndi:ldap://...}` 또는 `${jndi:rmi://...}`처럼 직접적인 JNDI lookup-like payload가 query/path/header-like 위치에 보일 때
- `url=` 또는 유사 parameter 값에 `http://` 또는 `https://` target이 직접 들어가고, 그 target이 metadata/localhost/RFC1918/internal hostname을 가리킬 때
- callback/redirect-like parameter에 외부 URL 또는 internal URL이 직접 주입된 형태가 분명할 때
- 같은 요청 안에서 JNDI marker와 obfuscation 변형이 함께 관찰되어 고신호 family로 볼 수 있을 때

context-only summary로 두는 것이 나은 경우:

- repeated probing pattern만 있고 개별 요청의 payload 직접성이 약할 때
- redirect-like parameter 이름은 있으나 값이 일반 상대경로이거나 benign browse와 구분이 약할 때
- metadata style path 조각만 있고 target URL 또는 명시적 JNDI marker가 없어 단일 요청 신호가 약할 때
- status/bytes/timing 변화만으로 의도를 해석해야 하는 경우

금지 원칙:

```text
- status=200이나 response_body_bytes를 exploit success 근거로 쓰지 않는다.
- duration_us/ttfb_us를 outbound call 또는 lookup success 근거로 쓰지 않는다.
- 반복 요청 수만으로 candidate 승격을 결정하지 않는다.
```

## 7. Fixture/regression 아이디어

이번 작업에서는 fixture를 추가하지 않는다. 다만 다음 구현 단계에서 검토할 후보는 아래와 같다.

- SSRF URL parameter fixture
  - `url=` / `target=` / `callback=` / `redirect=`에 external/internal URL이 들어가는 샘플
- metadata endpoint attempt fixture
  - `169.254.169.254`
  - `metadata.google.internal`
  - cloud metadata style path가 포함된 target URL
- Log4Shell JNDI query/path/header-like payload fixture
  - `${jndi:ldap://...}`
  - `${jndi:rmi://...}`
  - 단순 obfuscation variation
- benign URL parameter baseline 포함 여부
  - 일반 search/filter/navigation용 `url` 또는 `next` parameter가 공격 candidate로 과승격되지 않는지 확인하는 샘플

expected에서 확인할 것:

- candidate preserved
- L3 hint found
- success wording 없음
- Stage2 input retains candidate/context

추가 확인 포인트:

- 기존 `l3_log4shell_ssrf_context`를 확장할지
- 새 fixture를 family별로 분리할지
- benign baseline을 함께 넣어 false positive 억제 경계를 고정할지

## 8. Stage2 wording/lint guard 필요 여부

필요하다.

기존 stage dry-run expected는 이미 `RCE 성공`, `SSRF 성공`, `침해 성공`을 막고 있다. 이 후보를 확장한다면 metadata/JNDI 전용 금지 표현도 같은 수준으로 고정하는 편이 안전하다.

금지 표현:

- outbound request succeeded
- metadata stolen
- RCE succeeded
- JNDI lookup succeeded
- internal network accessed

허용 표현:

- SSRF-like request pattern
- metadata endpoint access attempt
- JNDI lookup-like payload observed
- requires manual review

권장 원칙:

```text
- hint name이나 candidate name이 Stage2 문장에서 성공 서술로 번역되지 않게 한다.
- callback, metadata, internal target 같은 단어가 있어도 request pattern 또는 attempt wording으로 제한한다.
- lint 또는 regression expected는 success/assertive wording을 명시적으로 막는 방향이 적절하다.
```

## 9. 구현 범위 후보

현재 단계에서 가능한 구현 범위 후보는 아래 수준에 묶는다.

- 기존 `src/prepare/l3_hints.py` 확장 가능성 검토
- shared attack hint path에서 최소 보강 검토

보류할 것:

- 새 module 생성 여부는 보류
- `prepare_llm_input.py` 직접 대규모 수정 금지
- `supporting_events` 변경 금지
- scoring/filtering 변경 금지

구현 전 선행 판단:

```text
- fixture/regression 경계가 먼저 고정되어야 한다.
- mechanical한 hint 확장인지, policy/search boundary를 흔드는 변경인지 먼저 구분해야 한다.
- new module 필요성은 초기 fixture/guard 검토 후 다시 판단한다.
```

## 10. 검증 기준

향후 실제 구현을 시작할 때의 검증 기준은 아래를 유지한다.

- `python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py`
- `python3 scripts/check_prepare_regression.py --strict`
- `python3 scripts/check_stage_dryrun_regression.py --strict`
- `python3 -m pytest tests/test_stage2_report_quality.py`
- 필요 시 dry-run spot check
- 필요 시 actual LLM spot check

검증 의도:

```text
- prepare regression strict 유지
- stage dry-run regression strict 유지
- Stage2 report quality wording guard 유지
- candidate/context preservation 계약 유지
```

## 11. 결론

SSRF / metadata endpoint attempt / Log4Shell JNDI lookup은 첫 단기 coverage 후보로 적절하다.

이유:

- 이미 `l3_hints.py`와 `l3_log4shell_ssrf_context` regression 바닥면이 있다.
- Apache logs-only boundary를 분명하게 고정할 수 있다.
- Stage1/Stage2 wording guard 필요성이 명확하고, fixture/regression으로 계약을 고정하기 좋다.
- shared family 확장으로 시작할 수 있어 초기 범위를 작게 유지하기 쉽다.

권장 순서:

1. 이 문서 기준으로 fixture/regression 계획을 먼저 더 구체화한다.
2. 그 다음 최소 범위의 `l3_hints.py` 또는 shared hint path 보강 여부를 판단한다.
3. scoring/filtering/supporting_events/new module 논의는 뒤로 미룬다.

Webshell/admin tool probe와의 우선순위 비교:

- Webshell/admin tool probe도 P1 후보지만, SSRF/Log4Shell은 이미 관련 hint와 regression fixture가 존재해 첫 번째 단기 후보로 더 적절하다.
- Webshell/admin tool probe는 sensitive path context와 candidate 경계 정리가 조금 더 필요하므로 본 후보 다음 순서가 무난하다.

최종 판단:

```text
- 바로 구현보다 fixture/regression 계획 고정이 먼저다.
- Apache logs-only 원칙을 강화하는 방향의 coverage plan으로 시작한다.
- 첫 short-term coverage 후보로 채택 가능하다.
```
