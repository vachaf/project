# Current Architecture

## 1. 문서 역할과 기준

- source 기준 revision: `d36a293c4eca9c85fc21165c1e06153bd9e1e26b`
- 기준일: 2026-09-19
- 상태: **Active / current runtime architecture**
- Evidence Boundary: [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)
- Final 범위 관리: [final/final-scope.md](./final/final-scope.md)
- Final 검증 상태: [final/final-verification-record.md](./final/final-verification-record.md)
- Final 상태·승격 기준: [final/final-status-and-freeze-criteria.md](./final/final-status-and-freeze-criteria.md)

이 문서는 **현재 main source에서 시스템이 어떤 경계와 데이터 흐름으로 연결되어 있는지**를 설명한다.

이 문서가 책임지는 것은 runtime architecture다. Final / Conditional Final / Deferred와 같은 범위 판정, 특정 revision의 PASS / FAIL / BLOCKED / NOT RUN, demo fixture freeze 상태는 각각의 Final 문서에서 관리한다.

또한 source나 test가 존재한다는 사실은 실제 배포 환경, DB migration, 외부 Provider 호출, 회귀 또는 E2E가 특정 revision에서 PASS했다는 뜻이 아니다.

---

## 2. Current Runtime Architecture

현재 사용자 흐름은 크게 **로그 관찰**, **Analysis Job 생성**, **Worker 분석**, **결과 검토**로 나뉜다.

~~~text
Apache access / security / error logs
                |
                v
          Log Shipper
   src/apache_log_shipper.py
                |
                v
             MariaDB
   +------------+-------------+
   |            |             |
   |            |             |
