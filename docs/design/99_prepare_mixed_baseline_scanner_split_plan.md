# 99_prepare_mixed_baseline_scanner_split_plan

- 문서 상태: `mixed_baseline_scanner_summaries` split plan
- 기준 시점: 2026-05-04
- 목적: `ip_behavior_aggregates`, `probing_sequence_summaries` 분리 완료 이후 round2 다음 후보인 `mixed_baseline_scanner_summaries` 계열을 실제 코드 분리 대상으로 볼 수 있는지, 분리 범위와 금지 범위, 해석 제한, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md)
- [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md)
- [99_prepare_probing_sequence_split_plan.md](./99_prepare_probing_sequence_split_plan.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md)
- [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md)

## 1. 결론

`mixed_baseline_scanner_summaries` 계열은 다음 코드 분리 후보로 검토 가능하다.

다만 지금까지 분리한 context summary 중 결합도가 가장 높을 가능성이 있다. mixed scanner는 static baseline, crawler baseline, sensitive path probe, probing sequence, IP behavior 같은 context 신호가 섞이는 영역일 수 있으므로 바로 의미 변경을 하면 안 된다.

권장 신규 모듈 후보:

```text
src/prepare/mixed_baseline_scanner.py
```

분리 방식:

```text
- mechanical refactor only
- `src/prepare_llm_input.py`에는 기존 공개 함수명 wrapper 유지
- constants 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- output key 의미 변경 없음
- policy wording 변경 없음
- static/crawler/sensitive/probing/ip behavior summary 의미 변경 없음
```

이번 분리는 mixed baseline scanner summary builder와 전용 helper만 좁게 이동한다. scanner-like context를 공격 성공, 침해, 파일 노출, crawler 신원, site structure 확인, WordPress 존재, admin access 성공으로 해석하는 변경은 하지 않는다.

## 2. 실제 코드 확인 대상

코드 작업 전 아래 grep으로 실제 함수명과 호출 위치를 확정한다.

```bash
grep -n "build_mixed_baseline_scanner_summaries\|mixed_baseline_scanner_summaries\|MIXED_BASELINE_SCANNER" src/prepare_llm_input.py
```

더 넓게 확인할 경우:

```bash
grep -n "mixed_baseline\|baseline_scanner\|scanner_summaries\|MIXED_BASELINE" src/prepare_llm_input.py
```

확인할 항목:

```text
- builder 함수명
- finalize/bucket helper 함수명
- mixed scanner 전용 classifier/helper 함수명
- 호출 위치
- main payload에 `mixed_baseline_scanner_summaries`를 넣는 위치
- `pipeline_counts` 또는 counts에 mixed scanner count를 넣는지 여부
- policy_notes에서 context-only rule을 고정하는지 여부
- Stage2 input / report에서 해당 key를 소비하는지 여부
- candidates, filtered_out, supporting_events와 직접 연결되는지 여부
- static_baseline.py, crawler_baseline.py, sensitive_path_probe.py, probing_sequence.py, ip_behavior.py와 공유하는 판단이 있는지 여부
```

현재 예상 후보:

```text
build_mixed_baseline_scanner_summaries
mixed_baseline_scanner_summaries
MIXED_BASELINE_SCANNER_WINDOW_SEC
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT
```

실제 코드에서 이름이 다르면 코드 이름을 우선한다. 이름 변경 refactor는 이번 분리와 섞지 않는다.

## 3. 입력 계약

`mixed_baseline_scanner_summaries` builder가 소비할 수 있는 입력은 Apache log에서 이미 정규화된 표면 정보로 제한한다.

허용 입력 범주:

```text
- normalized rows 또는 source rows
- src_ip
- method
- uri / raw_request_target
- query_string
- status_code
- response_body_bytes
- resp_content_type
- log_time
- request_id
- error_link_id
- user_agent
- referer
- source_table
- already prepared candidate/supporting/context summaries, if currently used
```

사용하면 안 되는 입력:

```text
- raw POST body 내용
- response body 원문
- DB query 결과
- filesystem 존재 여부
- WordPress 설치 여부
- admin login 가능 여부
- .env 내용
- phpinfo output
- server-status body
- backup archive 실제 내용
- browser execution 결과
- crawler 신원 검증 결과
- external threat intelligence identity
```

## 4. 출력 계약

유지해야 할 output key 후보:

```text
mixed_baseline_scanner_summaries
pipeline_counts.mixed_baseline_scanner_summary_count, if currently present
policy_notes.mixed_baseline_scanner_* 또는 context-only 관련 policy, if currently present
```

출력에 포함될 수 있는 정보:

```text
- src_ip 또는 group key
- request_count
- distinct_path_count
- method_counts
- status_counts
- sample_request_ids
- sample_paths
- baseline/static/crawler/sensitive/probing 관련 관찰 요약, if currently present
- time window metadata, if currently present
- context_role, if currently present
- should_promote_to_candidate, if currently present
- interpretation_limit, if currently present
- reason_hints, if currently present
```

출력 불변조건:

```text
- output key 이름 변경 금지
- count 의미 변경 금지
- sample request/path limit 의미 변경 금지
- candidate_rows 의미 변경 금지
- supporting_events 의미 변경 금지
- mixed baseline scanner summary를 incident로 승격 금지
- scanner-like context를 attack success로 해석하는 필드/문구 추가 금지
```

