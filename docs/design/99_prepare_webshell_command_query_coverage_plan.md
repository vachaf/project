# 99_prepare_webshell_command_query_coverage_plan

- 문서 상태: Webshell command query endpoint coverage plan
- 기준 시점: 2026-05-07
- 목적: Webshell-like path와 command-like query parameter 결합 시그널을 Apache logs-only 경계에서 검토하고, fixture/regression 추가 여부를 판단한다.

관련 문서:

- [99_prepare_webshell_probe_coverage_plan.md](./99_prepare_webshell_probe_coverage_plan.md)
- [99_prepare_webshell_probe_fixture_plan.md](./99_prepare_webshell_probe_fixture_plan.md)
- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_api_key_secret_probe_coverage_plan.md](./99_prepare_api_key_secret_probe_coverage_plan.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_traversal_cmdi_hints_split_plan.md](./99_prepare_traversal_cmdi_hints_split_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "cmd=\|exec=\|command=\|shell=\|whoami\|/cmd.php\|/shell.php\|webshell\|traversal_cmdi\|cmdi" src tests docs
```

확인 요약:

```text
- path-only webshell/admin probe는 l3_webshell_admin_tool_probe_context로 이미 1차 회귀가 고정되어 있다.
- command-like query endpoint는 traversal/CMDI 경계와 webshell 경계가 겹치는 후속 후보다.
- 기존 l3_ssti_webshell_context에 /upload/shell.php?cmd=id 복합 샘플이 있으나, webshell command-query 단독 family 회귀는 아직 별도 고정되지 않았다.
```

## 1. 목적

- Webshell command query endpoint coverage 후보를 검토한다.
- 구현 코드 작성이 아니라 boundary/coverage plan 문서를 작성한다.
- fixture/regression 추가 여부를 판단하기 위한 기준 문서다.
- 아래 단정 금지 기준을 먼저 고정한다.

```text
- command execution 단정 금지
- shell access 단정 금지
- RCE 단정 금지
- compromise 단정 금지
```

## 2. 현재 상태

- `l3_webshell_admin_tool_probe_context`는 path-only webshell/admin probe를 이미 다룬다.
- Webshell command query는 command-like parameter가 결합된 후속 coverage 후보다.
- `traversal_cmdi_hints`와 의미 경계가 민감하며, 해석 순서/문구 정렬이 중요하다.
- API key / secret token probe는 coverage plan만 작성되고 fixture/regression은 보류 상태다.

현재 회귀/검증 상태:

- prepare regression: `pass=25 warn=0 fail=0`
- stage dry-run regression: `pass=19 warn=0 fail=0`
- Stage2 report quality tests: `14 passed`

완료된 신규 coverage regression:

- `l3_ssrf_metadata_endpoint_context`
- `l3_log4shell_obfuscated_payload_context`
- `l3_webshell_admin_tool_probe_context`
- `l3_graphql_introspection_context`
- `l3_open_redirect_external_url_context`
- `l3_ssti_template_expression_context`
- `l3_xxe_external_entity_context`

## 3. 관찰 가능한 signal

Apache logs-only에서 관찰 가능한 signal:

- `/cmd.php?cmd=id`
- `/shell.php?exec=whoami`
- `/upload/shell.php?cmd=id`
- `/admin/shell.php?command=id`
- `cmd=`, `exec=`, `command=`, `shell=` query parameter
- webshell-like filename + command-like parameter 결합
- status/bytes/timing metadata

보조 해석 원칙:

```text
- parameter/value 형태는 intent signal일 수 있으나 실행 성공 증거는 아니다.
- status/bytes/timing은 보조 signal이며 실행/침해 확정 근거가 아니다.
```

## 4. Apache logs-only로 단정 금지

아래 표현/판단은 금지한다.

- command executed
- shell access gained
- webshell exists
- RCE succeeded
- attacker gained shell
- server compromised
- exploit succeeded
- response body contained command output
- upload succeeded

보수적 원칙:

```text
- Apache access logs alone do not confirm command execution or shell access.
- raw POST body 원문과 response body 원문은 알 수 없다.
- status_code=200/response_body_bytes만으로 실행 성공을 단정하지 않는다.
```

## 5. 기존 module과의 관계

`l3_hints.py` webshell hint와의 관계:

- `detect_webshell_hints`/`classify_webshell_path`는 webshell-like path와 command-like parameter를 이미 다루는 기반을 가진다.
- command-query coverage는 기존 hint 체계를 우선 활용하는 방향이 적절하다.

`traversal_cmdi_hints`와의 관계:

- `cmd=`, `exec=` 계열은 traversal/CMDI 신호와 의미가 겹칠 수 있다.
- query parameter만으로 CMDI/실행 성공을 단정하지 않고, webshell path 결합 여부를 함께 본다.

`sensitive_path_probe`와의 관계:

- 단순 path-only probing은 summary/context-only 경계에 남길 수 있다.
- command-query 결합이 있을 때만 candidate 승격을 검토한다.

`file_disclosure_hints`와의 경계:

- file disclosure family 의미를 변경하지 않는다.
- webshell command-query 문맥과 file disclosure 문맥은 분리해 해석한다.

기존 fixture와의 차이:

- `l3_webshell_admin_tool_probe_context`: path-only admin/webshell probe 중심
- `l3_ssti_webshell_context`: SSTI + webshell 복합 케이스
- 본 후보: webshell command-query 단독 family를 별도 검토

이번 계획에서 유지할 제외 범위:

```text
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지
```

## 6. candidate vs context-only 기준

candidate 가능 조건:

- webshell-like path + command-like query parameter 결합
- 동일 request/sequence에서 command-like probing 반복이 관찰되고 path 신호가 동반되는 경우

context-only 또는 보수 처리 조건:

- command-like query parameter만 존재하고 webshell path 신호가 약한 경우
- 단순 `/shell.php` path-only 요청(기존 path-only probe 문맥과 중복)
- benign/static/search 문맥과 구분이 약한 경우

고정 규칙:

```text
- status_code=200 또는 response_body_bytes를 command execution 성공 근거로 사용하지 않는다.
```

## 7. Fixture/regression 아이디어

후보 fixture:

- `l3_webshell_command_query_context`
  - `GET /cmd.php?cmd=id`
  - `GET /shell.php?exec=whoami`
  - `GET /upload/shell.php?cmd=id`

benign baseline:

- `GET /docs?topic=shell`
- `GET /static/shell-icon.png`
- `GET /search?q=whoami`

expected 확인 포인트:

- webshell-like path + command-like query candidate/context 보존
- webshell/CMDI 관련 hint 확인
- benign shell/search/static baseline 과승격 방지
- Stage2 input에 candidate/context 유지
- success wording 없음

## 8. Stage2 wording/lint guard 필요 여부

필요하다.

금지 표현:

- command executed
- shell access gained
- webshell exists
- RCE succeeded
- attacker gained shell
- server compromised
- command output returned
- exploit succeeded

허용 표현:

- webshell-like command query observed
- command-like query parameter observed
- webshell path with command-like parameter
- requires manual review
- Apache logs alone do not confirm command execution or shell access

## 9. 권장 결론

- traversal/CMDI 경계가 민감하므로 즉시 regression 추가보다 fixture plan 1회 선행이 안전하다.
- 기본 권장은 `l3_webshell_command_query_context`를 fixture plan에서 샘플 최소화/중복 제거 기준으로 먼저 고정한 뒤 구현 여부를 결정한다.
- 이미 존재하는 `l3_ssti_webshell_context`와 중복 최소화 기준이 확보되면 보수적으로 1차 regression을 추가할 수 있다.

## 10. 검증 기준

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```
