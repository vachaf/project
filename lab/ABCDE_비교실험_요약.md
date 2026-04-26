# 2026-04-24 ~ 2026-04-26 전체 비교실험 요약

- 작성일: 2026-04-26
- 문서 역할: A/B/C/D/E세트 전체 실험 결과 요약
- 기준 데이터: Apache `security` 로그 중심 산출물
- 분석 원칙: Apache 로그 표면 지표 기반 보수적 해석
- 비고: 파일명은 기존 `ABCD_비교실험_요약.md`를 유지하지만, 현재 내용은 E세트 OpenCart 결과까지 포함한다.

---

## 1. 전체 결론

A/B/C/D/E세트 실험은 전체적으로 주요 목적을 달성했다.

핵심 결론은 다음과 같다.

```text
LLM 기반 Apache 로그 분석 파이프라인은 SQLi, XSS, Traversal, HPP, PHP file disclosure 계열의 고신호 요청을 대체로 잘 선별했다.
초기에는 Time-based SQLi, POST body HPP, Directory Probing burst grouping, PHP wrapper file disclosure처럼 Apache 로그 표면만으로 판단이 어렵거나 rule hint가 부족한 영역의 한계가 확인되었다.
이후 double decode, HTML entity decode, supporting_events, false_positive_review_candidates, probing_sequence_summaries, PHP file disclosure hint 보강으로 탐지 보존성과 오탐 억제가 개선되었다.
```

실험 전체에서 가장 중요한 원칙은 유지되었다.

- 실제 성공/침해/유출을 성급히 단정하지 않는다.
- response body 원문이 없으면 파일 내용 노출이나 XSS 실행 성공을 확정하지 않는다.
- raw POST body가 없으면 POST body payload와 HPP 처리 결과를 확정하지 않는다.
- `status_code=200`, `text/html`, `response_body_bytes`는 보조 지표이지 성공 증거가 아니다.
- provider별 표현 차이는 있지만 최종 판단은 Apache 로그 표면 지표를 기준으로 보정한다.

---

## 2. 세트별 요약

| 세트 | 주제 | 주요 결과 | 최종 판단 |
|---|---|---|---|
| A세트 | 인증/기본 흐름 | provider별 보수성 차이 확인 | 완료 |
| B세트 R1 | SQLi / POST body visibility | GET SQLi 가시성 확인, POST body 한계 확인 | 완료 |
| B세트 R2A | Boolean / Time-based SQLi | xclose Boolean은 byte delta 성공, Time-based는 실패 | 완료 |
| B세트 R2B | SQLi evasion / chain / FP | double encoding 보존, temporal context, FP 분리 | 완료 |
| C세트 | XSS / encoding / FP | HTML entity decode, XSS 세부 hint, FP review 개선 | 완료 |
| D세트 R1 | Path Traversal | D-01~D-03 탐지 성공 | 완료, 부분 제한 |
| D세트 R2 | HPP | HPP+SQLi / HPP+XSS 탐지 성공 | 완료 |
| D세트 R3 | Directory Probing | 초기에는 sequence grouping이 약했으나, 개선 후 context 전달력 강화 | 완료, 개선 반영 |
| E세트 R1 | OpenCart route traversal / admin path | route parameter traversal 탐지, admin path context-only 보존 | 완료 |
| E세트 R2 | OpenCart PHP wrapper / config exposure | 수정 후 php://filter 2건 모두 candidate 보존, direct config path 과승격 방지 | 완료, 개선 반영 |
| E세트 R3 | OpenCart product/search SQLi/XSS | SQLi 1건, XSS 2건 모두 candidate 및 Stage1 분류 성공 | 완료 |

---

## 3. A세트 요약

A세트는 인증 흐름과 provider별 해석 차이를 확인하는 기반 실험이다.

핵심 관찰:

- 동일 로그 입력에서도 OpenAI와 Anthropic의 표현 강도가 다르다.
- OpenAI는 성공/침해 미확정을 더 강하게 유지한다.
- Anthropic은 흐름, campaign, known asset/test context를 더 적극적으로 묶는다.

A세트의 의의:

- 이후 B/C/D/E세트에서 provider별 해석 차이를 비교하는 기준선 역할을 했다.
- 단순 verdict 일치 여부보다 “같은 증거를 얼마나 강하게 해석하는가”가 중요하다는 점을 확인했다.

---

## 4. B세트 요약

B세트는 SQLi와 HPP, Time-based 탐지를 중심으로 진행했다.

### 4.1 B세트 R1

R1에서는 GET 기반 SQLi의 가시성과 POST body visibility 한계를 확인했다.

