# 99_prepare_webshell_probe_fixture_plan

- 문서 상태: Webshell / admin tool probe fixture plan
- 기준 시점: 2026-05-07
- 목적: Webshell/admin tool probe coverage plan 이후 실제 fixture/regression 추가 여부를 판단하기 위한 설계 기준을 고정한다.

관련 문서:

- [99_prepare_webshell_probe_coverage_plan.md](./99_prepare_webshell_probe_coverage_plan.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_fixture_plan.md](./99_prepare_ssrf_log4shell_fixture_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "webshell\|shell.php\|cmd.php\|wso\|c99\|r57\|phpunit\|cgi-bin\|upload.php\|filemanager\|file-manager" src tests docs
grep -n "webshell\|l3:webshell\|webshell_probe" src/prepare/l3_hints.py src/prepare_llm_input.py
grep -RIn "webshell\|phpunit\|cmd.php\|wso" tests/fixtures tests/expected
```

확인 요약:

```text
- src/prepare/l3_hints.py 에 WEBSHELL_KNOWN_FILENAMES, classify_webshell_path, detect_webshell_hints, l3:webshell_probe, webshell:cmd_parameter 경로가 이미 존재한다.
- src/prepare_llm_input.py 는 webshell hint를 wrapper/coordinator 경로로 반영하고 category(webshell)로 연결한다.
- existing fixture/expected는 l3_ssti_webshell_context 중심이며 /upload/shell.php?cmd=id 케이스를 이미 포함한다.
- tests 기준으로 phpunit/c99/wso/cgi-bin/admin probe를 직접 고정하는 fixture/expected는 현재 부족하다.
```

## 1. 목적

- coverage plan에서 정한 Webshell/admin tool probe 후보를 fixture/regression 관점으로 좁힌다.
- 바로 구현하지 않고 fixture 설계와 expected 확인 포인트를 먼저 고정한다.
- 이번 작업은 fixture plan 문서 작성이며 fixture/expected/code 수정은 수행하지 않는다.

## 2. 현재 coverage 확인 결과

`l3_hints.py` webshell 관련 상태:

- `WEBSHELL_KNOWN_FILENAMES={shell.php, cmd.php, webshell.php, wso.php, c99.php, r57.php}`
- `classify_webshell_path()` 존재
- `detect_webshell_hints()` 존재
- `l3:webshell_probe`, `webshell:script_filename`, `webshell:known_shell_name`, `webshell:cmd_parameter` 경로 존재

다른 module과의 관계:

- `sensitive_path_probe`: path probe를 context-only summary로 보존하는 경계
- `file_disclosure_hints`: wrapper/resource 기반 file exposure 시도 경계
- `traversal_cmdi_hints`: command-like token 경계와 일부 겹침 가능
- `mixed_baseline_scanner`: benign/scanner 혼합 문맥을 context-only로 보존

기존 fixture/expected 확인:

- 존재: `l3_ssti_webshell_context` (webshell path + cmd query 결합 케이스)
- 부족: `phpunit eval-stdin`, `cgi-bin admin`, `wso.php`, `c99.php`를 직접 분리 검증하는 fixture
- 부족: benign admin/static baseline을 webshell/admin probe와 같이 둔 과승격 억제 fixture

이미 있는 coverage:

- webshell path + command-like query의 최소 1개 고신호 candidate 보존
- `l3:webshell_probe` 및 `webshell:*` hint 보존

부족한 coverage:

- admin tool probe family(`phpunit`, `cgi-bin`) 분리 확인
- known shell filename family(`wso.php`, `c99.php`) 분리 확인
- benign baseline 동시 배치 시 false positive 억제 확인

## 3. fixture 후보

### 3.1 direct webshell path probe

- `GET /wso.php`
- `GET /c99.php`
- `GET /shell.php`

의도:

- known shell filename 계열의 path probe를 개별적으로 검증한다.

### 3.2 admin tool probe

- `GET /vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php`
- `GET /cgi-bin/admin.cgi`

의도:

- admin/tool style path를 webshell 계열 후보와 구분해 검증한다.

### 3.3 command-like query endpoint

- `GET /cmd.php?cmd=id`
- `GET /shell.php?exec=whoami`

의도:

- path + command-like query 결합 시 후보 보존 강도를 확인한다.

### 3.4 benign baseline

- `GET /admin/help`
- `GET /static/shell-icon.png`
- `GET /assets/file-manager-guide.png`

의도:

- 문자열 유사성만으로 candidate 과승격이 일어나지 않는지 확인한다.

## 4. 후보별 expected 검증 포인트

각 fixture 공통 체크:

- suspicious webshell/admin probe candidate 또는 context 보존 여부
- `l3:webshell_probe` 또는 webshell/admin/tool 관련 hint 확인 여부
- benign baseline이 `analysis_candidates`로 과승격되지 않는지
- Stage2 report input에 candidate/context가 유지되는지
- 성공 단정 문구가 없는지
- `status_code=200`/`response_body_bytes`만으로 성공 확정하지 않는지

fixture family별 최소 체크:

- direct webshell path probe: `webshell:script_filename` 및 known shell name 계열 hint 확인
- admin tool probe: admin/tool probe candidate 또는 context 분류 유지 확인
- command-like query endpoint: `webshell:cmd_parameter`와 path signal 결합 보존 확인
- benign baseline: filtered/context baseline으로 남고 공격 candidate 과승격 없음 확인

## 5. candidate vs context-only 기준

- webshell-like path + command-like query 결합은 `analysis_candidate` 가능
- 단순 `/shell.php` 반복 probe는 context-only 또는 `sensitive_path_probe` summary 가능
- `phpunit eval-stdin` path는 admin/tool probe candidate 가능
- benign static/admin help path는 filtered/context baseline
- `status=200`을 webshell 존재나 execution 성공 근거로 사용하지 않음

## 6. 기존 module 확장 여부

검토 포인트:

- `l3_hints.py` 확장으로 충분한지 우선 확인
- `sensitive_path_probe` category 확장이 필요한지 검토
- `traversal_cmdi_hints`와 command-like query 처리를 일부 공유할지 검토
- `file_disclosure_hints`와 겹침 여부는 경계 점검 수준으로 유지
- 새 module 생성은 보류

## 7. Stage dry-run regression 추가 여부

선택지:

- prepare regression만 추가
- prepare + stage dry-run regression 동시 추가
- 필요 시 actual LLM spot check 수행

권장:

- 1차는 `prepare + stage dry-run regression` 동시 추가
- actual LLM spot check는 필수는 아니지만 wording drift 확인 목적 1~2건 권장

## 8. 권장 1차 fixture

추천:

- `l3_webshell_admin_tool_probe_context` (완료)

후순위:

- `l3_webshell_command_query_context`

우선순위 이유:

- 현재 부족 구간이 admin tool family(`phpunit`, `cgi-bin`)라서 1차 후보로 적합
- command-query 계열은 기존 `l3_ssti_webshell_context`와 일부 중복되어 2차 분리 후보로 적합
- command-like query는 traversal/CMDI와 의미 경계가 더 민감하므로 별도 경계 검토 후 진행이 안전함

## 9. 금지 wording

금지 표현:

- webshell exists
- shell uploaded
- command executed
- RCE succeeded
- attacker gained shell
- server compromised
- exploit success
- upload succeeded

허용 표현:

- webshell-like path probe
- admin tool probe
- command-like query parameter observed
- requires manual review
- Apache logs alone do not confirm execution or compromise

## 10. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- 권장 1차 후보였던 `l3_webshell_admin_tool_probe_context`는 완료되었다.
- 구성된 fixture는 direct webshell path(`/wso.php`, `/c99.php`) + admin tool probe(`/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php`) + benign baseline(`/admin/help`, `/static/shell-icon.png`)를 포함한다.
- expected 고정 기준(후보 3건 보존, benign 과승격 억제, Stage1/Stage2 입력 힌트 보존, success wording 금지)을 만족하는 회귀 케이스로 유지한다.
- fixture 추가 전 확인할 것:
  - existing `l3_ssti_webshell_context`와 중복되지 않는 최소 샘플 구성
  - benign baseline 동시 배치로 과승격 억제 검증
  - Stage2 wording에서 성공 단정 금지 표현 유지
- 다음 구현 후보는 `l3_webshell_command_query_context`를 유지하되 traversal/CMDI 경계 검토 후 진행한다.
