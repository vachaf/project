# Current Architecture

## 1. 문서 기준

- 기준 revision: ec4c7a60841501fc824a6fe6d6a311639a4d2194
- 기준일: 2026-09-10
- 문서 상태: 2026년 9월 Final 기준의 canonical runtime architecture
- Final 범위: [final/final-scope.md](./final/final-scope.md)
- 문서 상태·권위 정책: [final/documentation-naming-status-policy.md](./final/documentation-naming-status-policy.md)
- design 문서 index: [design/README.md](./design/README.md)
- 증거 해석 기준: [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)

이 문서는 현재 main source의 구조를 설명한다. source 또는 test 파일이 존재한다는 사실은 실제 배포, 통합, 회귀, E2E가 완료됐다는 뜻이 아니다. 실제 freeze revision의 실행 결과는 별도 Final verification record에서 관리한다.

## 2. Final Runtime Architecture

Final runtime은 사용자가 시간 범위 기반 full_report Job을 등록하고, Worker가 기존 분석 파이프라인을 실행한 뒤 Report Viewer에서 결과를 읽는 흐름이다.

~~~text
Apache access / security / error logs
        |
        v
Log shipper / ingest
src/apache_log_shipper.py
        |
        v
MariaDB
apache_access_logs / apache_security_logs / apache_error_logs
        |
        +-------------------------------+
        |                               |
        v                               v
Web UI                            analysis_jobs
시간 범위 full_report 등록             PENDING
        |                               |
        +-------------> Analysis Job Worker
                             atomic claim
                             RUNNING
                               |
                               v
                         Export for time range
                               |
                               v
                         Prepare deterministic preprocessing
                               |
                               v
                         Stage1 LLM Classification
                               |
                               v
                         Deterministic Security Standards Mapping
                               |
                               v
                         Stage2 Report Synthesis
                               |
                               v
                         Deterministic Security Standards Summary
                               |
                               v
                  viewer_payload / reports / job-scoped artifacts
                               |
                               v
                  analysis_reports + job_events + terminal job status
                               |
                               v
                         Report Viewer / artifact routes
~~~

Security Standards Mapping은 detector나 취약점 확인 기능이 아니다. Stage1 결과와 Prepare evidence에 deterministic taxonomy 정보를 보강한다. Security Standards Summary는 이미 dedup된 finding을 집계하는 deterministic aggregate이며, 별도 detector가 아니다.

## 3. 데이터 흐름

### 3.1 Apache 로그에서 MariaDB까지

src/apache_log_shipper.py는 Apache access, security, error 로그를 파싱하여 MariaDB의 apache_access_logs, apache_security_logs, apache_error_logs에 저장한다. 파일 offset 상태와 실패 batch spool/replay는 shipper의 운영 책임이다.

시간 저장은 UTC naive DATETIME(3) 기준이다. Web UI의 분석 요청은 Asia/Seoul 입력을 허용하고, Job 정책 계층이 DB 조회에 사용할 UTC 범위로 정규화한다. 이 문서는 해당 변환의 source 존재를 설명할 뿐 실제 DB 연결이나 운영 결과를 검증한 기록은 아니다.

### 3.2 Job 생성에서 Worker까지

Web UI는 dashboard, 새 Job 등록, Job detail, artifact, viewer route를 제공한다. 새 Job은 analysis_jobs에 full_report mode의 PENDING row를 만들거나, 동일한 진행 중 요청이면 기존 row를 반환한다.

Analysis Job Worker는 analysis_jobs에서 PENDING full_report Job 하나를 atomic claim하여 RUNNING으로 전환한다. loop 실행 경로는 시간 범위를 export_db_logs_cli.py에 전달하고, 결과 export를 job별 artifact root에 연결한 뒤 run_analysis_pipeline.py를 실행한다. one-shot 경로는 run_pipeline 옵션이 없으면 claim 상태 확인까지만 하므로, claim 자체와 pipeline 실행을 같은 완료 사실로 해석하지 않는다.

