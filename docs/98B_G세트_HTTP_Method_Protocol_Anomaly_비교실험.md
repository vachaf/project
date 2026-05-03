# 98B_G세트_HTTP_Method_Protocol_Anomaly_비교실험

- 작성 기준일: 2026-05-03
- 문서 역할: G세트 HTTP method / protocol anomaly 비교실험 설계
- 적용 범위: HTTP method probing / unsupported method / risky method exposure / protocol anomaly / malformed request-like behavior
- 기준 데이터: Apache `security/access/error` 로그 표면 지표
- 핵심 전제: response body 원문, request body 원문, 서버 내부 설정은 확인하지 않는다
- 권장 runner label prefix: `lab-g-set`  
  단, 이 값은 실험 실행 추적용 label일 뿐이며 탐지/판정 근거로 사용하지 않는다.

> 이 문서는 승인된 로컬 실험 환경에서만 사용한다. Apache 로그만으로 method 허용, 업로드/삭제 성공, TRACE echo, CORS 취약점, 서버 설정 취약 여부를 확정하지 않는다.

---

## 0. G세트 위치와 설계 철학

G세트는 F세트 이후의 HTTP surface behavior 실험이다. 단일 payload exploit보다 `method`, `protocol`, `status_code`, 시계열 반복 패턴처럼 Apache 로그에 직접 남는 요청 표면을 본다.

핵심 목표는 다음 수준으로 제한한다.

- method probing 가능성
- unsupported method 또는 risky method exposure 관찰 가능성
- protocol anomaly 또는 malformed request-like behavior 관찰 가능성
- same `src_ip` / time window 기준 반복 probing sequence 보존 가능성

해석 원칙:

```text
status_code=200만으로 method 허용이나 취약점 성공을 단정하지 않는다.
PUT/DELETE/TRACE가 보이더라도 실제 업로드/삭제/XST 성공을 단정하지 않는다.
Apache 로그 표면에서 관찰 가능한 method/protocol behavior만 보수적으로 설명한다.
```

실험환경 특화 금지:

- `lab-*` User-Agent 기반 탐지 금지
- 특정 IP 기반 탐지 금지
- 특정 response size hard-code 금지
- Juice Shop/OpenCart 이름 기반 hard-code 금지
- 특정 route 문자열 기반 예외 금지

---

## 1. 비목표

G세트는 아래를 목표로 하지 않는다.

- TRACE 성공 또는 XST 성공 단정
- PUT 업로드 성공 단정
- DELETE 삭제 성공 단정
- CORS 취약점 단정
- 서버 설정 취약 확정
- malformed request 침해 성공 단정
- 자동 차단 또는 대응

---

## 2. Apache 로그에서 볼 수 있는 것

- `method`
- `uri` / `path`
- `protocol`
- `status_code`
- `response_body_bytes`
- `duration_us` / `ttfb_us`
- `user_agent`
- `referer`
- same `src_ip` / time window
- repeated method probing sequence

이 신호들로는 "어떤 요청 표면이 반복되었는가"를 볼 수 있다. 반면 응답 본문이나 서버 내부 상태를 모르면 허용 여부와 실제 영향은 보수적으로만 다뤄야 한다.

---

## 3. Apache 로그만으로 볼 수 없는 것

- 실제 파일 생성 여부
- 실제 리소스 삭제 여부
- TRACE 응답 body에 header echo가 있었는지
- CORS header 상세
- 브라우저 실행 여부
- 서버 설정 원문
- request body 원문

따라서 `200`, `201`, `204` 같은 상태만으로 write/delete/trace 성공을 결론내리면 안 된다.

---

## 4. Round 구성

| Round | 목적 | 해석 초점 |
|---|---|---|
| G R1 | 기본 method probing | risky/unsupported method candidate와 정상 baseline 분리 |
| G R2 | protocol / malformed request 관찰 | invalid method/protocol row가 어떤 로그 표면으로 남는지 확인 |
| G R3 | baseline / FP bait | 정상 HEAD/OPTIONS/GET가 과승격되지 않는지 확인 |

### G R1 — 기본 method probing

목표:

