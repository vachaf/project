# 99_prepare_xss_hints_split_plan

- 문서 상태: XSS hints split plan
- 기준 시점: 2026-05-04
- 목적: `99_prepare_hints_split_candidate_review.md` 이후 XSS hint 계열을 실제 코드 분리 대상으로 볼 수 있는지, 이동 가능 범위와 보류 범위, browser execution evidence boundary, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

XSS hint 계열은 분리 후보로 볼 수 있다. 다만 SQLi보다 더 조심해야 한다.

이유:

```text
- XSS는 decoded reconstruction, HTML entity handling, browser execution boundary와 직접 연결된다.
- Apache logs-only 기준에서는 브라우저가 실제로 payload를 실행했는지 알 수 없다.
- cookie/session 탈취, external navigation, exfiltration 성공도 Apache 로그만으로 단정할 수 없다.
- HTML entity handling은 이미 `src/prepare/decoders.py`에도 별도 정의가 있으므로 이번 XSS split에서 통합하거나 이동하지 않는다.
```

권장 신규 모듈 후보:

```text
src/prepare/xss_hints.py
```

1차 이동 후보:

```text
XSS_PATTERNS
SCRIPT_TAG_PATTERN
SCRIPT_TAG_CAPTURE_RE
EVENT_HANDLER_ASSIGNMENT_RE
JAVASCRIPT_PROTOCOL_RE
BROWSER_DATA_ACCESS_RE
EXTERNAL_NAVIGATION_RE
EXTERNAL_URL_RE
XSS_QUOTE_BREAKOUT_PATTERN
XSS_TAG_INJECTION_PATTERN
EDUCATIONAL_XSS_SEARCH_TERMS
EDUCATIONAL_XSS_KEYWORDS
```

1차에서 이동하지 않을 것:

```text
HTML_ENTITY_RE
detect_decoded_attack_hints
decoded variants helper/decoder 계열
candidate scoring 로직
browser execution / impact verdict logic
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
SQLi/file disclosure/traversal/CMDI patterns
```

이번 split plan의 기본 방향:

```text
- mechanical refactor only
- behavior 변경 없음
- XSS evidence boundary 변경 없음
- browser execution/impact 의미 변경 없음
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
grep -n "XSS_\|SCRIPT_TAG\|EVENT_HANDLER\|JAVASCRIPT_PROTOCOL\|BROWSER_DATA_ACCESS\|EXTERNAL_NAVIGATION\|EXTERNAL_URL\|EDUCATIONAL_XSS\|HTML_ENTITY_RE" src/prepare_llm_input.py src/prepare/*.py
```

요약 결과:

```text
XSS_PATTERNS: src/prepare_llm_input.py:242
HTML_ENTITY_RE: src/prepare_llm_input.py:489
SCRIPT_TAG_PATTERN: src/prepare_llm_input.py:493
SCRIPT_TAG_CAPTURE_RE: src/prepare_llm_input.py:494
EVENT_HANDLER_ASSIGNMENT_RE: src/prepare_llm_input.py:495
JAVASCRIPT_PROTOCOL_RE: src/prepare_llm_input.py:496
BROWSER_DATA_ACCESS_RE: src/prepare_llm_input.py:497
EXTERNAL_NAVIGATION_RE: src/prepare_llm_input.py:498
EXTERNAL_URL_RE: src/prepare_llm_input.py:501
XSS_QUOTE_BREAKOUT_PATTERN: src/prepare_llm_input.py:502
XSS_TAG_INJECTION_PATTERN: src/prepare_llm_input.py:503
EDUCATIONAL_XSS_SEARCH_TERMS: src/prepare_llm_input.py:505
EDUCATIONAL_XSS_KEYWORDS: src/prepare_llm_input.py:519
HTML_ENTITY_RE: src/prepare/decoders.py:9
```

주요 사용 위치:

```text
703: HTML entity stripping helper
730 / 760: decoded attack hints와 XSS_PATTERNS 연결
877 / 879: educational XSS search context
921~1039: script tag, event handler, javascript protocol, browser data access, external navigation, HTML entity decoded script 판단
1386: reason_hints 계열과 연결
3523: candidate scoring 계열과 연결
3934: SQLi/XSS/traversal/CMDI 통합 pattern check와 연결
```

해석:

