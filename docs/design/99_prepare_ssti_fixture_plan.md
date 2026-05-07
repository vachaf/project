# 99_prepare_ssti_fixture_plan

- 문서 상태: SSTI / template injection fixture plan
- 기준 시점: 2026-05-07
- 목적: SSTI / template injection coverage를 실제 fixture/regression 후보로 좁히고, Apache logs-only evidence boundary를 유지한 채 추가 여부를 판단한다.

관련 문서:

- [99_prepare_ssti_coverage_plan.md](./99_prepare_ssti_coverage_plan.md)
- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "ssti\|template\|{{\|<%=\|#{\|\${.*7.*7" src tests docs
```

확인 요약:

```text
- l3_hints.py에 SSTI 관련 hint detector(detect_ssti_hints)와 educational search detector가 이미 존재한다.
- prepare_llm_input.py에는 SSTI score/hint 연동과 educational_ssti_context 기반 false-positive 완화가 존재한다.
- 기존 fixture/expected에는 l3_ssti_webshell_context가 있어 SSTI+webshell 복합 케이스는 이미 커버된다.
- 이번 문서는 fixture plan 작성만 수행하며 fixture/expected/code는 수정하지 않는다.
```

## 1. 목적

- coverage plan에서 정한 SSTI 후보를 fixture/regression 관점으로 좁힌다.
- 바로 구현하지 않고 fixture 설계와 expected 확인 포인트를 고정한다.

## 2. 현재 coverage 확인 결과

SSTI 관련 hint 존재 여부:

- `src/prepare/l3_hints.py`
  - `detect_ssti_hints`
  - `detect_educational_ssti_search_context`
  - SSTI hint 계열: `l3:ssti`, `ssti:template_expression`, `ssti:jinja_expression`, `ssti:freemarker_expression`

기존 fixture와의 관계:

- `tests/fixtures/prepare_regression/l3_ssti_webshell_context.json`는 `{{7*7}}`와 `/upload/shell.php?cmd=id`가 함께 있는 복합 케이스다.
- 따라서 SSTI 단독 payload family를 분리 평가하는 독립 fixture는 아직 부족하다.

이미 있는 coverage vs 부족한 coverage:

- 이미 있는 coverage:
  - 복합 고신호(SSTI + webshell command query)에서 candidate/hint 보존 확인
- 부족한 coverage:
  - arithmetic/object 계열 SSTI payload만 따로 분리한 candidate/context 경계
  - benign template/search baseline 과승격 방지 경계

현재 regression 기준:

- prepare regression `pass=23 warn=0 fail=0`
- stage dry-run regression `pass=17 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. fixture 후보

아래 후보를 비교한다.

arithmetic template expression:

- `GET /search?q={{7*7}}`
- `GET /profile?name=${7*7}`
- `GET /template?value=<%=7*7%>`

template object/identifier expression:

- `GET /search?q={{config}}`
- `GET /view?name={{request}}`

benign template/search baseline:

- `GET /docs?topic=template`
- `GET /search?q=jinja template`
- `GET /product?name=curly-braces`

## 4. 후보별 expected 검증 포인트

각 fixture에서 아래 항목을 확인한다.

- template-expression-like payload candidate/context 보존 여부
- SSTI / template expression hint 확인 여부
- benign template search baseline이 analysis candidate로 과승격되지 않는지
- Stage2 report input에 candidate/context 유지 여부
- 성공 단정 문구 없음
- `status_code=200`/`response_body_bytes`만으로 template execution 성공 확정하지 않음

## 5. candidate vs context-only 기준

analysis candidate 가능 조건:

- `{{7*7}}`, `${7*7}`, `<%=7*7%>`, `#{7*7}`, `{{config}}`, `{{request}}` 같이 template-expression-like payload 직접성이 높은 경우
- 동일 계열 expression probing이 반복되어 탐색 패턴이 보이는 경우

context-only 또는 benign/search baseline 우선 조건:

- `template`, `jinja` 같은 일반 검색/학습 의도 텍스트
- 문서/상품 조회에서 braces 관련 문자열이 단순 키워드인 경우

고정 규칙:

```text
- response status/bytes만으로 실행 성공을 판단하지 않는다.
- POST body에만 payload가 있을 경우 Apache access log만으로 원문을 추정하지 않는다.
- 기존 l3_ssti_webshell_context와 중복되지 않도록 독립 SSTI fixture를 구성한다.
```

## 6. 기존 module 확장 여부

- `l3_hints.py`의 기존 SSTI pattern으로 1차 fixture 후보를 평가 가능한지 먼저 확인한다.
- 신규 pattern 필요성은 fixture dry-run 결과를 본 뒤에만 판단한다.
- 새 module 생성은 보류한다.

변경 금지 범위:

- shared attack/search policy 변경 금지
- normal search false-positive handling 변경 금지
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지

## 7. Stage dry-run regression 추가 여부

판단 기준:

- prepare regression만 추가하면 hint/candidate 경계 확인은 가능하다.
- stage dry-run regression까지 추가하면 Stage2 report input candidate/context 전달 일관성까지 검증 가능하다.

권장 판단:

- 1차 도입은 prepare regression + stage dry-run regression 동시 추가를 권장한다.
- actual LLM spot check는 필수는 아니며, wording risk가 반복되거나 dry-run에서 해석 경계가 불명확할 때 선택 수행한다.

## 8. 권장 1차 fixture

추천:

- `l3_ssti_template_expression_context`

후순위:

- `ssti_benign_template_search_context`

## 9. 금지 wording

금지 표현:

- SSTI executed
- template expression evaluated
- RCE succeeded
- command executed
- server compromised
- evaluated result returned
- template engine confirmed

허용 wording:

- SSTI-like payload observed
- template-expression-like payload observed
- requires manual review
- Apache logs alone do not confirm template execution

## 10. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- 첫 구현 후보는 `l3_ssti_template_expression_context`로 두는 것이 적절하다.
- fixture 추가 전 확인할 것:
  - 기존 `l3_ssti_webshell_context`와 중복되지 않는 독립 SSTI 샘플인지
  - benign template/search baseline 과승격 방지 조건이 expected에 충분히 반영되는지
  - success 단정 금지 wording과 Apache logs-only 경계가 유지되는지
  - stage dry-run input에서도 candidate/context가 일관되게 보존되는지
- 코드 수정은 다음 작업으로 분리한다.
