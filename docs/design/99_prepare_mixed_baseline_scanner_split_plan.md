# 99_prepare_mixed_baseline_scanner_split_plan

- 문서 상태: `mixed_baseline_scanner_summaries` split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `447779f94041c47713ad3bf68a31d7125a223675`
- 목적: `mixed_baseline_scanner_summaries` 계열의 코드 분리 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md)
- [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md)
- [99_prepare_probing_sequence_split_plan.md](./99_prepare_probing_sequence_split_plan.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)

## 1. 완료 결론

`mixed_baseline_scanner_summaries` 계열의 코드 분리는 완료했다.

신규 모듈:

```text
src/prepare/mixed_baseline_scanner.py
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
- supporting_events 생성/연결 로직 직접 변경 없음
- output key 의미 변경 없음
- policy wording 변경 없음
- static/crawler/sensitive/probing/ip behavior summary 의미 변경 없음
```

mixed baseline scanner summary는 계속 context-only 성격의 요약이다. scanner-like context를 공격 성공, 침해, 파일 노출, crawler 신원, site structure 확인, WordPress 존재, admin access 성공으로 해석하는 변경은 하지 않았다.

## 2. 이동 완료 함수

아래 함수 3개를 `src/prepare/mixed_baseline_scanner.py`로 이동했다.

```text
build_mixed_baseline_scanner_row_context
finalize_mixed_baseline_scanner_bucket
build_mixed_baseline_scanner_summaries
```

`src/prepare_llm_input.py`에는 기존 함수명을 유지하는 wrapper를 남겼다.

유지한 import 패턴:

```text
try:
    from src.prepare.mixed_baseline_scanner import ... as _...
except ImportError:
    from prepare.mixed_baseline_scanner import ... as _...
```

이 분리는 mixed baseline scanner summary builder와 전용 helper만 좁게 옮긴 것이다. main payload 구성, counts 계산, policy notes, Stage2 reporter는 바꾸지 않았다.

## 3. 이동하지 않은 constants

아래 constants는 이동하지 않았다.

```text
MIXED_BASELINE_SCANNER_WINDOW_SEC
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT
```

유지 이유:

```text
- mixed scanner는 static/crawler/sensitive/probing/IP behavior와 경계가 겹칠 수 있다.
- constants 이동까지 함께 하면 regression 실패 시 원인 추적이 어려워진다.
- constants.py 대량 분리는 별도 ownership map 이후에 검토한다.
```

## 4. 이동하지 않은 영역

이번 분리에서 아래 영역은 이동하거나 수정하지 않았다.

```text
- static_baseline helper
- crawler_baseline helper
- sensitive_path_probe helper
- probing_sequence helper
- ip_behavior helper
- supporting_events 생성/연결 로직
- candidate/scoring/filtering 로직
- SQLi/XSS/file disclosure hint helper
- Stage2 reporter
- expected/test fixture
```

## 5. 유지한 output 계약

아래 output/policy/count 위치는 유지했다.

```text
mixed_baseline_scanner_summaries
counts.mixed_baseline_scanner_summaries
policy_notes.mixed_baseline_scanner_summaries_are_context_only
policy_notes.mixed_baseline_scanner_window_sec
```

출력 불변조건:

```text
- output key 이름 변경 없음
- count 의미 변경 없음
- sample request/path limit 의미 변경 없음
- candidate_rows 의미 변경 없음
- filtered_out 의미 변경 없음
- supporting_events 의미 변경 없음
- mixed baseline scanner summary를 incident로 승격하지 않음
- scanner-like context를 attack success로 해석하는 필드/문구 추가 없음
```

## 6. Apache logs-only 해석 원칙

이번 분리 이후에도 아래 제한을 유지한다.

```text
- scanner-like context만으로 침해 성공을 단정하지 않는다.
- static/crawler/sensitive/probing/IP context가 섞였다는 이유만으로 공격 확정을 하지 않는다.
- static file 존재를 단정하지 않는다.
- JS 실행을 단정하지 않는다.
- robots/sitemap 내용이나 site structure를 단정하지 않는다.
- 실제 crawler identity를 단정하지 않는다.
- product/category page existence를 단정하지 않는다.
- WordPress 존재를 단정하지 않는다.
- admin access 성공을 단정하지 않는다.
- .env/phpinfo/server-status/backup 노출을 단정하지 않는다.
- status_code=200, content-type, response_body_bytes만으로 성공/노출/침해를 판단하지 않는다.
```

허용되는 표현:

```text
- mixed baseline/scanner-like context
- observed scanner-like request blend
- static/crawler/sensitive/probing context overlap
- context-only mixed scanner summary
- multiple baseline signals observed in the same time window
```

금지 표현:

```text
- scanner succeeded
- server compromise confirmed
- file exposure confirmed
- site structure was mapped
- real crawler identified
- WordPress exists
- admin access succeeded
- .env/phpinfo/server-status/backup was exposed
```

## 7. 기존 분리 모듈과의 경계

이번 분리 이후에도 아래 경계를 유지한다.

```text
- static_baseline_summaries는 static asset baseline/context를 다룬다.
- crawler_baseline_summaries는 crawler-like baseline/context를 다룬다.
- sensitive_path_probe_summaries는 민감 경로 probing context를 다룬다.
- probing_sequence_summaries는 시간 창 안의 여러 경로 순회 패턴을 다룬다.
- ip_behavior_aggregates는 source-IP-scoped request aggregate를 다룬다.
- mixed_baseline_scanner_summaries는 위 신호가 섞인 scanner-like context를 별도로 보존한다.
```

하지 않은 것:

```text
- static_baseline.py 수정
- crawler_baseline.py 수정
- sensitive_path_probe.py 수정
- probing_sequence.py 수정
- ip_behavior.py 수정
- 각 summary를 하나로 병합
- context-only summary를 candidate/incident로 승격
```

## 8. 검증 결과

기준 커밋 `447779f94041c47713ad3bf68a31d7125a223675`에서 아래 검증을 통과했다.

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

## 9. 롤백 기준

향후 관련 추가 분리에서 아래 중 하나라도 발생하면 해당 분리 커밋을 수정하거나 롤백한다.

```text
- prepare regression fail
- stage dry-run regression fail
- import cycle 발생
- mixed_baseline_scanner_summaries 누락
- pipeline_counts/counts 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- sample request/path limit 의미 변경
- static/crawler/sensitive/probing/ip behavior summary 변화
- scanner-like context를 공격 성공/침해/노출로 단정하는 문구 발생
- 특정 IP, lab-* UA, response size, product/route에 과적합하는 문구 발생
```

## 10. 다음 작업

`mixed_baseline_scanner_summaries` 분리는 완료했다.

round2에서 계획했던 context summary 후보 3개는 모두 완료 상태다.

```text
src/prepare/ip_behavior.py
src/prepare/probing_sequence.py
src/prepare/mixed_baseline_scanner.py
```

다음 작업은 바로 constants.py 대량 분리로 가지 않고, round2 summary를 먼저 작성한다.

권장 다음 문서:

```text
docs/design/99_prepare_module_split_round2_summary.md
```

round2 summary에서 정리할 항목:

```text
- round2 완료 모듈 3개
- 이동 함수 목록
- constants 이동 없음
- wrapper 유지
- fixture/expected/Stage2 reporter 수정 없음
- prepare/stage dry-run regression 결과
- 보류 후보: constants.py 대량 분리, SQLi hints, XSS hints, file_disclosure hints
- 다음 후보 결정 기준
```

문서 전용 커밋 후보:

```text
docs: record mixed baseline scanner split
```
