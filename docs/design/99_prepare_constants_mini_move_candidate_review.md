# 99_prepare_constants_mini_move_candidate_review

- 문서 상태: prepare constants mini-move 후보 검토
- 기준 시점: 2026-05-04
- 목적: `99_prepare_constants_ownership_map.md` 이후 실제 constants 이동을 바로 수행하지 않고, 소규모 이동 가능 후보와 보류 후보를 분리한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md)
- [99_prepare_probing_sequence_split_plan.md](./99_prepare_probing_sequence_split_plan.md)
- [99_prepare_mixed_baseline_scanner_split_plan.md](./99_prepare_mixed_baseline_scanner_split_plan.md)

## 1. 결론

지금은 `constants.py` 대량 분리를 하지 않는다.

검토 결과, 다음 단계는 **safe constants mini-move 후보를 grep으로 확인한 뒤 하나만 고르는 것**이 적절하다.

현재 우선순위:

```text
1. PROTOCOL_ANOMALY_* constants 검토
2. IP_BEHAVIOR_* constants 검토
3. METHOD_BEHAVIOR_* constants 검토
4. STATIC_BASELINE_* constants 검토
```

단, 실제 이동은 이 문서에서 하지 않는다. 이 문서는 이동 후보를 분류하고 다음 검증 명령을 정리하는 문서다.

현재 추천 next candidate:

```text
PROTOCOL_ANOMALY_* constants
```

이유:

```text
- owner module이 `src/prepare/protocol_anomalies.py`로 비교적 명확할 가능성이 높음
- constants 수가 적음
- SQLi/XSS/file disclosure evidence boundary와 직접 결합되지 않음
- sensitive/probing/mixed scanner처럼 path category 공유 위험이 낮음
```

## 2. mini-move 공통 원칙

constants 이동을 검토할 때 아래 원칙을 유지한다.

```text
- constants.py 대량 분리 금지
- 한 번에 한 constants group만 검토
- behavior 변경 금지
- output key 변경 금지
- policy wording 변경 금지
- expected/test fixture 수정 금지
- Stage2 reporter 수정 금지
- candidate/scoring/filtering 변경 금지
- supporting_events 생성/연결 로직 변경 금지
- Apache logs-only 해석 원칙 유지
```

실제 이동이 가능하더라도 아래 방식으로 제한한다.

```text
- owner module이 명확한 constants만 module-local로 이동
- 공유 constants는 `src/prepare_llm_input.py`에 유지
- import cycle 위험이 있으면 이동하지 않음
- constants 이동과 helper/function 이동을 같은 커밋에 섞지 않음
- constants 이동과 policy wording 변경을 같은 커밋에 섞지 않음
```

## 3. 검토 기준

각 constants group은 아래 기준으로 판단한다.

```text
1. owner module이 명확한가?
2. grep 결과 다른 모듈 또는 다른 helper 계열에서 직접 참조하지 않는가?
3. wrapper 인자 전달보다 module-local constant가 단순한가?
4. import cycle 없이 이동 가능한가?
5. regression 실패 시 원인 추적이 쉬운가?
6. Apache logs-only evidence boundary를 흔들지 않는가?
7. false positive suppression 또는 candidate preservation 의미를 바꾸지 않는가?
```

판정 값:

```text
MOVE_CANDIDATE
GREP_FIRST
KEEP_FOR_NOW
DO_NOT_MOVE_IN_BULK
```

## 4. 후보 비교 요약

| 후보 | 예상 owner | 현재 판단 | 이유 |
|---|---|---|---|
| `PROTOCOL_ANOMALY_*` | `protocol_anomalies.py` | `MOVE_CANDIDATE` | constants 수가 적고 owner가 비교적 명확함 |
| `IP_BEHAVIOR_*` | `ip_behavior.py` | `GREP_FIRST` | 독립적이지만 sensitive path limit이 경계 공유 가능 |
| `METHOD_BEHAVIOR_*` / method families | `method_summaries.py` | `GREP_FIRST` | method/protocol 경계와 `STANDARD_HTTP_METHODS` 공유 가능성 확인 필요 |
| `STATIC_BASELINE_*` | `static_baseline.py` | `GREP_FIRST` | static/crawler/mixed scanner 경계 확인 필요 |
| `PROBING_SEQUENCE_*` | `probing_sequence.py` | `KEEP_FOR_NOW` | sensitive path/mixed scanner와 path hint 경계 공유 가능 |
| `SENSITIVE_PATH_PROBE_*` / `DIR_PROBE_*` | `sensitive_path_probe.py` | `KEEP_FOR_NOW` | file disclosure/probing/mixed scanner와 경계 공유 가능 |
| `MIXED_BASELINE_SCANNER_*` | `mixed_baseline_scanner.py` | `KEEP_FOR_NOW` | 여러 context summary가 섞이는 영역 |
| SQLi/XSS/file disclosure patterns | future hint modules | `DO_NOT_MOVE_IN_BULK` | evidence boundary와 FP suppression에 직접 연결 |
| generic attack/search policy constants | shared policy 후보 | `DO_NOT_MOVE_IN_BULK` | 여러 hint 계열이 공유 가능 |

