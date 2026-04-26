# 2026-04-26 D세트 R1 Traversal 비교

- 작성일: 2026-04-26
- 문서 역할: D세트 Round 1(Path Traversal) 산출물 비교 및 판단 정리
- 기준 문서: [docs/98B_D세트_비교실험.md](../../docs/98B_D세트_비교실험.md)
- 분석 구간: `2026-04-26 10:31:00 ~ 10:34:00 KST`
- 기준 데이터: Apache `security` 로그 표면 지표
- 출발지 IP: `192.168.56.110`
- known asset context: `192.168.56.105`, `192.168.56.108`, `192.168.56.109`, `192.168.56.110`

---

## 1. 실험 개요

D세트 R1은 Path Traversal 요청에 대해 다음을 확인하기 위한 실험이다.

1. `raw_request` / `raw_request_target`에 남은 `../` 계열 traversal payload를 보존하는가.
2. Apache 또는 전처리 단계의 path normalization으로 인해 공격 의도가 사라지지 않는가.
3. `/etc/passwd`, `.env` 같은 민감 파일 접근 의도를 식별하는가.
4. `%00` null byte suffix, `%2e%2e%2f` URL encoding 같은 우회 기법을 구분하는가.
5. `400/404` 응답을 근거로 실제 파일 노출 성공을 단정하지 않는가.

이번 R1은 D-01~D-03 중심의 traversal 핵심 검증은 성공했지만, D-04/D-05까지 포함한 전체 Round 1 설계 기준으로는 부분 수행으로 보는 것이 정확하다.

---

## 2. raw export 요약

| 항목 | 값 |
|---|---:|
| 분석 구간 | `2026-04-26 10:31:00 ~ 10:34:00 KST` |
| 전체 row | 6 |
| security row | 6 |
| access row | 0 |
| error row | 0 |
| source table option | `security` |
| src_ip | `192.168.56.110` |

raw export에는 총 6건의 security log가 포함되었다. 이 중 3건은 path traversal candidate로 선별되었고, 나머지 3건은 filtered out으로 분류되었다.

---

## 3. prepare 결과 요약

| 항목 | OpenAI input | Claude input |
|---|---:|---:|
| total_exported_rows | 6 | 6 |
| selected_source_rows | 6 | 6 |
| candidate_rows | 3 | 3 |
| distinct_incident_candidates | 3 | 3 |
| filtered_out_rows | 3 | 3 |
| supporting_events | 0 | 0 |
| false_positive_review_candidates | 0 | 0 |
| noise_group_count | 0 | 0 |
| filtered_out_breakdown | `low_signal_fuzzing` 2, `benign_fallback_html` 1 | 동일 |

prepare 결과는 양 provider 입력에서 동일하다.

해석:

- D-01, D-02, D-03은 `path_traversal` candidate로 정상 선별되었다.
- 나머지 3건은 후보에서 제외되었다.
- filtered out 3건은 `low_signal_fuzzing` 2건, `benign_fallback_html` 1건이다.
- R1의 핵심 평가는 candidate로 살아남은 D-01~D-03 중심으로 수행하는 것이 적절하다.

---

## 4. R1 항목별 평가

| ID | 실험 항목 | 관찰 결과 | 처리 결과 | 평가 |
|---|---|---|---|---|
| D-01 | Basic Traversal `/etc/passwd` | `/public/images/../../../../etc/passwd` 요청, `uri=/etc/passwd`, `status=400` | candidate | 성공 |
| D-02 | Null Byte Traversal | `/etc/passwd%00.pdf`, `status=400` | candidate | 성공 |
| D-03 | URL Encoded Traversal `.env` | `%2e%2e%2f` 기반 `.env` 접근, `status=404` | candidate | 성공 |
| D-04 | Absolute Path Access | 후보에 남지 않음 | filtered out 추정 | 핵심 평가 제외/보조 취급 |
| D-05 | PHP Wrapper Optional | Juice Shop 대상에서는 환경 부적합 가능 | filtered out 추정 | OpenCart/PHP 환경에서 별도 검증 권장 |

### 4.1 D-01 Basic Traversal

D-01은 다음 구조를 보였다.

```text
raw_request = GET /public/images/../../../../etc/passwd HTTP/1.1
uri         = /etc/passwd
status      = 400
```

평가:

- traversal payload는 `raw_request`에 명확히 남았다.
- Apache 정규화 후 `uri`는 `/etc/passwd`로 바뀌었다.
- 전처리에서 `traversal:raw_request_uri_diff`가 붙어 raw path와 normalized URI 차이가 보존되었다.
- `400` 응답이므로 실제 파일 노출 성공은 확인되지 않는다.

판정:

```text
Traversal intent observed.
Path normalization observed.
File disclosure not confirmed.
```

### 4.2 D-02 Null Byte Traversal

D-02는 `/etc/passwd%00.pdf` 형태의 null byte suffix 우회 시도다.

