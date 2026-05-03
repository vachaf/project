# A~G 비교실험 요약

- 작성일: 2026-05-03
- 문서 역할: A~G세트 전체 실험 결과의 현재 요약
- 기준 데이터: Apache `security` 로그 중심 산출물
- 분석 원칙: Apache 로그 표면 지표 기반 보수적 해석

---

## 1. 전체 결론

A~G세트 실험은 현재까지 주요 목적을 달성했다.

핵심 결론은 다음과 같다.

```text
LLM 기반 Apache 로그 분석 파이프라인은 SQLi, XSS, Traversal, HPP, PHP file disclosure, L3 고신호 패턴, Auth/Login abuse context, HTTP method/protocol behavior context를 대체로 보수적으로 선별·요약할 수 있다.
다만 이 파이프라인은 성공한 공격 판정기가 아니라, Apache 로그 표면에서 관찰 가능한 공격 정황을 정리하는 분석기다.
```

계속 유지할 원칙:

- 실제 성공/침해/유출을 성급히 단정하지 않는다.
- response body 원문이 없으면 파일 내용 노출이나 XSS 실행 성공을 확정하지 않는다.
- raw POST body가 없으면 POST body payload, login credential, 인증 성공 여부를 확정하지 않는다.
- `status_code=200`, `text/html`, `response_body_bytes`는 보조 지표이지 성공 증거가 아니다.
- `PUT` / `DELETE` / `TRACE` / `OPTIONS`는 method behavior context로 보되 업로드·삭제·XST·CORS 취약점 성공을 단정하지 않는다.
- malformed request, bad protocol, missing/odd Host는 protocol anomaly context로만 보고 우회/침해 성공을 단정하지 않는다.
- provider별 표현 차이는 있지만 최종 판단은 Apache 로그 표면 지표를 기준으로 보정한다.

---

## 2. 세트별 현재 요약

| 세트 | 주제 | 주요 결과 | 최종 판단 |
|---|---|---|---|
| A세트 | 인증/기본 흐름 | provider별 보수성 차이 확인 | 완료 |
| B세트 | SQLi / POST body visibility / evasion | GET SQLi, Boolean xclose, double encoding 보존 성공. Time-based는 보류 | 완료, Time-based 제한 |
| C세트 | XSS / encoding / FP | HTML entity decode, XSS FP review, tutorial 검색 오탐 억제 | 완료 |
| D세트 | Traversal / HPP / Directory probing | Traversal/HPP 탐지, probing sequence context 보존 | 완료, 개선 반영 |
| E세트 | OpenCart / PHP wrapper / search baseline | PHP wrapper file disclosure, direct config path 과승격 방지, search SQLi/XSS와 정상 baseline 분리 | 완료, 개선 반영 |
| F세트 R1 | Auth/Login abuse | 반복 401, rapid burst, 401/200 혼재를 `auth_behavior_summaries`로 보존. candidate 43 → 3, supporting_events 0 → 40 | Round 1 완료 |
| F세트 R2A | 저속/혼합/FP baseline | Python runner 기반 실행. 저속 반복 401, browse 혼재, Chrome/CI 200 baseline을 보수적으로 분리 | Round 2A 완료 |
| F세트 R2B | 응답 차이 관찰형 | existing/nonexistent/lockout-probe 의도 그룹 모두 401/26B로 유사하게 관찰. user enumeration/lockout 발동 단정 불가 | Round 2B 완료 |
| G세트 R1 | HTTP method probing | OPTIONS/TRACE/PUT/DELETE/HEAD/GET를 `method_behavior_summaries`로 context-only 보존. HEAD/GET baseline 과승격 없음 | Round 1 완료 |
| G세트 R2 | protocol / malformed request | FAKEMETHOD, HTTP/1.0, bad protocol, missing/odd Host, long path를 `protocol_anomaly_summaries`로 context-only 보존 | Round 2 완료 |

---

## 3. 주요 개선 요약

| 개선 항목 | 목적 | 관련 세트 |
|---|---|---|
| URL decode depth 1/2 | double encoding payload 복원 | B, C, E, L3 |
| HTML entity decode view | entity encoded XSS 복원 | C, E |
| educational SQL/XSS 완화 | false positive 감소 | B, C |
| supporting_events | 후보 밖 저신호 문맥 보존 | B, D, F |
| false_positive_review_candidates | 교육용/오탐 가능 요청 보존 | C |
| probing_sequence_summaries | directory probing burst context 전달 | D, E |
| suspicious_file_disclosure | PHP wrapper/source disclosure를 traversal과 구분 | E |
| normal search baseline 분리 | 정상 검색을 reference baseline으로 보존 | E |
| ip_behavior_aggregates | same src_ip/time window 행동 문맥 보존 | D, E, F, G |
| auth_behavior_summaries | 반복 auth endpoint, 401/200 혼재, rapid/저속 반복 문맥 보존 | F |
| method_behavior_summaries | HTTP method probing과 baseline method를 성공 단정 없이 context로 보존 | G |
| protocol_anomaly_summaries | malformed/protocol request를 우회·침해 단정 없이 context로 보존 | G |
| L3 high-signal hints | Log4Shell, SSRF, SSTI, webshell-like access 보존 | L3 fixture |
| Stage dry-run regression | LLM 호출 없이 schema/prompt/report-input 골격 검증 | 전체 |
| prepare 모듈 분리 1단계 | decoders/l3_hints를 동작 변경 없이 분리 | 전체 |
| F/G세트 runner 도입 | curl 나열 대신 Python runner로 실험 재현성 개선 | F, G |

