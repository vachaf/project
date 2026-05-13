# 99 Apache 로그 수집 확장 계획서 범위 정정

- 문서 상태: 정정 문서
- 작성일: 2026-05-14
- 관련 문서: `docs/design/99_apache_log_collection_expansion_plan.md`

## 1. 정정 요지

`docs/design/99_apache_log_collection_expansion_plan.md`의 기준 범위에 있는 `Ubuntu Apache reverse proxy 환경` 표현은 너무 좁다.

정확한 기준 범위는 다음이다.

```text
웹단에 Apache HTTP Server를 사용하는 애플리케이션 전반
```

즉, reverse proxy 여부는 필수 전제가 아니다. Apache가 웹단에 위치한다면 다음 배치 유형을 모두 포함한다.

| 배치 유형 | 예 | 포함 여부 |
|---|---|---|
| 정적 파일 직접 서빙 | Apache document root 기반 HTML/CSS/JS/image 제공 | 포함 |
| PHP-FPM/CGI 연계 | WordPress, PHP 앱, CGI 스크립트 | 포함 |
| reverse proxy | Apache → Node/Java/Python 앱서버 | 포함 |
| WAF 연계 | Apache + ModSecurity/CRS | 포함 |
| 복합 VirtualHost | 사이트별 vhost/port/TLS 분리 | 포함 |

따라서 원 계획서는 reverse proxy 환경만을 대상으로 읽으면 안 된다. reverse proxy는 Apache 배치 유형 중 하나일 뿐이다.

## 2. 원 계획서에서 수정해야 할 기준 범위

기존 표현:

```text
- 기준 범위:
  - Ubuntu Apache reverse proxy 환경
```

수정 표현:

```text
- 기준 범위:
  - 웹단에 Apache HTTP Server를 사용하는 애플리케이션 전반
  - Ubuntu Apache 운영 환경을 우선 기준으로 하되, reverse proxy 여부는 필수 전제가 아님
  - Apache가 정적 파일 직접 서빙, PHP-FPM/CGI 연계, WAS/앱서버 reverse proxy, WAF 연계 등 어떤 배치로 쓰이든 적용 가능한 수집 확장 방향
```

## 3. 원 계획서 목적 문단 보강안

원 계획서의 목적 문단에는 다음 문장을 추가해야 한다.

```text
이 계획의 대상은 웹단에 Apache를 사용하는 애플리케이션 전반이다. Apache가 정적 리소스를 직접 서빙하는 경우, PHP-FPM/CGI와 연계되는 경우, 뒤쪽 앱서버로 reverse proxy 하는 경우, WAF/보안 모듈과 함께 쓰이는 경우를 모두 포함한다.
```

## 4. 별도 섹션 추가안

원 계획서에는 다음 섹션을 추가하는 것이 좋다.

```markdown
## 적용 대상 배치 유형

이 문서는 특정 Apache 배치 방식 하나에 종속되지 않는다.

| 배치 유형 | 예 | 수집 관점 |
|---|---|---|
| 정적 파일 직접 서빙 | Apache document root 기반 HTML/CSS/JS/image 제공 | access/security/error 로그가 핵심 |
| PHP-FPM/CGI 연계 | WordPress, PHP 앱, CGI 스크립트 | Apache 로그 + PHP-FPM/app 로그 연계 가능 |
| reverse proxy | Apache → Node/Java/Python 앱서버 | Apache 로그 + backend app 로그 request ID 연계 가능 |
| WAF 연계 | ModSecurity/CRS | Apache 로그 + WAF audit log optional context |
| 복합 VirtualHost | 사이트별 vhost/port/TLS 분리 | vhost/server_name/host 기반 분리 필요 |

reverse proxy는 위 유형 중 하나이며, 이 계획의 필수 전제가 아니다.
```

## 5. Phase D 문구 정정

기존 Phase D의 다음 표현은 reverse proxy 전용으로 오해될 수 있다.

```text
Apache reverse proxy 뒤의 애플리케이션 로그와 Apache 로그를 같은 request ID로 연결한다.
```

수정 표현:

```text
Apache 로그와 애플리케이션 로그를 같은 request ID 또는 근접 식별자로 연결한다. 이 단계는 reverse proxy 환경에만 한정하지 않는다.
```

배치 유형별 연계 방식은 다음처럼 정리한다.

| 배치 유형 | 연계 방식 |
|---|---|
| reverse proxy | Apache가 `X-Request-ID` 헤더를 backend app에 전달 |
| PHP-FPM/CGI | Apache/FastCGI 환경변수 또는 앱 프레임워크 request context에 request ID 전달 |
| 정적 파일 직접 서빙 | 앱 로그가 없을 수 있으므로 Apache log만 canonical evidence로 유지 |
| WAF 연계 | WAF transaction ID와 Apache request metadata를 시간/IP/request 기준으로 연결 |

## 6. 검증 기준 보강

원 계획서의 regression 기준에는 다음 항목을 추가해야 한다.

```text
- reverse proxy가 아닌 Apache 배치에서도 문서/테스트가 성립해야 함
```

## 7. 명시적 비범위 보강

원 계획서의 명시적 비범위에는 다음 항목을 추가해야 한다.

```text
- 특정 배치, 특히 reverse proxy 구조만을 전제로 한 설계 고정
```

## 8. 최종 기준

향후 Apache 로그 수집 확장 작업의 기준은 다음 문장으로 고정한다.

```text
이 프로젝트의 Apache 로그 수집 확장 범위는 reverse proxy 여부와 무관하게, 웹단에 Apache HTTP Server를 사용하는 애플리케이션 전반이다.
```
