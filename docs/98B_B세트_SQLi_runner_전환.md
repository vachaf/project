# 98B_B세트_SQLi_runner_전환

- 작성 기준일: 2026-05-03
- 문서 역할: 기존 curl 기반 B세트 SQLi 비교 실험을 Python runner로 전환한 범위와 해석 원칙을 정리

## 목적

`lab/b_set/run_b_r1_sqli_scenarios.py`와 `lab/b_set/run_b_r2_sqli_scenarios.py`를 추가해 기존 curl 기반 B세트 SQLi 실험을 Python runner로 전환했다.

이 runner들은 SQLi 성공 검증 도구가 아니다. 승인된 로컬 실험 환경에서 SQLi 관련 HTTP 요청을 표준화된 형식으로 생성하고, 실행 계획과 결과 메타데이터를 남기는 Apache-log-oriented 실험 harness다.

runner의 목적은 Apache 로그에 남을 request target/query 구조와 실행 메타데이터를 재현하는 것이다. DB 결과, row count, credential dump, auth bypass 성공 여부는 이 runner의 책임 범위가 아니다.

## R1 / R2 역할

| runner | 범위 | 주요 그룹 | 해석 주의 |
|---|---|---|---|
| `run_b_r1_sqli_scenarios.py` | Round 1 | Auth Bypass / Union-based / Error-based | POST body는 Apache baseline에서 보이지 않으므로 body 기반 auth bypass 성공을 단정하지 않음 |
| `run_b_r2_sqli_scenarios.py` | Round 2 | Boolean Blind / Time-based / Evasion / Temporal Chain / FP bait | Boolean은 byte delta를 간접 증거로만 보고, time-based는 Apache `duration_us` / `ttfb_us`를 기준으로 봄 |

## 시나리오 그룹과 해석 제한

R1 그룹:

- `auth`: `B-R1-01`~`B-R1-03`
- `union`: `B-R1-05`~`B-R1-07`
- `error`: `B-R1-08`~`B-R1-11`
- `B-R1-04`는 destructive optional scenario이며 `--include-optional` 없이는 선택할 수 없다.

R2 그룹:

- `boolean`: `B-R2A-00`~`B-R2A-04`
- `time`: `B-R2B-00`~`B-R2B-02`
- `evasion`: `B-R2B-E01`~`B-R2B-E05`
- `chain`: `B-R2B-C01`~`B-R2B-C10`
- `fp`: `B-R2B-F01`~`B-R2B-F03`
- `B-R2A-05`, `B-R2A-06`, `B-R2B-03`은 optional legacy/high-load scenario이며 `--include-optional` 없이는 선택할 수 없다.

공통 해석 제한:

- response body 원문은 저장하지 않고 body 길이만 기록한다.
- `status_code=200`, `response_body_bytes`, `duration_ms`만으로 SQLi 성공을 단정하지 않는다.
- POST body payload는 execution-only 입력일 뿐이며 Apache baseline에서 직접 보이지 않는다.
- time-based SQLi는 runner `duration_ms`가 아니라 Apache `duration_us` / `ttfb_us` delta로 해석해야 한다.

## Prepare Pipeline 기대 hint

prepare pipeline에서는 아래와 같은 hint가 기대된다.

- `sqli:quote_termination`
- `sqli:parenthesis_termination`
- `sqli:boolean_true_condition`
- `sqli:comment_sequence`
- `encoding:decoded_depth_2`
- `encoding:double_decoded_sqli`
- `possible_false_positive_sql_keyword_search` 또는 동등한 FP bait 표식

또한 문맥상 아래 성격의 보존이 기대된다.

- Boolean TRUE/FALSE pair 비교 문맥
- time-based ladder와 baseline 비교 문맥
- evasion payload의 decoded/normalized 의미 보존
- temporal chain의 단계적 sequence 보존
- educational SQL keyword search의 false-positive control 보존

## 성공 단정 금지

다음 단정은 금지한다.

- no DB data exfiltration confirmation
- no auth bypass confirmation from 200 alone
- no response body content inspection
- no time-based success without Apache duration_us / ttfb_us delta

추가 해석 제한:

- R1 POST login 시나리오는 Apache baseline에서 raw POST body가 보이지 않으므로 body payload 기반 성공/실패를 단정하지 않는다.
- UNION / schema / credential extraction payload는 query_string에서 intent를 관찰할 수 있어도 실제 데이터 내용 유출은 확정하지 않는다.
- Boolean TRUE/FALSE는 `response_body_bytes` 차이를 간접 물리 증거로만 본다.
- Time-based는 runner `duration_ms`를 참고값으로만 기록하고, 판단 기준은 Apache `duration_us` / `ttfb_us`에 둔다.
- FP bait는 SQL 키워드가 있어도 자연어 문맥이 강하면 benign 또는 false-positive control로 남겨야 한다.

## 산출물

두 runner 모두 항상 아래 파일을 생성한다.

- `execution_plan.json`
- `execution_plan.md`
- `run_metadata.json`

실제 실행 시에는 아래 파일이 추가된다.

- `request_results.jsonl`
- `run_summary.md`

`run_summary.md`에서는 Boolean pair가 포함된 경우 TRUE/FALSE byte 비교 표를 남기고, time track이 포함된 경우 runner `duration_ms`는 참고값일 뿐 Apache `duration_us` / `ttfb_us`가 기준이라는 문구를 남긴다.

이번 전환은 B세트 신규 runner 추가에만 한정된다. `src/prepare_llm_input.py`, Stage1, Stage2, pipeline core, fixture/expected는 수정하지 않는다.
