# 99 Lab Experiment Set Summaries

- 문서 상태: review / lab experiment set summary 이관 요약
- 기준 범위:
  - `../../lab/ABCDE_비교실험_요약.md`
  - `../../lab/04-24_A세트_산출물/**`
  - `../../lab/04-25_B세트*/**`
  - `../../lab/04-25_C세트_산출물/**`
  - `../../lab/04-26_D세트*/**`
  - `../../lab/04-26_*E세트*/**`
  - `../../lab/04-29_*E세트*/**`
  - `../../lab/04-30_*E세트*/**`
  - `../../lab/05-02_F세트*/**`
  - `../../lab/05-03_G세트*/**`
  - `../../lab/05-03_H세트*/**`
- 기준 원문:
  - `../../lab/ABCDE_비교실험_요약.md`
  - `../../lab/04-24_A세트_산출물/2026-04-24_A 세트 비교.md`
  - `../../lab/04-25_B세트R1_산출물/2026-04-25_B세트R1_비교.md`
  - `../../lab/04-25_B세트R2A_산출물/2026-04-25_B세트R2A_비교.md`
  - `../../lab/04-25_B세트R2B_산출물/2026-04-25_B세트R2B_비교.md`
  - `../../lab/04-25_C세트_산출물/04-25_C세트_비교.md`
  - `../../lab/04-26_D세트R1_산출물/2026-04-26_D세트R1_비교.md`
  - `../../lab/04-26_D세트R2_산출물/2026-04-26_D세트R2_비교.md`
  - `../../lab/04-26_D세트R3_산출물/2026-04-26_D세트R3_비교.md`
  - `../../lab/04-26_D세트R3_산출물v2/2026-04-26_D세트R3_개선후_비교.md`
  - `../../lab/04-26_E세트R1_산출물/2026-04-26_E세트R1_비교.md`
  - `../../lab/04-26_E세트R2_산출물/2026-04-26_E세트R2_비교.md`
  - `../../lab/04-26_E세트R3_산출물/2026-04-26_E세트R3_비교.md`
  - `../../lab/04-29_E세트R3B_산출물/2026-04-29_E세트R3B_비교.md`
  - `../../lab/04-30_E세트R2B_산출물/2026-04-30_E세트R2B_비교.md`
  - `../../lab/05-02_F세트R1_산출물/2026-05-02_F세트R1_비교.md`
  - `../../lab/05-02_F세트R2A_산출물/2026-05-02_F세트R2A_비교.md`
  - `../../lab/05-02_F세트R2B_산출물/2026-05-02_F세트R2B_비교.md`
  - `../../lab/05-03_G세트_산출물/2026-05-03_G세트_종합.md`
  - `../../lab/05-03_H세트_산출물/2026-05-03_H세트_종합.md`
