# 99_prepare_module_split_round2_candidate_review

- 문서 상태: prepare module split round2 후보 비교 및 다음 후보 결정
- 기준 시점: 2026-05-04
- 목적: round1 분리 완료 이후 남은 후보인 `mixed_baseline_scanner_summaries`, `probing_sequence_summaries`, `ip_behavior_aggregates`, `constants.py` 대량 분리를 비교하고, 다음 코드 분리 후보를 하나로 고정한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)

## 1. 결론

round2의 다음 코드 분리 후보는 `ip_behavior_aggregates`로 잡는다.

권장 신규 split plan 문서:

```text
docs/design/99_prepare_ip_behavior_aggregates_split_plan.md
```

그 다음에 실제 코드 분리를 검토한다.

권장 신규 모듈 후보:

```text
src/prepare/ip_behavior.py
```

현재 우선순위:

```text
1. ip_behavior_aggregates
2. probing_sequence_summaries
3. mixed_baseline_scanner_summaries
4. constants.py 대량 분리
```

단, 이 문서는 코드 분리 커밋이 아니다. 후보 비교와 다음 후보 결정만 기록한다.

## 2. round2 공통 원칙

round2에서도 round1과 같은 제한을 유지한다.

```text
- mechanical refactor만 수행
- constants 이동 없음, 필요하면 wrapper에서 인자로 전달
- prepare_llm_input.py에는 기존 공개 함수명 wrapper 유지
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- output key 의미 변경 없음
- pipeline_counts 의미 변경 없음
- supporting_events 구조 변경 없음
- policy wording 변경 없음
- Apache logs-only 해석 원칙 유지
```

추가로 round2 후보들은 baseline/context/candidate 경계가 더 민감하므로, split plan 작성 전에 반드시 아래를 확인한다.

```bash
grep -n "build_ip_behavior_aggregates\|ip_behavior_aggregates\|IP_BEHAVIOR" src/prepare_llm_input.py
grep -n "build_probing_sequence_summaries\|probing_sequence_summaries\|PROBING_SEQUENCE" src/prepare_llm_input.py
grep -n "build_mixed_baseline_scanner_summaries\|mixed_baseline_scanner_summaries\|MIXED_BASELINE_SCANNER" src/prepare_llm_input.py
```

확인할 항목:

```text
- 함수명
- 호출 위치
- 입력 rows/candidates/filtered/supporting 구조
- output key
- pipeline_counts 반영 여부
- supporting_events 연결 여부
- constants 의존성
- expected fixture 고정 지점
- Stage2 prompt/report에서 노출되는 문구
```

## 3. 평가 기준

다음 코드 분리 후보는 아래 기준으로 판단한다.

```text
1. output key와 expected fixture 영향이 작을 것
2. candidate/scoring/filtering에 직접 영향을 덜 줄 것
3. supporting_events와 강하게 결합되어 있지 않을 것
4. constants 이동을 최소화할 수 있을 것
5. Apache logs-only 해석 제한을 독립적으로 문서화할 수 있을 것
6. 실패 시 롤백 범위가 작을 것
7. 다른 context summary와 경계가 비교적 선명할 것
```

판단 결과 요약:

| 후보 | 결론 | 이유 |
|---|---|---|
| `ip_behavior_aggregates` | 다음 후보 | 기능 경계가 비교적 독립적이고, constants 의존 범위가 좁으며, split plan으로 해석 제한을 명확히 고정하기 좋음 |
| `probing_sequence_summaries` | 2순위 | sequence summary 경계는 있지만 sensitive path/probing constants와 결합되어 있음 |
| `mixed_baseline_scanner_summaries` | 보류 | 여러 baseline/scanner 신호가 섞여 candidate/context 경계가 흔들릴 위험이 큼 |
| `constants.py` 대량 분리 | 후순위 | import cycle과 원인 추적성 저하 위험이 큼 |

## 4. 후보 1: ip_behavior_aggregates

### 4.1 현재 판단

`ip_behavior_aggregates`를 round2의 다음 split candidate로 결정한다.

이유:

```text
- 후보군 중 기능 경계가 가장 독립적일 가능성이 높음
- IP 단위 집계/요약은 별도 모듈로 분리하기 쉬움
- mixed scanner나 probing sequence보다 path category 공유 위험이 낮음
- constants 의존 범위가 비교적 좁음
- wrapper 유지 방식으로 mechanical refactor를 적용하기 쉬움
- split plan에서 IP 해석 제한을 명확히 고정할 수 있음
```

예상 관련 constants:

```text
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

1차 분리에서는 위 constants를 이동하지 않는다. 필요하면 `prepare_llm_input.py` wrapper에서 인자로 넘긴다.

### 4.2 Apache logs-only 해석 제한

IP behavior aggregate는 특히 과해석 위험이 있다. 아래 제한을 반드시 유지한다.

```text
- 특정 IP를 attacker identity로 단정하지 않음
- 특정 IP를 실험환경 공격 주체로 일반화하지 않음
- source IP만으로 공격 의도나 침해 성공을 단정하지 않음
- 요청량/경로 다양성만으로 compromise를 단정하지 않음
- lab/source IP를 공격 근거로 사용하지 않음
- IP 단위 집계는 관찰된 요청 묶음이지 신원 식별 결과가 아님
```

허용되는 표현:

```text
- observed requests grouped by source IP
- IP-level request concentration
- repeated request context
- source-IP-scoped context summary
- scanner-like behavior context, if supported by request patterns
```

금지 표현:

```text
- attacker IP 확정
- compromised host 확정
- account takeover source 확정
- botnet node 확정
- 동일 공격자 확정
- lab IP이므로 공격 확정
```

### 4.3 split plan에서 확인할 항목

`docs/design/99_prepare_ip_behavior_aggregates_split_plan.md` 작성 시 아래를 확인한다.

```text
- 함수명: build_ip_behavior_aggregates 계열
- 입력: rows / candidates / filtered rows / supporting_events 사용 여부
- 출력: ip_behavior_aggregates output key
- pipeline_counts 반영 여부
- Stage2 prompt/report 노출 여부
- candidate_rows 또는 supporting_events에 직접 영향을 주는지
- IP 관련 constants 의존성
- sensitive path count 또는 sample request 제한과 연결되는지
- expected fixture에서 고정하는 key가 있는지
```

### 4.4 허용되는 코드 분리 범위

다음 코드 분리에서 허용되는 범위:

```text
- src/prepare/ip_behavior.py 생성
- ip behavior aggregate builder 함수 이동
- ip behavior 전용 helper 이동
- prepare_llm_input.py에 기존 함수명 wrapper 유지
- constants는 이동하지 않고 wrapper에서 전달
```

금지 범위:

```text
- constants.py 대량 분리
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- output key 변경
- policy wording 변경
- expected/test fixture 수정
- Stage2 reporter 수정
- IP를 attacker identity로 해석하는 문구 추가
```

## 5. 후보 2: probing_sequence_summaries

### 5.1 현재 판단

`probing_sequence_summaries`는 round2의 2순위 후보로 둔다. 바로 코드 분리하지 않는다.

이유:

```text
- sequence summary라는 기능 경계는 존재함
- 그러나 sensitive path/probing constants와 일부 경계가 겹침
- path prefix/segment/suffix 판단이 sensitive path probe와 연결될 가능성이 있음
- mixed scanner summary와도 중복될 수 있음
- probing sequence를 candidate로 과승격할 위험이 있음
```

예상 관련 constants:

```text
PROBING_SEQUENCE_WINDOW_SEC
PROBING_SEQUENCE_MIN_REQUESTS
PROBING_SEQUENCE_MIN_DISTINCT_PATHS
PROBING_SEQUENCE_SAMPLE_PATH_LIMIT
PROBING_SEQUENCE_PATH_PREFIX_HINTS
PROBING_SEQUENCE_PATH_SEGMENT_HINTS
PROBING_SEQUENCE_SUFFIX_HINTS
```

위 constants는 sensitive path probe 문서에서도 이동 보류로 기록한 상태다. 따라서 probing sequence를 분리할 경우 constants 이동 없이 wrapper 전달 방식부터 검토해야 한다.

### 5.2 Apache logs-only 해석 제한

유지할 제한:

```text
- 여러 경로를 순회했다는 사실만으로 침해 성공을 단정하지 않음
- admin page 존재를 단정하지 않음
- WordPress 존재를 단정하지 않음
- .env/phpinfo/server-status/backup 노출을 단정하지 않음
- scanner-like sequence는 context이지 incident 확정 근거가 아님
```

### 5.3 다음 검토 조건

probing sequence를 다음 후보로 올리려면 먼저 아래를 확인한다.

```text
- sensitive_path_probe.py와의 의존 방향
- PROBING_SEQUENCE_* constants ownership
- mixed_baseline_scanner_summaries와 중복되는 조건
- output key와 pipeline_counts 영향
- supporting_events 연결 여부
- expected fixture 고정 지점
```

권장 split plan 후보:

```text
docs/design/99_prepare_probing_sequence_split_plan.md
```

## 6. 후보 3: mixed_baseline_scanner_summaries

### 6.1 현재 판단

`mixed_baseline_scanner_summaries`는 보류한다.

이유:

```text
- 이름 그대로 여러 baseline/context 신호가 섞인 영역일 가능성이 높음
- static baseline, crawler baseline, sensitive path probe, probing sequence와 경계가 겹칠 수 있음
- scanner-like 문맥을 candidate로 과승격할 위험이 있음
- context-only summary와 incident 후보의 경계가 흔들릴 수 있음
- 분리 실패 시 영향 범위가 넓을 가능성이 큼
```

예상 관련 constants:

```text
MIXED_BASELINE_SCANNER_WINDOW_SEC
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT
```

### 6.2 Apache logs-only 해석 제한

유지할 제한:

```text
- mixed scanner context만으로 침해 성공 단정 금지
- 정상 baseline과 scanner-like 요청이 섞였다는 사실만으로 공격 확정 금지
- static/crawler/sensitive path/probing context를 incident로 병합하지 않음
- status_code, content_type, response_body_bytes만으로 성공/노출 단정 금지
```

### 6.3 다음 검토 조건

mixed baseline scanner는 split plan보다 먼저 inventory가 필요하다.

확인할 항목:

```text
- 어떤 baseline summary를 참조하는지
- 어떤 scanner-like 조건을 사용하는지
- output key와 pipeline_counts 영향
- candidate_rows와 supporting_events 연결 여부
- static/crawler/sensitive/probing summary와의 중복
- Stage2 report에서 context-only로 유지되는지
```

권장 split plan 후보:

```text
docs/design/99_prepare_mixed_baseline_scanner_split_plan.md
```

단, 이 문서는 `ip_behavior_aggregates`와 `probing_sequence_summaries` 검토 이후가 적절하다.

## 7. 후보 4: constants.py 대량 분리

### 7.1 현재 판단

`constants.py` 대량 분리는 round2에서 하지 않는다.

이유:

```text
- 여러 summary/helper가 constants를 공유함
- import cycle 위험이 큼
- constants 이동은 behavior 변경이 없어도 regression 실패 시 원인 추적을 어렵게 함
- sensitive/probing/mixed/file disclosure 경계가 아직 완전히 고정되지 않음
- constants를 한 번에 이동하면 작은 커밋 원칙을 깨기 쉬움
```

### 7.2 대안

대량 분리 대신 ownership map을 먼저 작성한다.

권장 문서:

```text
docs/design/99_prepare_constants_ownership_map.md
```

포함할 내용:

```text
- constants 이름
- 현재 사용 함수
- 예상 owner module
- 공유 여부
- 이동 가능 여부
- 이동 금지/보류 이유
- import 방향 원칙
```

### 7.3 가능해지는 조건

constants 분리는 아래 조건을 만족할 때만 검토한다.

```text
- owner module이 명확함
- 한 constants group이 한 모듈에만 사용됨
- wrapper 인자 전달보다 모듈 내부 소유가 더 단순함
- import cycle 가능성이 낮음
- regression 실패 시 원인 추적이 가능함
```

## 8. 최종 결정

다음 코드 분리 후보:

```text
ip_behavior_aggregates
```

다음 문서 작업:

```text
docs/design/99_prepare_ip_behavior_aggregates_split_plan.md
```

예상 코드 작업 범위:

```text
src/prepare/ip_behavior.py 생성
build_ip_behavior_aggregates 계열 함수 이동
ip behavior 전용 helper만 이동
prepare_llm_input.py wrapper 유지
constants 이동 없음
expected/test fixture 수정 없음
Stage2 reporter 수정 없음
candidate/scoring/filtering 변경 없음
```

검증 기준:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

성공 기준:

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
candidate_rows 의미 변경 없음
supporting_events 의미 변경 없음
pipeline_counts 의미 변경 없음
IP를 attacker identity로 단정하는 문구 없음
```

## 9. TODO 반영 후보

이 문서 작성 후 TODO에는 아래 상태로 반영한다.

```text
P4 prepare 모듈 분리 — ip_behavior_aggregates split plan 작성 대기

최근 완료:
- round2 후보 비교 문서 작성
- 다음 코드 분리 후보를 ip_behavior_aggregates로 결정

다음 작업:
- docs/design/99_prepare_ip_behavior_aggregates_split_plan.md 작성
```

문서 전용 커밋 후보:

```text
docs: compare prepare split round2 candidates
```
