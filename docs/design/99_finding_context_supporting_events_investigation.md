# 99 Finding Context Supporting Events Investigation

- 문서 상태: investigation / finding-context-supporting_events 분리 조사
- 기준 커밋: `3ab275b29f8a77db2e75569f5e046be4ec90ff72`
- 관련 기준: [Apache logs-only evidence boundary](../00_apache_logs_only_evidence_boundary.md)

## 1. 현재 증상 요약

Web UI payload detail 화면에는 `findings`와 `contexts` preview가 표시된다. 그러나 특정 finding 선택 시 `Related Contexts` 또는 `Related Supporting Events`가 0으로 보이는 사례가 있다. 현물 `viewer_payload.v1` artifact 조사에서는 top-level `contexts`와 `supporting_events`가 존재하는 payload에서도 finding 내부에 명시적 relation id 필드가 없었다.

중요한 제약은 다음과 같다.

- Web UI는 read-only 표시 계층이며 security meaning, severity, category, verdict를 재계산하지 않는다.
- Apache access log만으로 raw POST body, response body, DB result, browser execution, login/account takeover success, credential stuffing success, lockout, upload/delete/TRACE/XST/CORS/protocol bypass success, server compromise success, static file existence, file exposure, crawler identity, site structure, application route existence 등을 단정하지 않는다.
- `status_code=200`, `text/html`, `response_body_bytes`, lab UA, source IP, route, product name은 성공 증거가 아니다.

## 2. 조사한 파일 목록

| 영역 | 파일 |
|---|---|
| prepare | `src/prepare_llm_input.py`, `src/prepare/*` |
| Stage1 | `src/llm_stage1_classifier.py` |
| Stage2 | `src/llm_stage2_reporter.py` |
| pipeline/viewer payload | `src/run_analysis_pipeline.py`, `src/viewer_payload_builder.py`, `src/full_report_job_runner.py` |
| DB job | `src/analysis_job_worker.py`, `web/services/analysis_job_repository.py`, `web/services/analysis_job_policy.py`, `web/app.py` |
| file report viewer | `web/services/report_loader.py`, `web/routes/reports.py` |
| template | `web/templates/payload_detail.html` |
| tests | `tests/test_viewer_payload_builder.py`, `tests/test_web_job_viewer_route.py`, `tests/test_full_report_job_runner.py`, `tests/test_analysis_job_worker.py`, `tests/test_web_loader_run_dir_scan.py` |
| docs | `docs/00_apache_logs_only_evidence_boundary.md`, `docs/design/99_pipeline_run_dir_output_layout_plan.md`, `docs/design/99_web_ui_viewer_payload_display_plan.md`, `docs/operations/README.md` |

Note: requested root-level `run_analysis_pipeline.py` does not exist; the implementation is `src/run_analysis_pipeline.py`.

## 3. Artifact 샘플별 counts

Repo 안의 `viewer_payload.v1` 파일 36개를 조사했다. finding 내부의 relation-like key는 전체적으로 `context_only`만 관찰되었고, `related_contexts`, `related_context_ids`, `supporting_event_ids`, `supporting_events` 같은 명시 relation 필드는 발견되지 않았다.

| viewer_payload path | findings | contexts | supporting_events | finding relation field |
|---|---:|---:|---:|---|
| `runs/jobs/5/viewer_payload.json` | 5 | 2 | 0 | `context_only` only |
| `runs/jobs/4/viewer_payload.json` | 5 | 2 | 0 | `context_only` only |
| `runs/obs_opencart_v2_001_current_dryrun/viewer_payload.json` | 5 | 6 | 3 | `context_only` only |
| `runs/obs_juiceshop_proxy_v2_001_current_dryrun/viewer_payload.json` | 3 | 6 | 3 | `context_only` only |
| `runs/obs_php_sample_v2_error_heavy_external_001/viewer_payload.json` | 12 | 3 | 0 | `context_only` only |
| `reports/security_viewer_payload.json` | 12 | 5 | 3 | `context_only` only |
| `lab/op-security_2026-05-02_12-40-00_to_2026-05-02_12-46-00_kst_viewer_payload.json` | 3 | 2 | 40 | `context_only` only |
| `runs/webui_run_dir_smoke_actual_2026-05-10/viewer_payload.json` | 2 | 3 | 0 | `context_only` only |

