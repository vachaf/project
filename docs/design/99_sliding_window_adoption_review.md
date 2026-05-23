# 99_sliding_window_adoption_review

- 문서 상태: 팀원 작성 Sliding Window 문서 intake / adoption review
- 기준 시점: 2026-05-23
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

## 1. 현재 결론

Sliding Window 문서 세트는 운영 자동화와 token/cost control 관점에서 유효하다.

다만 window마다 full pipeline을 실행하거나 window마다 `runs/`를 생성하는 구조로 확정하지 않는다.

0523 기준 완료/확인:

```text
- 문서 intake
- CLI 옵션 호환성 확인
- dry-run 검증 범위 확정
- prepare-only window mode 검토
- scheduler의 data/windowed / data/rollups artifact layout ownership 검토
- sliding_window_scheduler.py planner mode 구현
- planner path/window count pytest 검증
- sliding_window_scheduler.py export mode 구현
- export artifact shape / skip policy / runs 미생성 smoke 검증
- prepare/scoring/filtering 변경 없음 확인
```

다음 판단 대상은 Level 2 prepare smoke 구현이다.

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

수용 가능한 scheduler ownership:

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

장점:

- prepare 내부 집계 로직을 건드리지 않는다.
- candidate policy를 변경하지 않는다.
- stage1/stage2 prompt나 report semantics를 변경하지 않는다.
- window별 중간 산출물과 Web UI report run의 의미를 분리한다.
- 하루치 window 수가 많아져도 `runs/`와 Web UI list가 폭증하지 않는다.
- 운영 scheduler가 `--processed-dir`, `--reports-dir`, `--run-dir` 조합을 매번 수동으로 맞추는 구조를 피한다.

## 3. 실행 단위 재검토

Sliding Window는 window마다 full pipeline을 실행하는 구조로 확정하지 않는다.

초기 수용 범위는 export 단계 windowing과 prepare-only window artifact 생성 가능성 검토로 제한한다. Stage1/Stage2는 window별 실행이 아니라 multi-window rollup 단위 실행을 우선 검토한다.

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
      prepared/

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

## 5. CLI boundary

운영 구조에서는 `run_analysis_pipeline.py` 옵션을 매 window마다 조합하는 방식에 의존하지 않는다.

판단 기준:

- `run_analysis_pipeline.py`는 export JSON에서 prepare -> stage1 -> stage2 -> viewer_payload로 이어지는 one-shot 실행기 또는 resume 실행기로 유지한다.
- `sliding_window_scheduler.py`는 window 생성, export 실행, prepare-only artifact layout, window summary 생성, rollup 입력 생성을 담당한다.
- prepare-only window에서는 `run_analysis_pipeline.py --run-dir`를 사용하지 않는다.
- prepare-only window에서는 `runs/`를 만들지 않는다.
- rollup 이후 Stage1/Stage2 report를 생성할 때만 `run_analysis_pipeline.py` 또는 stage1/stage2 wrapper를 사용해 `runs/<rollup_run_id>/`를 만든다.

운영 scheduler의 window prepare 기본 후보는 `prepare_llm_input.py` 직접 호출이다.

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

`run_analysis_pipeline.py --stop-after prepare --processed-dir ... --reports-dir ...` 방식은 smoke test 또는 호환성 검증에는 사용할 수 있다. 그러나 scheduler 운영 기본 구조로 확정하지 않는다.

## 6. CLI 호환성 검토 결과

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

## 7. 검증 범위와 결과

### 7.1 Level 구분

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
- stage1/stage2 실행 없음
- runs/가 아니라 data/windowed/<date>/<window_id>/에 저장
```

초기 검증은 Level 0부터 시작하고, 그 다음 일부 window에 대해서만 Level 1 export smoke를 수행했다. 하루치 전체 window를 처음부터 모두 export/prepare하지 않는다.

### 7.2 Level 0 planner 구현 및 검증 결과

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

확인된 동작:

- 1시간 window / 1시간 stride / 2시간 범위는 2개 window를 생성한다.
- 20분 window / 15분 stride / 2시간 범위는 partial final 제외 시 7개 window를 생성한다.
- `--include-partial-final`을 주면 8번째 partial window `sw_1045_1100`을 생성한다.
- window artifact 경로는 `data/windowed/YYYY-MM-DD/sw_HHMM_HHMM/` 형태로 계산된다.
- planner output에는 `runs/` 경로가 포함되지 않는다.

### 7.3 Level 1 export mode 구현 및 검증 결과

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
python3 src/sliding_window_scheduler.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-23 09:00:00" \
  --analysis-end "2026-05-23 10:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --mode export \
  --table security \
  --export-pretty

[SW] export summary: exported=1 skipped_existing=0 failed=0
```

생성된 artifact:

```text
data/windowed/2026-05-23/sw_0900_1000/export.json
```

payload shape 확인:

```text
meta.table_option = security
meta.start        = 2026-05-23T09:00:00.000+09:00
meta.end_exclusive= 2026-05-23T10:00:00.000+09:00
counts            = {'access': 0, 'security': 0, 'error': 0}
[OK] export payload shape is valid
```

skip 정책 확인:

```text
[SW] export skip existing: data/windowed/2026-05-23/sw_0900_1000/export.json
[SW] export summary: exported=0 skipped_existing=1 failed=0
```

`runs/sw_*` 디렉터리는 생성되지 않았다.

테스트 결과:

```text
python3 -m py_compile src/sliding_window_scheduler.py
python3 -m pytest -q tests/test_sliding_window_scheduler.py
# 8 passed

python3 -m pytest -q \
  tests/test_sliding_window_scheduler.py \
  tests/test_explain_prepare_candidates.py \
  tests/test_prepare_status_error_only_candidate_policy.py \
  tests/test_prepare_scanner_probe_candidate_policy.py
# 32 passed
```

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

## 10. 다음 판단 대상

다음 단계는 Level 2 prepare smoke 구현 여부 판단이다.

Level 2 후보 범위:

```text
- 일부 window의 export.json을 입력으로 prepare_llm_input.py 실행
- data/windowed/<date>/<window_id>/prepared/에 원본 prepare 산출물 저장
- window root에 llm_input.json / analysis_candidates.json / noise_summary.json 정규화 복사 또는 링크
- window_summary.json 생성 후보 검토
- stage1/stage2/viewer_payload 실행 없음
- runs/ 생성 없음
- prepare/scoring/filtering 변경 없음
```
