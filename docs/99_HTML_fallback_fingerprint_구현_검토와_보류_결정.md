# 99_HTML_fallback_fingerprint_구현_검토와_보류_결정

- 문서 상태: 검토 및 보류 결정
- 버전: v1.0
- 작성일: 2026-04-08
- 적용 대상: HTML fallback fingerprint 설계, 구현 시도, 검증 결과, 보류 결정 정리
- 연계 문서:
  - `02_MariaDB_환경_구축_및_설치.md`
  - `03_로그_표준과_DB_구조.md`
  - `04_로그_적재_및_운영.md`
  - `05_Export_LLM_분석_전략.md`

---

## 1. 문서 목적

이 문서는 path traversal 해석을 더 보수적으로 만들기 위해 검토했던 **HTML fallback fingerprint** 기능의 원래 목표, 실제 구현 시도 범위, 검증 결과, 그리고 최종적으로 **현 단계에서는 구현하지 않기로 한 결정**을 정리한 문서다.

이번 항목은 단순한 코드 수정이 아니라 다음 세 계층을 함께 연결해야 하는 과제였다.

1. DB 스키마 확장
2. shipper 적재 로직 확장
3. Apache security 로그 포맷과 상류 metadata 생성 로직 확장

검토 결과, **DB/shipper/LogFormat 배선은 가능했지만, 실제 fingerprint 값을 생성하는 상류 로직이 부재**하여 현 단계에서는 완전한 구현을 진행하지 않기로 결정하였다.

---

## 2. 원래 구현 목표

기존 path traversal 해석은 주로 아래 조건을 기준으로 보수적으로 판단하고 있었다.

- `status_code == 200`
- `resp_content_type == text/html`
- `response_body_bytes`가 충분히 큼
- `likely_html_fallback_response == true`

이 방식은 다음과 같은 장점이 있다.

- 실제 파일 노출을 성급하게 단정하지 않는다.
- SPA fallback 또는 기본 HTML 반환 가능성을 열어 둔다.
- 기존 보고서의 보수적 톤과 잘 맞는다.

그러나 한계도 분명했다.

- `text/html`이라는 사실만으로는 실제 fallback HTML인지 단정하기 어렵다.
- body size가 크더라도 그것이 곧 baseline HTML과 동일하다는 뜻은 아니다.
- 보고서에서 “fallback 가능성”은 말할 수 있지만, “baseline HTML과 유사/동일”이라는 더 강한 근거는 제시하지 못한다.

따라서 이번 검토의 목표는 다음과 같았다.

> path traversal 200 응답이 실제 파일 내용이 아니라, 애플리케이션의 기본 HTML fallback 페이지와 동일하거나 매우 유사하다는 근거를 `resp_html_*` metadata로 남겨, 기존 보수 해석을 더 단단하게 만들기

즉, 이 항목은 **침해 성공 입증**이 아니라 **fallback 가능성 강화**를 목표로 하는 설계였다.

---

## 3. 설계 개요

검토한 설계의 기본 방향은 아래와 같았다.

### 3.1 저장 대상

응답 본문 전체를 저장하지 않고, 아래와 같은 **정규화 fingerprint metadata**만 저장한다.

- `resp_html_norm_fingerprint`
- `resp_html_fingerprint_version`
- `resp_html_baseline_name`
- `resp_html_baseline_match`
- `resp_html_baseline_confidence`
- `resp_html_features_json`

### 3.2 저장 목적

이 metadata는 다음 목적을 가진다.

- path traversal 200 + `text/html` 응답이 실제 파일인지 fallback HTML인지 구분하는 보조 근거 확보
- `likely_html_fallback_response`보다 더 강한 보수 해석 근거 확보
- 향후 stage1 / stage2 보고서 문구 강화

### 3.3 원칙

- 응답 본문 전체는 상시 저장하지 않는다.
- fingerprint match는 fallback 가능성 강화 근거로만 사용한다.
- mismatch 또는 NULL만으로 실제 파일 노출 성공을 단정하지 않는다.
- 이 metadata는 우선 `apache_security_logs`에만 적용한다.

