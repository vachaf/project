# Juice Shop 로그 수집용 MariaDB 설계 문서

## 1. 문서 목적
이 문서는 **Apache2 기반 Juice Shop 로그 수집 환경**에서, 수집한 로그를 왜 MariaDB에 저장하도록 설계했는지와 실제 데이터베이스 구조를 정리한 문서이다.

이번 환경의 목적은 단순 웹서비스 운영 로그 보관이 아니라, **정상 요청과 공격성 요청을 함께 수집하고 이를 분석·분류할 수 있는 데이터셋을 구축하는 것**이다. 따라서 데이터베이스는 단순 보관소가 아니라, 다음 목적을 동시에 만족하도록 설계했다.

- 로그 원문 보존
- 주요 필드의 정규화 저장
- 요청 단위 상관분석 지원
- 공격 탐지 및 라벨링 확장성 확보
- 추후 통계, 검색, 분류 모델 학습용 데이터셋 활용

---

## 2. 시스템 구성과 저장 흐름
현재 구성은 다음과 같다.

- **로그 수집 웹서버**: `192.168.35.113`
- **MariaDB 서버**: `192.168.35.223`
- **웹서버 역할**: Apache2 리버스 프록시 + Juice Shop 로그 생성
- **DB 서버 역할**: 로그 적재 및 조회용 중앙 저장소

로그 흐름은 아래와 같다.

```text
클라이언트 / 공격 도구 / 실험 스크립트
                ↓
          Apache2 (로그 생성)
                ↓
   access / security / error 로그 파일
                ↓
      Python log shipper
                ↓
      MariaDB(web_logs)
```

이 구조를 선택한 이유는 다음과 같다.

1. **Apache가 모든 요청의 공통 수집 지점**이기 때문이다.
2. 파일 로그를 먼저 남기고 DB에 적재하면 **원본 보존과 후처리 분리**가 가능하다.
3. Python shipper를 이용하면 **실험 단계에서 로그 포맷 변경과 파싱 로직 수정이 쉽다**.
4. MariaDB에 정규화 저장하면 **검색, 집계, 분류용 질의**를 쉽게 수행할 수 있다.

---

## 3. 왜 DB 저장이 필요한가
기본적인 파일 로그만으로도 운영 확인은 가능하다. 그러나 이번 프로젝트 목적은 웹 공격 탐지와 로그 기반 분류 실험이므로, 단순 파일 보관만으로는 한계가 있다.

### 3.1 파일 로그만으로는 불편한 점
- 대량 로그에서 조건 검색이 번거롭다.
- 여러 로그 파일 사이의 요청 연계가 어렵다.
- 공격 유형별 집계가 불편하다.
- 특정 IP, URI, 상태코드, 요청 식별자 기준 검색이 비효율적이다.
- 머신러닝/통계 분석용 데이터셋으로 재활용하기 어렵다.

### 3.2 DB 저장의 장점
- `WHERE`, `GROUP BY`, `ORDER BY` 기반 탐색이 쉽다.
- access / security / error 로그를 요청 단위로 연계할 수 있다.
- 공격 라벨, 위험 점수, 의심 여부 같은 후처리 필드를 추가하기 쉽다.
- 대시보드, 탐지기, 보고서, 시각화로 확장하기 쉽다.

즉, 이번 DB는 **로그를 버리지 않고 구조화해 활용도를 높이는 저장 계층**으로 설계했다.

---

## 4. 로그 수집 전략과 DB 설계의 연결
기존 로그 수집 전략은 다음 원칙을 가진다.

- Apache를 수집 중심 지점으로 둔다.
- 기본 access log는 유지한다.
- 머신 파싱용 key=value security log를 별도 파일로 둔다.
- `UNIQUE_ID`를 주 요청 식별자로 사용하고, `%L`은 에러 연계용 보조 키로 둔다.
- access / security / error 로그를 분리 수집한다. fileciteturn4file1L1-L5 fileciteturn4file2L11-L20