### 3.3 분석 결과에서 Viewer까지

정상 pipeline 경로에서는 Export → Prepare → Stage1 → deterministic Security Standards Mapping → Stage2 → deterministic Security Standards Summary → viewer_payload 순서로 진행된다. Worker는 artifact 경로와 요약을 analysis_reports에 저장하고 job_events에 단계 이벤트를 남긴 뒤 terminal 상태를 갱신한다. no-data export는 pipeline을 강제로 진행하지 않는 별도 결과이며, 로그 없음은 관찰 신호 없음이나 안전을 뜻하지 않는다.

## 4. Job / Worker lifecycle

~~~text
Web UI 또는 API
  -> analysis_jobs: PENDING
  -> JOB_CLAIMED / RUNNING
  -> JOB_STARTED
  -> EXPORT_STARTED
     -> EXPORT_FAILED -> JOB_FAILED / FAILED
     -> EXPORT_NO_DATA -> JOB_NO_DATA -> REPORT_SAVE_STARTED
     -> EXPORT_COMPLETED -> PIPELINE_STARTED
        -> PIPELINE_FAILED -> JOB_FAILED / FAILED
        -> PIPELINE_COMPLETED -> REPORT_SAVE_STARTED
  -> REPORT_SAVE_COMPLETED -> JOB_SUCCEEDED / SUCCEEDED
  -> REPORT_SAVE_FAILED -> JOB_FAILED / FAILED
~~~

- 지원하는 Final analysis mode는 full_report다.
- Worker는 Job별 artifact root를 project root 아래에서 사용하며, 임의 경로를 Web UI 입력으로 받지 않는다.
- full_report의 정상 결과에는 export, Prepare, Stage1, Stage2, report, viewer_payload artifact가 필요하다.
- analysis_reports는 artifact metadata와 경로를 보관하고, job_events는 lifecycle 및 단계 기록을 보관한다.
- cancel, requeue, retry UX와 worker health dashboard 확대는 Final runtime 범위 밖이다.

## 5. Analysis Pipeline

### 5.1 Export와 Prepare

Export는 요청된 시간 범위의 원천 로그를 pipeline 입력으로 만든다. Prepare는 deterministic preprocessing으로 candidate, noise, filtered reason, context와 supporting evidence를 구성한다.

candidate-excluded는 분석 후보에서 제외됐다는 뜻이지 benign, normal 또는 safe 판정이 아니다. context-only 역시 finding 또는 incident로 자동 승격되지 않는다.

### 5.2 Stage1과 Security Standards Mapping

Stage1은 Prepare candidate별 evidence 기반 LLM classification을 수행한다. 현재 source에서 Stage1 결과 row 생성 직후 security_standards_mapping.py의 deterministic mapping이 standards_mapping으로 추가된다.

~~~text
Prepare candidate
  -> Stage1 classification result
  -> deterministic standards_mapping enrichment
~~~

Mapping은 관찰된 신호와 OWASP Top 10, CWE, WSTG 관계를 보수적으로 표현한다.

~~~text
Security Standards Mapping
= deterministic enrichment
!= detector
!= vulnerability confirmation
!= exploit success confirmation
~~~

### 5.3 Stage2와 Security Standards Summary

Stage2는 Stage1 결과를 dedup하여 finding 중심 report input을 만들고 report를 합성한다. 그 과정에서 security_standards_summary.py는 dedup된 Stage1 결과를 입력으로 deterministic aggregate를 만든다.

~~~text
deduplicated Stage1 findings
  -> deterministic Security Standards Summary
  -> stage2 report input
  -> viewer_payload copy-through
  -> Report Viewer display
~~~

Summary의 counting unit은 deduplicated finding이다. Viewer의 표시 목록은 top-N 또는 fallback shape일 수 있으므로 Viewer 배열 자체를 전체 summary 계산 입력으로 사용하지 않는다.

~~~text
Security Standards Summary
= deduplicated finding aggregate
!= finding-level mapping
!= compliance score
!= vulnerability confirmation
~~~

