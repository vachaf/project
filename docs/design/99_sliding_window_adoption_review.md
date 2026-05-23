# 99_sliding_window_adoption_review

- 문서 상태: 팀원 작성 Sliding Window 문서 intake / adoption review
- 기준 시점: 2026-05-23 작업 예정
- 목적: Sliding Window 문서 세트를 바로 구현하기 전에 현재 Apache logs-only LLM pipeline 기준으로 수용 범위, 검증 항목, 보류 항목을 정리한다.

관련 입력 문서:

- `sliding_window_definition.md`
- `sliding_window_architecture_plan.md`
- `sliding_window_integration.md`
- `token_cost_estimation.md`

관련 repo 문서:

- [99_prepare_candidate_policy.md](./99_prepare_candidate_policy.md)
- [99_prepare_candidate_policy_distribution_history.md](./99_prepare_candidate_policy_distribution_history.md)
- [99_observability_run_summary_index.md](./99_observability_run_summary_index.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 문서 세트의 성격

팀원 작성 Sliding Window 문서 세트는 prepare/scoring/filtering 변경 제안이 아니라 운영 자동화와 token/cost control을 위한 설계 패키지로 본다.

핵심 방향:

```text
긴 시간 범위 로그를 한 번에 pipeline에 넣지 않고,
export 단계에서 시간 window로 나누어 prepare/window artifact를 생성한 뒤,
필요한 경우 여러 window 결과를 rollup하여 Stage1/Stage2를 실행한다.
```

현재 기준 판단:

- Sliding Window 도입 위치는 prepare 내부가 아니라 export/scheduler 단계가 적절하다.
- `export_db_logs_cli.py --start/--end` 인터페이스를 활용하면 기존 prepare/stage1/stage2/viewer_payload 로직 변경을 최소화할 수 있다.
- prepare-only window 결과는 report run이 아니므로 기본적으로 `runs/`에 저장하지 않는다.
- `runs/`는 Stage2 report와 `viewer_payload.json`이 생성되는 rollup/report 단위에 한정하는 방향이 더 안전하다.

## 2. 우선 수용 가능한 방향

### 2.1 export 단계 scheduler 접근

수용 가능성이 높은 구조:

```text
sliding_window_scheduler.py
  -> window 목록 생성
  -> data/windowed/<date>/<window_id>/ 경로 결정
  -> export_db_logs_cli.py --start <window_start> --end <window_end> --out <window_dir>/export.json
  -> prepare_llm_input.py --input <window_dir>/export.json --out-dir <window_dir>/prepared
  -> window artifact 정규화/요약: llm_input.json, analysis_candidates.json, noise_summary.json, window_summary.json
  -> data/rollups/<date>/<rollup_id>/ rollup 입력 생성
  -> rollup 단위 Stage1/Stage2 실행 시에만 runs/<rollup_run_id>/ 생성
```

이 방식은 다음 장점이 있다.

- prepare 내부 집계 로직을 건드리지 않는다.
- candidate policy를 변경하지 않는다.
- stage1/stage2 prompt나 report semantics를 변경하지 않는다.
- window별 중간 산출물과 Web UI report run의 의미를 분리한다.
- 하루치 window 수가 많아져도 `runs/`와 Web UI list가 폭증하지 않는다.
- 운영 scheduler가 `--processed-dir`, `--reports-dir`, `--run-dir` 조합을 매번 수동으로 맞추는 구조를 피한다.

### 2.2 초기 운영 후보값

팀원 문서의 제안값은 검토 가치가 있다.

```text
window_size: 20분
stride:      15분 또는 30분
overlap:     5분 또는 상황별 조정
```

다만 이는 window마다 full pipeline을 실행한다는 전제에서 나온 값이므로, prepare-only window 기본값으로 바로 고정하지 않는다.

초기 권장 판단:

- prepare 기본 후보: `window_size=1시간`, `stride=1시간 또는 30분`
- burst 민감도 비교: `window_size=20분`, `stride=15분 또는 30분`
- 비용 우선 운영안은 rollup/stage2 실측 후 결정

## 3. Sliding Window 실행 단위 재검토

Sliding Window는 window마다 full pipeline을 실행하는 구조로 확정하지 않는다.

초기 수용 범위는 export 단계 windowing과 prepare-only window artifact 생성 가능성 검토로 제한한다. Stage1/Stage2는 window별 실행이 아니라 multi-window rollup 단위 실행을 우선 검토한다.

이 판단의 이유는 다음과 같다.

- 20분 window / 15분 stride / 5분 overlap은 scanner burst, sqlmap burst, 짧은 auth 반복 같은 단기 집중 패턴에는 유효하다.
- 그러나 1~4시간에 걸쳐 느리게 진행되는 low-and-slow probe나 campaign은 window별로 보면 단발 이벤트처럼 약화될 수 있다.
- window마다 stage2 report를 생성하면 하루 최대 수십~수백 개 report가 생겨 Web UI list, 운영자 검토, 중복 incident, 비용 측면에서 부담이 커진다.
- prepare는 Python 단계이므로 LLM token 비용 관점에서는 반드시 짧게 잘라야 하는 단계는 아니지만, export 크기, 실행 시간, artifact 재현성, burst 단위 관찰을 위해 windowing의 가치는 있다.
- 따라서 prepare window 결과를 다시 묶는 multi-window rollup artifact가 필요하다.

권장 구조는 다음과 같다.

1. Short/medium window prepare
   - 기본 후보는 1시간 window
   - 20분 window는 burst 민감도 비교용으로 유지
   - export + prepare까지만 실행
   - window별 candidate/context/policy distribution artifact 저장

2. Periodic rollup
   - 최근 2시간 또는 4시간 prepare 결과 수집
   - request_id dedup
   - src_ip / uri family / payload family / status pattern 집계
   - low-and-slow 후보 추출

3. LLM execution
   - stage1은 rollup top candidates만 실행
   - stage2는 window별이 아니라 rollup 단위로 1회 생성
   - 이 단계에서만 `runs/<rollup_run_id>/`를 생성한다.

4. Daily summary
   - raw log 전체 재분석이 아니라 rollup/stage2 결과 요약

## 4. Artifact layout 원칙

prepare-only window 결과는 아직 보안 보고서가 아니라 rollup을 만들기 위한 중간 산출물이다. 따라서 기본적으로 `runs/`에 저장하지 않는다.

권장 layout 후보:

```text
data/windowed/
  2026-05-23/
    sw_0900_1000/
      export.json
      llm_input.json
      analysis_candidates.json
      noise_summary.json
      window_summary.json
      prepared/                 # prepare_llm_input.py 원본 산출물 보관 후보

    sw_1000_1100/
      export.json
      llm_input.json
      analysis_candidates.json
      noise_summary.json
      window_summary.json
      prepared/

data/rollups/
  2026-05-23/
    rollup_0900_1300/
      rollup_input.json
      dedup_candidates.json
      rollup_summary.json

runs/
  rollup_20260523_0900_1300/
    manifest.json
    stage1_results.json
    stage2_report_input.json
    stage2_report.json
    stage2_report.md
    viewer_payload.json
```

역할 구분:

| 경로 | 역할 | Web UI 노출 기본값 |
|---|---|---|
| `data/windowed/` | window별 export/prepare 중간 산출물 | 노출하지 않음 |
| `data/rollups/` | multi-window rollup 입력/요약 산출물 | 노출하지 않음 |
| `runs/` | Stage2 report와 viewer_payload가 있는 report run | 노출 가능 |

이 구분을 유지하면 window 수가 늘어나도 Web UI list와 report run 개념이 흐려지지 않는다.

## 5. Scheduler ownership / CLI boundary

운영 구조에서는 `run_analysis_pipeline.py` 옵션을 매 window마다 조합하는 방식에 의존하지 않는다.

판단 기준:

- `run_analysis_pipeline.py`는 export JSON에서 prepare -> stage1 -> stage2 -> viewer_payload로 이어지는 one-shot 실행기 또는 resume 실행기로 유지한다.
- `sliding_window_scheduler.py`는 window 생성, export 실행, prepare-only artifact layout, window summary 생성, rollup 입력 생성을 담당한다.
- prepare-only window에서는 `run_analysis_pipeline.py --run-dir`를 사용하지 않는다.
- prepare-only window에서는 `runs/`를 만들지 않는다.
- rollup 이후 Stage1/Stage2 report를 생성할 때만 `run_analysis_pipeline.py` 또는 stage1/stage2 wrapper를 사용해 `runs/<rollup_run_id>/`를 만든다.

### 5.1 Window prepare 호출 방식

운영 scheduler의 기본 후보는 `prepare_llm_input.py` 직접 호출이다.

```text
export_db_logs_cli.py
  --start <window_start>
  --end <window_end>
  --table security
  --out data/windowed/<date>/<window_id>/export.json

prepare_llm_input.py
  --input data/windowed/<date>/<window_id>/export.json
  --out-dir data/windowed/<date>/<window_id>/prepared
  --base-name window
```

그 뒤 scheduler가 필요한 파일을 window root로 정규화한다.

```text
prepared/window_llm_input.json           -> llm_input.json
prepared/window_analysis_candidates.json -> analysis_candidates.json
prepared/window_noise_summary.json       -> noise_summary.json
```

`window_summary.json`은 prepare/scoring/filtering을 변경하지 않고 기존 prepare 산출물을 읽어서 만드는 후처리 artifact로 둔다.

### 5.2 Pipeline wrapper 사용 범위

`run_analysis_pipeline.py --stop-after prepare --processed-dir ... --reports-dir ...` 방식은 smoke test 또는 호환성 검증에는 사용할 수 있다. 그러나 scheduler 운영 기본 구조로 확정하지 않는다.

이유:

- window마다 `--processed-dir`, `--reports-dir`, `--work-dir`, `--base-name`를 조합하는 방식은 운영 실수 가능성이 높다.
- pipeline runner의 의미가 report pipeline과 window artifact generator 사이에서 흐려진다.
- `reports/`라는 이름의 중간 디렉터리가 prepare-only window 안에 생겨 개념적으로 혼동될 수 있다.

따라서 scheduler 구현에서는 layout ownership을 scheduler에 두고, window prepare는 `export_db_logs_cli.py` + `prepare_llm_input.py` 직접 호출을 우선 검토한다.

### 5.3 Scheduler 후보 인자

초기 scheduler 후보 인자는 다음 수준으로 제한한다.

```text
--work-dir
--analysis-start
--analysis-end
--window-minutes
--stride-minutes
--include-partial-final
--window-output-root
--rollup-output-root
--mode planner|export|prepare
```

추후 rollup 구현 시 후보:

```text
--rollup-minutes
--rollup-stride-minutes
--skip-existing-complete
--overwrite-failed
--prepare-source-tables
```

단, `--overwrite-failed` 같은 파괴적 동작은 기본값으로 두지 않는다.

## 6. 반드시 검증할 항목

### 6.1 CLI 호환성

문서 예시가 현재 repo의 실제 CLI 옵션과 맞는지 확인한다.

확인 대상:

- `src/export_db_logs_cli.py`
- `src/run_analysis_pipeline.py`
- `src/prepare_llm_input.py`
- `src/llm_stage1_classifier.py`
- `src/llm_stage2_reporter.py`

특히 다음 옵션은 실제 존재 여부와 이름을 확인해야 한다.

- `export_db_logs_cli.py`: `--start`, `--end`, `--table`, `--out`, `--out-dir`, `--limit`
- `prepare_llm_input.py`: `--input`, `--out-dir`, `--base-name`, `--min-score`, `--include-source-tables`
- `run_analysis_pipeline.py`: `--run-dir`, `--work-dir`, `--export-input`, `--processed-dir`, `--reports-dir`, `--stop-after`
- `llm_stage1_classifier.py`: `--input`, `--candidate-limit`, `--max-evidence-items`
- `llm_stage2_reporter.py`: stage2 top-N 관련 옵션명

문서 예시와 실제 CLI가 다르면 문서를 먼저 정정하고, 구현은 그 다음에 진행한다.

### 6.2 CLI 옵션 호환성 검토 결과

현재 repo 기준으로 Sliding Window 문서 예시 명령은 대부분 호환된다. 다만 direct CLI와 pipeline wrapper CLI의 옵션명을 분리해서 문서화해야 한다.

#### 6.2.1 호환되는 항목

`export_db_logs_cli.py`는 Sliding Window scheduler가 필요로 하는 시간 범위 export 옵션과 호환된다.

```text
--start
--end
--table
--pretty
--out
--out-dir
--limit
```

`run_analysis_pipeline.py`는 window export JSON을 받아 prepare-only 또는 full pipeline으로 실행할 수 있는 wrapper 옵션과 호환된다. 다만 prepare-only window artifact를 `runs/`에 저장하지 않으려면 `--run-dir`를 사용하지 않고, `--processed-dir` 등 산출물 경로 분리 방식을 검토해야 한다. 이는 smoke test에는 가능하지만 scheduler 운영 기본 구조로는 확정하지 않는다.

```text
--export-input
--work-dir
--processed-dir
--reports-dir
--run-dir
--llm-provider
--mode
--dry-run
--stop-after
--stage1-candidate-limit
--stage2-top-incidents
--stage2-top-noise-groups
--stage2-top-ips
```

#### 6.2.2 수정이 필요한 문서 예시

`llm_stage1_classifier.py`를 직접 실행할 때는 `--llm-input`이 아니라 `--input`을 사용해야 한다.

```bash
python3 src/llm_stage1_classifier.py \
  --input data/processed/security_..._llm_input.json \
  --candidate-limit 15 \
  --max-evidence-items 6
```

pipeline wrapper를 사용할 때는 stage1 제한 옵션명이 다르다.

```bash
python3 src/run_analysis_pipeline.py \
  --export-input data/raw/security_...json \
  --stage1-candidate-limit 15
```

stage2도 direct CLI와 wrapper CLI의 top-N 옵션명이 다르다.

```bash
# direct stage2
python3 src/llm_stage2_reporter.py \
  --stage1-results data/processed/security_..._stage1_results.json \
  --top-incidents 8 \
  --top-noise-groups 5 \
  --top-ips 5

# pipeline wrapper
python3 src/run_analysis_pipeline.py \
  --export-input data/raw/security_...json \
  --stage2-top-incidents 8 \
  --stage2-top-noise-groups 5 \
  --stage2-top-ips 5
```

#### 6.2.3 dry-run window count 주의

20분 window / 15분 stride / 2시간 범위는 기존 문서 예시처럼 6개 window가 아니다.

```text
partial final window 포함 시: 8개
full window만 허용 시:      7개
```

따라서 scheduler 설계 전 `partial final window`를 만들지 여부를 명시해야 한다. recurring 운영 기본값은 full window only가 더 안전하며, historical 검증에서만 partial final window 포함 여부를 별도 옵션으로 비교한다.

#### 6.2.4 현재 판단

CLI 옵션은 scheduler dry-run 설계로 진행할 수 있을 정도로 대체로 호환된다. 단, 팀원 작성 문서 4개를 그대로 편입할 경우 위 옵션명 차이와 window count 예시는 먼저 정정해야 한다.

### 6.3 prepare 내부 time window와 export window 관계

Sliding Window는 prepare 내부 time aggregation을 깨면 안 된다.

확인할 기준:

- `SUPPORTING_EVENT_TIME_WINDOW_SEC`
- `TEMPORAL_CONTEXT_BUCKET_SEC`
- `PROBING_SEQUENCE_WINDOW_SEC`
- `SENSITIVE_PATH_PROBE_WINDOW_SEC`
- `MIXED_BASELINE_SCANNER_WINDOW_SEC`
- `IP_BEHAVIOR_WINDOW_SEC`
- `AUTH_BEHAVIOR_WINDOW_SEC`

현재 판단:

- export/prepare window는 최소 5분보다 커야 한다.
- 현실적 하한은 10분 이상으로 둔다.
- prepare-only 기본 검증값은 1시간으로 둘 수 있다.
- 20분 window는 burst 민감도 비교용으로 유지한다.

### 6.4 overlap 중복 처리

overlap을 두면 동일 request가 두 window에 들어갈 수 있다.

초기 방침:

- prepare-only window artifact를 자동 dedup하지 않는다.
- 중복 request_id 확인은 diagnostic script 또는 rollup 단계에서 수행한다.
- dedup 결과를 Web UI verdict/severity/category에 반영하지 않는다.
- rollup 입력 생성 시점에 dedup 기준을 별도 문서화한다.

### 6.5 Web UI run list 증가

15분 stride로 window마다 `runs/`를 만들면 하루 최대 96개 run이 생길 수 있다. 이 구조는 기본안에서 제외한다.

검토 항목:

- `runs/`는 rollup/report 단위로 제한할 수 있는가
- prepare-only window artifact는 `data/windowed/`에 저장할 수 있는가
- Web UI loader가 `data/windowed/`를 report run으로 오인하지 않는가
- retention/cleanup 정책이 필요한가
- output cleanup script는 여전히 별도 승인 전까지 실제 삭제를 보류한다.

### 6.6 token/cost 실측

`token_cost_estimation.md`는 근사치 문서로 보고, 실제 운영 전에는 현재 모델 단가와 실제 run artifact 기반으로 재측정한다.

확인 항목:

- stage1 candidate 1건당 실제 input/output token
- stage2 report 1회당 실제 input/output token
- 1시간 prepare window의 평균 candidate 수
- 20분 prepare window와 1시간 prepare window의 candidate/context distribution 차이
- 2시간/4시간 rollup 단위 stage2 입력 크기
- Anthropic `max_tokens` truncation 재발 여부

## 7. Dry-run 검증 범위

Sliding Window scheduler 구현 전에는 실제 운영 자동화나 LLM 호출을 하지 않고, window 생성 규칙과 prepare-only artifact layout을 먼저 검증한다.

### 7.1 Dry-run level 구분

`dry-run`이라는 용어가 넓기 때문에 검증 단계를 분리한다.

```text
Level 0. planner dry-run
- window 목록만 출력
- DB 조회 없음
- 파일 생성 없음

Level 1. export smoke
- 일부 window만 export JSON 생성
- prepare 실행 없음 또는 선택
- 저장 위치는 data/windowed/<date>/<window_id>/

Level 2. prepare smoke
- 일부 window에 대해 export + prepare 실행
- stage1/stage2 실행 없음
- runs/가 아니라 data/windowed/<date>/<window_id>/에 저장
```

초기 검증은 Level 0부터 시작하고, 그 다음 일부 window에 대해서만 Level 2 prepare smoke를 수행한다. 하루치 전체 window를 처음부터 모두 prepare-only로 실행하지 않는다.

### 7.2 검증 목표

- 1시간 window / 1시간 또는 30분 stride에서 window 목록이 의도대로 생성되는지 확인한다.
- 20분 window / 15분 또는 30분 stride는 burst 민감도 비교용으로만 확인한다.
- recurring 운영에서는 partial final window를 기본 생성하지 않는 방향을 검토한다.
- historical 검증에서는 partial final window 포함 여부를 별도 비교한다.
- `export_db_logs_cli.py --start/--end`로 window별 export JSON을 생성할 수 있는지 확인한다.
- prepare-only artifact를 `runs/`가 아니라 `data/windowed/`에 저장할 수 있는지 확인한다.
- prepare/scoring/filtering 변경 없이 candidate/context/policy distribution shape가 유지되는지 확인한다.

### 7.3 검증에서 제외하는 항목

- stage1 live LLM 호출
- stage2 report 생성
- window마다 full pipeline 실행
- window마다 `runs/` 생성
- multi-window rollup 구현
- cron/systemd production 등록
- Web UI timeline view
- overlap 자동 dedup
- cleanup 실제 삭제
- prepare/scoring/filtering 변경

### 7.4 1차 dry-run 범위

1차 검증은 historical 1~2시간 범위로 제한한다.

```text
primary prepare window: 1시간
primary stride:         1시간 또는 30분
comparison window:      20분
comparison stride:      30분 또는 15분
mode:                   planner dry-run -> 일부 prepare smoke
stage1:                 실행하지 않음
stage2:                 실행하지 않음
viewer:                 생성하지 않음
```

초기 planner dry-run은 새 scheduler의 `planner` mode로 검증한다.

```bash
python3 src/sliding_window_scheduler.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-23 09:00:00" \
  --analysis-end "2026-05-23 11:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --mode planner
```

초기 prepare smoke는 scheduler가 `data/windowed/` layout을 직접 생성하는 방식으로 검증한다.

```bash
python3 src/sliding_window_scheduler.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-23 09:00:00" \
  --analysis-end "2026-05-23 11:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --window-output-root data/windowed \
  --mode prepare
```

`run_analysis_pipeline.py --stop-after prepare --processed-dir ... --reports-dir ...` 방식은 호환성 smoke test로만 둔다. scheduler 운영 기본 구조는 `export_db_logs_cli.py`와 `prepare_llm_input.py` 직접 호출을 우선 검토한다.

### 7.5 확인 항목

- 생성된 window 개수
- 각 window start/end 시각
- partial final window 포함 여부
- export JSON 생성 여부
- prepare artifact 생성 여부
- `data/windowed/` layout 적합성
- candidate_count
- policy class distribution
- context summary 생성 여부
- overlap 구간 중복 request_id 존재 여부
- `runs/`가 생성되지 않는지 여부
- rollup 입력으로 필요한 추가 summary artifact 목록

### 7.6 CLI 변경 판단 기준

dry-run 결과를 본 뒤에만 CLI 변경을 검토한다.

초기 구현은 `sliding_window_scheduler.py` 전용 옵션으로 제한한다. `run_analysis_pipeline.py`에는 window layout 전용 옵션을 추가하지 않는다.

후보:

```text
--window-minutes
--stride-minutes
--analysis-start
--analysis-end
--lookback-hours
--prepare-only
--include-partial-final
--window-output-root
--rollup-output-root
--skip-existing-complete
```

### 7.7 Planner 구현 및 검증 결과

`src/sliding_window_scheduler.py`의 Phase 1 planner mode를 추가했다.

구현 범위:

- window 목록 계산
- `data/windowed/<date>/<window_id>/` 경로 계산
- `data/rollups` root 경로 계산
- full window only 기본 정책
- `--include-partial-final` 지정 시 마지막 partial window 포함
- text / JSON 출력 지원
- `mode=export`, `mode=prepare`는 예약만 하고 아직 실행하지 않음
- `runs/` 디렉터리 생성 없음

검증 결과:

```text
python3 -m py_compile src/sliding_window_scheduler.py
python3 -m pytest -q tests/test_sliding_window_scheduler.py
# 5 passed

python3 -m pytest -q \
  tests/test_sliding_window_scheduler.py \
  tests/test_explain_prepare_candidates.py \
  tests/test_prepare_status_error_only_candidate_policy.py \
  tests/test_prepare_scanner_probe_candidate_policy.py
# 29 passed
```

확인된 동작:

- 1시간 window / 1시간 stride / 2시간 범위는 2개 window를 생성한다.
- 20분 window / 15분 stride / 2시간 범위는 partial final 제외 시 7개 window를 생성한다.
- `--include-partial-final`을 주면 8번째 partial window `sw_1045_1100`을 생성한다.
- window artifact 경로는 `data/windowed/YYYY-MM-DD/sw_HHMM_HHMM/` 형태로 계산된다.
- planner output에는 `runs/` 경로가 포함되지 않는다.

다음 단계는 Level 1 export smoke 구현 여부를 판단하는 것이다. Level 1에서는 일부 window에 대해 `export.json`만 생성하고, prepare/stage1/stage2는 계속 제외한다.

## 8. 구현 전 보류 항목

아래는 바로 구현하지 않는다.

- prepare 내부 chunking
- prepare scoring/filtering 변경
- window마다 full pipeline을 자동 실행하는 운영 구조 확정
- window마다 `runs/`를 생성하는 구조 확정
- `run_analysis_pipeline.py`에 window layout 전용 옵션을 추가하는 변경
- stage2 report를 여러 window로 나눈 뒤 자동 병합하는 기능
- overlap 자동 dedup으로 verdict/category/severity를 바꾸는 기능
- Web UI timeline view
- remoteIP 연동
- output cleanup 실제 삭제
- cron/systemd production 등록

## 9. Apache logs-only guardrail

Sliding Window는 실행 단위와 비용/토큰 제어를 위한 운영 전략이다. 다음을 바꾸지 않는다.

- `status_code=200`으로 공격 성공/침해 성공 단정 금지
- `status_code=403/404/500/503`만으로 취약점/공격 성공/침해 단정 금지
- `response_body_bytes`, `resp_content_type`, `text/html`로 파일 노출/정보 유출 단정 금지
- POST metadata만으로 로그인 성공/업로드 저장 성공 단정 금지
- raw POST body, response body, DB 결과, browser execution 추론 금지
- context-only를 finding/incident로 승격 금지
- Web UI에서 severity/category/verdict 재계산 금지
- prepare/scoring/filtering 변경 금지

## 10. 0523 권장 작업 순서

1. 팀원 문서 4개를 repo 경로로 편입할지, 요약 review 문서만 유지할지 결정한다.
2. 현재 CLI와 문서 예시 명령어의 옵션명을 대조한다.
3. `sliding_window_scheduler.py` 구현 전 dry-run 설계만 확정한다.
4. prepare-only window mode와 multi-window rollup artifact 필요성을 먼저 검토한다.
5. `data/windowed/`와 `data/rollups/` artifact layout을 검증한다.
6. scheduler가 window/rollup layout ownership을 갖는 구조를 우선 검토한다.
7. planner mode 검증 결과를 기준으로 Level 1 export smoke 구현 여부를 판단한다.
8. token/cost 문서는 실제 모델 단가와 현재 run artifact 기준으로 재측정할 항목을 표시한다.

## 11. 현재 결론

Sliding Window 문서 세트는 운영 자동화/토큰 제어 관점에서 유효하다.

다만 window마다 full pipeline을 실행하거나 window마다 `runs/`를 생성하는 구조로 확정하지 않는다. 0523에는 다음을 완료/확인했다.

```text
- 문서 intake
- CLI 옵션 호환성 확인
- dry-run 검증 범위 확정
- prepare-only window mode 검토
- scheduler의 data/windowed / data/rollups artifact layout ownership 검토
- sliding_window_scheduler.py planner mode 구현
- planner path/window count pytest 검증
- prepare/scoring/filtering 변경 없음 확인
```

다음 판단 대상은 Level 1 export smoke 구현이다.
