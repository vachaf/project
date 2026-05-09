# 99_prepare_xxe_coverage_plan

- 문서 상태: XXE / XML parser abuse attempt coverage plan (1차 regression 반영 완료)
- 기준 시점: 2026-05-07
- 목적: XXE / XML parser abuse attempt 1차 regression 반영 상태를 정리하고, Apache logs-only evidence boundary를 유지한 채 후속 보강 후보를 판단한다.

관련 문서:

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
grep -RIn "xxe\|DOCTYPE\|ENTITY\|SYSTEM\|file:///\|external entity" src tests docs
```

확인 요약:

```text
- src/prepare/l3_hints.py에 `detect_xxe_hints` 최소 패턴이 추가되어 `DOCTYPE`/`ENTITY`/`SYSTEM`/`file://`/external entity URL marker를 XXE hint 경로로 보존한다.
- src/prepare_llm_input.py는 XXE hint 연동만 최소 보강되었고 shared attack/search policy, normal search false-positive handling, detect_decoded_attack_hints는 변경되지 않았다.
- tests/fixtures/prepare_regression/l3_xxe_external_entity_context.json 및 prepare/stage dry-run expected가 추가되어 1차 regression이 완료되었다.
- Apache access log는 raw POST body 원문이 비가시적인 경우가 많아 XML payload 관측면이 제한된다.
```

## 1. 목적

- XXE / XML parser abuse attempt coverage 후보를 검토한다.
- file read, external entity resolution, SSRF success, XML parser vulnerability를 단정하지 않는 기준을 고정한다.
- 이번 문서는 구현 코드 작성이 아니라 coverage plan 문서다.
- fixture/regression 추가 여부를 판단하기 위한 기준 문서로 유지한다.

## 2. 현재 상태

기존 module 경계 관계:

- `src/prepare/l3_hints.py`
  - `detect_ssrf_hints`, `classify_ssrf_target`가 URL target 기반 SSRF-like signal을 처리한다.
  - `detect_xxe_hints`가 XXE-like marker를 보수적으로 처리한다.
- `src/prepare/file_disclosure_hints.py`
  - `detect_file_disclosure_hints`가 php wrapper/resource 계열 file disclosure 시도 신호를 처리한다.
  - XML parser abuse 전용 marker는 현재 없다.

XXE 관련 hint/module/fixture 확인 결과:

- XXE 전용 hint/module:
  - `detect_xxe_hints`(최소 패턴)
- XXE 전용 fixture/expected:
  - `l3_xxe_external_entity_context`
- XXE 관련 설계/후보 문서:
  - `docs/design/99_prepare_p2_attack_coverage_candidate_review.md`
  - `docs/design/99_prepare_new_attack_coverage_candidate_review.md`

Apache logs-only 한계:

- raw POST body가 Apache access log에 보이지 않는 케이스가 많다.
- 따라서 body-only XML payload는 로그만으로 원문을 확정할 수 없다.

현재 regression 상태:

- 완료된 신규 coverage regression:
  - `l3_ssrf_metadata_endpoint_context`
  - `l3_log4shell_obfuscated_payload_context`
  - `l3_webshell_admin_tool_probe_context`
  - `l3_graphql_introspection_context`
  - `l3_open_redirect_external_url_context`
  - `l3_ssti_template_expression_context`
  - `l3_xxe_external_entity_context`
- prepare regression `pass=25 warn=0 fail=0`
- stage dry-run regression `pass=19 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. 관찰 가능한 signal

Apache logs-only 기준에서 관찰 가능한 XXE/XML parser abuse signal:

- `<!DOCTYPE`
- `<!ENTITY`
- `SYSTEM "file:///etc/passwd"`
- `SYSTEM "http://external.example/xxe"`
- query/path에 포함된 XML/ENTITY-like marker
- XML endpoint path
  - `/xml`
  - `/api/xml`
  - `/upload`
  - `/soap`
- status/bytes/timing metadata

## 4. Apache logs-only로 단정 금지

