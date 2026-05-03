# 98B_H세트_Static_Crawler_Noise_비교실험

- 작성 기준일: 2026-05-03
- 문서 역할: H세트 Static / Crawler / Scanner-like Noise 비교실험 설계
- 적용 범위: static asset baseline, health check, crawler-like access, scanner-like low-signal path
- 기준 데이터: Apache `security/access/error` 로그 표면 지표
- 핵심 전제: response body 원문, request body 원문, 브라우저 실행 여부, 서버 내부 파일 존재 여부는 확인하지 않는다

> H세트는 새 공격 성공을 검증하는 세트가 아니다. 실제 운영 로그에서 많이 섞이는 static asset, crawler-like, health check, scanner-like 저신호 요청을 공격 candidate로 과승격하지 않고 baseline/context/noise로 분리할 수 있는지 확인한다.

---

## 0. H세트 위치와 설계 철학

A~G세트는 SQLi, XSS, Traversal, HPP, PHP wrapper, Auth/Login behavior, HTTP method/protocol behavior를 검증했다.

H세트는 그 다음 단계로, 공격 payload 자체보다 운영 환경에서 자주 보이는 정상/저신호 웹 요청을 다룬다.

핵심 질문은 다음과 같다.

```text
1. static asset 요청이 공격 candidate로 과승격되지 않는가?
2. favicon/robots/sitemap/health check 요청이 probing 또는 취약점 시도로 과장되지 않는가?
3. crawler-like User-Agent가 정상/악성으로 단정되지 않고 baseline/context로 보존되는가?
4. scanner-like low-signal path가 단발 요청일 때 과승격되지 않는가?
5. 정상 browse와 scanner-like path가 섞일 때 둘을 분리해서 설명할 수 있는가?
```

H세트의 목적은 false positive 억제와 baseline/noise 해석 안정화다.

---

## 1. 비목표

H세트는 아래를 목표로 하지 않는다.

- crawler가 실제 Google/Bing인지 검증
- favicon/robots/sitemap 존재 여부를 보안 판단으로 사용
- static file 내용 검증
- `.env`, `backup.zip`, `server-status`의 실제 노출 성공 확인
- scanner IP 확정
- 자동 차단 또는 대응
- request body / response body 원문 분석

---

## 2. Apache 로그에서 볼 수 있는 것

- `method`
- `uri` / `path`
- `query_string`
- `status_code`
- `response_body_bytes`
- `duration_us` / `ttfb_us`
- `resp_content_type`
- `user_agent`
- `referer`
- same `src_ip` / time window
- repeated path or path family
- static asset extension

이 신호로는 요청의 표면 형태와 반복 문맥을 볼 수 있다. 실제 파일 내용, 브라우저 실행, crawler 검증, 서버 내부 상태는 확인할 수 없다.

---

## 3. Apache 로그만으로 볼 수 없는 것

- response body 내용
- JavaScript/CSS/image 파일 실제 내용
- crawler User-Agent 진위
- robots.txt 정책 내용
- sitemap 내용
- `.env`, backup, config 파일의 실제 노출 여부
- browser rendering 여부
- 서버 내부 파일 존재 여부

따라서 `200`, `404`, `text/html`, `response_body_bytes`만으로 정상/공격/노출 성공을 단정하면 안 된다.

---

## 4. Round 구성

| Round | 목적 | 해석 초점 |
|---|---|---|
| H R1 | Static / health baseline | static asset, favicon, health check 과승격 방지 |
| H R2 | Crawler-like baseline | robots/sitemap/crawler UA 해석 보수성 |
| H R3 | Scanner-like low-signal path | 흔한 scanner path의 context-only 보존 |
| H R4 | Mixed benign + scanner-like | 정상 browse와 scanner-like path 분리 |

초기 실행 우선순위는 H R1이다. H R2/R3/R4는 R1 결과를 보고 순차 진행한다.

---

## 5. H R1 — Static / health baseline

### 목표

정적 자산, favicon, robots, sitemap, health check, 일반 browse 요청이 공격 candidate로 과승격되지 않는지 확인한다.

### 케이스