```text
- XSS pattern/constants는 `src/prepare_llm_input.py`에 집중되어 있다.
- `HTML_ENTITY_RE`는 `src/prepare_llm_input.py`와 `src/prepare/decoders.py` 양쪽에 정의되어 있어 이번 XSS split에서 이동하거나 통합하지 않는다.
- XSS pattern은 decoded hints, educational XSS context, strong structure 판단, candidate scoring, 통합 pattern check와 연결된다.
- 따라서 1차 분리는 XSS 전용 pattern/constants로 제한해야 한다.
```

## 3. XSS evidence boundary

XSS hints는 Apache log surface에서 관찰 가능한 payload 구조를 다룬다. 아래 한계를 반드시 유지한다.

```text
- 브라우저 실행 여부를 단정하지 않는다.
- alert/document.cookie/localStorage/sessionStorage 접근 코드가 실제 실행되었다고 단정하지 않는다.
- 쿠키 탈취, 세션 탈취, 외부 전송, exfiltration 성공을 단정하지 않는다.
- URL decoding이나 HTML entity decoding은 payload reconstruction이지 execution proof가 아니다.
- script tag, event handler, javascript: protocol, external URL은 payload structure 신호이지 impact confirmation이 아니다.
- educational XSS search는 구조적 공격 신호가 약하면 false positive로 보수 처리한다.
```

허용되는 표현:

```text
- XSS-like payload structure observed
- script-like or event-handler-like payload observed
- decoded script-like payload candidate
- browser-executable pattern, not browser execution evidence
- possible exfil intent in payload text, not exfil success
- educational XSS search likely false positive, if applicable
```

금지 표현:

```text
- XSS executed
- browser ran the script
- cookie was stolen
- session was hijacked
- exfiltration succeeded
- victim clicked or executed payload
- JavaScript execution confirmed
```

## 4. 이동 가능 범위

### 4.1 pattern/constants

1차 이동 가능:

```text
XSS_PATTERNS
SCRIPT_TAG_PATTERN
SCRIPT_TAG_CAPTURE_RE
EVENT_HANDLER_ASSIGNMENT_RE
JAVASCRIPT_PROTOCOL_RE
BROWSER_DATA_ACCESS_RE
EXTERNAL_NAVIGATION_RE
EXTERNAL_URL_RE
XSS_QUOTE_BREAKOUT_PATTERN
XSS_TAG_INJECTION_PATTERN
EDUCATIONAL_XSS_SEARCH_TERMS
EDUCATIONAL_XSS_KEYWORDS
```

이동 방식:

```text
- `src/prepare/xss_hints.py`에 constants/patterns를 정의한다.
- `src/prepare_llm_input.py`의 동일 정의를 제거한다.
- `src/prepare_llm_input.py` import 블록에 동일 이름으로 import한다.
- 기존 내부 참조 이름은 그대로 둔다.
```

### 4.2 narrow helper

1차 이동 가능 후보는 이번 문서에서는 확정하지 않는다.

이유:

```text
- educational XSS context helper는 `EDUCATIONAL_XSS_SEARCH_TERMS`와 `EDUCATIONAL_XSS_KEYWORDS`를 소비하지만, 실제 false positive 처리와 결합되어 있을 수 있다.
- script tag extraction, payload structure 판단 helper는 browser execution/impact wording과 가까울 수 있다.
- 따라서 1차는 pattern/constants 이동만 권장한다.
```

## 5. 1차에서 이동하지 않을 것

### 5.1 HTML entity handling

보류:

```text
HTML_ENTITY_RE
```

보류 이유:

```text
- `src/prepare_llm_input.py`와 `src/prepare/decoders.py`에 각각 정의가 있다.
- decoders.py의 HTML entity handling과 XSS hint 판단을 한 커밋에서 통합하면 import/ownership 경계가 복잡해진다.
- HTML entity decoding은 XSS뿐 아니라 decoded variants evidence reconstruction과 연결된다.
```

### 5.2 decoded attack hints

보류:

```text
detect_decoded_attack_hints
```

보류 이유:

```text
- SQLi, XSS, traversal, file disclosure, CMDI와 연결될 가능성이 높다.
- decoded variants와 encoding descriptors는 shared evidence reconstruction 성격이다.
- XSS 전용 모듈로 이동하면 SQLi/file disclosure와의 경계가 흐려질 수 있다.
```

