# 99_prepare_sqli_hints_split_plan

- 문서 상태: SQLi hints split plan
- 기준 시점: 2026-05-04
- 목적: `99_prepare_hints_split_candidate_review.md` 이후 SQLi hint 계열을 실제 코드 분리 대상으로 볼 수 있는지, 이동 가능 범위와 보류 범위, evidence boundary, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

SQLi hint 계열은 분리 후보로 볼 수 있다. 다만 candidate scoring, false positive suppression, decoded attack hints, supporting context와 연결되어 있으므로 바로 넓게 이동하지 않는다.

권장 신규 모듈 후보:

```text
src/prepare/sqli_hints.py
```

1차 이동 후보:

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
detect_educational_sql_search_context
```

1차에서 이동하지 않을 것:

```text
detect_decoded_attack_hints
candidate scoring 로직
possible_false_positive_sql_keyword_search verdict 결정 로직
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
```

이번 split plan의 기본 방향:

```text
- mechanical refactor only
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

## 2. grep 확인 결과

확인 명령:

```bash
grep -n "SQLI_\|EDUCATIONAL_SQL_SEARCH_TERMS\|SUPPORTING_SQL_KEYWORDS\|REPEATED_QUOTE_PATTERN" src/prepare_llm_input.py src/prepare/*.py

grep -n "detect_decoded_attack_hints\|educational.*sql\|sqli:\|possible_false_positive_sql_keyword_search" src/prepare_llm_input.py src/prepare/*.py
```

요약 결과:

```text
SQLI_PATTERNS: src/prepare_llm_input.py:210
EDUCATIONAL_SQL_SEARCH_TERMS: src/prepare_llm_input.py:452
SUPPORTING_SQL_KEYWORDS: src/prepare_llm_input.py:472
SQLI_BOOLEAN_CONDITION_PATTERN: src/prepare_llm_input.py:505
SQLI_BOOLEAN_TRUE_CONDITION_PATTERN: src/prepare_llm_input.py:506
SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN: src/prepare_llm_input.py:518
SQLI_PAREN_TERMINATION_PATTERN: src/prepare_llm_input.py:522
SQLI_XCLOSE_PATTERN: src/prepare_llm_input.py:526
SQLI_UNION_COLUMN_ENUM_PATTERN: src/prepare_llm_input.py:527
SQLI_SCHEMA_ACCESS_PATTERN: src/prepare_llm_input.py:528
SQLI_FROM_USERS_PATTERN: src/prepare_llm_input.py:529
SQLI_COMMENT_PATTERN: src/prepare_llm_input.py:530
REPEATED_QUOTE_PATTERN: src/prepare_llm_input.py:531
```

주요 사용 위치:

```text
771 / 807 / 814~826: decoded attack hints와 SQLi pattern 결합
908 / 912: educational SQL search context
941~958: 강한 SQLi 구조 판단
1156 / 1161: supporting SQL keyword / repeated quote 판단
1429~1442 / 1508: supporting/reason_hints 계열과 연결
3563~3593: candidate scoring 계열과 연결
3741~3899: educational SQL false-positive verdict 판단
3980: SQLi/XSS/traversal/CMDI 통합 pattern check와 연결
```

해석:

```text
- SQLi pattern/constants는 아직 `src/prepare_llm_input.py`에 집중되어 있다.
- 단순 pattern 정의뿐 아니라 decoded hints, strong structure 판단, supporting keyword 판단, candidate scoring, educational SQL false-positive verdict와 연결된다.
- 따라서 1차 분리는 constants/patterns와 매우 좁은 helper로 제한해야 한다.
```

## 3. SQLi evidence boundary

SQLi hints는 Apache log surface에서 관찰 가능한 구조를 다룬다. 아래 한계를 반드시 유지한다.

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

## 4. 이동 가능 범위

### 4.1 pattern/constants

1차 이동 가능:

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

이동 방식:

```text
- `src/prepare/sqli_hints.py`에 constants/patterns를 정의한다.
- `src/prepare_llm_input.py`의 동일 정의를 제거한다.
- `src/prepare_llm_input.py` import 블록에 동일 이름으로 import한다.
- 기존 내부 참조 이름은 그대로 둔다.
```

### 4.2 narrow helper

1차 이동 가능 후보:

```text
detect_educational_sql_search_context
```

이유:

```text
- `EDUCATIONAL_SQL_SEARCH_TERMS`만 직접 소비하는 좁은 helper일 가능성이 높다.
- false positive verdict 결정 로직 자체는 이동하지 않고 helper만 이동하면 경계가 좁다.
```

단, 실제 코드 이동 전에는 함수 body를 확인해야 한다. 다른 shared helper에 강하게 의존하면 wrapper 인자 전달 또는 보류를 우선한다.

## 5. 1차에서 이동하지 않을 것

### 5.1 decoded attack hints

보류:

```text
detect_decoded_attack_hints
```

보류 이유:

```text
- SQLi뿐 아니라 XSS, traversal, file disclosure, CMDI와 연결될 가능성이 높다.
- decoded variants와 encoding descriptors는 shared evidence reconstruction 성격이다.
- SQLi 전용 모듈로 이동하면 XSS/file disclosure와의 경계가 흐려질 수 있다.
```

