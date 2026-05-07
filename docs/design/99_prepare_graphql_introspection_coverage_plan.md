# 99_prepare_graphql_introspection_coverage_plan

- 문서 상태: GraphQL / API introspection attempt coverage plan
- 기준 시점: 2026-05-07
- 목적: P2 첫 신규 coverage 후보로 GraphQL / API introspection attempt 계열을 검토하고, Apache logs-only evidence boundary를 먼저 고정한 뒤 fixture/regression 추가 여부를 판단한다.

관련 문서:

- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_webshell_probe_coverage_plan.md](./99_prepare_webshell_probe_coverage_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "graphql\|__schema\|__type\|IntrospectionQuery" src tests docs
```

확인 요약:

```text
- GraphQL introspection 전용 fixture/regression(`l3_graphql_introspection_context`)이 추가되었다.
- `src/prepare/l3_hints.py`와 `src/prepare_llm_input.py` 최소 수정으로 `__schema`/`__type`/`IntrospectionQuery`와 `/graphql` 계열 path 탐지가 반영되었다.
- 이번 문서는 구현 지시가 아니라 coverage 기준 정리 문서로 유지한다.
```

## 1. 목적

- GraphQL endpoint / introspection-like query coverage 후보를 검토한다.
- schema disclosure success, introspection enabled confirmed, API structure exposure를 단정하지 않는 기준을 고정한다.
- 이번 문서는 구현 코드 작성 문서가 아니라 coverage plan 문서다.

## 2. 현재 상태

P1 coverage 완료 상태:

- SSRF metadata endpoint
- Log4Shell obfuscated payload
- Webshell/admin tool path probe

현재 regression 상태:

- prepare regression `pass=22 warn=0 fail=0`
- stage dry-run regression `pass=16 warn=0 fail=0`
- Stage2 quality tests `14 passed`

GraphQL 관련 기존 coverage 관찰:

- `l3_graphql_introspection_context` fixture/expected(prepare, stage dry-run)가 추가 완료되었다.
- introspection-like query 3건과 benign baseline 2건으로 candidate/context 보존과 과승격 억제 경계를 함께 고정했다.

## 3. 관찰 가능한 signal

Apache logs-only 기준에서 관찰 가능한 주요 signal:

- `/graphql`
- `/api/graphql`
- `query={__schema{...}}`
- `query={__type(name:"...")}`
- `IntrospectionQuery`
- `__schema`
- `__type`
- GraphQL playground-like endpoint 접근
- status/bytes/timing metadata

## 4. Apache logs-only로 단정 금지

아래 항목은 Apache access logs만으로 단정하지 않는다.

- schema disclosure success
- introspection enabled confirmed
- API structure exposed
- backend data exfiltration
- GraphQL vulnerability confirmed
- auth bypass
- raw POST body contents
- response body contents

보수적 해석 원칙:

```text
- query string marker는 request surface signal이다.
- status_code=200, response_body_bytes, timing metadata는 보조 signal이지 결과 확정 근거가 아니다.
- /graphql endpoint 접근 사실만으로 취약점 존재를 단정하지 않는다.
```

## 5. 기존 module과의 관계

- 현재 전용 GraphQL hint module은 없다.
- `l3_hints.py`에 API/introspection-like hint를 최소 보강할지 검토 대상이다.
- shared attack/search policy와의 경계를 유지한다.
- normal search false-positive와의 경계를 유지한다.

이번 계획에서 고정할 제외 범위:

```text
- supporting_events 변경 없음
- scoring/filtering 변경 없음
- Stage2 reporter 변경 없음
- detect_decoded_attack_hints 변경 없음
```

## 6. candidate vs context-only 기준

candidate 가능 조건:

- GET query string에 `__schema` / `__type` / `IntrospectionQuery`가 직접 관찰될 때
- GraphQL endpoint 신호와 introspection-like marker가 결합되어 직접성이 높을 때

context-only 또는 low signal 우선 조건:

- `/graphql` 단순 접근만 있는 경우
- `/graphql/playground` 접근 단독인 경우
- 검색/탐색형 benign query에서 `graphql` 문자열만 관찰되는 경우

고정 규칙:

```text
- status=200/bytes를 schema 노출 성공 근거로 사용하지 않는다.
- playground 접근 단독으로 취약점 근거를 만들지 않는다.
```

## 7. Fixture/regression 아이디어

이번 문서에서는 fixture를 추가하지 않는다. 다음 구현 단계 후보만 고정한다.

GraphQL introspection query fixture 후보:

- `GET /graphql?query={__schema{types{name}}}`
- `GET /api/graphql?query=IntrospectionQuery`

GraphQL endpoint baseline 후보:

- `GET /graphql`
- `GET /graphql/playground`

benign text baseline 후보:

- `GET /api/search?q=graphql`

expected 확인 포인트:

- introspection-like query candidate/context 보존
- GraphQL/introspection hint 확인
- benign search baseline 과승격 방지
- Stage2 input에 candidate/context 유지
- success wording 없음

## 8. Stage2 wording/lint guard 필요 여부

필요하다.

금지 표현:

- GraphQL schema exposed
- introspection enabled confirmed
- API structure exposed
- data exfiltration
- auth bypass succeeded
- vulnerability confirmed

허용 표현:

- GraphQL introspection-like request observed
- GraphQL endpoint access observed
- requires manual review
- Apache logs alone do not confirm schema disclosure

## 9. 구현 범위 후보

- 기존 `l3_hints.py` 확장 가능성 검토
- 새 module 생성은 보류
- candidate/scoring/filtering 변경 금지
- supporting_events 변경 금지
- detect_decoded_attack_hints 변경 금지
- Stage2 reporter 변경 금지

## 10. 권장 1차 fixture 후보

추천:

- `l3_graphql_introspection_context` (1차 regression 완료)

후순위:

- `graphql_endpoint_baseline_context`

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

- GraphQL introspection 1차 regression(`l3_graphql_introspection_context`)은 완료되었다.
- schema disclosure success / introspection enabled confirmed / API structure exposed 단정 금지 원칙은 유지한다.
- 다음 P2 우선순위는 Open redirect와 SSTI 중 선택으로 정리한다.