## 6. Artifact / DB output

### 6.1 Job-scoped artifact

full_report Worker는 Job별 artifact root를 사용한다. 정상 결과에서 확인하는 대표 artifact는 다음과 같다.

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

artifact는 원본 로그와 분석 단계의 파일 산출물이고, DB에는 큰 JSON 전체 대신 상태, 요약, artifact 경로 같은 metadata를 둔다.

### 6.2 MariaDB의 역할 분리

~~~text
원천 로그
  apache_access_logs
  apache_security_logs
  apache_error_logs

Job 제어와 결과 색인
  analysis_jobs
  job_events
  analysis_reports
~~~

analysis_jobs는 실행 queue다. analysis_reports는 report와 artifact metadata의 색인이고, job_events는 lifecycle trace다. 이 구조는 rollup 결과를 사람이 우선 검토하는 operator queue와 다르다.

## 7. Web / Viewer 역할

Web UI는 분석 시간 범위의 full_report Job 등록, 상태와 job event 조회, 완료 결과의 report 및 viewer_payload 표시를 담당한다. 대표 route surface는 dashboard, 새 Job 등록, Job detail, artifact route, Job viewer와 legacy report route다.

Viewer는 artifact를 해석·표시하는 계층이다.

- Stage1/Stage2 verdict, severity, confidence, standards mapping 또는 summary를 재계산하지 않는다.
- context-only를 finding으로 승격하지 않는다.
- security_standards_summary가 있으면 schema를 확인하고 표시용으로 sanitize한다.
- raw payload와 secret, authorization, cookie, 민감한 원문 노출에 보수적인 경계를 둔다.

Web UI의 read-only 원칙은 보안 결과의 의미를 바꾸지 않는다는 뜻이다. DB-backed Final runtime에서 Job 등록과 상태 조회를 위한 DB write/read는 이 원칙과 충돌하지 않는다.

## 8. Evidence Boundary

Apache logs-only는 관찰된 HTTP metadata와 그로부터 보수적으로 해석 가능한 신호의 경계다.

~~~text
Apache logs-only
!= exploit success confirmation
!= compromise confirmation
!= vulnerability existence confirmation
!= file exposure, browser execution, DB result, outbound callback confirmation
~~~

status_code, content type, response size, route name, user agent 또는 특정 IP만으로 공격 성공·침해·유출을 확정하지 않는다. Mapping과 Summary도 이 경계를 넘는 새 verdict를 만들지 않는다.

세부 금지/허용 표현과 POST body, auth, file operation, protocol anomaly, Viewer 표시 기준은 [00_apache_logs_only_evidence_boundary.md](./00_apache_logs_only_evidence_boundary.md)가 canonical이다.

## 9. Offline Verification Architecture

Offline Verification은 Final runtime과 분리한다.

~~~text
Fixtures / dry-run regression
        |
        +-> Prepare / Stage1 / Stage2 regression evidence
        |
CRS / CSIC benchmark provenance
        |
        +-> source integrity / annotation / semantic validation / controlled review
        |
Prepare full-output harness
        |
        +-> typed capture / identity / comparison building blocks
~~~

- fixture와 regression은 Final runtime의 사용자 Job 흐름이 아니라 검증 근거다.
- CRS와 CSIC는 runtime 제품 경로에 포함하지 않는다.
- benchmark의 historical PASS, baseline, source review는 freeze revision의 current PASS가 아니다.
- harness package와 관련 test source가 있어도 C self-validation, D source/corpus identity, E before baseline, after comparison, compatibility PASS가 완료됐다는 뜻이 아니다.

관련 문서의 현재 권위와 provenance 관계는 [design/README.md](./design/README.md)를 따른다.

## 10. Conditional Final

### 10.1 Shared Security Signal Extractor

Shared Security Signal Extractor는 Conditional Final이며 현재 Final runtime 실선에 넣지 않는다. 설계와 regression/harness 자산은 존재하지만 production runtime 완료로 표현하지 않는다.

