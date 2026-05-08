# scripts/

## 목적

`scripts/`는 회귀 검증, 요약, 보조 점검, 실험 로그 생성 스크립트를 두는 폴더다.

주요 목적은 코드 변경 후 prepare / stage dry-run 결과가 기대 구조를 유지하는지 확인하고, Stage2 실제 보고서의 Apache logs-only wording risk를 review-only 방식으로 점검하는 것이다.

또한 `generate_lab_traffic.py`는 authorized lab 환경에서 Apache access log 원천 데이터를 의도적으로 생성해 `export -> prepare -> stage1 -> stage2 -> viewer_payload` 흐름을 검증하는 보조 CLI다. 이 도구는 실제 exploit 성공, 침해, 권한 획득, 서버 상태 변경을 검증하는 도구가 아니다.

## 주요 검증 명령

```bash
python3 scripts/check_prepare_regression.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py
python3 scripts/check_stage_dryrun_regression.py --strict
python3 scripts/check_stage2_report_quality.py --input path/to/stage2_report.json --pretty
python3 -m pytest tests/test_stage2_report_quality.py

python3 -m py_compile scripts/generate_lab_traffic.py
python3 -m pytest tests/test_generate_lab_traffic.py
```

## 주요 스크립트

- `check_prepare_regression.py`
  - prepare output key, candidate 보존, filtered/context-only 구조를 fixture 기준으로 검증한다.
- `check_stage_dryrun_regression.py`
  - prepare -> stage1 dry-run -> stage2 dry-run 구조가 기대 schema와 policy를 유지하는지 검증한다.
- `check_stage2_report_quality.py`
  - Stage2 report JSON의 성공/침해/유출/실행 단정 wording risk를 Apache logs-only 기준으로 점검한다.
  - 기본 모드는 warning-only이며 exit code 0을 유지한다.
  - `--fail-on-blocker`를 지정한 경우에만 blocker가 있을 때 non-zero exit을 사용할 수 있다.
  - `--pretty`는 결과 JSON을 보기 좋게 stdout에 출력한다.
  - `--output`이 있을 때만 결과 JSON 파일을 저장한다.
  - strong negation과 weak conservative context를 구분해 safe negation blocker 과잉탐지를 줄인다.
- `generate_lab_traffic.py`
  - authorized lab 전용 Apache access log 원천 데이터 생성기다.
  - 실제 exploit 성공/침해/권한획득/서버 상태 변경 검증 도구가 아니다.
  - GET/HEAD/OPTIONS 중심, fragment(`#`) 금지, 시나리오 기반 marker/context 로그 생성에 사용한다.
  - SQLi/XSS/traversal/CMDI/HPP/PHP wrapper/file disclosure/Log4Shell-style/SSRF-like/SSTI/XXE/webshell/auth/method/protocol/static/crawler/scanner/mixed context coverage를 넓히기 위한 v2 시나리오를 제공한다.
  - `--mutate-params`, `--profile-delay`, `--print-curl`, `--xff-pool-file` 등은 실험 로그 다양성 확보용 옵션이며, Apache logs-only 해석 원칙을 바꾸지 않는다.
- `run_qa_check_production_v4.py`
  - 공식 regression/lint를 대체하지 않는 별도 QA v4 보조/실험 스크립트다.
  - score/confidence/debug 기반으로 Stage2 report 품질을 보조 점검할 때 사용한다.
  - `"report": null` 형태의 dry-run report도 안전하게 처리한다.
- `cleanup_outputs.py`
  - output retention policy 기준의 list-only cleanup candidate inventory를 만든다.
  - 삭제 기능 없음, `--apply` 미구현.

QA v4 보조 스크립트 예시:

```bash
python3 scripts/run_qa_check_production_v4.py \
  --input path/to/stage2_report.json \
  --rule-weight strict \
  --debug
```

구분 기준:

- `check_stage2_report_quality.py`
  - Apache logs-only wording risk를 review-only lint로 점검하는 공식 축
- `run_qa_check_production_v4.py`
  - 별도 scoring 기반 QA 보조 스크립트

## generate_lab_traffic.py 사용 기준

`generate_lab_traffic.py`는 실험 환경에서 로그가 자연스럽게 충분히 쌓이지 않을 때, 정상/노이즈/의심 marker 요청을 의도적으로 발생시켜 pipeline E2E 검증용 원천 데이터를 만드는 도구다.

운영 원칙:

- authorized lab target에만 사용한다.
- 실제 exploit 성공, 파일 노출, 명령 실행, 계정 탈취, 브라우저 실행 여부를 확인하지 않는다.
- `status_code`, response size, content type, UA, IP, route name은 success proof가 아니라 로그 필드일 뿐이다.
- 기본 허용 method는 `GET`, `HEAD`, `OPTIONS`다.
- `#` fragment는 Apache 로그에 남지 않으므로 시나리오 endpoint에서 금지한다.
- X-Forwarded-For는 Apache log format 또는 `mod_remoteip` 설정 없이는 실제 `source_ip`를 바꾸지 않는다.
- 실제 source IP 다양성이 필요하면 여러 VM/컨테이너/호스트에서 같은 스크립트를 실행한다.

