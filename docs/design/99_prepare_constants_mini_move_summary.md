# 99_prepare_constants_mini_move_summary

- 문서 상태: prepare constants mini-move 완료 요약
- 기준 시점: 2026-05-04
- 목적: `99_prepare_constants_ownership_map.md`와 `99_prepare_constants_mini_move_candidate_review.md` 이후 수행한 안전한 constants mini-move 결과를 정리하고, 계속 보류할 constants와 다음 후보를 고정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_protocol_anomaly_constants_move_plan.md](./99_prepare_protocol_anomaly_constants_move_plan.md)
- [99_prepare_ip_behavior_constants_move_plan.md](./99_prepare_ip_behavior_constants_move_plan.md)
- [99_prepare_method_behavior_constants_move_plan.md](./99_prepare_method_behavior_constants_move_plan.md)
- [99_prepare_static_baseline_constants_move_plan.md](./99_prepare_static_baseline_constants_move_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

prepare constants mini-move 1차는 완료 상태로 본다.

이번 mini-move의 목적은 `constants.py`를 새로 만들거나 constants를 대량 이동하는 것이 아니라, owner가 비교적 명확하고 영향 범위가 작은 constants group만 각 topic module로 옮기는 것이었다.

완료한 이동:

```text
PROTOCOL_ANOMALY_* constants -> src/prepare/protocol_anomalies.py
IP_BEHAVIOR_* constants -> src/prepare/ip_behavior.py
METHOD_BEHAVIOR_* / method family constants 일부 -> src/prepare/method_summaries.py
STATIC_BASELINE_* constants 일부 -> src/prepare/static_baseline.py
```

공통 원칙:

```text
- constants.py 대량 분리 금지
- 한 번에 한 constants group만 이동
- behavior 변경 없음
- helper/function 추가 이동 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- Apache logs-only 해석 원칙 유지
```

## 2. 완료한 mini-move 목록

### 2.1 protocol anomaly constants

기준 커밋:

```text
b81db3f449b06fccd7815dae30c7c4db6f30aa57
refactor: move protocol anomaly constants
```

이동한 constants:

```text
PROTOCOL_ANOMALY_WINDOW_SEC = 300
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT = 10
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN = 512
```

owner module:

```text
src/prepare/protocol_anomalies.py
```

수정 파일:

```text
src/prepare/protocol_anomalies.py
src/prepare_llm_input.py
```

유지한 계약:

```text
- helper/function 추가 이동 없음
- long path threshold 값 변경 없음
- window/sample limit 값 변경 없음
- protocol anomaly detection 로직 변경 없음
- policy_notes 의미 변경 없음
- output key 변경 없음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

해석 제한:

```text
- protocol bypass 성공 단정 금지
- malformed request exploit success 단정 금지
- 서버 침해 성공 단정 금지
- status_code나 error log 존재만으로 exploit 성공 판단 금지
```

### 2.2 IP behavior constants

기준 커밋:

```text
66d46f419b88b01e69144be93edd59b60afd9dc0
refactor: move ip behavior constants
```

이동한 constants:

```text
IP_BEHAVIOR_WINDOW_SEC = 300
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT = 10
```

owner module:

```text
src/prepare/ip_behavior.py
```

수정 파일:

```text
src/prepare/ip_behavior.py
src/prepare_llm_input.py
```

유지한 계약:

```text
- helper/function 추가 이동 없음
- IP behavior aggregate 로직 변경 없음
- window/sample/sensitive-path limit 값 변경 없음
- policy_notes 의미 변경 없음
- output key 변경 없음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

해석 제한:

```text
- 특정 IP를 attacker identity로 단정하지 않음
- source IP만으로 공격 의도, 공격 성공, 침해 성공을 단정하지 않음
- IP 단위 집계는 관찰된 요청 묶음이지 신원 식별 결과가 아님
- sensitive path sample은 파일 노출 또는 앱 존재 증거가 아님
```

### 2.3 method behavior constants

기준 커밋:

```text
6bfa68e599501b27154181b8048f0362ce059e6b
refactor: move method behavior constants
```

이동한 constants:

```text
METHOD_BEHAVIOR_WINDOW_SEC = 300
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
METHOD_RISKY_FAMILIES = ("OPTIONS", "TRACE", "PUT", "DELETE", "PATCH")
METHOD_BASELINE_FAMILIES = ("GET", "HEAD")
METHOD_DESTRUCTIVE_FAMILIES = {"PUT", "DELETE", "PATCH"}
```

owner module:

```text
src/prepare/method_summaries.py
```

보류한 constant:

```text
STANDARD_HTTP_METHODS
```

보류 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- method behavior뿐 아니라 protocol anomaly / malformed method 판단에도 사용됨
- method_summaries.py 단독 owner로 보기 어려움
- protocol_anomalies.py와의 공유 경계를 흐릴 수 있음
```

수정 파일:

```text
src/prepare/method_summaries.py
src/prepare_llm_input.py
```

유지한 계약:

```text
- helper/function 추가 이동 없음
- method classification 로직 변경 없음
- protocol anomaly 로직 변경 없음
- window/sample/family 값 변경 없음
- STANDARD_HTTP_METHODS 이동 없음
- policy_notes 의미 변경 없음
- output key 변경 없음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

해석 제한:

```text
- PUT 업로드 성공 단정 금지
- DELETE 삭제 성공 단정 금지
- TRACE/XST 성공 단정 금지
- OPTIONS/CORS 취약점 성공 단정 금지
- method family classification은 context이지 exploit success 증거가 아님
```

### 2.4 static baseline constants

기준 커밋:

```text
f97164b8e5be89aa354c9ef575e1d7b45a56cf2e
refactor: move static baseline constants
```

이동한 constants:

```text
STATIC_BASELINE_WINDOW_SEC = 300
STATIC_BASELINE_MIN_STATIC_PATHS = 3
STATIC_BASELINE_SAMPLE_REQUEST_LIMIT = 10
```

owner module:

```text
src/prepare/static_baseline.py
```

보류한 constants:

```text
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

보류 위치:

```text
src/prepare_llm_input.py
```

보류 이유:

```text
- STATIC_EXTENSIONS / STATIC_PREFIXES는 일반 static row 판별과 다른 baseline/context summary 경계에 걸릴 수 있음
- STATIC_BASELINE_IMAGE_EXTENSIONS는 image/static classification 의미와 연결됨
- HEALTH_LIKE_PATHS는 health 정상 여부 단정 금지와 연결됨
- static/crawler/mixed scanner 경계가 남아 있음
```

수정 파일:

```text
src/prepare/static_baseline.py
src/prepare_llm_input.py
```

유지한 계약:

```text
- helper/function 추가 이동 없음
- static path classification 로직 변경 없음
- health-like path 판단 로직 변경 없음
- image/static classification 로직 변경 없음
- crawler baseline 로직 변경 없음
- mixed scanner 로직 변경 없음
- window/min-static/sample 값 변경 없음
- policy_notes 의미 변경 없음
- output key 변경 없음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

해석 제한:

```text
- static file 존재 단정 금지
- JS 실행 단정 금지
- robots/sitemap 내용이나 site structure 단정 금지
- health 정상 여부 단정 금지
- response bytes/content-type만으로 file exposure 단정 금지
```

## 3. 계속 보류할 constants

이번 mini-move 이후에도 아래 constants는 계속 보류한다.

### 3.1 shared method / protocol constants

```text
STANDARD_HTTP_METHODS
```

보류 이유:

```text
- method behavior와 protocol anomaly가 공유함
- 단일 owner가 명확하지 않음
- shared module 없이 이동하면 import 방향이 복잡해질 수 있음
```

### 3.2 static path/classification constants

```text
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

보류 이유:

```text
- 일반 static row 판별과 health-like path 판단에 연결됨
- crawler baseline, mixed scanner와 경계가 있을 수 있음
- static file 존재/JS 실행/health 정상 여부 단정 금지와 연결됨
```

### 3.3 probing / sensitive / mixed scanner constants

```text
PROBING_SEQUENCE_*
SENSITIVE_PATH_PROBE_*
DIR_PROBE_*
MIXED_BASELINE_SCANNER_*
```

보류 이유:

```text
- sensitive path, probing sequence, mixed scanner가 path/category 판단을 공유할 수 있음
- file disclosure와 의미 경계가 겹침
- context-only summary를 candidate/incident로 과승격하지 않도록 경계를 유지해야 함
```

### 3.4 hint patterns / generic attack policy constants

```text
SQLI_* patterns
XSS_* patterns
FILE_DISCLOSURE_* patterns
TRAVERSAL_* patterns
CMDI_* patterns
AUTOMATION_UA_* patterns
STRONG_ATTACK_* constants
ATTACK_ENCODED_PAYLOAD_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
```

보류 이유:

```text
- candidate selection, false positive suppression, supporting context와 연결될 수 있음
- SQLi는 DB 결과를 볼 수 없음
- XSS는 브라우저 실행 여부를 볼 수 없음
- file disclosure는 response body 원문/파일 내용/실제 노출 여부를 볼 수 없음
- evidence boundary 문서 없이 이동하면 의미 변경 위험이 큼
```

## 4. mini-move에서 의도적으로 하지 않은 것

아래 작업은 mini-move 범위에서 제외했다.

```text
- constants.py 생성
- shared constants module 생성
- constants 대량 이동
- helper/function 추가 이동
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- SQLi/XSS/file disclosure hint patterns 이동
```

제외 이유:

```text
- import cycle과 원인 추적성 저하를 피하기 위함
- evidence boundary가 민감한 영역을 mechanical refactor와 섞지 않기 위함
- Apache logs-only 해석 한계를 유지하기 위함
```

## 5. 현재 상태 평가

현재까지의 constants mini-move는 여기서 멈추는 것이 적절하다.

이유:

```text
- owner가 비교적 명확한 constants group은 1차로 정리했음
- 남은 constants는 공유 경계 또는 evidence boundary가 더 민감함
- 추가 이동은 constants 이동보다 후보 비교/경계 문서가 먼저 필요함
```

바로 진행하지 않을 것:

```text
- constants.py 대량 분리
- PROBING_SEQUENCE_* 이동
- SENSITIVE_PATH_PROBE_* / DIR_PROBE_* 이동
- MIXED_BASELINE_SCANNER_* 이동
- SQLi/XSS/file_disclosure patterns 이동
```

## 6. 권장 다음 작업

다음 작업은 constants 추가 이동이 아니라 hints split candidate review다.

권장 신규 문서:

```text
docs/design/99_prepare_hints_split_candidate_review.md
```

비교 대상:

```text
SQLi hints
XSS hints
file_disclosure hints
traversal/cmdi/automation hints
shared attack/search policy constants
```

이 문서에서 확인할 항목:

```text
- 후보별 함수명과 constants/patterns
- candidate selection 영향
- false positive suppression 영향
- supporting_events 영향
- Stage1/Stage2 wording 영향
- Apache logs-only evidence boundary
- 다음 코드 분리 후보를 고를 수 있는지 여부
```

## 7. 커밋/검증 메모

이 문서는 constants mini-move summary 기록용이다.

문서 작성 시 기대 변경 범위:

```text
docs/design/99_prepare_constants_mini_move_summary.md
```

코드 변경은 없다.

문서 전용 커밋 후보:

```text
docs: summarize prepare constants mini moves
```