- `OPTIONS` / `TRACE` / `PUT` / `DELETE` / `HEAD`가 Apache 로그에 어떻게 남는지 확인
- unsupported/risky method가 candidate 또는 context로 보존되는지 확인
- 정상 `HEAD`와 위험 method를 구분할 수 있는지 확인
- 2026-05-03 prepare-only 확인에서 mixed method row가 전부 `low_signal_fuzzing` + `dir_probe:burst`로만 남는 문제가 확인되어, 후속 prepare 개선에서는 `method_behavior_summaries`로 method context를 별도 보존한다.
- 2026-05-03 G R2 prepare-only 확인에서는 invalid method / bad protocol / missing Host / odd Host / long path row가 `baseline:normal_get` 위주로 정리되는 한계가 확인되었고, 후속 prepare 개선에서는 `protocol_anomaly_summaries`로 protocol/malformed context를 별도 보존한다.

실행 방식:

- G R1은 긴 `curl` 나열보다 Python runner 사용을 권장한다.
- runner 위치: `lab/g_set/run_g_r1_method_probe.py`
- runner는 request body 원문과 response body 원문을 저장하지 않는다.
- runner는 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점 성공을 검증하지 않는다.

권장 예시:

```bash
python3 lab/g_set/run_g_r1_method_probe.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R1_산출물/runner_logs
```

dry-run / print-plan 예시:

```bash
python3 lab/g_set/run_g_r1_method_probe.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R1_산출물/runner_logs \
  --dry-run

python3 lab/g_set/run_g_r1_method_probe.py \
  --base-url http://192.168.56.105 \
  --scenario trace \
  --out lab/05-xx_G세트R1_산출물/runner_logs_trace \
  --print-plan
```

케이스:

| ID | runner label | 요청 | 기대 관찰 | 기대 해석 | 기대 응답 | 해석 제한 |
|---|---|---|---|---|---|---|
| G-R1-01 | `options_root` | `OPTIONS /` | `method=OPTIONS`, `status_code`, `response_body_bytes` 관찰 | method discovery/probing 가능성 | any | `no_cors_or_method_exposure_success_inference` |
| G-R1-02 | `trace_root` | `TRACE /` | `method=TRACE`, `status_code` 관찰 | TRACE method exposure probing 가능성 | any | `no_xst_success_inference_without_response_body` |
| G-R1-03 | `put_probe` | `PUT /upload/g_probe.txt` | `method=PUT`, `status_code` 관찰 | upload/write method probing 가능성 | any | `no_file_write_success_inference` |
| G-R1-04 | `delete_probe` | `DELETE /api/resource/g_probe` | `method=DELETE`, `status_code` 관찰 | destructive method probing 가능성 | any | `no_resource_delete_success_inference` |
| G-R1-05 | `head_root` | `HEAD /` | `method=HEAD`, `status_code` 관찰 | 정상 baseline 가능성 | any | `baseline_head_no_attack_inference` |
| G-R1-06 | `get_root` | `GET /` | `method=GET`, `status_code` 관찰 | 정상 baseline | any | `baseline_get_no_attack_inference` |

추가 제한:

- `TRACE` 응답 body는 runner가 저장하거나 출력하지 않는다.
- `PUT`은 짧은 dummy body만 전송할 수 있으나 body 원문은 저장하지 않고 길이만 기록한다.
- `DELETE`는 테스트 전용 path만 사용한다.
- `200` / `201` / `204` 같은 상태만으로 성공을 단정하지 않는다.

### G R2 — protocol / malformed request 관찰

목표:

- 이상 method token, protocol version, malformed request-like row가 어떻게 남는지 확인
- Apache `security/access/error` 중 어떤 로그 표면에 보존되는지 확인
- `400` / `408` / `501` 류 상태를 protocol anomaly context로만 해석하는지 확인
- malformed request가 `security/access/error` 중 어디에 남는지 확인하는 것이 R2 핵심이다.

실행 방식:

- G R2는 Python raw socket runner 사용을 권장한다.
- runner 위치: `lab/g_set/run_g_r2_protocol_anomaly.py`
- runner는 `http://` base URL만 지원하며 `https://`는 명확히 거부한다.
- runner는 raw request 원문, request body 원문, response body 원문을 저장하지 않는다.
- runner는 침해 성공, 우회 성공, malformed request 성공을 검증하지 않는다.

권장 예시:

```bash
python3 lab/g_set/run_g_r2_protocol_anomaly.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R2_산출물/runner_logs
```

dry-run / print-plan 예시:

```bash
python3 lab/g_set/run_g_r2_protocol_anomaly.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R2_산출물/runner_logs \
  --dry-run

python3 lab/g_set/run_g_r2_protocol_anomaly.py \
  --base-url http://192.168.56.105 \
  --scenario bad_protocol \
  --out lab/05-xx_G세트R2_산출물/runner_logs_bad_protocol \
  --print-plan
```

