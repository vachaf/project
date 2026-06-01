# 98B_D세트_runner_전환

- 작성 기준일: 2026-05-03
- 문서 역할: 기존 curl 기반 D세트 비교 실험을 Python runner로 전환한 범위와 해석 원칙을 정리
- docs-side experiment summary: [../../reviews/99_lab_experiment_set_summaries.md](../../reviews/99_lab_experiment_set_summaries.md)
- runner path status: 현재 runner는 아직 `lab/d_set` 아래의 current/legacy lab runner path를 사용한다. 경로 변경이나 `scripts/tools` 이관은 후속 PR에서 검토한다.

## 목적

`lab/d_set/run_d_set_scenarios.py`를 추가해 기존 curl 기반 D세트 Path Traversal / HPP / Directory Probing 실험을 Python runner로 전환했다.

이 runner는 공격 성공 검증 도구가 아니다. 승인된 로컬 실험 환경에서 Traversal / HPP / Directory Probing 관련 HTTP 요청을 표준화된 형식으로 생성하고, 실행 계획과 결과 메타데이터를 남기는 Apache-log-oriented 실험 harness다.

runner의 목적은 Apache 로그에 남을 request target/query 구조를 재현하는 것이다. 파일 읽기 성공, 디렉터리 노출, HPP 서버측 처리 결과는 이 runner의 책임 범위가 아니다.

## Round별 요약

| round | scenario_id | 기대 관찰 | 해석 제한 |
|---|---|---|---|
| R1 Traversal | `D-R1-01`~`D-R1-05` | `../`, encoded traversal, `%00` suffix, `/etc/passwd`, `php://filter` 같은 민감 경로/우회 의도 관찰 | no file read success, no env/config disclosure confirmation, PHP wrapper는 PHP target only |
| R2 HPP | `D-R2-01`~`D-R2-04` | duplicate parameter, `hpp_detected`, `hpp_param_names`, HPP+SQLi/XSS coupling, POST body visibility limitation 관찰 | no server-side chosen value confirmation, no browser execution confirmation, no POST body HPP success confirmation |
| R3 Probing | `D-R3-01`~`D-R3-09` | `.git`, `.env`, `config.php`, `backup.zip`, `/server-status`, `/admin` 계열 path guessing과 burst probing sequence 관찰 | no directory/file exposure confirmation, single admin path is not high severity, probing은 sequence context 중심 |

## Prepare Pipeline 기대 결과

prepare pipeline에서는 아래와 같은 결과가 기대된다.

- traversal candidate/context
- HPP 관련 `hpp_detected` / `hpp_param_names`
- HPP + SQLi/XSS coupling 문맥
- probing_sequence_summaries
- benign duplicate HPP는 high-confidence attack 아님
- single admin path는 high severity 아님

## 성공 단정 금지

다음 단정은 금지한다.

- no file read success
- no directory/file exposure confirmation
- no HPP server-side value selection confirmation
- no POST body HPP success confirmation
- response body raw content not inspected

추가 해석 제한:

- `status_code=200/403/404`만으로 성공, 차단, 노출을 단정하지 않는다.
- runner는 response body 원문을 저장하지 않으며, 실제 실행 시에도 body 길이만 기록한다.
- POST body HPP는 Apache baseline에서 raw body가 보이지 않는다는 한계를 반드시 병기한다.
- benign duplicate HPP는 공격 payload가 없으면 review/context 수준으로 유지해야 한다.
- single `/admin` probe는 반복/burst 맥락이 없으면 high severity로 올리면 안 된다.

## urllib 한계

이번 runner는 Python 표준 라이브러리 `urllib.request`를 사용한다. 따라서 다음 한계를 문서와 execution plan에 명시했다.

- `urllib` may normalize dot-segment paths
- raw traversal validation must be done by checking Apache `raw_request_target`
- strict raw malformed/protocol tests belong to G-set raw socket runner

즉, D세트 runner는 traversal 의도를 재현하고 실행 메타데이터를 표준화하는 용도이며, raw malformed request 자체를 보존해 전송하는 도구는 아니다.

## 산출물

runner는 항상 아래 파일을 생성한다.

- `execution_plan.json`
- `execution_plan.md`
- `run_metadata.json`

실제 실행 시에는 아래 파일이 추가된다.

- `request_results.jsonl`
- `run_summary.md`

이번 전환은 D세트 신규 runner 추가에만 한정된다. `src/prepare_llm_input.py`, Stage1, Stage2, pipeline core, fixture/expected는 수정하지 않는다.