| ID | 요청 | 기대 관찰 | 기대 해석 | 금지 |
|---|---|---|---|---|
| H-R1-01 | `GET /favicon.ico` | `status_code`, bytes 관찰 | static/favicon baseline 가능성 | probing 단정 |
| H-R1-02 | `GET /robots.txt` | `status_code`, bytes 관찰 | robots baseline 가능성 | crawler 정책 해석 단정 |
| H-R1-03 | `GET /sitemap.xml` | `status_code`, bytes 관찰 | sitemap baseline 가능성 | 사이트 구조 노출 성공 단정 |
| H-R1-04 | `GET /assets/app.js` | static JS path 관찰 | static asset baseline 가능성 | XSS/JS 실행 단정 |
| H-R1-05 | `GET /assets/style.css` | static CSS path 관찰 | static asset baseline 가능성 | 공격 단정 |
| H-R1-06 | `GET /images/logo.png` | image path 관찰 | static asset baseline 가능성 | 파일 노출 단정 |
| H-R1-07 | `GET /api/health` | health-like endpoint 관찰 | health check baseline 가능성 | auth/API abuse 단정 |
| H-R1-08 | `GET /` | normal browse | normal baseline | 공격 단정 |

### 기대 prepare 결과

```text
- analysis_candidates=0 또는 매우 낮은 수
- static asset / health / normal baseline이 filtered_out 또는 noise_summary로 정리
- ip_behavior_aggregates가 생겨도 context-only
- response_body_bytes나 status=200만으로 성공/노출 단정 없음
```

### 향후 hint 후보

이번 설계 문서에서는 구현하지 않는다. 실행 결과를 보고 필요하면 검토한다.

```text
static_asset_baseline
baseline:static_asset
baseline:favicon
baseline:robots_txt
baseline:sitemap_xml
baseline:health_check
baseline:normal_browse
```

---

## 6. H R2 — Crawler-like baseline

### 목표

crawler-like User-Agent와 robots/sitemap/category/product browse 요청이 공격으로 과승격되지 않는지 확인한다.

### 케이스

| ID | 요청 | User-Agent | 기대 해석 |
|---|---|---|---|
| H-R2-01 | `GET /robots.txt` | Googlebot-like | crawler-like baseline 가능성 |
| H-R2-02 | `GET /sitemap.xml` | Googlebot-like | sitemap crawl 가능성 |
| H-R2-03 | `GET /products/` | generic crawler | crawl/browse context |
| H-R2-04 | `GET /category/` | generic crawler | crawl/browse context |
| H-R2-05 | `GET /` | browser-like UA | normal browse baseline |

주의:

- User-Agent가 Googlebot/Bingbot처럼 보여도 실제 crawler라고 단정하지 않는다.
- User-Agent는 spoof 가능하다.
- crawler-like 접근이 반복되더라도 성공/침해 단정은 하지 않는다.

### 향후 hint 후보

```text
crawler_like_context
baseline:robots_txt
baseline:sitemap_xml
baseline:crawler_like_browse
```

---

## 7. H R3 — Scanner-like low-signal path

### 목표

운영 로그에서 자주 보이는 scanner-like path가 단발 또는 짧은 burst로 들어왔을 때 과승격되지 않고, context-only로 보존되는지 확인한다.

### 케이스

| ID | 요청 | 기대 관찰 | 기대 해석 | 금지 |
|---|---|---|---|---|
| H-R3-01 | `GET /wp-login.php` | status 관찰 | common scanner path context | WordPress 취약 단정 |
| H-R3-02 | `GET /wp-admin/` | status 관찰 | common scanner path context | 관리자 접근 성공 단정 |
| H-R3-03 | `GET /.env` | status 관찰 | sensitive config path probing 가능성 | `.env` 노출 성공 단정 |
| H-R3-04 | `GET /phpinfo.php` | status 관찰 | sensitive diagnostic path probing 가능성 | phpinfo 노출 성공 단정 |
| H-R3-05 | `GET /server-status` | status 관찰 | server-status probing 가능성 | Apache status 노출 성공 단정 |
| H-R3-06 | `GET /backup.zip` | status 관찰 | backup artifact probing 가능성 | backup 파일 노출 성공 단정 |

### 기대 prepare 결과

