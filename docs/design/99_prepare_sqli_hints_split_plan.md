# 99_prepare_sqli_hints_split_plan

- 문서 상태: SQLi hints split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `4bf7ee08f9bc47aac4dfe905609f4b251ca6e9bd`
- 목적: SQLi hint pattern/constants와 좁은 helper를 `src/prepare/sqli_hints.py`로 분리한 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

SQLi hint pattern/constants 1차 분리는 완료했다.

생성 파일:

```text
src/prepare/sqli_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이번 작업은 mechanical refactor로 제한했다.

```text
- behavior 변경 없음
- SQLi evidence boundary 변경 없음
- false positive suppression 의미 변경 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
```

## 2. 이동 완료 pattern/constants

아래 pattern/constants를 `src/prepare/sqli_hints.py`로 이동했다.

```text
SQLI_PATTERNS
SQLI_BOOLEAN_CONDITION_PATTERN
SQLI_BOOLEAN_TRUE_CONDITION_PATTERN
SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN
SQLI_PAREN_TERMINATION_PATTERN
SQLI_XCLOSE_PATTERN
SQLI_UNION_COLUMN_ENUM_PATTERN
SQLI_SCHEMA_ACCESS_PATTERN
SQLI_FROM_USERS_PATTERN
SQLI_COMMENT_PATTERN
REPEATED_QUOTE_PATTERN
EDUCATIONAL_SQL_SEARCH_TERMS
SUPPORTING_SQL_KEYWORDS
```

`src/prepare_llm_input.py`에는 기존 내부 참조 이름을 그대로 유지하도록 import를 추가했다.

## 3. 이동 완료 helper

아래 helper를 `src/prepare/sqli_hints.py`로 이동했다.

```text
detect_educational_sql_search_context
```

`src/prepare_llm_input.py`에는 기존 공개 함수명을 유지하는 wrapper를 남겼다.

```python
def detect_educational_sql_search_context(text: str) -> bool:
    return _detect_educational_sql_search_context(text)
```

## 4. 이동하지 않은 함수/로직

아래 항목은 이동하거나 수정하지 않았다.

```text
detect_decoded_attack_hints
decoded variants helper/decoder 계열
candidate scoring/filtering 전반
possible_false_positive_sql_keyword_search verdict 결정 로직
strong_sqli_structure 판단 로직
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
XSS/file disclosure/traversal/CMDI patterns
```

보류한 shared attack/search policy constants:

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

보류 이유:

```text
- 여러 hint 계열이 공유할 수 있다.
- false positive suppression과 candidate preservation의 경계에 있다.
- shared policy module을 별도로 검토하기 전에는 이동하지 않는다.
```

## 5. 유지한 SQLi evidence boundary

이번 분리 이후에도 아래 한계를 유지한다.

```text
- DB query 결과를 단정하지 않는다.
- SQL injection 성공을 단정하지 않는다.
- Boolean blind true/false가 실제 DB 조건 결과라고 단정하지 않는다.
- Time-based delay가 DB sleep 성공이라고 단정하지 않는다.
- DB schema 노출, row 반환, 인증 우회 성공, 데이터 탈취를 단정하지 않는다.
- status_code, response_body_bytes, duration_us, ttfb_us는 관찰 신호이지 DB 결과가 아니다.
- educational SQL search는 구조적 공격 신호가 약하면 false positive로 보수 처리한다.
```

허용되는 표현:

```text
- SQLi-like structure observed
- quote termination / boolean condition / SQL comment marker observed
- possible SQLi candidate based on Apache log surface
- timing/byte delta observed, not DB result
- educational SQL search likely false positive, if applicable
```

금지 표현:

```text
- SQL injection succeeded
- DB returned rows
- authentication bypass succeeded
- data exfiltration confirmed
- database schema was exposed
- sleep() executed in database
- Boolean condition evaluated true in DB
```

## 6. 검증 결과

기준 커밋 `4bf7ee08f9bc47aac4dfe905609f4b251ca6e9bd`에서 아래 검증을 통과했다.

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

## 7. 롤백 기준

향후 관련 추가 분리에서 아래 중 하나라도 발생하면 해당 커밋을 수정하거나 롤백한다.

```text
- import cycle 발생
- py_compile fail
- prepare regression fail
- stage dry-run regression fail
- SQLi pattern 값/score 변화
- reason_hints 이름 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- possible_false_positive_sql_keyword_search 변화
- decoded hints 변화
- output key 이름 변경
- SQL injection 성공 / DB 결과 / 인증 우회 / 데이터 탈취 단정 문구 발생
```

## 8. 다음 작업

SQLi hints 1차 분리는 완료했다.

`99_prepare_hints_split_candidate_review.md` 기준 다음 후보는 XSS hints다. 다만 XSS는 decoded reconstruction과 browser execution boundary가 민감하므로, 먼저 grep 확인과 split plan 작성 여부를 판단한다.

권장 확인 명령:

```bash
grep -n "XSS_\|SCRIPT_TAG\|EVENT_HANDLER\|JAVASCRIPT_PROTOCOL\|BROWSER_DATA_ACCESS\|EXTERNAL_NAVIGATION\|EXTERNAL_URL\|EDUCATIONAL_XSS\|HTML_ENTITY_RE" src/prepare_llm_input.py src/prepare/*.py
```

다음 후보 문서:

```text
docs/design/99_prepare_xss_hints_split_plan.md
```

문서 전용 커밋 후보:

```text
docs: record SQLi hint split
```