결론:

- GET query string에 남는 SQLi payload는 비교적 잘 탐지된다.
- POST body payload는 현재 Apache 로그 baseline에서 직접 보이지 않는다.
- 따라서 POST body 기반 공격은 method, URI, content-type, content-length, status 정도로만 보수적으로 해석해야 한다.

### 4.2 B세트 R2A

R2A에서는 Boolean Blind와 Time-based SQLi를 분리해 검증했다.

결론:

- xclose 기반 Boolean pair는 `response_body_bytes` 차이가 명확해 성공했다.
- Time-based SQLi는 `duration_us` / `ttfb_us` 기준으로 충분한 지연 차이가 관찰되지 않아 실패로 기록했다.
- Apache 로그에서 Time-based를 성공시키려면 payload와 애플리케이션/DB 특성에 대한 추가 검증이 필요하다.

### 4.3 B세트 R2B

R2B에서는 SQLi evasion, temporal chain, false positive bait를 검증했다.

결론:

- double URL encoding SQLi는 candidate로 보존되었다.
- chain 중간 저신호 step은 incident로 과승격하지 않고 supporting context로 보존되었다.
- educational SQL search는 likely_false_positive 또는 supporting context로 분리되었다.
- 개선 핵심은 탐지 건수 증가보다 보존성, 오탐 억제, Stage2 문맥 제공 강화다.

---

## 5. C세트 요약

C세트는 XSS와 encoding reconstruction, false positive suppression을 검증했다.

핵심 성과:

- 기본 `<script>` payload 탐지 성공
- URL/double encoding 계열 XSS 의미 복원
- `onerror`, `javascript:`, `document.cookie`, external navigation/exfil intent hint 강화
- HTML entity decode view 추가 후 C-08 오탐 개선
- C-10 tutorial 검색은 candidate로 과승격하지 않고 false positive review context로 보존

C세트 결론:

```text
XSS 탐지와 의미 복원은 성공했다.
다만 Apache 로그만으로 브라우저 실행, 쿠키 탈취, 외부 전송 성공은 확정할 수 없다.
```

---

## 6. D세트 요약

D세트는 Traversal, HPP, Directory Probing을 분리해 검증했다.

### 6.1 D세트 R1 — Traversal

결론:

- D-01~D-03은 path traversal candidate로 선별되었다.
- `/etc/passwd`, `.env`, null byte, URL encoded traversal 의도를 두 provider 모두 잘 판단했다.
- `400/404` 응답이므로 실제 파일 노출은 단정하지 않았다.
- D-04/D-05는 이번 핵심 평가에서 제외했다.

### 6.2 D세트 R2 — HPP

결론:

- HPP+SQLi와 HPP+XSS는 candidate로 선별되었다.
- benign duplicate HPP는 candidate로 과승격하지 않고 supporting context로 보존되었다.
- POST body HPP는 raw body visibility 한계로 핵심 평가에서 제외했다.

### 6.3 D세트 R3 — Directory Probing

초기 결론:

- 10건의 directory probing 성격 요청이 raw export에 수집되었다.
- `/server-status` 403만 candidate로 선별되었다.
- 나머지는 `low_signal_dir_probe` / `low_signal_fuzzing`으로 낮춰졌다.
- 보수적 판단은 성공했지만, burst probing sequence grouping은 부족했다.

개선 후 결론:

- `probing_sequence_summaries`를 추가했다.
- candidate 수와 severity는 그대로 유지했다.
- 저신호 directory probe를 incident로 과승격하지 않았다.
- Stage2가 `/.git/config`, `.env`, `/admin`, `/backup`, `/phpmyadmin` 등 주변 저신호 요청을 하나의 probing sequence로 해석할 수 있게 되었다.

---

## 7. E세트 요약 — OpenCart 일반화 검증

E세트는 Juice Shop이 아닌 OpenCart 환경에서 기존 탐지 로직과 최근 코드 보강이 일반화되는지 확인하기 위해 수행했다.

OpenCart는 Juice Shop과 구조가 다르다.

| 항목 | Juice Shop | OpenCart |
|---|---|---|
| 앱 구조 | Node/SPA/API 중심 | PHP/OpenCart route 중심 |
| 주요 endpoint | `/rest/products/search`, `/public/images/...` | `/index.php?route=...` |
| 응답 유형 | JSON API 또는 SPA fallback HTML | 대부분 `text/html` |
| 주요 해석 축 | API query, path 정규화, fallback 구분 | `route=`, `search=`, PHP wrapper, admin/config path |
| 주의점 | SPA fallback 200을 성공으로 오해하지 말 것 | 200 text/html, 0B body, PHP empty output을 성공으로 오해하지 말 것 |

