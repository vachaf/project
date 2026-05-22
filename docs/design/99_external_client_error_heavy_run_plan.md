# 99_external_client_error_heavy_run_plan

- 문서 상태: external client error-heavy run plan/result
- 기준 시점: 2026-05-22
- 목적: local/internal client와 external client에서 error-heavy distribution 및 Apache client identity 관찰값이 어떻게 달라지는지 비교하기 위한 실행 계획과 결과를 정리한다.

관련 문서:

- [99_observability_run_summary_index.md](./99_observability_run_summary_index.md)
- [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md)
- [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)
- [99_proxy_error_check_scenario_extension_review.md](./99_proxy_error_check_scenario_extension_review.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 목적

- external client 기반 error-heavy run을 실제로 수행할지 판단하기 위한 설계 문서를 남긴다.
- local/internal client baseline과 external client run의 candidate distribution 차이를 비교한다.
- `src_ip`, `peer_ip`, client header 계열 관찰값이 Apache logs-only 범위에서 어떤 차이를 보이는지 확인한다.
- 실제 run 결과는 문서에 관찰 결과로만 반영하고, prepare/scoring/filtering 변경 근거로 사용하지 않는다.

## 2. 배경

현재 기준 상태:

- v2 3-way observability baseline은 완료 상태다.
- PHP sample direct app: `obs_php_sample_v2_001`
- OpenCart front-controller PHP app: `obs_opencart_v2_001`
- Juice Shop reverse proxy backend app: `obs_juiceshop_proxy_v2_001`

추가로 정리된 관련 판단:

- `proxy_error_check` review는 완료 상태다.
- 관련 문서: [99_proxy_error_check_scenario_extension_review.md](./99_proxy_error_check_scenario_extension_review.md)
- 결론은 정규 S01~S15 편입 보류, availability extension 후보 유지, prepare/scoring/filtering 변경 없음이다.

이번 plan/result의 초점:

- external client로 error-heavy 요청을 보냈을 때도 payload candidate 보존 원칙이 유지되는지 확인한다.
- payload 없는 status/error-only 요청은 계속 diagnostic bucket으로 남는지 확인한다.
- client identity 관찰값이 달라져도 prepare 정책을 바꾸지 않고 설명 가능한 범위인지 확인한다.

## 3. 현재 Baseline

현재 비교 기준 dry-run:

- `obs_php_sample_v2_error_heavy_001_current_dryrun`

현재 알려진 분포:

- `candidate_count=12`
- `keep_candidate_payload=3`
- `context_candidate_probe=4`
- `demotion_candidate_status_error_only=3`
- `context_candidate_auth_failure=1`
- `context_candidate_upload_failure=1`

이번 비교의 핵심 질문:

- external client run에서도 이 분포가 대체로 유지되는가
- `src_ip`, `peer_ip`, `x_forwarded_for`, `client_ip_source` 차이 때문에 `reason_hints`나 candidate policy 분포가 달라지는가
- payload-bearing request는 계속 `keep_candidate_payload`로 유지되는가
- payload 없는 error-heavy request는 계속 status/error-only 진단 버킷에 머무는가

## 4. 추천 1차 Run

1차 추천 대상:

- run id 후보: `obs_php_sample_v2_error_heavy_external_001`
- topology: direct PHP app, `apache_security_io_v2`
- 목적: local/internal error-heavy baseline과 external client 관찰 차이를 가장 단순한 topology에서 비교

우선 추천 이유:

- reverse proxy나 remoteIP 해석이 섞이지 않는다.
- direct app 기준이라 `src_ip`와 request header 관찰 차이를 분리해서 보기 쉽다.
- 기존 PHP sample error-heavy baseline과 1:1 대응 비교가 가능하다.
- payload candidate 유지와 status/error-only bucket 유지 여부를 가장 적은 변동성으로 먼저 볼 수 있다.

2차 후보:

- run id 후보: `obs_juiceshop_proxy_v2_error_heavy_external_001`
- topology: reverse proxy backend app
- 목적: reverse proxy에서 external client와 backend response, fallback, error context 차이를 후속 검토
- 단, 1차 direct app 비교 이후로 미룬다.

## 5. 추천하지 않는 범위

이번 plan에서 추천하지 않는 것:

- `mod_remoteip` 또는 remoteIP 설정 변경
- trusted proxy 기준 추가
- prepare/scoring/filtering 변경
- `scripts/explain_prepare_candidates.py` label detector 변경
- Web UI의 verdict, severity, category 변경
- external client 관찰값을 attacker identity로 해석하는 문구

## 6. 실행 전 확인 사항

- external client가 어느 네트워크와 어느 호스트에서 요청을 보내는지 확인
- Apache vhost가 external client에서 접근 가능한지 확인
- DNS 또는 `/etc/hosts`가 준비돼 있는지, 아니면 `Host` header 방식이 필요한지 확인
- 방화벽, 라우팅, 포트 접근 여부 확인
- 대상 access/error/security 로그 포맷이 `apache_security_io_v2`인지 확인
- 로그 수집 경로가 기존 v2 run과 동일하게 유지되는지 확인
- external client에서 보낼 요청 세트가 기존 error-heavy artifact와 일치하는지 확인
- EH01~EH12 재생은 `scripts/run_error_heavy_observability_scenarios.sh` 기준으로 수행한다.

## 7. 관찰 항목

이번 비교에서 우선 확인할 항목:

- `src_ip`
- `peer_ip`
- `x_forwarded_for`
- `x_real_ip`
- `forwarded`
- `client_ip_source`
- `remoteip_proxy_chain`
- `request_id`
- `error_link_id`
- `status_code`
- `handler`
- `req_host`
- `request_target`
- `raw_request_target`
- `reason_hints`
- candidate policy distribution

## 8. Runner 사용 예시

실행 전 run 변수:

```bash
RUN_ID=obs_php_sample_v2_error_heavy_external_001
RUN_DIR=lab/observability/runs/$RUN_ID
```

run notes 초기화:

```bash
scripts/init_observability_run_notes.sh \
  --run-id "$RUN_ID" \
  --target-base-url http://apache-log-test-v2.local \
  --target-app php_sample \
  --topology apache_php \
  --app-stack 'Apache+PHP' \
  --log-format-version apache_security_io_v2
```

DNS/hosts가 잡힌 경우:

```bash
scripts/run_error_heavy_observability_scenarios.sh \
  --run-id "$RUN_ID" \
  --base-url http://apache-log-test-v2.local
```

Host header 방식:

```bash
scripts/run_error_heavy_observability_scenarios.sh \
  --run-id "$RUN_ID" \
  --base-url http://<APACHE_SERVER_IP> \
  --host-header apache-log-test-v2.local
```

EH01만 단건 실행:

```bash
scripts/run_error_heavy_observability_scenarios.sh \
  --run-id "$RUN_ID" \
  --base-url http://<APACHE_SERVER_IP> \
  --host-header apache-log-test-v2.local \
  --scenario EH01
```

실행 메모:

- 현재 repo에는 `scripts/run_error_heavy_observability_scenarios.sh`가 추가되어 있다.
- 이 runner는 EH01~EH12 request generation만 담당한다.
- 기본 query pattern은 `?scenario=EHxx&run=$RUN_ID`다.
- `?obs_run=$RUN_ID&scenario=EHxx` 형태는 EH01 smoke에서 label 인식이 약했으므로 runner 기본값으로 쓰지 않는다.
- Host header가 지정되면 `Host:`만 추가하고, `X-Forwarded-For`, `X-Real-IP`, `Forwarded`, `Referer`는 기본적으로 보내지 않는다.
- EH04/EH06 POST body는 artifact를 역복구한 것이 아니라 현재 lab endpoint 기준의 synthetic best-effort body다.

## 9. 로그 수집 / Export / Dry-run / Explain 명령 초안

로그 수집:

```bash
scripts/collect_observability_server_logs.sh \
  --run-id "$RUN_ID" \
  --security-log /var/log/apache2/apache-log-test-v2_security.log \
  --access-log /var/log/apache2/apache-log-test-v2_access.log \
  --error-log /var/log/apache2/apache-log-test-v2_error.log \
  --sudo-cp \
  --force
```

export 변환:

```bash
python3 scripts/convert_observability_logs_to_export_json.py \
  --run-dir "$RUN_DIR" \
  --pretty
```

dry-run:

```bash
python3 src/run_analysis_pipeline.py \
  --export-input "$RUN_DIR/exported/security.json" \
  --work-dir . \
  --run-dir "runs/${RUN_ID}" \
  --dry-run \
  --pretty \
  --write-filtered-out
```

candidate explanation:

```bash
python3 scripts/explain_prepare_candidates.py \
  --run-dir "runs/${RUN_ID}" \
  --format markdown \
  --sort policy \
  --out "$RUN_DIR/candidate_policy_explanation.md"
```

## 10. EH01~EH12 구성 방식

구성 원칙:

- 기존 artifact `lab/observability/runs/obs_php_sample_v2_error_heavy_001/exported/security.json`
  와 `candidate_policy_explanation.md`에서 method, URI, query pattern, user-agent를 우선 복원했다.
- EH01/EH02는 artifact와 동일한 path/query shape를 유지한다.
- EH03는 기존처럼 `/does-not-exist-error-heavy-$RUN_ID` 형태의 run-specific missing path를 사용한다.
- EH10~EH12는 artifact에 남아 있는 payload query를 그대로 따른다.
- EH04/EH06은 content type과 endpoint는 artifact를 따르고, POST body는 raw 로그로 복원할 수 없으므로 synthetic best-effort body를 사용한다.
- 이 runner는 "기존 run을 완전 복제"가 아니라 "현재 lab PHP sample endpoint 기준 error-heavy request set 재현"을 목표로 한다.

## 11. EH01 Smoke Check Result

2026-05-22에 `obs_php_sample_v2_error_heavy_external_001`의 EH01 단건 smoke check를 수행했다.

요약:

- client host: `192.168.56.114`
- Apache/PHP v2 server `local_ip`: `192.168.56.115`
- request: `GET /error.php?obs_run=obs_php_sample_v2_error_heavy_external_001&scenario=EH01`
- status: `500`
- handler: `application/x-httpd-php`
- `log_schema`: `apache_security_io_v2`
- `client_ip_source`: `direct`
- `src_ip`: `192.168.56.114`
- `peer_ip`: `192.168.56.114`
- `x_forwarded_for`, `x_real_ip`, `forwarded`: not present
- candidate_count: `1`
- policy_class: `demotion_candidate_status_error_only`

해석:

- 같은 host-only/전용망의 다른 머신에서 Apache v2 PHP sample vhost로 접근하는 controlled external client path가 확인되었다.
- remoteIP 없이도 direct peer 기반 identity field가 `.114`로 보존되었다.
- EH01 단건은 payload 없는 `500`/`error_linked` 요청이므로 status/error-only diagnostic bucket에 분리되는 것이 기대 결과다.
- 이 결과는 EH01 단건 smoke check이며, EH01~EH12 전체 distribution 비교 근거로 일반화하지 않는다.
- `status_code=500`, `text/html`, response size는 취약점, 공격 성공, 침해 성공, 내부 결과 노출 근거가 아니다.
- prepare/scoring/filtering 변경은 없다.

메모:

- 이 smoke artifact의 candidate explanation에서는 scenario 표시가 `-`로 남았다.
- 이후 확인 결과, 이는 구버전/다른 checkout path에서 생성된 stale explanation artifact 문제로 보는 것이 맞다.
- 최신 `/opt/web_log_analysis` 기준의 current script로 재생성하면 EH01 label이 정상 표시된다.
- 이번 확인은 label UX artifact 정정이며, prepare/scoring/filtering 변경은 없다.

## 12. EH01~EH12 External Run Result

2026-05-22에 `obs_php_sample_v2_error_heavy_external_001`의 EH01~EH12 전체 external run을 수행했다.

Identity / header observation:

- client host: `192.168.56.114`
- Apache/PHP v2 server `local_ip`: `192.168.56.115`
- `log_schema`: `apache_security_io_v2`
- `total_count`: `12`
- `client_ip_source`: `direct`
- `src_ip`: `192.168.56.114`
- `peer_ip`: `192.168.56.114`
- `remoteip_proxy_chain`: not present
- `x_forwarded_for`, `x_real_ip`, `forwarded`: not present

Candidate policy distribution:

| policy_class | count |
|---|---:|
| `context_candidate_auth_failure` | 1 |
| `context_candidate_probe` | 4 |
| `context_candidate_upload_failure` | 1 |
| `demotion_candidate_status_error_only` | 3 |
| `keep_candidate_payload` | 3 |

Interpretation:

- external client 환경에서도 local/internal `obs_php_sample_v2_error_heavy_001_current_dryrun`과 같은 conservative distribution shape가 유지되었다.
- EH10 traversal-like, EH11 SQLi-like, EH12 XSS-like 요청은 explicit payload 구조가 있어 `keep_candidate_payload`로 유지되었다.
- EH01/EH02/EH05는 status/error-only diagnostic bucket으로 분리되었다.
- EH04 login POST 401은 auth failure context로 분리되었다.
- EH06 upload POST 400은 upload failure context로 분리되었다.
- EH03/EH07/EH08/EH09 계열 probe-like request는 probe context로 분리되었다.
- `src_ip`/`peer_ip`가 external controlled client로 남더라도 attacker attribution proof는 아니다.
- prepare/scoring/filtering 변경은 없다.
- broad demotion은 계속 보류한다.

Scenario label resolution:

- 최초 external run의 `candidate_policy_explanation.md`에서는 모든 candidate의 scenario label이 `-`로 표시되었다.
- 확인 결과, security export와 `llm_input.json`에는 `scenario=EHxx` query string과 `obs-error-heavy/EHxx` User-Agent가 보존되어 있었다.
- 원인은 구버전 또는 다른 checkout/path에서 생성된 stale explanation artifact로 정리한다.
- 최신 `/opt/web_log_analysis` 기준으로 `candidate_policy_explanation.md`를 재생성한 뒤 EH01~EH12 label이 정상 표시된다.
- 이는 candidate policy, scoring, prepare 문제가 아니다.

## 13. 비교 기준

1차 비교는 아래 순서로 본다.

1. `candidate_count`, `keep_candidate_payload`, `demotion_candidate_status_error_only`가 baseline과 크게 달라지는지 본다.
2. 동일한 payload-bearing request가 external client에서도 `keep_candidate_payload`로 유지되는지 본다.
3. payload 없는 error-heavy request가 여전히 diagnostic/status-error-only 계열로 남는지 본다.
4. `reason_hints`가 client identity 관련 관찰값 때문에 새 의미로 바뀌지 않는지 본다.
5. `src_ip`, `peer_ip`, `x_forwarded_for`, `x_real_ip`, `forwarded`, `client_ip_source`가 어떤 조합으로 남는지 비교한다.
6. `request_id`와 `error_link_id` 연결이 direct app topology에서 안정적으로 유지되는지 본다.

## 14. 해석 Guardrail

이번 plan/result에서 유지할 Apache logs-only 해석 경계:

- external client에서 요청이 왔더라도 그 자체만으로 attacker라고 확정하지 않는다.
- `X-Forwarded-For`, `X-Real-IP`, `Forwarded`는 관찰 header일 뿐이며 identity proof가 아니다.
- trusted proxy 또는 remoteIP 설정이 없는 환경에서는 `src_ip`를 `X-Forwarded-For`로 대체하지 않는다.
- remoteIP가 적용되지 않은 환경에서는 `src_ip`와 `x_forwarded_for`를 섞어 재해석하지 않는다.
- `status_code=404/500/503`만으로 취약점, exploit success, compromise를 단정하지 않는다.
- `status_code=200`만으로 공격 성공, 로그인 성공, 업로드 성공을 단정하지 않는다.
- `response_body_bytes`, `content_type`, `text/html`만으로 파일 노출이나 내부 결과를 단정하지 않는다.
- payload-bearing request가 candidate로 남아도 DB 영향, 파일 노출, 실행 성공 증거로 승격하지 않는다.
- payload 없는 status/error-only 요청은 diagnostic bucket으로만 관찰한다.
- actual prepare demotion 확대 적용은 계속 보류한다.

## 15. Open Questions

- reverse proxy topology는 1차 direct app 비교 후에도 추가 가치가 충분한가
- OpenCart v2 external run은 PHP sample 이후 실제로 필요한가
- remoteIP 환경은 별도 설계 후 어느 범위에서 비교해야 하는가

## 16. Recommended Next Step

- direct PHP external error-heavy baseline은 일단 닫는다.
- 2차 proxy topology run 필요 여부를 다시 판단한다.
- remoteIP, prepare/scoring/filtering, Web UI taxonomy 변경은 모두 별도 설계 전까지 보류한다.
