# 99 Lab Runner Migration Plan

- 문서 상태: design plan / lab runner migration
- 적용 범위: `lab/a_set` ~ `lab/h_set` runner code
- 비범위: lab 산출물 삭제, `.gitignore` 수정, observability script 경로 변경

## 1. 배경

`lab/`에는 generated artifact와 실행 runner code가 함께 남아 있다.

현재 `lab/*_산출물` 아래의 JSON, JSONL, log 계열 파일은 장기적으로 ignore, untrack, remove 후보가 많다. 그러나 `lab/a_set` ~ `lab/h_set` 아래의 `.py` 파일은 산출물이 아니라 재현 가능한 실험 traffic을 만드는 실행 harness이므로 단순 삭제나 ignore 대상이 아니다.

runner를 `scripts/lab_runners/`로 옮기면 다음 경계를 명확히 할 수 있다.

- 실행 code는 `scripts/` 아래에 둔다.
- generated artifact와 legacy comparison output은 `lab/` 아래에 둔다.
- 후속 `.gitignore` 정리에서 lab artifact와 runner code를 혼동하지 않는다.
- `docs/experiments`의 실행 예시도 runner path와 output path를 분리해 설명할 수 있다.

`lab/observability`는 아직 여러 observability script의 기본 input/output 위치로 남아 있다. 따라서 이 문서의 migration 범위에는 포함하지 않는다.

## 2. 대상 Runner Inventory

권장 proposed path는 set별 하위 디렉터리를 유지하는 구조다.

```text
scripts/lab_runners/{a_set,b_set,c_set,d_set,e_set,f_set,g_set,h_set}/...
```

이 구조를 권장하는 이유는 다음이다.

- 기존 set 구분을 유지한다.
- `docs/experiments` 문서와 current/proposed path mapping이 쉽다.
- 산출물인 `lab/`과 실행 code인 `scripts/`가 분리된다.
- 후속 `.gitignore`에서 lab artifact 정리가 쉬워진다.

