# 99_sliding_window_adoption_review

- 문서 상태: 팀원 작성 Sliding Window 문서 intake / adoption review
- 기준 시점: 2026-05-24
- 목적: Sliding Window 문서 세트를 현재 Apache logs-only LLM pipeline 기준으로 수용할 범위, 검증 항목, 보류 항목을 정리한다.

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

## 1. 현재 결론

Sliding Window 문서 세트는 운영 자동화와 token/cost control 관점에서 유효하다.

다만 window마다 full pipeline을 실행하거나 window마다 `runs/`를 생성하는 구조로 확정하지 않는다.

0524 기준 완료/확인:

```text
- 문서 intake
- CLI 옵션 호환성 확인
- dry-run 검증 범위 확정
- prepare-only window mode 검토
- scheduler의 data/windowed / data/rollups artifact layout ownership 검토
- sliding_window_scheduler.py planner mode 구현
- sliding_window_scheduler.py export mode 구현
- prepare_llm_input.py --flat-output-names 추가
- sliding_window_scheduler.py prepare mode 구현
- sliding_window_summary.py window_summary.json v1 builder 추가
- scheduler prepare mode에서 window_summary.json 자동 생성 연결
- Level 0 planner / Level 1 export / Level 2 prepare smoke 통과
- window_summary.json v1 smoke 및 unit test 통과
- prepare/scoring/filtering 변경 없음 확인
```

다음 판단 대상은 multi-window rollup input 포맷, request_id dedup 기준, src_ip/uri/payload family 장기 aggregation 기준이다.

## 2. 수용 방향

Sliding Window는 prepare/scoring/filtering 변경 제안이 아니라 운영 자동화와 token/cost control을 위한 설계 패키지로 본다.

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
- `runs/`는 Stage2 report와 `viewer_payload.json`이 생성되는 rollup/report 단위에 한정한다.
- prepare/scoring/filtering 변경은 하지 않는다.

현재 scheduler ownership:

```text
sliding_window_scheduler.py
  -> window 목록 생성
  -> data/windowed/<date>/<window_id>/ 경로 결정
  -> export_db_logs_cli.py --start <window_start> --end <window_end> --out <window_dir>/export.json
  -> prepare_llm_input.py --input <window_dir>/export.json --out-dir <window_dir> --flat-output-names
  -> sliding_window_summary.py로 window_summary.json 생성
  -> data/rollups/<date>/<rollup_id>/ rollup 입력 생성 후보
  -> rollup 단위 Stage1/Stage2 실행 시에만 runs/<rollup_run_id>/ 생성
```

장점:

- prepare 내부 집계 로직을 건드리지 않는다.
- candidate policy를 변경하지 않는다.
- stage1/stage2 prompt나 report semantics를 변경하지 않는다.
- window별 중간 산출물과 Web UI report run의 의미를 분리한다.
- 하루치 window 수가 많아져도 `runs/`와 Web UI list가 폭증하지 않는다.
- 운영 scheduler가 `--processed-dir`, `--reports-dir`, `--run-dir` 조합을 매번 수동으로 맞추는 구조를 피한다.
- `prepared/` 하위 디렉터리에 생성한 뒤 복사/링크하는 중간 단계를 피한다.

## 3. 실행 단위 재검토

Sliding Window는 window마다 full pipeline을 실행하는 구조로 확정하지 않는다.

초기 수용 범위는 export 단계 windowing과 prepare-only window artifact 생성으로 제한한다. Stage1/Stage2는 window별 실행이 아니라 multi-window rollup 단위 실행을 우선 검토한다.

이 판단의 이유는 다음과 같다.

- 20분 window / 15분 stride / 5분 overlap은 scanner burst, sqlmap burst, 짧은 auth 반복 같은 단기 집중 패턴에는 유효하다.
- 그러나 1~4시간에 걸쳐 느리게 진행되는 low-and-slow probe나 campaign은 window별로 보면 단발 이벤트처럼 약화될 수 있다.
- window마다 stage2 report를 생성하면 하루 최대 수십~수백 개 report가 생겨 Web UI list, 운영자 검토, 중복 incident, 비용 측면에서 부담이 커진다.
- prepare는 Python 단계이므로 LLM token 비용 관점에서는 반드시 짧게 잘라야 하는 단계는 아니지만, export 크기, 실행 시간, artifact 재현성, burst 단위 관찰을 위해 windowing의 가치는 있다.
- 따라서 prepare window 결과를 다시 묶는 multi-window rollup artifact가 필요하다.