### 5.3 scoring / impact / verdict logic

보류:

```text
candidate scoring 로직
browser execution / impact verdict logic
educational XSS false positive 판단 로직
```

보류 이유:

```text
- candidate selection과 false positive suppression 의미를 바꿀 위험이 크다.
- browser execution boundary와 직접 연결된다.
- mechanical refactor 실패 시 regression 차이 원인 추적이 어렵다.
```

### 5.4 supporting context

보류:

```text
supporting_events 생성/연결 로직
XSS hint를 실제 supporting event로 연결하는 로직
```

보류 이유:

```text
- supporting_events 보존/연결 기준은 여러 공격군과 공유될 수 있다.
- XSS hint 이동과 supporting event 의미 변경을 같은 커밋에 섞으면 안 된다.
```

### 5.5 shared attack/search policy constants

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
    from src.prepare.xss_hints import (
        BROWSER_DATA_ACCESS_RE,
        EDUCATIONAL_XSS_KEYWORDS,
        EDUCATIONAL_XSS_SEARCH_TERMS,
        EVENT_HANDLER_ASSIGNMENT_RE,
        EXTERNAL_NAVIGATION_RE,
        EXTERNAL_URL_RE,
        JAVASCRIPT_PROTOCOL_RE,
        SCRIPT_TAG_CAPTURE_RE,
        SCRIPT_TAG_PATTERN,
        XSS_PATTERNS,
        XSS_QUOTE_BREAKOUT_PATTERN,
        XSS_TAG_INJECTION_PATTERN,
    )
except ImportError:
    from prepare.xss_hints import (
        BROWSER_DATA_ACCESS_RE,
        EDUCATIONAL_XSS_KEYWORDS,
        EDUCATIONAL_XSS_SEARCH_TERMS,
        EVENT_HANDLER_ASSIGNMENT_RE,
        EXTERNAL_NAVIGATION_RE,
        EXTERNAL_URL_RE,
        JAVASCRIPT_PROTOCOL_RE,
        SCRIPT_TAG_CAPTURE_RE,
        SCRIPT_TAG_PATTERN,
        XSS_PATTERNS,
        XSS_QUOTE_BREAKOUT_PATTERN,
        XSS_TAG_INJECTION_PATTERN,
    )
```

주의:

```text
- existing names는 그대로 유지한다.
- `HTML_ENTITY_RE`는 이동하지 않는다.
- `detect_decoded_attack_hints`는 이동하지 않는다.
- candidate scoring / verdict 로직은 이동하지 않는다.
- browser execution/impact 판단 의미를 바꾸지 않는다.
```

## 7. 허용 범위

허용되는 변경:

```text
- `src/prepare/xss_hints.py` 생성
- XSS 전용 pattern/constants 이동
- `src/prepare_llm_input.py`에 import 추가
- 기존 내부 참조 이름 유지
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- HTML_ENTITY_RE 이동 또는 통합
- detect_decoded_attack_hints 이동
- decoded variants helper 이동
- candidate scoring 변경
- false positive suppression 의미 변경
- browser execution/impact verdict logic 이동 또는 변경
- supporting_events 생성/연결 로직 변경
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- XSS pattern 값 변경
- XSS score 값 변경
- XSS reason_hints 이름 변경
- SQLi/file disclosure/traversal/CMDI patterns 이동
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
browser execution/impact 의미 변경 없음
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
- XSS pattern 값/score 변화
- reason_hints 이름 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- decoded hints 변화
- output key 이름 변경
- XSS 실행 / 브라우저 실행 / 쿠키 탈취 / 세션 탈취 / exfiltration 성공 단정 문구 발생
```

## 10. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_xss_hints_split_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 생성 파일: src/prepare/xss_hints.py
- 이동한 pattern/constants 목록
- 보류한 함수/로직 목록
- HTML_ENTITY_RE 이동 없음
- detect_decoded_attack_hints 이동 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 11. 다음 작업

문서 작성 후 다음 작업은 Codex에 1차 XSS hint split을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan XSS hint split
2. refactor: extract XSS hint patterns
3. docs: record XSS hint split
```

코드 이동 커밋 후보 메시지:

```text
refactor: extract XSS hint patterns
```