| set | current path | proposed path | purpose | safety guardrail | output behavior | migration risk |
| --- | --- | --- | --- | --- | --- | --- |
| A | `lab/a_set/run_a_baseline_auth_scenarios.py` | `scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py` | baseline browsing/search, auth failure, POST body visibility, protected resource baseline | public/general target은 기본 거부, dry-run/print-plan 지원, local/private/test 중심 | `--out` 아래 plan/metadata, 실행 시 results/summary 생성. response body 원문 저장 없음 | low |
| B | `lab/b_set/run_b_r1_sqli_scenarios.py` | `scripts/lab_runners/b_set/run_b_r1_sqli_scenarios.py` | SQLi R1 auth/union/error/path probe | public/general target 기본 거부, optional/destructive scenario는 `--include-optional` 필요 | `--out` 아래 plan/metadata/results/summary. body length만 기록 | low |
| B | `lab/b_set/run_b_r2_sqli_scenarios.py` | `scripts/lab_runners/b_set/run_b_r2_sqli_scenarios.py` | SQLi R2 boolean/time/evasion/chain/FP bait | public/general target 기본 거부, optional/high-load scenario는 `--include-optional` 필요 | `--out` 아래 plan/metadata/results/summary. response body 원문 저장 없음 | low |
| C | `lab/c_set/run_c_xss_scenarios.py` | `scripts/lab_runners/c_set/run_c_xss_scenarios.py` | XSS request target/query 재현과 FP bait | public/general target 기본 거부, dry-run/print-plan 지원 | `--out` 아래 plan/metadata/results/summary. body length만 기록 | low |
| D | `lab/d_set/run_d_set_scenarios.py` | `scripts/lab_runners/d_set/run_d_set_scenarios.py` | traversal, HPP, directory probing | public/general target 기본 거부, raw malformed/protocol은 G-set 범위로 분리 | `--out` 아래 plan/metadata/results/summary. response body 원문 저장 없음 | low |
| E | `lab/e_set/run_e_r2_php_wrapper_scenarios.py` | `scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py` | PHP wrapper, config path, file disclosure intent | public/general target 기본 거부, OpenCart/PHP lab 전제 | `--out` 아래 plan/metadata/results/summary. body length만 기록 | low |
| E | `lab/e_set/run_e_r3_search_scenarios.py` | `scripts/lab_runners/e_set/run_e_r3_search_scenarios.py` | search baseline, SQLi, XSS, HTML entity XSS | public/general target 기본 거부, dry-run/print-plan 지원 | `--out` 아래 plan/metadata/results/summary. response body 원문 저장 없음 | low |
| F | `lab/f_set/run_f_r2a_auth_scenarios.py` | `scripts/lab_runners/f_set/run_f_r2a_auth_scenarios.py` | low-and-slow auth failures, interleaved browse/auth, 200 baseline | public IP 차단. hostname target은 경고 후 operator 책임으로 제한 | `--out` 아래 plan/metadata/results/summary. response body length만 기록 | medium |
| F | `lab/f_set/run_f_r2b_response_delta.py` | `scripts/lab_runners/f_set/run_f_r2b_response_delta.py` | auth response delta, existing/nonexistent/lockout-like failures | public/general target 기본 거부, auth success/account/lockout inference 금지 | `--out` 아래 plan/metadata/results/summary. response body length만 기록 | low |
| G | `lab/g_set/run_g_r1_method_probe.py` | `scripts/lab_runners/g_set/run_g_r1_method_probe.py` | OPTIONS/TRACE/PUT/DELETE/HEAD/GET method probing | public/general target 기본 거부, method success 단정 금지 | `--out` 아래 plan/metadata/results/summary. raw body 저장 없음 | low |
| G | `lab/g_set/run_g_r2_protocol_anomaly.py` | `scripts/lab_runners/g_set/run_g_r2_protocol_anomaly.py` | protocol/malformed request-like behavior, raw socket HTTP | public/general target 기본 거부, `http://` target만 지원, raw socket 주의 필요 | `--out` 아래 plan/metadata/results/summary. raw request/response body 원문 저장 없음 | medium |
| G | `lab/g_set/run_g_r3_baseline.py` | `scripts/lab_runners/g_set/run_g_r3_baseline.py` | method/protocol baseline and FP bait | public/general target 기본 거부, CORS/method vulnerability 단정 금지 | `--out` 아래 plan/metadata/results/summary. raw body 저장 없음 | low |
| H | `lab/h_set/run_h_r1_static_baseline.py` | `scripts/lab_runners/h_set/run_h_r1_static_baseline.py` | static/health/normal browse baseline | public/general target 기본 거부, static existence 단정 금지 | `--out` 아래 plan/metadata/results/summary. response body 원문 저장 없음 | low |
| H | `lab/h_set/run_h_r2_crawler_baseline.py` | `scripts/lab_runners/h_set/run_h_r2_crawler_baseline.py` | crawler-like UA, robots/sitemap/product/category baseline | public/general target 기본 거부, crawler authenticity 단정 금지 | `--out` 아래 plan/metadata/results/summary. response body 원문 저장 없음 | low |
| H | `lab/h_set/run_h_r3_scanner_low_signal.py` | `scripts/lab_runners/h_set/run_h_r3_scanner_low_signal.py` | scanner-like sensitive path low-signal runner | public/general target 기본 거부, app/file exposure success 단정 금지 | `--out` 아래 plan/metadata/results/summary. body bytes discarded only | low |
| H | `lab/h_set/run_h_r4_mixed_baseline_scanner.py` | `scripts/lab_runners/h_set/run_h_r4_mixed_baseline_scanner.py` | mixed benign/static/crawler/scanner context | public/general target 기본 거부, mixed chain success 단정 금지 | `--out` 아래 plan/metadata/results/summary. response body 원문 저장 없음 | low |

## 3. Safety Guardrail 유지 기준

runner migration은 파일 위치 변경이어야 하며 safety behavior를 바꾸면 안 된다.

유지해야 할 기준은 다음이다.

