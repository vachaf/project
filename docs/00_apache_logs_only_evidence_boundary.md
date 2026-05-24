# 00_apache_logs_only_evidence_boundary

- 문서 상태: canonical evidence boundary guide
- 기준 시점: 2026-05-24
- 목적: Apache logs-only 분석에서 관찰 가능한 사실과 단정하면 안 되는 보안 판정을 한곳에 고정한다.
- 범위: prepare, context summary, sliding window summary, rollup, scheduler summary, Stage1/Stage2 report, viewer payload, lint rule, 관련 설계 문서 전반

## 1. 결론

이 문서는 새로운 판정 정책을 추가하지 않는다.

기존 문서와 코드에 흩어져 있던 아래 원칙을 하나의 기준점으로 모은다.

```text
Apache access/security/error log만으로는 공격 성공, 침해 성공, 노출 성공, 인증 성공, 서버 내부 상태를 단정하지 않는다.
```

따라서 이 문서는 다음 역할을 한다.

```text
- summary/rollup 단계에서 의미가 승격되는 것을 방지한다.
- Stage1/Stage2 보고서 wording의 상한선을 고정한다.
- prepare context가 finding/security verdict로 승격되는 것을 방지한다.
- docs/design 문서들이 반복하던 evidence boundary를 한 곳에서 참조하게 한다.
- lint rule과 사람이 읽는 문서의 기준을 맞춘다.
```

현재 권장 적용 방식:

```text
docs/00_apache_logs_only_evidence_boundary.md: CREATE

docs/01_용어_가이드.md: DEFER
src/GUARDRAILS.md: DEFER
```

보류 이유:

```text
- 용어 가이드는 이 문서의 Wording Guide 섹션으로 충분하다.
- src/GUARDRAILS.md를 별도로 만들면 코드 guardrails와 중복될 수 있다.
- 지금 필요한 것은 문서 수 증가가 아니라 single source of truth다.
```

## 2. 기본 원칙

Apache 로그 기반 분석은 request/response metadata 관찰이다.

관찰 가능한 것은 아래와 같다.

```text
- 요청 시각
- 요청 출발지로 기록된 IP/peer 정보
- method
- URI / query string / raw request target
- protocol
- status code
- response body byte count
- duration / TTFB
- handler / vhost / server name
- User-Agent 등 기록된 header metadata
- Apache error/security log에 기록된 메시지
- 동일 시간대의 요청 반복, 분포, sequence, grouping
```

관찰 불가능하거나 단정할 수 없는 것은 아래와 같다.

```text
- raw POST body 원문
- response body 원문
- DB query 결과
- 애플리케이션 내부 인증 결과
- 브라우저 렌더링 또는 JavaScript 실행 여부
- 파일 시스템 내 실제 파일 존재 여부
- 업로드 파일의 저장 성공 여부
- 삭제 요청의 실제 삭제 성공 여부
- 서버 침해 또는 원격 코드 실행 성공 여부
- 사용자의 실제 계정 탈취 여부
- crawler/bot의 실제 정체
```

핵심 규칙:

```text
로그에 기록된 metadata로 관찰한 사실은 말할 수 있다.
로그에 없는 body, DB, browser, filesystem, application state는 추론하지 않는다.
```

## 2.1 오탐/미탐 균형 원칙

이 문서의 단정 금지 원칙은 의심 정황을 제거하거나 위험도를 무조건 낮추기 위한 기준이 아니다.

```text
단정 금지 != 후보 삭제
승격 금지 != 위험 신호 누락
success inference 금지 != suspicious context 제거
```

Apache 로그만으로 성공, 침해, 노출을 확정하지 않되, 관찰 가능한 suspicious context, candidate signal, 반복 패턴, payload-like 요청은 누락하지 않고 Stage1/Stage2 및 sliding window/rollup 입력에 안전한 표현으로 전달한다.

따라서 false positive를 줄이기 위해 성공 단정과 context promotion은 금지하지만, false negative를 줄이기 위해 observable suspicious evidence는 보존한다.

권장 적용 방식:

```text
- 확정 판정은 만들지 않는다.
- 관찰 가능한 의심 정황은 버리지 않는다.
- 의심 정황은 context/candidate/suspicious signal로 보존한다.
- Stage1/Stage2에는 성공 단정이 아니라 조사 우선순위와 해석 한계를 전달한다.
- rollup은 중복 제거와 요약을 수행하되 payload-like/context signal을 임의로 삭제하지 않는다.
```