### 5.2 strong structure / scoring / verdict logic

보류:

```text
strong_sqli_structure 판단 로직
candidate scoring 로직
possible_false_positive_sql_keyword_search verdict 결정 로직
```

보류 이유:

```text
- candidate selection과 false positive suppression 의미를 바꿀 위험이 크다.
- SQLi evidence boundary와 직접 연결된다.
- mechanical refactor 실패 시 regression 차이 원인 추적이 어렵다.
```

### 5.3 supporting context

보류:

```text
supporting_events 생성/연결 로직
supporting SQL keyword를 실제 supporting event로 연결하는 로직
```

보류 이유:

```text
- supporting_events 보존/연결 기준은 여러 공격군과 공유될 수 있다.
- SQLi hint 이동과 supporting event 의미 변경을 같은 커밋에 섞으면 안 된다.
```

### 5.4 shared attack/search policy constants

보류:

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
- SQLi/XSS/file disclosure/traversal/CMDI 등 여러 hint 계열이 공유할 수 있다.
- false positive suppression과 candidate preservation의 경계에 있다.
- shared policy module을 별도로 검토하기 전에는 이동하지 않는다.
```

## 6. 예상 구현 방식

권장 import 패턴:

```python
try:
    from src.prepare.sqli_hints import (
        EDUCATIONAL_SQL_SEARCH_TERMS,
        REPEATED_QUOTE_PATTERN,
        SQLI_BOOLEAN_CONDITION_PATTERN,
        SQLI_BOOLEAN_TRUE_CONDITION_PATTERN,
        SQLI_COMMENT_PATTERN,
        SQLI_FROM_USERS_PATTERN,
        SQLI_PAREN_TERMINATION_PATTERN,
        SQLI_PATTERNS,
        SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN,
        SQLI_SCHEMA_ACCESS_PATTERN,
        SQLI_UNION_COLUMN_ENUM_PATTERN,
        SQLI_XCLOSE_PATTERN,
        SUPPORTING_SQL_KEYWORDS,
        detect_educational_sql_search_context as _detect_educational_sql_search_context,
    )
except ImportError:
    from prepare.sqli_hints import (
        EDUCATIONAL_SQL_SEARCH_TERMS,
        REPEATED_QUOTE_PATTERN,
        SQLI_BOOLEAN_CONDITION_PATTERN,
        SQLI_BOOLEAN_TRUE_CONDITION_PATTERN,
        SQLI_COMMENT_PATTERN,
        SQLI_FROM_USERS_PATTERN,
        SQLI_PAREN_TERMINATION_PATTERN,
        SQLI_PATTERNS,
        SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN,
        SQLI_SCHEMA_ACCESS_PATTERN,
        SQLI_UNION_COLUMN_ENUM_PATTERN,
        SQLI_XCLOSE_PATTERN,
        SUPPORTING_SQL_KEYWORDS,
        detect_educational_sql_search_context as _detect_educational_sql_search_context,
    )
```

`src/prepare_llm_input.py` wrapper 예시:

```python
def detect_educational_sql_search_context(text: str) -> bool:
    return _detect_educational_sql_search_context(text)
```

주의:

```text
- existing names는 그대로 유지한다.
- `detect_decoded_attack_hints`는 이동하지 않는다.
- candidate scoring / verdict 로직은 이동하지 않는다.
- `possible_false_positive_sql_keyword_search`를 생성하는 판단 로직은 그대로 둔다.
```

## 7. 허용 범위

허용되는 변경:

```text
- `src/prepare/sqli_hints.py` 생성
- SQLi pattern/constants 이동
- `detect_educational_sql_search_context` 이동 또는 wrapper 유지
- `src/prepare_llm_input.py`에 import 추가
- 기존 공개 함수명 wrapper 유지
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- detect_decoded_attack_hints 이동
- decoded variants helper 이동
- candidate scoring 변경
- false positive suppression 의미 변경
- possible_false_positive_sql_keyword_search verdict 결정 로직 이동 또는 변경
- supporting_events 생성/연결 로직 변경
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- SQLi pattern 값 변경
- SQLi score 값 변경
- SQLi reason_hints 이름 변경
- XSS/file disclosure/traversal/CMDI patterns 이동
- shared attack/search policy constants 이동
```

## 8. 검증 계획

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
reason_hints 이름/의미 변경 없음
possible_false_positive_sql_keyword_search 처리 의미 변경 없음
output key 의미 변경 없음
policy_notes 의미 변경 없음
expected/test fixture 수정 없음
Stage2 reporter 수정 없음
```

## 9. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

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

## 10. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_sqli_hints_split_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 생성 파일: src/prepare/sqli_hints.py
- 이동한 pattern/constants 목록
- 이동한 helper 여부
- 보류한 함수/로직 목록
- candidate/scoring/filtering 변경 없음
- supporting_events 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 11. 다음 작업

문서 작성 후 다음 작업은 Codex에 1차 SQLi hint split을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan SQLi hint split
2. refactor: extract SQLi hint patterns
3. docs: record SQLi hint split
```

코드 이동 커밋 후보 메시지:

```text
refactor: extract SQLi hint patterns
```