- public/general target은 기본 차단하거나 명시적 override를 요구한다.
- 기본 실행 대상은 local/private/test target 중심으로 유지한다.
- `--dry-run` 또는 `--print-plan`은 실제 HTTP 요청을 보내지 않는 계획 검토 수단으로 유지한다.
- response body 원문은 저장하지 않는다.
- request body 원문, 특히 POST body는 Apache logs-only 분석 pipeline에서 보이지 않는 execution-only input으로 유지한다.
- destructive/high-load/optional scenario는 명시 flag를 요구한다.
- G R2 raw socket runner는 `http://` 전용 raw socket behavior와 malformed/protocol anomaly 주의를 별도 표시한다.
- auth runner는 login success, account takeover, user enumeration success, lockout 발동을 단정하지 않는 실험 harness임을 유지한다.
- SQLi, XSS, traversal, file disclosure, method/protocol anomaly, scanner-like path는 Apache logs-only evidence boundary를 따른다.

관련 canonical boundary는 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

## 4. Docs 수정 범위

4C-2 migration PR에서는 runner path와 output path를 분리해서 갱신한다.

| docs path | current reference | migration update |
| --- | --- | --- |
| `docs/experiments/README.md` | `lab/a_set`~`lab/h_set` runner 경로를 legacy path로 설명 | runner code는 `scripts/lab_runners/{set}/`, lab output은 legacy/generated artifact path로 분리 설명 |
| `docs/experiments/B_set/*.md` | `lab/b_set` runner path와 runner 전환 설명 | `scripts/lab_runners/b_set/*.py`로 실행 예시 갱신. old path는 historical path로만 남김 |
| `docs/experiments/C_set/*.md` | `lab/c_set` runner path와 runner 전환 설명 | `scripts/lab_runners/c_set/*.py`로 갱신 |
| `docs/experiments/D_set/*.md` | `lab/d_set` runner path와 runner 전환 설명 | `scripts/lab_runners/d_set/*.py`로 갱신 |
| `docs/experiments/E_set/*.md` | `lab/e_set` runner path와 runner 전환 설명 | `scripts/lab_runners/e_set/*.py`로 갱신 |
| `docs/experiments/F_set/*.md` | `python3 lab/f_set/*.py` 실행 예시 | `python3 scripts/lab_runners/f_set/*.py`로 갱신 |
| `docs/experiments/G_set/*.md` | `python3 lab/g_set/*.py`, current/legacy lab runner path | `python3 scripts/lab_runners/g_set/*.py`로 갱신. G R2 raw socket 주의 유지 |
| `docs/experiments/H_set/*.md` | `python3 lab/h_set/*.py`, current/legacy lab runner path | `python3 scripts/lab_runners/h_set/*.py`로 갱신 |
| `docs/reviews/99_lab_experiment_set_summaries.md` | runner 위치가 `../../lab/*_set`로 기록됨 | current/historical runner path와 proposed path를 혼동하지 않게 갱신 |

수정 기준은 다음이다.

- `python3 lab/*_set/*.py`는 `python3 scripts/lab_runners/*_set/*.py`로 전환한다.
- old path는 필요한 경우 historical/legacy path로만 남긴다.
- `lab/*_산출물` output path는 legacy artifact/output 예시로 계속 남길 수 있다.
- runner path와 output path를 같은 종류의 path처럼 설명하지 않는다.

## 5. 테스트 / Smoke 기준

4C-2 migration PR에서는 최소한 Python syntax와 기존 regression boundary를 확인한다.

기본 compile check:

```bash
python3 -m py_compile \
  scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py \
  scripts/lab_runners/b_set/run_b_r1_sqli_scenarios.py \
  scripts/lab_runners/b_set/run_b_r2_sqli_scenarios.py \
  scripts/lab_runners/c_set/run_c_xss_scenarios.py \
  scripts/lab_runners/d_set/run_d_set_scenarios.py \
  scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py \
  scripts/lab_runners/e_set/run_e_r3_search_scenarios.py \
  scripts/lab_runners/f_set/run_f_r2a_auth_scenarios.py \
  scripts/lab_runners/f_set/run_f_r2b_response_delta.py \
  scripts/lab_runners/g_set/run_g_r1_method_probe.py \
  scripts/lab_runners/g_set/run_g_r2_protocol_anomaly.py \
  scripts/lab_runners/g_set/run_g_r3_baseline.py \
  scripts/lab_runners/h_set/run_h_r1_static_baseline.py \
  scripts/lab_runners/h_set/run_h_r2_crawler_baseline.py \
  scripts/lab_runners/h_set/run_h_r3_scanner_low_signal.py \
  scripts/lab_runners/h_set/run_h_r4_mixed_baseline_scanner.py
```

