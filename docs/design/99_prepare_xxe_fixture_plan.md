# 99_prepare_xxe_fixture_plan

- 문서 상태: XXE / XML parser abuse attempt fixture plan (1차 regression 반영 완료)
- 기준 시점: 2026-05-07
- 목적: XXE / XML parser abuse attempt coverage를 fixture/regression 후보로 좁히고, Apache logs-only evidence boundary를 유지한 채 추가 여부를 판단한다.

관련 문서:

- [99_prepare_xxe_coverage_plan.md](./99_prepare_xxe_coverage_plan.md)
- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssti_coverage_plan.md](./99_prepare_ssti_coverage_plan.md)
- [99_prepare_open_redirect_coverage_plan.md](./99_prepare_open_redirect_coverage_plan.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_deferred_split_items.md](./99_prepare_deferred_split_items.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "xxe\|DOCTYPE\|ENTITY\|SYSTEM\|file:///\|external entity\|xml" src tests docs
```

확인 요약:

```text
- src/prepare/l3_hints.py에 `detect_xxe_hints` 최소 패턴이 추가되어 XXE-like marker를 보존한다.
- src/prepare/file_disclosure_hints.py와 SSRF hint 의미는 변경되지 않았고 경계는 유지된다.
- `l3_xxe_external_entity_context` fixture/expected가 추가되어 1차 regression이 반영되었다.
- Apache access log에서는 raw POST body가 비가시적인 경우가 많아 body-only XML payload 원문을 추정할 수 없다.
```

## 1. 목적

- coverage plan에서 정한 XXE 후보를 fixture/regression 관점으로 좁힌다.
- 바로 구현하지 않고 fixture 설계와 expected 확인 포인트를 고정한다.
- file read, external entity resolution, SSRF success, XML parser vulnerability를 단정하지 않는 기준을 고정한다.

## 2. 현재 coverage 확인 결과

XXE 관련 기존 hint/module/fixture 여부:

- `src/prepare/l3_hints.py`
  - `detect_xxe_hints` 최소 패턴이 반영됨
  - SSRF 관련 detector(`detect_ssrf_hints`, `classify_ssrf_target`)는 존재
- `src/prepare/file_disclosure_hints.py`
  - file disclosure wrapper/resource signal은 존재
  - XML parser abuse 전용 signal은 없음
- `tests/fixtures`, `tests/expected`
  - `l3_xxe_external_entity_context` 추가 완료

기존 family와의 관계:

- file_disclosure_hints 경계:
  - `file://` marker가 보여도 file read success 단정 금지
- SSRF 경계:
  - external entity URL은 SSRF-like intent와 겹칠 수 있음
  - external/internal request success 단정 금지
- L3 hints 경계:
  - XXE-like marker는 `l3:xxe_probe`, `xxe:*`로 보존하고 success 단정으로 확장하지 않음

현재 regression 기준:

- prepare regression `pass=25 warn=0 fail=0`
- stage dry-run regression `pass=19 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

현재 신규 coverage 완료 목록:

- `l3_ssrf_metadata_endpoint_context`
- `l3_log4shell_obfuscated_payload_context`
- `l3_webshell_admin_tool_probe_context`
- `l3_graphql_introspection_context`
- `l3_open_redirect_external_url_context`
- `l3_ssti_template_expression_context`
- `l3_xxe_external_entity_context`

## 3. fixture 후보

비교 후보:

- external entity marker in query/path
  - `GET /xml?data=<!DOCTYPE%20foo%20[<!ENTITY%20xxe%20SYSTEM%20%22file:///etc/passwd%22>]>`
  - `GET /api/xml?payload=<!ENTITY%20xxe%20SYSTEM%20%22http://external.example/xxe%22>`
- XML endpoint path baseline
  - `GET /xml`
  - `GET /api/xml`
  - `GET /soap`
- benign XML/search baseline
  - `GET /docs?topic=xml`
  - `GET /api/search?q=doctype`
  - `GET /feed.xml`

주의 사항:

- URL encoding 형태를 fixture에 사용할 수 있다.
- raw POST body에만 존재하는 XML payload는 Apache access log만으로 볼 수 없으므로 1차 fixture 범위에서 제외한다.

## 4. 후보별 expected 검증 포인트

각 fixture별 공통 확인:

- XXE-like marker candidate/context 보존 여부
- `DOCTYPE`/`ENTITY`/`SYSTEM`/`file://` 또는 external entity hint 확인 여부
- benign XML endpoint baseline이 analysis candidate로 과승격되지 않는지
- benign XML/search baseline이 analysis candidate로 과승격되지 않는지
- Stage2 report input에 candidate/context 유지 여부
- 성공 단정 문구 없음
- `status_code=200` 또는 `response_body_bytes`만으로 entity resolution/file read 성공 확정하지 않음

## 5. candidate vs context-only 기준

analysis candidate 가능 조건:

- query/path에 `DOCTYPE` / `ENTITY` / `SYSTEM` marker가 명확히 보이는 경우
- `file:///` 또는 external entity URL이 marker 내부에 직접 보이는 경우

context-only 또는 low signal 우선 조건:

- `/xml`, `/api/xml`, `/soap` 단순 endpoint 접근
- `feed.xml` 같은 정상 XML/static resource 접근
- `q=doctype` 같은 검색성 요청

고정 규칙:

- POST body에만 payload가 있을 경우 Apache access log만으로 payload 원문을 추정하지 않는다.
- `status=200` 또는 `response_body_bytes`를 file read/entity resolution 성공 근거로 사용하지 않는다.

## 6. 기존 module 확장 여부

검토 항목:

- `l3_hints.py`에 최소 XXE-like hint 추가가 적절한지
- file_disclosure_hints 경계 유지
  - `file://` marker가 있어도 file read success 단정 금지
- SSRF hints 경계 유지
  - external entity URL은 SSRF-like intent와 겹칠 수 있음
  - external request success 단정 금지

보류/금지 항목:

```text
- 새 module 생성 보류
- shared attack/search policy 변경 금지
- normal search false-positive handling 변경 금지
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지
```

## 7. Stage dry-run regression 추가 여부

판단 항목:

- prepare regression만 추가할지
- stage dry-run regression까지 추가할지
- actual LLM spot check가 필요한지

권장:

- 1차 fixture는 prepare + stage dry-run expected까지 함께 검토한다.
- dry-run expected 반영 후 필요 시 actual LLM spot check를 선택적으로 수행한다.

## 8. 권장 1차 fixture

추천:

- `l3_xxe_external_entity_context` (완료)

후순위:

- `xxe_xml_endpoint_baseline_context` (필요 시 선택 후보)

참고:

- fixture naming은 기존 repo convention과 기존 prepare_regression naming 규칙에 맞춰 최종 확정한다.

## 9. 금지 wording

금지:

- XXE succeeded
- external entity resolved
- file read succeeded
- /etc/passwd returned
- SSRF succeeded
- XML parser vulnerable
- response body contained file contents
- internal request success
- credential theft
- server compromised

허용:

- XXE-like marker observed
- external-entity-like payload observed
- XML parser abuse attempt pattern
- requires manual review
- Apache logs alone do not confirm entity resolution or file read

## 10. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- `l3_xxe_external_entity_context` 1차 regression은 완료되었다.
- fixture 추가 전 확인할 것:
  - query/path에서 직접 관찰 가능한 marker만 candidate로 승격되는지
  - XML endpoint baseline/benign search baseline이 과승격되지 않는지
  - success 확정 wording이 expected/Stage2 입력에서 발생하지 않는지
  - Apache logs-only 경계와 raw POST body 비가시성 원칙이 유지되는지
- 코드 수정은 다음 작업으로 분리한다.
- 다음 후보는 API key / secret token probe 또는 Webshell command query 중에서 선택한다.