## 5. Apache logs-only 해석 원칙

mixed baseline scanner summary는 여러 baseline/context 신호가 섞인 요청 패턴을 context로 보존하는 기능이다. 아래 제한을 반드시 유지한다.

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

## 6. constants 사용 방침

관련 constants 후보:

```text
MIXED_BASELINE_SCANNER_WINDOW_SEC
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT
```

1차 코드 분리 원칙:

```text
- 위 constants는 이동하지 않는다.
- 새 모듈이 필요로 하는 값은 `prepare_llm_input.py` wrapper에서 인자로 넘긴다.
- constants.py 대량 분리와 섞지 않는다.
```

보류 이유:

```text
- mixed scanner는 static/crawler/sensitive/probing/IP behavior와 경계가 겹칠 수 있다.
- constants 이동까지 함께 하면 regression 실패 시 원인 추적이 어려워진다.
- constants ownership map은 별도 문서에서 다룬다.
```

## 7. 기존 분리 모듈과의 경계

mixed scanner는 이미 분리된 여러 context summary와 겹칠 수 있다.

유지할 경계:

```text
- static_baseline_summaries는 static asset baseline/context를 다룬다.
- crawler_baseline_summaries는 crawler-like baseline/context를 다룬다.
- sensitive_path_probe_summaries는 민감 경로 probing context를 다룬다.
- probing_sequence_summaries는 시간 창 안의 여러 경로 순회 패턴을 다룬다.
- ip_behavior_aggregates는 source-IP-scoped request aggregate를 다룬다.
- mixed_baseline_scanner_summaries는 위 신호가 섞인 scanner-like context를 별도로 보존한다.
```

이번 분리에서 하지 않을 것:

```text
- static_baseline.py 수정
- crawler_baseline.py 수정
- sensitive_path_probe.py 수정
- probing_sequence.py 수정
- ip_behavior.py 수정
- 각 summary를 하나로 병합
- context-only summary를 candidate/incident로 승격
```

## 8. helper 이동 방침

이동 가능 범위:

```text
- mixed baseline scanner summary builder
- mixed baseline scanner 전용 bucket/finalize helper
- mixed baseline scanner 전용 classifier/helper
- mixed baseline scanner 전용 sample request/path formatting helper
```

이동 금지 또는 보류:

```text
- generic row normalization helper
- generic timestamp parser
- generic path normalization helper
- candidate selection/scoring helper
- supporting_events 생성/연결 helper
- static/crawler/sensitive/probing/ip behavior 전용 helper
- SQLi/XSS/file disclosure hint helper
```

공용 helper가 필요하면 새 shared module을 만들지 않고, 이번 round에서는 기존 위치에서 import하거나 wrapper 인자로 전달하는 방식을 우선한다.

## 9. 예상 구현 단계

권장 코드 작업 순서:

```text
1. grep으로 `build_mixed_baseline_scanner_summaries` 계열 함수와 호출 위치 확인
2. `src/prepare/mixed_baseline_scanner.py` 생성
3. mixed baseline scanner summary builder와 전용 helper만 이동
4. `src/prepare_llm_input.py`에 import 추가
5. 기존 공개 함수명 wrapper 유지
6. constants는 이동하지 않고 wrapper에서 전달
7. output key, pipeline_counts/counts, supporting_events 의미가 바뀌지 않았는지 확인
8. py_compile, prepare regression, stage dry-run regression 실행
```

권장 import 패턴:

```text
try:
    from src.prepare.mixed_baseline_scanner import ... as _...
except ImportError:
    from prepare.mixed_baseline_scanner import ... as _...
```

기존 round1/round2 모듈 분리와 같은 형태를 유지한다.

## 10. 금지 범위

이번 코드 분리에서 하지 않을 것:

```text
- constants 이동
- constants.py 생성 또는 대량 분리
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- mixed baseline scanner summary를 incident로 승격
- static/crawler/sensitive/probing/ip behavior summary 병합
- SQLi/XSS/file disclosure hint 이동
- scanner-like context를 성공/침해/노출 증거로 단정하는 문구 추가
- lab-* UA 또는 특정 IP를 공격 근거로 일반화
```

## 11. 검증 계획

코드 분리 전:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

코드 분리 후:

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
candidate_rows 의미 변경 없음
filtered_out 의미 변경 없음
supporting_events 의미 변경 없음
pipeline_counts/counts 의미 변경 없음
mixed_baseline_scanner_summaries output key 유지
scanner-like context를 attack success로 단정하는 문구 없음
```

## 12. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

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

## 13. 다음 작업

이 문서 작성 후 다음 작업은 실제 코드 분리다.

권장 커밋 순서:

```text
1. docs: plan mixed baseline scanner split
2. refactor: extract mixed baseline scanner summary helpers
3. docs: record mixed baseline scanner split
```

코드 분리 커밋 후보 메시지:

```text
refactor: extract mixed baseline scanner summary helpers
```

완료 후 문서 반영 대상:

```text
docs/design/99_prepare_mixed_baseline_scanner_split_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```
