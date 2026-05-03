# B Set SQLi Runners

이 디렉터리는 B세트 SQL Injection 실험용 Python runner를 둔다.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 SQLi 성공 검증 도구가 아니라 Apache 로그에 남을 request target/query 구조와 실행 메타데이터를 재현하는 실험 harness다.
- public target 실제 실행은 기본적으로 금지한다. 계획 검토는 `--dry-run` 또는 `--print-plan`으로만 수행한다.
- response body 원문은 저장하거나 분석하지 않는다. 실제 실행 시에도 body 길이만 기록한다.
- SQLi 성공, DB 유출, 인증 우회 성공을 검증하지 않는다.

현재 runner:

- `run_b_r1_sqli_scenarios.py`: Round 1 Auth Bypass / Union-based / Error-based SQLi 시나리오
- `run_b_r2_sqli_scenarios.py`: Round 2 Boolean Blind / Time-based / Evasion / Chain / FP bait 시나리오

운영 원칙:

- R1과 R2는 별도 export window로 분리 운영하는 것을 강하게 권장한다.
- R2 안에서도 `r2a`와 `r2b`를 분리하면 Boolean/Time과 Evasion/Chain/FP를 더 명확히 비교할 수 있다.
- POST body 기반 payload는 execution-only 입력이다. Apache baseline 로그에서는 raw POST body가 보이지 않으므로 body 내용 자체를 근거로 해석하면 안 된다.
- time-based SQLi는 runner의 `duration_ms`가 아니라 Apache `duration_us` / `ttfb_us`를 기준으로 해석해야 한다.

Public target guard:

- `--dry-run` / `--print-plan`에서는 public URL도 허용한다. 실제 HTTP 요청을 보내지 않기 때문이다.
- 실제 실행 모드에서는 `localhost`, `127.0.0.1`, `::1`, private IP, `.local`, `.test`만 기본 허용한다.
- 그 외 public IP 또는 일반 도메인은 `--allow-public-target` 없이는 실행을 거부한다.
- public target 실제 실행 예시는 제공하지 않는다.

Optional 시나리오:

- R1 `B-R1-04`는 destructive stacked `DROP TABLE` 계열이라 기본 제외된다.
- R2 `B-R2A-05`, `B-R2A-06`는 quote-only legacy pair라 기본 제외된다.
- R2 `B-R2B-03`은 `randomblob(30000000)` high-load 시나리오라 기본 제외된다.
- optional 시나리오는 `--include-optional`을 명시해야만 선택할 수 있다.
- 특히 destructive/high-load 시나리오는 격리된 로컬 환경에서만 사용해야 한다.

R1 dry-run 예시:

```bash
python3 lab/b_set/run_b_r1_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario core \
  --out lab/05-xx_B세트R1_산출물/runner_logs \
  --dry-run

python3 lab/b_set/run_b_r1_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario B-R1-06,B-R1-07 \
  --out lab/05-xx_B세트R1_산출물/runner_logs \
  --dry-run
```

R1 실제 실행 예시:

```bash
python3 lab/b_set/run_b_r1_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario core \
  --out lab/05-xx_B세트R1_산출물/runner_logs

python3 lab/b_set/run_b_r1_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario auth \
  --out lab/05-xx_B세트R1_산출물/runner_logs
```

R2 dry-run 예시:

```bash
python3 lab/b_set/run_b_r2_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario core \
  --out lab/05-xx_B세트R2_산출물/runner_logs \
  --dry-run

python3 lab/b_set/run_b_r2_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r2b \
  --out lab/05-xx_B세트R2B_산출물/runner_logs \
  --dry-run

python3 lab/b_set/run_b_r2_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario B-R2B-E04,B-R2B-F01 \
  --out lab/05-xx_B세트R2_산출물/runner_logs \
  --dry-run
```

R2 실제 실행 예시:

```bash
python3 lab/b_set/run_b_r2_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r2a \
  --out lab/05-xx_B세트R2A_산출물/runner_logs

python3 lab/b_set/run_b_r2_sqli_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r2b \
  --out lab/05-xx_B세트R2B_산출물/runner_logs
```

출력 파일:

- 항상 생성: `execution_plan.json`, `execution_plan.md`, `run_metadata.json`
- 실제 실행 시 추가 생성: `request_results.jsonl`, `run_summary.md`

출력 파일 설명:

- `execution_plan.json`: runner 메타데이터와 request 계획의 machine-readable JSON
- `execution_plan.md`: 사람이 검토하기 위한 request 계획 표와 해석 제한
- `run_metadata.json`: 실행 인자, 모드, 시나리오 수, 생성 시각 기록
- `request_results.jsonl`: 실제 실행 시 각 요청의 status/body-bytes/duration/error 기록
- `run_summary.md`: 실제 실행 시 status 분포, scenario별 결과, 오류 요약, body-bytes 요약, boolean pair 비교, time-track 주의 문구 기록

시나리오 선택:

- R1: `all`, `core`, `auth`, `union`, `error`, 개별 ID, comma-separated ID
- R2: `all`, `core`, `boolean`, `time`, `evasion`, `chain`, `fp`, `r2a`, `r2b`, 개별 ID, comma-separated ID

주의:

- `--out`은 출력 디렉터리다. 파일은 해당 디렉터리 내부에 생성된다.
- `--dry-run` / `--print-plan`은 HTTP 요청을 보내지 않는다.
- public target 실제 실행 예시는 의도적으로 제공하지 않는다.