```text
- 단발 scanner-like path는 high candidate로 과승격하지 않음
- 여러 sensitive/scanner path가 짧은 window에 있으면 probing_sequence_summaries 또는 ip_behavior_aggregates로 보존 가능
- 200/403/404만으로 노출 성공/차단 성공을 단정하지 않음
```

### 향후 hint 후보

```text
scanner_path_context
sensitive_path_probe_context
baseline:not_applicable
```

---

## 8. H R4 — Mixed benign + scanner-like

### 목표

정상 browse/static 요청과 scanner-like path가 같은 시간대에 섞일 때, pipeline이 이를 하나의 공격으로 과도하게 묶지 않고 baseline과 scanner context를 분리할 수 있는지 확인한다.

### 케이스 후보

```text
GET /
GET /assets/app.js
GET /favicon.ico
GET /.env
GET /wp-login.php
GET /robots.txt
```

기대:

```text
- normal/static/robots 요청은 baseline
- scanner-like/sensitive path는 low-signal context
- 두 범주가 같은 src_ip/time window에 있어도 성공/침해 단정 금지
```

---

## 9. prepare 관찰 포인트

H세트 실행 후 prepare 단계에서 확인할 사항:

- static asset 요청이 candidate로 과승격되는가?
- favicon/robots/sitemap이 probing으로 과장되는가?
- health check가 auth/API abuse나 method anomaly로 과승격되는가?
- crawler-like User-Agent가 정상/악성으로 단정되는가?
- scanner-like path가 단발일 때 high candidate로 올라가는가?
- 여러 sensitive path가 짧은 window에 있을 때 context-only summary로 보존되는가?
- 정상 browse와 scanner-like path가 섞일 때 baseline과 scanner context가 분리되는가?

---

## 10. Stage1 / Stage2 체크포인트

분석 결과에서 다음을 확인한다.

- static asset / health / robots / sitemap을 정상 baseline 또는 low-signal로 설명하는가
- crawler-like UA를 실제 Google/Bing으로 단정하지 않는가
- scanner-like path를 보더라도 노출 성공을 단정하지 않는가
- `/.env`, `/backup.zip`, `/server-status`의 `200/403/404`만으로 파일 노출/차단 성공을 단정하지 않는가
- same src_ip/time window context를 보수적으로 사용하는가
- candidate가 없거나 적어도 Stage2가 이를 실패로 보지 않고 baseline/noise 결과로 설명하는가

---

## 11. Python runner 계획

H세트도 Python runner 기반으로 관리한다.

예상 파일:

```text
lab/h_set/README.md
lab/h_set/run_h_r1_static_baseline.py
lab/h_set/run_h_r2_crawler_baseline.py
lab/h_set/run_h_r3_scanner_low_signal.py
lab/h_set/run_h_r4_mixed_baseline_scanner.py
```

초기 구현 우선순위는 H R1이다.

---

## 12. 실행 전 주의

- 승인된 로컬 실험 환경에서만 실행
- public target 금지
- crawler-like UA는 실제 crawler 검증 용도가 아님
- scanner-like path는 실제 민감 파일 접근 성공을 검증하는 용도가 아님
- runner는 response body 원문을 저장하지 않음
- raw export JSON, LLM input JSON은 공개 비권장

---

## 13. 산출물 관리

공개 또는 공유에 적합한 산출물:

- H세트 비교 Markdown
- 최종 Stage2 Markdown
- 통합 요약 문서

공개 또는 공유에 부적합한 산출물:

- raw export JSON
- LLM input JSON
- stage2_report_input JSON
- analysis_candidates JSON
- runner request body가 포함될 수 있는 실행 로그

---

## 14. 다음 작업

1. H R1 Python runner 설계
2. H R1 실행
3. prepare-only 확인
4. 필요 시 static/health baseline context 보강
5. Stage1 / Stage2 실행
6. H R1 비교 문서 작성
7. H R2/R3 순차 진행

---

## 15. 발표용 한 줄 정리

H세트는 실제 운영 로그에서 빈번히 나타나는 static asset, crawler-like, health check, scanner-like 저신호 요청을 공격으로 과승격하지 않고 baseline/context/noise로 분리할 수 있는지 확인하는 실험이다.