권장 구조:

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

권장 layout:

```text
data/windowed/
  2026-05-24/
    sw_0200_0300/
      export.json
      llm_input.json
      analysis_candidates.json
      noise_summary.json
      window_summary.json

data/rollups/
  2026-05-24/
    rollup_0200_0600/
      rollup_input.json
      dedup_candidates.json
      rollup_summary.json

runs/
  rollup_20260524_0200_0600/
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
| `data/windowed/` | window별 export/prepare/summary 중간 산출물 | 노출하지 않음 |
| `data/rollups/` | multi-window rollup 입력/요약 산출물 | 노출하지 않음 |
| `runs/` | Stage2 report와 viewer_payload가 있는 report run | 노출 가능 |

## 5. CLI boundary

운영 구조에서는 `run_analysis_pipeline.py` 옵션을 매 window마다 조합하는 방식에 의존하지 않는다.

판단 기준:

- `run_analysis_pipeline.py`는 export JSON에서 prepare -> stage1 -> stage2 -> viewer_payload로 이어지는 one-shot 실행기 또는 resume 실행기로 유지한다.
- `sliding_window_scheduler.py`는 window 생성, export 실행, prepare-only artifact layout, window summary 생성, rollup 입력 생성을 담당한다.
- prepare-only window에서는 `run_analysis_pipeline.py --run-dir`를 사용하지 않는다.
- prepare-only window에서는 `runs/`를 만들지 않는다.
- rollup 이후 Stage1/Stage2 report를 생성할 때만 `run_analysis_pipeline.py` 또는 stage1/stage2 wrapper를 사용해 `runs/<rollup_run_id>/`를 만든다.

운영 scheduler의 window prepare 호출은 다음 형태를 기준으로 한다.

```text
export_db_logs_cli.py
  --start <window_start>
  --end <window_end>
  --table security
  --out data/windowed/<date>/<window_id>/export.json

prepare_llm_input.py
  --input data/windowed/<date>/<window_id>/export.json
  --out-dir data/windowed/<date>/<window_id>
  --flat-output-names