기본 dry-run:

```bash
python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id SQLi_Markers \
  --count 10 \
  --seed 1337 \
  --dry-run \
  --print-curl
```

정상/노이즈 로그 생성:

```bash
python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id JuiceShop_Normal \
  --count 100 \
  --profile-delay \
  --seed 101

python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id Baseline_Crawler_Mixed \
  --count 80 \
  --profile-delay \
  --seed 102
```

의심 marker 로그 생성:

```bash
python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id SQLi_Markers \
  --count 40 \
  --mutate-params \
  --seed 201

python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id XSS_Markers \
  --count 40 \
  --mutate-params \
  --seed 202

python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id Mixed_Context_Heavy \
  --count 120 \
  --profile-delay \
  --mutate-params \
  --seed 299
```

저속 probing context:

```bash
python3 scripts/generate_lab_traffic.py \
  --base-url http://192.168.56.105 \
  --target-name JuiceShop \
  --scenario-id LowAndSlow \
  --duration-minutes 15 \
  --profile-delay \
  --seed 301
```

실행 summary의 `start_time`, `end_time`, `request_count`, `http_error_count`, `transport_error_count`, `method_counts`, `tag_counts`, `ua_family_counts`, `endpoint_unique_count`를 보고 export window와 실험 품질을 확인한다.

## generate_lab_traffic.py 주요 시나리오

기존 baseline 시나리오:

- `JuiceShop_Normal`
- `OpenCart_Normal`
- `Static_Noise`
- `ScannerBurst`
- `LowAndSlow`
- `SuspiciousQueryMix`

v2 coverage 시나리오:

- `SQLi_Markers`
- `XSS_Markers`
- `Traversal_FileDisclosure_Markers`
- `CMDI_Markers`
- `HPP_Markers`
- `Log4Shell_SSRF_Markers`
- `SSTI_XXE_Markers`
- `Webshell_Path_Markers`
- `Auth_Context_Markers`
- `Method_Protocol_Context`
- `Baseline_Crawler_Mixed`
- `Mixed_Context_Heavy`

권장 사용 순서:

1. `--dry-run --print-curl`로 요청 계획을 확인한다.
2. 정상/노이즈 시나리오를 먼저 실행한다.
3. marker 시나리오를 시간대를 분리해 실행한다.
4. summary의 start/end를 기준으로 `export_db_logs_cli.py --start --end` window를 잡는다.
5. `run_analysis_pipeline.py --export-input`으로 E2E 분석을 실행한다.
6. `noise_summary`, `analysis_candidates`, context-only summaries, `supporting_events`, `viewer_payload`를 확인한다.

## 현재 검증 기준

```text
prepare regression: pass=25 warn=0 fail=0
stage dry-run regression: pass=19 warn=0 fail=0
Stage2 report quality lint tests: 14 passed
table resolution tests: 8 passed
```

최신 H R4 / E R2B actual report quality lint 기준:

```text
blocker_count=0
warning_count=0
info_count=6
verdict=PASS
```

## 관리 원칙

- 공식 검증 기준은 `check_prepare_regression.py`, `check_stage_dryrun_regression.py`, `check_stage2_report_quality.py`를 우선한다.
- regression check, dry-run check, 요약 helper처럼 개발/검증 보조 스크립트를 둔다.
- Stage2 report quality lint는 공격 성공 여부를 판정하는 도구가 아니라 wording review 도구다.
- `generate_lab_traffic.py`는 공격 자동화 도구가 아니라 authorized lab traffic generator다.
- `generate_lab_traffic.py`는 로그 indicator를 생성할 뿐 exploit 성공, 파일 노출, 명령 실행, 계정 탈취, 브라우저 실행 여부를 검증하지 않는다.
- QA v4 score는 공식 regression 통과/실패와 같은 의미가 아니다.
- QA v4는 Apache logs-only 단정 금지 원칙을 보조적으로 점검하는 용도다.
- warning은 사람이 검토해야 하는 후보이지 자동 실패가 아니다.
- `--fail-on-blocker`는 수동 확인 후 제한적으로 사용한다.
- 파이프라인 본체 코드는 `src/`에 둔다.
- 실험 산출물은 `lab/`에 둔다.
- expected fixture와 실제 출력의 차이는 코드 변경 의도와 함께 검토한다.

## 관련 문서

- 현재 상태: `../docs/진행상황.md`
- 운영 기준 실행 가이드: `../docs/operations/01_운영_기준_실행_가이드.md`
- prepare regression 설계: `../docs/design/99_prepare_regression_fixture_설계.md`
- stage dry-run regression 설계: `../docs/design/99_stage_dryrun_regression_설계.md`
- Stage2 report quality lint 후보 검토: `../docs/design/99_stage2_report_quality_lint_candidate_review.md`
- Stage2 report quality lint tuning: `../docs/design/99_stage2_report_quality_lint_tuning_plan.md`
- Stage2 prompt compaction: `../docs/design/99_stage2_prompt_compaction_plan.md`
