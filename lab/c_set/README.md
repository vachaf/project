# C Set XSS Runner

이 디렉터리는 C세트 XSS 실험용 Python runner를 둔다.

Migration note:

- Runner code has moved to `scripts/lab_runners/c_set/`.
- This `lab/c_set/README.md` is retained as a legacy set note.
- Generated lab outputs remain under `lab/`.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 XSS 공격 성공 검증 도구가 아니라 Apache 로그에 남을 request target/query 구조를 재현하는 실험 harness다.
- public target 실제 실행은 기본적으로 거부한다. 계획 확인은 `--dry-run` 또는 `--print-plan`으로만 수행한다.
- response body 원문은 저장하거나 분석하지 않는다. 실제 실행 시에도 body 길이만 기록한다.
- XSS 실행 성공, 브라우저 렌더링, DOM 반영, 쿠키 탈취 성공을 검증하지 않는다.

현재 runner:

- `run_c_xss_scenarios.py`: C세트 XSS encoded/basic/attribute/false-positive control 시나리오 실행

시나리오:

- `basic_script`: 기본 `<script>alert(1)</script>` 형태를 encoded path로 재현
- `url_encoded`: `document.cookie` 접근 의도가 포함된 URL-encoded script tag 재현
- `html_entity`: HTML entity encoded script tag 재현
- `attribute_event`: `onerror` attribute injection 형태 재현
- `fp_bait`: `tutorial` / `onerror` / `javascript` 키워드가 포함된 false-positive control

dry-run 예시:

```bash
python3 scripts/lab_runners/c_set/run_c_xss_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_C세트_runner_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/c_set/run_c_xss_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario fp_bait \
  --out lab/05-xx_C세트_runner_산출물/runner_logs \
  --dry-run
```

실제 실행 예시:

```bash
python3 scripts/lab_runners/c_set/run_c_xss_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_C세트_runner_산출물/runner_logs

python3 scripts/lab_runners/c_set/run_c_xss_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario attribute_event \
  --out lab/05-xx_C세트_runner_산출물/runner_logs
```

출력 파일:

- 항상 생성: `execution_plan.json`, `execution_plan.md`, `run_metadata.json`
- 실제 실행 시 추가 생성: `request_results.jsonl`, `run_summary.md`

출력 파일 설명:

- `execution_plan.json`: runner 메타데이터와 request 계획의 machine-readable JSON
- `execution_plan.md`: 사람이 검토하기 위한 request 계획 표
- `run_metadata.json`: 실행 인자, 모드, 시나리오 수, 생성 시각 기록
- `request_results.jsonl`: 실제 실행 시 각 요청의 status/body-bytes/duration/error 기록
- `run_summary.md`: 실제 실행 시 status 분포, scenario별 결과, 오류 요약, body-bytes 요약 기록

주의:

- `--dry-run` / `--print-plan`은 HTTP 요청을 보내지 않는다.
- public IP 또는 일반 도메인 대상 실제 실행은 `--allow-public-target` 없이는 거부된다.
- README 예시는 승인된 로컬 실험 환경을 전제로 하며, public target 실제 실행 예시는 제공하지 않는다.