---

## 4. F세트 요약

F세트는 POST body가 보이지 않는 Apache 로그 환경에서 auth endpoint 반복 패턴을 보수적으로 해석할 수 있는지 확인한다.

### F세트 R1

| 항목 | 개선 전 | 개선 후 |
|---|---:|---:|
| candidate rows | 43 | 3 |
| distinct incidents | 43 | 3 |
| supporting events | 0 | 40 |
| auth behavior summaries | 1 | 1 |
| auth baseline context | 5 | 5 |

결론:

- 반복 401 login request를 개별 incident 43건으로 나열하지 않고 대표 3건만 candidate로 유지했다.
- 나머지 40건은 `auth_behavior_support` context로 보존했다.
- 200 login 5건은 `auth_baseline_context`로 유지되며 candidate로 과승격되지 않았다.
- Stage2는 반복 401, rapid burst, 401/200 혼재를 설명하면서도 로그인 성공·계정 탈취·침해 성공을 단정하지 않았다.

### F세트 R2A

R2A는 `lab/f_set/run_f_r2a_auth_scenarios.py` Python runner 기반으로 실행했다.

| 항목 | 값 |
|---|---:|
| 전체 export rows | 14 |
| candidate rows | 3 |
| supporting events | 6 |
| filtered out rows | 5 |
| ip behavior aggregates | 1 |
| auth behavior summaries | 1 |

결론:

- 저속 반복 auth 실패는 보존하되 rapid burst로 오판하지 않았다.
- 정상 browse/search는 auth abuse candidate로 과승격되지 않았다.
- Chrome/CI 단독 200 login은 `auth_baseline_context`로 분리되었다.
- Stage2는 known asset/IP 내부 테스트 가능성과 POST body 미확인 한계를 유지했다.

### F세트 R2B

R2B는 `lab/f_set/run_f_r2b_response_delta.py` Python runner 기반으로 실행했다.

| 항목 | 값 |
|---|---:|
| 전체 export rows | 11 |
| candidate rows | 3 |
| supporting events | 8 |
| filtered out rows | 0 |
| ip behavior aggregates | 1 |
| auth behavior summaries | 1 |

결론:

- existing/nonexistent/lockout-probe 의도 그룹 모두 Apache 표면에서는 `401 / 26B`로 유사하게 관찰되었다.
- 계정 존재 여부, user enumeration 성공, lockout 발동은 단정할 수 없다.
- 반복 401은 대표 candidate 3건과 supporting context 8건으로 정리되었다.
- Stage2는 low severity와 response surface comparison 중심으로 보수적으로 설명했다.

상세 문서:

- `docs/98B_F세트_Auth_Login_Abuse_비교실험.md`
- `docs/98B_F세트_Auth_Login_Abuse_R2.md`
- `lab/05-02_F세트R1_산출물/2026-05-02_F세트R1_비교.md`
- `lab/05-02_F세트R2A_산출물/2026-05-02_F세트R2A_비교.md`
- `lab/05-02_F세트R2B_산출물/2026-05-02_F세트R2B_비교.md`

---

## 5. G세트 요약

G세트는 HTTP method / protocol surface behavior를 Apache 로그 표면에서 보수적으로 해석할 수 있는지 확인한다.

### G세트 R1

G R1은 `lab/g_set/run_g_r1_method_probe.py` Python runner 기반으로 실행했다.

| 항목 | 값 |
|---|---:|
| 전체 export rows | 6 |
| candidate rows | 0 |
| filtered out rows | 6 |
| method behavior summaries | 1 |
| Stage1 processed candidates | 0 |

관찰된 method:

```text
OPTIONS / -> 204
TRACE / -> 405
PUT /upload/g_probe.txt -> 200
DELETE /api/resource/g_probe -> 500
HEAD / -> 200
GET / -> 200
```

결론:

- 최초 prepare에서는 6건 모두 `low_signal_fuzzing + dir_probe:burst`로만 정리되어 method 문맥이 약했다.
- 개선 후 `method_behavior_summaries=1`로 `OPTIONS/TRACE/PUT/DELETE/HEAD/GET`가 context-only 보존되었다.
- `HEAD/GET` baseline은 candidate로 과승격되지 않았다.
- `PUT/DELETE/TRACE/OPTIONS`의 성공 여부는 단정하지 않았다.
- Stage2는 method behavior context를 보수적으로 설명했다.

