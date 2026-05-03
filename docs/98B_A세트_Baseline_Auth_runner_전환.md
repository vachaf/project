# 98B_A세트_Baseline_Auth_runner_전환

- 작성 기준일: 2026-05-03
- 문서 역할: 기존 A세트 baseline/auth 흐름을 Python runner로 전환한 범위와 해석 원칙을 정리

## 목적

`lab/a_set/run_a_baseline_auth_scenarios.py`를 추가해 기존 A세트 baseline/auth 흐름을 Python runner로 전환했다.

이 runner는 로그인 성공 또는 우회 성공 검증 도구가 아니다. 승인된 로컬 실험 환경에서 baseline browsing/search, auth endpoint request, protected resource access 관련 HTTP 요청을 표준화된 형식으로 생성하고, 실행 계획과 결과 메타데이터를 남기는 Apache-log-oriented 실험 harness다.

## 그룹별 요약

| 그룹 | scenario_id | 기대 관찰 | 해석 제한 |
|---|---|---|---|
| baseline | `A-R1-01`~`A-R1-06` | home/products/search/detail/whoami의 정상 HTTP surface | benign baseline이며 공격 후보로 승격 금지 |
| auth | `A-R1-07`~`A-R1-11` | auth endpoint status/bytes/time surface, 단 POST body는 baseline에 보이지 않음 | single failure는 과장 금지, repeated failure는 auth behavior context 가능, 200도 auth success 확정 아님 |
| protected | `A-R1-12` | protected resource endpoint surface | authorization state는 Apache 로그만으로 확정 불가 |

## Prepare Pipeline 기대 결과

prepare pipeline에서는 아래와 같은 결과가 기대된다.

- baseline search/products/home은 benign/filtered/context
- single auth failure는 low/inconclusive/likely_false_positive
- repeated auth failure는 auth behavior context 가능
- auth bypass-like POST body SQLi는 POST body 미확인 한계로 보수적 해석
- normal login 200은 `auth_baseline_context` 또는 normal baseline 가능

핵심은 A세트가 공격 성공 검증이 아니라 baseline과 auth surface의 보수적 해석 기준을 확인하는 세트라는 점이다.

## 해석 원칙

- raw POST body는 Apache 로그 baseline에서 보이지 않는다.
- response body 원문은 저장하지 않는다.
- 로그인 성공, 인증 우회 성공, 계정 탈취, token issuance, session creation은 단정하지 않는다.
- `status_code=200`은 HTTP response observation일 뿐 인증 성공 확정이 아니다.
- `response_body_bytes`는 보조 지표일 뿐이다.

## 성공 단정 금지

다음 단정은 금지한다.

- no auth success confirmation
- no token issuance confirmation
- no auth bypass confirmation
- no account takeover
- response body raw content not inspected

추가 해석 제한:

- POST login 요청은 body payload가 보이지 않으므로 `email`, `password`, SQLi-like body 내용 자체를 Apache 로그 근거로 확인할 수 없다.
- `A-R1-10`은 SQLi 성공 검증이 아니라 POST body visibility limitation 확인용이다.
- `A-R1-11`의 200 가능성은 normal login response baseline일 뿐 token/session 확인을 의미하지 않는다.
- protected resource 접근은 auth state confirmation 없이 과장하면 안 된다.

## 산출물

runner는 항상 아래 파일을 생성한다.

- `execution_plan.json`
- `execution_plan.md`
- `run_metadata.json`

실제 실행 시에는 아래 파일이 추가된다.

- `request_results.jsonl`
- `run_summary.md`

이번 전환은 A세트 신규 runner 추가에만 한정된다. `src/prepare_llm_input.py`, Stage1, Stage2, pipeline core, fixture/expected는 수정하지 않는다.