Regression check:

```bash
python3 -m pytest -q tests/test_cleanup_outputs.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

Optional runner smoke:

- 각 runner의 `--help`를 실행한다.
- dry-run 옵션이 있는 runner는 승인된 localhost/private lab target과 임시 output directory로 dry-run을 확인한다.
- dry-run 옵션이 없는 runner가 생기면 우선 `--help`와 `py_compile`까지만 확인한다.
- 실제 HTTP 요청이 발생하는 smoke는 localhost/private lab 환경에서 별도 수행한다.

주의:

- migration PR에서 외부/public target으로 runner를 실행하지 않는다.
- response body 원문 저장 여부가 바뀌면 안 된다.
- `scripts/check_prepare_regression.py`와 `scripts/check_stage_dryrun_regression.py`는 기본 fixture를 `tests/fixtures/prepare_regression`에서 읽으므로 runner path 이동과 직접 충돌하지 않아야 한다.

## 6. cleanup_outputs 영향

현재 `scripts/cleanup_outputs.py`는 `PROTECTED_PATHS`에 `lab` 전체를 둔다. `tests/test_cleanup_outputs.py`도 lab directory와 repo root lab child가 보호되는지 확인한다.

runner 이동 직후에도 다음 이유로 `lab` 보호를 즉시 제거하지 않는다.

- `lab/observability`가 아직 observability scripts의 기본 input/output 위치다.
- legacy lab artifact와 comparison output이 남아 있다.
- lab artifact removal safety policy는 runner migration과 별도 판단이 필요하다.

따라서 cleanup policy 변경은 PR 4C-3에서 별도 검토한다. 4C-2 runner migration PR에서는 `cleanup_outputs.py`와 `tests/test_cleanup_outputs.py`의 lab 보호 정책을 유지한다.

## 7. .gitignore / lab artifact 정리 영향

runner 이동은 `/lab/` 전체 ignore를 즉시 가능하게 만들지 않는다.

남는 제약은 다음이다.

- `lab/observability`와 legacy artifact가 남아 있다.
- tracked lab 파일에는 `.gitignore`가 소급 적용되지 않는다.
- `lab/*_산출물` JSON/JSONL/log untrack 또는 remove 여부는 별도 PR에서 결정해야 한다.

보수적 전략은 우선 `lab/*_산출물` JSON/JSONL/log 중심으로 ignore/remove 후보를 다루는 것이다. artifact untrack/remove와 `.gitignore` 정리는 PR 4C-4 또는 별도 PR에서 수행한다.

## 8. 실제 Migration PR 계획

PR 4C-2:

- `lab/*_set` runner `.py` 파일을 `scripts/lab_runners/*_set/`로 이동한다.
- set별 README를 같이 옮길지, `docs/experiments`로 흡수할지 결정한다.
- `docs/experiments` 실행 예시를 갱신한다.
- `docs/reviews/99_lab_experiment_set_summaries.md` runner path를 갱신한다.
- `py_compile`을 수행한다.
- regression checker를 수행한다.
- `cleanup_outputs` policy는 유지한다.

PR 4C-3:

- `cleanup_outputs` protected path 정책을 재검토한다.
- lab artifact removal safety를 검토한다.
- `tests/test_cleanup_outputs.py` 갱신 여부를 판단한다.

PR 4C-4:

- lab artifact JSON/JSONL/log untrack/remove 후보를 처리한다.
- `.gitignore`를 정리한다.

## 9. 최종 결론

```text
runner 이동은 가능하지만, 설계 문서 작성 후 별도 migration PR에서 수행한다.
권장 위치는 scripts/lab_runners/{set}/ 이다.
migration PR에서는 runner code 이동과 docs 실행 예시 갱신까지만 수행하고,
lab artifact 삭제, .gitignore 변경, cleanup_outputs policy 변경은 분리한다.
```