- 관련 문서:
  - [99_A-H세트_중간정리.md](./99_A-H세트_중간정리.md)
  - [99_A-F세트_대표샘플_6선.md](./99_A-F세트_대표샘플_6선.md)
  - [99_llm_sample_validation_review.md](./99_llm_sample_validation_review.md)
  - [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
  - [../design/99_lab_runner_migration_plan.md](../design/99_lab_runner_migration_plan.md)

## 1. 목적

이 문서는 `lab/*_산출물`과 `lab/ABCDE_비교실험_요약.md`에 흩어진 A~H 세트 실험 결론을 `docs/reviews` 쪽에서 읽을 수 있게 요약한다.

이 문서가 하는 일은 다음이다.

- lab 산출물 `.md`에 흩어진 실험 결론을 docs에서 읽을 수 있게 요약한다.
- A~H 세트별 실험 목적과 결론을 정리한다.
- 어떤 lab artifact가 대표 샘플 또는 fixture 후보인지 기록한다.
- lab 원본이 아직 legacy lab artifact로 남아 있음을 명확히 한다.

이 문서가 하지 않는 일은 다음이다.

- 새로운 prepare policy 확정
- 새로운 scoring/verdict 확정
- Stage1/Stage2 결과 재계산
- lab JSON/JSONL artifact 삭제
- runner 코드 동작 변경
- lab 원본 문서 대체 또는 삭제

## 2. 세트별 요약

| set | 주제 | runner 위치 | 산출물 위치 | 주요 결론 | docs 반영 상태 | 남은 lab 의존성 |
| --- | --- | --- | --- | --- | --- | --- |
| A | baseline/auth 계열 | curl 기반 실행 문서 중심, 별도 legacy runner 없음 | `../../lab/04-24_A세트_산출물` | 인증 실패와 200 login response가 provider별 해석 차이를 만든다. OpenAI는 보수적으로 내부 테스트 가능성을 우선하고, Anthropic은 401에서 200으로 이어지는 흐름을 더 적극적으로 강조했다. Apache 로그만으로 token 발급, session 성립, 계정 탈취는 단정하지 않는다. | 이 문서와 [99_A-F세트_대표샘플_6선.md](./99_A-F세트_대표샘플_6선.md)에 요약 | legacy comparison md와 stage2 report 원본은 유지 |
| B | SQLi runner / R1/R2A/R2B | `../../scripts/lab_runners/b_set` | `../../lab/04-25_B세트R1_산출물`, `../../lab/04-25_B세트R2A_산출물`, `../../lab/04-25_B세트R2B_산출물` | GET query에 남은 SQLi payload는 안정적으로 후보화됐다. R1은 POST body visibility 한계를 드러냈고, R2A는 Boolean pair의 response surface 차이를 관찰했지만 Time-based 성공은 보류했다. R2B는 double encoding, temporal support, educational FP bait 분리를 검증했다. SQLi DB success, 데이터 유출, DB dump는 단정하지 않는다. | 이 문서와 LLM sample validation summary에 요약 | B R2B는 대표 샘플/fixture 후보. raw/stage report 원본은 후속 fixture 선별까지 유지 |
| C | XSS 계열 | `../../scripts/lab_runners/c_set` | `../../lab/04-25_C세트_산출물` | URL/HTML entity decode로 XSS intent를 복원하고, tutorial/onerror 계열 FP bait를 candidate로 과승격하지 않고 review context로 보존했다. browser execution, cookie theft, external exfiltration 성공은 단정하지 않는다. | 이 문서와 LLM sample validation summary에 요약 | C HTML entity XSS는 대표 sample fixture 후보. 원본 산출물은 유지 |
| D | traversal/HPP/probe 계열 | `../../scripts/lab_runners/d_set` | `../../lab/04-26_D세트R1_산출물`, `../../lab/04-26_D세트R2_산출물`, `../../lab/04-26_D세트R3_산출물`, `../../lab/04-26_D세트R3_산출물v2` | R1은 traversal 핵심 후보를 보존했고 R2는 query-string HPP+SQLi/XSS를 보존했다. R3는 `/server-status` 403 대표 candidate만 남기고 나머지 probing burst를 context로 묶는 방향이 개선됐다. 200/text/html 반복은 fallback 가능성으로만 보며 file read/file exposure/admin access success를 단정하지 않는다. | 이 문서와 중간정리에 요약 | D R3 probing sequence는 fixture 후보. fallback-like 판단은 response body 없이 확정하지 않음 |
| E | OpenCart/php wrapper/search 계열 | `../../scripts/lab_runners/e_set` | `../../lab/04-26_E세트R1_산출물`, `../../lab/04-26_E세트R2_산출물`, `../../lab/04-26_E세트R3_산출물`, `../../lab/04-29_E세트R3B_산출물`, `../../lab/04-30_E세트R2B_산출물` | OpenCart front-controller/routed response 환경에서도 query parameter 의미를 기준으로 후보를 보존했다. PHP wrapper는 source/config disclosure intent로 분리하고, direct config path는 과승격하지 않는다. search normal baseline과 SQLi/XSS payload를 분리한다. 200/text/html, 0B, 32KB response surface만으로 config/source 노출 성공을 단정하지 않는다. | 이 문서, representative sample, LLM sample validation summary에 요약 | E R2B는 대표 fixture 후보. front-controller/fallback 200 guardrail 유지를 위해 원본 유지 |
| F | auth response delta | `../../scripts/lab_runners/f_set` | `../../lab/05-02_F세트R1_산출물`, `../../lab/05-02_F세트R2A_산출물`, `../../lab/05-02_F세트R2B_산출물` | 반복 auth endpoint interaction을 개별 incident 43건으로 나열하지 않고 대표 candidate와 supporting context로 줄였다. R2B에서는 existing/nonexistent/lockout-probe 그룹이 모두 401/26B로 유사하게 관찰됐다. login success, account takeover, credential stuffing success, user enumeration success, lockout 발동은 단정하지 않는다. | 이 문서와 LLM sample validation summary에 요약 | F R2B는 대표 fixture 후보. POST body visibility 한계 검증용 원본 유지 |
| G | method/protocol/baseline | `../../scripts/lab_runners/g_set` | `../../lab/05-03_G세트R1_산출물`, `../../lab/05-03_G세트R2_산출물`, `../../lab/05-03_G세트R3_산출물`, `../../lab/05-03_G세트_산출물` | method/protocol 요청은 고신호 incident가 아니라 context-only summary로 보존하는 것이 목적이다. R1은 OPTIONS/TRACE/PUT/DELETE/HEAD/GET, R2는 raw socket 기반 malformed/protocol anomaly, R3는 baseline/monitoring-like method 요청을 검증했다. protocol anomaly와 attack success를 구분한다. | 이 문서와 LLM sample validation summary에 요약 | G R2 raw socket runner는 단순 삭제 금지. raw protocol 재현성 때문에 runner는 `scripts/lab_runners`에, 산출물은 legacy lab artifact로 유지 |
| H | static/crawler/scanner/mixed | `../../scripts/lab_runners/h_set` | `../../lab/05-03_H세트R1_산출물`, `../../lab/05-03_H세트R2_산출물`, `../../lab/05-03_H세트R3_산출물`, `../../lab/05-03_H세트R4_산출물`, `../../lab/05-03_H세트_산출물` | static/health/normal browse, crawler-like UA, scanner-like sensitive path, mixed benign+scanner context를 분리했다. R1/R2는 candidate 0이 정상이며, R3/R4는 `/server-status` 403 대표 candidate 1건만 low로 유지한다. static file existence, crawler authenticity, site structure, WordPress 존재, `.env`/phpinfo/backup/server-status 노출, 단일 공격 성공 chain은 단정하지 않는다. | 이 문서와 LLM sample validation summary에 요약 | H R2/R3/R4는 대표 fixture 후보. mixed context와 low severity wording 검증용 원본 유지 |

## 3. Apache Logs-Only Guardrail

A~H 세트에서 공통으로 유지해야 할 guardrail은 다음이다.

- `status_code=200`, `response_body_bytes`, `resp_content_type`, `handler`만으로 성공, 노출, 침해를 단정하지 않는다.
- POST body, response body, DB result, browser execution은 Apache logs-only 입력에서 보이지 않는다.
- payload candidate 유지와 exploit success는 분리한다.
- auth, upload, probe, status-error-only 계열은 context 또는 weak signal로 다루며 broad demotion 확정 근거가 아니다.
- handler, route, front-controller, proxy/backend hint는 topology/context로 보며 backend route existence나 file existence proof가 아니다.
- source IP, known asset, User-Agent는 관찰값이며 외부 공격자 attribution proof가 아니다.
- lab 전용 UA는 실험 문맥 확인에는 유용하지만 일반 운영 탐지 근거처럼 쓰지 않는다.

## 4. 대표 샘플과 Fixture 후보

후속 PR에서 fixture로 선별할 만한 후보는 다음이다.

| 후보 | 이유 | 주의점 |
| --- | --- | --- |
| B R2B double encoded SQLi | double decode, supporting context, educational FP bait 분리를 함께 검증 | SQLi DB success 단정 금지 |
| C HTML entity XSS | HTML entity decode와 tutorial/onerror FP bait 분리 검증 | browser execution/cookie theft 단정 금지 |
| D R3 probing sequence | candidate 과승격 없이 probing sequence summary 전달 검증 | fallback-like 200을 file exposure로 단정 금지 |
| E R2B PHP wrapper | PHP wrapper source/config disclosure intent와 direct config path 과승격 방지 검증 | 200/text/html, 0B, 32KB만으로 source/config 노출 단정 금지 |
| F R2B auth response delta | auth response surface가 유사할 때 success/account inference를 제한하는지 검증 | POST body 미확인, user enumeration/lockout 단정 금지 |
| G R2 protocol anomaly | raw socket malformed/protocol request를 context-only로 보존하는지 검증 | protocol bypass/침해 성공 단정 금지 |
| H R2 crawler baseline | crawler-like UA와 robots/sitemap/browse가 candidate로 과승격되지 않는지 검증 | crawler authenticity/site structure 단정 금지 |
| H R3 scanner low-signal path | sensitive path probe context와 `/server-status` 대표 candidate 분리 검증 | WordPress/file exposure/admin access 단정 금지 |
| H R4 mixed baseline scanner | 정상 baseline과 scanner-like context를 단일 성공 공격으로 합치지 않는지 검증 | key finding severity가 대표 incident보다 강해지지 않게 관리 |

## 5. Lab 원본과의 관계

lab 산출물은 이번 작업에서 삭제하지 않는다. 이 문서는 lab 산출물 `.md`의 docs-side summary이며, lab JSON/JSONL/log artifact 제거 여부는 후속 PR에서 판단한다.

lab 원본은 다음 이유로 당분간 legacy lab artifact로 남긴다.

- runner 실행 재현 경로는 `scripts/lab_runners/{set}/`로 이관됐다.
- runner code의 current path와 migration 영향 범위는 [../design/99_lab_runner_migration_plan.md](../design/99_lab_runner_migration_plan.md)를 따른다.
- raw/stage report artifact는 fixture 후보 선별과 회귀 기대값 확인에 필요할 수 있다.
- G R2처럼 raw socket runner 특성이 중요한 경우 단순 삭제하면 재현성이 깨진다.
- 대표 fixture 후보는 후속 PR에서 별도로 선별해야 한다.

## 6. 결론

A~H lab 비교/종합 문서에서 docs로 이관해야 할 핵심 판단은 새 policy가 아니라 evidence boundary와 context 보존 원칙이다.

핵심 결론은 다음이다.

- SQLi, XSS, traversal, HPP, PHP wrapper, auth behavior, method/protocol anomaly, static/crawler/scanner-like noise는 Apache 로그 표면에서 후보 또는 context로 보존할 수 있다.
- 그러나 이 파이프라인은 성공한 공격 판정기가 아니며, 성공/침해/노출/실행/계정 상태/DB 결과는 별도 증거 없이는 확정하지 않는다.
- lab 원본은 legacy source로 남기되, docs에서는 이 문서와 관련 review summary를 우선 참조한다.
