# 99_prepare_module_split_plan

- 문서 상태: P4 prepare module split 진행 계획 / 1차 분리 완료 현황
- 기준 시점: 2026-05-04
- 목적: `src/prepare_llm_input.py`의 책임을 회귀 안전성을 유지하면서 점진적으로 분리한다.

이 문서는 전면 리팩터링 계획이 아니다. 이미 안정화된 작은 단위만 분리하고, behavior 변경과 refactor를 같은 커밋에 섞지 않는 것을 원칙으로 한다.

## 1. 배경

`src/prepare_llm_input.py`는 전처리 파이프라인의 핵심 오케스트레이션 파일이다. 현재도 아래 책임이 남아 있다.

```text
- decoded/text analysis helper 연결
- SQLi / XSS / traversal / HPP / file disclosure hint 생성과 score 반영
- false positive review 후보 분리
- supporting_events
- probing_sequence_summaries
- ip_behavior_aggregates
- sensitive_path_probe_summaries
- mixed_baseline_scanner_summaries
- Stage1/Stage2 입력용 output JSON 생성
- CLI와 파일 입출력
```

반면 아래 영역은 이미 별도 모듈로 분리됐다.

```text
src/prepare/decoders.py
src/prepare/l3_hints.py
src/prepare/models.py
src/prepare/method_summaries.py
src/prepare/protocol_anomalies.py
src/prepare/auth_behavior.py
src/prepare/static_baseline.py
src/prepare/crawler_baseline.py
```

## 2. 현재 회귀 안전장치

분리 전후 기본 검증은 아래 기준으로 본다.

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

현재 기준:

```text
prepare regression: 18 fixtures, warn=0 fail=0
stage dry-run regression: 12 fixtures, warn=0 fail=0
```

## 3. 핵심 원칙

```text
- 동작 변경 없는 mechanical refactor 우선
- 한 번에 한 책임만 분리
- 분리와 기능 개선을 같은 커밋에 섞지 않음
- output JSON 의미와 key 구조를 바꾸지 않음
- reason_hints 이름을 바꾸지 않음
- score / candidate / filtering 기준을 바꾸지 않음
- Stage1 / Stage2 prompt나 schema는 module split과 별도로 관리
- Apache logs-only 원칙 유지
- 실험환경 특화 rule 금지
```

특히 아래는 금지한다.

```text
- raw POST body, response body 원문, DB 결과, 브라우저 실행 여부 사용
- status_code=200, text/html, response_body_bytes만으로 성공/침해/유출 단정
- lab-* UA, 특정 IP, 특정 response size, 특정 제품명, 특정 route에 과적합
```

## 4. 완료된 분리

### 4.1 `decoders.py` — 완료

역할:

```text
- URL decode depth 1/2
- HTML entity decode
- decoded variants 생성
- HTML entity variant 추가
```

유지 조건:

```text
- decode depth 의미 변경 금지
- + 처리 방식 변경 금지
- truncation 기준 변경 금지
- decoded variant output shape 변경 금지
```

### 4.2 `l3_hints.py` — 완료

역할:

```text
- Log4Shell-style JNDI lookup hint
- SSRF-like URL/internal/metadata target hint
- SSTI expression hint
- webshell-like path/parameter hint
- L3 query pair extraction helper
```

유지 조건:

```text
- L3 탐지 조건 확대 금지
- L3 reason_hints 이름 변경 금지
- 새 L3 패턴 추가와 module split 혼합 금지
```

### 4.3 `models.py` — 완료

역할:

```text
- Candidate dataclass
- NoiseAggregate dataclass
```

유지 조건:

```text
- dataclass field 이름/순서/기본값 변경 금지
- asdict() 기반 output JSON shape 변경 금지
```

### 4.4 `method_summaries.py` — 완료

역할:

```text
- method_behavior_summaries builder
- method behavior reason hints
- method behavior summary contexts
```

검증 기준:

```text
- g_r1_method_behavior_context
- method_behavior_summary_count 유지
- candidate_rows == 0 유지
- PUT/DELETE/TRACE/OPTIONS 성공 단정 금지
```

### 4.5 `protocol_anomalies.py` — 완료

역할:

```text
- protocol_anomaly_summaries builder
- protocol anomaly reason hints
- protocol anomaly summary contexts
```

검증 기준:

```text
- g_r2_protocol_anomaly_context
- protocol_anomaly_summary_count 유지
- candidate_rows == 0 유지
- protocol bypass / virtual host bypass / 침해 성공 단정 금지
```

### 4.6 `auth_behavior.py` — 완료

역할:

```text
- auth_behavior_summaries builder
- auth behavior summary contexts
```

의도적으로 남긴 범위:

```text
- supporting_events 생성/연결 로직은 prepare_llm_input.py에 유지
- representative candidate demotion logic은 이동하지 않음
```

검증 기준:

```text
- f_r1_auth_behavior_context
- auth_behavior_summary_count 유지
- candidate_rows == 3 유지
- supporting_event_count == 1 유지
- login success / credential stuffing success / lockout 단정 금지
```