케이스:

| ID | runner label | 요청 | 기대 관찰 | 기대 해석 | 기대 응답 | 해석 제한 |
|---|---|---|---|---|---|---|
| G-R2-01 | `invalid_method_token` | `FAKEMETHOD / HTTP/1.1` + `Host: <host>` | `security/access/error` 중 어디에 남는지, `method=FAKEMETHOD` 또는 parse failure 흔적 확인 | unsupported/invalid method probing possibility; no exploit success inference | `400/405/501` 등 가능 | `protocol_anomaly_context_only_no_success_inference` |
| G-R2-02 | `http10_odd_request` | `GET / HTTP/1.0` + no `Host` | `protocol=HTTP/1.0`으로 남는지, Host 없는 요청이 어떻게 기록되는지 확인 | legacy protocol or probing-like context; no vulnerability inference | `200/400/403` 등 가능 | `protocol_surface_observation_only` |
| G-R2-03 | `bad_protocol_version` | `GET / HTTP/9.9` + `Host: <host>` | bad protocol version이 `security/access/error` 중 어디에 남는지 확인 | protocol anomaly context; no bypass or exploit success inference | `400/505/501` 등 가능 | `protocol_anomaly_context_only_no_success_inference` |
| G-R2-04 | `missing_host_http11` | `GET / HTTP/1.1` + no `Host` | missing `Host`가 어떤 status/log surface로 남는지 확인 | malformed HTTP/1.1 request-like context; no exploit success inference | `400` 등 가능 | `malformed_request_context_only` |
| G-R2-05 | `odd_host_header` | `GET / HTTP/1.1` + `Host: invalid..host` | odd `Host` header가 어떻게 기록되는지 확인 | odd host/protocol surface observation; no virtual-host bypass inference | `400/403/200` 등 가능 | `host_header_anomaly_context_only` |
| G-R2-06 | `long_path_probe` | `GET /g-probe/<long-token> HTTP/1.1` + `Host: <host>` | long path가 정상 row로 남는지, 거절 status가 나는지 확인 | malformed/long path probing-like context; no exploit success inference | `200/400/414/404` 등 가능 | `long_path_context_only_no_success_inference` |

주의:

- malformed request 성공 또는 침해 단정 금지
- 특정 상태코드만으로 exploit/우회 성공 단정 금지
- `status_code=400/408/501/505` 류는 protocol anomaly context로만 해석한다.
- long path는 대략 2048~4096자 범위로 제한하며, 서버에 과도한 부담을 주지 않는다.

### G R3 — baseline / FP bait

목표:

- 정상 monitoring/health-check-like method가 공격으로 과승격되지 않는지 확인
- User-Agent, 단일 method, 단일 status만으로 공격 단정하지 않는지 확인

케이스:

| ID | 유형 | 기대 관찰 | 기대 해석 |
|---|---|---|---|
| G-R3-01 | normal `HEAD` health check | 반복 가능하나 단순 `HEAD` 중심 | baseline/reference context 우선 |
| G-R3-02 | browser-like `OPTIONS` preflight | `OPTIONS`와 일반 브라우저성 부가 신호 혼재 가능 | 정상 동작 가능성 병기 |
| G-R3-03 | normal `GET` browse | 일반 `GET` / `200` / 정적 자산 접근 | baseline 유지 |
| G-R3-04 | known internal monitoring UA | 규칙적 접근 또는 점검성 패턴 | UA 단독 확정 없이 내부 점검 가능성 병기 |

주의:

- User-Agent만으로 정상/공격 단정 금지
- baseline/reference context로만 보존하는 방향을 우선 검토

---

## 5. prepare 관찰 포인트

- `method_probe` 또는 `protocol_anomaly` candidate가 필요한지 판단
- repeated method probing sequence가 `ip_behavior_aggregates`로 충분한지 확인
- `HEAD` / `GET` baseline이 candidate로 과승격되지 않는지 확인
- `PUT` / `DELETE` / `TRACE`가 성공 단정 없이 보존되는지 확인
- malformed request가 `security` 로그에 남는지, `access` / `error` 로그 보조가 필요한지 확인
- method/protocol hint가 필요한지 검토

향후 hint 후보:

- `method_probe:options`
- `method_probe:trace`
- `method_probe:put`
- `method_probe:delete`
- `method_probe:unsupported_method`
- `method_probe:destructive_method`
- `protocol_anomaly:invalid_method`
- `protocol_anomaly:bad_protocol_version`
- `protocol_anomaly:malformed_request`
- `baseline:normal_head`
- `baseline:normal_get`

