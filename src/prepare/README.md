# src/prepare/

## 1. 역할

`src/prepare/`는 `src/prepare_llm_input.py`가 사용하는 **deterministic preprocessing helper, security hint, context builder, shared-signal adapter**를 관리한다.

`prepare_llm_input.py`는 여전히 Prepare 단계의 coordinator이며, 이 디렉터리의 모듈은 각 세부 책임을 분리한다.

~~~text
export JSON
   |
   v
prepare_llm_input.py
   |
   +-> decoding / normalization
   +-> security hints
   +-> scoring / candidate policy
   +-> filtering / noise
   +-> context summaries
   +-> supporting events
   +-> shared signal adapter
   |
   v
Prepare artifacts
~~~

Prepare의 핵심 목적은 원천 로그에서 **Stage1이 직접 검토할 candidate**와 **해석에 필요한 context/supporting evidence**를 구조화하는 것이다.

전체 분석 pipeline은 [../README.md](../README.md), 전체 runtime architecture는 [../../docs/00_current_architecture.md](../../docs/00_current_architecture.md)를 따른다.

---

## 2. Prepare ownership

Prepare가 소유하는 주요 의미는 다음과 같다.

- candidate score
- candidate selection
- candidate filtering
- filtered reason
- candidate deduplication
- noise aggregation
- supporting-event 구성
- context summary 구성
- Prepare verdict hint / reason hint
- Stage1 입력용 candidate와 evidence 구조

반대로 Shared Security Signal Extractor는 Prepare의 전체 policy owner가 아니다.

~~~text
Shared Security Signal Extractor
  -> deterministic observation facts

Prepare
  -> score
  -> reason_hints
  -> verdict_hint
  -> candidate policy
  -> filtering policy
  -> supporting/context policy
~~~

따라서 shared observation이 존재한다는 사실만으로 candidate, severity, final verdict가 결정되지 않는다.

---

## 3. Prepare output contract

`prepare_llm_input.py`는 export JSON을 입력으로 다음 artifact를 생성한다.

기본 prefix 기반 출력:

~~~text
<base>_llm_input.json
<base>_analysis_candidates.json
<base>_noise_summary.json
<base>_filtered_reasons.json
<base>_filtered_out_rows.json   # --write-filtered-out 사용 시
~~~

`--flat-output-names` 사용 시:

~~~text
llm_input.json
analysis_candidates.json
noise_summary.json
filtered_reasons.json
filtered_out_rows.json          # --write-filtered-out 사용 시
~~~

`--flat-output-names`는 artifact 이름을 바꾸는 옵션이며 candidate/scoring/filtering 의미를 바꾸는 옵션이 아니다.

`filtered_out_rows.json`은 선택 출력이지만 `filtered_reasons.json`은 기본 Prepare output에 포함된다.

---

## 4. Prepare가 만드는 주요 구조

### 4.1 Candidate

Candidate는 Stage1 LLM classification의 직접 입력 대상이다.

~~~text
candidate
= Stage1 검토 대상으로 선택된 row / incident
~~~

Candidate는 deterministic hint와 score, source identity, request/evidence 정보를 가진다.

중복된 source row는 Prepare policy에 따라 incident 기준으로 dedup될 수 있다.

### 4.2 Filtered row / filtered reason

Candidate로 선택되지 않은 row에는 제외 사유가 기록될 수 있다.

~~~text
candidate-excluded
= candidate policy에서 제외됨

!= benign
!= normal
!= safe
~~~

`filtered_reasons.json`은 어떤 이유로 row가 candidate 밖에 있었는지 집계·설명하기 위한 artifact다.

### 4.3 Noise

반복적인 baseline/noise 성격의 요청은 LLM에 raw row 전체를 그대로 보내기보다 aggregation하여 보존할 수 있다.

~~~text
noise aggregation
!= safety verdict
~~~

### 4.4 Supporting Event

Supporting Event는 high-signal candidate 주변의 요청 중 해석에 도움이 되는 참고 event다.

~~~text
supporting event
= candidate 주변의 참고 요청

!= candidate
!= finding
!= incident 자동 승격
~~~

지원 event는 같은 source IP, endpoint/family, 시간적 근접성 등의 bounded context를 사용해 연결될 수 있다.

### 4.5 Context-only collections

현재 대표 context collection:

~~~text
false_positive_review_candidates
probing_sequence_summaries
static_baseline_summaries
crawler_baseline_summaries
sensitive_path_probe_summaries
mixed_baseline_scanner_summaries
ip_behavior_aggregates
auth_behavior_summaries
method_behavior_summaries
protocol_anomaly_summaries
~~~

이 collection은 finding을 새로 만드는 detector가 아니다.

~~~text
context-only
!= finding
!= severity 자동 상승
!= exploit success
~~~

