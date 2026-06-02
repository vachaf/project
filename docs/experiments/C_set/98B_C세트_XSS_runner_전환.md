# 98B_C세트_XSS_runner_전환

- 작성 기준일: 2026-05-03
- 문서 역할: 기존 curl 기반 C세트 XSS 실험을 Python runner로 전환한 범위와 해석 원칙을 정리
- docs-side experiment summary: [../../reviews/99_lab_experiment_set_summaries.md](../../reviews/99_lab_experiment_set_summaries.md)
- runner path status: runner code는 `scripts/lab_runners/c_set` 아래의 current path로 이관됐다. `lab/c_set/README.md`는 legacy lab-side runner note로 남아 있다.

## 목적

`scripts/lab_runners/c_set/run_c_xss_scenarios.py`를 추가해 기존 curl 기반 C세트 XSS 실험을 Python runner로 전환했다.

이 runner는 공격 성공 검증 도구가 아니다. 승인된 로컬 실험 환경에서 XSS 관련 HTTP 요청을 표준화된 형식으로 생성하고, 실행 계획과 결과 메타데이터를 남기는 Apache-log-oriented 실험 harness다.

runner의 목적은 Apache 로그에 남을 request target/query 구조를 재현하는 것이다. 브라우저에서의 script execution, DOM 반영, 쿠키 탈취 성공 여부는 이 runner의 책임 범위가 아니다.

## 시나리오 요약

| scenario | scenario_id | 기대 관찰 | 해석 제한 |
|---|---|---|---|
| `basic_script` | `C-XSS-01` | decoded request target에서 script tag와 `alert()` 호출 관찰 | no browser execution |
| `url_encoded` | `C-XSS-02` | encoded payload 내부 `document.cookie` 토큰 관찰 | no cookie theft success |
| `html_entity` | `C-XSS-03` | HTML entity encoded script tag 복원 가능성 관찰 | no browser rendering confirmation |
| `attribute_event` | `C-XSS-04` | `onerror` 계열 event-handler-like attribute injection 관찰 | no interaction or DOM execution inference |
| `fp_bait` | `C-XSS-05` | `tutorial` / `onerror` / `javascript` 키워드가 포함된 자연어 query 관찰 | false positive review required |

## Prepare Pipeline 기대 hint

prepare pipeline에서는 아래와 같은 hint가 기대된다.

- `xss:script_tag`
- `xss:alert_call`
- `encoding:url_encoded_payload`
- `encoding:html_entity_decoded_xss`
- `xss:event_handler`
- `false_positive_review` 또는 `filtered/context` 성격의 표시 for `fp_bait`

## 해석 원칙

다음 단정은 금지한다.

- no browser execution
- no cookie theft success
- no DOM reflection confirmation
- response body raw content not inspected

추가 해석 제한:

- `status_code=200`만으로 XSS 성공을 단정하지 않는다.
- `response_body_bytes`만으로 payload reflection 또는 script execution을 단정하지 않는다.
- runner는 response body 원문을 저장하지 않으며, 실제 실행 시에도 body 길이만 기록한다.
- fp_bait는 XSS 관련 키워드를 포함하더라도 높은 확신의 공격으로 자동 승격하면 안 된다.

## 산출물

runner는 항상 아래 파일을 생성한다.

- `execution_plan.json`
- `execution_plan.md`
- `run_metadata.json`

실제 실행 시에는 아래 파일이 추가된다.

- `request_results.jsonl`
- `run_summary.md`

이 구조로 C세트도 F세트/G세트와 유사한 Python runner 운영 패턴에 편입되지만, 이번 전환은 C세트 신규 runner 추가에만 한정된다. 기존 F세트 runner, prepare pipeline, Stage1, Stage2, fixture/expected는 수정하지 않는다.