### 4.7 `static_baseline.py` — 완료

역할:

```text
- static_baseline_summaries builder
- static baseline reason hints
- static baseline summary contexts
```

검증 기준:

```text
- h_r1_static_baseline_context
- static_baseline_summary_count 유지
- candidate_rows == 0 유지
- static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부 단정 금지
```

### 4.8 `crawler_baseline.py` — 완료

역할:

```text
- crawler_baseline_summaries builder
- crawler-like user-agent family classifier
- crawler browse path classifier
- crawler baseline reason hints
- crawler baseline summary contexts
```

검증 기준:

```text
- h_r2_crawler_baseline_context
- crawler_baseline_summary_count 유지
- candidate_rows == 0 유지
- 실제 crawler 정체, robots/sitemap 내용, site structure, page existence, attack success 단정 금지
```

분리 방식:

```text
- prepare_llm_input.py에는 기존 함수명 wrapper 유지
- constants 이동 없음
- static/sensitive/mixed summary 이동 없음
- expected fixture 수정 없음
```

## 5. 1차 분리 완료 판단

현재까지의 분리는 `prepare_llm_input.py`에서 비교적 독립적인 summary builder와 dataclass/helper를 이동한 1차 mechanical refactor로 본다.

완료 범위:

```text
decoders.py
l3_hints.py
models.py
method_summaries.py
protocol_anomalies.py
auth_behavior.py
static_baseline.py
crawler_baseline.py
```

현재 상태:

```text
- prepare/stage dry-run strict regression 통과 유지
- constants 대량 이동 없음
- Stage1/Stage2 prompt/schema 변경 없음
- expected fixture 수정 없음
- candidate/supporting/filtering coordination은 prepare_llm_input.py에 유지
```

## 6. 아직 분리하지 않을 영역

아래는 현재 보류한다.

```text
- SQLi hint 분리
- XSS hint 분리
- file disclosure hint 분리
- sensitive_path_probe_summaries 분리
- mixed_baseline_scanner_summaries 분리
- probing_sequence_summaries 분리
- ip_behavior_aggregates 분리
- constants.py 대량 분리
- CLI / file IO 분리
```

보류 이유:

```text
- SQLi/XSS/file disclosure는 scoring, FP 억제, candidate 승격 조건과 강하게 결합됨
- sensitive/mixed/probing/ip behavior는 Stage2 context-only 해석 및 candidate/supporting/filtering 구조와 강하게 연결됨
- constants에는 regex, score weight, category string, window size가 섞여 있어 대량 이동 시 위험함
```

## 7. 다음 후보

다음 후보는 `sensitive_path_probe_summaries` 계열 검토다.

단, 바로 코드 분리하지 않는다. 먼저 좁은 계획 문서를 작성한다.

추천 다음 문서:

```text
docs/design/99_prepare_sensitive_path_probe_split_plan.md
```

검토 이유:

```text
- H R3 sensitive path probe fixture가 있음
- .env, .git, phpinfo, server-status, backup/config 경로와 연결됨
- 200/text/html + bytes를 file exposure로 단정하지 않는 guard가 중요함
- file disclosure / sensitive path category 판단과 일부 겹칠 수 있음
```

## 8. 장기 목표 구조

```text
src/
├── prepare/
│   ├── __init__.py
│   ├── decoders.py
│   ├── l3_hints.py
│   ├── models.py
│   ├── method_summaries.py
│   ├── protocol_anomalies.py
│   ├── auth_behavior.py
│   ├── static_baseline.py
│   ├── crawler_baseline.py
│   ├── constants.py          # future, small slices only
│   ├── sqli_hints.py         # future
│   ├── xss_hints.py         # future
│   ├── file_disclosure.py    # future
│   ├── sensitive_path_probe.py # future
│   ├── mixed_baseline_scanner.py # future
│   ├── ip_behavior.py        # future
│   └── probing.py            # future
└── prepare_llm_input.py
```

`prepare_llm_input.py`의 장기 역할:

```text
- CLI
- input / output file handling
- pipeline orchestration
- backwards-compatible output format 유지
- candidate/supporting/filtering coordination
```

## 9. 실패 시 롤백 기준

아래 중 하나라도 발생하면 해당 분리 커밋은 수정 또는 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- candidate 수 변화
- filtered_out 수 변화
- supporting_events 수 변화
- summary count 변화
- reason_hints 누락
- output JSON key 변화
- interpretation_limit 변화
- context-only policy 약화
- import cycle 발생
```

## 10. 현재 결론

P4는 현재 아래까지 1차 분리 완료 상태다.

```text
decoders.py
l3_hints.py
models.py
method_summaries.py
protocol_anomalies.py
auth_behavior.py
static_baseline.py
crawler_baseline.py
```

다음은 `sensitive_path_probe_summaries` 계열을 문서로 검토한다. 코드 분리는 해당 문서에서 함수명, 출력 key, fixture, 불변조건을 확인한 뒤 별도 판단한다.