아래 항목은 Apache access logs만으로 단정하지 않는다.

- XXE succeeded
- external entity resolved
- file read succeeded
- `/etc/passwd` returned
- SSRF succeeded
- XML parser vulnerable
- response body contained file contents
- internal request success
- credential theft
- server compromise

보수적 해석 원칙:

```text
- XML/ENTITY-like marker는 request surface signal이다.
- status_code, response_body_bytes, timing metadata는 보조 signal이지 결과 확정 근거가 아니다.
- raw POST body/response body 원문이 없으면 entity resolution 또는 file read 여부를 확정하지 않는다.
```

## 5. 기존 module과의 관계

- `file_disclosure_hints` 경계:
  - file read/exposure 성공 단정 금지 원칙을 유지한다.
  - XXE 문맥에서도 동일하게 성공 단정으로 확장하지 않는다.
- SSRF hints 경계:
  - external entity URL은 SSRF-like intent와 신호가 겹칠 수 있다.
  - SSRF 관련 기존 분류와 충돌 없이 context를 분리해야 한다.
- `l3_hints.py` 경계:
  - XXE-like marker를 L3 hint로 추가할지 여부를 검토한다.
  - 이번 문서는 구현 지시가 아니라 검토 문서다.

변경 금지 고정:

```text
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지
- shared attack/search policy 변경 금지
- normal search false-positive handling 변경 금지
```

## 6. candidate vs context-only 기준

analysis candidate 가능 조건:

- query/path에 `DOCTYPE`/`ENTITY` marker가 명확히 관찰되는 경우
- `SYSTEM "file:///..."`, `SYSTEM "http://..."` 형태처럼 external-entity-like 의도가 드러나는 경우
- XML endpoint probing과 marker가 같은 request surface에서 함께 관찰되는 경우

context-only 또는 low signal 우선 조건:

- XML endpoint 단순 접근만 보이는 경우
- 일반 문서/검색성 XML 키워드 요청
- payload marker 직접성이 약한 경우

고정 규칙:

```text
- POST body에만 XML payload가 있을 경우 Apache access log만으로 payload 원문을 추정하지 않는다.
- status_code/response_body_bytes만으로 file read/external entity resolution 성공을 단정하지 않는다.
- endpoint path만으로 XML parser vulnerability를 단정하지 않는다.
```

## 7. 반영된 Fixture/regression

후보 fixture:

- `l3_xxe_external_entity_context`
  - `GET /xml?data=<!DOCTYPE...`
  - `GET /api/xml?payload=<!ENTITY...`

benign baseline:

- `GET /docs?topic=xml`
- `GET /api/search?q=doctype`
- `GET /feed.xml`

expected 확인 포인트:

- XXE-like marker candidate/context 보존
- XXE/external entity hint 확인
- benign XML/search baseline 과승격 방지
- Stage2 input에 candidate/context 유지
- success wording 없음

## 8. Stage2 wording/lint guard 필요 여부

필요하다.

금지 표현:

- XXE succeeded
- external entity resolved
- file read succeeded
- /etc/passwd returned
- SSRF succeeded
- XML parser vulnerable
- response body contained file contents

허용 표현:

- XXE-like marker observed
- external-entity-like payload observed
- XML parser abuse attempt pattern
- requires manual review
- Apache logs alone do not confirm entity resolution or file read

## 9. 권장 1차 fixture 후보

추천:

- `l3_xxe_external_entity_context`

후순위:

- `xxe_xml_endpoint_baseline_context`

## 10. 검증 기준

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- `l3_xxe_external_entity_context` 기준 XXE / XML parser abuse attempt 1차 regression은 완료되었다.
- file read, external entity resolution, SSRF success, XML parser vulnerability 단정 금지 원칙은 유지한다.
- raw POST body/response body 원문 비가시성 전제를 유지하며, status/bytes만으로 성공을 확정하지 않는다.
- 다음 후보는 API key / secret token probe 또는 Webshell command query 중에서 선택한다.
