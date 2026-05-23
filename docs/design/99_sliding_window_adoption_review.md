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
export 단계에서 짧은 시간 window로 나누어 각 window를 독립 run_dir로 실행한다.
```

현재 기준 판단:

- Sliding Window 도입 위치는 prepare 내부가 아니라 export/scheduler 단계가 적절하다.
- `export_db_logs_cli.py --start/--end` 인터페이스를 활용하면 기존 prepare/stage1/stage2/viewer_payload 로직 변경을 최소화할 수 있다.
- window 단위 run은 기존 `runs/*/manifest.json` 기반 Web UI list 구조와 대체로 호환될 가능성이 높다.

## 2. 우선 수용 가능한 방향

### 2.1 export 단계 scheduler 접근

수용 가능성이 높은 구조:

```text
scheduler
  -> export_db_logs_cli.py --start <window_start> --end <window_end>
  -> run_analysis_pipeline.py --export-input <window_export.json> --run-dir runs/sw_<...>
```

이 방식은 다음 장점이 있다.

- prepare 내부 집계 로직을 건드리지 않는다.
- candidate policy를 변경하지 않는다.
- stage1/stage2 prompt나 report semantics를 변경하지 않는다.
- window별 run_dir와 manifest를 통해 재현성과 추적성을 유지할 수 있다.

### 2.2 초기 운영 후보값

팀원 문서의 제안값은 검토 가치가 있다.

```text
window_size: 20분
stride:      15분 또는 30분
overlap:     5분 또는 상황별 조정
```

다만 현재 repo에 바로 고정하지 않고 dry-run으로 검증한다.

초기 권장 판단:

- 기능 검증: `window_size=20분`, `stride=30분`
- overlap 민감도 검증: `window_size=20분`, `stride=15분`
- 비용 우선 운영안은 token/cost 실측 후 결정

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

1. Short window prepare
   - 20분 window
   - 15분 또는 30분 stride
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

4. Daily summary
   - raw log 전체 재분석이 아니라 rollup/stage2 결과 요약

## 4. 반드시 검증할 항목

### 4.1 CLI 호환성

문서 예시가 현재 repo의 실제 CLI 옵션과 맞는지 확인한다.

확인 대상:

- `src/export_db_logs_cli.py`
- `src/run_analysis_pipeline.py`
- `src/llm_stage1_classifier.py`
- `src/llm_stage2_reporter.py`

특히 다음 옵션은 실제 존재 여부와 이름을 확인해야 한다.

- `--run-dir`
- `--work-dir`
- `--export-input`
- `--llm-provider` 또는 provider 관련 옵션명
- `--mode`
- `--dry-run`
- `--stop-after`
- `--stage1-candidate-limit`
- stage2 top-N 관련 옵션명

문서 예시와 실제 CLI가 다르면 문서를 먼저 정정하고, 구현은 그 다음에 진행한다.

### 4.2 CLI 옵션 호환성 검토 결과

현재 repo 기준으로 Sliding Window 문서 예시 명령은 대부분 호환된다. 다만 direct CLI와 pipeline wrapper CLI의 옵션명을 분리해서 문서화해야 한다.

#### 4.2.1 호환되는 항목

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

`run_analysis_pipeline.py`는 window export JSON을 받아 run_dir 단위로 실행하는 wrapper 옵션과 호환된다.

```text
--export-input
--work-dir
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

#### 4.2.2 수정이 필요한 문서 예시

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

#### 4.2.3 dry-run window count 주의

20분 window / 15분 stride / 2시간 범위는 기존 문서 예시처럼 6개 window가 아니다.

```text
partial final window 포함 시: 8개
full window만 허용 시:      7개
```

따라서 scheduler 설계 전 `partial final window`를 만들지 여부를 명시해야 한다. recurring 운영 기본값은 full window only가 더 안전하며, historical 검증에서만 partial final window 포함 여부를 별도 옵션으로 비교한다.

#### 4.2.4 현재 판단

CLI 옵션은 scheduler dry-run 설계로 진행할 수 있을 정도로 대체로 호환된다. 단, 팀원 작성 문서 4개를 그대로 편입할 경우 위 옵션명 차이와 window count 예시는 먼저 정정해야 한다.

### 4.3 prepare 내부 time window와 export window 관계

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

- export window는 최소 5분보다 커야 한다.
- 현실적 하한은 10분 이상으로 둔다.
- 기본 검증값은 20분으로 둔다.

### 4.4 overlap 중복 처리

5분 overlap을 두면 동일 request가 두 window에 들어갈 수 있다.

초기 방침:

- pipeline 결과를 자동 dedup하지 않는다.
- 각 window run을 독립 run_dir로 유지한다.
- 중복 request_id 확인은 diagnostic script 또는 수동 검토로만 둔다.
- dedup 결과를 Web UI verdict/severity/category에 반영하지 않는다.

### 4.5 Web UI run list 증가

15분 stride면 하루 최대 96개 run이 생길 수 있다.

검토 항목:

- run list 필터로 충분한가
- `sw_YYYYMMDD_HHMM_<hash>` run_id가 사용성에 적절한가
- retention/cleanup 정책이 필요한가
- output cleanup script는 여전히 별도 승인 전까지 실제 삭제를 보류한다.

### 4.6 token/cost 실측

`token_cost_estimation.md`는 근사치 문서로 보고, 실제 운영 전에는 현재 모델 단가와 실제 run artifact 기반으로 재측정한다.

확인 항목:

- stage1 candidate 1건당 실제 input/output token
- stage2 report 1회당 실제 input/output token
- 20분 window의 평균 candidate 수
- 15분/30분/60분 stride별 일·월 비용
- Anthropic `max_tokens` truncation 재발 여부

## 5. 구현 전 보류 항목

아래는 바로 구현하지 않는다.

- prepare 내부 chunking
- prepare scoring/filtering 변경
- window마다 full pipeline을 자동 실행하는 운영 구조 확정
- stage2 report를 여러 window로 나눈 뒤 자동 병합하는 기능
- overlap 자동 dedup으로 verdict/category/severity를 바꾸는 기능
- Web UI timeline view
- remoteIP 연동
- output cleanup 실제 삭제
- cron/systemd production 등록

## 6. Apache logs-only guardrail

Sliding Window는 실행 단위와 비용/토큰 제어를 위한 운영 전략이다. 다음을 바꾸지 않는다.

- `status_code=200`으로 공격 성공/침해 성공 단정 금지
- `status_code=403/404/500/503`만으로 취약점/공격 성공/침해 단정 금지
- `response_body_bytes`, `resp_content_type`, `text/html`로 파일 노출/정보 유출 단정 금지
- POST metadata만으로 로그인 성공/업로드 저장 성공 단정 금지
- raw POST body, response body, DB 결과, browser execution 추론 금지
- context-only를 finding/incident로 승격 금지
- Web UI에서 severity/category/verdict 재계산 금지
- prepare/scoring/filtering 변경 금지

## 7. 0523 권장 작업 순서

1. 팀원 문서 4개를 repo 경로로 편입할지, 요약 review 문서만 유지할지 결정한다.
2. 현재 CLI와 문서 예시 명령어의 옵션명을 대조한다.
3. `sliding_window_scheduler.py` 구현 전 dry-run 설계만 확정한다.
4. prepare-only window mode와 multi-window rollup artifact 필요성을 먼저 검토한다.
5. historical export 1~2시간 범위로 window 목록만 생성하는 dry-run 검증 계획을 작성한다.
6. token/cost 문서는 실제 모델 단가와 현재 run artifact 기준으로 재측정할 항목을 표시한다.

## 8. 현재 결론

Sliding Window 문서 세트는 운영 자동화/토큰 제어 관점에서 유효하다.

다만 window마다 full pipeline을 실행하는 구조로 확정하지 않는다. 0523에는 다음까지만 진행한다.

```text
- 문서 intake
- CLI 옵션 호환성 확인
- dry-run 검증 범위 확정
- prepare-only window mode 검토
- multi-window rollup 입력/summary artifact 필요성 검토
- prepare/scoring/filtering 변경 없음 확인
```

그 다음에만 최소 scheduler 구현 여부를 판단한다.