승격 전에는 다음이 모두 분리되어 확인돼야 한다.

~~~text
C harness self-validation
  -> D corpus/source identity
  -> E before compatibility baseline
  -> shared extractor implementation
  -> after comparison
  -> Prepare full-output compatibility PASS
~~~

compatibility, corrected, live_adoption expectation family는 서로 대체하지 않는다. extractor는 deterministic signal facts만 공유해야 하며 DB/file/network I/O, score, severity, verdict, candidate selection을 수행하지 않는다.

### 10.2 Live Monitoring v3.1

기준 revision ec4c7a60841501fc824a6fe6d6a311639a4d2194의 main checkout에서 Live Monitoring runtime의 /live route, /api/live/snapshot route, 전용 source 또는 route test는 확인되지 않았다. 이름에 live가 포함된 external benchmark source는 Live Monitoring runtime 구현이 아니다.

따라서 Live Monitoring v3.1은 별도 작업 자산 / main 통합 전의 Conditional Final로 기록하며, 이 문서의 Final runtime diagram에는 포함하지 않는다.

기본 Live Monitoring은 shared extractor 없이 독립적으로 Final 승격할 수 있다. 다만 다음 Live Security Observation과 같은 기능으로 묶지 않는다.

### 10.3 Live Security Observation

Live Security Observation은 shared extractor compatibility와 live_adoption을 모두 선행조건으로 하는 Conditional Final이다.

~~~text
shared extractor compatibility PASS
  -> live_adoption PASS
  -> 제한된 observation 표시
~~~

Live 자체는 공격 verdict를 만들지 않으며, observation도 severity, exploit success, incident verdict를 생성하지 않는다. processing_status와 assessment는 별도 축으로 유지한다.

### 10.4 Live에서 Analysis Job으로의 연결

현재 Final runtime의 분석 진입점은 시간 범위 기반 full_report Job이다. Live 선택 row를 Job에 전달하는 계약과 E2E 연결은 아직 확정되지 않았으므로 Conditional Final로 남긴다.

## 11. Deferred / Post-final

다음은 source나 test 자산 존재 여부와 무관하게 2026년 9월 Final runtime 본편에서 제외한다.

- windowed_triage 사용자 통합
- Sliding Window, Rollup, operator queue 확대와 관련 Web UI
- cancel, requeue, retry UX
- worker health dashboard 확대
- Viewer compare/history, advanced relationship view, standards drill-down/filter/dashboard badge 확대
- WebSocket/SSE Live
- Live duplicate collapse와 Live masking 확장
- 신규 attack family와 추가 fixture/coverage 확대
- observability capability matrix

Deferred는 삭제나 실패가 아니라 Post-final 작업 근거다. operator queue는 analysis_jobs 실행 queue가 아니라 rollup 결과의 사람 검토 queue라는 기존 구분을 유지한다.

## 12. Known Architecture Boundaries

- 이 문서는 checkpoint 기준 source 구조를 설명하며 DB, LLM, network, 실제 Worker 실행, regression, benchmark, E2E를 이번 갱신에서 실행하지 않았다.
- Stage1과 Stage2는 LLM 단계다. source가 존재해도 provider 설정, credential, 실제 호출 성공이나 report 품질을 보장하지 않는다.
- full_report의 Job/Worker/artifact 계약은 source와 test 구조에서 확인했지만, Final freeze revision의 통합 PASS는 별도 verification record가 필요하다.
- no-data Job은 분석 구간에 로그가 없다는 결과일 뿐 관찰 신호 없음, 정상 또는 안전을 의미하지 않는다.
- artifact 보존, raw 데이터 표시, secret redaction과 evidence 표현은 Web/Viewer가 새 보안 의미를 만들지 않도록 제한한다.
- historical benchmark와 design 문서는 삭제하지 않으며, 현재 권위·후속 관계는 design index와 Final 문서 정책으로 관리한다.