## 5. 후보 1: PROTOCOL_ANOMALY_* constants

대상 constants:

```text
PROTOCOL_ANOMALY_WINDOW_SEC
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN
```

예상 owner:

```text
src/prepare/protocol_anomalies.py
```

현재 판단:

```text
MOVE_CANDIDATE
```

검토 이유:

```text
- protocol anomaly 모듈은 이미 분리되어 있음
- constants 수가 적음
- malformed request/protocol anomaly summary 계열에 topic-local일 가능성이 높음
- sensitive path/probing/mixed scanner보다 공유 위험이 낮음
```

주의할 evidence boundary:

```text
- protocol bypass 성공 단정 금지
- malformed request exploit success 단정 금지
- 서버 침해 성공 단정 금지
- status_code나 error log 존재만으로 exploit 성공 판단 금지
```

이동 전 확인 명령:

```bash
grep -n "PROTOCOL_ANOMALY_" src/prepare_llm_input.py src/prepare/*.py
```

이동 가능 조건:

```text
- `PROTOCOL_ANOMALY_*` 참조가 protocol anomaly wrapper/모듈에만 있음
- `src/prepare/protocol_anomalies.py`가 `src/prepare_llm_input.py`를 import하지 않음
- 이동 후 wrapper 기본값이나 호출부 의미가 바뀌지 않음
- prepare/stage dry-run regression이 그대로 통과함
```

권장 다음 split plan:

```text
docs/design/99_prepare_protocol_anomaly_constants_move_plan.md
```

실제 이동 커밋 후보:

```text
refactor: move protocol anomaly constants
```

## 6. 후보 2: IP_BEHAVIOR_* constants

대상 constants:

```text
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

예상 owner:

```text
src/prepare/ip_behavior.py
```

현재 판단:

```text
GREP_FIRST
```

검토 이유:

```text
- ip_behavior.py는 이미 분리됨
- IP behavior aggregate는 비교적 독립적임
- 다만 `IP_BEHAVIOR_SENSITIVE_PATH_LIMIT`는 sensitive path/probing 계열과 의미 경계가 겹칠 수 있음
```

주의할 evidence boundary:

```text
- 특정 IP를 attacker identity로 단정하지 않음
- source IP만으로 공격 의도, 공격 성공, 침해 성공을 단정하지 않음
- IP 단위 집계는 관찰된 요청 묶음이지 신원 식별 결과가 아님
```

확인 명령:

```bash
grep -n "IP_BEHAVIOR_" src/prepare_llm_input.py src/prepare/*.py
```

이동 가능 조건:

```text
- `IP_BEHAVIOR_*` 참조가 ip_behavior wrapper/모듈에만 있음
- sensitive path/probing/mixed scanner에서 직접 참조하지 않음
- `IP_BEHAVIOR_SENSITIVE_PATH_LIMIT` 의미가 흔들리지 않음
```

현재 결론:

```text
PROTOCOL_ANOMALY_*보다 후순위
```

## 7. 후보 3: METHOD_BEHAVIOR_* / method constants

대상 constants:

```text
METHOD_BEHAVIOR_WINDOW_SEC
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT
METHOD_RISKY_FAMILIES
METHOD_BASELINE_FAMILIES
METHOD_DESTRUCTIVE_FAMILIES
STANDARD_HTTP_METHODS
```

예상 owner:

```text
src/prepare/method_summaries.py
```

현재 판단:

```text
GREP_FIRST
```

검토 이유:

```text
- method_summaries.py는 이미 분리됨
- method behavior constants 일부는 module-local일 수 있음
- 하지만 `STANDARD_HTTP_METHODS`는 protocol anomaly와 경계가 있을 수 있음
- `METHOD_RISKY_FAMILIES`, `METHOD_DESTRUCTIVE_FAMILIES`는 PUT/DELETE/TRACE/OPTIONS 해석 제한과 연결됨
```

주의할 evidence boundary:

```text
- PUT 업로드 성공 단정 금지
- DELETE 삭제 성공 단정 금지
- TRACE/XST 성공 단정 금지
- OPTIONS/CORS 취약점 성공 단정 금지
```

확인 명령:

```bash
grep -n "METHOD_BEHAVIOR_\|METHOD_RISKY_FAMILIES\|METHOD_BASELINE_FAMILIES\|METHOD_DESTRUCTIVE_FAMILIES\|STANDARD_HTTP_METHODS" src/prepare_llm_input.py src/prepare/*.py
```

현재 결론:

```text
`STANDARD_HTTP_METHODS` 공유 여부 확인 전까지 보류
```

## 8. 후보 4: STATIC_BASELINE_* / static constants

대상 constants:

```text
STATIC_BASELINE_WINDOW_SEC
STATIC_BASELINE_MIN_STATIC_PATHS
STATIC_BASELINE_SAMPLE_REQUEST_LIMIT
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

예상 owner:

```text
src/prepare/static_baseline.py
```

현재 판단:

```text
GREP_FIRST
```

검토 이유:

```text
- static_baseline.py는 이미 분리됨
- 하지만 static constants는 crawler baseline, mixed scanner, health-like path 해석과 경계가 있음
- static file 존재/JS 실행/health 정상 여부를 단정하지 않는 policy와 연결됨
```

주의할 evidence boundary:

```text
- static file 존재 단정 금지
- JS 실행 단정 금지
- robots/sitemap 내용 단정 금지
- health 정상 여부 단정 금지
- response bytes/content-type만으로 file exposure 단정 금지
```

확인 명령:

```bash
grep -n "STATIC_BASELINE_\|STATIC_EXTENSIONS\|STATIC_PREFIXES\|HEALTH_LIKE_PATHS" src/prepare_llm_input.py src/prepare/*.py
```

현재 결론:

```text
mixed scanner 경계 확인 전까지 보류
```

## 9. 계속 보류할 후보

아래 constants는 현재 mini-move 대상으로 삼지 않는다.

### 9.1 PROBING_SEQUENCE_*

보류 이유:

```text
- sensitive path probe와 path category 경계 공유 가능
- mixed baseline scanner와 중복 가능
- 여러 경로 순회를 침해/노출/성공으로 단정하지 않는 policy와 연결됨
```

### 9.2 SENSITIVE_PATH_PROBE_* / DIR_PROBE_*

보류 이유:

```text
- file disclosure/probing/mixed scanner와 경계 공유 가능
- sensitive path supporting event 생성/연결 로직은 아직 이동하지 않았음
- .env/phpinfo/server-status/backup 노출 단정 금지와 직접 연결됨
```

### 9.3 MIXED_BASELINE_SCANNER_*

보류 이유:

```text
- static/crawler/sensitive/probing/IP context가 섞이는 영역
- round2에서 방금 분리한 고위험 context summary
- context-only 경계를 더 안정화한 뒤 검토
```

### 9.4 SQLi/XSS/file disclosure patterns

보류 이유:

```text
- candidate selection, false positive suppression, supporting context와 연결됨
- evidence boundary가 민감함
- SQLi는 DB 결과를 볼 수 없음
- XSS는 브라우저 실행 여부를 볼 수 없음
- file disclosure는 response body 원문/파일 내용/실제 노출 여부를 볼 수 없음
```

### 9.5 generic attack/search policy constants

보류 이유:

```text
- 여러 hint 계열이 공유할 수 있음
- false positive suppression과 candidate preservation의 경계에 있음
- shared hint policy 모듈을 새로 만들기 전에는 이동하지 않음
```

## 10. 권장 다음 작업

다음 작업은 아래 순서가 적절하다.

```text
1. PROTOCOL_ANOMALY_* grep 결과 확인
2. docs/design/99_prepare_protocol_anomaly_constants_move_plan.md 작성
3. protocol anomaly constants만 소규모 이동할지 결정
```

명령:

```bash
grep -n "PROTOCOL_ANOMALY_" src/prepare_llm_input.py src/prepare/*.py
```

이동을 진행한다면 반드시 단일 커밋으로 제한한다.

예상 변경 범위:

```text
src/prepare/protocol_anomalies.py
src/prepare_llm_input.py
```

예상 검증:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

성공 기준:

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
output key 의미 변경 없음
policy wording 변경 없음
expected/test fixture 수정 없음
```

## 11. TODO 반영 후보

이 문서 작성 후 TODO에는 아래 상태로 반영한다.

```text
P4 prepare 모듈 분리 — protocol anomaly constants move plan 대기

최근 완료:
- constants mini-move candidate review 작성
- constants.py 대량 분리는 보류
- 다음 소규모 후보를 PROTOCOL_ANOMALY_* constants로 결정

다음 작업:
- docs/design/99_prepare_protocol_anomaly_constants_move_plan.md 작성
```

문서 전용 커밋 후보:

```text
docs: review prepare constants mini move candidates
```