각 collection의 `request_count`는 서로 다른 scope/window를 가질 수 있으므로 같은 사건 수처럼 직접 합산하지 않는다.

---

## 5. 현재 모듈

~~~text
decoders.py
l3_hints.py
models.py
method_summaries.py
protocol_anomalies.py
auth_behavior.py
static_baseline.py
crawler_baseline.py
apache_observability_context.py
sensitive_path_probe.py
ip_behavior.py
probing_sequence.py
mixed_baseline_scanner.py
sqli_hints.py
xss_hints.py
file_disclosure_hints.py
traversal_cmdi_hints.py
shared_signal_adapter.py
~~~

---

## 6. 모듈별 책임

### `decoders.py`

URL decode, HTML entity decode 등 Prepare가 사용하는 decoded variant helper를 관리한다.

Decode된 문자열은 원천 로그 자체가 아니라 분석을 위해 파생된 surface이므로 provenance를 구분해야 한다.

### `l3_hints.py`

기존 내부 파일명 `l3_hints.py`를 유지하고 있지만 현재 책임은 네트워크 L3/transport layer 자체를 분석하는 모듈이라는 의미가 아니다.

현재 여러 application/security hint helper를 포함한다.

대표 영역:

- Log4Shell / JNDI lookup pattern
- SSRF-like target
- Open Redirect
- SSTI
- GraphQL introspection
- XXE-like pattern
- Webshell-like path/query context

이 hint들은 각자 동일한 수준의 전용 detector/verdict를 의미하지 않는다.

~~~text
hint observed
!= dedicated attack verdict
!= vulnerability confirmation
!= exploit success
~~~

### `models.py`

Prepare 내부에서 공유하는 경량 데이터 모델을 관리한다.

### `sqli_hints.py`

SQL Injection 관련 pattern/constants와 educational-search false-positive context helper를 관리한다.

### `xss_hints.py`

XSS 관련 pattern/constants와 educational/search context를 관리한다.

### `file_disclosure_hints.py`

PHP wrapper / file-resource / file-disclosure 관련 deterministic pattern과 helper를 관리한다.

### `traversal_cmdi_hints.py`

Path Traversal과 Command Injection 관련 pattern/constants를 관리한다.

일부 approved CMDi signal은 shared signal adapter와 연결될 수 있지만, candidate score와 최종 Prepare policy는 Prepare가 소유한다.

### `method_summaries.py`

HTTP method behavior summary와 관련 constants를 관리한다.

### `protocol_anomalies.py`

HTTP protocol/request anomaly 관련 context summary를 관리한다.

### `auth_behavior.py`

Login/auth endpoint 요청의 반복·행동 문맥 summary를 관리한다.

~~~text
auth behavior context
!= login success
!= account takeover
!= credential stuffing success
~~~

### `static_baseline.py`

Static/health-like baseline context를 관리한다.

### `crawler_baseline.py`

Crawler-like baseline context를 관리한다.

User-Agent나 요청 패턴만으로 실제 crawler identity를 확정하지 않는다.

### `apache_observability_context.py`

Apache handler, route, proxy, fallback 등 Apache가 노출한 관찰값으로 topology-aware context hint를 만든다.

이 정보는 context이며 공격 성공이나 candidate score를 단독으로 확정하는 증거가 아니다.

### `sensitive_path_probe.py`

민감 경로 probe 성격의 반복 요청 context를 관리한다.

~~~text
sensitive path request
!= resource existence
!= exposure
!= compromise
~~~

### `ip_behavior.py`

Source-IP 단위 aggregate context를 관리한다.

특정 IP 자체를 악성 판정 규칙으로 사용하지 않는다.

### `probing_sequence.py`

시간적으로 연속된 probing-like request sequence summary를 관리한다.

### `mixed_baseline_scanner.py`

Baseline/static/crawler-like 요청과 scanner-like 요청이 섞인 문맥을 요약한다.

### `shared_signal_adapter.py`

`src/security_signals/extractor.py`의 shared observation을 Prepare surface에 투영한다.

현재 adapter는:

- Prepare용 `prepare_compat_v1` input profile 사용
- shared signal을 legacy hint group과 연결
- observation과 hint 관계를 Prepare에 제공

하지만 다음을 직접 수행하지 않는다.

~~~text
score 계산
candidate 선택
severity 결정
Stage1 verdict 생성
final finding 생성
~~~

Prepare의 기존 detector/policy 계층이 이러한 의미의 owner다.

---

## 7. Shared Signal과 Prepare의 경계

Shared extractor와 Prepare의 관계는 다음처럼 이해한다.

~~~text
raw / decoded request surfaces
        |
        v
Shared Security Signal Extractor
        |
        v
observation facts + evidence provenance
        |
        v
