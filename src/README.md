# src/

## 1. 역할

`src/`는 프로젝트의 **로그 수집 이후 분석 runtime과 분석 파이프라인을 구성하는 주요 Python 코드**를 관리한다.

현재 사용자 `full_report` 흐름은 크게 두 계층으로 나뉜다.

~~~text
Job 실행 계층
  Analysis Job Worker
    -> FullReportJobRunner
    -> Export

분석 파이프라인 계층
  Prepare
    -> Stage1 Classification
    -> Security Standards Mapping
    -> Stage2 Report Input
       + Security Standards Summary
    -> Stage2 Report Synthesis
    -> Viewer Payload
~~~

Web request handler가 이 파이프라인을 직접 실행하지 않는다. Web UI/API는 Analysis Job을 생성하고, 실제 실행은 `Analysis Job Worker`가 담당한다.

전체 시스템 연결 관계는 [../docs/00_current_architecture.md](../docs/00_current_architecture.md)를 따른다.

---

## 2. Current full_report runtime

현재 DB-backed Analysis Job의 canonical analysis mode는 `full_report`다.

~~~text
analysis_jobs: PENDING
        |
        v
analysis_job_worker.py
        |
        v
FullReportJobRunner
        |
        +-> export_db_logs_cli.py
        |
        v
run_analysis_pipeline.py
        |
        +-> prepare_llm_input.py
        |
        +-> llm_stage1_classifier.py
        |       |
        |       +-> security_standards_mapping.py
        |
        +-> llm_stage2_reporter.py
        |       |
        |       +-> security_standards_summary.py
        |
        +-> viewer_payload_builder.py
        |
        v
job-scoped artifacts
~~~

중요한 경계:

- Worker가 Job lifecycle을 소유한다.
- Runner가 Export와 pipeline subprocess 실행을 연결한다.
- `run_analysis_pipeline.py`는 이미 생성된 export JSON 이후의 분석 pipeline을 orchestration한다.
- Security Standards Mapping은 Stage1 result 생성 시 deterministic하게 추가된다.
- Security Standards Summary는 Stage2 report input을 만들 때 deduplicated Stage1 result를 기준으로 계산된다.
- Viewer Payload는 Stage2 결과와 관련 artifact를 읽어 별도 builder가 생성한다.

---

## 3. Runtime entrypoints

### 3.1 `analysis_job_worker.py`

DB-backed Analysis Job Worker entrypoint다.

주요 책임:

- `PENDING` `full_report` Job atomic claim
- `RUNNING` 전환
- worker identity / heartbeat 관리
- runner 호출
- stage event 기록
- analysis report metadata 저장
- `SUCCEEDED` / `FAILED` terminal 상태 반영
- stale-running recovery 관련 운영 경로 제공

Worker는 Job을 claim했다고 해서 pipeline 완료로 간주하지 않는다.

~~~text
claim
!= pipeline success
~~~

실제 분석은 pipeline 실행 옵션이 활성화된 Worker 경로에서 `FullReportJobRunner`를 통해 수행된다.

### 3.2 `full_report_job_runner.py`

하나의 claimed `full_report` Job을 실제 export + analysis pipeline 실행으로 연결한다.

~~~text
claimed Job
  -> Export command 생성
  -> export_db_logs_cli.py 실행
  -> no-data 확인
  -> run_analysis_pipeline.py 실행
  -> artifact materialization 검증
  -> result 반환
~~~

현재 Job 입력 방식은 두 종류다.

#### time_range

일반 시간 범위 Job은 `time_from / time_to`를 exporter에 전달한다.

#### live_selected_logs

Live에서 선택한 로그 기반 Job은 선택된 `apache_security_logs.id`를 authoritative input으로 사용한다.

~~~text
input_kind = live_selected_logs
  -> selected_input_rows
  -> selected source IDs
  -> --selected-log-id ...
  -> exact-ID export
~~~

runner는 selected-input Job에서 선택하지 않은 같은 시간대 row를 분석 입력으로 자동 승격하지 않는다.

### 3.3 `export_db_logs_cli.py`

MariaDB 원천 로그를 분석용 JSON으로 export한다.

대표 source table:

- security
- access
- error

시간 범위 기반 export와 selected security-log ID 기반 exact export를 모두 지원한다.

Export 결과는 `prepare_llm_input.py`와 `run_analysis_pipeline.py`의 입력이다.

### 3.4 `run_analysis_pipeline.py`

export JSON 이후의 분석 파이프라인을 통합 실행한다.

기본 흐름:

~~~text
export JSON
  -> Prepare
  -> Stage1
  -> Stage2 input / Stage2
  -> Viewer Payload
