# LLM 로그 전달 전략 및 노이즈 필터링 가이드

## 1. 문서 목적

이 문서는 현재 구축된 Apache → MariaDB → JSON export 환경에서, DB에 적재된 웹 로그를 LLM에 어떤 방식으로 전달할지에 대한 전략을 정리한 문서다.

특히 다음 문제를 해결하는 것을 목표로 한다.

- `socket.io` polling 같은 **정상인데 반복성이 높아 잡음이 많은 요청**을 어떻게 다룰지
- 원본 로그와 분석용 로그를 어떻게 분리할지
- LLM에 무엇을 그대로 넘기고, 무엇을 줄이거나 묶어서 넘길지
- 공격 징후 탐지를 위해 어떤 프롬프트 구조를 사용할지
- 향후 보고서 자동화를 위해 어떤 파이프라인을 택할지

---

## 2. 현재 환경 기준

현재 구조는 다음과 같다.

- 웹서버: Apache reverse proxy 기반 웹 로그 수집 서버
- DB 서버: MariaDB `web_logs`
- DB 테이블:
  - `apache_access_logs`
  - `apache_security_logs`
  - `apache_error_logs`
- Export 스크립트:
  - `export_db_logs_cli.py`
- 시간 기준:
  - DB 저장은 UTC 기반
  - JSON export는 KST 기준으로 변환하여 출력하는 방식 권장

현재 운영상 중요한 점은 다음과 같다.

1. **DB에는 원본에 가까운 로그를 최대한 유지**한다.
2. **LLM에는 DB 원본 전체를 그대로 보내지 않는다.**
3. **정상 잡음은 사전에 줄이거나 묶어서 전달**한다.
4. **최종 보고서는 LLM이 작성하되, 1차 분류 또는 정제는 규칙 기반으로 선행**하는 것이 더 안정적이다.

---

## 3. 왜 원본 JSON 전체를 그대로 보내면 안 되는가

DB export 결과를 그대로 LLM에 전달하면 가장 구현은 쉽다. 그러나 다음 문제가 있다.

### 3.1 토큰 낭비

로그는 요청 한 건당 필드 수가 많다.

예를 들어 security 로그 한 건에는 다음과 같은 필드가 들어간다.

- `log_time`
- `request_id`
- `src_ip`
- `raw_request`
- `query_string`
- `status_code`
- `duration_us`
- `ttfb_us`
- `user_agent`
- `raw_log`
- 기타 메타데이터

여기에 `socket.io` polling 같은 요청이 수백 건 들어오면, 실제로는 분석 가치가 낮은 정상 트래픽이 토큰 대부분을 차지하게 된다.

### 3.2 분석 품질 저하

잡음 로그가 많으면 LLM은 다음 문제를 일으키기 쉽다.

- 중요한 의심 요청을 놓친다.
- 반복적인 정상 요청을 과대해석한다.
- 의미 없는 URI 반복을 보고서에 많이 써버린다.
- 전체 구조보다 표면 빈도에 끌려간다.

### 3.3 보고서가 길어지고 핵심이 흐려짐

분석 보고서는 “무슨 공격 징후가 있었는가”가 핵심인데, polling/heartbeat 류 요청이 많으면 보고서가 운영 로그 요약처럼 변질된다.

---

## 4. 기본 원칙

권장 원칙은 다음과 같다.

### 4.1 DB는 원본 보존

DB에는 가능한 한 원본 로그를 보존한다.

즉,

- access 로그는 기본 요청 흐름 보존
- security 로그는 탐지/분석용 확장 필드 보존
- error 로그는 장애/오류 상관분석용 보존

### 4.2 LLM 입력은 “분석용 정제본” 사용

LLM에 넘기는 데이터는 아래 둘 중 하나로 한다.

1. **원본 JSON 전체**
   - 데이터 양이 매우 적을 때만 사용
2. **필터링/축약/집계한 분석용 JSON**
   - 기본 권장 방식

### 4.3 잡음은 삭제보다 “분리”가 우선

무조건 버리기보다 다음 순서가 좋다.

1. 정상 잡음 후보를 식별
2. 원본에서는 유지
3. 분석용 전달본에서는
   - 제외하거나
   - 축약하거나
   - 하나의 그룹으로 집계

즉, **저장 계층과 분석 계층을 분리**한다.

---

## 5. 어떤 로그가 잡음이 될 가능성이 큰가

현재 환경에서는 아래 유형이 대표적인 정상 잡음 후보다.

### 5.1 `socket.io` polling / websocket 보조 요청

예:

- `/socket.io/?EIO=4&transport=polling...`
- session 유지용 polling 요청
- 짧은 간격으로 다수 반복되는 POST/GET

