# H Set Runner Notes

이 디렉터리는 H세트 Static / Crawler / Scanner-like Noise 실험 runner를 둔다.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 HTTP 요청과 실행 메타를 기록하는 실험 harness다.
- runner는 static file 존재, robots/sitemap 내용, JS/CSS/image 내용, health endpoint 정상 여부, 공격 성공을 검증하지 않는다.
- request body와 response body 원문은 저장하지 않는다.
- public target 실제 실행은 기본적으로 거부하며, dry-run으로 계획만 확인할 수 있다.

현재 runner:

- `run_h_r1_static_baseline.py`: R1 static / health / normal browse baseline
- `run_h_r2_crawler_baseline.py`: R2 crawler-like baseline for robots/sitemap/product/category browse and repeated crawler-like UA sequences
- `run_h_r3_scanner_low_signal.py`: R3 scanner-like low-signal path runner for `/wp-login.php`, `/wp-admin/`, `/.env`, `/phpinfo.php`, `/server-status`, `/backup.zip`, and a short sensitive-path burst sequence
- `run_h_r4_mixed_baseline_scanner.py`: R4 mixed benign + scanner-like runner for same-window baseline/static/crawler-like requests and scanner-like sensitive-path requests

권장 예시:

```bash
python3 lab/h_set/run_h_r1_static_baseline.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_H세트R1_산출물/runner_logs \
  --dry-run

python3 lab/h_set/run_h_r2_crawler_baseline.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_H세트R2_산출물/runner_logs \
  --dry-run

python3 lab/h_set/run_h_r3_scanner_low_signal.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_H세트R3_산출물/runner_logs \
  --dry-run

python3 lab/h_set/run_h_r4_mixed_baseline_scanner.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_H세트R4_산출물/runner_logs \
  --dry-run
```

실행 산출물:

- 항상 생성: `execution_plan.json`, `execution_plan.md`, `run_metadata.json`
- 실제 실행 시 추가 생성: `request_results.jsonl`, `run_summary.md`

주의:

- runner는 static file 존재 여부를 증명하지 않는다.
- R2 runner는 robots/sitemap/product/category browse와 crawler-like UA가 candidate로 과승격되지 않는지 보는 baseline harness다.
- R3 runner는 scanner-like/sensitive-looking path가 성공 단정 없이 context-only로 보존되는지 보는 harness다.
- R4 runner는 정상 browse/static/crawler-like 요청과 scanner-like sensitive path가 같은 window에 섞였을 때 baseline context와 scanner-like context를 과도하게 합치지 않는지 보는 mixed harness다.
- Googlebot/Bingbot-like UA라도 실제 crawler로 단정하지 않는다.
- `/wp-login.php`, `/wp-admin/`, `/.env`, `/phpinfo.php`, `/server-status`, `/backup.zip` 요청은 scanner-like 또는 sensitive-looking path context로만 다룬다.
- runner는 robots/sitemap 내용, site structure, product/category page existence를 검증하지 않는다.
- runner는 WordPress 존재, admin access 성공, `.env` 노출, `phpinfo` 노출, `server-status` 노출/차단 성공, `backup.zip` 노출, 공격 성공을 검증하지 않는다.
- runner는 mixed 시나리오에서도 crawler authenticity, file exposure, app presence, attack success를 검증하지 않는다.
- runner는 `robots.txt` / `sitemap.xml` 내용을 저장하거나 정책/구조를 해석하지 않는다.
- runner는 JS/CSS/image 내용을 저장하거나 실행 의미를 해석하지 않는다.
- runner는 health endpoint의 정상 여부를 단정하지 않는다.
- runner는 `status_code`, `response_body_bytes`, `User-Agent`만으로 정상/공격/노출 성공을 단정하지 않는다.
- request body와 response body 원문은 저장하지 않는다.