### G세트 R2

G R2는 `lab/g_set/run_g_r2_protocol_anomaly.py` raw socket runner 기반으로 실행했다.

| 항목 | 값 |
|---|---:|
| all export rows | 12 |
| access rows | 6 |
| security rows | 6 |
| error rows | 0 |
| candidate rows | 0 |
| filtered out rows | 6 |
| ip behavior aggregates | 1 |
| method behavior summaries | 1 |
| protocol anomaly summaries | 1 |

관찰된 protocol/malformed context:

```text
FAKEMETHOD
HTTP/1.0 request
bad protocol version
missing Host
odd Host
long path
```

결론:

- 최초 prepare에서는 일부 row가 `baseline:normal_get` 중심으로만 정리되어 protocol anomaly 문맥이 약했다.
- 개선 후 `protocol_anomaly_summaries=1`로 unsupported method, HTTP/1.0, bad protocol, missing/odd Host, long path가 context-only 보존되었다.
- `access=6`, `security=6`, `error=0`으로 이번 malformed/protocol 요청은 access/security 표면에 남았다.
- protocol bypass, malformed request 우회, 서버 침해 성공은 단정하지 않았다.
- Stage2는 protocol anomaly context를 보수적으로 설명했다.

상세 문서:

- `docs/98B_G세트_HTTP_Method_Protocol_Anomaly_비교실험.md`
- `lab/05-03_G세트R1_산출물/2026-05-03_G세트R1_비교.md`
- `lab/05-03_G세트R2_산출물/2026-05-03_G세트R2_비교.md`

---

## 6. 회귀 검증 상태

현재 회귀 검증 기준:

```text
prepare regression: 14 fixtures, warn=0 fail=0
stage dry-run regression: 8 fixtures, warn=0 fail=0
py_compile 주요 스크립트 통과
```

회귀 검증은 다음 범위를 고정한다.

- double encoded SQLi 보존
- educational SQL/XSS FP 완화
- HTML entity XSS 복원
- directory probing sequence
- PHP wrapper file disclosure
- direct config path 과승격 방지
- search attack + normal baseline 분리
- ip_behavior_aggregates context-only
- L3 high-signal hints
- F세트 auth_behavior_summaries 및 repeated auth candidate noise 축소
- G세트 method_behavior_summaries 및 method success 단정 금지
- G세트 protocol_anomaly_summaries 및 protocol bypass/침해 단정 금지

---

## 7. 주요 한계 항목

| 항목 | 한계 |
|---|---|
| Time-based SQLi | 충분한 duration/ttfb 차이 미관찰 |
| POST body payload | raw POST body가 보이지 않음 |
| Auth/Login abuse | email/password, 인증 성공, 계정 탈취는 Apache 로그만으로 확정 불가 |
| Method probing | PUT/DELETE/TRACE/OPTIONS의 실제 성공 여부는 Apache 로그만으로 확정 불가 |
| Protocol anomaly | malformed request 우회, Host bypass, protocol bypass 성공은 Apache 로그만으로 확정 불가 |
| response body 검증 | 파일 내용, XSS 반영, DB 결과 확인 불가 |
| fallback HTML | 200 text/html 대용량 응답을 성공으로 보면 안 됨 |
| PHP empty output | `/config.php` 200/0B를 안전 또는 성공으로 단정하면 안 됨 |
| provider 표현 차이 | provider별 강도 차이가 있어 보수적 기준으로 해석해야 함 |
| 자동 대응 | 현재는 보고/검토 중심이며 자동 차단은 후순위 |

---

## 8. 다음 우선순위

1. G세트 R3 baseline / FP bait runner 설계
   - normal HEAD health check
   - browser-like OPTIONS preflight
   - normal GET browse
   - internal monitoring UA
2. G R3 실행 전 정상 method/baseline 요청이 candidate로 과승격되지 않는지 기대 기준 정리
3. 필요 시 baseline/reference context 보강
4. 실제 LLM 샘플 검증 체계는 dry-run regression 유지 이후 후순위로 검토

---

## 9. 발표용 한 줄 정리

A~G세트 결과, Apache 로그 기반 LLM 분석 파이프라인은 SQLi, XSS, Traversal, HPP, PHP wrapper, L3 고신호 패턴, Auth/Login abuse context, HTTP method/protocol behavior context를 보수적으로 정리할 수 있음을 확인했다. 핵심은 실제 성공·유출·로그인 성공·침해·method/protocol 실행 결과를 단정하지 않고, 로그 표면에서 관찰 가능한 시도와 문맥만 제한적으로 보고하는 것이다.