대표 run 주변 artifact 비교:

| run | llm_input candidates | llm_input supporting_events | stage2 top_incidents | stage2 supporting_events | viewer findings | viewer contexts | viewer supporting_events | 해석 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `runs/jobs/5` | 5 | 0 | 5 | 0 | 5 | 2 | 0 | prepare 시점부터 supporting_events가 0 |
| `runs/jobs/4` | 5 | 0 | 5 | 0 | 5 | 2 | 0 | prepare 시점부터 supporting_events가 0 |
| `runs/obs_opencart_v2_001_current_dryrun` | 5 | 3 | 5 | 3 | 5 | 6 | 3 | supporting_events 보존 확인 |
| `runs/obs_php_sample_v2_error_heavy_external_001` | 12 | 0 | 12 | 0 | 12 | 3 | 0 | prepare 시점부터 supporting_events가 0 |

## 4. Finding to Contexts 흐름도

| 단계 | 입력 | 출력/필드 | 현재 관찰 | 손실 가능 지점 |
|---|---|---|---|---|
| prepare | export rows | `analysis_candidates`, `*_summaries`, `ip_behavior_aggregates` | context collection은 top-level summary로 생성된다. candidate 내부에는 context relation id가 없다. | relation contract 없음 |
| Stage1 | `analysis_candidates` | `results` | `Stage1Result` schema는 candidate 판정 필드 중심이며 relation field가 없다. | relation contract 없음 |
| Stage2 | `stage1_results`, `llm_input` | `top_incidents`, context summary collections | `build_report_input()`가 context collections를 보존하지만 `top_incidents`에 related context id를 붙이지 않는다. | relation contract 없음 |
| viewer_payload builder | stage2 input, stage1, llm_input | `findings`, `contexts`, `supporting_events` | `build_finding()`은 relation field를 생성하지 않는다. `build_context_item()`은 context-only collection만 만든다. | 명시 relation 미생성 |
| file report Web route | viewer_payload | sanitized findings/context preview | `sanitize_payload_findings()`가 허용 필드만 새 dict로 구성한다. 나중에 builder가 relation field를 추가해도 sanitizer가 보존하지 않으면 template에 전달되지 않는다. | sanitizer 필드 drop 가능 |
| DB job Web route | DB `analysis_reports.viewer_payload_path` | 같은 payload template | `web/app.py`도 같은 sanitizer와 template을 사용한다. artifact path 자체는 job root 아래에서 보존된다. | relation field drop 가능 |
| template | sanitized findings + raw contexts | JS detail panel | 현재 JS가 `request_id`, `src_ip`, `uri`, category, hint prefix 등으로 display-only match를 계산한다. 명시 relation을 읽지는 않는다. | 표시 계층 휴리스틱 의존 |

현재 가장 중요한 결론은 finding-context 관계가 prepare/Stage1/Stage2/viewer_payload schema 어디에서도 명시 contract로 생성되지 않는다는 점이다. Web template의 `getRelatedContexts()`는 display-only association이라고 주석을 달고 있지만, 실제로는 payload에 없는 관계를 클라이언트에서 휴리스틱으로 계산한다. 이는 severity/category/verdict를 올리는 보안 판정은 아니지만, “Web UI는 관계를 새로 추론하지 않는다”는 정책과는 정합성을 재검토해야 한다.

## 5. supporting_events 흐름도

