# 99_proxy_error_check_scenario_extension_review

- 문서 상태: proxy error check scenario extension review
- 기준 시점: 2026-05-22
- 목적: Juice Shop reverse proxy v2 `proxy_error_check` 결과를 기준으로, 해당 run을 정규 S01~S15 scenario catalog에 편입할지 아니면 별도 availability extension 후보로 유지할지 보수적으로 검토한다.

관련 문서:

- [99_observability_run_summary_index.md](./99_observability_run_summary_index.md)
- [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md)
- [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_prepare_new_attack_coverage_candidate_review.md](./99_prepare_new_attack_coverage_candidate_review.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 목적

- `proxy_error_check`를 S01~S15와 같은 정규 scenario로 다뤄야 하는지 검토한다.
- 이번 문서는 catalog 확정 문서가 아니라 review 문서다.
- 이번 단계에서는 코드, runner, prepare, explain label detector, scoring/filtering을 바꾸지 않는다.

## 2. 배경

현재 관찰 기준:

- v2 3-way observability baseline은 완료 상태다.
- PHP sample direct app: `obs_php_sample_v2_001`
- OpenCart front-controller PHP app: `obs_opencart_v2_001`
- Juice Shop reverse proxy backend app: `obs_juiceshop_proxy_v2_001`

추가 관찰 run:

- Juice Shop v2 proxy error check: `obs_juiceshop_proxy_v2_error_check_001`
- 관련 dry-run: `obs_juiceshop_proxy_v2_error_check_001_current_dryrun`

이번 run에서 확인된 핵심 분포:

- `candidate_count=2`
- `demotion_candidate_status_error_only=1`
- `keep_candidate_payload=1`

관찰 결과 요약:

- payload 없는 `GET /` 503은 status/error-only bucket으로 내려간다.
- SQLi 구조가 있는 `GET /search` 503은 payload candidate로 유지된다.
- 이 차이는 candidate policy 상 request pattern 보존 여부를 보여주지만, 503 자체를 공격 성공이나 compromise evidence로 해석하게 만들지는 않는다.

## 3. 해석 기준

이번 검토에서 반드시 유지하는 Apache logs-only guardrail:

- `status_code=200`만으로 공격 성공, 침해 성공, 내부 처리 성공을 단정하지 않는다.
- `status_code=404/500/503`만으로 취약점, 공격 성공, 침해 성공을 단정하지 않는다.
- `response_body_bytes`, `content_type`, `text/html`만으로 파일 노출, 정보 유출, 내부 오류 상세 노출을 단정하지 않는다.
- POST 요청 존재만으로 로그인 성공, 업로드 저장 성공을 단정하지 않는다.
- raw POST body, response body, DB 결과, 브라우저 실행 여부를 추론하지 않는다.
- `proxy` / `proxy_http` error는 backend availability evidence이지 compromise evidence가 아니다.
- context-only 신호를 finding 또는 incident로 승격하지 않는다.
- Web UI에서 severity, category, verdict를 재계산하지 않는다.
- prepare/scoring/filtering 변경과 broad demotion 재정의는 이번 문서 범위가 아니다.

## 4. 현재 결론

`proxy_error_check`는 당장 정규 S01~S15에 편입하지 않는다.

현재 결론:

- 별도 availability extension 후보로 둔다.
- 공격/침해 시나리오가 아니라 backend availability context 관찰 run으로 본다.
- 정규 scenario catalog의 공격/행위 taxonomy와 바로 같은 층위로 합치지 않는다.
- prepare/scoring/filtering 변경은 없다.
- `scripts/explain_prepare_candidates.py`의 label detector 확장도 이번에는 하지 않는다.

보수적 유지 이유:

- 이번 run이 보여준 것은 backend unavailable 상황에서 candidate policy가 payload 유무를 어떻게 나누는지에 가깝다.
- 이는 attack success proof보다 availability context의 분류/표현 문제에 더 가깝다.
- 같은 `503`이라도 payload 없는 baseline request와 payload가 있는 request를 구분할 수는 있지만, 그 차이가 scenario catalog 편입을 곧바로 정당화하지는 않는다.

## 5. Extension 후보 naming

아직 최종 naming은 확정하지 않는다. 아래는 후보안이다.

PX 계열 후보:

- `PX01 backend_unavailable_baseline`
- `PX02 backend_unavailable_with_payload_pattern`
- `PX03 backend_recovered`

AV 계열 후보:

- `AV01 backend_unavailable_baseline`
- `AV02 backend_unavailable_with_payload_pattern`
- `AV03 backend_recovered`

비교 메모:

- `PXxx`는 reverse proxy 맥락이 더 직접적으로 보인다.
- `AVxx`는 availability extension이라는 의미가 더 넓고 vendor/app 중립적이다.
- 현재 단계에서는 어느 쪽도 확정하지 않고, 후속 catalog 초안에서만 다시 비교한다.

## 6. Interpretation Policy

`proxy_error_check`를 후속 문서에서 다룰 때의 해석 정책:

- `503` / `proxy_http` / backend unavailable 계열은 backend availability evidence로만 읽는다.
- payload가 함께 있어도 request-pattern candidate일 뿐이며, exploit success proof가 아니다.
- SQLi-like structure가 남아 있어도 DB 영향, query execution success, data exfiltration을 단정하지 않는다.
- error page 또는 HTML 응답이 보여도 파일 노출, 내부 경로 노출, 민감 정보 유출을 단정하지 않는다.
- 해당 run은 "공격이 성공했다"보다 "availability error 상태에서도 payload-bearing request는 candidate로 남을 수 있다"는 관찰에 가깝다.

## 7. Implementation Boundary

이번 문서에서 하지 않는 것:

- scenario catalog 정의 변경 없음
- runner 변경 없음
- prepare 변경 없음
- `scripts/explain_prepare_candidates.py` label detector 변경 없음
- scoring/filtering 변경 없음
- Web UI badge/label 확장 없음

필요하다면 다음 단계에서만 별도 설계를 연다.

가능한 다음 단계 예시:

- availability extension catalog 초안 작성
- external client run을 포함한 error-heavy 표본 추가 수집
- error log의 `request_id` 연결 안정성 점검 범위 정의
- Web UI에서 read-only context badge를 어떻게 보여줄지 문서 설계

## 8. Open Questions

- `proxy_error_check`를 S01~S15처럼 logical scenario로 봐야 하는가
- 아니면 availability extension으로 별도 관리해야 하는가
- external client run과 결합해 재현 범위를 넓혀야 하는가
- Apache error log와 access log 사이 `request_id` 연결 안정성을 어디까지 검증해야 하는가
- reverse proxy 전용 naming이 적절한가, 아니면 app-agnostic availability naming이 더 적절한가

## 9. Recommended Next Step

- 우선은 문서-only review 상태로 유지한다.
- 다음 단계가 필요하면 scenario catalog extension 초안을 별도 문서로 작성한다.
- 그 전까지는 `proxy_error_check`를 backend availability context 관찰 run으로만 유지한다.
- 정규 S01~S15 편입, label detector 확장, prepare/scoring/filtering 변경은 모두 보류한다.
