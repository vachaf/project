# 99_prepare_auth_behavior_constants_move_plan

- 문서 상태: auth behavior constants mini-move plan
- 기준 시점: 2026-05-04
- 목적: `AUTH_*`, `LOGIN_URI_HINTS`, `AUTH_ENDPOINT_FAMILY_PATTERNS` grep 결과를 바탕으로, auth behavior 관련 constants/patterns의 module-local 이동 가능 범위와 금지사항, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_constants_mini_move_candidate_review.md](./99_prepare_constants_mini_move_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_auth_behavior_split_plan.md](./99_prepare_auth_behavior_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

Auth behavior constants/patterns는 소규모 이동 후보로 검토 가능하다.

이동 후보:

```text
AUTH_SUCCESS_ATTACK_HINT_PATTERN
LOGIN_URI_HINTS
AUTH_ENDPOINT_FAMILY_PATTERNS
AUTH_BEHAVIOR_WINDOW_SEC
AUTH_BEHAVIOR_RAPID_WINDOW_SEC
AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT
AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT
```

권장 owner module:

```text
src/prepare/auth_behavior.py
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
```

주의:

```text
`AUTH_SUCCESS_ATTACK_HINT_PATTERN`이라는 이름은 success를 포함하지만, 이 패턴은 login success 또는 bypass success를 단정하는 근거가 아니다.
공격성 단어가 auth 문맥에 섞였는지 보는 보조 신호로만 유지한다.
```

## 2. grep 확인 결과

확인 명령:

```bash
grep -n "AUTH_SUCCESS_ATTACK_HINT_PATTERN\|LOGIN_URI_HINTS\|AUTH_ENDPOINT_FAMILY_PATTERNS\|AUTH_BEHAVIOR_" src/prepare_llm_input.py src/prepare/*.py
```

확인 결과:

```text
src/prepare_llm_input.py:297:AUTH_SUCCESS_ATTACK_HINT_PATTERN = re.compile(
src/prepare_llm_input.py:303:LOGIN_URI_HINTS = (
src/prepare_llm_input.py:313:AUTH_ENDPOINT_FAMILY_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
src/prepare_llm_input.py:458:AUTH_BEHAVIOR_WINDOW_SEC = 300
src/prepare_llm_input.py:459:AUTH_BEHAVIOR_RAPID_WINDOW_SEC = 60
src/prepare_llm_input.py:460:AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT = 10
src/prepare_llm_input.py:461:AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT = 3
src/prepare_llm_input.py:1507:        sample_request_limit=AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:1513:    window_sec: int = AUTH_BEHAVIOR_WINDOW_SEC,
src/prepare_llm_input.py:1514:    rapid_window_sec: int = AUTH_BEHAVIOR_RAPID_WINDOW_SEC,
src/prepare_llm_input.py:1520:        sample_request_limit=AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
src/prepare_llm_input.py:1521:        auth_endpoint_family_patterns=AUTH_ENDPOINT_FAMILY_PATTERNS,
src/prepare_llm_input.py:1871:    representative_limit: int = AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT,
src/prepare_llm_input.py:2119:    return any(hint in uri_lower for hint in LOGIN_URI_HINTS)
src/prepare_llm_input.py:2130:    for family, pattern in AUTH_ENDPOINT_FAMILY_PATTERNS:
src/prepare_llm_input.py:2152:    return bool(combined and AUTH_SUCCESS_ATTACK_HINT_PATTERN.search(combined))
src/prepare_llm_input.py:4047:                "auth_behavior_window_sec": AUTH_BEHAVIOR_WINDOW_SEC,
src/prepare_llm_input.py:4048:                "auth_behavior_rapid_window_sec": AUTH_BEHAVIOR_RAPID_WINDOW_SEC,
```

해석:

```text
- Auth behavior constants/patterns는 현재 `src/prepare_llm_input.py`에 남아 있다.
- `src/prepare/auth_behavior.py` 또는 다른 `src/prepare/*.py`에서 직접 참조하는 결과는 보이지 않는다.
- owner module은 `src/prepare/auth_behavior.py`로 비교적 명확하다.
- 다만 auth success / bypass wording과 연결될 수 있으므로 값과 의미를 바꾸지 않는 조건에서만 이동한다.
```

## 3. 현재 구조 추정

현재 `src/prepare_llm_input.py`에는 auth behavior wrapper 계열과 auth endpoint classification helper가 남아 있고, 실제 auth behavior summary builder는 이미 `src/prepare/auth_behavior.py`로 분리되어 있다.

사용 지점 유형:

```text
- auth behavior summary builder 호출 인자
- auth behavior summary builder 기본 window / rapid window
- auth endpoint family classifier
- login endpoint check
- auth attack-word hint check
- representative candidate limit
- policy_notes 메타 값
```

이동 후에도 아래 값 의미는 유지해야 한다.

```text
auth_behavior_window_sec = 300
auth_behavior_rapid_window_sec = 60
auth_behavior_sample_request_limit = 10
auth_behavior_representative_candidate_limit = 3
```

## 4. 이동 방식

권장 방식:

```text
1. `src/prepare/auth_behavior.py`에 이동 후보 constants/patterns를 정의한다.
2. `src/prepare_llm_input.py`의 동일 constants/patterns 정의를 제거한다.
3. `src/prepare_llm_input.py` import 블록에서 이동한 constants/patterns를 함께 import한다.
4. 기존 wrapper 기본값과 policy_notes 참조는 동일한 constant 이름을 사용하게 한다.
5. 함수 호출 인자, output key, policy_notes key는 변경하지 않는다.
```

권장 import 예시:

```python
try:
    from src.prepare.auth_behavior import (
        AUTH_BEHAVIOR_RAPID_WINDOW_SEC,
        AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT,
        AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        AUTH_BEHAVIOR_WINDOW_SEC,
        AUTH_ENDPOINT_FAMILY_PATTERNS,
        AUTH_SUCCESS_ATTACK_HINT_PATTERN,
        LOGIN_URI_HINTS,
        build_auth_behavior_summaries as _build_auth_behavior_summaries,
        build_auth_behavior_summary_contexts as _build_auth_behavior_summary_contexts,
        finalize_auth_behavior_bucket as _finalize_auth_behavior_bucket,
    )
except ImportError:
    from prepare.auth_behavior import (
        AUTH_BEHAVIOR_RAPID_WINDOW_SEC,
        AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT,
        AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT,
        AUTH_BEHAVIOR_WINDOW_SEC,
        AUTH_ENDPOINT_FAMILY_PATTERNS,
        AUTH_SUCCESS_ATTACK_HINT_PATTERN,
        LOGIN_URI_HINTS,
        build_auth_behavior_summaries as _build_auth_behavior_summaries,
        build_auth_behavior_summary_contexts as _build_auth_behavior_summary_contexts,
        finalize_auth_behavior_bucket as _finalize_auth_behavior_bucket,
    )
```

주의:

```text
- import alias를 새로 만들 필요는 없다.
- 기존 코드에서 `AUTH_*`와 `LOGIN_URI_HINTS` 이름을 그대로 참조할 수 있게 import한다.
- auth behavior helper/function을 추가 이동하지 않는다.
```

## 5. 허용 범위

허용되는 변경:

```text
- `src/prepare/auth_behavior.py`에 auth behavior constants/patterns 추가
- `src/prepare_llm_input.py`에서 동일 constants/patterns 정의 제거
- `src/prepare_llm_input.py` import 블록에 constants/patterns import 추가
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- auth behavior helper/function 추가 이동
- auth endpoint classification 로직 변경
- login endpoint detection 로직 변경
- auth attack-word hint 로직 변경
- representative candidate reduction 의미 변경
- auth behavior summary output key 변경
- policy_notes key 또는 wording 변경
- expected/test fixture 수정
- Stage2 reporter 수정
- candidate/scoring/filtering 변경
- supporting_events 생성/연결 로직 변경
- constants.py 생성
- 다른 constants group 이동
```

## 6. Apache logs-only 해석 원칙

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

## 7. 검증 계획

이동 전:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

이동 후:

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
policy_notes 의미 변경 없음
expected/test fixture 수정 없음
Stage2 reporter 수정 없음
candidate/scoring/filtering 변경 없음
auth behavior summary count 변화 없음
representative candidate reduction 의미 변경 없음
login/account takeover/lockout/bypass success 단정 문구 없음
```

## 8. 실패 시 롤백 기준

아래 중 하나라도 발생하면 constants/patterns 이동 커밋을 수정하거나 롤백한다.

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

## 9. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_auth_behavior_constants_move_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 이동한 constants/patterns 목록
- 기준 커밋
- `src/prepare/auth_behavior.py`에 constants/patterns 정의 추가
- `src/prepare_llm_input.py`에서 constants/patterns import 사용
- helper/function 추가 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 10. 다음 작업

문서 작성 후 다음 작업은 Codex에 auth behavior constants/patterns 이동을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan auth behavior constants move
2. refactor: move auth behavior constants
3. docs: record auth behavior constants move
```

코드 이동 커밋 후보 메시지:

```text
refactor: move auth behavior constants
```
