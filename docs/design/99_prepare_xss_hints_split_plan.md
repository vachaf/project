# 99_prepare_xss_hints_split_plan

- 문서 상태: XSS hints split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `de89a90df2e4f6bdecc21a06c62f0dfaf284b7f7`
- 목적: XSS 전용 hint pattern/constants를 `src/prepare/xss_hints.py`로 분리한 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_constants_ownership_map.md](./99_prepare_constants_ownership_map.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

XSS 전용 hint pattern/constants 1차 분리는 완료했다.

생성 파일:

```text
src/prepare/xss_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이번 작업은 mechanical refactor로 제한했다.

```text
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

## 2. 이동 완료 pattern/constants

아래 XSS 전용 pattern/constants를 `src/prepare/xss_hints.py`로 이동했다.

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

`src/prepare_llm_input.py`에는 기존 내부 참조 이름을 그대로 유지하도록 import를 추가했다.

## 3. 이동하지 않은 함수/로직

아래 항목은 이동하거나 수정하지 않았다.

```text
HTML_ENTITY_RE
detect_decoded_attack_hints
decoded variants helper/decoder 계열
append_html_entity_variants
build_html_entity_variants
build_html_entity_decoded_variant
candidate scoring/filtering 로직
browser execution / impact verdict logic
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
SQLi/file disclosure/traversal/CMDI patterns
```

특히 `HTML_ENTITY_RE`는 `src/prepare_llm_input.py`에 유지했고, `src/prepare/decoders.py`의 `HTML_ENTITY_RE`도 수정하지 않았다.

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

## 4. 유지한 XSS evidence boundary

이번 분리 이후에도 아래 한계를 유지한다.

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

## 5. 검증 결과

기준 커밋 `de89a90df2e4f6bdecc21a06c62f0dfaf284b7f7`에서 아래 검증을 통과했다.

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

향후 관련 추가 분리에서 아래 중 하나라도 발생하면 해당 커밋을 수정하거나 롤백한다.

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

## 7. 다음 작업

XSS hints 1차 분리는 완료했다.

`99_prepare_hints_split_candidate_review.md` 기준 다음 후보는 file disclosure hints다. 다만 file disclosure는 suspicious_file_disclosure verdict, sensitive path probe, response bytes/content-type/status 해석과 연결되므로 먼저 grep 확인과 split plan 작성 여부를 판단한다.

권장 확인 명령:

```bash
grep -n "FILE_DISCLOSURE_\|PHP_FILTER_CANONICAL_PATTERN\|suspicious_file_disclosure\|file_disclosure" src/prepare_llm_input.py src/prepare/*.py src/llm_stage2_reporter.py tests/expected -R
```

다음 후보 문서:

```text
docs/design/99_prepare_file_disclosure_hints_split_plan.md
```

문서 전용 커밋 후보:

```text
docs: record XSS hint split
```
