# D Set Runner

이 디렉터리는 D세트 Path Traversal / HPP / Directory Probing 실험용 Python runner를 둔다.

Migration note:

- Runner code has moved to `scripts/lab_runners/d_set/`.
- This `lab/d_set/README.md` is retained as a legacy set note.
- Generated lab outputs remain under `lab/`.

- runner는 승인된 로컬 실험 환경에서만 실행한다.
- runner는 공격 성공 검증 도구가 아니라 Apache 로그에 남을 request target/query 구조를 재현하는 실험 harness다.
- public target 실제 실행은 기본적으로 금지한다. 계획 검토는 `--dry-run` 또는 `--print-plan`으로만 수행한다.
- response body 원문은 저장하거나 분석하지 않는다. 실제 실행 시에도 body 길이만 기록한다.
- 파일 읽기 성공, HPP 처리 결과, directory/file exposure를 검증하지 않는다.

현재 runner:

- `run_d_set_scenarios.py`: D세트 R1 traversal, R2 HPP, R3 directory probing 시나리오 실행

urllib 한계:

- `urllib`는 dot-segment path를 정규화할 수 있다.
- traversal raw path 보존 여부는 실행 후 Apache `raw_request_target`을 확인해야 한다.
- raw malformed request, protocol anomaly, raw socket 수준 검증은 G세트 raw socket runner 범위다.

시나리오:

- `r1`: `D-R1-01`~`D-R1-05` traversal / encoded traversal / null-byte-like suffix / PHP wrapper optional
- `r2`: `D-R2-01`~`D-R2-04` benign duplicate HPP / HPP+SQLi / HPP+XSS / POST body HPP optional
- `r3`: `D-R3-01`~`D-R3-09` sensitive path probing / admin path guessing / burst probing
- `all`: 전체 요청 계획 검토 또는 dry-run 전체 점검용
- 개별 ID 또는 comma-separated ID:
  - `D-R1-01`
  - `D-R2-02,D-R2-03`
  - `D-R3-09`

dry-run 예시:

```bash
python3 scripts/lab_runners/d_set/run_d_set_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r1 \
  --out lab/05-xx_D세트R1_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/d_set/run_d_set_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario D-R2-02,D-R2-03 \
  --out lab/05-xx_D세트R2_산출물/runner_logs \
  --dry-run

python3 scripts/lab_runners/d_set/run_d_set_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario all \
  --out lab/05-xx_D세트_산출물/runner_logs \
  --dry-run
```

실제 실행 예시:

```bash
python3 scripts/lab_runners/d_set/run_d_set_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r1 \
  --out lab/05-xx_D세트R1_산출물/runner_logs

python3 scripts/lab_runners/d_set/run_d_set_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r2 \
  --out lab/05-xx_D세트R2_산출물/runner_logs

python3 scripts/lab_runners/d_set/run_d_set_scenarios.py \
  --base-url http://192.168.56.105 \
  --scenario r3 \
  --out lab/05-xx_D세트R3_산출물/runner_logs
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

운영 권장:

- `all`은 dry-run 또는 전체 계획 검토에 더 적합하다.
- 실제 실험은 `r1`, `r2`, `r3`를 분리해 별도 export window로 운영하는 것을 권장한다.
- R2의 `D-R2-04`는 POST body visibility limitation 문서화용이다. Apache baseline에서 raw body가 보이지 않는다는 한계를 함께 기록해야 한다.

주의:

- `--dry-run` / `--print-plan`은 HTTP 요청을 보내지 않는다.
- public IP 또는 일반 도메인 대상 실제 실행은 `--allow-public-target` 없이는 거부된다.
- public target 실제 실행 예시는 의도적으로 제공하지 않는다.
