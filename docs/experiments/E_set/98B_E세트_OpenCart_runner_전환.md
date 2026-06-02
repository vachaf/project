# 98B_E세트_OpenCart_runner_전환

- 작성 기준일: 2026-05-03
- 문서 역할: 기존 curl 기반 E세트 OpenCart 실험을 Python runner로 전환한 범위와 해석 원칙을 정리
- docs-side experiment summary: [../../reviews/99_lab_experiment_set_summaries.md](../../reviews/99_lab_experiment_set_summaries.md)
- runner path status: runner code는 `scripts/lab_runners/e_set` 아래의 current path로 이관됐다. `lab/e_set/README.md`는 legacy lab-side runner note로 남아 있다.

## 목적

`scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py`와 `scripts/lab_runners/e_set/run_e_r3_search_scenarios.py`를 추가해 기존 curl 기반 E세트 OpenCart/PHP 실험을 Python runner로 전환했다.

이 runner들은 공격 성공 검증 도구가 아니다. 승인된 로컬 OpenCart/PHP 실험 환경에서 request target/query 구조와 실행 메타데이터를 표준화된 형식으로 생성하고 기록하는 Apache-log-oriented 실험 harness다.

## 두 runner로 나눈 이유

R2/R2B와 R3/R3B는 평가 대상과 해석 기준이 다르다.

- R2/R2B는 `php://filter`, `convert.base64-encode`, `resource=` 같은 PHP wrapper/file disclosure intent와 direct config path probe를 다룬다.
- R3/R3B는 일반화된 `/search?q=...` 구조에서 normal baseline, SQLi, XSS, HTML entity XSS를 다룬다.

따라서 wrapper/file disclosure 계열과 search baseline/attack 비교 계열을 분리해 운영하는 편이 plan 검토, export 관리, prepare 결과 비교에 더 적합하다.

## E R2/R2B 기대 prepare 동작

prepare 단계에서는 아래와 같은 보존이 기대된다.

- php wrapper candidate 보존
- `file_disclosure:php_filter_wrapper`
- `file_disclosure:base64_source_intent`
- `file_disclosure:resource_parameter`
- direct config path는 wrapper처럼 과승격 금지

즉, `php://filter/convert.base64-encode/resource=...` 계열은 file/source disclosure intent로 candidate 또는 강한 context로 남는 것이 기대되지만, `/config.php`, `/admin/config.php` 단발 direct probe는 low-signal 또는 context-only 성격이 더 적절하다.

## E R3/R3B 기대 prepare 동작

prepare 단계에서는 아래와 같은 보존이 기대된다.

- normal search baseline은 benign/reference baseline
- SQLi/XSS search payload는 candidate
- HTML entity XSS decode
- normal search에 `dir_probe:*` 없음

즉, `q=apple`, `q=phone` 같은 정상 검색은 baseline/supporting 성격으로 남아야 하고, `x')) OR 1=1 --`, `<script>alert(1)</script>`, `&#x3C;script...` 계열은 SQLi/XSS candidate로 유지되는 것이 기대된다.

## 성공 단정 금지

다음 단정은 금지한다.

- no source disclosure confirmation
- no config exposure confirmation
- no SQLi result confirmation
- no XSS browser execution
- response body raw content not inspected

추가 해석 제한:

- `status_code=200`, `text/html`, `response_body_bytes`만으로 source disclosure, config exposure, SQLi success, XSS execution을 단정하지 않는다.
- R2/R2B는 wrapper intent를 기록하는 실험이지 실제 PHP wrapper 처리 성공 여부를 증명하는 도구가 아니다.
- R3/R3B는 search payload가 Apache 로그에 어떻게 남는지와 baseline이 어떻게 분리되는지를 보는 실험이지 DB result count나 browser render를 확인하는 도구가 아니다.
- response body 원문은 저장하지 않고 body 길이만 기록한다.

## 산출물

두 runner 모두 항상 아래 파일을 생성한다.

- `execution_plan.json`
- `execution_plan.md`
- `run_metadata.json`

실제 실행 시에는 아래 파일이 추가된다.

- `request_results.jsonl`
- `run_summary.md`

이번 전환은 E세트 신규 runner 추가에만 한정된다. `src/prepare_llm_input.py`, Stage1, Stage2, pipeline core, fixture/expected는 수정하지 않는다.