### 7.1 E세트 R1 — route traversal / admin path

R1에서는 OpenCart의 route parameter와 admin path 접근을 검증했다.

결론:

- `route=../../../../etc/passwd` 형태의 route parameter traversal intent는 candidate로 탐지되었다.
- `/admin/`, `/admin/index.php`는 개별 incident로 과승격하지 않고 probing context로 보존되었다.
- OpenCart에서는 `/admin/index.php`가 실제 관리자 로그인 페이지일 수 있으므로, Juice Shop의 SPA fallback과 다르게 해석해야 한다.

### 7.2 E세트 R2 — PHP wrapper / config exposure

R2에서는 PHP wrapper와 config path exposure intent를 검증했다.

초기 문제:

- `route=php://filter/convert.base64-encode/resource=index.php`는 candidate가 되었다.
- 하지만 `path=php://filter/convert.base64-encode/resource=config.php`는 candidate에서 빠졌다.
- `/config.php`, `/admin/config.php`는 직접 접근이지만 body 0B라 파일 노출 성공 근거는 없었다.

코드 수정:

- `FILE_DISCLOSURE_PATTERNS`와 `detect_file_disclosure_hints()` 추가
- `php://filter`, `convert.base64-encode`, `resource=`, `config.php`, `admin/config.php`, `index.php`를 일반 file disclosure intent로 점수화
- direct `/config.php`, `/admin/config.php`는 단발이면 candidate로 과승격하지 않고 context-only 유지

수정 후 결과:

- `route=php://filter...index.php`는 score 상승 및 candidate 유지
- `path=php://filter...config.php`는 신규 candidate 승격
- 두 wrapper 요청 모두 `suspicious_file_disclosure` hint를 받음
- `/config.php`, `/admin/config.php`는 `low_signal_dir_probe` / `probing_sequence_summaries`로 보존

R2 결론:

```text
PHP wrapper 기반 source/config disclosure intent 탐지는 개선 후 성공했다.
다만 Stage1 최종 verdict는 아직 suspicious_path_traversal로 수렴하는 경향이 있어, suspicious_file_disclosure verdict 정식화를 후속 개선으로 남긴다.
```

### 7.3 E세트 R3 — product/search SQLi/XSS

R3에서는 OpenCart의 `product/search` 구조에서 SQLi/XSS 탐지가 가능한지 검증했다.

결과:

- `search=x')) OR 1=1 --` → SQLi candidate / `suspicious_sqli`
- `search=<script>alert(1)</script>` → XSS candidate / `suspicious_xss`
- `search=&#x3C;script&#x3E;alert(1)...` → HTML entity XSS candidate / `suspicious_xss`

결론:

- OpenCart의 `/index.php?route=product/search&search=...` 구조에서도 기존 SQLi/XSS 탐지 로직이 동작했다.
- C세트에서 보강한 HTML entity decode가 OpenCart에서도 정상 동작했다.
- R3 재수행은 필수는 아니다.

---

## 8. Provider별 전체 경향

| 비교 항목 | OpenAI | Anthropic Claude |
|---|---|---|
| 전반 성향 | 보수적, 운영 보고형 | 기술 흐름/캠페인 서술 적극적 |
| 성공 단정 억제 | 매우 안정적 | 대체로 안정적, 표현은 더 강함 |
| evidence 구조화 | 핵심 토큰 중심, 과잉 단정 적음 | 상세하고 서사형 설명이 많음 |
| known asset 처리 | 내부 테스트 가능성 병기 | 내부 테스트/자동화 정황 적극 반영 |
| 권고 조치 | review/correlate/watch 중심 | investigate/P1 표현이 더 자주 등장 |
| 위험도 산정 | 상대적으로 낮게 유지 | 일부 고신호 payload에 더 높은 severity 부여 |
| OpenCart/PHP 해석 | 성공 미확정 원칙을 강하게 유지 | PHP wrapper/config exposure 위험을 더 적극적으로 설명 |

---

## 9. 주요 성공 항목

| 항목 | 결과 |
|---|---|
| GET SQLi 탐지 | 성공 |
| Boolean xclose SQLi byte delta | 성공 |
| double encoded SQLi 보존 | 성공 |
| XSS HTML entity decode | 성공 |
| XSS FP bait 분리 | 성공 |
| Traversal D-01~D-03 탐지 | 성공 |
| HPP+SQLi / HPP+XSS 결합 탐지 | 성공 |
| Directory probing sequence context 전달 | 개선 후 성공 |
| OpenCart route traversal 탐지 | 성공 |
| OpenCart PHP wrapper file disclosure intent | 개선 후 성공 |
| OpenCart product/search SQLi/XSS 탐지 | 성공 |
| 성공 단정 억제 | 대체로 성공 |