## 3. 절대 단정 금지

아래 표현은 Apache logs-only 증거만으로 사용하지 않는다.

```text
- 공격 성공
- 침해 성공
- 침해 확인
- 권한 획득 확인
- 서버 장악 확인
- 원격 코드 실행 성공
- SQL injection 성공
- XSS 실행 성공
- 파일 노출 확인
- 민감정보 유출 확인
- 로그인 성공
- 계정 탈취 성공
- credential stuffing 성공
- lockout 발동 확인
- 업로드 성공
- 파일 저장 성공
- 파일 삭제 성공
- TRACE/XST 성공
- CORS 우회 성공
- protocol bypass 성공
- malformed request exploit 성공
- WordPress 존재 확인
- admin access 확인
- .env 노출 확인
- phpinfo 노출 확인
- server-status 노출 확인
- backup 파일 노출 확인
- robots.txt/sitemap.xml 내용 확인
- JavaScript 실행 확인
- product/category page 존재 확인
- crawler 정체 확인
```

금지 이유:

```text
- status_code=200은 애플리케이션 성공을 증명하지 않는다.
- text/html은 응답 본문 내용을 증명하지 않는다.
- response_body_bytes는 어떤 데이터가 노출됐는지 증명하지 않는다.
- POST metadata는 POST body와 인증 결과를 보여주지 않는다.
- URI에 민감 경로가 있어도 실제 파일 존재나 노출을 증명하지 않는다.
- User-Agent는 도구/자동화 가능성의 context일 뿐 공격 성공 근거가 아니다.
```

## 4. 허용 표현

아래 표현은 Apache logs-only 범위에서 사용할 수 있다.

```text
- 요청이 관찰됨
- 시도가 관찰됨
- 패턴이 관찰됨
- 반복 접근이 관찰됨
- 민감 경로로 보이는 URI 요청이 관찰됨
- 로그인 관련 endpoint로 보이는 POST 요청이 관찰됨
- 업로드 endpoint로 보이는 요청이 관찰됨
- 스캐너/자동화 도구와 유사한 User-Agent가 관찰됨
- 의심 패턴 후보
- context-only signal
- candidate signal
- 추가 확인 필요
- 로그만으로 성공 여부 판단 불가
- 로그만으로 노출 여부 판단 불가
- 로그만으로 인증 성공 여부 판단 불가
- 로그만으로 서버 침해 여부 판단 불가
```

권장 framing:

```text
관찰: Apache 로그에서 보이는 사실
해석 한계: 로그만으로 단정할 수 없는 것
후속 확인: 애플리케이션 로그, DB 로그, WAF 로그, 파일 시스템, response body, 인증 이벤트 등 필요한 추가 증거
```

## 5. 금지 표현과 대체 표현

| 금지 표현 | 대체 표현 |
|---|---|
| 공격 성공 | 공격 시도 또는 의심 패턴 관찰 |
| 침해 확인 | 침해 여부는 Apache 로그만으로 확인 불가 |
| SQLi 성공 | SQLi payload로 보이는 요청 관찰 |
| XSS 실행 | XSS payload로 보이는 요청 관찰 |
| 로그인 성공 | 로그인 관련 POST 요청 관찰 |
| 계정 탈취 | 계정 탈취 여부는 Apache 로그만으로 확인 불가 |
| credential stuffing 성공 | 반복 로그인 시도 패턴 관찰 |
| 파일 노출 확인 | 민감 경로 요청 관찰 |
| .env 노출 | `.env` 경로 요청 관찰 |
| phpinfo 노출 | `phpinfo` 관련 경로 요청 관찰 |
| server-status 노출 | `/server-status` 요청 관찰 |
| 업로드 성공 | 업로드 endpoint로 보이는 요청 관찰 |
| 파일 삭제 성공 | DELETE 요청 또는 삭제 endpoint 요청 관찰 |
| RCE 성공 | RCE payload로 보이는 문자열 포함 요청 관찰 |
| JS 실행 | JS 실행 여부는 로그만으로 확인 불가 |
| DB 조회 성공 | DB 결과는 Apache 로그만으로 확인 불가 |
| crawler 확인 | crawler-like User-Agent 또는 반복 수집 패턴 관찰 |
| WordPress 존재 | WordPress 관련 경로 요청 관찰 |
| admin access 성공 | admin/login 관련 경로 접근 시도 관찰 |