평가:

- `../../../../etc/passwd`와 `%00.pdf`가 함께 관찰되었다.
- Stage1은 이를 path traversal 및 null byte 우회 시도로 해석했다.
- `400 text/html` 응답이므로 Apache/서버 단계에서 거부된 요청으로 보는 것이 적절하다.
- 실제 파일 읽기 성공이나 우회 성공은 확인되지 않는다.

판정:

```text
Null byte traversal attempt observed.
Server rejection observed.
File disclosure not confirmed.
```

### 4.3 D-03 URL Encoded Traversal

D-03은 `%2e%2e%2f`를 활용한 encoded traversal이다.

평가:

- raw path에는 encoded traversal이 남았다.
- decoded/normalized view에서는 `/public/images/../../../.env` 형태가 확인되었다.
- `.env` 파일 접근 의도가 있으므로 sensitive file intent로 볼 수 있다.
- `404` 응답이므로 실제 `.env` 노출은 확인되지 않는다.

판정:

```text
Encoded traversal reconstruction observed.
.env access intent observed.
File disclosure not confirmed.
```

### 4.4 D-04 / D-05 처리

D-04와 D-05 계열로 보이는 요청은 Stage1 candidate에 남지 않았다.

해석:

- D-04는 기존 실행에서 `/public/images//etc/passwd`처럼 웹 경로 내부 문자열로 남을 수 있어 “절대 파일 시스템 경로 접근” 실험으로는 애매하다.
- D-05 `php://filter`는 OpenCart/PHP 환경 선택 항목이다. Juice Shop URL로 실행하면 PHP wrapper 검증으로 보기 어렵다.
- 따라서 이번 R1의 핵심 평가는 D-01~D-03에 한정하는 것이 적절하다.

후속 권장:

- D-04는 `$JUICE_URL/etc/passwd` 형태로 별도 재실험 가능
- D-05는 실제 OpenCart/PHP target URL 확인 후 별도 실행 권장

---

## 5. Stage1 결과 비교

| 항목 | OpenAI | Claude |
|---|---:|---:|
| processed_candidate_count | 3 | 3 |
| success_count | 3 | 3 |
| error_count | 0 | 0 |
| verdict | `suspicious_path_traversal` 3 | `suspicious_path_traversal` 3 |
| severity | `medium` 3 | `medium` 3 |
| confidence | high 중심 | high 중심 |

두 provider 모두 candidate 3건을 전부 `suspicious_path_traversal`로 분류했다. Stage1 error는 없었다.

### 5.1 OpenAI Stage1 성향

OpenAI는 각 후보를 path traversal 시도로 분류하면서도, `400/404` 응답을 근거로 실제 파일 노출 성공은 단정하지 않았다.

특징:

- `../../../../etc/passwd`와 `%00` 조합을 명확히 path traversal로 인식
- `/etc/passwd`, `.env` 민감 파일 접근 의도 식별
- `status_code=400/404`와 `resp_content_type=text/html`을 차단/오류 응답으로 해석
- 실제 파일 노출 성공은 미확정으로 유지

### 5.2 Claude Stage1 성향

Claude도 3건을 모두 path traversal 시도로 분류했다.

특징:

- null byte와 URL encoding을 우회 기법으로 적극 설명
- User-Agent의 `lab-d-set-trav-*` 라벨을 내부 테스트/자동화 테스트 정황으로 강하게 반영
- `400/404` 응답으로 실제 파일 노출은 성공하지 않았다고 제한
- OpenAI보다 “테스트 도구”, “우회 기법”, “체계적 시도” 표현이 강함

주의:

- 실험 환경에서는 UA 라벨 반영이 유용하지만, 일반 운영 환경에서는 User-Agent보다 `raw_request_target`, `status_code`, `response_body_bytes`, known asset 문맥을 우선해야 한다.

---

## 6. Stage2 결과 비교

### 6.1 OpenAI Stage2

OpenAI Stage2는 가장 보수적인 해석을 유지했다.

주요 결론:

- 동일 IP에서 path traversal 시도 3건 연속 관찰
- 대상은 `/etc/passwd`, `.env`
- `400/404 text/html` 응답이므로 실제 파일 노출이나 침해 성공은 확인되지 않음
- known asset IP이므로 내부 테스트/운영 점검 가능성 고려
- 후보 밖 탐색성 요청도 일부 존재하지만 공격 강도보다 시험/탐색 성격으로 해석 가능

평가:

- D세트의 Apache 로그 기반 한계를 잘 지켰다.
- “시도 정황”과 “성공 미확정”을 구분했다.
- 운영 확인 권고도 `review_raw_log`, `review_error_log`, `correlate_request_id`, `correlate_src_ip` 중심으로 적절하다.

### 6.2 Claude Stage2

Claude Stage2도 전반적으로 적절하다.

주요 결론:

- 3건의 경로 탐색 공격 시도 탐지
- 모두 동일 내부 IP에서 발생
- 서버 응답 400/404로 볼 때 실제 파일 노출은 성공하지 않음
- null byte, URL encoding 등 다양한 우회 기법 관찰
- User-Agent와 known asset 문맥상 내부 보안 검증 활동 가능성 높음

평가:

- traversal 시도와 우회 기법을 잘 묶었다.
- 실제 파일 노출 성공을 단정하지 않은 점은 적절하다.
- 다만 “방어 체계의 성숙도”, “공격자의 기술 수준” 등 일부 표현은 Apache 로그 표면만으로는 다소 강할 수 있다.

---

## 7. Provider별 비교 요약

| 비교 항목 | OpenAI | Claude |
|---|---|---|
| Stage1 verdict | `suspicious_path_traversal` 3 | 동일 |
| Stage1 severity | `medium` 3 | 동일 |
| 실제 파일 노출 단정 억제 | 매우 좋음 | 좋음 |
| raw_request/uri 차이 해석 | 적절 | 적절 |
| null byte 우회 설명 | 적절 | 더 적극적 |
| URL encoded traversal 설명 | 적절 | 더 적극적 |
| known asset 해석 | 내부 테스트 가능성 유지 | 내부 보안 검증 가능성을 더 강하게 표현 |
| UA label 활용 | 보조 근거 | 강하게 활용 |
| 권고 조치 | review/correlate/watch 중심 | investigate 표현이 일부 포함 |

---

## 8. 제대로 진행됐는지 판단

### 8.1 정상 진행된 부분

다음은 제대로 진행되었다.

- raw export 정상 생성
- security row 6건 수집
- D-01~D-03 핵심 traversal 요청이 candidate로 선별됨
- `raw_request`와 normalized `uri` 차이가 보존됨
- null byte 우회 시도 식별
- URL encoded traversal 및 `.env` 접근 의도 식별
- OpenAI/Claude 모두 path traversal 시도로 분류
- 두 provider 모두 실제 파일 노출 성공을 단정하지 않음

### 8.2 제한 또는 보완이 필요한 부분

다음은 제한적으로 해석해야 한다.

- candidate는 3건뿐이므로 R1 전체를 D-01~D-05 완전 수행으로 보기는 어렵다.
- D-04/D-05는 Stage1 핵심 후보에 남지 않아 이번 비교의 중심에서 제외한다.
- D-05는 Juice Shop 환경에서는 PHP wrapper 검증으로 적절하지 않다.
- filtered_out 3건은 별도 supporting_events로 보존되지 않았다.

최종 판단:

```text
D세트 R1은 D-01~D-03 Path Traversal 핵심 검증 관점에서는 성공이다.
다만 D-04/D-05까지 포함한 Round 1 전체 설계 기준으로는 부분 수행이며,
이번 비교 문서는 D-01~D-03 중심으로 제한해 해석하는 것이 정확하다.
```

---

## 9. Apache 로그 기반 한계

이번 R1에서 확인할 수 있는 것은 “시도”다.

확인 가능:

- traversal payload 전송
- null byte suffix 우회 시도
- URL encoded traversal 시도
- `/etc/passwd`, `.env` 접근 의도
- path normalization 정황
- `400/404` 오류 응답

확인 불가:

- 실제 파일 내용 반환
- `/etc/passwd` 내용 유출
- `.env` 내용 유출
- 애플리케이션 내부 file read 여부
- response body 원문에 민감 파일 내용 포함 여부

따라서 보고서 표현은 다음처럼 제한한다.

```text
Apache 로그상 path traversal 및 민감 파일 접근 의도는 관찰되었다.
그러나 response body 원문이 없고 상태 코드가 400/404이므로,
실제 파일 내용 노출이나 침해 성공은 확인되지 않았다.
```

---

## 10. 후속 권장 사항

1. D세트 R1 비교 문서는 D-01~D-03 중심으로 확정한다.
2. D-04 absolute path는 필요하면 `$JUICE_URL/etc/passwd` 형태로 별도 재실험한다.
3. D-05 PHP wrapper는 OpenCart/PHP target URL이 확인될 때만 별도 실행한다.
4. D세트 R2 HPP는 별도 export window로 진행한다.
5. D세트 R3 Directory Probing도 별도 export window로 진행한다.
6. R2/R3까지 끝난 뒤 D세트 통합 비교 문서를 작성한다.

---

## 11. 발표용 한 줄 정리

D세트 R1에서는 D-01~D-03 traversal 핵심 요청이 모두 `suspicious_path_traversal`로 선별되었고, 두 provider 모두 `/etc/passwd`, `.env`, null byte, URL encoding을 path traversal 시도로 적절히 해석했다. 다만 400/404 응답과 Apache 로그 한계상 실제 파일 노출 성공은 확인되지 않았으며, D-04/D-05는 이번 핵심 평가에서 제외하는 것이 타당하다.