| 단계 | 동작 | 현재 관찰 | 손실 가능 지점 |
|---|---|---|---|
| prepare 생성 | `build_supporting_events(filtered_rows, candidates, min_score)`는 고신호 candidate 주변의 filtered row 중 query string과 시간/endpoint 조건을 만족하는 row를 context-only event로 만든다. | high signal candidate가 없거나 주변 filtered row 조건이 맞지 않으면 빈 배열이 정상이다. | 정상 0 가능 |
| prepare demotion | `reduce_repeated_auth_candidates()`와 `reduce_repeated_sensitive_path_candidates()`는 대표 candidate 제한을 넘는 반복 row를 `auth_behavior_support` 또는 `sensitive_path_probe_support` supporting event로 내린다. | 반복 auth/sensitive path 조건과 representative limit을 넘어야 생성된다. | 정상 0 가능 |
| llm_input | top-level `supporting_events`와 `meta.counts.supporting_events`를 저장한다. | jobs 4/5와 error-heavy run은 이 단계부터 0이다. | prepare 조건 미충족 |
| Stage2 input | `llm_stage2_reporter.build_report_input()`가 `supporting_events[:20]`을 포함한다. | nonzero sample은 Stage2 input에도 보존된다. | Stage2 input 단독 사용 시 20개 cap |
| viewer_payload | builder가 `stage2_report_input.supporting_events + llm_input.supporting_events`를 de-dup해 top-level `supporting_events`로 보존한다. | pipeline에서 llm_input을 같이 넘기면 20개 cap을 보완할 수 있다. | llm_input 없이 builder를 실행하면 cap 영향 가능 |
| Web UI | template이 top-level supporting events를 읽고 finding과 휴리스틱 매칭한다. | finding 내부 relation id는 없다. | relation contract 없음, display heuristic 의존 |

## 6. 원인 분류

### Confirmed

- `src/viewer_payload_builder.py`의 `build_finding()`은 `related_contexts`, `related_context_ids`, `supporting_event_ids` 같은 relation field를 만들지 않는다.
- 현물 `viewer_payload.v1` 36개에서 finding 내부 relation-like field는 `context_only`만 발견되었다.
- `web/routes/reports.py`와 `web/app.py`는 template에 넘길 `findings`를 `sanitize_payload_findings()`로 재구성한다. 현재 sanitizer는 relation field를 보존하지 않는다.
- `web/templates/payload_detail.html`은 raw `contexts`/`supporting_events` 배열을 읽지만, finding 쪽은 sanitized finding을 사용한다.
- `runs/jobs/4`, `runs/jobs/5`, `runs/obs_php_sample_v2_error_heavy_external_001`의 `supporting_events=0`은 `llm_input.json`부터 0이므로 viewer_payload 생성 과정에서 drop된 사례가 아니다.
- `runs/obs_opencart_v2_001_current_dryrun`은 `llm_input -> stage2_report_input -> viewer_payload`에서 `supporting_events=3`이 보존된다.

### Likely

- Finding to Contexts 문제의 주 원인은 viewer payload schema/contract에 명시 relation 필드가 없고, Web UI가 임시 display-only 매칭에 의존하는 구조다.
- `Related Contexts=0`은 payload에 context가 없어서가 아니라, context summary 안의 `sample_request_ids`, `sample_paths`, `path_counts`, `src_ip`, category/hint prefix가 selected finding과 template heuristic 조건으로 맞지 않아서 발생할 수 있다.
- `supporting_events=0`은 많은 sample/run에서 정상 케이스일 수 있다. 생성 대상이 filtered row 주변 고신호 candidate 또는 반복 auth/sensitive-path demotion으로 제한되어 있기 때문이다.

### Unknown

- 어떤 product requirement가 “Finding과 Contexts는 명시 relation id로 연결되어야 한다”고 요구하는지 아직 문서 contract가 없다.
- relation id를 생성한다면 source-of-truth를 prepare 단계에 둘지, viewer_payload builder의 deterministic adapter 단계에 둘지 결정이 필요하다.
- DB-backed job 화면에서 관찰된 “연결이 약함”이 file report viewer와 완전히 같은 원인인지, 특정 job artifact의 llm_input 누락/partial resume와 결합된 현상인지는 추가 재현이 필요하다.

### Not a bug / expected behavior 가능성

- `supporting_events`가 0인 것 자체는 버그가 아닐 수 있다. prepare 조건상 생성 대상이 없으면 빈 배열이 정상이다.
- context summary가 존재해도 특정 finding과 직접 연결되지 않는 것은 현재 schema에서는 정상이다. 다만 UI가 “Related”라고 표현하면 사용자는 명시 관계가 있다고 기대할 수 있다.

## 7. 수정 후보

### 코드 수정이 필요한 경우

