# 99_prepare_api_key_secret_probe_coverage_plan

- 문서 상태: API key / secret token probe coverage plan
- 기준 시점: 2026-05-07
- 목적: `api_key=`/`token=`/`access_token=`/`secret=` 및 `.env`/config probe 계열을 Apache logs-only 기준으로 검토하고, fixture/regression 추가 여부를 보수적으로 판단한다.

관련 문서:

- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_xxe_coverage_plan.md](./99_prepare_xxe_coverage_plan.md)
- [99_prepare_ssti_coverage_plan.md](./99_prepare_ssti_coverage_plan.md)
- [99_prepare_open_redirect_coverage_plan.md](./99_prepare_open_redirect_coverage_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "api_key\|access_token\|token=\|secret=\|\.env\|config" src tests docs
```

확인 요약:

```text
- `.env`/config/sensitive path 계열은 `sensitive_path_probe`와 file disclosure 문맥에 이미 일부 반영되어 있다.
- API key/secret token probe는 정상 API traffic과 문자열 표면이 겹쳐 false positive 위험이 높다.
- 현재 단계에서는 구현보다 evidence boundary와 candidate/context 기준 고정이 우선이다.
```

## 1. 목적

- API key / secret token probe coverage 후보를 검토한다.
- `api_key=`/`token=`/`access_token=`/`secret=` 및 `.env`/config probe 계열의 Apache logs-only 해석 경계를 고정한다.
- 이번 문서는 구현 문서가 아니라 coverage plan 문서다.
- false positive 위험이 높으므로 이번 단계에서는 fixture/regression을 바로 추가하지 않는다.

## 2. 현재 상태

현재 검증 기준:

- prepare regression: `pass=25 warn=0 fail=0`
- stage dry-run regression: `pass=19 warn=0 fail=0`
- Stage2 report quality tests: `14 passed`

완료된 신규 coverage:

- `l3_ssrf_metadata_endpoint_context`
- `l3_log4shell_obfuscated_payload_context`
- `l3_webshell_admin_tool_probe_context`
- `l3_graphql_introspection_context`
- `l3_open_redirect_external_url_context`
- `l3_ssti_template_expression_context`
- `l3_xxe_external_entity_context`

현재 판단:

- API key/secret token probe는 P2 후속 후보로 유지한다.
- 다만 정상 API query와 표현이 겹쳐 false positive 위험이 높으므로 즉시 구현하지 않는다.

## 3. 관찰 가능한 signal

Apache logs-only 기준에서 관찰 가능한 signal:

- query string의 `api_key=`
- query string의 `access_token=`
- query string의 `token=`
- query string의 `secret=`
- `.env` 경로 접근 시도
- `/config`, `/config.php`, `/admin/config.php` 등 config-like path probe
- 반복적인 secret-like parameter probing 패턴
- status/bytes/timing metadata

보조 해석 원칙:

```text
- parameter name 자체는 intent signal일 수 있으나 exposure proof는 아니다.
- `.env`/config path 접근은 probing signal일 수 있으나 노출 성공 근거는 아니다.
```

## 4. Apache logs-only 단정 금지

아래 표현/판단은 금지한다.

- API key leaked
- token exfiltrated
- credential theft
- auth bypass
- secret exposed
- config disclosed
- response body contained secret
- server compromised

보수적 원칙:

```text
- Apache access logs alone do not confirm secret exposure.
- raw POST body 원문과 response body 원문은 알 수 없다.
- status_code=200/response_body_bytes만으로 유출/인증우회를 단정하지 않는다.
```

## 5. 기존 module과의 경계

file_disclosure_hints와의 경계:

- wrapper/resource 기반 file disclosure signal과 의미가 겹칠 수 있다.
- file disclosure 의심과 secret probe 의심을 혼동하지 않도록 분리된 reason_hints 설계가 필요하다.
- `file_disclosure:*`는 시도 근거이지 노출 성공 근거가 아니다.

sensitive_path_probe와의 경계:

- `.env`/`/config`/backup 계열 접근은 context-only summary와 강하게 인접한다.
- low-signal path 접근을 candidate로 과승격하지 않도록 기본값은 context-only 우선이 안전하다.

shared attack/search policy와의 경계:

- 일반 검색/정상 API query와 공격성 probe를 구분하는 정책을 유지해야 한다.
- shared attack/search policy를 약화하거나 우회하는 별도 규칙 추가는 지양한다.

normal search false-positive와의 경계:

- `token`, `secret`, `api key` 같은 일반 검색어성 질의는 FP 위험이 매우 높다.
- normal search FP 억제 규칙과 충돌하지 않도록 보수적으로 다뤄야 한다.

## 6. candidate vs context-only 초안 기준

candidate 가능 조건(초안):

- secret-like parameter가 반복 probing 패턴으로 관찰되는 경우
- `.env`/config path probe와 secret-like query probing이 결합된 경우
- 단일 요청이 아닌 sequence context에서 공격성 직접성이 높아지는 경우

context-only 우선 조건(초안):

- 단건 `token=`/`secret=` 요청
- 정상 API endpoint의 일반 파라미터 사용 가능성이 큰 경우
- 문서/개발 검색성 요청(`q=api key`, `q=token`) 
- `.env`/config 단순 접근 1건

고정 규칙:

```text
- status/bytes만으로 secret exposure 또는 auth bypass를 판단하지 않는다.
- response body 원문 부재 상황에서 내용 유출을 단정하지 않는다.
```

## 7. Stage2 wording/lint guard 필요 여부

필요하다(높음).

금지 표현:

- API key leaked
- token exfiltrated
- credential theft
- auth bypass
- secret exposed

허용 표현:

- secret-token-like parameter probe observed
- API key-like query parameter observed
- sensitive config path probing context
- requires manual review

## 8. fixture/regression 추가 여부 (이번 단계 판단)

이번 단계 결론:

- fixture/regression **즉시 추가 보류**
- coverage plan 문서화만 수행

보류 이유:

- 정상 API traffic과 신호 중첩으로 false positive 위험이 높음
- candidate 승격 기준을 먼저 더 엄격히 고정해야 함
- `file_disclosure_hints`/`sensitive_path_probe`/shared policy 경계 정합성 검토가 선행되어야 함

## 9. 구현 범위 원칙(차기 작업용)

차기 구현 시에도 아래는 고정:

```text
- 새 module 생성 보류
- shared attack/search policy 변경 금지
- normal search false-positive handling 변경 금지
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지(필요 시 wording guard만 별도 검토)
```

## 10. 검증 기준

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- API key / secret token probe는 다음 신규 coverage 후보로 유지한다.
- false positive 위험이 높아 이번 단계에서는 fixture/regression을 추가하지 않는다.
- 우선은 경계 문서화(본 문서)를 기준으로 유지하고, 다음 단계에서 fixture plan 분리 여부를 별도 판단한다.
- Webshell command query와의 우선순위는 병행 비교하되, Webshell은 traversal/CMDI 경계 민감도 때문에 별도 검토를 유지한다.
