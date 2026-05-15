# Observability Run Summary

- run_id: obs_php_sample_v2_001
- target_app: php_sample
- topology: apache_php
- app_stack: Apache+PHP
- log_format_version: apache_security_io_v2
- scenario_catalog_version: apache_observability_s01_s15_v1

## 1. High-Level Result

`apache_security_io_v2`를 적용한 Apache+PHP 샘플 서버에서 S01~S15 관측 run을 수행했다.

결과적으로 v2 LogFormat 출력, raw log 수집, export JSON 변환, prepare/stage dry-run 연결까지 1차 확인이 완료되었다.

확인된 핵심 결과는 다음과 같다.

```text
source rows: 21
log_schema: apache_security_io_v2
log_schemas: [apache_security_io_v2]
skipped_lines: 0
malformed_lines: 0
prepare candidate_rows: 13
filtered_out_rows: 8
supporting_events: 3
viewer finding_count: 12
viewer context_count: 5
viewer supporting_event_count: 3
```

v2 추가 필드는 raw security log와 export JSON 양쪽에서 보존된다.

```text
request_target
req_host
client_ip_source
has_cookie
has_authorization
```

`has_cookie`와 `has_authorization`은 Cookie/Authorization 원문을 저장하지 않고 presence flag로만 보존된다. 이번 S01~S15 run에서는 scenario traffic에 Cookie/Auth header가 없었으므로 export JSON에서 둘 다 `false`로 normalize되었다.

별도 presence check에서는 `has_cookie="1"`, `has_authorization="1"` 출력이 확인되었다. 이는 헤더 존재 여부이며 인증 성공을 의미하지 않는다.

## 2. Evidence Level Summary

이번 run은 기존 PHP sample baseline과 동일한 S01~S15 카탈로그를 사용한다. evidence level 해석은 v1 PHP sample과 동일하게 유지한다.

| evidence level | count | notes |
|---|---:|---|
| O0 | 0 | 관찰 불가 scenario 없음 |
| O1 | 12 | 대부분 Apache request/response metadata로 관찰 가능 |
| O1/O4 | 2 | S08 login_post, S09 upload_like_post. POST 관찰은 가능하지만 결과 확인은 app/DB audit 필요 |
| O2 | 1 | S11 server_error. Apache/PHP warn/error context와 연결 가능 |
| O3 | 0 | WAF context 없음 |
| O4 | 0 | DB/app audit 기반 결과 확인 없음 |

주의:

- S06 forbidden path와 S15 traversal-like는 error log와 연결되지만, 파일 내용 노출이나 침해 성공을 의미하지 않는다.
- S08/S09는 request metadata와 app notice context가 있어도 로그인 성공/업로드 저장 성공으로 판단하지 않는다.
- S13/S14는 SQLi/XSS-like payload 관찰이며 DB 영향이나 브라우저 실행 증거가 아니다.

## 3. v2 Field Observation Result

v2 목적은 더 강한 보안 판정을 만들기 위한 것이 아니라 parser/viewer/LLM 입력 안정성을 높이기 위한 것이다.

이번 run에서 확인된 v2 필드 상태는 다음과 같다.

| field | observed | notes |
|---|---:|---|
| `log_schema` | yes | `apache_security_io_v2` |
| `request_target` | yes | `%U%q` 기반 normalized convenience target |
| `raw_request_target` | yes | converter가 `raw_request`에서 파생한 compatibility target |
| `req_host` | yes | client-supplied Host header. `apache-v2-test.local` |
| `host` | yes | downstream compatibility를 위해 `req_host`에서 fallback copy |
| `client_ip_source` | yes | `direct` |
| `has_cookie` | yes | boolean-like normalized flag. scenario traffic은 `false` |
| `has_authorization` | yes | boolean-like normalized flag. scenario traffic은 `false` |
| `remoteip_proxy_chain` | n/a | 기본 v2에서는 null. remoteip schema에서 별도 검토 |

### request_target vs raw_request_target

S01에서 다음 차이가 확인된다.

```text
raw_request:        GET /?obs_run=obs_php_sample_v2_001&scenario=S01 HTTP/1.1
request_target:     /index.php?obs_run=obs_php_sample_v2_001&scenario=S01
raw_request_target: /?obs_run=obs_php_sample_v2_001&scenario=S01
```

이 차이는 의도한 설계와 맞다.

- `request_target`은 Apache `%U%q` 기반 normalized convenience target이다.
- `raw_request_target`은 raw request line에서 추출한 request-target이다.
- raw fidelity가 필요한 분석에서는 `raw_request` 또는 `raw_request_target`을 우선한다.
- 일반 표시/요약에는 `request_target`을 사용할 수 있다.

## 4. Pipeline Dry-Run Result

`obs_php_sample_001_v2_pipeline_dryrun`으로 export JSON 기반 dry-run pipeline을 수행했다.

결과:

```text
prepare return_code: 0
stage1 return_code: 0
stage2 return_code: 0
viewer_payload 생성: yes
```

prepare 주요 수치:

```text
total_exported_rows: 21
selected_source_rows: 21
candidate_rows: 13
filtered_out_rows: 8
supporting_events: 3
probing_sequence_summaries: 1
static_baseline_summaries: 1
sensitive_path_probe_summaries: 1
mixed_baseline_scanner_summaries: 1
ip_behavior_aggregates: 1
```

viewer payload 주요 수치:

```text
finding_count: 12
context_count: 5
supporting_event_count: 3
```

`finding_count=12`는 dry-run stage2 reporter의 top incidents 제한에 따른 결과로 보인다. prepare candidate는 13건이고, stage2 input/viewer에는 상위 12건이 표시된다.

## 5. Candidate Count Note

이번 v2 dry-run에서 `candidate_rows=13`으로 나타났다.

추가 확인 결과, 같은 최신 prepare/scoring 기준으로 다시 실행한 v1 PHP sample dry-run도 `candidate_rows=13`, `distinct_incident_candidates=13`으로 확인됐다. 따라서 이 13건은 v2 필드 추가 때문이 아니다.

정정된 해석:

```text
candidate_rows=13은 v2 field 추가 때문이 아니라,
현재 prepare scoring/filtering 기준에서 PHP sample S01~S15가 그렇게 분류된 결과다.
```

대표 후보:

```text
S15 traversal_like: /download.php, 404, path_traversal
S14 xss_like: /search.php, 200, xss
S13 sqli_like: /search.php, 200, sqli
S12 scanner_burst: /admin, /wp-login.php, /.env, /server-status, /does-not-exist
S11 server_error: /error.php, 500
S09 upload_like_post: /upload.php, 400
S08 login_post: /login.php, 401
```

해석:

- v2 필드는 score/severity/verdict를 올리는 용도가 아니다.
- candidate count 증가는 v2 migration 이슈가 아니라 PHP sample S01~S15에 대한 현재 prepare policy 이슈다.
- 필요한 경우 별도 `PHP sample candidate policy review`로 다룬다.
- v2 검증의 핵심은 `request_target`, `req_host`, `client_ip_source`, Cookie/Auth presence flag가 손실 없이 전달되는지다.

## 6. Guardrail Checks

| guardrail | result | notes |
|---|---|---|
| No success inference from status_code=200 | pass | S13/S14 200은 payload 관찰이지 SQLi/XSS 성공 증거가 아님 |
| No exposure inference from response size only | pass | S15는 404/text/html이며 파일 내용 노출 증거 없음 |
| No login success inference from POST only | pass | S08 POST는 401. 로그인 성공 판단 금지 |
| No upload success inference from POST only | pass | S09 POST는 400. 업로드 저장 성공 판단 금지 |
| No compromise inference from WAF match only | n/a | WAF context 없음 |
| No attacker IP assertion from x_forwarded_for only | pass | `x_forwarded_for`는 observed header일 뿐 신뢰 IP 근거 아님 |
| No authentication inference from has_cookie/has_authorization | pass | presence flag는 헤더 존재 여부만 의미 |

## 7. Completed Follow-up

- `convert_observability_logs_to_export_json.py` v2 field 보존 결과를 회귀 테스트로 고정했다.
- v2 fixture를 추가했다.
  - `tests/fixtures/apache_security_io_v2_sample.log`
  - 408 timeout row, S01 normalized request_target difference, Cookie/Auth presence flag 포함
- converter 테스트를 추가했다.
  - `tests/test_convert_observability_logs_to_export_json.py`
  - `request_target`, `raw_request_target`, `req_host`, `host`, `client_ip_source`, `has_cookie`, `has_authorization`, `log_schema`, `log_schemas` 검증
- 검증:
  - `python3 -m pytest -q tests/test_convert_observability_logs_to_export_json.py`
  - `5 passed`

## 8. Recommended Next Changes

- v2 field를 prepare analysis_candidates 또는 viewer_payload에 어디까지 pass-through할지 별도 검토한다.
  - 현재 pipeline은 핵심 분석 필드와 raw_log에는 보존되지만, 모든 v2 display-only field가 viewer findings에 직접 노출되는 단계는 아니다.
- candidate_rows=13은 v2 문제가 아니라 current prepare policy 결과로 분리한다.
  - 필요 시 `PHP sample S01~S15 candidate policy review` 문서로 다룬다.
- remoteip schema는 아직 진행하지 않는다.
  - `apache_security_io_remoteip_v2`는 별도 trusted proxy 테스트 서버에서만 검증한다.
- actual LLM execution은 보류한다.
  - v2 fixture/test와 candidate policy review를 끝낸 뒤 필요 시 actual spot check를 수행한다.

## 9. Current Decision

```text
apache_security_io_v2 LogFormat output: pass
observability raw collection: pass
export JSON v2 field preservation: pass
converter v2 fixture/test: pass
pipeline dry-run connectivity: pass
actual LLM execution: not yet performed
v2 production migration: not started
candidate_rows=13: current prepare policy result, not v2 field effect
```

v1 기준 서버와 기존 observability run은 그대로 유지한다. v2는 새 서버 기반 검증 대상으로만 유지하며, 추가 적용 여부는 candidate policy review와 v2 display-only field pass-through 검토 후 판단한다.