특징:

- 빈도 높음
- URI 패턴이 반복적임
- 상태코드가 주로 200
- 브라우저 user-agent와 referer가 정상적임
- 실제 공격 판단에는 기여도가 낮음

### 5.2 정적 리소스 요청

예:

- `.js`, `.css`, `.png`, `.jpg`, `.svg`, `.ico`, `.woff`, `.map`
- `/assets/`, `/frontend/`, `/dist/` 등

특징:

- 정상 페이지 로드시 자동 발생
- 개별 요청 분석 가치가 낮음
- 다량 발생 시 보고서 품질을 떨어뜨림

### 5.3 정상 브라우저의 반복 API 호출

예:

- 상태 갱신용 polling API
- 추천/검색 자동완성 API
- 헬스 체크성 호출

특징:

- 특정 UI 동작으로 반복 발생
- URI는 동적이지만 의미가 제한적임

---

## 6. 잡음 필터링 전략

핵심은 **제외**, **축약**, **집계** 세 가지를 조합하는 것이다.

### 6.1 1단계: 완전 제외 규칙

LLM에 절대 보낼 필요가 거의 없는 요청은 제외 후보로 둔다.

예시:

- 확장자가 정적 파일인 요청
- 정상 referer / 정상 browser UA / 200 응답 / payload 없음 / 의심 문자 없음
- `socket.io` polling 중 정상 패턴 반복

예시 규칙:

```text
다음 조건을 모두 만족하면 분석용 전달본에서 제외 후보로 본다.
- uri 가 /socket.io/ 로 시작
- status_code 가 200
- raw_request, query_string 에 SQLi/XSS/Traversal 시그니처 없음
- 같은 src_ip 에서 짧은 시간 동안 반복 발생
- error_link_id 없음
```

주의:

- DB에서 삭제하지 않는다.
- 분석용 JSON에서만 제외한다.

### 6.2 2단계: 축약 규칙

완전 제외하기 애매하지만, 개별 요청 단위로 다 보낼 필요는 없는 경우에는 축약한다.

예:

- 동일한 `src_ip + uri + method + status_code + user_agent` 조합이 수십 회 반복

이 경우 LLM에는 개별 row 50개를 넘기지 않고 다음처럼 축약한다.

```json
{
  "type": "aggregated_normal_noise",
  "category": "socketio_polling",
  "src_ip": "192.168.35.27",
  "uri": "/socket.io/",
  "method": "POST",
  "status_code": 200,
  "count": 84,
  "time_range": {
    "start": "2026-04-02T15:30:00+09:00",
    "end": "2026-04-02T15:45:00+09:00"
  },
  "note": "정상 웹 UI 세션 유지로 보이는 반복 polling 요청"
}
```

이렇게 하면 LLM이 “해당 시간대에 정상 반복 요청이 많았다”는 사실은 이해하되, 토큰은 크게 줄일 수 있다.

### 6.3 3단계: 별도 그룹화

정상 잡음을 아예 별도 섹션으로 분리할 수도 있다.

예:

```json
{
  "meta": { ... },
  "noise_summary": [ ... ],
  "analysis_candidates": [ ... ]
}
```

이 방식의 장점:

- LLM이 노이즈를 무시하지 않고 참고만 할 수 있음
- 보고서 본문은 `analysis_candidates` 중심으로 작성 가능

---

## 7. 의심 요청 후보 선정 기준

LLM에 넘길 핵심 대상은 `analysis_candidates` 다.

아래 기준 중 하나라도 만족하면 후보로 포함하는 방식을 권장한다.

### 7.1 상태코드 기반

- `status_code >= 400`
- 특히 `401`, `403`, `404`, `500`, `502`, `503`

### 7.2 페이로드/문자 패턴 기반

다음 문자열이 `query_string`, `uri`, `raw_request`, `raw_log` 에 포함될 경우 의심 후보로 본다.

- SQL Injection 계열
  - `' or 1=1`
  - `union select`
  - `sleep(`
  - `benchmark(`
  - `information_schema`
- XSS 계열
  - `<script>`
  - `javascript:`
  - `onerror=`
  - `alert(`
- Path Traversal 계열
  - `../`
  - `..%2f`
  - `%2e%2e%2f`
- Command Injection 계열
  - `;cat /etc/passwd`
  - `| whoami`
  - `` `id` ``
  - `$(id)`
- 인코딩 우회/이상 요청
  - 과도한 `%25`
  - 이중 인코딩 흔적

### 7.3 반복성 기반

- 동일 IP가 짧은 시간 내 다양한 URI를 연속 탐색
- 동일 IP가 로그인/인증 관련 요청 반복
- 동일 URI에 비정상 파라미터를 반복 삽입

