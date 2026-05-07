# 99_prepare_open_redirect_fixture_plan

- 문서 상태: Open redirect / redirect abuse attempt fixture plan
- 기준 시점: 2026-05-07
- 목적: Open redirect / redirect abuse attempt coverage plan 이후 실제 fixture/regression 추가 여부를 판단하기 위한 기준을 고정한다.

관련 문서:

- [99_prepare_open_redirect_coverage_plan.md](./99_prepare_open_redirect_coverage_plan.md)
- [99_prepare_p2_attack_coverage_candidate_review.md](./99_prepare_p2_attack_coverage_candidate_review.md)
- [99_prepare_graphql_introspection_coverage_plan.md](./99_prepare_graphql_introspection_coverage_plan.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [99_prepare_ssrf_log4shell_coverage_plan.md](./99_prepare_ssrf_log4shell_coverage_plan.md)
- [../../src/prepare/README.md](../../src/prepare/README.md)
- [../진행상황.md](../진행상황.md)

작업 전 확인:

```bash
grep -RIn "redirect=\|next=\|return=\|continue=\|callback=\|url=\|open_redirect\|open redirect" src tests docs
```

확인 요약:

```text
- redirect-like parameter 신호는 SSRF coverage 및 P2 후보 비교 문서에 이미 분산되어 있다.
- Open redirect 전용 fixture/regression 케이스는 아직 없는 상태다.
- 이번 작업은 fixture plan 문서 작성이며 fixture/expected/code 수정은 수행하지 않는다.
```

## 1. 목적

- Open redirect coverage 후보를 fixture/regression 관점으로 좁힌다.
- 바로 구현하지 않고 fixture 설계와 expected 확인 포인트를 고정한다.

## 2. 현재 coverage 확인 결과

Open redirect 관련 기존 hint/module/fixture 확인:

- Open redirect 전용 hint module은 없다.
- Open redirect 전용 fixture/expected 회귀 케이스는 아직 없다.
- URL parameter 계열 신호(`url`, `callback`, `next`, `return`, `continue`, `redirect`)는 SSRF 문맥과 일부 중첩된다.

SSRF URL parameter와의 중복 여부:

- `url=`/`callback=`/`next=`는 SSRF/Open redirect 양쪽에서 사용 가능하다.
- metadata/internal target 신호는 SSRF 해석 우선이 필요하다.
- external URL + redirect-like parameter 조합은 Open redirect-like 시도로 분리 검토 가능하다.

현재 regression 기준:

- prepare regression `pass=22 warn=0 fail=0`
- stage dry-run regression `pass=16 warn=0 fail=0`
- Stage2 report quality tests `14 passed`

## 3. fixture 후보

아래 후보를 비교한다.

external redirect-like parameter:

- `GET /login?next=https://external.example/`
- `GET /redirect?url=//external.example/`
- `GET /oauth/authorize?continue=https://external.example/`

benign relative redirect baseline:

- `GET /login?next=/account`
- `GET /checkout?return=/cart`

benign URL/documentation baseline:

- `GET /product?url=https://example.com/manual.pdf`
- `GET /search?q=redirect`

## 4. 후보별 expected 검증 포인트

각 fixture에서 아래 항목을 확인한다.

- external redirect-like parameter candidate/context 보존 여부
- open-redirect-like hint 확인 여부
- benign relative redirect baseline이 analysis candidate로 과승격되지 않는지
- benign documentation URL이 analysis candidate로 과승격되지 않는지
- Stage2 report input에 candidate/context 유지 여부
- success wording 없음
- status_code=200/302/3xx 또는 bytes만으로 redirect 성공 확정하지 않음

## 5. candidate vs context-only 기준

analysis candidate 가능 조건:

- redirect-like parameter + external URL 조합
- protocol-relative external URL(`//external.example/`) 조합

context-only 또는 baseline 우선 조건:

- same-site relative URL(`next=/account`, `return=/cart`)
- documentation/manual URL(`url=https://example.com/manual.pdf`)
- 검색 질의(`q=redirect`)

추가 기준:

- repeated probing은 success 판정이 아니라 context summary 후보로 관리
- 3xx/status/bytes로 redirect success를 단정하지 않음

## 6. SSRF와의 경계

- `url`/`callback`/`next` parameter는 SSRF와 Open redirect 모두에서 사용 가능하다.
- metadata/internal target이면 SSRF 우선 해석.
- external domain + redirect-like parameter이면 Open redirect-like attempt 후보.
- 단순 URL parameter만으로 취약점 확정 금지.

경계 우선순위(초안):

```text
1) metadata/internal target 직접성 높음 -> SSRF 우선
2) external URL + redirect-like parameter 반복 -> Open redirect-like attempt 후보
3) same-site/documentation/search 성격 -> baseline/context
```

## 7. 기존 module 확장 여부

- `l3_hints.py`에 최소 open redirect-like hint 추가가 적절한지 검토한다.
- 새 module 생성은 보류한다.

변경 금지 범위:

- shared attack/search policy 변경 금지
- normal search false-positive handling 변경 금지
- detect_decoded_attack_hints 변경 금지
- supporting_events/scoring/filtering 변경 금지
- Stage2 reporter 변경 금지

## 8. 권장 1차 fixture

추천:

- `l3_open_redirect_external_url_context`

후순위:

- `open_redirect_baseline_context`

## 9. 금지 wording

금지 표현:

- open redirect confirmed
- redirect succeeded
- victim followed redirect
- phishing succeeded
- credential theft
- browser redirected
- exploit succeeded

허용 wording:

- open-redirect-like parameter observed
- external URL in redirect-like parameter
- redirect abuse attempt pattern
- requires manual review
- Apache logs alone do not confirm redirect success

## 10. 검증 명령

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python -m pytest tests/test_stage2_report_quality.py
```

## 11. 결론

- 첫 구현 후보는 `l3_open_redirect_external_url_context`로 두는 것이 적절하다.
- fixture 추가 전 확인할 것:
  - SSRF 경계(내부/metadata target 우선)와 Open redirect-like 경계를 expected에서 분리했는지
  - relative/documentation baseline 과승격 방지 기준이 충분한지
  - Stage2 wording에서 redirect/phishing 성공 단정 금지 표현이 유지되는지
- 코드 수정은 다음 작업으로 분리한다.
