# 99_prepare_graphql_introspection_fixture_plan

- 문서 상태: GraphQL / API introspection fixture plan
- 기준 시점: 2026-05-07
- 목적: GraphQL / API introspection coverage plan 이후 실제 fixture/regression 추가 여부를 판단하기 위한 설계 기준을 고정한다.

관련 문서:

- [99_prepare_graphql_introspection_coverage_plan.md](./99_prepare_graphql_introspection_coverage_plan.md)
- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
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
- GraphQL 관련 문자열은 주로 docs/design 후보 검토/coverage plan 문서에 존재한다.
- src/tests에는 GraphQL introspection 전용 fixture/expected 회귀 케이스가 아직 없다.
- 이번 작업은 fixture plan 문서 작성이며 fixture/expected/code 수정은 수행하지 않는다.
```

## 1. 목적

- coverage plan에서 정한 GraphQL 후보를 fixture/regression 관점으로 좁힌다.
- 바로 구현하지 않고 fixture 설계와 expected 확인 포인트를 고정한다.

## 2. 현재 coverage 확인 결과

GraphQL 관련 기존 hint/module/fixture 확인:

- 전용 GraphQL hint module은 없다.
- `l3_hints.py`에 GraphQL introspection 전용 hint 경로는 아직 명시적으로 분리되어 있지 않다.
- GraphQL introspection 전용 fixture/expected는 아직 없다.

이미 있는 coverage:

- P2 후보 검토 문서에서 GraphQL introspection 신호와 Apache logs-only 해석 경계가 정리되어 있다.
- 기존 prepare/stage dry-run 검증 체계는 안정 상태로 유지되고 있다.

부족한 coverage:

- `__schema` / `__type` / `IntrospectionQuery` query string 기반 회귀 샘플 부재
- `/graphql` 및 `/graphql/playground` baseline과 introspection query의 과승격 경계 검증 부재
- benign search/doc 문자열(`graphql`)의 false-positive 억제 회귀 부재

현재 regression 기준:

- prepare regression `pass=21 warn=0 fail=0`
- stage dry-run regression `pass=15 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. fixture 후보

아래 후보를 비교한다.

GraphQL introspection query:

- `GET /graphql?query={__schema{types{name}}}`
- `GET /api/graphql?query=IntrospectionQuery`
- `GET /graphql?query={__type(name:"Query"){fields{name}}}`

GraphQL endpoint baseline:

- `GET /graphql`
- `GET /graphql/playground`

benign text baseline:

- `GET /api/search?q=graphql`
- `GET /docs?topic=graphql`

## 4. 후보별 expected 검증 포인트

각 fixture 공통 체크:

- introspection-like query candidate 또는 context 보존 여부
- GraphQL / introspection hint 확인 여부
- benign search/doc baseline이 `analysis_candidates`로 과승격되지 않는지
- Stage2 report input에 candidate/context 유지 여부
- 성공 단정 문구 없음
- `status_code=200`/bytes만으로 schema 노출 성공을 확정하지 않음

fixture family별 최소 체크:

- GraphQL introspection query: `__schema` / `__type` / `IntrospectionQuery` 신호가 candidate 또는 고신호 context로 보존되는지 확인
- GraphQL endpoint baseline: 단순 endpoint 접근은 low-signal context로 유지되는지 확인
- benign text baseline: `graphql` 문자열 포함만으로 공격 candidate 과승격이 없는지 확인

## 5. candidate vs context-only 기준

- `/graphql` 단순 접근은 context-only 또는 low signal
- GET query string에 `__schema` / `__type` / `IntrospectionQuery`가 있으면 analysis candidate 가능
- POST body만 있는 GraphQL query는 Apache access log만으로 원문 확인 불가
- GraphQL playground 접근은 취약점 근거가 아님
- `status=200`을 schema disclosure 성공 근거로 쓰지 않음

## 6. 기존 module 확장 여부

- `l3_hints.py`에 최소 GraphQL introspection-like hint 추가가 적절한지 검토
- 새 module 생성은 보류
- shared attack/search policy 변경 금지
- normal search false-positive handling 변경 금지
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지

## 7. Stage dry-run regression 추가 여부

선택지:

- prepare regression만 추가
- prepare + stage dry-run regression 동시 추가
- 필요 시 actual LLM spot check 수행

권장:

- 1차는 `prepare + stage dry-run regression` 동시 추가
- actual LLM spot check는 필수는 아니지만 wording drift 관찰 목적 1~2건을 조건부 권장

## 8. 권장 1차 fixture

추천:

- `l3_graphql_introspection_context`

후순위:

- `graphql_endpoint_baseline_context`

우선순위 이유:

- P2 첫 후보의 핵심 직접 신호(`__schema`, `__type`, `IntrospectionQuery`)를 먼저 고정하는 편이 가치가 높다.
- baseline-only 케이스는 introspection query 고정 이후 false-positive 억제 보강용으로 분리하는 편이 안전하다.

## 9. 금지 wording

금지 표현:

- GraphQL schema exposed
- introspection enabled confirmed
- API structure exposed
- data exfiltration
- auth bypass succeeded
- GraphQL vulnerability confirmed

허용 wording:

- GraphQL introspection-like request observed
- GraphQL endpoint access observed
- requires manual review
- Apache logs alone do not confirm schema disclosure

## 10. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- 첫 구현 후보는 `l3_graphql_introspection_context`로 두는 것이 적절하다.
- fixture 추가 전 확인할 것:
  - introspection-like query 직접 신호와 baseline-only 요청을 한 fixture에 과도하게 혼합하지 않는지
  - benign search/doc baseline 과승격 억제 확인이 가능한지
  - Stage2 wording에서 schema disclosure 성공 단정 금지 표현이 유지되는지
- 코드 수정은 다음 작업으로 분리하고, 이번 문서는 fixture/regression 설계 기준 고정으로 마감한다.
