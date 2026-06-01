# 99 LLM Sample Validation Review

- 문서 상태: review / lab LLM sample validation 이관 요약
- 기준 원문:
  - `../../lab/LLM샘플검증/2026-05-03_FGH_sample_review.md`
  - `../../lab/LLM샘플검증/2026-05-04_BCE_sample_review.md`
- 관련 문서:
  - [99_lab_experiment_set_summaries.md](./99_lab_experiment_set_summaries.md)
  - [99_llm_sample_review_plan.md](./99_llm_sample_review_plan.md)
  - [99_A-F세트_대표샘플_6선.md](./99_A-F세트_대표샘플_6선.md)
  - [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
  - [../design/99_prepare_candidate_policy.md](../design/99_prepare_candidate_policy.md)
  - [../design/99_prepare_candidate_policy_distribution_history.md](../design/99_prepare_candidate_policy_distribution_history.md)

## 1. 목적

이 문서는 `lab/LLM샘플검증/*.md`에 남아 있는 수동 LLM sample review 결과를 `docs/reviews` 쪽에서 읽을 수 있게 요약한다.

검토 목적은 대표 샘플에 대한 LLM 판단 품질, scoring/분류 해석, false-positive/overclaim 위험을 정리하는 것이다. 특히 Apache logs-only evidence boundary가 Stage1/Stage2 판단과 report wording에서 유지되는지 확인한다.

A~H 실험 묶음 자체의 목적, 결론, legacy lab artifact 관계는 [99_lab_experiment_set_summaries.md](./99_lab_experiment_set_summaries.md)를 우선 본다. 이 문서는 그중 대표 샘플에 대한 LLM 판단 품질 검토에 초점을 둔다.

이 문서가 하는 일은 다음이다.

- lab 원문에 있던 핵심 판단과 guardrail을 docs 쪽에서 읽을 수 있게 정리한다.
- 대표 샘플 검토가 prepare/stage 판단에 어떤 의미를 주었는지 요약한다.
- Apache logs-only evidence boundary가 LLM 판단에서 어떻게 유지되어야 하는지 정리한다.

이 문서가 하지 않는 일은 다음이다.

- 새로운 prepare policy 확정
- 새로운 scoring 기준 확정
- Stage1/Stage2 verdict 재계산
- lab sample 원본 삭제 또는 대체 실행 artifact 생성

## 2. 검토 대상 요약

| source | sample/set | 검토 목적 | 현재 docs 상태 |
| --- | --- | --- | --- |
| `2026-05-03_FGH_sample_review.md` | F R2B, G R2, H R2, H R3, H R4 | auth response delta, protocol anomaly, crawler/scanner baseline, mixed baseline+scanner wording 검토 | 이 문서에 docs-side 요약. lab 원문은 legacy lab source로 유지 |
| `2026-05-04_BCE_sample_review.md` | B R2B, C HTML entity XSS, E R2B | double encoded SQLi, HTML entity XSS, PHP wrapper file disclosure 판단 품질 검토 | 이 문서에 docs-side 요약. lab 원문은 legacy lab source로 유지 |
| [99_A-F세트_대표샘플_6선.md](./99_A-F세트_대표샘플_6선.md) | A~F representative set | 수동 리뷰와 발표/온보딩용 대표 샘플 대조 기준 | 세부 대표 샘플 기준 문서. LLM sample validation summary는 이 문서를 우선 참조 |

## 3. 공통 결론

수동 review의 공통 결론은 다음이다.

- LLM이 `status_code=200`, response size, content-type, handler만으로 공격 성공, 파일 노출, 로그인 성공, backend route 존재를 단정하면 안 된다.
- POST body, response body, DB result, browser execution은 Apache logs-only 분석에서 보이지 않는다.
- payload-like request는 candidate로 유지할 수 있지만 success proof는 아니다.
- auth/upload/probe/status-error-only 계열은 문맥에 따라 context 또는 weak signal로 다뤄야 한다.
- false positive 또는 overclaim 방지 wording이 report 품질에 중요하다.
- “관찰된 것”과 “추론할 수 없는 것”을 분리해야 한다.

정량 검토된 샘플은 대체로 통과 수준이었다. 낮은 점수나 개선 후보는 탐지 실패보다 wording, taxonomy, severity consistency, false-positive 설명 명시도에 집중되어 있었다.

## 4. 샘플별 관찰 요약

| sample | 관찰된 신호 | LLM 판단상 주의점 | 보존할 guardrail |
| --- | --- | --- | --- |
| B R2B double encoded SQLi | double encoded SQLi-like query, decoded depth hint, educational SQL FP bait | SQLi 시도와 educational search를 분리하고, chain/supporting context를 incident로 과승격하지 않는다. | SQLi 성공, DB schema 유출, DB dump, 데이터 유출을 단정하지 않는다. |
| C HTML entity XSS | HTML entity encoded XSS-like query, tutorial/onerror FP bait | entity decode로 XSS intent를 읽되 tutorial 검색은 false-positive review context로 보존한다. | browser execution, cookie theft, external exfiltration 성공을 단정하지 않는다. |
| E R2B PHP wrapper/file disclosure | `php://filter` wrapper, config source disclosure intent, direct config probe context | wrapper/file disclosure intent는 보존하되 direct config path probe를 과승격하지 않는다. taxonomy와 lab-* UA wording은 보수적으로 관리한다. | 200/text/html, 큰 response body size만으로 config/source 노출 성공을 단정하지 않는다. |
| F R2B auth response delta | 반복 login POST, 401 response surface, auth behavior summary | existing/nonexistent/lockout-probe 의도 그룹이 있더라도 Apache 로그 표면만으로 계정 존재나 lockout을 판단하지 않는다. | POST body 미확인 상태에서 user enumeration success, lockout 발동, login success를 단정하지 않는다. |
| G R2 protocol anomaly | malformed/protocol-like request context, candidate 없음, protocol anomaly summary | candidate가 없는 것은 실패가 아니며 protocol anomaly context-only 보존이 목적이다. | protocol bypass, malformed request exploit, 침해 성공을 단정하지 않는다. |
| H R2 crawler-like baseline | crawler-like UA, robots/sitemap/product/category browse, baseline summaries | crawler-like UA와 browse sequence를 공격으로 과승격하지 않는다. | crawler 진위, site structure, page existence를 Apache 로그만으로 확정하지 않는다. |
| H R3 scanner-like sensitive path | `/server-status` 대표 candidate, sensitive path probe summary, probing sequence | sensitive path probe는 low severity context로 설명한다. | WordPress 존재, `.env`/phpinfo/backup/server-status 노출, admin access, 침해 성공을 단정하지 않는다. |
| H R4 mixed benign + scanner-like | 정상 browse/static/crawler-like와 scanner-like sensitive path 혼재 | mixed context를 단일 공격 chain처럼 쓰지 않고 baseline과 scanner-like context를 분리한다. | key finding severity가 대표 incident보다 과도하게 높아지지 않게 wording을 관리한다. |

## 5. Apache Logs-Only Evidence Boundary

LLM report에서 유지해야 할 상한선은 다음이다.

- 관찰 가능한 것은 request/response metadata, query/path/header metadata, status code, response size, content type, handler, error/security log message, sequence/grouping이다.
- Apache 로그만으로 raw POST body, response body, DB query result, browser execution, filesystem state, application auth state는 알 수 없다.
- `status_code=200`은 HTTP response 관찰이지 success proof가 아니다.
- `response_body_bytes`와 `resp_content_type`은 body content proof가 아니다.
- handler, route name, `_route_=`, `proxy-server`는 topology hint이며 backend route existence나 file existence proof가 아니다.
- source IP/header metadata는 관찰값이며 attacker attribution proof가 아니다.

허용되는 표현은 “요청이 관찰됨”, “payload-like pattern이 관찰됨”, “context-only signal”, “candidate signal”, “추가 확인 필요”, “로그만으로 성공 여부 판단 불가” 수준이다.

## 6. Prepare/Stage/Report 품질에 주는 의미

prepare 관점에서는 suspicious evidence를 버리지 않는 것이 중요하다. 다만 candidate visibility가 곧 success verdict는 아니다.

- explicit payload 후보는 유지할 수 있다.
- auth/upload/probe/status-error-only 계열은 context 또는 weak signal로 분리한다.
- broad demotion, scoring 변경, severity 변경은 이 review만으로 확정하지 않는다.
- taxonomy 개선 후보는 별도 design 문서와 regression을 거쳐야 한다.

Stage1/Stage2/report 관점에서는 다음 기준을 유지한다.

- candidate와 supporting/context summary를 구분한다.
- false-positive review candidate를 공격 성공처럼 쓰지 않는다.
- known asset, baseline, internal test, UA spoof 가능성을 필요한 곳에 병기한다.
- severity와 key finding wording이 로그 표면보다 강해지지 않도록 제한한다.
- “보이는 사실”과 “추가 증거 없이는 알 수 없는 것”을 같은 문단 안에서도 분리한다.

## 7. Lab 원본과의 관계

lab 원문은 현재 삭제하지 않는다.

이 문서는 장기적으로 docs에서 lab 직접 링크를 줄이기 위한 review summary다. lab 원문은 삭제/이동/archive 전까지 legacy lab source 또는 원본 lab artifact로 남긴다.

lab 원문 삭제, 이동, archive 여부는 별도 PR에서만 검토한다.

## 8. 결론

`lab/LLM샘플검증`의 수동 review 결과는 현재 Stage1/Stage2가 Apache logs-only 보수적 해석 원칙을 대체로 잘 지킨다는 근거로 볼 수 있다.

핵심 보존 결론은 다음이다.

- 성공/침해/노출 단정을 피한다.
- payload-like request와 context-only summary를 구분한다.
- false-positive와 baseline 가능성을 함께 설명한다.
- taxonomy, severity consistency, wording guard는 계속 품질 검토 대상으로 둔다.
