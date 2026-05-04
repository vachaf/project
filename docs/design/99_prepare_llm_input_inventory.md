# 99_prepare_llm_input_inventory

- 문서 상태: inventory / 분리 후보 검토
- 기준 시점: 2026-05-04
- 목적: `src/prepare_llm_input.py`에 남아 있는 책임을 분류하고, 다음 실제 module split 후보를 하나로 좁힌다.

이 문서는 코드 변경 계획서가 아니라, 다음 refactor 후보를 안전하게 고르기 위한 책임 영역 inventory다.

관련 계획 문서: [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 현재 결론

다음 실제 코드 분리 후보는 아래로 잡는다.

```text
src/prepare/models.py
```

1차 분리 대상은 아래 두 dataclass로 제한한다.

```text
Candidate
NoiseAggregate
```

이번 판단의 이유:

- `decoders.py`와 `l3_hints.py`는 이미 분리 완료 상태다.
- `Candidate`와 `NoiseAggregate`는 판정 로직보다 data shape 정의에 가깝다.
- SQLi/XSS/file disclosure/context summary 로직보다 behavior 변경 위험이 낮다.
- 다음 refactor에서 import 변경 범위를 비교적 좁게 유지할 수 있다.

이번 inventory의 비결론:

- SQLi/XSS/file disclosure hint 로직을 지금 분리하지 않는다.
- context summary builder를 지금 분리하지 않는다.
- scoring, filtering, candidate 승격 기준을 바꾸지 않는다.
- output JSON key 구조를 바꾸지 않는다.

## 2. 이미 분리된 영역

### 2.1 `src/prepare/decoders.py`

이미 분리 완료된 역할:

```text
- URL decode depth 1/2
- HTML entity decode
- decoded variants 생성
- HTML entity variant 추가
```

유지 조건:

- decode depth 의미를 바꾸지 않는다.
- `+` 처리, truncation 기준, empty input 처리 방식을 바꾸지 않는다.
- decoded variant output shape를 바꾸지 않는다.

### 2.2 `src/prepare/l3_hints.py`

이미 분리 완료된 역할:

```text
- Log4Shell-style JNDI lookup hint
- SSRF-like URL/internal/metadata target hint
- SSTI expression hint
- webshell-like path/parameter hint
- L3 query pair extraction helper
```

유지 조건:

- L3 탐지 조건을 넓히지 않는다.
- L3 `reason_hints` 이름을 바꾸지 않는다.
- 새 L3 패턴 추가와 module split을 같은 커밋에 섞지 않는다.

## 3. `prepare_llm_input.py`에 남아 있는 책임 영역

### 3.1 data shape / model 정의

현재 남아 있는 대표 구조:

```text
Candidate
NoiseAggregate
```

성격:

- 전처리 결과 row를 담는 data shape
- downstream JSON 생성과 asdict 변환에 사용
- behavior rule 자체는 아님

분리 후보 판단:

```text
1순위 후보
```

이유:

- 로직보다 구조 정의에 가까움
- score, hint detection, filtering 조건을 직접 바꾸지 않음
- 다음 단계에서 `src/prepare/models.py`로 옮기기 적합

주의:

- field 이름, 기본값, 타입 의미를 바꾸지 않는다.
- dataclass field 순서를 불필요하게 바꾸지 않는다.
- output JSON shape가 바뀌면 안 된다.

### 3.2 constants / pattern 정의

현재 포함된 대표 범주:

```text
SQLI_PATTERNS
XSS_PATTERNS
TRAVERSAL_PATTERNS
FILE_DISCLOSURE_PATTERNS
CMDI_PATTERNS
AUTOMATION_UA_PATTERNS
AUTH / LOGIN / QUERY / DIR_PROBE / STATIC / CRAWLER 관련 상수
summary window / sample limit / threshold 상수
regex helper pattern
```

성격:

- 단순 상수와 behavior rule이 섞여 있음
- regex pattern, score weight, category string, window size가 함께 존재

분리 후보 판단:

```text
2순위 또는 보류
```

이유:

- `constants.py`로 옮기는 것은 가능하지만 diff가 넓어질 수 있음
- score weight나 regex pattern이 expected와 직접 연결됨
- 단순 이동이어도 regression 실패 시 원인 파악이 어려워질 수 있음

권장:

- 지금 바로 대량 분리하지 않는다.
- 나중에 한다면 pure string/window constant와 rule pattern을 분리해서 단계적으로 진행한다.

### 3.3 SQLi hint / scoring logic

성격:

- quote termination
- boolean condition
- xclose
- union/schema access
- educational SQL search FP
- double decoded SQLi hint
- candidate score boost

분리 후보 판단:

```text
보류
```

이유:

- B R2B double encoded SQLi 품질과 직접 연결됨
- educational SQL false positive 완화와 결합되어 있음
- `supporting_events` 보존과도 일부 연결됨
- 단순 함수 이동이라도 회귀 리스크가 큼

향후 조건:

- SQLi rule weight / FP rule / attack structure rule을 명시적으로 분리할 때 다시 검토한다.

### 3.4 XSS hint / scoring logic

성격:

- script tag
- event handler
- javascript protocol
- document.cookie
- external navigation/exfil intent
- HTML entity decoded XSS
- tutorial/onerror FP bait

분리 후보 판단:

```text
보류
```

이유:

- C HTML entity XSS 품질과 직접 연결됨
- HTML entity decode와 XSS structure 복원이 결합되어 있음
- FP bait 분리 기준을 깨뜨릴 수 있음

향후 조건:

- XSS attack structure rule과 educational/context-only rule을 먼저 문서화한 뒤 검토한다.

### 3.5 traversal / HPP / command injection / file disclosure hint logic

성격:

- traversal pattern
- HPP detection
- command injection marker
- PHP wrapper / file disclosure marker
- direct config path / source disclosure intent

분리 후보 판단:

```text
file disclosure는 보류
기타는 inventory 후 재검토
```

이유:

- E R2B PHP wrapper, `suspicious_file_disclosure`, Stage1/Stage2 wording guard가 최근 보강됨
- direct `/config.php`류와 PHP wrapper candidate 구분이 중요함
- file disclosure를 지금 옮기면 과승격/과소탐지 회귀 위험이 있음

향후 조건:

- source disclosure / local file read / direct sensitive path contract를 먼저 정의한 뒤 분리한다.

### 3.6 false positive review logic

성격:

- educational SQL / XSS / SSTI search context
- normal search value
- known asset / baseline context 보조
- likely_false_positive 분류

분리 후보 판단:

```text
보류
```

이유:

- 공격 후보 보존과 FP 억제의 균형을 잡는 핵심 로직
- Stage1/Stage2 품질 평가와 직접 연결됨
- 별도 모듈화 전에 rule boundary가 더 명확해야 함

### 3.7 candidate scoring / filtering / promotion logic

성격:

- score 계산
- `verdict_hint` 결정
- candidate / filtered_out / supporting_events 분리
- high-signal / low-signal 기준

분리 후보 판단:

```text
보류
```

이유:

- behavior 변경 위험이 가장 큼
- regression failure가 생기면 영향 범위가 넓음
- P1/P2에서 안정화한 품질 기준을 흔들 수 있음

### 3.8 supporting events / temporal context logic

성격:

- 같은 IP / endpoint family / time window 기반 support 보존
- SQLi temporal chain 저신호 step 보존
- Stage2 context-only 전달

분리 후보 판단:

```text
보류
```

이유:

- B R2B supporting_events 품질과 직접 연결됨
- candidate 승격과 context-only 보존 사이의 경계가 중요함
- 별도 input/output contract 없이 옮기기 위험함

### 3.9 context summary builders

대상 범주:

```text
probing_sequence_summaries
ip_behavior_aggregates
auth_behavior_summaries
method_behavior_summaries
protocol_anomaly_summaries
static_baseline_summaries
crawler_baseline_summaries
sensitive_path_probe_summaries
mixed_baseline_scanner_summaries
```

분리 후보 판단:

```text
구조적 효과는 크지만 현재는 보류
```

이유:

- Stage2 report input 구조와 직접 연결됨
- 각 summary의 policy / interpretation_hint / count가 expected에 연결됨
- context-only 과승격 금지 원칙과 직접 관련됨

향후 조건:

- summary builder별 input/output contract를 먼저 문서화한다.
- 각 summary type별 fixture가 충분히 고정된 뒤 하나씩 분리한다.

### 3.10 output JSON shaping / file IO / CLI

성격:

- input JSON load
- output filename 결정
- `*_llm_input.json`, `*_analysis_candidates.json`, `*_noise_summary.json`, `*_filtered_out_rows.json` 생성
- CLI option 처리

분리 후보 판단:

```text
현재 보류
```

이유:

- 파이프라인 외부 인터페이스이므로 변경 리스크가 있음
- 파일명/출력 key 변화가 downstream 작업에 영향

향후 조건:

- 내부 로직 분리가 더 진행된 뒤 orchestration layer로 정리한다.

## 4. 후보 비교표

| 후보 | 위험도 | 효과 | 판단 |
|---|---:|---:|---|
| `prepare/models.py` | 낮음 | 중간 | 다음 후보 |
| `prepare/constants.py` | 중간 | 중간 | 나중에 작은 단위로 |
| `prepare/file_disclosure_hints.py` | 높음 | 중간 | 보류 |
| `prepare/sqli_hints.py` | 높음 | 중간 | 보류 |
| `prepare/xss_hints.py` | 높음 | 중간 | 보류 |
| `prepare/context_summaries.py` | 높음 | 높음 | contract 문서화 후 검토 |
| `prepare/io.py` 또는 `prepare/cli.py` | 중간 | 낮음~중간 | 내부 분리 이후 검토 |

## 5. 다음 실제 분리 범위

권장 다음 코드 커밋:

```text
refactor: extract prepare models
```

변경 대상:

```text
src/prepare/models.py
src/prepare/__init__.py
src/prepare_llm_input.py
```

분리 대상:

```text
Candidate
NoiseAggregate
```

금지:

```text
- field 이름 변경
- field 기본값 변경
- field 순서 불필요 변경
- asdict output shape 변경
- score / candidate / filtering 로직 변경
- reason_hints 이름 변경
- output file name 변경
```

## 6. 검증 계획

분리 전:

```bash
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
```

분리 후:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

성공 기준:

```text
prepare regression: 18 fixtures, warn=0 fail=0
stage dry-run regression: 12 fixtures, warn=0 fail=0
candidate count 변화 없음
reason_hints 변화 없음
output JSON key 구조 변화 없음
```

## 7. 실패 시 롤백 기준

아래 중 하나라도 발생하면 해당 분리 커밋은 수정 또는 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- candidate 수 변화
- filtered_out 수 변화
- supporting_events 수 변화
- reason_hints 누락
- output JSON key 변화
- dataclass 기본값 변화
- import cycle 발생
```

## 8. 최종 판단

현재 P4의 다음 후보는 `prepare/models.py`다.

단, 이 후보는 작은 mechanical refactor로만 진행한다.

```text
1. Candidate / NoiseAggregate dataclass만 이동
2. import 경로만 최소 수정
3. regression strict 통과 확인
4. 이후 constants나 context summary 분리는 별도 판단
```