## 6. 상태 코드 해석 경계

`status_code`는 HTTP 처리 결과의 일부일 뿐, 애플리케이션 의미의 성공을 직접 증명하지 않는다.

```text
200:
  - HTTP 응답이 반환됐다는 관찰이다.
  - 공격 성공, 파일 노출, 로그인 성공, 취약점 성공을 증명하지 않는다.

301/302/303/307/308:
  - redirect 관찰이다.
  - 인증 성공, 우회 성공, 권한 획득을 증명하지 않는다.

401/403:
  - 접근 거부 또는 인증 필요 응답으로 볼 수 있다.
  - 공격 실패를 완전히 증명하지 않는다.

404:
  - 해당 요청 target에 대해 not found 응답이 기록됐다는 관찰이다.
  - 전체 파일 부재, 제품 부재, site structure 부재를 증명하지 않는다.

500 계열:
  - 서버 오류가 관찰됐다는 사실이다.
  - exploit 성공, 서버 장악, 데이터 유출을 증명하지 않는다.
```

권장 표현:

```text
- status_code=200 응답이 관찰됐다.
- status_code=403 응답이 관찰되어 접근 제한 가능성이 있다.
- status_code=500 응답이 관찰됐지만, 로그만으로 exploit 성공 여부는 판단할 수 없다.
```

## 7. body / byte / content-type 해석 경계

Apache access log에 남는 `response_body_bytes`, `out_bytes`, `content-type` 계열 metadata는 응답 본문 원문이 아니다.

금지:

```text
- response_body_bytes가 크므로 데이터 유출 성공이라고 단정
- text/html이므로 로그인 페이지 또는 admin 화면이 노출됐다고 단정
- JSON 응답이므로 API 결과가 노출됐다고 단정
- 응답 크기가 다르므로 SQLi blind extraction이 성공했다고 단정
```

허용:

```text
- 응답 크기 차이가 관찰됐다.
- 응답 content-type metadata가 관찰됐다.
- 동일 endpoint에서 response_body_bytes 편차가 있어 추가 확인이 필요하다.
- 본문 원문이 없어 노출 내용은 판단할 수 없다.
```

## 8. POST / auth / account behavior 해석 경계

POST 요청은 POST body 원문과 인증 결과를 보여주지 않는다.

금지:

```text
- 로그인 성공
- 비밀번호 탈취
- 계정 탈취
- credential stuffing 성공
- lockout 발동
- MFA 우회
- 세션 발급
```

허용:

```text
- 로그인 관련 endpoint로 보이는 POST 요청 관찰
- 반복적인 로그인 시도 패턴 관찰
- 여러 계정명/식별자로 보이는 query/path 패턴 관찰
- 인증 성공 여부는 Apache 로그만으로 판단 불가
```

권장 interpretation_limit:

```text
post_body_not_visible_no_auth_success_inference
```

## 9. upload / delete / file operation 해석 경계

Apache 로그만으로 파일 시스템 변경 결과를 단정하지 않는다.

금지:

```text
- 파일 업로드 성공
- 웹쉘 저장 성공
- 파일 삭제 성공
- 설정 파일 변경 성공
- 백업 파일 다운로드 성공
```

허용:

```text
- 업로드 endpoint로 보이는 요청 관찰
- multipart/form-data content-type metadata 관찰
- DELETE method 요청 관찰
- 파일 조작으로 보이는 endpoint 요청 관찰
- 실제 저장/삭제/노출 여부는 파일 시스템 또는 애플리케이션 로그 확인 필요
```

## 10. sensitive path / static file / exposure 해석 경계

민감 경로 요청은 노출 증거가 아니라 probing 또는 access attempt context다.

금지:

```text
- .env 파일 노출 확인
- backup 파일 노출 확인
- phpinfo 노출 확인
- server-status 노출 확인
- robots/sitemap 내용 확인
- static JS/CSS 안의 token 확인
- WordPress 설치 확인
- admin console 접근 성공
```

허용:

```text
- `.env` 경로 요청 관찰
- backup/archive 확장자로 보이는 경로 요청 관찰
- `/server-status` 요청 관찰
- WordPress 관련 경로 요청 관찰
- admin/login 관련 경로 접근 시도 관찰
- 실제 노출 여부는 response body 또는 서버 설정 확인 필요
```

## 11. scanner / automation / crawler 해석 경계

User-Agent, 요청 속도, 반복 패턴은 자동화 가능성을 보여주는 context일 수 있다.

금지:

```text
- 특정 User-Agent만으로 공격자 확정
- lab-* User-Agent를 공격 근거로 사용
- crawler User-Agent만으로 실제 crawler 정체 확인
- sqlmap/nikto/nmap/curl/wget/python-requests User-Agent만으로 공격 성공 판단
- 특정 IP만으로 악성 판단
```

허용:

```text
- scanner-like User-Agent 관찰
- automation-like 요청 패턴 관찰
- crawler-like User-Agent 관찰
- 동일 IP 또는 동일 UA에서 반복 요청 관찰
- 실제 도구 정체 또는 공격 성공 여부는 추가 증거 필요
```

실험환경 특화 금지:

```text
- lab-* UA를 공격 근거로 쓰지 않는다.
- 특정 실험 IP에 과적합하지 않는다.
- 특정 response size에 과적합하지 않는다.
- 특정 제품명에 과적합하지 않는다.
- 특정 route에 과적합하지 않는다.
```

## 12. protocol anomaly / malformed request 해석 경계

비정상 protocol, malformed request, unusual method는 관찰 가능한 anomaly다.

금지:

```text
- protocol bypass 성공
- malformed request exploit 성공
- 서버 침해 성공
- WAF 우회 성공
- request smuggling 성공
```

허용:

```text
- protocol anomaly 관찰
- malformed request 관찰
- unusual method 요청 관찰
- HTTP parser 또는 upstream 처리 차이 가능성
- 성공 여부는 Apache 로그만으로 판단 불가
```

## 13. summary / rollup 단계 적용 원칙

summary와 rollup은 원본 evidence보다 강한 보안 판정을 만들면 안 된다.

적용 대상:

```text
- prepare context summaries
- sliding window summaries
- sliding window rollup
- scheduler summary
- Stage1 input summaries
- Stage2 report input
- viewer payload summaries
```

금지:

```text
- context-only signal을 finding으로 승격
- candidate signal을 confirmed incident로 승격
- 반복 요청을 공격 성공으로 승격
- status_code=200을 exploit success로 승격
- response size 차이를 data exposure로 승격
- POST 요청을 auth success로 승격
```

허용:

```text
- 관찰된 요청군을 요약
- 반복 패턴을 요약
- 후보군을 묶어서 LLM 분석 비용을 줄임
- 의미 있는 context를 보존
- 로그만으로 판단할 수 없는 항목을 명시
```

summary guardrail 기준:

```text
summary_only: true
no_new_security_verdict: true
no_success_inference: true
no_body_inference: true
no_context_promotion: true
```

## 14. Stage1 / Stage2 보고서 적용 원칙

Stage1/Stage2는 Apache logs-only boundary를 넘어서는 단정 표현을 만들면 안 된다.

보고서에서 허용되는 구조:

```text
Observation:
  Apache 로그에서 관찰된 metadata와 패턴

Assessment:
  관찰 가능한 범위 내의 의심도 또는 조사 우선순위

Limitations:
  로그만으로 판단할 수 없는 항목

Recommended follow-up:
  추가 확인이 필요한 증거원
```

보고서에서 금지되는 구조:

```text
Conclusion:
  공격 성공 확인
  침해 확인
  파일 노출 확인
  로그인 성공 확인
  서버 장악 확인
```

권장 문장:

```text
- Apache 로그 기준으로는 해당 요청이 관찰됐지만, 성공 여부는 판단할 수 없다.
- 본문 원문이 없어 실제 노출된 데이터는 확인할 수 없다.
- 인증 결과는 Apache 로그만으로 확인할 수 없다.
- 추가 확인에는 애플리케이션 로그, 인증 로그, DB 로그, response body, 파일 시스템 상태가 필요하다.
```

## 15. Viewer / UI 적용 원칙

Viewer는 저장된 payload를 읽고 보여주는 도구다.

금지:

```text
- UI에서 새로운 관계 추론
- UI에서 severity/category/verdict 재계산
- context-only item을 finding/incident로 승격
- related contexts를 근거 없이 생성
- supporting events를 새로 합성
```

허용:

```text
- 저장된 finding 표시
- 저장된 context 표시
- 저장된 supporting events 표시
- 저장된 viewer_payload 표시
- source artifact와 연결된 metadata 표시
```

## 16. 코드와의 관계

이 문서는 코드 guardrails의 상위 설명 문서다.

대표 guardrails:

```python
"guardrails": {
    "summary_only": True,
    "no_new_security_verdict": True,
    "no_success_inference": True,
    "no_body_inference": True,
    "no_context_promotion": True,
}
```

모듈별 interpretation_limit 예:

```python
"interpretation_limit": "post_body_not_visible_no_auth_success_inference"
"interpretation_limit": "context_only_no_success_inference"
```

코드 변경 시 확인할 것:

```text
- 새 summary가 보안 판정을 만들지 않는가?
- context가 finding으로 승격되지 않는가?
- body/DB/browser/filesystem 상태를 추론하지 않는가?
- status_code=200을 성공 근거로 사용하지 않는가?
- 실험용 UA/IP/route/size에 과적합하지 않는가?
- lint rule이 이 문서의 wording boundary와 충돌하지 않는가?
```

## 17. 문서 작성 체크리스트

새 설계 문서, 작업일지, 진행상황 문서를 작성할 때 아래를 확인한다.

```text
[ ] Apache logs-only evidence boundary를 명시했는가?
[ ] 공격 성공/침해 성공/노출 확인 같은 단정 표현을 쓰지 않았는가?
[ ] POST body, response body, DB 결과, browser execution을 추론하지 않았는가?
[ ] status_code=200을 성공 근거로 쓰지 않았는가?
[ ] context-only signal과 finding/security verdict를 구분했는가?
[ ] summary/rollup이 원본 evidence보다 강한 의미를 만들지 않았는가?
[ ] 필요한 경우 추가 확인 증거원을 명시했는가?
```

## 18. 변경 정책

이 문서는 canonical guide로 유지한다.

변경할 때는 아래 기준을 따른다.

```text
- 새로운 금지 표현이 발견되면 이 문서에 먼저 추가한다.
- lint rule을 강화할 경우 이 문서의 wording guide와 맞춘다.
- design 문서에는 긴 원칙을 반복하지 말고 이 문서를 참조한다.
- docs/01_용어_가이드.md는 Wording Guide가 커질 때 분리한다.
- src/GUARDRAILS.md는 개발자용 체크리스트가 코드와 분리되어 필요해질 때 만든다.
```

## 18.1 적용 버전과 확장 가능성

이 문서의 boundary는 현재 Apache logs-only 파이프라인, 특히 v1.0~v1.5 sliding window / rollup 구조를 기준으로 한다.

추후 DB 감사 로그, 애플리케이션 인증 로그, WAF 로그, response body capture, 파일 무결성 로그 등 별도 증거원이 파이프라인에 공식 연동될 경우 evidence boundary는 확장될 수 있다.

다만 확장 후에도 각 증거원이 직접 관찰할 수 있는 사실과 추론하면 안 되는 판정은 별도 계약으로 명시해야 한다. 새로운 증거원이 추가되더라도 해당 증거원으로 확인할 수 없는 성공, 침해, 노출, 인증 결과는 계속 단정하지 않는다.

확장 시 필요한 최소 조건:

```text
- 새 증거원의 schema와 보존 필드가 문서화되어 있음
- 해당 증거원이 직접 관찰 가능한 사실과 불가능한 추론이 분리되어 있음
- Apache logs-only 결과와 외부 증거 결합 방식이 명시되어 있음
- Stage1/Stage2 wording과 lint rule의 boundary가 함께 갱신되어 있음
- viewer/UI가 새 증거를 표시하더라도 임의로 security verdict를 재계산하지 않음
```

권장 참조 문장:

```markdown
이 문서는 Apache logs-only evidence boundary를 따른다. 자세한 기준은 [00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 참조한다.
```

같은 `docs/` 디렉터리에서 참조할 때:

```markdown
이 문서는 Apache logs-only evidence boundary를 따른다. 자세한 기준은 [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)를 참조한다.
```