1. 명시 relation contract를 도입한다.
   - 후보 파일: `src/prepare_llm_input.py`, `src/llm_stage2_reporter.py`, `src/viewer_payload_builder.py`
   - 가능한 필드: `finding.related_context_ids`, `finding.supporting_event_ids`, context/event의 stable id
   - 제약: relation은 Apache logs-only metadata 기반 연결이어야 하며 success/severity/category/verdict를 새로 만들면 안 된다.

2. viewer payload sanitizer가 relation field를 보존하게 한다.
   - 후보 파일: `web/routes/reports.py`, `web/app.py`
   - 이유: 현재 template의 finding JSON은 sanitized output이므로 builder가 relation field를 추가해도 UI로 전달되지 않는다.

3. template은 명시 relation만 표시하고 휴리스틱 matching을 제거하거나 fallback으로 격하한다.
   - 후보 파일: `web/templates/payload_detail.html`
   - 제약: Web UI에서 relation을 새로 추론하지 않는다. 보안 의미 승격도 금지한다.

4. Stage2 input의 `supporting_events[:20]` cap과 viewer builder 입력 조합을 contract로 고정한다.
   - 후보 파일: `src/llm_stage2_reporter.py`, `src/viewer_payload_builder.py`, `src/run_analysis_pipeline.py`
   - 현재 pipeline은 llm_input을 builder에 넘기므로 보존 가능하지만, resume/수동 실행에서 llm_input이 빠지면 cap 영향이 생길 수 있다.

### 문서/테스트만 필요한 경우

1. `supporting_events=0`이 정상인 조건을 문서화한다.
2. viewer payload contract test를 추가해 top-level `contexts`/`supporting_events` 보존과 relation field 유무를 명확히 한다.
3. Web UI test에서 “context-only items are not promoted”뿐 아니라 “relation field가 있을 때만 related로 표시” 같은 contract를 추가한다.

## 8. 권장 다음 작업 순서

1. 최소 재현 테스트 작성
   - input fixture: context가 있으나 finding relation field가 없는 viewer_payload
   - 기대: UI가 relation을 새로 만들지 않는 정책이면 `Related`가 explicit relation 없음으로 표시되어야 한다.

2. schema/contract 결정
   - `viewer_payload.v1`에 relation ids를 추가할지, `viewer_payload.v2`로 올릴지 결정한다.
   - relation 생성 계층은 prepare 또는 viewer_payload builder 중 하나로 고정한다.

3. prepare/viewer_payload builder 수정
   - stable context/event id 생성
   - finding에 relation id 연결
   - top-level context/event는 context-only guardrail 유지

4. sanitizer/route 수정
   - `sanitize_payload_findings()`가 relation id만 pass-through하도록 제한적으로 확장한다.
   - raw body, response body, DB result 같은 비가시 evidence는 추가하지 않는다.

5. Web UI 표시 수정
   - explicit relation id를 표시만 한다.
   - 휴리스틱 matching은 제거하거나 “possible context match”로 별도 격하한다.

6. DB-backed job artifact smoke
   - `analysis_reports.viewer_payload_path`가 `runs/jobs/<id>/viewer_payload.json`을 가리키고, payload relation field가 route/template까지 보존되는지 확인한다.

## 9. 현재 판단

Finding to Contexts 연결 문제는 Web UI 색상/레이아웃 문제가 아니다. 현재 구조에서는 prepare부터 viewer_payload까지 명시 relation contract가 없고, web sanitizer/template도 명시 relation을 보존/소비하지 않는다. 따라서 우선 수정해야 할 계층은 backend 판정 로직이나 DB schema가 아니라 viewer payload contract와 read-only display contract다.

supporting_events 문제는 두 갈래다. `supporting_events=0`은 prepare 단계에서 생성 대상이 없으면 정상이다. 반면 nonzero event가 있는 run에서는 llm_input, Stage2 input, viewer_payload까지 보존되는 사례가 확인되었다. 따라서 현 시점에서 “viewer_payload builder가 supporting_events를 일반적으로 drop한다”는 증거는 없다. 다만 Stage2 input의 20개 cap, llm_input 없는 수동 builder 실행, Web UI의 휴리스틱 related matching은 후속 contract test가 필요하다.