---

## 10. 주요 한계 항목

| 항목 | 한계 |
|---|---|
| Time-based SQLi | 충분한 duration/ttfb 차이 미관찰 |
| POST body payload | raw POST body가 보이지 않음 |
| response body 검증 | 파일 내용, XSS 반영, DB 결과 확인 불가 |
| fallback HTML | 200 text/html 대용량 응답을 성공으로 보면 안 됨 |
| PHP empty output | `/config.php` 200/0B를 안전 또는 성공으로 단정하면 안 됨 |
| provider 표현 차이 | Claude는 더 강하게, OpenAI는 더 보수적으로 서술 |
| Directory probing | 개선 후 context 전달은 가능해졌지만, 실제 리소스 존재/노출은 여전히 확정 불가 |
| Stage1 verdict taxonomy | `php://filter`가 아직 `suspicious_path_traversal`로 흡수되는 경향 |

---

## 11. 코드 개선 요약

비교 실험을 통해 반영한 주요 코드 개선은 다음이다.

| 개선 항목 | 목적 | 관련 세트 |
|---|---|---|
| URL decode depth 1/2 분석 | double encoding payload 복원 | B, C, E |
| HTML entity decode view | entity encoded XSS 복원 | C, E |
| educational SQL/XSS 완화 | false positive 감소 | B, C |
| supporting_events | 후보 밖 저신호 문맥 보존 | B, D |
| false_positive_review_candidates | 교육용/오탐 가능 요청 보존 | C |
| probing_sequence_summaries | directory probing burst context 전달 | D, E |
| PHP file disclosure hint | `php://filter`/`resource=` 탐지 보강 | E |
| UTC 저장 / KST export 보강 | 서버 timezone 차이 제거 | E 운영 과정 |

---

## 12. 후속 개선 우선순위

### 12.1 우선순위 높음

1. E세트 R1/R2/R3 통합 비교 문서 작성
2. A~E 전체 비교 실험 요약을 발표용 구조로 압축
3. 실행 명령의 `known_asset_ips`에 OpenCart IP `192.168.56.111` 포함

### 12.2 선택적 코드 개선

1. `suspicious_file_disclosure` Stage1 verdict 정식화
2. SQLi xclose/quote termination 세부 hint 추가
3. direct config path `200/0B` context-only hint 세분화
4. Stage2 prompt에 `php://filter/convert.base64-encode`의 source disclosure 의미 설명 보강
5. fallback HTML 반복 응답의 “유사 크기” 허용 범위 검토

### 12.3 보류 또는 제한 유지

1. Time-based SQLi는 재설계 전까지 실패/미검증으로 유지
2. POST body payload 분석은 Apache 로그 baseline만으로는 한계 유지
3. response body 원문 기반 성공 판정은 현 구조에서는 하지 않음

---

## 13. 최종 평가

A/B/C/D/E세트 실험은 전체적으로 목적을 달성했다.

다만 이 파이프라인은 “성공한 공격 판정기”가 아니라 “Apache 로그 표면에서 관찰 가능한 공격 정황을 보수적으로 정리하는 분석기”로 보는 것이 정확하다.

최종 결론:

```text
SQLi, XSS, Traversal, HPP, PHP file disclosure 계열의 고신호 요청은 대체로 잘 탐지되었다.
Time-based, POST body, response body 기반 성공 판정은 여전히 한계가 남았다.
Directory probing sequence grouping과 PHP wrapper 탐지는 실험 중 발견된 약점을 코드 개선으로 보강했다.
Juice Shop뿐 아니라 OpenCart에서도 주요 탐지 로직이 일정 수준 일반화됨을 확인했다.
```

---

## 14. 발표용 한 줄 정리

A~E세트 전체 실험 결과, Apache 로그 기반 LLM 분석 파이프라인은 SQLi, XSS, Traversal, HPP, PHP file disclosure 계열의 주요 시도를 잘 탐지했고, 실제 성공·유출·실행 여부는 보수적으로 제한했다. 특히 `probing_sequence_summaries`와 PHP file disclosure hint 보강을 통해 후보 밖 탐색 문맥과 OpenCart/PHP 계열 공격 해석력이 개선되었으며, Time-based SQLi와 POST body visibility는 후속 과제로 남았다.