이번 문서에서는 hint 구현을 다루지 않는다.

---

## 6. Stage1 / Stage2 체크포인트

- method probing 가능성으로 설명하는가
- `TRACE` / `PUT` / `DELETE` 성공을 단정하지 않는가
- `HEAD` / `GET` baseline을 과승격하지 않는가
- `200` / `201` / `204` 같은 상태만으로 성공 단정하지 않는가
- same `src_ip` / time window context를 보수적으로 사용하는가
- known asset 또는 내부 점검 가능성이 있으면 그 가능성을 병기하는가
- `400` / `408` / `501`을 protocol anomaly context로 제한하는가

---

## 7. provider 비교 포인트

G세트는 provider별 표현 차이가 생길 수 있으므로, Stage1/Stage2 비교 시 아래 항목을 본다.

| 비교 항목 | 확인 내용 |
|---|---|
| method probing 인식 | `PUT` / `DELETE` / `TRACE`를 risky method probe로 설명하는가 |
| 정상 method 구분 | `HEAD` / `GET` / preflight-like `OPTIONS`를 과승격하지 않는가 |
| status code 보수성 | `200` / `201`만으로 method 허용 또는 성공을 단정하지 않는가 |
| protocol anomaly | malformed/invalid method를 anomaly context로만 보존하는가 |
| probing sequence | same `src_ip` 내 method 다양성을 context-only로 설명하는가 |
| known asset 고려 | 내부 모니터링/자동화 가능성을 병기하는가 |

---

## 8. Python runner 구성

G세트는 긴 `curl` 나열보다 Python runner 기반으로 관리한다. 현재 기준 구성은 다음과 같다.

파일:

- `lab/g_set/README.md`
- `lab/g_set/run_g_r1_method_probe.py`
- `lab/g_set/run_g_r2_protocol_anomaly.py`
- `lab/g_set/run_g_r3_baseline.py`

역할:

- `README.md`: round 범위, 실행 순서, export 연계 위치 정리
- `run_g_r1_method_probe.py`: `OPTIONS/TRACE/PUT/DELETE/HEAD/GET` 시나리오 실행
- `run_g_r2_protocol_anomaly.py`: invalid method/protocol/malformed request 후보 실행
- `run_g_r3_baseline.py`: 정상 `HEAD/OPTIONS/GET` 및 monitoring-like baseline 실행

현재 범위:

- `run_g_r1_method_probe.py`: 완료
- `run_g_r2_protocol_anomaly.py`: 이번 작업에서 runner 추가 및 dry-run 검증
- `run_g_r3_baseline.py`: 향후 작업

---

## 9. 실행 전 주의

- 승인된 로컬 실험 환경에서만 실행
- public target 금지
- 실제 리소스 생성/삭제 위험이 있으므로 `PUT` / `DELETE`는 테스트용 path만 사용
- 가능하면 target app이 안전한 실험 VM인지 확인
- `DELETE`는 실제 중요한 리소스를 대상으로 하지 않음
- `PUT`은 쓰기 성공 여부를 검증하지 않음
- `TRACE` / `OPTIONS` 응답 body를 수집하거나 분석하지 않음

---

## 10. 산출물 관리

공개 또는 공유에 적합한 산출물:

- G세트 비교 Markdown
- 최종 Stage2 Markdown
- 통합 요약 문서

공개 또는 공유에 부적합한 산출물:

- raw export JSON
- LLM input JSON
- stage2_report_input JSON
- analysis_candidates JSON
- runner request body가 포함된 실행 로그

주의:

- runner 로그에는 실험용 request body가 들어갈 수 있으므로 공유 범위를 제한한다.
- 비교 문서에는 raw body나 credential-like 값을 직접 싣지 않는다.

---

## 11. 다음 작업

1. 승인된 로컬 실험 환경에서 G R2 실제 실행
2. G R2 prepare-only 확인
3. G R2 Stage1 / Stage2 비교
4. 필요 시 `method_probe` / `protocol_anomaly` hint 검토
5. G R3 baseline runner 설계 및 비교 실험 준비

---

## 12. 발표용 한 줄 정리

G세트는 Apache 로그 표면에서 `method`, `protocol`, 반복 시퀀스를 근거로 HTTP method probing과 protocol anomaly 가능성을 보수적으로 해석할 수 있는지 확인하는 설계 문서다.
