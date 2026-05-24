# 99_sliding_window_rollup_pipeline_integration

- 문서 상태: 채택 후보 / pipeline v1.0 정렬본
- 기준 시점: 2026-05-24
- 작성 배경: 안수홍님 작성 Rollup pipeline 초안을 `99_sliding_window_rollup_input_review.md` 기준으로 축소/정렬
- 적용 범위: 파일 artifact 기반 Sliding Window + Rollup 흐름

## 1. 결론

Rollup pipeline은 기존 single-window pipeline을 대체하지 않는다. 추가 분석 경로로 붙인다.

```text
Single Window:
export.json
  -> prepare_llm_input.py
  -> llm_input.json / analysis_candidates.json / noise_summary.json
  -> Stage1
  -> Stage2
  -> Web UI

Sliding Window + Rollup:
sw_*/window_summary.json
  -> sliding_window_rollup.py
  -> rollup_input.json / dedup_candidates.json / rollup_summary.json
  -> Stage1/Stage2 compatibility target (v1.5 후보)
```

v1.0에서 `sliding_window_rollup.py`는 Stage1/Stage2 실행까지 담당하지 않는다. v1.0은 rollup artifact 생성까지만 담당한다.

## 2. 기존 Single Window 구조

```text
One Dump
  ↓
export.json
  ↓
prepare_llm_input.py
  ↓
llm_input.json
analysis_candidates.json
noise_summary.json
  ↓
llm_stage1_classifier.py
  ↓
stage1_results.json
  ↓
llm_stage2_reporter.py
  ↓
stage2_report.json / stage2_report.md
  ↓
Web UI
```

이 흐름은 변경하지 않는다.

## 3. Sliding Window + Rollup v1.0 구조

```text
Continuous Log Range
  ↓
sliding_window_scheduler.py --mode planner
  ↓
window plan
  ↓
sliding_window_scheduler.py --mode export
  ↓
data/windowed/<date>/sw_*/export.json
  ↓
sliding_window_scheduler.py --mode prepare
  ↓
data/windowed/<date>/sw_*/
  ├── export.json
  ├── llm_input.json
  ├── analysis_candidates.json
  ├── noise_summary.json
  └── window_summary.json
  ↓
sliding_window_rollup.py
  ↓
data/rollups/<date>/<rollup_id>/
  ├── rollup_input.json
  ├── dedup_candidates.json
  └── rollup_summary.json
```

## 4. 책임 분리

### sliding_window_scheduler.py

```text
- window 계획
- window별 export 실행
- window별 prepare 실행
- window_summary.json 생성 호출
```

### sliding_window_summary.py

```text
- 단일 window의 summary-only index 생성
- candidate_index 생성
- distributions 생성
- rollup_hints 생성
```

### sliding_window_rollup.py

v1.0 책임:

```text
- 여러 window_summary.json 로드
- missing/invalid window 상태 기록
- request_id dedup
- request_id 없는 후보 보존
- fallback duplicate는 marked_only_not_removed로 표시
- candidate_index merge
- distribution merge
- rollup_input.json / dedup_candidates.json / rollup_summary.json 저장
```

v1.0에서 하지 않는 일:

```text
- uri_family_hints 생성
- low_and_slow_hints 생성
- Stage1/Stage2 실행
- analysis_candidates projection 생성
- runs/ 생성
- Web UI 수정
```

### llm_stage1_classifier.py

```text
- v1.0에서 직접 수정 대상 아님
- rollup_input compatibility는 v1.5 후보로 별도 테스트 후 판단
```

### llm_stage2_reporter.py

```text
- v1.0에서 직접 수정 대상 아님
- rollup metadata/context 호환성은 v1.5 후보로 별도 테스트 후 판단
```

## 5. v1.0 실행 예시

### 5.1 Planner

```bash
python3 src/sliding_window_scheduler.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-24 02:00:00" \
  --analysis-end "2026-05-24 06:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --mode planner
```

### 5.2 Export

```bash
python3 src/sliding_window_scheduler.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-24 02:00:00" \
  --analysis-end "2026-05-24 06:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --mode export \
  --table security
```

### 5.3 Prepare

```bash
python3 src/sliding_window_scheduler.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-24 02:00:00" \
  --analysis-end "2026-05-24 06:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --mode prepare
```

### 5.4 Rollup

`--out-dir`를 주지 않으면 기본값은 다음 후보를 사용한다.

```text
data/rollups/<date>/rollup_YYYYMMDD_HHMM_HHMM
```

