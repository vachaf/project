# 99_prepare_auth_behavior_constants_move_plan

- 문서 상태: auth behavior constants mini-move 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `735d7eba0cb22835716a5098be75cded6c61b4ec`
- 목적: auth behavior 관련 constants/patterns를 `src/prepare/auth_behavior.py`로 이동한 완료 범위, 유지한 계약, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

Auth behavior constants/patterns의 module-local 이동은 완료했다.

이동한 constants/patterns:

```text
AUTH_SUCCESS_ATTACK_HINT_PATTERN
LOGIN_URI_HINTS
AUTH_ENDPOINT_FAMILY_PATTERNS
AUTH_BEHAVIOR_WINDOW_SEC = 300
AUTH_BEHAVIOR_RAPID_WINDOW_SEC = 60
AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT = 3
```

owner module:

```text
src/prepare/auth_behavior.py
```

수정 파일:

```text
src/prepare/auth_behavior.py
src/prepare_llm_input.py
```

이번 작업의 성격:

```text
- constants/patterns mini-move only
- behavior 변경 없음
- helper/function 추가 이동 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- constants.py 생성 없음
- 다른 constants group 이동 없음
```

## 2. 적용 내용

적용한 변경:

```text
- `src/prepare/auth_behavior.py`에 auth behavior constants/patterns 7개 추가
- `src/prepare_llm_input.py`의 동일 constants/patterns 정의 7개 제거
- `src/prepare_llm_input.py`의 `auth_behavior` try/except import 블록 양쪽에 constants/patterns 7개 import 추가
- 내부 참조 이름 `AUTH_*`, `LOGIN_URI_HINTS`는 그대로 유지
- `src/prepare/auth_behavior.py` 내부 기본값 리터럴은 동일 값의 constants 참조로만 정리
```

유지한 값:

```text
auth_behavior_window_sec = 300
auth_behavior_rapid_window_sec = 60
auth_behavior_sample_request_limit = 10
auth_behavior_representative_candidate_limit = 3
```

주의:

```text
`AUTH_SUCCESS_ATTACK_HINT_PATTERN`이라는 이름은 success를 포함하지만, 이 패턴은 login success 또는 bypass success를 단정하는 근거가 아니다.
공격성 단어가 auth 문맥에 섞였는지 보는 보조 신호로만 유지한다.
```

## 3. 이동하지 않은 것

이번 커밋에서 아래 항목은 이동하거나 수정하지 않았다.

```text
build_auth_behavior_summaries
build_auth_behavior_summary_contexts
finalize_auth_behavior_bucket
auth endpoint classification helper
login endpoint detection helper
auth attack-word hint helper
representative candidate reduction 로직
candidate/scoring/filtering 로직
supporting_events 생성/연결 로직
Stage2 reporter
expected/test fixture
policy wording
output key
다른 constants group
```

## 4. Apache logs-only 해석 원칙

이번 constants/patterns 이동 이후에도 아래 해석 제한은 유지한다.

```text
- 로그인 성공을 단정하지 않는다.
- 계정 탈취를 단정하지 않는다.
- credential stuffing 성공을 단정하지 않는다.
- lockout 발동을 단정하지 않는다.
- auth bypass 성공을 단정하지 않는다.
- 200/302/401/403만으로 계정 상태를 단정하지 않는다.
- auth behavior summary는 context이지 success proof가 아니다.
```

특히 `AUTH_SUCCESS_ATTACK_HINT_PATTERN`에 포함된 단어는 아래처럼 해석한다.

```text
- bypass/exploit/attack/abuse/intrud/tamper/payload/fuzz/poc/scanner/sqlmap/nikto/nmap 같은 단어는 공격성 문맥 보조 신호다.
- 이 단어만으로 login success, bypass success, account takeover success를 단정하지 않는다.
```

금지 표현:

```text
- login succeeded
- account takeover confirmed
- credential stuffing succeeded
- lockout triggered
- authentication bypass succeeded
- attacker gained access
```

## 5. 검증 결과

기준 커밋 `735d7eba0cb22835716a5098be75cded6c61b4ec`에서 아래 검증을 통과했다.

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

## 6. 롤백 기준

향후 관련 추가 이동에서 아래 중 하나라도 발생하면 해당 커밋을 수정하거나 롤백한다.

```text
- import cycle 발생
- py_compile fail
- prepare regression fail
- stage dry-run regression fail
- auth_behavior_* policy_notes 값 변화
- auth behavior summary count 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- output key 이름 변경
- representative candidate reduction 의미 변경
- auth endpoint family 이름 변화
- login success / account takeover / credential stuffing success / lockout / bypass success 단정 문구 발생
```

## 7. 다음 작업

Auth behavior constants/patterns 이동은 완료했다.

다음 mini-move 후보는 crawler baseline constants다. 다만 crawler 쪽은 실제 crawler identity, robots/sitemap 내용, site structure, product/category page existence 단정 금지와 연결되므로, 먼저 grep 확인과 move plan 작성 여부를 판단한다.

권장 확인 명령:

```bash
grep -n "CRAWLER_BASELINE_\|BROWSER_UA_HINTS\|CRAWLER_BROWSE_PRODUCT_SEGMENTS\|CRAWLER_BROWSE_CATEGORY_SEGMENTS\|CRAWLER_BROWSE_GENERIC_SEGMENTS" src/prepare_llm_input.py src/prepare/*.py
```

다음 후보 문서:

```text
docs/design/99_prepare_crawler_baseline_constants_move_plan.md
```

문서 전용 커밋 후보:

```text
docs: record auth behavior constants move
```