~~~

이 파일이 DB export 자체를 수행하는 것은 아니다. DB Export는 Worker/Runner 경로에서 `export_db_logs_cli.py`가 담당한다.

지원 resume 입력:

- `--export-input`
- `--llm-input`
- `--stage1-results`

대표 기능:

- Prepare 실행
- Stage1 실행
- Stage2 실행
- Viewer Payload 생성
- dry-run
- provider/model override
- source table resolution
- run-dir artifact materialization
- pipeline manifest 기록

`--export-input` 경로에서는 export payload의 table/count/data 정보를 기준으로 Prepare source table을 자동 결정할 수 있다.

---

## 4. Prepare

### 4.1 `prepare_llm_input.py`

Export JSON을 입력으로 받아 Stage1과 Stage2가 사용할 deterministic 분석 구조를 생성한다.

현재 `prepare_llm_input.py`는 coordinator 역할을 유지하고, 세부 detector/helper/context builder는 [prepare/README.md](./prepare/README.md)의 모듈로 분리되어 있다.

주요 책임:

- input normalization
- decoded variant 생성
- candidate scoring / selection
- candidate deduplication
- filtered reason 기록
- noise aggregation
- supporting event 구성
- context summary 구성
- Stage1용 candidate artifact 생성
- LLM input payload 생성

대표 산출물:

~~~text
llm_input.json
analysis_candidates.json
noise_summary.json
filtered_reasons.json
filtered_out_rows.json   # optional
~~~

prefix 기반 출력도 지원하며, Job `run-dir`에서는 flat artifact name을 사용한다.

의미 경계:

~~~text
candidate
= Stage1 검토 대상으로 선택된 행/incident

candidate-excluded
= candidate policy에서 제외
!= benign
!= normal
!= safe

context-only
= 해석 문맥
!= finding

supporting event
= 주변 참고 요청
!= finding
~~~

### 4.2 `src/prepare/`

Prepare 내부 helper와 policy-adjacent module은 `src/prepare/`에서 관리한다.

대표 영역:

- decoding
- SQLi / XSS / Traversal / CMDi / file disclosure hint
- auth behavior
- method behavior
- protocol anomaly
- static / crawler baseline
- sensitive path probing
- IP behavior
- probing sequence
- mixed baseline / scanner context
- Apache observability context
- shared security signal adapter

세부 ownership은 [prepare/README.md](./prepare/README.md)를 따른다.

---

## 5. Shared Security Signal Observation

### 5.1 `security_signals/extractor.py`

Prepare와 Live가 공통으로 사용할 수 있는 **pure deterministic observation layer**다.

현재 extractor는 caller가 전달한 text surface를 제한된 rule allowlist로 관찰하고 evidence/provenance를 반환한다.

주요 경계:

~~~text
Shared Security Signal Extractor
  = observation facts

!= candidate policy
!= severity
!= verdict
!= exploit confirmation
~~~

DB/file/network I/O를 수행하지 않으며 Prepare나 Live의 전체 policy를 소유하지 않는다.

현재 approved rule family에는 제한된 형태의 다음 구조가 포함된다.

- SQL termination / boolean / union structure
- XSS event-handler structure
- shell separator command structure
- PHP filter/resource structure

### 5.2 Prepare adapter

`prepare/shared_signal_adapter.py`는 shared observation을 Prepare의 기존 hint 관계에 투영한다.

현재 Prepare의 score, candidate selection, filtering, supporting-event 정책은 Prepare가 소유한다.

즉 shared extractor를 사용한다는 사실이 Prepare의 전체 detector policy가 extractor로 이전됐다는 뜻은 아니다.

---

## 6. Stage1과 Security Standards Mapping

### 6.1 `llm_stage1_classifier.py`

Prepare의 `analysis_candidates`를 대상으로 candidate별 LLM classification을 수행한다.

대표 출력 정보:

- verdict
- severity
- confidence
- reasoning summary
- evidence fields
- recommended actions
- provider/model/usage metadata

Stage1은 Apache logs-only evidence boundary 안에서 판단해야 한다.

### 6.2 `security_standards_mapping.py`

Stage1 candidate classification이 성공하면 결과 row에 deterministic `standards_mapping`을 추가한다.

실제 실행 관계:

~~~text
Prepare candidate
  -> Stage1 LLM classification
  -> build_security_standards_mapping(...)
  -> Stage1 result row
~~~

Mapping은 Stage1 verdict와 Prepare evidence를 기준으로 관련 taxonomy 정보를 보강한다.

현재 표준 surface:

- OWASP Top 10
- CWE
- WSTG

