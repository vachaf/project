# Analysis Job Stage-Level Job Events Design

## 1. 배경

현재 DB-backed analysis job의 `job_events`는 job lifecycle 중심으로 기록된다. `JOB_CREATED`, `JOB_CLAIMED`, `JOB_STARTED`, `JOB_SUCCEEDED`, `JOB_FAILED` 같은 이벤트는 전체 작업 상태를 파악하기에는 충분하지만, worker가 실제로 어느 실행 경계까지 진행했는지와 실패 위치를 세밀하게 진단하기에는 부족하다.

이 문서의 목표는 Web UI read-only timeline과 운영 진단을 위한 stage event 설계를 정리하는 것이다. 설계 범위는 Apache logs-only 원칙을 유지하며, Web UI는 저장된 job event와 artifact를 표시하는 read-only projection으로만 동작한다.

## 2. 조사 결과 요약

- `analysis_job_worker.py`는 job claim 이후 `JOB_STARTED`를 기록하고 `FullReportJobRunner.run()`만 호출한다.
- `FullReportJobRunner.run()`은 정상 데이터 기준으로 두 개의 subprocess를 실행한다.
  - `export_db_logs_cli.py`
  - `run_analysis_pipeline.py`
- no-data export에서는 `run_analysis_pipeline.py`를 실행하지 않는다. 이 경우 export artifact만 materialize하고 job은 no-data success로 닫힌다.
- `run_analysis_pipeline.py` 내부에서 `prepare_llm_input.py`, `llm_stage1_classifier.py`, `llm_stage2_reporter.py`, `viewer_payload_builder.py`가 실행된다.
- 따라서 현재 worker/runner는 prepare, stage1, stage2, viewer_payload의 실제 시작/종료 경계를 직접 관찰하지 못한다.
- `manifest_path`는 `analysis_reports` DB mapping에 없고, worker/runner가 manifest를 읽어 stage event를 사후 생성하는 경로도 없다.
- manifest 사후 파싱은 실제 event time이 아니므로 Phase 1 stage event 설계에서 제외한다.

## 3. Phase 1: 최소 변경 설계

Phase 1은 현재 worker/runner가 정확히 관찰 가능한 실행 경계만 `job_events`에 기록한다. 목표는 coarse boundary를 통해 운영자가 export 실패, pipeline 실패, report 저장 실패를 구분할 수 있게 하는 것이다.

Phase 1에서 정확히 기록 가능한 경계:

- job lifecycle
- export subprocess 시작/완료/실패/no-data
- pipeline subprocess 시작/완료/실패
- report metadata 저장 시작/완료/실패
- final success/failure

Phase 1 이벤트 목록:

```text
JOB_CREATED
JOB_CLAIMED
JOB_STARTED
EXPORT_STARTED
EXPORT_COMPLETED
EXPORT_FAILED
EXPORT_NO_DATA
PIPELINE_STARTED
PIPELINE_COMPLETED
PIPELINE_FAILED
REPORT_SAVE_STARTED
REPORT_SAVE_COMPLETED
REPORT_SAVE_FAILED
JOB_SUCCEEDED
JOB_FAILED
```

Phase 1에서는 `PREPARE_*`, `STAGE1_*`, `STAGE2_*`, `VIEWER_PAYLOAD_*` 이벤트를 만들지 않는다. 현재 구조에서는 이 경계가 `run_analysis_pipeline.py` 내부에 감춰져 있어 정확한 event time을 기록할 수 없기 때문이다.

## 4. Phase 1 `detail_json` 예시

`job_events.detail_json`은 기존 컬럼을 재사용한다. DB schema 변경은 필수가 아니다.

성공 이벤트 예시:

```json
{
  "worker_id": "worker-01",
  "artifact_root": "runs/jobs/123",
  "export_path": "runs/jobs/123/export.json",
  "duration_seconds": 1.42
}
```

pipeline 완료 이벤트 예시:

```json
{
  "worker_id": "worker-01",
  "artifact_root": "runs/jobs/123",
  "stage2_report_path": "runs/jobs/123/stage2_report.json",
  "viewer_payload_path": "runs/jobs/123/viewer_payload.json",
  "duration_seconds": 87.31
}
```

실패 이벤트 예시:

```json
{
  "worker_id": "worker-01",
  "artifact_root": "runs/jobs/123",
  "failed_at_stage": "pipeline",
  "duration_seconds": 12.08,
  "error_type": "FullReportRunnerError",
  "error_message": "pipeline command failed rc=1 stderr=[REDACTED]"
}
```

`failed_at_stage`의 Phase 1 허용 값:

```text
export
pipeline
report_save
```

`error_message`는 operator-safe redacted summary만 저장한다. `detail_json`에는 API key, provider secret, raw provider error body, Authorization/Cookie 값, raw request body, response body를 저장하지 않는다.

## 5. Phase 1 구현 원칙

