# 99_prepare_open_redirect_coverage_plan

- 문서 상태: Open redirect / redirect abuse attempt coverage plan
- 기준 시점: 2026-05-07
- 목적: P2 다음 coverage 후보인 Open redirect / redirect abuse attempt 계열을 검토하고, Apache logs-only evidence boundary와 SSRF URL parameter 경계를 먼저 고정한 뒤 fixture/regression 추가 여부를 판단한다.

관련 문서:

- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_graphql_introspection_coverage_plan.md](./99_prepare_graphql_introspection_coverage_plan.md)
- [99_prepare_graphql_introspection_fixture_plan.md](./99_prepare_graphql_introspection_fixture_plan.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_ssrf_log4shell_fixture_plan.md](./99_prepare_ssrf_log4shell_fixture_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_shared_attack_policy_reentry_review.md](./99_prepare_shared_attack_policy_reentry_review.md)
- [99_prepare_search_false_positive_policy_reentry_review.md](./99_prepare_search_false_positive_policy_reentry_review.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "redirect=\|next=\|return=\|continue=\|callback=\|url=\|open redirect\|open_redirect" src tests docs
```

확인 요약:

```text
- redirect/next/return/continue/callback/url 신호는 기존 SSRF 문맥과 P2 후보 비교 문서에 분산되어 있다.
- Open redirect 전용 coverage plan 문서는 아직 없었고, 이번 문서에서 경계 기준을 고정한다.
- 이번 작업은 문서 작성만 수행하며 fixture/expected/코드 수정은 하지 않는다.
```

## 1. 목적

- Open redirect / redirect abuse attempt coverage 후보를 검토한다.
- redirect 성공, phishing 성공, open redirect 취약점 확인을 단정하지 않는 기준을 고정한다.
- 이번 문서는 구현 코드 작성 문서가 아니라 coverage plan 문서다.

## 2. 현재 상태

- P2 후보 비교 문서에서 Open redirect는 GraphQL 다음 2순위 후보로 정리되어 있다.
- `url=`, `callback=`, `next=` 계열 parameter는 SSRF URL parameter family와 일부 경계가 겹친다.
- shared attack/search policy 및 normal search false-positive 경계는 유지한다.

현재 regression 상태:

- 완료된 신규 coverage regression:
  - `l3_ssrf_metadata_endpoint_context`
  - `l3_log4shell_obfuscated_payload_context`
  - `l3_webshell_admin_tool_probe_context`
  - `l3_graphql_introspection_context`
- prepare regression `pass=22 warn=0 fail=0`
- stage dry-run regression `pass=16 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. 관찰 가능한 signal

Apache logs-only 기준에서 관찰 가능한 주요 signal:

- `redirect=http://external.example/`
- `redirect=https://external.example/`
- `url=http://external.example/`
- `next=//external.example/`
- `return=https://external.example/`
- `continue=https://external.example/`
- `callback=https://external.example/`
- absolute external URL
- protocol-relative URL
- repeated redirect-like parameter probing
- status/bytes/timing metadata

## 4. Apache logs-only로 단정 금지

아래 항목은 Apache access logs만으로 단정하지 않는다.

- redirect succeeded
- victim followed redirect
- phishing succeeded
- open redirect vulnerability confirmed
- browser navigation happened
- exploit succeeded
- user credential theft
- server compromise

보수적 해석 원칙:

```text
- redirect-like parameter는 request surface signal이다.
- status_code=200/302/3xx, response_body_bytes, timing metadata는 보조 signal이지 결과 확정 근거가 아니다.
- 외부 URL parameter가 관찰되어도 성공 여부는 Apache logs만으로 확정하지 않는다.
```

## 5. SSRF와의 경계

- `url=`, `callback=`, `next=` 등은 SSRF와 Open redirect 양쪽에서 나타날 수 있다.
- internal target 또는 metadata endpoint 신호가 핵심이면 SSRF 쪽 해석을 우선한다.
- external domain이 redirect-like parameter에 들어가면 Open redirect-like attempt로 볼 수 있다.
- 단순 외부 URL parameter만으로 취약점을 확정하지 않는다.
- status=200/302/3xx만으로 redirect 성공을 단정하지 않는다.

경계 우선순위(초안):

```text
1) metadata/internal target 직접성 높음 -> SSRF 우선
2) redirect-like parameter + external URL 반복 탐색 -> Open redirect-like attempt 후보
3) 단일 정상 링크/문서 URL -> context 또는 benign baseline
```

## 6. 기존 module과의 관계

- `l3_hints.py`에 URL parameter 기반 hint를 추가할지 검토 대상이다.
- SSRF hint와의 중복 가능성 및 분기 기준을 먼저 문서화해야 한다.
- shared attack/search policy 변경은 금지한다.
- normal search false-positive handling 변경은 금지한다.

이번 계획에서 고정할 제외 범위:

```text
- detect_decoded_attack_hints 변경 없음
- supporting_events/scoring/filtering 변경 없음
- Stage2 reporter 변경 없음
- 새 module 생성 보류
```

## 7. candidate vs context-only 기준

analysis candidate 가능 조건:

- redirect-like parameter(`redirect`, `url`, `next`, `return`, `continue`, `callback`)와 external URL이 결합된 경우
- 동일 계열 parameter probing이 반복되어 탐색 패턴이 보이는 경우

context-only 또는 baseline 우선 조건:

- `url=https://example.com/manual.pdf`처럼 정상 문서 링크 성격이 강한 경우
- same-site relative URL(`next=/account`) 중심인 경우
- 검색 질의(`q=redirect`)처럼 일반 탐색 성격이 강한 경우

고정 규칙:

```text
- same-site relative URL을 analysis candidate로 과승격하지 않는다.
- status_code/bytes만으로 성공을 판단하지 않는다.
- 반복 probing은 success가 아니라 context summary로만 보존한다.
```

## 8. Fixture/regression 아이디어

이번 문서에서는 fixture를 추가하지 않는다. 다음 구현 단계 후보만 고정한다.

후보 fixture:

- `l3_open_redirect_external_url_context`
  - `GET /login?next=https://external.example/`
  - `GET /redirect?url=//external.example/`
  - `GET /oauth/authorize?continue=https://external.example/`

benign baseline 후보:

- `GET /product?url=https://example.com/manual.pdf`
- `GET /login?next=/account`
- `GET /search?q=redirect`

expected 확인 포인트:

- external redirect-like parameter candidate/context 보존
- open-redirect-like hint 확인
- benign external documentation URL 과승격 방지
- same-site relative redirect baseline 과승격 방지
- Stage2 input에 candidate/context 유지
- success wording 없음

## 9. Stage2 wording/lint guard 필요 여부

필요하다.

금지 표현:

- open redirect confirmed
- redirect succeeded
- victim followed redirect
- phishing succeeded
- exploit succeeded
- credential theft
- browser redirected

허용 표현:

- open-redirect-like parameter observed
- external URL in redirect-like parameter
- redirect abuse attempt pattern
- requires manual review
- Apache logs alone do not confirm redirect success

## 10. 권장 1차 fixture 후보

추천:

- `l3_open_redirect_external_url_context`

후순위:

- `open_redirect_baseline_context`

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

- Open redirect / redirect abuse attempt는 GraphQL 다음 P2 후보로 유지한다.
- 바로 구현하기보다 fixture plan을 한 번 더 분리해 expected 경계와 SSRF 분기 기준을 먼저 고정하는 경로가 안전하다.
- SSTI와의 우선순위는 Open redirect를 먼저 검토하는 쪽으로 유지한다.
- Webshell command query는 traversal/CMDI 의미 경계가 민감하므로 계속 별도 검토 후보로 유지한다.