access logs  security logs  error logs
                |
                +----------------------+
                |                      |
                v                      |
        Live Monitoring                |
       /live, /api/live/*              |
                |                      |
                |              시간 범위 기반 입력
                |                      |
       Security Observation            |
                |                      |
        선택 security log IDs          |
                |                      |
                +----------+-----------+
                           |
                           v
                     Analysis Job
                  analysis_mode=full_report
                           |
                           v
                  Analysis Job Worker
                           |
                           v
                         Export
                           |
                           v
                        Prepare
                           |
                           v
               Stage1 LLM Classification
                           |
                           v
          Security Standards Mapping
                 deterministic
                           |
                           v
             Stage2 Report Input
          + Standards Summary
                 deterministic
                           |
                           v
              Stage2 Report Synthesis
                           |
                           v
          viewer_payload / reports /
             job-scoped artifacts
                           |
               +-----------+-----------+
               |                       |
               v                       v
          Job Detail             Analysis Viewer
               |
               v
    analysis_reports / job_events
~~~

핵심 경계는 다음과 같다.

- Live Monitoring은 최근 원천 로그를 조회하고 분석 입력을 선택하는 UI다.
- Live 조회 경로가 Prepare, Stage1, Mapping, Stage2 또는 Worker를 직접 실행하지 않는다.
- 선택 로그 분석은 별도 Analysis Job을 생성하여 기존 `full_report` Job/Worker lifecycle을 재사용한다.
- Analysis Viewer는 완료된 artifact를 읽어 표시하며 새로운 보안 verdict를 생성하지 않는다.

---

## 3. Log Ingest와 Storage

### 3.1 Apache Log Shipper

`src/apache_log_shipper.py`는 Apache access, security, error 로그를 파싱하여 MariaDB에 적재한다.

~~~text
Apache access log
  -> apache_access_logs

Apache security log
  -> apache_security_logs

Apache error log
  -> apache_error_logs
~~~

파일 offset과 실패 batch spool/replay는 shipper 운영 계층의 책임이다.

### 3.2 시간 기준

원천 로그와 Job의 DB 시간 값은 UTC naive `DATETIME(3)` 정책을 사용한다.

시간 범위 기반 새 Analysis Job에서는 Web UI가 `Asia/Seoul` 입력을 받고, Job policy 계층이 DB 조회에 사용할 UTC 범위로 정규화한다.

Live 화면은 DB의 UTC 시각을 사용자 표시 시점에 KST로 변환한다.

---

## 4. Web UI와 Live Monitoring

### 4.1 Web UI 역할

현재 Web UI는 다음 역할을 제공한다.

- Analysis Job dashboard
- 시간 범위 기반 새 Analysis Job 생성
- Live Monitoring
- Live에서 선택한 로그 기반 Analysis Job 생성
- Job Detail 및 lifecycle/event 조회
- Job artifact 조회
- Analysis Viewer
- 기존 legacy report/viewer route

보안 결과에 대한 Web UI의 read-only 원칙은 **DB write를 전혀 하지 않는다는 뜻이 아니라, 분석 결과의 의미를 Web UI가 다시 판정하거나 변경하지 않는다는 뜻**이다.

### 4.2 Live 조회 경로

Live 조회는 다음 경로로 구성된다.

~~~text
GET /live
GET /api/live/snapshot
GET /api/live/logs/{row_id}/raw
~~~

조회 데이터의 주 원천은 `apache_security_logs`다.

Live snapshot은 period, HTTP status class, method, source IP, Request Target keyword와 cursor를 이용한 조회를 지원한다. 기본 page size의 상한은 50건이다.

Live는 polling 기반으로 최근 상태를 갱신한다. WebSocket/SSE 기반 stream이 아니다.

### 4.3 Live 조회와 Job write 경계

Live의 로그 조회와 Analysis Job 생성은 같은 책임이 아니다.

~~~text
Live snapshot/raw
  -> LiveLogRepository
  -> apache_security_logs 조회
  -> 관찰/표시

선택 로그로 분석 작업 만들기
  -> POST /api/live/jobs/create
  -> AnalysisJobRepository
  -> analysis_jobs + selected-input metadata 저장
~~~

즉 Live 화면이 pipeline stage를 직접 호출하는 구조가 아니라, **사용자가 선택한 로그를 입력으로 하는 Job을 등록하는 구조**다.

---

## 5. Analysis Job 입력 모델

현재 지원되는 Analysis mode는 `full_report`다. 같은 Worker와 pipeline을 사용하지만 입력 identity는 두 방식으로 구분된다.

### 5.1 시간 범위 기반 입력

일반 새 Analysis Job은 사용자가 지정한 시간 범위를 입력으로 사용한다.

~~~text
Web UI
  -> time_from / time_to
  -> Asia/Seoul validation
  -> UTC DB range
  -> analysis_jobs: PENDING
  -> input_kind = time_range
~~~

정책 계층은 지원 timezone, `full_report` mode, 최대 시간 범위와 artifact path 정책을 검증한다.

### 5.2 Live selected logs 입력

Live에서 선택한 로그는 시간 범위 Job으로 의미를 변환하지 않는다.

~~~text
Live row selection
  -> selected_log_ids
  -> validate_selected_log_request()
  -> source_table = apache_security_logs
  -> input_kind = live_selected_logs
  -> stable input_fingerprint
  -> Analysis Job 생성
~~~

현재 입력 계약의 주요 특성은 다음과 같다.

- 선택 ID는 양의 정수만 허용한다.
- 한 요청의 최대 선택 수는 50개다.
- 중복 ID는 입력 순서를 보존하면서 제거한다.
- source table은 `apache_security_logs`로 고정한다.
- 정렬된 unique ID 집합으로 stable fingerprint를 만든다.
- 동일 사용자의 동일한 active selected-input Job 중복 생성을 방지한다.

Job 생성 시 source row 존재 여부를 확인하고, 요청된 선택 identity를 `analysis_job_selected_input_rows`에 저장한다.

~~~text
analysis_jobs
  id
  analysis_mode
  input_kind
  input_source_table
  input_fingerprint
  artifact_root
  ...

analysis_job_selected_input_rows
  job_id
  source_id
  selection_index
  found_at_submission
  log_time_at_submission
  created_at
~~~

`selection_index`는 사용자의 선택 순서를 보존한다. `found_at_submission`과 `log_time_at_submission`은 제출 시점의 source identity를 기록한다.

모든 선택 ID가 존재하지 않으면 Job을 생성하지 않고 NO_DATA로 처리할 수 있다. 일부 ID만 존재하는 경우에는 누락 identity도 별도로 기록하여 제출 당시 입력과 실제 존재 여부를 구분한다.

### 5.3 Worker에서의 selected-input 처리

Worker가 `live_selected_logs` Job을 claim하면 parent Job 정보와 함께 `analysis_job_selected_input_rows`를 읽는다.

selected-input Job의 authoritative input은 이 child-row metadata이며, runner는 선택된 source ID를 exporter의 exact-ID 조건으로 전달한다.

따라서 Live에서 선택한 입력을 단순히 넓은 시간 범위로 환산해 주변 행까지 분석 입력으로 포함하는 구조가 아니다.

---

## 6. Analysis Job / Worker Lifecycle

`analysis_jobs`는 DB-backed 실행 queue다.

대표 lifecycle은 다음과 같다.

~~~text
Web UI / API
  -> analysis_jobs: PENDING
  -> Worker atomic claim
  -> RUNNING
  -> JOB_STARTED
  -> EXPORT_STARTED
       |
       +-> EXPORT_FAILED
       |      -> JOB_FAILED / FAILED
       |
       +-> EXPORT_NO_DATA
       |      -> JOB_NO_DATA
       |
       +-> EXPORT_COMPLETED
              -> PIPELINE_STARTED
                    |
                    +-> PIPELINE_FAILED
                    |      -> JOB_FAILED / FAILED
                    |
                    +-> PIPELINE_COMPLETED
                           -> REPORT_SAVE_STARTED
                           -> REPORT_SAVE_COMPLETED
                           -> JOB_SUCCEEDED / SUCCEEDED
~~~

Worker는 `PENDING`인 `full_report` Job 하나를 transaction 안에서 claim하고 `RUNNING`으로 전환한다.

Job 실행 중에는 heartbeat와 stage event를 기록한다. 완료 후 artifact metadata와 요약은 `analysis_reports`에 저장되고 terminal status가 갱신된다.

no-data는 요청 범위 또는 exact selected-input 조건에서 실제 분석할 row가 없다는 실행 결과다.

~~~text
NO_DATA
!= no security signal
!= benign
!= safe
~~~

one-shot Worker 실행에서 pipeline 실행 옵션을 사용하지 않는 경로는 claim 동작 확인 용도로 사용할 수 있으므로, **Job claim 자체를 pipeline 완료로 해석하지 않는다.**

---

## 7. Analysis Pipeline

정상 `full_report` pipeline은 다음 순서를 사용한다.

~~~text
Export
  -> Prepare
  -> Stage1
  -> Security Standards Mapping
  -> Stage2 Report Input + Security Standards Summary
  -> Stage2 Report Synthesis
  -> viewer_payload
~~~

### 7.1 Export

`src/export_db_logs_cli.py`가 MariaDB 원천 로그를 pipeline 입력 JSON으로 만든다.

시간 범위 Job은 요청 범위를 이용해 export한다.

Live selected-input Job은 runner가 Job metadata의 bounded time 정보와 함께 exact selected source ID 조건을 exporter에 전달한다. selected ID가 authoritative input이므로 같은 시간 구간의 선택되지 않은 security row를 selected input으로 승격하지 않는다.

### 7.2 Prepare

`src/prepare_llm_input.py`는 deterministic preprocessing coordinator다.

주요 역할은 다음과 같다.

- 입력 normalization / decoding
- candidate 구성
- candidate 제외 사유 기록
- noise summary
- context 구성
- supporting evidence 구성
- security hint 생성
- LLM 입력 artifact 생성

대표 의미 경계:

~~~text
candidate
= Stage1 검토 대상

candidate-excluded
= 후보에서 제외
!= benign
!= normal
!= safe

context-only
= finding 해석용 문맥
!= finding 자동 승격

supporting event
= 주변 참고 요청
!= finding
~~~

### 7.3 Shared Security Signal Adapter in Prepare

Prepare는 `src/prepare/shared_signal_adapter.py`를 통해 shared signal observation을 사용한다.

이 adapter의 역할은 shared observation을 Prepare 입력 surface에 투영하고 기존 hint 관계와 연결하는 것이다.

중요한 소유권 경계는 다음과 같다.

~~~text
Shared Security Signal Extractor
  -> deterministic observation facts

Prepare
  -> score
  -> reason_hints
  -> candidate policy
  -> filtering policy

Shared Extractor
  != candidate policy owner
  != severity owner
  != verdict owner
~~~

현재 Prepare는 shared observation을 사용하더라도 candidate/scoring/filtering 의미의 최종 소유권을 유지한다. shared signal 계층을 사용한다는 사실이 Prepare의 전체 detection policy를 extractor로 이전했다는 뜻은 아니다.

### 7.4 Stage1

`src/llm_stage1_classifier.py`는 Prepare candidate별 evidence 기반 LLM classification을 수행한다.

Stage1 결과에는 candidate에 대한 verdict, severity, confidence 및 분석 근거가 포함될 수 있다.

Stage1 역시 Apache logs-only evidence boundary를 넘는 공격 성공 사실을 새로 관찰할 수는 없다.

### 7.5 Security Standards Mapping

`src/security_standards_mapping.py`는 Stage1 결과와 Prepare evidence를 입력으로 deterministic standards enrichment를 생성한다.

현재 taxonomy surface는 OWASP Top 10, CWE, WSTG다.

~~~text
Security Standards Mapping
= deterministic taxonomy enrichment

!= detector
!= vulnerability confirmation
!= exploit success confirmation
~~~

### 7.6 Stage2 Report Input과 Security Standards Summary

`src/llm_stage2_reporter.py`는 Stage1 결과를 먼저 deduplicate하고 Prepare context와 함께 Stage2 report input을 구성한다.

이 과정에서 `src/security_standards_summary.py`가 deduplicated finding 집합의 standards mapping을 deterministic하게 집계한다.

~~~text
Stage1 results
  -> deduplicated findings
  -> Security Standards Summary
  -> Stage2 report input
~~~

~~~text
Security Standards Summary
= deduplicated finding aggregate

counting unit
= deduplicated_finding

!= detector
!= compliance score
!= vulnerability confirmation
~~~

Viewer의 표시용 top-N finding 배열 자체를 전체 Standards Summary 계산 입력으로 사용하지 않는다.

### 7.7 Stage2 Report Synthesis

Stage2 LLM은 이미 구성된 report input을 바탕으로 finding 중심의 최종 report를 합성한다.

즉 Security Standards Summary는 Stage2 LLM 호출 이후의 후처리가 아니라 **Stage2 입력 구성 단계에서 먼저 계산되는 deterministic aggregate**다.

Stage2는 여러 candidate 결과와 구조화된 문맥을 사람이 읽을 수 있는 보고서 관점에서 정리하지만, Apache 로그에서 관찰되지 않은 실행 성공·침해 사실을 새 evidence로 만들지 않는다.

---

## 8. Shared Security Signal Observation

`src/security_signals/extractor.py`는 Prepare와 Live가 공통으로 사용할 수 있는 **순수 deterministic observation 계층**이다.

현재 extractor의 기본 계약은 다음과 같다.

- DB / file / network I/O를 수행하지 않는다.
- caller가 제공한 text surface만 관찰한다.
- URL decode와 HTML entity decode variant를 제한적으로 생성한다.
- approved narrow rule allowlist만 적용한다.
- signal evidence와 provenance를 반환한다.
- 공격 verdict, severity, candidate selection을 직접 만들지 않는다.

현재 주요 signal family에는 제한된 SQL 구조, XSS event-handler 구조, command-separator 구조, PHP filter/resource 구조가 포함된다.

### 8.1 Prepare 사용

Prepare는 `prepare_compat_v1` profile과 adapter를 통해 shared observation을 사용한다.

Prepare의 기존 score/candidate/filtering 정책은 별도 계층에 남는다.

### 8.2 Live 사용

Live는 `web/services/live_security_observation.py`를 통해 `live_target_v1` profile의 observation을 사용한다.

Live Security Observation의 핵심 축은 다음과 같다.

~~~text
processing_status
  complete
  partial
  unavailable
  error

assessment
  review_required
  no_signal
  undetermined
~~~

이 두 축은 다른 의미다.

~~~text
review_required
!= attack verdict
!= severity
!= exploit success confirmation

no_signal
!= benign
!= safe
~~~

Live adoption layer는 shared extractor의 모든 rule을 자동으로 받아들이지 않고 승인된 signal/rule allowlist를 별도로 유지한다.

---

## 9. Artifact와 DB Output

### 9.1 Job-scoped artifacts

`full_report` Worker는 Job별 artifact root를 사용한다.

대표 정상 산출물:

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

artifact는 분석 단계의 파일 산출물이며, DB에는 큰 payload 전체보다 Job 상태, 요약, lifecycle 및 artifact 경로 metadata를 보관한다.

### 9.2 MariaDB 역할 분리

~~~text
원천 로그
  apache_access_logs
  apache_security_logs
  apache_error_logs

Job 실행
  analysis_jobs

Live selected-input identity
  analysis_job_selected_input_rows

Lifecycle
  job_events

결과 / artifact index
  analysis_reports
~~~

`analysis_jobs`는 실행 queue다.

`analysis_job_selected_input_rows`는 Live selected-input Job의 입력 identity를 보존한다.

`job_events`는 Job lifecycle과 stage trace를 보관한다.

`analysis_reports`는 완료 결과의 요약과 artifact metadata를 색인한다.

Sliding Window / rollup의 operator queue는 이 DB-backed Analysis Job 실행 queue와 다른 개념이다.

---

## 10. Job Detail과 Analysis Viewer

### 10.1 Job Detail

Job Detail은 **결과가 어떤 Job과 lifecycle, artifact를 거쳐 만들어졌는지 추적하는 운영 화면**이다.

대표적으로 다음 정보를 연결한다.

- Job ID와 analysis mode
- input 종류
- status
- lifecycle event
- artifact root
- 분석 산출물
- Provider/usage 관련 저장 정보가 있는 경우 해당 정보
- Analysis Viewer 진입

### 10.2 Analysis Viewer

Analysis Viewer는 완료된 `viewer_payload.v1`과 관련 artifact를 해석·표시하는 read-only interpretation layer다.

Viewer는 다음 의미를 새로 만들지 않는다.

- Stage1/Stage2 verdict 변경
- severity 재계산
- confidence 재계산
- Standards Mapping/Summary 재계산
- Context의 Finding 승격
- 공격 성공 여부 추론

Viewer는 표시 안전성과 가독성을 위해 sanitize 또는 presentation label을 적용할 수 있지만, source `viewer_payload`의 분석 의미를 변경하지 않는다.

정보 역할은 다음처럼 분리한다.

~~~text
Finding
  주요 탐지 요청

Context
  Finding 해석을 위한 문맥 / 집계 정보

Supporting Event
  Finding 주변의 참고 요청
~~~

---

## 11. Apache Logs-only Evidence Boundary

현재 runtime의 핵심 의미 경계는 Apache logs-only다.

~~~text
Apache logs-only
!= exploit success confirmation
!= command execution confirmation
!= compromise confirmation
!= vulnerability existence confirmation
!= file exposure confirmation
!= browser execution confirmation
!= DB result confirmation
!= outbound callback confirmation
~~~

HTTP status, response size, Content-Type, route, User-Agent, source IP 또는 특정 문자열 하나만으로 공격 성공·침해·유출을 확정하지 않는다.

Prepare hint, Stage1/Stage2 결과, Standards Mapping/Summary, Live Security Observation, Viewer 중 어느 계층도 **관찰되지 않은 성공 사실을 새 evidence처럼 만들 수 없다.**

세부 허용/금지 표현과 POST body, auth, file operation, protocol anomaly, Viewer 표시 기준은 [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)를 따른다.

---

## 12. Current Runtime 밖의 코드와 검증 자산

저장소에는 현재 사용자 `full_report` runtime 외의 실험·검증·후속 구조도 존재한다.

대표적으로:

- Prepare regression fixtures
- Stage dry-run regression
- OWASP CRS / CSIC external benchmark
- Prepare full-output comparison harness
- Sliding Window
- Rollup
- operator queue
- windowed_triage 관련 자산

이들은 source가 존재하더라도 모두 현재 사용자 runtime의 실선으로 해석하지 않는다.

~~~text
Current runtime
= Apache / MariaDB / Web-Live / Analysis Job / Worker /
  full_report pipeline / Job Detail / Analysis Viewer

Offline verification
= fixture / regression / benchmark / harness

Separate or post-final paths
= sliding window / rollup / operator queue / windowed_triage 등
~~~

각 항목의 Final 범위 여부는 [final/final-scope.md](./final/final-scope.md), 특정 revision의 실제 검증 결과는 [final/final-verification-record.md](./final/final-verification-record.md)에서 관리한다.

---

## 13. Architecture Boundaries

현재 구조를 해석할 때 다음을 유지한다.

- Live Monitoring은 `apache_security_logs` 관찰 화면이지 Stage1/Stage2 실행 화면이 아니다.
- Live selected-input은 정확한 DB row identity를 보존하는 Job 입력 방식이다.
- `full_report`는 현재 Analysis Job의 canonical analysis mode다.
- Shared Security Signal Extractor는 observation 계층이며 Prepare/Live policy 전체의 owner가 아니다.
- Prepare는 candidate와 context를 구분하고 candidate-excluded를 안전 판정으로 사용하지 않는다.
- Standards Mapping/Summary는 taxonomy enrichment/aggregate이지 detector가 아니다.
- Job Detail은 lifecycle과 artifact 추적 화면이고 Analysis Viewer는 결과 해석 화면이다.
- Viewer는 payload를 표시할 뿐 새로운 보안 판정을 만들지 않는다.
- no-data는 로그/입력 부재 결과이지 정상·안전 판정이 아니다.
- Provider-backed Stage1/Stage2는 외부 설정, credential, network/provider 상태의 영향을 받는다.
- source 존재, test 존재, historical PASS는 특정 현재 revision의 runtime PASS와 같은 뜻이 아니다.

---

## 14. 관련 기준 문서

역할별 기준 문서는 다음과 같이 분리한다.

| 문서 | 책임 |
| --- | --- |
| [README.md](../README.md) | 프로젝트 목적, 상위 흐름, 처음 읽는 사람을 위한 소개 |
| **현재 문서** | 현재 runtime의 코드 경계와 데이터 흐름 |
| [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md) | 로그 기반 해석의 canonical 의미 경계 |
| [final/final-scope.md](./final/final-scope.md) | Final / Conditional / Deferred 범위 관리 |
| [final/final-status-and-freeze-criteria.md](./final/final-status-and-freeze-criteria.md) | freeze 및 promotion 판정 규칙 |
| [final/final-verification-record.md](./final/final-verification-record.md) | revision별 실제 검증 evidence |
| [docs/README.md](./README.md) | 전체 문서 허브 |
| [design/README.md](./design/README.md) | 상세 설계 문서 색인 |
| [operations/README.md](./operations/README.md) | 실행·DB·Worker 운영 문서 색인 |

Architecture 문서에는 과거 promotion 상태나 테스트 숫자를 고정하지 않는다. 해당 정보는 책임 문서에서 관리하고, 이 문서는 **현재 코드가 실제로 어떻게 연결되어 있는지**를 설명하는 데 집중한다.