---

## 4. 실제 구현 시도 범위

이번 검토에서 실제로 시도한 범위는 아래와 같다.

### 4.1 DB 스키마 확장

`apache_security_logs`에 다음 컬럼을 추가했다.

- `resp_html_norm_fingerprint`
- `resp_html_fingerprint_version`
- `resp_html_baseline_name`
- `resp_html_baseline_match`
- `resp_html_baseline_confidence`
- `resp_html_features_json`

이를 통해 downstream 저장 구조는 준비되었다.

### 4.2 shipper 확장

`src/apache_log_shipper.py`에 아래 변경을 적용했다.

- `apache_security_logs` INSERT 구문에 `resp_html_*` 6개 컬럼 추가
- `parse_security_line()`에 `resp_html_*` key 매핑 추가
- `resp_html_baseline_match`를 nullable tinyint로 안전하게 처리하는 헬퍼 추가

즉, shipper는 로그 원문에 `resp_html_*` key가 존재할 경우 이를 DB 컬럼으로 적재할 수 있도록 준비되었다.

### 4.3 Apache security LogFormat 확장

`juice-shop.conf`의 `security_db_aligned` LogFormat에 아래 출력 항목을 추가했다.

- `resp_html_norm_fingerprint="%{resp_html_norm_fingerprint}n"`
- `resp_html_fingerprint_version="%{resp_html_fingerprint_version}n"`
- `resp_html_baseline_name="%{resp_html_baseline_name}n"`
- `resp_html_baseline_match="%{resp_html_baseline_match}n"`
- `resp_html_baseline_confidence="%{resp_html_baseline_confidence}n"`
- `resp_html_features_json="%{resp_html_features_json}n"`

즉, Apache security log가 해당 note를 **출력할 수 있는 포맷**까지는 연결하였다.

---

## 5. 실제 검증 절차

검증은 아래 순서로 수행하였다.

1. shipper DB 연결 확인
2. shipper `--once` 실행
3. `/admin_99` 요청으로 `text/html` 응답 생성
4. `/rest/products/search?q=test` 요청으로 `application/json` 응답 생성
5. `/var/log/apache2/app_security.log` 원문 확인
6. `apache_security_logs` 최근 행 조회
7. `raw_log` 확인

검증 중 확인한 핵심 포인트는 다음과 같았다.

- 새 요청은 실제로 DB에 적재되었다.
- `text/html` 응답 행도 정상 생성되었다.
- security log 원문에는 `resp_html_*` key가 추가되어 출력되었다.
- 그러나 `resp_html_*`의 값은 모두 `"-"`였다.
- DB에도 결과적으로 `NULL`만 저장되었다.

즉, **DB와 shipper와 LogFormat 배선은 동작했지만, 실제 fingerprint 값은 생성되지 않았다.**

---

## 6. 실제 검증 결과

검증 결과는 아래와 같이 정리할 수 있다.

### 6.1 성공한 부분

- DB 컬럼 추가 성공
- shipper 구문 확장 성공
- shipper 적재 자체는 정상 동작
- Apache security log 포맷 확장 성공
- `resp_html_*` key 이름은 실제 로그에 출력됨

### 6.2 실패한 부분

- `resp_html_*`에 실제 값이 채워지지 않음
- `text/html` 응답에서도 fingerprint metadata가 생성되지 않음
- DB에는 `resp_html_*`가 모두 `NULL`로 적재됨

### 6.3 직접 확인된 상태

실제 security log에서는 다음과 같은 형태가 확인되었다.

- `resp_html_norm_fingerprint="-"`  
- `resp_html_fingerprint_version="-"`  
- `resp_html_baseline_name="-"`  
- `resp_html_baseline_match="-"`  
- `resp_html_baseline_confidence="-"`  
- `resp_html_features_json="-"`

즉, 키는 있으나 값이 비어 있었다.

---

## 7. resp_html_*가 "-" / NULL로만 남은 이유

이유는 간단하다.

> Apache는 현재 `resp_html_*`를 **출력만 하도록 설정되었고**, 그 값을 **생성해서 note에 넣는 로직은 존재하지 않는다.**

