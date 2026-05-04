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

따라서 과거 계획의 Step 1-A `decoders.py` 분리와 Step 1-B `l3_hints.py` 분리는 완료된 상태다.

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

2차 분리는 바로 코드부터 하지 않는다. 먼저 `prepare_llm_input.py` 책임 영역 inventory를 작성하고, 그 결과를 보고 하나만 선택한다.

### 후보 A: `prepare/models.py` 또는 `prepare/types.py`

성격:

- dataclass, TypedDict, constants, enum-like string set 등 구조 정의 중심

장점:

- behavior 변경 위험이 상대적으로 낮음
- 이후 summary builder나 hint module 분리의 기반이 될 수 있음

위험:

- import 변경 범위가 넓어질 수 있음
- 지금 코드가 dict 중심이면 억지 타입화가 오히려 복잡도를 키울 수 있음

판단:

- 다음 실제 코드 분리 후보로는 가장 안전한 편이다.
- 단, 먼저 `prepare_llm_input.py` 안의 data shape와 constants inventory가 필요하다.

### 후보 B: `prepare/constants.py`

성격:

- 반복되는 marker, category name, policy string, protected key 이름 등을 분리

장점:

- behavior risk 낮음
- 문자열 오타 방지 가능

위험:

- 단순 이동만으로 구조적 이득이 작을 수 있음
- 너무 많이 옮기면 diff가 넓어짐

판단:

- 작은 단위로 하면 안전하다.
- 단, candidate/filtering 기준 문자열은 output과 expected에 연결되므로 이름 변경 금지.

### 후보 C: `prepare/file_disclosure_hints.py`

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

### 후보 D: `prepare/context_summaries.py`

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
- 먼저 summary builder inventory가 필요하다.

## 7. 다음 작업 순서

### P4-A. 문서 최신화 — 완료

이 문서가 현재 상태를 반영한다.

반영 내용:

- regression 기준을 18 / 12 fixtures로 갱신
- `decoders.py` 분리 완료 상태 반영
- `l3_hints.py` 분리 완료 상태 반영
- 다음 후보를 2차 분리 검토로 재정의

### P4-B. `prepare_llm_input.py` 책임 영역 inventory 작성 — 다음 단계

목표:

- 지금 남아 있는 함수/상수/책임을 분류한다.
- 코드 이동 없이 문서만 작성한다.
- 다음 실제 분리 후보를 1개만 고른다.

추천 문서:

```text
docs/design/99_prepare_llm_input_inventory.md
```

inventory 항목 예:

```text
- decoded/text analysis helper
- SQLi hint logic
- XSS hint logic
- traversal/HPP/file disclosure hint logic
- false positive review logic
- candidate scoring/filtering logic
- supporting_events builder
- context summary builders
- output JSON shaping
- CLI/file IO
- constants/category strings
```

### P4-C. 다음 실제 분리 후보 결정

P4-B 이후 아래 중 하나만 고른다.

권장 우선순위:

```text
1. constants/models 성격의 낮은 위험 분리
2. file disclosure hints inventory 보강
3. context summary builder 분리 검토
```

SQLi/XSS/file disclosure/context summary를 바로 분리하지 않는다.

### P4-D. 실제 코드 분리

조건:

- inventory 문서 작성 완료
- 다음 후보 1개 선정 완료
- `git status` clean
- prepare/stage dry-run strict pass
- py_compile pass

## 8. 장기 목표 구조

아래는 장기 목표일 뿐이며, 지금 당장 모두 구현하는 계획이 아니다.

```text
src/
├── prepare/
│   ├── __init__.py
│   ├── decoders.py
│   ├── l3_hints.py
│   ├── constants.py          # possible next
│   ├── models.py             # possible next
│   ├── sqli_hints.py         # future
│   ├── xss_hints.py          # future
│   ├── file_disclosure.py    # future
│   ├── context_summaries.py  # future
│   ├── ip_behavior.py        # future
│   └── probing.py            # future
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
```

### 다음 문서 커밋

```bash
git commit -m "docs: add prepare input inventory"
```

내용:

- `docs/design/99_prepare_llm_input_inventory.md` 추가
- 코드 변경 없음
- 다음 실제 분리 후보 1개 선정

### 이후 코드 커밋 후보

```bash
git commit -m "Extract prepare constants"
```

또는

```bash
git commit -m "Extract prepare models"
```

조건:

- inventory에서 낮은 위험 후보로 확인된 경우만 진행
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

- P4로 넘어가는 것은 맞다.
- 다만 바로 SQLi/XSS/file disclosure/context summary 분리를 시작하지 않는다.
- `decoders.py`와 `l3_hints.py`는 이미 분리 완료 상태다.
- 다음 작업은 `prepare_llm_input.py` 책임 영역 inventory를 작성하는 것이다.
- 실제 코드 분리는 inventory 이후 가장 낮은 위험 후보 1개만 선택해서 진행한다.
