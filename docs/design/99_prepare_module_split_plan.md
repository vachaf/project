# 99_prepare_module_split_plan

## 1. 배경

`src/prepare_llm_input.py`는 전처리 파이프라인의 핵심 오케스트레이션 파일이다. 기능 안정화 초기에는 한 파일에 유지하는 편이 변경 추적에 유리했지만, 현재는 다음 책임이 한 파일에 많이 남아 있다.

- decoded variants 조합과 분석 텍스트 구성
- SQLi / XSS / traversal / HPP / file disclosure hint 생성과 score 반영
- false positive review 후보 분리
- `supporting_events`
- `probing_sequence_summaries`
- `ip_behavior_aggregates`
- `auth_behavior_summaries`
- `method_behavior_summaries`
- `protocol_anomaly_summaries`
- `static_baseline_summaries`
- `crawler_baseline_summaries`
- `sensitive_path_probe_summaries`
- `mixed_baseline_scanner_summaries`
- Stage1/Stage2 입력용 output JSON 생성
- CLI와 파일 입출력

이 문서의 목적은 전면 리팩터링 계획이 아니라, 회귀 안전성을 유지하는 점진적 모듈 분리 계획을 최신 상태로 정리하는 것이다.

## 2. 현재 상태

### 2.1 이미 완료된 1차 분리

아래 모듈은 이미 분리되어 있다.

```text
src/prepare/__init__.py
src/prepare/decoders.py
src/prepare/l3_hints.py
src/prepare/models.py
```

`src/prepare/decoders.py`는 다음 역할을 담당한다.

- URL decode depth 1/2
- HTML entity decode
- decoded variant 생성
- HTML entity variant 추가

`src/prepare/l3_hints.py`는 다음 역할을 담당한다.

- Log4Shell-style JNDI lookup hint
- SSRF-like URL/internal/metadata target hint
- SSTI expression hint
- webshell-like path/parameter hint
- L3 query pair extraction helper

`src/prepare/models.py`는 다음 역할을 담당한다.

- `Candidate` dataclass
- `NoiseAggregate` dataclass

따라서 과거 계획의 Step 1-A `decoders.py` 분리, Step 1-B `l3_hints.py` 분리, 그리고 data shape 1차 분리는 완료된 상태다.

### 2.2 현재 회귀 안전장치

현재 prepare / stage dry-run 관련 안전장치는 아래 기준으로 본다.

```bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

현재 기준:

```text
prepare regression: 18 fixtures, warn=0 fail=0
stage dry-run regression: 12 fixtures, warn=0 fail=0
```

추가 확인 후보:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
```

## 3. 핵심 원칙

- 동작 변경 없는 mechanical refactor 우선
- 한 번에 한 책임만 분리
- 분리와 기능 개선을 같은 커밋에 섞지 않음
- regression 실패 시 원인 범위가 1개 변경 단위로 좁혀져야 함
- output JSON 의미와 key 구조를 바꾸지 않음
- `reason_hints` 이름을 바꾸지 않음
- score / candidate / filtering 기준을 바꾸지 않음
- Stage1 / Stage2 prompt나 schema는 module split과 별도로 관리
- Apache logs-only 원칙 유지
- response body 원문, DB 결과, 브라우저 실행 여부 사용 금지
- `status_code=200`, `text/html`, `response_body_bytes`만으로 성공 단정 금지
- 실험환경 특화 rule 금지
  - `lab-*` User-Agent
  - 특정 IP
  - 특정 response size
  - 특정 제품명
  - 특정 route 문자열

## 4. 완료된 단계

### Step 1-A: `decoders.py` 분리 — 완료

완료 상태:

```text
src/prepare/decoders.py
```

현재 역할:

- `build_decoded_variants()`
- `build_html_entity_decoded_variant()`
- `build_html_entity_variants()`
- `append_html_entity_variants()`

유지해야 할 조건:

- URL decode 동작 변경 금지
- `+` 처리 방식 변경 금지
- HTML entity decode 결과 변경 금지
- truncation 기준 변경 금지
- decoded variant depth 의미 변경 금지

### Step 1-B: `l3_hints.py` 분리 — 완료

완료 상태:

```text
src/prepare/l3_hints.py
```

현재 역할:

- Log4Shell hint
- SSRF hint
- SSTI hint
- webshell-like hint

유지해야 할 조건:

- L3 탐지 조건 변경 금지
- 고신호 조건 확대 금지
- 새 L3 패턴 추가와 module split을 같은 커밋에 섞지 않음
- 기존 L3 fixture의 `reason_hints` 변화 금지

### Step 1-C: `models.py` 분리 — 완료

완료 상태:

```text
src/prepare/models.py
```

현재 역할:

- `Candidate`
- `NoiseAggregate`

유지해야 할 조건:

- dataclass field 이름 변경 금지
- dataclass field 순서 불필요 변경 금지
- dataclass 기본값 변경 금지
- `asdict()` 기반 output JSON shape 변경 금지
- score / candidate / filtering / reason_hints 로직 변경 금지

검증 상태:

```text
py_compile 통과
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
```

## 5. 현재 하면 안 되는 분리

### SQLi / XSS hint 분리 보류

보류 이유:

- scoring과 candidate 판정에 강하게 결합되어 있음
- xclose, quote termination, boolean hint, educational SQL FP 분리 로직이 최근 안정화됨
- HTML entity XSS, onerror/javascript/document.cookie, tutorial FP bait가 decoded variants와 결합되어 있음
- 단순 함수 이동만으로는 구조적 이득이 작고, 회귀 위험은 큼

향후 분리 조건:

- SQLi / XSS rule weight 구조를 도입할 때
- hint scoring을 별도 rule engine으로 재설계할 때
- FP rule과 attack structure rule을 명확히 분리할 때

### file disclosure hint 분리 보류

보류 이유:

- `suspicious_file_disclosure` Stage1 verdict와 Stage2 wording guard가 최근 보강됨
- direct config path와 PHP wrapper candidate 구분이 중요함
- 지금 분리하면 과승격 / 과소탐지 회귀 위험이 있음

향후 분리 조건:

- source disclosure / local file read / direct sensitive path rule을 명확히 나눌 때
- PHP wrapper와 direct sensitive path의 input/output contract를 먼저 정의한 뒤

### context summary / supporting_events 분리 보류

보류 이유:

- Stage2 report input 구조와 직접 연결됨
- candidate / support / filtered_out 구조와 의존성이 큼
- context-only 원칙이 분석 품질에 직접 영향을 줌
- summary별 정책 문구와 Stage2 guard가 같이 움직임

향후 분리 조건:

- candidate data model을 표준화한 뒤
- context summary builder의 입력/출력 contract를 먼저 문서화한 뒤
- 각 summary type별 fixture가 충분히 고정된 뒤

## 6. 다음 2차 분리 후보

다음 분리는 바로 코드부터 하지 않는다. `models.py` 분리 이후 남은 책임을 다시 보고 하나만 고른다.

### 후보 A: `prepare/constants.py`

성격:

- 반복되는 marker, category name, policy string, protected key 이름 등을 분리

장점:

- 문자열 오타 방지 가능
- 일부 pure constant는 behavior risk가 낮음

위험:

- 현재 상수에는 regex, score weight, category string, window size가 섞여 있음
- 대량 이동 시 diff가 커지고 회귀 실패 원인 추적이 어려워짐

판단:

- 당장 대량 분리는 하지 않는다.
- 한다면 pure string/window constant부터 아주 작게 분리한다.

### 후보 B: `prepare/file_disclosure_hints.py`

성격:

- PHP wrapper, direct config path, source disclosure intent 관련 hint 추출

장점:

- E R2B와 file disclosure taxonomy를 독립적으로 관리 가능

위험:

- 최근 변경된 `suspicious_file_disclosure`, Stage1/Stage2 UA guard, E R2B expected와 결합됨
- PHP wrapper candidate와 direct path filtered/context 구분을 깨뜨릴 수 있음

판단:

- 당장 하지 않음.
- E R2B 실제 LLM 재검증 또는 추가 fixture가 필요할 때 다시 검토.

### 후보 C: `prepare/context_summaries.py`

성격:

- auth/method/protocol/static/crawler/sensitive/mixed summaries 생성 로직 분리

장점:

- 현재 `prepare_llm_input.py`의 큰 책임을 줄일 수 있음
- Stage2 context-only 입력 구조를 더 명확하게 할 수 있음

위험:

- Stage2 report input 구조와 직접 연결됨
- summary count, policy, interpretation_hint가 expected에 강하게 묶여 있음

판단:

- 구조상 효과는 크지만 아직 위험이 크다.
- 먼저 summary builder contract 문서화가 필요하다.

## 7. 다음 작업 순서

### P4-A. 문서 최신화 — 완료

반영 내용:

- regression 기준을 18 / 12 fixtures로 갱신
- `decoders.py` 분리 완료 상태 반영
- `l3_hints.py` 분리 완료 상태 반영
- `models.py` 분리 완료 상태 반영

### P4-B. `prepare_llm_input.py` 책임 영역 inventory 작성 — 완료

문서:

```text
docs/design/99_prepare_llm_input_inventory.md
```

결론:

- 다음 실제 분리 후보로 `models.py`를 선택했다.
- `Candidate` / `NoiseAggregate`만 이동 대상으로 제한했다.
- SQLi/XSS/file disclosure/context summary는 보류했다.

### P4-C. `models.py` 분리 — 완료

완료 내용:

```text
src/prepare/models.py 생성
Candidate / NoiseAggregate 이동
src/prepare_llm_input.py import 경로 조정
src/prepare/__init__.py export 추가
```

검증:

```text
py_compile 통과
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
```

### P4-D. 다음 후보 재검토 — 다음 단계

바로 다음 코드 분리를 진행하지 않는다.

검토 대상:

```text
- constants.py를 아주 작게 분리할 수 있는지
- context summary builder contract 문서화가 먼저 필요한지
- file disclosure hint 분리를 더 늦출지
```

## 8. 장기 목표 구조

아래는 장기 목표일 뿐이며, 지금 당장 모두 구현하는 계획이 아니다.

```text
src/
├── prepare/
│   ├── __init__.py
│   ├── decoders.py
│   ├── l3_hints.py
│   ├── models.py
│   ├── constants.py          # possible future
│   ├── sqli_hints.py         # future
│   ├── xss_hints.py         # future
│   ├── file_disclosure.py   # future
│   ├── context_summaries.py # future
│   ├── ip_behavior.py       # future
│   └── probing.py           # future
└── prepare_llm_input.py
```

`prepare_llm_input.py`의 장기 역할:

- CLI
- input / output file handling
- pipeline orchestration
- backwards-compatible output format 유지

## 9. 단계별 커밋 계획

### 완료된 커밋 계열

```bash
git commit -m "Extract prepare decoders"
git commit -m "Extract L3 prepare hints"
git commit -m "refactor: extract prepare models"
```

### 다음 문서/검토 커밋 후보

```bash
git commit -m "docs: review next prepare split candidate"
```

내용:

- 다음 후보를 하나로 좁히기 위한 검토
- 코드 변경 없음

### 이후 코드 커밋 후보

아직 확정하지 않는다.

조건:

- 낮은 위험 후보 1개만 선택
- 동작 변경 없음
- regression strict pass

## 10. 체크리스트

### 분리 전

- `git status` clean
- prepare regression strict pass
- stage dry-run regression strict pass
- `py_compile` pass
- 분리 후보가 1개로 제한되어 있음
- 기능 개선과 refactor가 섞이지 않음

### 각 분리 후

- 새 파일 `py_compile` pass
- import cycle 없음
- prepare regression strict pass
- stage dry-run regression strict pass
- 기존 output JSON 구조 변화 없음
- `reason_hints` 이름 변화 없음
- score / candidate count 변화 없음
- 문서 업데이트는 최소화

## 11. 실패 시 롤백 기준

아래 중 하나라도 발생하면 해당 분리 커밋은 롤백 또는 수정해야 한다.

- prepare regression fail
- stage dry-run regression fail
- candidate 수 변화
- `reason_hints` 누락
- decoded view 변화
- L3 fixture hint 변화
- educational SQL / XSS FP fixture 실패
- normal baseline fixture 실패
- PHP wrapper / direct config path fixture 실패
- `ip_behavior_aggregates` fixture 실패
- import cycle 발생
- CLI output filename 변화

## 12. 현재 결론

- P4는 `decoders.py`, `l3_hints.py`, `models.py`까지 1차 분리 완료 상태다.
- `models.py` 분리는 mechanical refactor로 완료됐고 strict regression을 통과했다.
- 바로 다음 코드 분리로 이어가지 않는다.
- 다음 작업은 남은 책임 중 가장 낮은 위험 후보를 다시 고르는 것이다.
