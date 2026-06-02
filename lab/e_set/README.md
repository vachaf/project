# E Set OpenCart Runners

이 디렉터리는 E세트 OpenCart/PHP 실험용 Python runner를 둔다.

> Migration note:
> Runner code moved from this legacy `lab/e_set` directory to
> `scripts/lab_runners/e_set/`.
> This README is kept as a legacy set note. Generated lab outputs remain under
> `lab/`.

- runner는 승인된 로컬 OpenCart/PHP 실험 환경에서만 실행한다.
- runner는 공격 성공 검증 도구가 아니라 Apache 로그에 남을 request target/query 구조와 실행 메타데이터를 재현하는 실험 harness다.
- public target 실제 실행은 기본적으로 금지한다. 계획 검토는 `--dry-run` 또는 `--print-plan`으로만 수행한다.
- response body 원문은 저장하거나 분석하지 않는다. 실제 실행 시에도 body 길이만 기록한다.
- 파일 노출, SQLi 성공, XSS 실행, DB 유출을 검증하지 않는다.

현재 runner:

- `run_e_r2_php_wrapper_scenarios.py`: R2/R2B PHP wrapper / config exposure / file disclosure intent 시나리오
- `run_e_r3_search_scenarios.py`: R3/R3B search baseline / SQLi / XSS / HTML entity XSS 시나리오

분리 이유:

- R2/R2B는 OpenCart/PHP 환경에서만 의미가 큰 `php://filter`와 config path probing을 다룬다.
- R3/R3B는 일반화된 `/search?q=...` 형태로 baseline / SQLi / XSS query 구조를 비교한다.
- 두 축은 해석 기준이 달라 별도 export window와 별도 runner로 운영하는 것이 적절하다.

Public target guard:

- `--dry-run` / `--print-plan`에서는 public URL도 허용한다. 실제 HTTP 요청을 보내지 않기 때문이다.
- 실제 실행 모드에서는 `localhost`, `127.0.0.1`, `::1`, private IP, `.local`, `.test`만 기본 허용한다.
- 그 외 public IP 또는 일반 도메인은 `--allow-public-target` 없이는 실행을 거부한다.
- public target 실제 실행 예시는 제공하지 않는다.

운영 원칙:

- R2/R2B와 R3/R3B는 별도 export window로 분리 운영하는 것을 권장한다.
- PHP wrapper 시나리오는 OpenCart/PHP 환경에서만 의미가 있다.
- `/config.php`, `/admin/config.php` direct probe는 wrapper보다 낮은 신호로 봐야 한다.
- `status_code=200`, `text/html`, `response_body_bytes`만으로 파일 노출, SQLi 성공, XSS 실행을 단정하면 안 된다.

R2 dry-run 예시:

```bash
python3 scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario all \
  --out lab/05-xx_E세트R2_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario variant \
  --out lab/05-xx_E세트R2B_산출물/runner_logs \
  --dry-run
```

R2 실제 실행 예시:

```bash
python3 scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario wrapper \
  --out lab/05-xx_E세트R2_산출물/runner_logs

python3 scripts/lab_runners/e_set/run_e_r2_php_wrapper_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario direct_config \
  --out lab/05-xx_E세트R2_산출물/runner_logs
```

R3 dry-run 예시:

```bash
python3 scripts/lab_runners/e_set/run_e_r3_search_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario all \
  --out lab/05-xx_E세트R3_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/e_set/run_e_r3_search_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario baseline \
  --out lab/05-xx_E세트R3B_산출물/runner_logs \
  --dry-run
```

R3 실제 실행 예시:

```bash
python3 scripts/lab_runners/e_set/run_e_r3_search_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario all \
  --out lab/05-xx_E세트R3_산출물/runner_logs

python3 scripts/lab_runners/e_set/run_e_r3_search_scenarios.py \
  --base-url http://192.168.56.111 \
  --scenario xss \
  --out lab/05-xx_E세트R3_산출물/runner_logs
```

출력 파일:

- 항상 생성: `execution_plan.json`, `execution_plan.md`, `run_metadata.json`
- 실제 실행 시 추가 생성: `request_results.jsonl`, `run_summary.md`

출력 파일 설명:

- `execution_plan.json`: runner 메타데이터와 request 계획의 machine-readable JSON
- `execution_plan.md`: 사람이 검토하기 위한 request 계획 표와 해석 제한
- `run_metadata.json`: 실행 인자, 모드, 시나리오 수, 생성 시각 기록
- `request_results.jsonl`: 실제 실행 시 각 요청의 status/body-bytes/duration/error 기록
- `run_summary.md`: 실제 실행 시 status 분포, scenario별 결과, 오류 요약, body-bytes 요약 기록

지원 scenario 필터:

- R2 runner: `all`, `wrapper`, `direct_config`, `variant`, 개별 ID, comma-separated ID
- R3 runner: `all`, `baseline`, `sqli`, `xss`, 개별 ID, comma-separated ID

주의:

- `--out`은 출력 디렉터리다. 파일은 해당 디렉터리 내부에 생성된다.
- `--dry-run` / `--print-plan`은 HTTP 요청을 보내지 않는다.
- public target 실제 실행 예시는 의도적으로 제공하지 않는다.