### 7.4 error 연계 기반

- `error_link_id` 가 존재
- 같은 `request_id` 로 error 로그와 연결됨
- 5xx 응답 또는 Apache error 발생

### 7.5 사용자 행태 기반

- 브라우저 UA가 아닌 자동화 도구 흔적
- referer 부재 + 고빈도 반복 + 탐색형 URI
- 의심 경로 순회

---

## 8. 추천 전달 구조

현재 환경에서는 아래 구조를 권장한다.

### 8.1 원본 export

`export_db_logs_cli.py` 로 KST 기준 JSON 생성

예:

- `today_logs_kst.json`
- 특정 시간대 JSON

이 파일은 **원본 보존용**이다.

### 8.2 분석용 정제 JSON 생성

원본 export 후, 별도 전처리 스크립트로 아래를 수행한다.

1. `socket.io` polling, 정적 리소스 등 노이즈 식별
2. 완전 제외 대상 제거
3. 반복 정상 요청 집계
4. 의심 요청 후보 선별
5. LLM 입력용 축약 JSON 생성

출력 예:

- `today_logs_kst_filtered.json`
- `today_logs_kst_candidates.json`
- `today_logs_kst_noise_summary.json`

### 8.3 LLM 전달용 최종 JSON 구조

권장 예시는 아래와 같다.

```json
{
  "meta": {
    "query_timezone": "Asia/Seoul",
    "analysis_window": {
      "start": "2026-04-02T00:00:00+09:00",
      "end_exclusive": "2026-04-03T00:00:00+09:00"
    },
    "total_exported_rows": 684,
    "filtered_out_rows": 520,
    "candidate_rows": 164
  },
  "noise_summary": [
    {
      "category": "socketio_polling",
      "count": 342,
      "note": "정상 세션 유지로 추정되는 반복 요청"
    }
  ],
  "analysis_candidates": [
    {
      "time": "2026-04-02T15:38:29.518+09:00",
      "src_ip": "192.168.35.27",
      "method": "GET",
      "uri": "/rest/products/search",
      "query_string": "?q=' OR 1=1 --",
      "status_code": 200,
      "request_id": "...",
      "reason_hint": ["SQLi_signature_in_query"]
    }
  ]
}
```

---

## 9. LLM 전달 방식별 전략 비교

### 9.1 방법 A: 원본 JSON 전체 전달

#### 장점
- 구현이 가장 단순함
- 빠르게 시도 가능

#### 단점
- 토큰 낭비 큼
- 노이즈에 취약
- 보고서 품질이 들쭉날쭉해짐

#### 권장도
- 낮음
- 로그 양이 매우 적을 때만

### 9.2 방법 B: 원본 + 노이즈 요약 + 후보 리스트 전달

#### 장점
- 현재 환경에 가장 적합
- 설명력과 효율이 균형적
- 보고서 품질이 안정적

#### 단점
- 전처리 스크립트가 하나 더 필요

#### 권장도
- 가장 높음

### 9.3 방법 C: 후보 리스트만 전달

#### 장점
- 토큰 효율 최고
- 공격 징후 중심 보고서에 유리

#### 단점
- 정상 맥락이 줄어듦
- 과도한 필터링 시 오탐/누락 가능

#### 권장도
- 중간
- 발표나 경보용 요약에 적합

---

## 10. 권장 파이프라인

현재 기준 추천 파이프라인은 아래와 같다.

```text
Apache 로그
  ↓
MariaDB 적재
  ↓
KST 기준 JSON export
  ↓
노이즈 필터링 / 축약 / 후보 추출
  ↓
LLM 1차 분석 (후보 분류)
  ↓
LLM 2차 분석 (보고서 작성)
```

### 10.1 1차 분석 목표

LLM이 각 후보를 다음처럼 분류하게 한다.

- `normal`
- `suspicious_scan`
- `suspicious_sqli`
- `suspicious_xss`
- `suspicious_path_traversal`
- `suspicious_command_injection`
- `suspicious_auth_abuse`
- `suspicious_bot_activity`
- `server_error_related`
- `unknown`

### 10.2 2차 분석 목표

1차 결과를 기반으로 사람이 읽는 보고서를 만든다.

예:

- 전체 요약
- 시간대별 주요 이벤트
- 의심 요청 목록
- 공격 유형별 분석
- 주요 근거 필드
- 심각도 평가
- 대응 권고
- 최종 결론

---

## 11. `socket.io` polling 필터링 권장 규칙

현재 환경에서 가장 먼저 넣을 만한 실전 규칙은 다음과 같다.