~~~text
Security Standards Mapping
= deterministic taxonomy enrichment

!= detector
!= vulnerability confirmation
!= exploit success confirmation
~~~

---

## 7. Stage2와 Security Standards Summary

### 7.1 `llm_stage2_reporter.py`

Stage1 result와 Prepare context를 바탕으로 최종 report input과 Stage2 report를 생성한다.

Stage2는 먼저 Stage1 result를 incident/finding 기준으로 정리하고, context와 filtered/noise 정보를 함께 구성한다.

대표 입력 정보:

- deduplicated Stage1 findings
- candidate evidence
- supporting events
- filtered-out breakdown
- noise groups
- source-IP context
- auth / method / protocol context
- baseline/scanner context
- known asset information
- Stage1 error metadata

### 7.2 `security_standards_summary.py`

Security Standards Summary는 Stage2 LLM 호출 이후의 후처리 단계가 아니다.

실제 실행 위치는 **Stage2 report input 구성 과정**이다.

~~~text
Stage1 results
  -> dedup_stage1_results(...)
  -> build_security_standards_summary(...)
  -> Stage2 report input
  -> Stage2 LLM synthesis
~~~

counting unit은 `deduplicated_finding`이다.

~~~text
Security Standards Summary
= deterministic aggregate

!= finding-level detector
!= compliance score
!= vulnerability confirmation
~~~

Viewer에 표시되는 top-N finding 배열을 전체 summary 계산 입력으로 사용하지 않는다.

### 7.3 Stage2 report synthesis

Stage2 LLM은 이미 구성된 report input을 바탕으로 사람이 읽을 수 있는 보고서를 생성한다.

대표 output:

- Stage2 report JSON
- Stage2 Markdown
- Stage2 report input artifact

Stage2 역시 Apache 로그에서 확인되지 않은 명령 실행, 파일 노출, 브라우저 실행, 서버 침해 같은 사실을 새 evidence처럼 생성해서는 안 된다.

---

## 8. Viewer Payload

### `viewer_payload_builder.py`

Stage2 report와 report input, Stage1 result, Prepare artifact를 읽어 `viewer_payload.v1`을 생성한다.

대표 입력:

- stage2 report
- stage2 report input
- stage1 results
- llm input
- noise summary
- optional raw export

대표 출력:

~~~text
viewer_payload.json
~~~

Viewer Payload Builder는 Viewer가 사용할 projection을 만들지만 Stage1/Stage2의 보안 의미를 재판정하지 않는다.

~~~text
Viewer Payload Builder
  -> projection / role organization / display source

!= new detector
!= verdict recalculation
!= severity recalculation
~~~

Web 표시 계층의 상세 경계는 [../web/README.md](../web/README.md)를 참고한다.

---

## 9. LLM Client

### `llm_client.py`

Stage1과 Stage2가 사용하는 provider abstraction을 제공한다.

주요 역할:

- provider normalize
- provider별 API 설정
- JSON structured response 호출
- usage normalization
- usage aggregation
- API key / base URL resolution

현재 Stage1/Stage2는 외부 Provider 설정과 network 상태의 영향을 받는다.

source와 test가 존재한다는 사실만으로 provider-backed runtime success를 보장하지 않는다.

---

## 10. Job-scoped artifacts

정상 `full_report` Job은 Job별 artifact root를 사용한다.

대표 artifact:

~~~text
export.json
llm_input.json
analysis_candidates.json
noise_summary.json
filtered_reasons.json
stage1_results.json
stage2_report_input.json
stage2_report.json
stage2_report.md
viewer_payload.json
manifest.json
~~~

모든 파일이 모든 실행 경로에서 항상 생성되는 것은 아니다.

예:

- no-data Job은 pipeline 전체를 실행하지 않을 수 있다.
- `filtered_out_rows.json`은 option에 따라 생성된다.
- Stage1 error artifact는 error 발생 여부에 따라 달라질 수 있다.
- dry-run은 provider call 결과 대신 dry-run contract를 따른다.

Job runtime에서 필수 artifact 검증과 DB metadata 저장은 `FullReportJobRunner`와 Worker 계층이 담당한다.

---

## 11. Apache logs-only Evidence Boundary

`src/` 분석 계층 전체는 Apache logs-only 의미 경계를 유지한다.

직접 근거로 사용할 수 있는 대표 정보:

- request method
- URI / Request Target
- source IP
- status code
- response size
- Content-Type
- User-Agent
- log time
- 반복/주변 요청 패턴
- Apache handler / route / protocol 관련 관찰값

Apache 로그만으로 다음을 확정하지 않는다.