- 정확히 관찰 가능한 경계만 event로 남긴다.
- prepare/stage1/stage2/viewer_payload event를 사후 추정으로 만들지 않는다.
- manifest 사후 파싱은 실제 event time이 아니므로 Phase 1 설계에서 제외한다.
- DB schema 변경은 필수가 아니다.
- 기존 `append_job_event()` API와 `job_events.detail_json`을 재사용한다.
- `detail_json`에는 recursive redaction이 필요하다.
- `JOB_FAILED`의 `detail_json.failed_at_stage`는 Phase 1에서 `export`, `pipeline`, `report_save`까지만 정확히 기록한다.
- Apache logs-only 원칙을 유지한다. stage event는 실행/운영 metadata이며, Apache log evidence의 보안 의미를 새로 만들지 않는다.

## 6. Phase 2: 확장 설계

prepare/stage1/stage2/viewer_payload 단위의 fine-grained event가 필요하면 runner/pipeline 구조 변경이 선행되어야 한다. 현재 구조에서 해당 이벤트를 바로 추가하면 실제 실행 시각이 아니라 사후 추정 timeline이 된다.

Phase 2 구조 변경 후보:

### a. `FullReportJobRunner`가 단계별 직접 orchestration

`FullReportJobRunner`가 `run_analysis_pipeline.py` 한 번 호출 대신 다음 subprocess를 직접 실행한다.

```text
prepare_llm_input.py
llm_stage1_classifier.py
llm_stage2_reporter.py
viewer_payload_builder.py
```

이 방식은 runner가 각 subprocess 시작/완료/실패를 직접 관찰하므로 가장 단순하게 정확한 event time을 기록할 수 있다. 다만 `run_analysis_pipeline.py`의 path resolution, dry-run, run-dir sync, manifest 생성 로직을 runner 쪽으로 이동하거나 공통화해야 한다.

### b. `run_analysis_pipeline.py`를 event hook 가능한 in-process runner로 분리

pipeline orchestration 로직을 import 가능한 함수 또는 class로 분리하고, worker/runner가 event hook을 주입한다. 각 단계 전후에 hook을 호출하면 DB event를 정확히 기록할 수 있다.

이 방식은 pipeline의 기존 책임을 보존하면서 event emission을 외부에서 제어할 수 있다. 단, CLI와 in-process API 사이의 계약을 명확히 나눠야 한다.

### c. pipeline stdout JSONL event를 runner가 streaming parse

`run_analysis_pipeline.py`가 각 단계 시작/완료/실패를 JSONL로 stdout에 출력하고, runner가 subprocess stdout을 streaming parse하여 `job_events`로 저장한다.

이 방식은 pipeline을 subprocess로 유지할 수 있지만, 현재 runner의 `capture_output=True` 완료 후 처리 방식으로는 충분하지 않다. 정확한 event time을 위해 streaming subprocess 처리와 JSONL protocol 안정화가 필요하다.

Phase 2 이후에만 다음 이벤트 도입을 검토한다.

```text
PREPARE_STARTED
PREPARE_COMPLETED
PREPARE_FAILED
STAGE1_STARTED
STAGE1_COMPLETED
STAGE1_FAILED
STAGE2_STARTED
STAGE2_COMPLETED
STAGE2_FAILED
VIEWER_PAYLOAD_STARTED
VIEWER_PAYLOAD_COMPLETED
VIEWER_PAYLOAD_FAILED
```

## 7. Web UI 정책

- Web UI는 `job_events`를 read-only timeline으로 표시한다.
- Web UI는 pipeline이나 worker를 직접 실행하지 않는다.
- Web UI는 새로운 보안 판단을 수행하지 않는다.
- Web UI는 severity, category, verdict를 재계산하지 않는다.
- Web UI는 context-only item을 finding으로 승격하지 않는다.
- Web UI는 저장된 `analysis_reports`와 `viewer_payload.json`을 read-only artifact로 표시한다.
- timeline 표시는 event order와 detail visibility를 돕기 위한 운영 UI이며, Apache logs-only evidence boundary를 확장하지 않는다.

## 8. 테스트 후보

- export/pipeline/report_save event 순서 테스트
- export 실패 시 `failed_at_stage=export`
- pipeline 실패 시 `failed_at_stage=pipeline`
- report save 실패 시 `failed_at_stage=report_save`
- no-data export 시 `EXPORT_NO_DATA`와 `JOB_SUCCEEDED`
- `detail_json` recursive redaction
- Web UI read-only timeline 회귀 테스트

## 9. 결론

Phase 1은 현재 구조에서 정확히 관찰 가능한 coarse boundary만 기록해야 한다. 이 범위에서는 DB schema 변경 없이 `append_job_event()`와 `job_events.detail_json` 재사용으로 구현 가능하다.

prepare/stage1/stage2/viewer_payload 단위 이벤트는 현재 worker/runner 구조에서 정확히 구현할 수 없다. 이 이벤트들은 Phase 2에서 runner/pipeline 구조를 바꾼 뒤 도입해야 한다.
