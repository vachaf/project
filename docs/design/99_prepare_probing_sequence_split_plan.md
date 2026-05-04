# 99_prepare_probing_sequence_split_plan

- 문서 상태: `probing_sequence_summaries` split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `85a5508e5308d5bcdfc9f1fc14948ed233007f32`
- 목적: `probing_sequence_summaries` 계열의 코드 분리 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md)
- [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)

## 1. 완료 결론

`probing_sequence_summaries` 계열의 코드 분리는 완료했다.

신규 모듈:

```text
src/prepare/probing_sequence.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이번 작업은 mechanical refactor로 제한했다.

```text
- `src/prepare_llm_input.py`에는 기존 공개 함수명 wrapper 유지
- constants 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- output key 의미 변경 없음
- policy wording 변경 없음
```

probing sequence summary는 계속 context-only 성격의 요약이다. 여러 경로 순회 정황을 공격 성공, 침해, 파일 노출, WordPress 존재, admin access 성공으로 해석하는 변경은 하지 않았다.

## 2. 이동 완료 함수

아래 함수 2개를 `src/prepare/probing_sequence.py`로 이동했다.

```text
finalize_probing_sequence_bucket
build_probing_sequence_summaries
```

`src/prepare_llm_input.py`에는 기존 함수명을 유지하는 wrapper를 남겼다.

유지한 import 패턴:

```text
try:
    from src.prepare.probing_sequence import ... as _...
except ImportError:
    from prepare.probing_sequence import ... as _...
```

이 분리는 probing sequence summary builder와 전용 finalize helper만 좁게 옮긴 것이다. main payload 구성, counts 계산, policy notes, Stage2 reporter는 바꾸지 않았다.

## 3. 이동하지 않은 constants

아래 constants는 이동하지 않았다.

```text
PROBING_SEQUENCE_PATH_PREFIX_HINTS
PROBING_SEQUENCE_PATH_SEGMENT_HINTS
PROBING_SEQUENCE_SUFFIX_HINTS
PROBING_SEQUENCE_WINDOW_SEC
PROBING_SEQUENCE_MIN_REQUESTS
PROBING_SEQUENCE_MIN_DISTINCT_PATHS
PROBING_SEQUENCE_SAMPLE_PATH_LIMIT
```

유지 이유:

```text
- PROBING_SEQUENCE_* constants는 sensitive path probe와 path category 경계가 겹칠 수 있다.
- mixed baseline scanner도 probing sequence 조건을 참조할 가능성이 있다.
- constants 이동까지 함께 하면 regression 실패 시 원인 추적이 어려워진다.
- constants.py 대량 분리는 별도 ownership map 이후에 검토한다.
```

## 4. 이동하지 않은 영역

이번 분리에서 아래 영역은 이동하거나 수정하지 않았다.

```text
- PROBING_SEQUENCE_* constants를 사용하는 다른 path hint 계열 함수
- sensitive_path_probe helper
- mixed_baseline_scanner helper
- supporting_events 생성/연결 로직
- candidate/scoring/filtering 로직
- Stage2 reporter
- expected/test fixture
```

## 5. 유지한 output 계약

아래 output/policy/count 위치는 유지했다.

```text
probing_sequence_summaries
counts.probing_sequence_summaries
policy_notes.probing_sequence_summaries_are_context_only
policy_notes.probing_sequence_window_sec
```

출력 불변조건:

```text
- output key 이름 변경 없음
- count 의미 변경 없음
- sample path/request limit 의미 변경 없음
- candidate_rows 의미 변경 없음
- filtered_out 의미 변경 없음
- supporting_events 의미 변경 없음
- probing sequence summary를 incident로 승격하지 않음
- sequence 정황을 attack success로 해석하는 필드/문구 추가 없음
```

## 6. Apache logs-only 해석 원칙

이번 분리 이후에도 아래 제한을 유지한다.

```text
- 여러 경로를 순회했다는 사실만으로 침해 성공을 단정하지 않는다.
- admin page 존재를 단정하지 않는다.
- WordPress 존재를 단정하지 않는다.
- .env 노출을 단정하지 않는다.
- phpinfo 노출을 단정하지 않는다.
- server-status 노출 또는 차단 성공을 단정하지 않는다.
- backup/config 노출을 단정하지 않는다.
- static file 존재나 site structure를 단정하지 않는다.
- scanner-like sequence는 context이지 incident 확정 근거가 아니다.
- status_code=200, content-type, response_body_bytes만으로 성공/노출/침해를 판단하지 않는다.
```

허용되는 표현:

```text
- observed probing-like request sequence
- scanner-like path traversal context
- repeated multi-path request context
- source-scoped probing sequence context
- sensitive or administrative path probing context, if supported by paths
```

금지 표현:

```text
- exploitation succeeded
- server compromise confirmed
- WordPress exists
- admin access succeeded
- .env was exposed
- phpinfo was exposed
- server-status was exposed
- backup file was disclosed
- scanner successfully mapped the site
```

## 7. 검증 결과

기준 커밋 `85a5508e5308d5bcdfc9f1fc14948ed233007f32`에서 아래 검증을 통과했다.

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

수정하지 않은 영역:

```text
- tests/fixtures
- tests/expected
- src/llm_stage2_reporter.py
- src/llm_stage1_classifier.py
- src/run_analysis_pipeline.py
```

## 8. 롤백 기준

향후 관련 추가 분리에서 아래 중 하나라도 발생하면 해당 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- import cycle 발생
- probing_sequence_summaries 누락
- pipeline_counts 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- sample path/request limit 의미 변경
- sensitive path probe summary 변화
- mixed baseline scanner summary 변화
- 여러 경로 순회를 공격 성공/침해/노출로 단정하는 문구 발생
- 특정 IP, lab-* UA, response size, product/route에 과적합하는 문구 발생
```

## 9. 다음 작업

`probing_sequence_summaries` 분리는 완료했다.

round2 후보 비교 기준상 다음 후보는 `mixed_baseline_scanner_summaries`다. 다만 이 후보는 static/crawler/sensitive/probing context가 섞일 가능성이 높으므로 바로 코드 분리하지 않고 split plan 문서를 먼저 작성한다.

권장 다음 문서:

```text
docs/design/99_prepare_mixed_baseline_scanner_split_plan.md
```

다음 후보에서 특히 주의할 점:

```text
- mixed scanner context를 incident로 과승격하지 않음
- static/crawler/sensitive/probing summary와 경계를 명확히 함
- status_code, content_type, response_body_bytes만으로 성공/노출 단정 금지
- constants 이동 없이 wrapper 전달 방식을 우선 검토
```

문서 전용 커밋 후보:

```text
docs: record probing sequence split
```