현재 구성에서 수행된 작업은 다음 두 단계뿐이다.

1. Apache LogFormat에 `%{resp_html_*}n`를 추가
2. shipper가 그 key를 읽어 DB로 적재

그러나 중간의 핵심 단계가 비어 있다.

- 누가 `resp_html_norm_fingerprint`를 계산하는가
- 누가 `resp_html_baseline_name`을 결정하는가
- 누가 `resp_html_baseline_match`를 판정하는가
- 누가 `resp_html_features_json`을 생성하는가

이 생성 단계가 없기 때문에 Apache는 해당 note를 찾지 못하고 `"-"`를 출력한 것이다.

---

## 8. Apache note 출력과 note 생성의 차이

이 항목에서 가장 중요하게 확인된 개념 차이는 아래와 같다.

### 8.1 note 출력

Apache LogFormat에서

```apache
%{resp_html_baseline_match}n
```

와 같이 쓰는 것은 **해당 note 값을 로그에 출력하라**는 뜻이다.

즉, 이것은 **출력 포맷 정의**다.

### 8.2 note 생성

반면 실제로 `resp_html_baseline_match`라는 note 값이 존재하려면, 어딘가에서 미리 아래와 같은 작업이 있어야 한다.

- 응답 본문 분석
- HTML 구조 특징 추출
- baseline과 비교
- match 여부 계산
- 계산된 값을 Apache note에 저장

즉, 이것은 **값 생성 로직**이다.

### 8.3 이번 검토에서 도달한 결론

이번 시도는 **출력 포맷은 연결했지만, 값 생성 로직은 구현하지 못한 상태**까지 진행된 것이다.

따라서 다음과 같이 이해해야 한다.

- `%{...}n`를 LogFormat에 넣는 것만으로는 fingerprint가 생기지 않는다.
- `resp_html_*` note를 실제로 생성하는 상류 로직이 없으면 결과는 `"-"`가 된다.
- shipper는 계산기가 아니라 적재기다.
- 따라서 현재 shipper 수정만으로는 4단계 완성에 도달할 수 없다.

---

## 9. 왜 현 단계에서는 구현하지 않기로 했는가

이번 항목을 현 단계에서 보류하기로 한 이유는 아래와 같다.

### 9.1 Apache만으로 해결되지 않는다

현재 구조에서는 Apache LogFormat이 응답 본문을 직접 fingerprint로 변환하지 않는다.

즉, 다음과 같은 별도 상류 구현이 필요하다.

- Apache 모듈 또는 Lua 등으로 응답 본문/특징 분석
- 애플리케이션 또는 미들웨어에서 fingerprint metadata 생성
- 별도 sidecar/중간 계층에서 note 값 생성

이는 현재 프로젝트 범위를 넘어서는 추가 구현이다.

### 9.2 현재 파이프라인의 핵심 목표는 이미 달성 중이다

현 파이프라인은 이미 아래 보수 해석을 수행하고 있다.

- HPP 문맥 보존
- raw_request_target 보존
- path traversal 보수 해석
- `likely_html_fallback_response` 유지
- 후보 밖 탐색성 요청 분리

즉, 보고서의 보수적 품질을 유지하는 데 필요한 핵심 기능은 이미 작동 중이다.

### 9.3 도입 비용 대비 효과가 현재 단계에서는 크지 않다

이번 항목은 설계상 의미는 있으나, 실제 구현을 완성하려면 다음이 추가로 필요하다.

- 응답 HTML 특징 추출기
- baseline 관리 방식
- Apache note 주입 메커니즘
- 재현 가능한 fingerprint 기준
- 오탐/누락 검증

현재 단계에서 이 비용은 상대적으로 크고, 프로젝트 진행 우선순위 대비 즉시 효과는 제한적이다.

---

## 10. 현 단계에서의 최종 결정

최종 결정은 다음과 같다.

> **HTML fallback fingerprint 기능은 현 단계에서는 구현하지 않기로 한다.**

보다 정확히는 다음과 같이 정리한다.

