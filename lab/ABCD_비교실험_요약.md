# 2026-04-24 ~ 2026-04-26 전체 비교실험 요약

- 작성일: 2026-04-26
- 문서 역할: A/B/C/D세트 전체 실험 결과 요약
- 기준 데이터: Apache `security` 로그 중심 산출물
- 분석 원칙: Apache 로그 표면 지표 기반 보수적 해석

---

## 1. 전체 결론

A/B/C/D세트 실험은 전체적으로 완료되었다.

핵심 결론은 다음과 같다.

```text
LLM 기반 Apache 로그 분석 파이프라인은 SQLi, XSS, Traversal, HPP 계열의 고신호 요청을 대체로 잘 선별했다.
초기에는 Time-based SQLi, POST body HPP, Directory Probing burst grouping처럼 Apache 로그 표면만으로 판단이 어려운 영역의 한계가 확인되었다.
이후 Directory Probing burst grouping은 probing_sequence_summaries 도입으로 일부 개선되었다.
```

실험 전체에서 가장 중요한 원칙은 유지되었다.

- 실제 성공/침해/유출을 성급히 단정하지 않는다.
- response body 원문이 없으면 파일 내용 노출이나 XSS 실행 성공을 확정하지 않는다.
- raw POST body가 없으면 POST body payload와 HPP 처리 결과를 확정하지 않는다.
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

---

## 3. A세트 요약

A세트는 인증 흐름과 provider별 해석 차이를 확인하는 기반 실험이다.

핵심 관찰:

- 동일 로그 입력에서도 OpenAI와 Anthropic의 표현 강도가 다르다.
- OpenAI는 성공/침해 미확정을 더 강하게 유지한다.
- Anthropic은 흐름, campaign, known asset/test context를 더 적극적으로 묶는다.

A세트의 의의:

- 이후 B/C/D세트에서 provider별 해석 차이를 비교하는 기준선 역할을 했다.
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
- Stage2가 `/.git/config`, `/.env`, `/admin`, `/backup`, `/phpmyadmin` 등 주변 저신호 요청을 하나의 probing sequence로 해석할 수 있게 되었다.

---

## 7. Provider별 전체 경향

| 비교 항목 | OpenAI | Anthropic Claude |
|---|---|---|
| 전반 성향 | 보수적, 운영 보고형 | 기술 흐름/캠페인 서술 적극적 |
| 성공 단정 억제 | 매우 안정적 | 대체로 안정적, 표현은 더 강함 |
| evidence 구조화 | 핵심 토큰 중심, 과잉 단정 적음 | 상세하고 서사형 설명이 많음 |
| known asset 처리 | 내부 테스트 가능성 병기 | 내부 테스트/자동화 정황 적극 반영 |
| 권고 조치 | review/correlate/watch 중심 | investigate 표현이 더 자주 등장 |
| 위험도 산정 | 상대적으로 낮게 유지 | 일부 고신호 payload에 더 높은 severity 부여 |

---

## 8. 주요 성공 항목

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
| 성공 단정 억제 | 대체로 성공 |

---

## 9. 주요 한계 항목

| 항목 | 한계 |
|---|---|
| Time-based SQLi | 충분한 duration/ttfb 차이 미관찰 |
| POST body payload | raw POST body가 보이지 않음 |
| response body 검증 | 파일 내용, XSS 반영, DB 결과 확인 불가 |
| fallback HTML | 200 text/html 대용량 응답을 성공으로 보면 안 됨 |
| provider 표현 차이 | Claude는 더 강하게, OpenAI는 더 보수적으로 서술 |
| Directory probing | 개선 후 context 전달은 가능해졌지만, 실제 리소스 존재/노출은 여전히 확정 불가 |

---

## 10. 후속 개선 우선순위

1. fallback HTML 반복 응답의 “유사 크기” 허용 범위 검토
2. OpenCart 같은 PHP 기반 서비스에서 `probing_sequence_summaries` 일반성 확인
3. POST body visibility 한계 문서화 유지
4. Time-based SQLi는 재설계 전까지 실패/미검증으로 유지
5. D세트 R1 D-04/D-05는 OpenCart/PHP target 정리 후 필요 시 재실험

---

## 11. 최종 평가

A/B/C/D세트 실험은 전체적으로 목적을 달성했다.

다만 이 파이프라인은 “성공한 공격 판정기”가 아니라 “Apache 로그 표면에서 관찰 가능한 공격 정황을 보수적으로 정리하는 분석기”로 보는 것이 정확하다.

최종 결론:

```text
SQLi, XSS, Traversal, HPP 계열의 고신호 요청은 대체로 잘 탐지되었다.
Time-based, POST body, response body 기반 성공 판정은 여전히 한계가 남았다.
Directory probing sequence grouping은 probing_sequence_summaries 도입으로 개선되었다.
```

---

## 12. 발표용 한 줄 정리

A/B/C/D세트 전체 실험 결과, Apache 로그 기반 LLM 분석 파이프라인은 SQLi, XSS, Traversal, HPP 계열의 주요 시도를 잘 탐지했고, 실제 성공·유출·실행 여부는 보수적으로 제한했다. D세트 R3에서는 `probing_sequence_summaries` 도입으로 directory probing burst의 문맥 전달력이 개선되었으며, Time-based SQLi와 POST body visibility는 후속 과제로 남았다.
