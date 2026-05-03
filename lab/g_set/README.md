# G Set Runner Notes

이 디렉터리는 G세트 HTTP Method / Protocol Anomaly 실험 runner를 둔다.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 HTTP 요청과 실행 메타를 기록하는 실험 harness다.
- runner는 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점 성공을 검증하지 않는다.
- raw response body와 request body 원문은 저장하지 않는다.
- public target 실제 실행은 기본적으로 거부하며, dry-run으로 계획만 확인할 수 있다.

현재 runner:

- `run_g_r1_method_probe.py`: R1 `OPTIONS` / `TRACE` / `PUT` / `DELETE` / `HEAD` / `GET` method probing

future:

- `run_g_r2_protocol_anomaly.py`
- `run_g_r3_baseline.py`

권장 예시:

```bash
python3 lab/g_set/run_g_r1_method_probe.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_G세트R1_산출물/runner_logs \
  --dry-run
```

실행 산출물:

- 항상 생성: `execution_plan.json`, `execution_plan.md`, `run_metadata.json`
- 실제 실행 시 추가 생성: `request_results.jsonl`, `run_summary.md`

주의:

- `TRACE` 응답 body는 수집하거나 출력하지 않는다.
- `PUT` dummy body는 매우 짧게 사용하며, body 원문은 저장하지 않고 길이만 기록한다.
- `DELETE`는 테스트 전용 path에만 사용한다.
