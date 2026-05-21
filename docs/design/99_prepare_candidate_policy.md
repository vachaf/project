# 99_prepare_candidate_policy

- 기준 시점: 2026-05-21
- 문서 역할: prepare candidate policy의 현재 기준 문서
- 관련 historical 문서:
  - [99_prepare_php_sample_candidate_policy_review.md](../archive/design/99_prepare_php_sample_candidate_policy_review.md)
  - [99_prepare_upload_multipart_sql_comment_false_positive_review.md](../archive/design/99_prepare_upload_multipart_sql_comment_false_positive_review.md)
  - [99_prepare_status_error_only_candidate_demotion_review.md](../archive/design/99_prepare_status_error_only_candidate_demotion_review.md)
  - [99_prepare_scanner_probe_context_candidate_demotion_review.md](../archive/design/99_prepare_scanner_probe_context_candidate_demotion_review.md)
  - [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)

## 1. 현재 결론

현재 prepare candidate policy에서 **실제로 로직에 반영된 것**과 **관찰/검토만 한 것**은 아래처럼 구분한다.

### 1.1 실제 로직에 반영됨

- upload-like POST에서 `sqli:sql_comment` 단독 약신호를 strong SQLi처럼 과분류하지 않도록 하는 narrow guard
- diagnostic helper(`scripts/explain_prepare_candidates.py`)의 policy bucket 정리

### 1.2 아직 로직에 반영되지 않음

- broad status/error-only demotion
- scanner/probe context candidate demotion
- topology 자체를 이용한 broad demotion
- proxy error context의 정식 scoring/filtering 반영

즉, 현재 단계는 “candidate policy를 관찰 가능하게 정리한 상태”이지, broad demotion을 실제 prepare에 넣은 상태가 아니다.

## 2. 실제 반영된 현재 정책

### 2.1 upload/sql-comment narrow guard

현재 반영 범위:

```text
POST
+ upload-like/multipart context
+ sqli:sql_comment 단독 약신호
+ logged target에 더 강한 SQLi 구조 없음
```

이 경우:

- strong SQLi로 과분류하지 않는다.
- 약한 upload/sql-comment context로 본다.
- candidate visibility 자체는 유지할 수 있다.

이 정책이 **의미하지 않는 것**:

- upload 성공/실패를 확정하지 않는다.
- 파일 저장 성공, webshell 업로드 성공, 서버 침해 성공을 단정하지 않는다.
- raw POST body나 response body를 복원하지 않는다.

### 2.2 diagnostic helper의 의미

`scripts/explain_prepare_candidates.py`는 다음 역할만 한다.

- 왜 threshold를 넘었는지 설명
- policy_class를 review bucket으로 분류

이 도구는 다음을 하지 않는다.

- prepare score 변경
- candidate 승격/강등
- severity/category/verdict 재계산
- Web UI 판단 변경

## 3. review-only 상태로 남겨둔 정책

아래 항목은 **검토됨/관찰됨**이지, **실제 로직 반영**이 아니다.

### 3.1 status/error-only demotion

관찰 내용:

- `error_status(+2) + error_linked(+2)`만으로 threshold를 넘는 row가 있다.
- direct PHP / error-heavy 표본에서는 이 bucket을 review 대상으로 분리해 볼 근거가 생겼다.

현재 결론:

- broad demotion은 아직 넣지 않는다.
- 실제 prepare/scoring/filtering 변경은 보류다.

### 3.2 scanner/probe context demotion

관찰 내용:

- `/admin`, `/.env`, `/wp-login.php`, not-found burst 같은 row는 `probing_sequence`, `sensitive_path_probe`, `mixed_baseline_scanner`, `ip_behavior` 같은 context summary와 중복해서 보일 수 있다.

현재 결론:

- context summary가 있다는 이유만으로 broad demotion을 바로 넣지 않는다.
- explicit payload 후보는 유지한다.
- review artifact와 distribution 표본만 축적 중이다.

### 3.3 topology interpretation context

다음은 interpretation context이지 scoring/severity/verdict 변경 근거가 아니다.

- `fallback_200_candidate`
- `backend_fallback_200_candidate`
- reverse proxy / front-controller / redirect-follow / `_route_` context
- proxy error / backend unavailable context

현재 결론:

- context로는 유지한다.
- broad demotion 또는 incident 생성 기준으로 쓰지 않는다.

## 4. Apache logs-only guardrail

이 문서에서 유지하는 해석 한계:

- Apache access/security/error log만으로 POST body, response body, DB 결과, 브라우저 실행 결과를 단정하지 않는다.
- 로그인 성공, 계정 탈취 성공, 서버 침해 성공, 업로드 저장 성공, 파일 존재, 정적 리소스 노출, admin 접근 성공을 단정하지 않는다.
- `status_code=200`, `status_code=404`, `response_body_bytes`, `resp_content_type`, `handler`, route 이름, product/category 이름, 특정 UA/IP만으로 공격 성공을 단정하지 않는다.
- `server-status` 관찰은 topology/client context를 포함해 해석하며, 외부 노출 성공을 자동 단정하지 않는다.
- Web UI는 read-only이며 새 보안 판단/관계/심각도/incident를 만들지 않는다.

## 5. 현재 읽는 순서

1. 이 문서에서 실제 반영 정책을 확인한다.
2. [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)에서 distribution/history를 본다.
3. 세부 검토 원문이 필요하면 archive 문서를 본다.

## 6. 다음 관찰 포인트

- 외부 client 기반 error-heavy run이 필요한지
- `proxy_error_check`를 정식 scenario catalog extension으로 뺄지
- OpenCart v2 추가 표본이 필요한지
- `mod_remoteip`/remoteIP 환경 표본이 필요한지

이 항목들은 현재도 **관찰 후보**이며, 아직 prepare 정책 반영 결정이 아니다.
