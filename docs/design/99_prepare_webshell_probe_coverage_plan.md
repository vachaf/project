# 99_prepare_webshell_probe_coverage_plan

- 문서 상태: Webshell / admin tool probe coverage plan
- 기준 시점: 2026-05-07
- 목적: 새 공격 coverage 단기 P1 후보 중 Webshell / admin tool probe 계열을 검토하고, Apache logs-only evidence boundary를 먼저 고정한 뒤 fixture/regression 추가 여부를 판단한다.

관련 문서:

- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_ssrf_log4shell_fixture_plan.md](./99_prepare_ssrf_log4shell_fixture_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_file_disclosure_hints_split_plan.md](./99_prepare_file_disclosure_hints_split_plan.md)
- [99_prepare_traversal_cmdi_hints_split_plan.md](./99_prepare_traversal_cmdi_hints_split_plan.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_mixed_baseline_scanner_split_plan.md](./99_prepare_mixed_baseline_scanner_split_plan.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "webshell\|shell.php\|cmd.php\|wso\|c99\|r57\|phpunit\|cgi-bin\|upload.php\|filemanager\|file-manager" src tests docs
grep -RIn "sensitive_path_probe\|file_disclosure\|traversal_cmdi\|mixed_baseline_scanner" src/prepare tests/expected docs/design
```

확인 요약:

```text
- src/prepare/l3_hints.py 에 WEBSHELL_KNOWN_FILENAMES, classify_webshell_path, detect_webshell_hints, l3:webshell_probe 경로가 이미 존재한다.
- src/prepare_llm_input.py 는 webshell hint를 reason_hints/category로 반영하는 wrapper/coordinator 경로를 이미 가진다.
- tests/fixtures, tests/expected 에 l3_ssti_webshell_context 회귀 샘플이 이미 존재한다.
- sensitive_path_probe/file_disclosure/traversal_cmdi/mixed_baseline_scanner는 모두 split 완료 상태이며 context-only 경계 문구가 고정되어 있다.
```

## 1. 목적

- Webshell / admin tool probe coverage 후보를 검토한다.
- 이번 문서는 구현 코드 작성 문서가 아니라 coverage plan 문서다.
- fixture/regression 추가 여부를 판단하기 위한 기준 문서다.
- 아래 단정 금지 기준을 먼저 고정한다.

```text
- webshell 존재 단정 금지
- command execution 단정 금지
- upload success 단정 금지
- compromise 단정 금지
```

## 2. 현재 상태

기존 module/coverage와의 현재 관계:

- `sensitive_path_probe`는 민감 경로 probing을 context-only summary로 보존한다.
- `file_disclosure_hints`는 wrapper/resource 계열 file exposure 시도 신호를 분리 관리한다.
- `traversal_cmdi_hints`는 traversal/CMDI payload token 경계를 관리한다.
- `mixed_baseline_scanner`는 baseline + scanner 혼합 문맥을 context-only로 보존한다.
- `l3_hints`에는 webshell 계열 path/parameter 힌트가 이미 존재한다.

이미 context-only로 처리되는 영역 확인:

```text
- sensitive_path_probe_summaries / mixed_baseline_scanner_summaries 는 context-only collection
- scanner-like path 요청은 summary/supporting_events로 내려가는 경로가 이미 존재
- low-signal 반복 probe는 candidate보다 context 보존 우선 경로가 이미 존재
```

현재 regression 상태 요약:

```text
- prepare regression pass=20 warn=0 fail=0
- stage dry-run regression pass=14 warn=0 fail=0
- Stage2 quality tests 14 passed
```

## 3. 관찰 가능한 signal

Apache logs-only에서 관찰 가능한 주요 signal:

- `/shell.php`
- `/cmd.php`
- `/wso.php`
- `/c99.php`
- `/r57.php`
- `/vendor/phpunit/...`
- `/cgi-bin/...` admin/tool style path
- `/upload.php`
- `/filemanager` 또는 `/file-manager`
- `cmd=`, `exec=`, `command=`, `shell=` 형태 query parameter
- repeated probing pattern
- status/bytes/timing metadata

## 4. Apache logs-only로 단정 금지

아래 항목은 Apache logs만으로 단정하지 않는다.

- webshell exists
- command executed
- upload succeeded
- file manager accessed
- RCE succeeded
- server compromised
- response body contents
- attacker identity
- exploit success

보수적 해석 원칙:

```text
- status_code=200, response_body_bytes, timing 변화는 보조 signal이지 실행/침해 확정 근거가 아님
- request path/query 구조는 의심 신호이며, 시스템 상태 확정 정보가 아님
```

## 5. 기존 module과의 관계

- `sensitive_path_probe`
  - path probe/context-only boundary를 담당
  - webshell/admin tool probing 저신호 반복은 summary 쪽에 남길 여지가 큼
- `file_disclosure_hints`
  - file exposure/sensitive file probe boundary를 담당
  - webshell path probing 자체와는 분리하되 wrapper/resource 동반 시 경계 충돌 가능성만 점검
- `traversal_cmdi_hints`
  - command-like token/traversal payload boundary를 담당
  - `cmd=` 형태는 webshell 후보와 겹칠 수 있어 해석 순서/문구 정렬이 필요
- `mixed_baseline_scanner`
  - mixed static/baseline/probe context 보존
  - admin/tool style path가 benign/static 흐름과 섞일 때 과승격 억제 역할
- `l3_hints`
  - webshell L3 후보(`l3:webshell_probe`, `webshell:*`)가 이미 존재함을 확인

이번 계획에서 유지할 제외 범위:

```text
- supporting_events 변경 없음
- scoring/filtering 변경 없음
```

## 6. candidate vs context-only 기준

candidate 가능 조건:

- 강한 webshell/admin tool path + command-like query가 함께 관찰되는 경우
- 동일 request에서 webshell filename 신호와 command-like parameter 신호가 결합되는 경우

context-only 또는 summary 우선 조건:

- 단순 `/shell.php` 404/low-signal 반복
- path 신호는 있으나 query/패턴 직접성이 약한 경우
- baseline/static/admin noise와 구분이 약한 경우

고정 규칙:

```text
- status=200 또는 bytes 크기를 성공 근거로 사용하지 않음
```

## 7. Fixture/regression 아이디어

이번 문서에서는 fixture를 추가하지 않고 후보만 고정한다.

후보 시나리오:

- direct webshell path probe
  - `GET /shell.php`
  - `GET /wso.php`
- admin tool probe
  - `GET /vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php`
  - `GET /cgi-bin/admin.cgi`
- command-like query
  - `GET /cmd.php?cmd=id`
- benign admin/static baseline
  - `GET /admin/help`
  - `GET /static/shell-icon.png`

expected 확인 포인트:

- strong webshell/admin probe candidate/context 보존
- webshell/admin/tool hint 확인
- benign baseline 과승격 방지
- success wording 없음
- Stage2 input candidate/context 유지

## 8. Stage2 wording/lint guard 필요 여부

필요하다.

금지 표현:

- webshell exists
- command execution succeeded
- upload succeeded
- server compromised
- attacker gained shell
- RCE succeeded

허용 표현:

- webshell-like path probe
- admin tool probe
- command-like query parameter observed
- requires manual review
- Apache logs alone do not confirm execution or compromise

## 9. 구현 범위 후보

비교 대상:

- `sensitive_path_probe` 확장: low/medium signal path probe를 context summary로 유지하면서 경계 강화
- `traversal_cmdi_hints` 확장: command-like token 신호의 결합 조건만 제한적으로 점검
- `file_disclosure_hints` 확장: 직접 대상은 아니며 경계 충돌 가능성만 점검
- `l3_hints` 확장: webshell/admin probe 계열 hint 네이밍/범위 최소 보강 가능성

현재 계획 고정:

```text
- 새 module 생성은 보류
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지
```

## 10. 권장 1차 fixture 후보

권장 후보(이름 제안):

- `l3_webshell_admin_tool_probe_context`
- `l3_webshell_command_query_context`

메모:

- 기존 naming convention(`l3_<family>_<focus>_context`)에 맞춘 이름이다.
- 대안으로 `webshell_admin_tool_probe_context`, `webshell_command_query_context`도 가능하나 기존 `l3_*_context`와 맞추는 쪽이 일관성이 높다.

## 11. 검증 기준

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

필요 시:

- dry-run spot check
- actual LLM spot check

## 12. 결론

- Webshell/admin tool probe는 단기 P1 후보로 유지할 가치가 있다.
- 다만 Apache logs-only 경계를 먼저 고정하고, fixture/expected 설계를 한 번 더 확정한 뒤 구현에 들어가는 순서가 안전하다.
- 즉시 구현보다 fixture plan 보강 1회가 우선이다.
- 우선순위는 SSRF/Log4Shell과 병행 가능한 P1 축으로 정리하되, 현재 안정 regression을 흔들지 않는 최소 범위로 진행한다.