- DB 컬럼 확장, shipper 확장, Apache LogFormat 출력 배선은 검토 및 시도 완료
- 그러나 실제 `resp_html_*` 값을 생성하는 상류 로직은 구현 범위 밖으로 판단
- 따라서 4단계는 **완전 구현 과제**가 아니라 **검토 후 보류 과제**로 전환

즉, 본 항목은 **“설계 가능성 검토와 배선 확인”까지 수행하고, 실제 값 생성 구현은 보류**한 상태다.

---

## 11. 기존 보수 해석 유지 방침

이번 보류 결정 이후에도 path traversal 해석은 다음 방침을 유지한다.

### 11.1 유지할 판단 근거

- `raw_request_target`
- `path_normalized_from_raw_request`
- `status_code`
- `resp_content_type`
- `response_body_bytes`
- `likely_html_fallback_response`

### 11.2 유지할 보고서 톤

- `text/html` 200 응답만으로 파일 노출 성공을 단정하지 않는다.
- HTML fallback 가능성을 계속 우선 검토한다.
- fingerprint 부재 또는 NULL은 성공 증거로 사용하지 않는다.
- 기존 보수 해석을 깨지 않는다.

즉, 4단계가 보류되어도 기존 보수 해석 체계는 유지된다.

---

## 12. 향후 재검토 조건

향후 아래 조건이 충족되면 이 항목을 다시 검토할 수 있다.

### 12.1 상류 생성 로직 확보 가능 시

다음 중 하나가 가능해질 경우 재검토할 수 있다.

- 애플리케이션 또는 미들웨어에서 HTML 구조 metadata 생성
- Apache 모듈/Lua를 이용한 note 생성 구현
- 응답 헤더나 별도 내부 로깅 채널로 fingerprint 전달

### 12.2 baseline 관리 전략이 정리될 시

아래 항목이 명확해져야 한다.

- 어떤 HTML을 baseline으로 볼 것인가
- baseline 버전 변경 시 어떻게 관리할 것인가
- `main_index_html`, `spa_fallback_html`, `default_404_html` 구분 기준은 무엇인가

### 12.3 재현 가능한 검증 경로가 확보될 시

다음이 확보되어야 한다.

- 동일 요청에 대해 일관된 fingerprint 생성
- body hash가 아니라 구조 fingerprint 기준의 안정성
- text/html 응답과 fallback HTML을 구분할 수 있는 검증 샘플

---

## 13. 이번 검토의 의미

이번 시도는 실패라기보다, **어디까지가 현재 구조에서 가능한지 경계를 확인한 과정**으로 보는 것이 맞다.

확인된 사실은 다음과 같다.

- DB와 shipper 확장은 가능하다.
- Apache LogFormat 배선도 가능하다.
- 그러나 `%{...}n` 출력은 값 생성과 다르다.
- 현재 구조에서는 생성기가 없으면 결과는 `"-"` / `NULL`이다.
- 따라서 4단계의 핵심 난점은 DB나 shipper가 아니라 **상류 metadata 생성 위치**다.

이 결론은 이후 구조 설계에 의미가 있다.

즉, 향후 이 기능을 다시 시도한다면 문제의 중심은 **DB/shipper가 아니라 응답 metadata 생성 계층**이 된다.

---

## 14. 최종 요약

이번 검토에서 HTML fallback fingerprint 기능은 다음 수준까지 진행되었다.

1. DB 컬럼 설계 및 추가
2. shipper 적재 로직 확장
3. Apache security LogFormat 출력 항목 추가
4. 실제 요청으로 검증 수행
5. `resp_html_*`가 `"-"` / `NULL`로만 남는 문제 확인
6. note 출력과 note 생성이 다르다는 점 확인
7. 현 단계에서는 구현하지 않기로 결정

최종 결정은 아래 문장으로 요약할 수 있다.

> **HTML fallback fingerprint는 설계상 유의미하지만, 현재 구조에서는 값 생성 로직이 부재하여 완전 구현이 어렵다. 따라서 현 단계에서는 본 기능을 구현하지 않고, 기존의 보수적 path traversal 해석을 유지한다.**