~~~text
raw POST body 내용
실제 response body 내용
DB query 실행 결과
OS command 실행 결과
실제 파일 내용 노출
브라우저 JavaScript 실행
외부 callback 성공
취약점 존재
서버 침해
데이터 유출
~~~

~~~text
status_code
response_body_bytes
resp_content_type
specific IP
specific User-Agent
specific route

각각 단독으로
!= exploit success
!= compromise
!= exfiltration
~~~

세부 기준은 [../docs/00_apache_logs_only_evidence_boundary.md](../docs/00_apache_logs_only_evidence_boundary.md)를 따른다.

---

## 12. Runtime 외 코드

`src/`에는 현재 사용자 `full_report` runtime 외의 검증·실험·후속 코드도 존재한다.

### Offline verification / benchmark

대표 파일:

~~~text
external_benchmark_crs*.py
external_benchmark_csic2010*.py
external_benchmark_prepare*.py
external_benchmark_stage1*.py
prepare_full_output_harness/
~~~

이 코드는 fixture, external benchmark, compatibility comparison 등을 위한 검증 자산이다.

~~~text
offline validation code
!= current user runtime
~~~

### Separate / post-final analysis paths

대표 파일:

~~~text
sliding_window_scheduler.py
sliding_window_summary.py
sliding_window_rollup.py
sliding_window_operator_queue.py
sliding_window_operator_queue_detail.py
~~~

이 경로는 `analysis_jobs` 기반 `full_report` 실행 queue와 동일한 runtime으로 해석하지 않는다.

현재 사용자 runtime에 포함되는 경로는 [../docs/00_current_architecture.md](../docs/00_current_architecture.md)를 기준으로 해석한다.

---

## 13. Regression / verification

분석 코드 변경 시 대표적으로 다음 검증을 사용한다.

~~~bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
~~~

필요한 focused pytest와 compile check는 변경 범위에 따라 추가한다.

Stage2 report wording 검토에는 다음 lint를 사용할 수 있다.

~~~bash
python3 scripts/check_stage2_report_quality.py \
  --input path/to/stage2_report.json \
  --pretty
~~~

이 lint는 공격 성공 여부를 판정하는 detector가 아니라 Apache logs-only wording boundary를 점검하는 도구다.

고정 테스트 개수나 과거 spot-check 결과는 이 README에서 current baseline으로 관리하지 않는다. 실제 검증 여부는 해당 revision에서 실행한 regression/pytest/E2E 결과와 Git history를 기준으로 확인한다.

---

## 14. 주요 코드 책임 요약

| 파일 / 영역 | 책임 |
| --- | --- |
| `analysis_job_worker.py` | DB-backed Job claim / lifecycle / runner 실행 |
| `full_report_job_runner.py` | Export와 분석 pipeline 연결, Job artifact materialization |
| `export_db_logs_cli.py` | MariaDB 원천 로그 export |
| `prepare_llm_input.py` | deterministic candidate/context/supporting evidence 구성 |
| `prepare/` | Prepare 내부 helper, hint, context module |
| `security_signals/` | shared deterministic security observation |
| `llm_stage1_classifier.py` | candidate별 Stage1 LLM classification |
| `security_standards_mapping.py` | Stage1 result의 deterministic standards enrichment |
| `llm_stage2_reporter.py` | Stage2 report input 구성 및 report synthesis |
| `security_standards_summary.py` | deduplicated finding 기준 deterministic standards aggregate |
| `viewer_payload_builder.py` | Analysis Viewer용 viewer_payload.v1 projection |
| `run_analysis_pipeline.py` | export JSON 이후 Prepare → Stage1 → Stage2 → Viewer orchestration |
| `llm_client.py` | LLM provider / usage abstraction |

---

## 15. 관련 문서

| 문서 | 역할 |
| --- | --- |
| [../README.md](../README.md) | 프로젝트 전체 소개 |
| [../docs/00_current_architecture.md](../docs/00_current_architecture.md) | 전체 runtime architecture |
| [prepare/README.md](./prepare/README.md) | Prepare 내부 모듈과 ownership |
| [../web/README.md](../web/README.md) | Web 계층 구조와 Viewer 경계 |
| [../docs/00_apache_logs_only_evidence_boundary.md](../docs/00_apache_logs_only_evidence_boundary.md) | 분석 의미 경계 |
| [../docs/operations/README.md](../docs/operations/README.md) | DB / 환경 / Worker runtime support |

이 문서는 과거 refactor round나 특정 fixture 숫자를 현재 구조 설명과 섞지 않는다. `src/` README의 책임은 **현재 분석 runtime 코드가 어떤 단계와 ownership으로 연결되어 있는지 설명하는 것**이다.