### 11.1 완전 제외 규칙 예시

다음 조건을 모두 만족하면 `filtered_out` 로 보낸다.

- `uri == "/socket.io/"`
- `status_code == 200`
- `method in ("GET", "POST")`
- `query_string` 에 의심 패턴 없음
- `user_agent` 가 일반 브라우저 패턴
- `referer` 가 내부 웹 서버 주소 또는 정상 페이지
- `is_suspicious == 0`
- `attack_label == "unknown"`

### 11.2 집계 규칙 예시

다음 키로 그룹화한다.

- `src_ip`
- `uri`
- `method`
- `status_code`
- `user_agent`
- 1분 또는 5분 단위 시간 버킷

그리고 개별 row 대신 아래 정보를 남긴다.

- count
- 첫 발생 시각
- 마지막 발생 시각
- 대표 request 예시 1건

### 11.3 예외 처리

다음 중 하나라도 해당되면 제외하지 않고 후보군으로 올린다.

- `status_code >= 400`
- `error_link_id` 존재
- `query_string` 에 의심 패턴 존재
- `duration_us` 나 `ttfb_us` 가 비정상적으로 큼
- 같은 세션에서 다른 의심 요청과 시간상 인접

즉, `socket.io` 라고 해서 무조건 버리면 안 되고, **정상 반복 패턴일 때만 제외/집계**한다.

---

## 12. 프롬프트 전략

권장 방식은 **2단계 프롬프트**다.

### 12.1 1차 분류 프롬프트

입력:

- `noise_summary`
- `analysis_candidates`

목표:

- 각 후보 이벤트를 보안 분류 라벨로 분류
- 근거 필드 명시
- 확신 수준 부여

### 12.2 2차 보고서 프롬프트

입력:

- 1차 분류 결과
- 메타정보
- 필요 시 noise summary

목표:

- 한국어 보안 분석 보고서 생성
- 공격 확정/의심/추가 확인 필요 구분
- 대응 권고 포함

### 12.3 프롬프트에 반드시 명시할 것

- 시간 기준은 KST
- 노이즈 요약은 참고용이며 본문 비중을 낮게 둘 것
- 공격 확정과 의심을 구분할 것
- 단순 404/단순 오타를 과대해석하지 말 것
- request_id, src_ip, uri, query_string, raw_request, status_code, error 관련 필드를 우선 볼 것

---

## 13. 오늘 기준 권장 실행 전략

오늘 작업에서는 아래 순서를 권장한다.

### 단계 1
KST 기준으로 원본 JSON export

### 단계 2
원본 JSON에서 아래를 분리

- `noise_summary`
- `analysis_candidates`
- 필요 시 `filtered_out_count`

### 단계 3
LLM에 `analysis_candidates` 중심으로 전달

### 단계 4
`noise_summary` 는 참고 섹션으로만 함께 제공

### 단계 5
최종 보고서 생성

이때 당장 가장 현실적인 선택은 아래다.

- 원본 JSON은 보존
- `socket.io` 정상 polling 은 집계 또는 제외
- 의심 요청 후보 위주로 LLM 전달
- 보고서는 한국어, KST 기준으로 생성

---

## 14. 최종 권고

현재 환경에서 가장 적절한 전략은 다음과 같다.

1. **DB는 원본 그대로 유지한다.**
2. **`export_db_logs_cli.py` 는 KST 기준 export 로 사용한다.**
3. **LLM에는 원본 전체가 아니라 분석용 정제 JSON을 우선 전달한다.**
4. **`socket.io` polling 같은 정상 반복 요청은 제거 또는 집계한다.**
5. **LLM은 1차 분류 + 2차 보고서 작성의 두 단계로 사용한다.**

즉, 정리하면 다음 문장으로 요약할 수 있다.

> **원본은 DB에 남기고, 분석은 정제본으로 수행하며, 노이즈는 제거보다 집계를 우선한다.**

---

## 15. 다음 구현 과제

다음 단계 구현 과제는 아래와 같다.

1. `export_db_logs_cli.py` KST 기준 최종 반영
2. `today_logs_kst.json` 생성 자동화
3. `noise_filter.py` 또는 `prepare_llm_input.py` 작성
4. `socket.io`, 정적 리소스, 반복 정상 요청 집계 규칙 구현
5. `analysis_candidates.json` 생성
6. LLM 1차 분류 프롬프트 템플릿 작성
7. LLM 2차 보고서 프롬프트 템플릿 작성

이 순서로 진행하면, 이후에는 “특정 시간대 로그 export → 정제 → LLM 분석 → 보고서 생성” 흐름을 거의 반복 가능한 형태로 운영할 수 있다.