```

`--flat-output-names`는 기존 prepare/scoring/filtering 의미를 바꾸지 않고 파일명만 다음처럼 평탄화한다.

```text
llm_input.json
analysis_candidates.json
noise_summary.json
filtered_out_rows.json  # --write-filtered-out 사용 시
```

기존 기본 출력명 규칙은 호환성을 위해 유지한다.

```text
<base>_llm_input.json
<base>_analysis_candidates.json
<base>_noise_summary.json
```

`--flat-output-names`와 `--base-name`은 함께 쓰지 않는다.

`window_summary.json`은 prepare/scoring/filtering을 변경하지 않고 기존 export/prepare 산출물을 읽어서 만드는 후처리 artifact다.

## 6. window_summary.json v1

`window_summary.json`은 새 보안 판단 파일이 아니라 rollup이 빠르게 읽을 수 있는 summary-only index artifact다.

생성 위치:

```text
data/windowed/<date>/<window_id>/window_summary.json
```

생성 기준:

- `--mode prepare` 성공 후 자동 생성한다.
- prepare output 3종이 이미 있어서 `skipped_existing`인 경우에도 `window_summary.json`이 없으면 생성한다.
- `window_summary.json`이 이미 있고 `--overwrite`가 없으면 유지한다.
- 저장된 `window_summary.json` 안에서는 `artifact_status.window_summary.exists=true`로 표시한다.

포맷 핵심 필드:

```text
schema: sliding_window_summary_v1
window: window_id/start/end_exclusive/timezone/duration_minutes/is_partial
artifact_status: export/llm_input/analysis_candidates/noise_summary/window_summary 존재 여부
source: database/table_option/selected_source_tables/analysis_primary_table
counts.export: access/security/error/total
counts.prepare: total_exported_rows, selected_source_rows, filtered_out_rows, candidate_rows, distinct_incident_candidates, noise_group_count, supporting_events, context_summary_count 등
distributions: candidate_status_code, candidate_method, candidate_verdict_hint, candidate_src_ip, candidate_uri, candidate_reason_hint_prefix, filtered_out_breakdown
candidate_index: request_id/src_ip/method/uri/status_code/score/verdict_hint/reason_hint_prefixes
rollup_hints: has_candidates/has_noise_groups/has_supporting_events/has_context_summaries/candidate_request_ids
guardrails: summary_only, no_new_security_verdict, no_success_inference, no_body_inference, no_context_promotion
```

`candidate_index`는 rollup dedup을 위한 최소 index만 포함한다. `raw_log`, `raw_request`, `user_agent`, `referer`는 복제하지 않는다.

v1에서 제외하는 항목:

- severity
- category
- final verdict
- attack success 여부
- exploit success 여부
- data exposure 여부
- account takeover 여부
- upload saved 여부
- low_and_slow_candidate 여부
- policy_distribution 재계산

특히 `policy_distribution`은 아직 넣지 않는다. 현재 candidate artifact에 정식 policy bucket 필드가 없으므로 summary generator가 policy bucket을 재계산하면 prepare policy 이중 구현이 된다.

## 7. CLI 호환성 검토 결과

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

주의할 문서 예시:

- `llm_stage1_classifier.py` 직접 실행은 `--llm-input`이 아니라 `--input`을 사용한다.
- direct Stage2 CLI는 `--top-incidents`, `--top-noise-groups`, `--top-ips`를 사용한다.
- pipeline wrapper는 `--stage2-top-incidents`, `--stage2-top-noise-groups`, `--stage2-top-ips`를 사용한다.

window count 주의:

```text
20분 window / 15분 stride / 2시간 범위
- partial final window 포함 시: 8개
- full window만 허용 시:      7개
```

recurring 운영 기본값은 full window only가 더 안전하며, historical 검증에서만 partial final window 포함 여부를 별도 옵션으로 비교한다.

## 8. 검증 범위와 결과

### 8.1 Level 구분

```text
Level 0. planner dry-run
- window 목록만 출력
- DB 조회 없음
- 파일 생성 없음

Level 1. export smoke
- 일부 window만 export JSON 생성
- prepare 실행 없음
- 저장 위치는 data/windowed/<date>/<window_id>/

Level 2. prepare smoke
- 일부 window에 대해 export + prepare 실행
- window_summary.json 생성
- stage1/stage2 실행 없음
- runs/가 아니라 data/windowed/<date>/<window_id>/에 저장
```

### 8.2 Level 0 planner 구현 및 검증 결과

`src/sliding_window_scheduler.py`의 planner mode를 추가했다.

구현 범위:

- window 목록 계산
- `data/windowed/<date>/<window_id>/` 경로 계산
- `data/rollups` root 경로 계산
- full window only 기본 정책
- `--include-partial-final` 지정 시 마지막 partial window 포함
- text / JSON 출력 지원
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

### 8.3 Level 1 export mode 구현 및 검증 결과

`src/sliding_window_scheduler.py --mode export`를 추가했다.

구현 범위:

- planner가 계산한 각 window에 대해 `data/windowed/<date>/<window_id>/export.json` 생성
- 내부적으로 `export_db_logs_cli.py` 호출
- `--table access|security|error|all` 지원
- `--limit` 지원
- `--export-pretty` 지원
- 기존 `export.json`이 있으면 기본 skip
- `--overwrite` 지정 시 재생성
- `--keep-going` 지정 시 실패 후 다음 window 계속 처리
- prepare/stage1/stage2 실행 없음
- `runs/` 생성 없음

수동 smoke 결과:

```text
[SW] export summary: exported=1 skipped_existing=0 failed=0
```

### 8.4 flat prepare output names 구현 및 검증 결과

`src/prepare_llm_input.py`에 opt-in `--flat-output-names`를 추가했다.

구현 범위:

- 기존 기본 출력명 규칙은 유지한다.
- `--flat-output-names` 지정 시 window root에 표준 파일명으로 출력한다.
- `--base-name`과 `--flat-output-names`는 argparse 상호배타로 막는다.
- 출력 파일명만 바꾸며 prepare/scoring/filtering 의미는 바꾸지 않는다.

검증 결과:

```text
python3 -m py_compile src/prepare_llm_input.py
python3 -m pytest -q tests/test_prepare_llm_input_output_names.py
# 4 passed

