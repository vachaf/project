# 99_prepare_file_disclosure_hints_split_plan

- 문서 상태: file disclosure hints split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `2981dd11d96bd93e0973f0c0b8fa228092c2f0f4`
- 목적: file disclosure hint pattern/constants와 전용 detector를 `src/prepare/file_disclosure_hints.py`로 분리한 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_xss_hints_split_plan.md](./99_prepare_xss_hints_split_plan.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

file disclosure hint pattern/constants와 전용 detector 1차 분리는 완료했다.

생성 파일:

```text
src/prepare/file_disclosure_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이번 작업은 mechanical refactor로 제한했다.

```text
- behavior 변경 없음
- file disclosure evidence boundary 변경 없음
- suspicious_file_disclosure verdict 의미 변경 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- Stage2 reporter 수정 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
```

## 2. 이동 완료 pattern/constants

아래 pattern/constants를 `src/prepare/file_disclosure_hints.py`로 이동했다.

```text
FILE_DISCLOSURE_PATTERNS
PHP_FILTER_CANONICAL_PATTERN
```

`src/prepare_llm_input.py`에는 기존 내부 참조 이름을 그대로 유지하도록 import를 추가했다.

## 3. 이동 완료 helper

아래 detector helper를 `src/prepare/file_disclosure_hints.py`로 이동했다.

```text
detect_file_disclosure_hints
```

`src/prepare_llm_input.py`에는 기존 공개 함수명을 유지하는 wrapper를 남겼다.

```python
def detect_file_disclosure_hints(...):
    return _detect_file_disclosure_hints(...)
```

## 4. 이동하지 않은 함수/로직

아래 항목은 이동하거나 수정하지 않았다.

```text
suspicious_file_disclosure verdict 결정 로직
php_filter_wrapper_detected 기반 verdict 선택 로직
candidate scoring/filtering 로직
supporting_events 생성/연결 로직
Stage2 reporter
expected/test fixture
sensitive path probe 로직
DIR_PROBE_* constants
SENSITIVE_PATH_PROBE_* constants
shared attack/search policy constants
SQLi/XSS/traversal/CMDI patterns
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

## 5. 유지한 file disclosure evidence boundary

이번 분리 이후에도 아래 한계를 유지한다.

```text
- 파일 내용 노출을 단정하지 않는다.
- response body 원문을 추정하지 않는다.
- .env 노출을 단정하지 않는다.
- phpinfo 노출을 단정하지 않는다.
- server-status 노출 또는 차단 성공을 단정하지 않는다.
- backup/config 파일 노출을 단정하지 않는다.
- PHP source/config disclosure 성공을 단정하지 않는다.
- status_code=200, content-type, response_body_bytes만으로 file exposure를 확정하지 않는다.
- suspicious_file_disclosure는 의심 verdict이지 confirmed disclosure가 아니다.
```

허용되는 표현:

```text
- file disclosure-like request pattern observed
- php://filter-style wrapper observed
- suspicious_file_disclosure candidate
- possible sensitive file access attempt, not confirmed exposure
- source/config disclosure attempt pattern, not source disclosure success
```

금지 표현:

```text
- file was disclosed
- .env contents leaked
- phpinfo was exposed
- server-status data was exposed
- backup archive was downloaded
- PHP source code was exposed
- config file contents were returned
```

## 6. 유지한 Stage2 / expected 계약

아래 Stage2 reporter와 expected fixture는 수정하지 않았다.

```text
src/llm_stage2_reporter.py
tests/expected/prepare_regression/e_r2_direct_config_path.expected.json
tests/expected/prepare_regression/e_r2_php_wrapper.expected.json
tests/expected/stage_dryrun_regression/e_r2_php_wrapper.expected.json
```

계속 고정되는 주요 값:

```text
file_disclosure:php_filter_wrapper
file_disclosure:base64_source_intent
file_disclosure:resource_parameter
suspicious_file_disclosure
policy_notes.file_disclosure_policy
```

## 7. 검증 결과

기준 커밋 `2981dd11d96bd93e0973f0c0b8fa228092c2f0f4`에서 아래 검증을 통과했다.

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

향후 관련 추가 분리에서 아래 중 하나라도 발생하면 해당 커밋을 수정하거나 롤백한다.

```text
- import cycle 발생
- py_compile fail
- prepare regression fail
- stage dry-run regression fail
- FILE_DISCLOSURE_PATTERNS 값/score 변화
- file_disclosure reason_hints 이름 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- suspicious_file_disclosure verdict 변화
- Stage2 file_disclosure_policy 변화
- output key 이름 변경
- file disclosure / source disclosure / config disclosure 성공 단정 문구 발생
```

## 9. 다음 작업

file disclosure hints 1차 분리는 완료했다.

prepare hints split의 주요 3개 후보는 완료 상태다.

```text
src/prepare/sqli_hints.py
src/prepare/xss_hints.py
src/prepare/file_disclosure_hints.py
```

다음 작업은 traversal/CMDI/automation으로 바로 들어가기보다 hints split summary를 먼저 작성한다.

권장 다음 문서:

```text
docs/design/99_prepare_hints_split_summary.md
```

summary에서 정리할 항목:

```text
- SQLi/XSS/file disclosure 완료 모듈
- 각 모듈 이동 항목
- 보류한 shared logic
- prepare/stage dry-run regression 결과
- 남은 후보: traversal/CMDI/automation hints, shared attack/search policy constants
- 다음 후보를 코드 분리로 진행할지, 후보 비교 문서로 먼저 갈지 결정
```

문서 전용 커밋 후보:

```text
docs: record file disclosure hint split
```
