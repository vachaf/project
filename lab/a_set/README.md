# A Set Baseline/Auth Runner

이 디렉터리는 A세트 baseline/auth 실험용 Python runner를 둔다.

Migration note:

- Runner code has moved to `scripts/lab_runners/a_set/`.
- This `lab/a_set/README.md` is retained as a legacy set note.
- Generated lab outputs remain under `lab/`.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 로그인 성공 검증 도구가 아니라 Apache 로그에 남을 request target/method/status/bytes/time/user-agent 구조와 실행 메타데이터를 재현하는 실험 harness다.
- public target 실제 실행은 기본적으로 금지한다. 계획 검토는 `--dry-run` 또는 `--print-plan`으로만 수행한다.
- response body 원문은 저장하거나 분석하지 않는다. 실제 실행 시에도 body 길이만 기록한다.
- 로그인 성공, 인증 우회 성공, token issuance, session creation, account takeover를 검증하지 않는다.

현재 runner:

- `run_a_baseline_auth_scenarios.py`: baseline browsing/search, 단일 auth failure, 반복 auth failure, POST body visibility limitation, protected resource baseline 시나리오

운영 원칙:

- A세트는 baseline/auth 기본 흐름 확인용이다.
- F세트처럼 반복적이고 공격성 강한 auth abuse 실험이 아니라 baseline 중심 비교에 가깝다.
- POST body는 execution-only 입력이다. Apache 로그 기반 분석 pipeline에는 raw POST body가 보이지 않는다.
- `status_code=200`과 `response_body_bytes`는 HTTP surface observation일 뿐 로그인 성공이나 우회 성공을 뜻하지 않는다.

Public target guard:

- `--dry-run` / `--print-plan`에서는 public URL도 허용한다. 실제 HTTP 요청을 보내지 않기 때문이다.
- 실제 실행 모드에서는 `localhost`, `127.0.0.1`, `::1`, private IP, `.local`, `.test`만 기본 허용한다.
- 그 외 public IP 또는 일반 도메인은 `--allow-public-target` 없이는 실행을 거부한다.
- public target 실제 실행 예시는 제공하지 않는다.

dry-run 예시:

```bash
python3 scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_A세트_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario baseline \
  --out lab/05-xx_A세트_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario A-R1-10,A-R1-11 \
  --out lab/05-xx_A세트_산출물/runner_logs \
  --dry-run
```

실제 실행 예시:

```bash
python3 scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_A세트_산출물/runner_logs

python3 scripts/lab_runners/a_set/run_a_baseline_auth_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario auth \
  --out lab/05-xx_A세트_산출물/runner_logs
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

- `all`
- `baseline`
- `auth`
- `protected`
- 개별 ID
- comma-separated ID

주의:

- `--out`은 출력 디렉터리다. 파일은 해당 디렉터리 내부에 생성된다.
- `--dry-run` / `--print-plan`은 HTTP 요청을 보내지 않는다.
- response body 원문은 저장하지 않고, token/session 값을 검사하지 않는다.
