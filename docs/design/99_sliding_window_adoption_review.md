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

## 3. 반드시 검증할 항목

### 3.1 CLI 호환성

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

### 3.2 prepare 내부 time window와 export window 관계

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

### 3.3 overlap 중복 처리

5분 overlap을 두면 동일 request가 두 window에 들어갈 수 있다.

초기 방침:

- pipeline 결과를 자동 dedup하지 않는다.
- 각 window run을 독립 run_dir로 유지한다.
- 중복 request_id 확인은 diagnostic script 또는 수동 검토로만 둔다.
- dedup 결과를 Web UI verdict/severity/category에 반영하지 않는다.

### 3.4 Web UI run list 증가

15분 stride면 하루 최대 96개 run이 생길 수 있다.

검토 항목:

- run list 필터로 충분한가
- `sw_YYYYMMDD_HHMM_<hash>` run_id가 사용성에 적절한가
- retention/cleanup 정책이 필요한가
- output cleanup script는 여전히 별도 승인 전까지 실제 삭제를 보류한다.

### 3.5 token/cost 실측

`token_cost_estimation.md`는 근사치 문서로 보고, 실제 운영 전에는 현재 모델 단가와 실제 run artifact 기반으로 재측정한다.

확인 항목:

- stage1 candidate 1건당 실제 input/output token
- stage2 report 1회당 실제 input/output token
- 20분 window의 평균 candidate 수
- 15분/30분/60분 stride별 일·월 비용
- Anthropic `max_tokens` truncation 재발 여부

## 4. 구현 전 보류 항목

아래는 바로 구현하지 않는다.

- prepare 내부 chunking
- prepare scoring/filtering 변경
- stage2 report를 여러 window로 나눈 뒤 자동 병합하는 기능
- overlap 자동 dedup으로 verdict/category/severity를 바꾸는 기능
- Web UI timeline view
- remoteIP 연동
- output cleanup 실제 삭제
- cron/systemd production 등록

## 5. Apache logs-only guardrail

Sliding Window는 실행 단위와 비용/토큰 제어를 위한 운영 전략이다. 다음을 바꾸지 않는다.

- `status_code=200`으로 공격 성공/침해 성공 단정 금지
- `status_code=403/404/500/503`만으로 취약점/공격 성공/침해 단정 금지
- `response_body_bytes`, `resp_content_type`, `text/html`로 파일 노출/정보 유출 단정 금지
- POST metadata만으로 로그인 성공/업로드 저장 성공 단정 금지
- raw POST body, response body, DB 결과, browser execution 추론 금지
- context-only를 finding/incident로 승격 금지
- Web UI에서 severity/category/verdict 재계산 금지
- prepare/scoring/filtering 변경 금지

## 6. 0523 권장 작업 순서

1. 팀원 문서 4개를 repo 경로로 편입할지, 요약 review 문서만 유지할지 결정한다.
2. 현재 CLI와 문서 예시 명령어의 옵션명을 대조한다.
3. `sliding_window_scheduler.py` 구현 전 dry-run 설계만 확정한다.
4. historical export 1~2시간 범위로 window 목록만 생성하는 dry-run 검증 계획을 작성한다.
5. token/cost 문서는 실제 모델 단가와 현재 run artifact 기준으로 재측정할 항목을 표시한다.

## 7. 현재 결론

Sliding Window 문서 세트는 운영 자동화/토큰 제어 관점에서 유효하다.

다만 바로 scheduler 구현으로 들어가지 않고, 0523에는 다음까지만 진행한다.

```text
- 문서 intake
- CLI 옵션 호환성 확인
- dry-run 검증 범위 확정
- prepare/scoring/filtering 변경 없음 확인
```

그 다음에만 최소 scheduler 구현 여부를 판단한다.
