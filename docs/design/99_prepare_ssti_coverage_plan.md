# 99_prepare_ssti_coverage_plan

- 문서 상태: SSTI / template injection coverage plan (1차 regression 반영 완료)
- 기준 시점: 2026-05-07
- 목적: P2 다음 coverage 후보인 SSTI / template injection 계열을 검토하고, Apache logs-only evidence boundary를 먼저 고정한 뒤 fixture/regression 추가 여부를 판단한다.

관련 문서:

- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_graphql_introspection_coverage_plan.md](./99_prepare_graphql_introspection_coverage_plan.md)
- [99_prepare_open_redirect_coverage_plan.md](./99_prepare_open_redirect_coverage_plan.md)
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
- src/prepare/l3_hints.py에 detect_ssti_hints, detect_educational_ssti_search_context가 이미 존재한다.
- src/prepare_llm_input.py에서 ssti score_boost/hints 연동과 educational_ssti_context 기반 false-positive 완화가 이미 존재한다.
- tests/fixtures/prepare_regression/l3_ssti_webshell_context.json 및 대응 expected가 존재한다.
- 이번 문서는 구현이 아니라 SSTI coverage 판단 기준을 고정하는 계획 문서다.
```

## 1. 목적

- SSTI / template injection coverage 후보를 검토한다.
- template execution, expression evaluation, RCE 성공을 단정하지 않는 기준을 고정한다.
- 이번 문서는 구현 코드 작성 문서가 아니라 coverage plan 문서다.
- fixture/regression 추가 여부를 판단하기 위한 기준 문서로 유지한다.

## 2. 현재 상태

기존 SSTI 관련 신호:

- `src/prepare/l3_hints.py`
  - `detect_ssti_hints`
  - `detect_educational_ssti_search_context`
  - `l3:ssti`, `ssti:template_expression`, `ssti:jinja_expression`, `ssti:freemarker_expression` hint 경로
- `src/prepare_llm_input.py`
  - `detect_ssti_hints` 결과 연동(score_boost + reason_hints)
  - `educational_ssti_context` 감지 시 `fp_hint:ssti_keyword_without_runtime_evidence`로 과승격 완화

기존 fixture 관계:

- `tests/fixtures/prepare_regression/l3_ssti_webshell_context.json`는 SSTI(`{{7*7}}`)와 webshell command query(`/upload/shell.php?cmd=id`)가 결합된 복합 케이스다.
- `l3_ssti_template_expression_context`가 추가되어 SSTI 단독 template-expression family 1차 회귀 경계가 고정되었다.

현재 regression 상태:

- 완료된 신규 coverage regression:
  - `l3_ssrf_metadata_endpoint_context`
  - `l3_log4shell_obfuscated_payload_context`
  - `l3_webshell_admin_tool_probe_context`
  - `l3_graphql_introspection_context`
  - `l3_open_redirect_external_url_context`
  - `l3_ssti_template_expression_context`
- prepare regression `pass=24 warn=0 fail=0`
- stage dry-run regression `pass=18 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. 관찰 가능한 signal

Apache logs-only 기준에서 관찰 가능한 주요 signal:

- `{{7*7}}`
- `{{config}}`
- `${7*7}`
- `<%= 7*7 %>`
- `#{7*7}`
- template-expression-like query parameter
- status/bytes/timing metadata

## 4. Apache logs-only로 단정 금지

아래 항목은 Apache access logs만으로 단정하지 않는다.

- template execution succeeded
- expression evaluated
- RCE succeeded
- server-side template engine confirmed
- command executed
- server compromised
- response body contained evaluated result

보수적 해석 원칙:

```text
- template-expression-like marker는 request surface signal이다.
- status_code, response_body_bytes, timing metadata는 보조 signal이지 execution proof가 아니다.
- raw POST body 원문, response body 원문, runtime evaluation 결과는 Apache access log만으로 확정하지 않는다.
```

## 5. 기존 module과의 관계

- `src/prepare/l3_hints.py`의 SSTI hint 경로(`detect_ssti_hints`)와 연결해 coverage 확장이 가능하다.
- `detect_decoded_attack_hints`와의 경계는 유지한다. 이번 계획에서 decoded shared logic 변경은 다루지 않는다.
- shared attack/search policy와의 경계는 유지한다.
- normal search false-positive handling과의 경계는 유지한다.
- supporting_events/scoring/filtering은 건드리지 않는다.
- Stage2 reporter 변경은 없다.

이번 계획의 제외 범위:

```text
- detect_decoded_attack_hints 변경 없음
- shared attack/search policy 변경 없음
- normal search false-positive handling 변경 없음
- supporting_events/scoring/filtering 변경 없음
- Stage2 reporter 변경 없음
- 새 module 생성 보류
```

## 6. candidate vs context-only 기준

analysis candidate 가능 조건:

- `{{7*7}}`, `${7*7}`, `<%= 7*7 %>`, `#{7*7}`, `{{config}}` 같이 template-expression-like payload 직접성이 높은 경우
- 동일 source/request family에서 expression probing이 반복되어 탐색 패턴이 보이는 경우

context-only 또는 benign/search baseline 우선 조건:

- `template`, `jinja` 같은 일반 검색어 중심 요청
- 문서 조회/학습 의도가 강한 텍스트 검색 요청
- product/documentation query에서 braces 문자열이 단순 키워드로만 쓰인 경우

고정 규칙:

```text
- response status/bytes만으로 template execution success를 판단하지 않는다.
- POST body에만 payload가 있을 가능성은 Apache access log만으로 원문 추정하지 않는다.
- search-like 텍스트는 educational/benign baseline과 분리해 과승격을 억제한다.
```

## 7. Fixture/regression 반영

후보 fixture:

- `l3_ssti_template_expression_context`
  - `GET /search?q={{7*7}}`
  - `GET /profile?name=${7*7}`
  - `GET /template?value=<%=7*7%>`

benign baseline 후보:

- `GET /docs?topic=template`
- `GET /search?q=jinja template`
- `GET /product?name=curly-braces`

expected 확인 포인트:

- template-expression-like payload candidate/context 보존
- SSTI / template expression hint 확인
- benign template search baseline 과승격 방지
- Stage2 input에 candidate/context 유지
- success wording 없음

## 8. Stage2 wording/lint guard 필요 여부

필요하다.

금지 표현:

- SSTI executed
- template expression evaluated
- RCE succeeded
- command executed
- server compromised
- evaluated result returned

허용 표현:

- SSTI-like payload observed
- template-expression-like payload observed
- requires manual review
- Apache logs alone do not confirm template execution

## 9. 권장 1차 fixture 후보

추천:

- `l3_ssti_template_expression_context`

후순위:

- `ssti_benign_template_search_context`

## 10. 검증 기준

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- `l3_ssti_template_expression_context` 기준 SSTI / template injection 1차 regression은 완료되었다.
- 기존 `l3_ssti_webshell_context`와 분리된 SSTI 단독 family 경계가 fixture/expected에 고정되었다.
- template execution, expression evaluated, RCE 단정 금지 원칙은 유지한다.
- 다음 후보는 XXE / API key / Webshell command query 중에서 선택한다.