또한 security 로그는 `reqid`, `errid`, `src`, `raw_req`, `uri`, `qs`, `status`, `resp_body_bytes`, `dur_us`, `ttfb_us`, `ua`, `host` 같은 필드를 담는 **key=value 구조**로 설계되었다. fileciteturn4file0L1-L7

따라서 DB도 하나의 테이블에 모든 로그를 섞지 않고, 다음처럼 역할별로 분리하는 방식이 적절했다.

- `apache_access_logs`
- `apache_security_logs`
- `apache_error_logs`

이 구조는 **원본 로그의 의미를 유지하면서도, 분석 목적에 맞게 정규화**할 수 있다는 장점이 있다.

---

## 5. 데이터베이스 개요
실제 데이터베이스 이름은 다음과 같다.

```sql
web_logs
```

문자셋은 다국어 로그와 다양한 헤더 값을 안정적으로 저장하기 위해 `utf8mb4` 계열을 사용한다.

DB 접근 정책은 다음 원칙을 따른다.

- 원격 `root` 접속은 사용하지 않는다.
- 로그 적재 전용 계정을 분리한다.
- 웹서버(`192.168.35.113`)에서만 DB 쓰기 권한을 갖도록 제한한다.

이 구조는 운영 보안 측면에서도 적절하다. 즉, 웹서버는 **로그 생성자이자 적재자**, MariaDB 서버는 **중앙 보관소**로 역할을 분리한다.

---

## 6. 테이블 분리 이유

### 6.1 `apache_access_logs`
이 테이블은 기본 접근 로그를 저장한다.

주요 목적:
- 전체 요청 흐름 보관
- 사람이 읽기 쉬운 수준의 기본 요청 확인
- IP, URI, 상태코드, User-Agent 기준 탐색
- 보안 로그와의 비교 기준선 제공

### 6.2 `apache_security_logs`
이 테이블은 분석용 확장 로그를 저장한다.

주요 목적:
- 분류 및 탐지용 특징값 저장
- 요청 식별자 기반 상관분석
- 응답 크기, 지연시간, 헤더 계열 등 부가 메타데이터 확보
- 향후 공격 라벨링 및 점수화 확장

### 6.3 `apache_error_logs`
이 테이블은 Apache 에러 로그를 저장한다.

주요 목적:
- 서버 오류나 프록시 계층 문제 확인
- access/security 로그와 에러 상관관계 분석
- 요청 실패 원인 분석

즉, 이번 DB는 단순한 로그 아카이브가 아니라, **운영 확인용 / 분석용 / 장애 확인용** 정보를 역할별로 나눠 담는 구조다.

---

## 7. 테이블별 설계 설명

## 7.1 `apache_access_logs`
이 테이블은 기본 접근 로그를 저장한다.

핵심 컬럼:
- `log_time`: 요청 시각
- `client_ip`: 클라이언트 IP
- `method`: HTTP 메서드
- `raw_request`: 원본 요청 라인
- `uri`: 요청 경로
- `query_string`: 쿼리 문자열
- `protocol`: HTTP 프로토콜 버전
- `status_code`: 응답 상태 코드
- `response_body_bytes`: 응답 바디 크기
- `referer`: Referer 헤더
- `user_agent`: User-Agent 헤더
- `host`: Host 헤더
- `vhost`: 가상 호스트명
- `raw_log`: 원본 로그 한 줄 전체
- `created_at`: DB 적재 시각

설계 의도:
- 운영 관점에서 가장 많이 보는 기본 요청 정보를 담는다.
- 요청 라인과 분해된 필드를 함께 저장해, 원문 확인과 조건 검색을 동시에 지원한다.
- `raw_log`를 함께 보관하여 파싱 오류나 재처리에 대응한다.

실제 스키마에서는 `log_time`, `client_ip`, `status_code` 에 인덱스가 설정되어 있어 시간·IP·상태코드 기준 조회를 빠르게 수행할 수 있다. fileciteturn4file7L1-L12

---

## 7.2 `apache_security_logs`
이 테이블은 분석용 확장 로그를 저장한다.