명시적으로 지정할 수도 있다.

```bash
python3 src/sliding_window_rollup.py \
  --work-dir /opt/web_log_analysis \
  --analysis-start "2026-05-24 02:00:00" \
  --analysis-end "2026-05-24 06:00:00" \
  --window-minutes 60 \
  --stride-minutes 60 \
  --out-dir data/rollups/2026-05-24/rollup_20260524_0200_0600 \
  --pretty
```

## 6. Stage1/Stage2 호환성 원칙

초안의 “기존 코드 그대로” 표현은 v1.0 문서에서는 쓰지 않는다.

대신 다음으로 정리한다.

```text
- 목표: Stage1/Stage2가 기존 analysis_candidates 기반 처리를 유지하도록 한다.
- 보장 전제: rollup_input이 필요한 compatibility projection을 제공한다.
- 현재 상태: v1.0에서는 projection을 만들지 않는다.
- 검증: 별도 fixture 기반 test가 필요하다.
```

호환성 테스트 후보:

```text
tests/test_stage1_rollup_input_compat.py
tests/test_stage2_rollup_input_compat.py
```

초기에는 `sliding_window_rollup.py`가 Stage1/Stage2를 실행하지 않는다.

## 7. Single Window와 Rollup의 사용 위치

### Single Window

```text
- 빠른 분석
- 짧은 시간 범위 검토
- 실시간성 우선
- 기존 Web UI 흐름 유지
```

### Rollup

```text
- 여러 window에 걸친 중복 제거
- 긴 기간의 후보 index 병합
- 운영자 심화 검토
- 긴 기간의 LLM 입력 후보 축약 전 단계
```

Rollup은 단기 대응용 alert 엔진이 아니다.

## 8. 후보 흐름

### Window 0

```text
sw_0200_0300
  candidate_index:
    req_1 GET /admin/config.php 403 sensitive_path_probe
    req_2 GET /search 200 sqli_hint
```

### Window 1

```text
sw_0300_0400
  candidate_index:
    req_1 GET /admin/config.php 403 sensitive_path_probe
    req_3 GET /search 200 sqli_hint
```

### Rollup v1.0

```text
request_id dedup:
  req_1 중복 1건 제거
  req_2 유지
  req_3 유지

candidate_index:
  req_1 source_window_ids=[sw_0200_0300, sw_0300_0400]
  req_2 source_window_ids=[sw_0200_0300]
  req_3 source_window_ids=[sw_0300_0400]

rollup_context:
  v1.0에서는 notes만 기록
```

`req_2`, `req_3`을 합쳐 새 low-and-slow Stage1 후보를 만들지는 않는다.

## 9. 오류 처리

### window_summary.json 누락

```text
- rollup 전체를 즉시 실패시키지 않는다.
- source_windows에 missing 상태를 기록한다.
- counts.windows_missing_or_failed를 증가시킨다.
- rollup_summary.json에 incomplete_analysis=true를 기록한다.
```

### schema 불일치

```text
- schema가 sliding_window_summary_v1이 아니면 해당 window를 failed로 기록한다.
- strict mode에서는 전체 실패 가능.
- 기본 mode에서는 실패 window를 제외하고 incomplete로 생성한다.
```

### candidate_index 누락

```text
- window는 loaded로 기록하되 candidate_index_count=0으로 처리한다.
- artifact_status와 warning을 남긴다.
```

## 10. Web UI 통합 범위

v1.0에서는 Web UI를 수정하지 않는다.

향후 후보:

```text
- report list에 [ROLLUP] artifact 표시
- rollup_summary.json detail view
- source window drill-down
- dedup_report display
```

Web UI는 새 security verdict를 만들거나 후보를 재계산하지 않는다.

## 11. DB / FastAPI 범위

v1.0에서는 제외한다.

```text
- MariaDB rollup table 생성 없음
- FastAPI endpoint 추가 없음
- artifact file 기반으로만 진행
```

DB/API는 포맷과 운영 흐름이 안정화된 뒤 별도 문서에서 검토한다.

## 12. 구현 순서

```text
1. docs/design/99_sliding_window_rollup_input_format.md v1.0 확정
2. src/sliding_window_rollup.py 최소 구현
3. tests/test_sliding_window_rollup.py fixture 작성
4. 실제 data/windowed fixture로 dry-run
5. rollup_input.json schema 확인
6. uri_family/low_and_slow는 v1.1에서 별도 검토
7. Stage1/Stage2 compatibility test는 v1.5에서 별도 진행
```