Prepare Shared Signal Adapter
        |
        v
Prepare policy
score / reason_hints / candidate / filter
~~~

Shared extractor의 현재 approved narrow allowlist에는 제한된 형태의 다음 구조가 포함된다.

- SQL termination/boolean/union
- XSS event handler
- shell separator command
- PHP filter/resource

Prepare 자체는 이 shared allowlist보다 더 넓은 hint/context policy를 가질 수 있다.

따라서:

~~~text
shared extractor coverage
!= Prepare 전체 coverage
~~~

---

## 8. Source table과 identity

Prepare는 export payload에서 선택된 source table 범위를 분석한다.

대표 source:

- security
- access
- error

일반 `run_analysis_pipeline.py --export-input` 경로에서는 export metadata/count/data를 바탕으로 Prepare source table을 자동 결정할 수 있다.

Prepare 내부에서는 원천 row identity와 dedup된 incident identity를 구분한다.

대표적으로 다음 provenance를 가능한 범위에서 유지한다.

- source table
- log id
- request id
- error link id
- merged source tables
- merged log ids
- incident group key

이 provenance는 Stage1/Stage2/Viewer가 결과 근거를 추적하는 데 사용된다.

---

## 9. Apache logs-only Evidence Boundary

Prepare는 Apache access/security/error log에서 관찰 가능한 정보와 그 deterministic 파생값만 사용한다.

Apache 로그만으로 다음을 확정하지 않는다.

- raw POST body 내용
- 실제 response body 내용
- DB query 실행 결과
- browser JavaScript 실행
- login 성공
- account takeover
- credential stuffing 성공
- file/source disclosure 성공
- path traversal 파일 읽기 성공
- OS command 실행 성공
- server compromise
- external callback 성공
- static file 실제 존재
- 실제 crawler identity
- site structure 존재
- 특정 제품/CMS 존재

또한 다음 값 하나만으로 성공·침해·유출을 확정하지 않는다.

~~~text
status_code
resp_content_type
response_body_bytes
specific IP
specific User-Agent
specific route
product/CMS-looking path
~~~

세부 canonical 기준은 [../../docs/00_apache_logs_only_evidence_boundary.md](../../docs/00_apache_logs_only_evidence_boundary.md)를 따른다.

---

## 10. 변경 시 ownership 원칙

현재 Prepare 모듈 변경에서는 “옛 wrapper를 영구적으로 변경 금지” 같은 과거 refactor 규칙보다 **의미 ownership과 compatibility를 명확히 검증하는 것**을 우선한다.

변경 시 특히 확인해야 할 항목:

- candidate selection 의미가 의도치 않게 바뀌지 않았는가
- scoring threshold/weight가 의도치 않게 바뀌지 않았는가
- filtered reason이 safety verdict로 변질되지 않았는가
- supporting event가 finding으로 승격되지 않았는가
- context collection이 severity/verdict를 암묵적으로 올리지 않는가
- source identity / dedup provenance가 유지되는가
- shared signal adoption이 Prepare 전체 policy ownership을 침범하지 않는가
- Apache logs-only evidence boundary를 넘지 않는가

Mechanical refactor가 필요한 경우에는 output contract와 regression compatibility를 보존해야 한다.

---

## 11. 검증

Prepare 변경의 대표 검증:

~~~bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
~~~

Shared signal 관련 변경이라면 해당 focused test를 추가한다.

대표 예:

~~~bash
python3 -m pytest tests/test_prepare_shared_signal_adoption.py
python3 -m pytest tests/test_prepare_pipe_shared_replacement.py
python3 -m pytest tests/test_shared_security_signal_extractor.py
~~~

변경 범위에 따라 corrected semantics, candidate policy, context summary, external benchmark 관련 focused regression도 추가한다.

고정 fixture 개수나 과거 PASS 숫자는 이 README의 current baseline으로 관리하지 않는다. 실제 검증 여부는 해당 revision에서 실행한 regression/pytest 결과와 Git history를 기준으로 확인한다.

---

## 12. 관련 문서

| 문서 | 역할 |
| --- | --- |
| [../README.md](../README.md) | 전체 분석 runtime / pipeline |
| [../../docs/00_current_architecture.md](../../docs/00_current_architecture.md) | 전체 시스템 runtime architecture |
| [../../docs/00_apache_logs_only_evidence_boundary.md](../../docs/00_apache_logs_only_evidence_boundary.md) | 로그 기반 의미 경계 |

과거 module split round, constants mini-move, 특정 refactor 작업 기록은 historical design/review 문서에 남긴다.

이 문서는 **현재 Prepare가 어떤 output과 policy ownership을 가지며, 하위 모듈이 어떤 책임으로 나뉘는지**를 설명하는 데 집중한다.