핵심 컬럼:
- `log_time`: 요청 시각
- `request_id`: 주 요청 식별자
- `error_link_id`: 에러 로그 연계용 보조 식별자
- `vhost`: 가상 호스트
- `src_ip`: 원본 클라이언트 IP
- `peer_ip`: 프록시/피어 IP
- `method`: HTTP 메서드
- `raw_request`: 원본 요청 라인
- `uri`: 요청 경로
- `query_string`: 쿼리 문자열
- `protocol`: 프로토콜 버전
- `status_code`: 응답 상태 코드
- `response_body_bytes`: 응답 바디 크기
- `in_bytes`, `out_bytes`, `total_bytes`: I/O 크기 관련 지표
- `duration_us`: 전체 처리 시간
- `ttfb_us`: 첫 바이트 반환 시간
- `keepalive_count`: keep-alive 관련 카운트
- `connection_status`: 연결 상태
- `req_content_type`, `req_content_length`: 요청 본문 메타데이터
- `resp_content_type`: 응답 Content-Type
- `referer`, `user_agent`, `host`, `x_forwarded_for`: 헤더 계열 정보
- `attack_label`: 공격 분류 라벨
- `risk_score`: 위험 점수
- `matched_rule`: 탐지 규칙명
- `is_suspicious`: 의심 여부
- `raw_log`: 원본 로그 한 줄 전체
- `created_at`: DB 적재 시각

설계 의도:
- 단순 운영 로그를 넘어서, 분류기나 탐지기에 바로 투입 가능한 특징값을 축적한다.
- `request_id`, `error_link_id` 를 통해 access / error 로그와 상관분석이 가능하다.
- `attack_label`, `risk_score`, `matched_rule`, `is_suspicious` 를 미리 두어 후속 탐지 로직 확장을 쉽게 한다.

실제 스키마에서도 `request_id`, `error_link_id`, `src_ip`, `status_code`, `attack_label`, `is_suspicious` 에 인덱스가 설정되어 있으며, 이는 요청 추적과 이상 탐지 분석을 염두에 둔 구조다. fileciteturn4file5L1-L14 fileciteturn4file8L1-L9

---

## 7.3 `apache_error_logs`
이 테이블은 Apache 에러 로그를 저장한다.

핵심 컬럼:
- `log_time`: 에러 발생 시각
- `error_link_id`: 에러 연계 식별자
- `request_id`: 요청 식별자
- `module_name`: Apache 모듈명
- `log_level`: 에러 레벨
- `src_ip`: 관련 클라이언트 IP
- `peer_ip`: 관련 피어 IP
- `message`: 에러 메시지 본문
- `raw_log`: 원본 로그 전체
- `created_at`: DB 적재 시각

설계 의도:
- 장애 분석과 보안 분석을 분리하지 않고 함께 볼 수 있도록 한다.
- 요청 처리 실패, 프록시 문제, 경고 메시지를 access/security 로그와 연결할 수 있게 한다.
- 에러가 없는 정상 요청도 많으므로, error 로그는 요청 전체 집합이 아니라 **보조 분석 테이블**로 본다.

실제 스키마에서도 `log_time`, `error_link_id`, `request_id`, `log_level` 에 인덱스가 존재한다. fileciteturn4file8L10-L14

---

## 8. raw_log를 따로 저장한 이유
각 테이블에 `raw_log` 컬럼을 둔 이유는 다음과 같다.

1. 파싱 실패 시 원본 복구가 가능하다.
2. 정규식 수정 후 재처리할 수 있다.
3. 사람이 실제 원문을 바로 확인할 수 있다.
4. 추후 파서 변경 시 기존 적재 데이터를 검증할 수 있다.

즉, 정규화 컬럼만 저장하면 편리하지만 유연성이 떨어진다. 따라서 이번 설계는 **정규화 필드 + 원문 보존**을 함께 택했다.

---

## 9. 인덱스 설계 이유
로그 테이블은 쓰기량이 많기 때문에 인덱스를 과도하게 두면 성능에 불리하다. 그래서 자주 조회할 축 위주로만 인덱스를 둔다.

주요 인덱스 목적은 다음과 같다.

