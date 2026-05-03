# G Set Runner Notes

이 디렉터리는 G세트 HTTP Method / Protocol Anomaly 실험 runner를 둔다.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 HTTP 요청과 실행 메타를 기록하는 실험 harness다.
- runner는 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점 성공을 검증하지 않는다.
- raw response body와 request body 원문은 저장하지 않는다.
- public target 실제 실행은 기본적으로 거부하며, dry-run으로 계획만 확인할 수 있다.

현재 runner:

- `run_g_r1_method_probe.py`: R1 `OPTIONS` / `TRACE` / `PUT` / `DELETE` / `HEAD` / `GET` method probing
- `run_g_r2_protocol_anomaly.py`: R2 protocol / malformed request-like behavior 관찰 runner, raw socket 기반 HTTP 요청 사용
- `run_g_r3_baseline.py`: R3 baseline / FP bait runner, 정상 `HEAD` / browser-like `OPTIONS` preflight / normal `GET` / monitoring-like UA baseline 관찰

future:

- 필요 시 후속 round runner 추가

권장 예시:

```bash
python3 lab/g_set/run_g_r1_method_probe.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R1_산출물/runner_logs \
  --dry-run

python3 lab/g_set/run_g_r2_protocol_anomaly.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R2_산출물/runner_logs \
  --dry-run

python3 lab/g_set/run_g_r3_baseline.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R3_산출물/runner_logs \
  --dry-run
```

실행 산출물:

- 항상 생성: `execution_plan.json`, `execution_plan.md`, `run_metadata.json`
- 실제 실행 시 추가 생성: `request_results.jsonl`, `run_summary.md`

주의:

- `TRACE` 응답 body는 수집하거나 출력하지 않는다.
- `PUT` dummy body는 매우 짧게 사용하며, body 원문은 저장하지 않고 길이만 기록한다.
- `DELETE`는 테스트 전용 path에만 사용한다.
- R2는 invalid method, bad protocol version, missing/odd `Host`, long path 같은 protocol / malformed request-like behavior가 Apache 로그 표면에 어떻게 남는지 관찰하기 위한 harness다.
- R2는 raw socket 기반일 수 있으며 `http://` target만 지원한다.
- R2는 침해 성공, 우회 성공, malformed request 성공을 검증하지 않는다.
- R2는 raw request 원문과 response body 원문을 저장하지 않는다.
- R3는 정상 `HEAD`, browser-like `OPTIONS` preflight, normal `GET`, monitoring-like UA가 `method_probe` 또는 `protocol_anomaly`로 과승격되지 않는지 보는 baseline / FP bait harness다.
- R3는 CORS 취약점, method 허용, 서버 설정 취약 여부를 검증하지 않는다.
- R3는 request body 원문과 response body 원문을 저장하지 않는다.
