# 99_HTML_fallback_fingerprint_구현_검토와_보류_결정

- 문서 상태: 보류 결정 메모
- 버전: v1.1
- 작성일: 2026-04-09

## 1. 결론

HTML fallback fingerprint 기능은 현재 구현/운영 기준이 아니다. 문서에서는 **보류 기능**으로 취급한다.

## 2. 이유

현재 코드 기준으로 확인되는 상태:

- `src/apache_log_shipper.py` 는 `resp_html_*` 키가 로그에 있으면 DB 컬럼으로 적재할 수 있다.
- 하지만 `resp_html_*` 값을 실제로 생성하는 상류 로직은 현재 기준 코드 범위에 없다.
- 따라서 `resp_html_*` 는 `NULL` 또는 `"-"` 상태로 남을 수 있다.

즉, 적재 경로 일부는 있어도 실제 분석에서 신뢰 가능한 운영 기능으로 쓰기 어렵다.

## 3. 현재 문서에서의 취급 기준

### 3.1 현재 사용 중인 항목

- `resp_content_type`
- `response_body_bytes`
- `raw_request_target`
- `path_normalized_from_raw_request`
- `likely_html_fallback_response`

### 3.2 현재 보류 항목

- `resp_html_norm_fingerprint`
- `resp_html_fingerprint_version`
- `resp_html_baseline_name`
- `resp_html_baseline_match`
- `resp_html_baseline_confidence`
- `resp_html_features_json`

## 4. 운영 문구 기준

문서에는 아래처럼 쓴다.

- `likely_html_fallback_response` 는 현재 사용 중인 보수 해석 기준이다.
- `resp_html_*` 는 보류 또는 선택 컬럼이다.
- `resp_html_*` 값이 비어 있다고 해서 실제 파일 노출 성공으로 해석하지 않는다.
- `resp_html_*` 를 현재 분석 파이프라인의 핵심 근거처럼 쓰지 않는다.