python3 scripts/check_prepare_regression.py --strict
# pass=25 warn=0 fail=0

python3 scripts/check_stage_dryrun_regression.py --strict
# pass=19 warn=0 fail=0
```

### 8.5 Level 2 prepare mode 구현 및 검증 결과

`src/sliding_window_scheduler.py --mode prepare`를 추가했다.

구현 범위:

- window별 `export.json` 존재 확인
- `prepare_llm_input.py --flat-output-names` 호출
- `--out-dir`은 window root로 지정
- `llm_input.json`, `analysis_candidates.json`, `noise_summary.json` 생성 확인
- `window_summary.json` 생성
- stage1/stage2/viewer_payload 실행 없음
- `runs/` 생성 없음

보수적 상태 정책:

```text
export.json 없음
  -> missing_export, 기본 stop

output 3종 모두 이미 있음
  -> skipped_existing

output 일부만 있음
  -> partial_existing, 기본 stop

prepare 실행 성공 후 output 누락
  -> missing_output

window_summary.json 생성 실패
  -> summary_failed

--overwrite
  -> 기존 output과 summary가 있어도 재실행 허용

--keep-going
  -> 실패 후 다음 window 계속 처리
```

테스트 결과:

```text
python3 -m py_compile src/sliding_window_summary.py src/sliding_window_scheduler.py
python3 -m pytest -q \
  tests/test_sliding_window_summary.py \
  tests/test_sliding_window_scheduler_summary.py \
  tests/test_sliding_window_scheduler.py
# 18 passed

python3 -m pytest -q \
  tests/test_sliding_window_summary.py \
  tests/test_sliding_window_scheduler_summary.py \
  tests/test_sliding_window_scheduler.py \
  tests/test_prepare_llm_input_output_names.py \
  tests/test_explain_prepare_candidates.py \
  tests/test_prepare_status_error_only_candidate_policy.py \
  tests/test_prepare_scanner_probe_candidate_policy.py
# 46 passed
```

수동 1-window smoke 결과:

```text
--mode export
[SW] export summary: exported=1 skipped_existing=0 failed=0

--mode prepare --overwrite
[SW] prepare summary: prepared=1 skipped_existing=0 missing_export=0 partial_existing=0 missing_output=0 summary_failed=0 summary_written=1 failed=0
```

생성된 window root artifact:

```text
data/windowed/2026-05-24/sw_0200_0300/analysis_candidates.json
data/windowed/2026-05-24/sw_0200_0300/export.json
data/windowed/2026-05-24/sw_0200_0300/llm_input.json
data/windowed/2026-05-24/sw_0200_0300/noise_summary.json
data/windowed/2026-05-24/sw_0200_0300/window_summary.json
```

`artifact_status.window_summary.exists=true` 확인 완료.

## 9. 구현 전 보류 항목

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

## 10. Apache logs-only guardrail

Sliding Window는 실행 단위와 비용/토큰 제어를 위한 운영 전략이다. 다음을 바꾸지 않는다.

- `status_code=200`으로 공격 성공/침해 성공 단정 금지
- `status_code=403/404/500/503`만으로 취약점/공격 성공/침해 단정 금지
- `response_body_bytes`, `resp_content_type`, `text/html`로 파일 노출/정보 유출 단정 금지
- POST metadata만으로 로그인 성공/업로드 저장 성공 단정 금지
- raw POST body, response body, DB 결과, browser execution 추론 금지
- context-only를 finding/incident로 승격 금지
- Web UI에서 severity/category/verdict 재계산 금지
- prepare/scoring/filtering 변경 금지

## 11. 다음 판단 대상

다음 단계는 multi-window rollup input 포맷 설계다.

후보 범위:

```text
- rollup 대상 window_summary.json 목록 수집
- request_id dedup 기준
- candidate_index merge 기준
- src_ip / uri family / reason_hint_prefix 장기 aggregation 기준
- low-and-slow 후보는 단일 window가 아니라 rollup 단계에서만 후보화
- stage1/stage2/viewer_payload 실행 없음
- runs/ 생성 없음
- prepare/scoring/filtering 변경 없음
```