- 시간대별 조회: `log_time`
- 출발지 기준 조회: `client_ip`, `src_ip`
- 응답 상태 기준 조회: `status_code`
- 요청 상관분석: `request_id`, `error_link_id`
- 탐지 결과 집계: `attack_label`, `is_suspicious`
- 에러 수준별 조회: `log_level`

즉, 인덱스는 모든 컬럼이 아니라 **운영 확인, 사고 분석, 탐지 실험에서 자주 쓰는 컬럼** 위주로 설계했다.

---

## 10. 로그 전달 방식과 DB 설계의 관계
현재 구조는 Apache가 로그 파일을 남기고, Python shipper가 이를 읽어 MariaDB에 적재한다.

이 방식에 맞춰 DB를 설계할 때 고려한 점은 다음과 같다.

- 파일 로그와 DB 적재는 느슨하게 분리한다.
- DB 적재 실패 시 spool에 임시 저장 후 재전송 가능해야 한다.
- 로그 로테이션 이후에도 같은 스키마로 계속 적재 가능해야 한다.
- access/security/error 로그를 각각 독립적으로 처리할 수 있어야 한다.

즉, DB는 수집 파이프라인의 마지막 단계이면서도, **수집기 교체나 파서 변경이 있어도 유지 가능한 비교적 안정된 인터페이스**가 되어야 한다.

---

## 11. 향후 확장 방향
이번 설계는 현재 실험 목적에 맞춘 1차 구조이지만, 확장 가능성을 고려했다.

### 11.1 탐지 로직 확장
향후 다음 기능을 붙일 수 있다.

- SQL Injection 탐지 라벨링
- XSS 탐지 라벨링
- Path Traversal 탐지 라벨링
- Scanner/봇 트래픽 태깅
- 위험 점수 산정

이를 위해 `attack_label`, `risk_score`, `matched_rule`, `is_suspicious` 컬럼을 미리 두었다.

### 11.2 데이터셋 활용
이 DB는 다음 형태로 활용 가능하다.

- CSV 추출 후 학습 데이터셋 생성
- 특정 공격 유형별 샘플 추출
- 정상/비정상 요청 비교 분석
- IP / URI / 상태코드 단위 통계 산출

### 11.3 운영 확장
규모가 커지면 다음도 고려할 수 있다.

- 월별 아카이브 테이블
- 파티셔닝
- 중복 삽입 방지용 해시 컬럼
- 대시보드 연동
- 알림 시스템 연동

---

## 12. 설계상 주의점

### 12.1 로그는 빠르게 증가한다
특히 Juice Shop처럼 실험적으로 반복 요청을 많이 발생시키는 환경에서는 `/socket.io/` 같은 요청도 계속 쌓일 수 있다. 따라서 DB 저장만 믿지 말고, 로그 로테이션과 보관 정책도 함께 가져가야 한다.

### 12.2 민감정보 저장은 최소화한다
query string, header, request body 계열에는 민감한 값이 포함될 수 있으므로, 향후 본문 저장이나 쿠키 저장을 추가할 경우 마스킹 정책이 필요하다.

### 12.3 error 로그는 항상 생기지 않는다
정상 운영 중에는 `apache_error_logs` 가 비어 있을 수 있다. 이는 장애가 없다는 뜻일 수 있으므로 비정상으로 볼 필요는 없다.

---

## 13. 결론
이번 MariaDB 설계는 **Apache 중심 로그 수집 전략**을 데이터 저장 구조로 옮긴 것이다.

정리하면 다음과 같다.

1. Apache를 로그 수집의 중심으로 둔다.
2. access / security / error 로그를 분리 수집한다.
3. 파일 로그는 원본 보관용으로 유지한다.
4. Python shipper가 로그를 읽어 MariaDB에 정규화 저장한다.
5. DB는 원문 보존과 분석 편의성을 함께 만족하도록 설계한다.
6. `request_id`, `error_link_id`, `attack_label` 같은 컬럼을 통해 향후 상관분석과 탐지 확장을 가능하게 한다.

즉, 이 DB 구조는 단순 저장을 위한 구조가 아니라, **웹 공격 탐지와 로그 기반 분류 실험을 위한 분석 지향적 설계**라고 볼 수 있다.
