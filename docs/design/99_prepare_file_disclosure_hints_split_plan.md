# 99_prepare_file_disclosure_hints_split_plan

- 문서 상태: file disclosure hints split plan
- 기준 시점: 2026-05-04
- 목적: `99_prepare_hints_split_candidate_review.md` 이후 file disclosure hint 계열을 실제 코드 분리 대상으로 볼 수 있는지, 이동 가능 범위와 보류 범위, suspicious_file_disclosure verdict / Stage2 policy / expected fixture 경계, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_xss_hints_split_plan.md](./99_prepare_xss_hints_split_plan.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_constants_mini_move_summary.md](./99_prepare_constants_mini_move_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

file disclosure hint 계열은 분리 후보로 볼 수 있다. 다만 SQLi/XSS보다 Stage2 reporter와 expected fixture 결합이 더 직접적이므로 1차 범위를 좁게 제한한다.

권장 신규 모듈 후보:

```text
src/prepare/file_disclosure_hints.py
```

1차 이동 후보:

```text
FILE_DISCLOSURE_PATTERNS
PHP_FILTER_CANONICAL_PATTERN
detect_file_disclosure_hints
```

단, `detect_file_disclosure_hints`가 shared helper 의존성이 크면 1차에서는 pattern/constants만 이동하고 함수는 wrapper 유지 또는 보류한다.

1차에서 이동하지 않을 것:

```text
suspicious_file_disclosure verdict 결정 로직
candidate scoring/filtering 로직
Stage2 reporter file_disclosure policy/report wording
expected/test fixture
sensitive path probe 로직
supporting_events 생성/연결 로직
shared attack/search policy constants
SQLi/XSS/traversal/CMDI patterns
```

이번 split plan의 기본 방향:

```text
- mechanical refactor only
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

## 2. grep 확인 결과

확인 명령:

```bash
grep -n "FILE_DISCLOSURE_\|PHP_FILTER_CANONICAL_PATTERN\|suspicious_file_disclosure\|file_disclosure" src/prepare_llm_input.py src/prepare/*.py src/llm_stage2_reporter.py tests/expected -R
```

요약 결과:

```text
src/prepare_llm_input.py:275:FILE_DISCLOSURE_PATTERNS
src/prepare_llm_input.py:491:"file_disclosure:" shared hint prefix
src/prepare_llm_input.py:511:PHP_FILTER_CANONICAL_PATTERN
src/prepare_llm_input.py:776:detect_file_disclosure_hints
src/prepare_llm_input.py:792:FILE_DISCLOSURE_PATTERNS 사용
src/prepare_llm_input.py:794:points_by_name 생성
src/prepare_llm_input.py:796:PHP_FILTER_CANONICAL_PATTERN 사용
src/prepare_llm_input.py:802:PHP_FILTER_CANONICAL_PATTERN variant 사용
src/prepare_llm_input.py:816~834:file_disclosure:* reason_hints 생성
src/prepare_llm_input.py:1384~1389:reason_hints 계열과 연결
src/prepare_llm_input.py:1449~1450:attack category file_disclosure 분류
src/prepare_llm_input.py:3536~3543:candidate scoring과 연결
src/prepare_llm_input.py:3819:php_filter_wrapper_detected
src/prepare_llm_input.py:3851:suspicious_file_disclosure verdict 결정
```

Stage2 reporter 결합:

```text
src/llm_stage2_reporter.py:1099:has_php_wrapper_file_disclosure_context
src/llm_stage2_reporter.py:1101:suspicious_file_disclosure verdict 확인
src/llm_stage2_reporter.py:1105~1107:file_disclosure:* hints 확인
src/llm_stage2_reporter.py:1496~1499:file_disclosure_policy
src/llm_stage2_reporter.py:1632~1633:file_disclosure 성공/유출 단정 금지 문구
src/llm_stage2_reporter.py:1723~1724:file_disclosure report guidance
src/llm_stage2_reporter.py:1927 / 2374:report context 사용
```

expected fixture 결합:

```text
tests/expected/prepare_regression/e_r2_direct_config_path.expected.json
tests/expected/prepare_regression/e_r2_php_wrapper.expected.json
tests/expected/stage_dryrun_regression/e_r2_php_wrapper.expected.json
```

고정되는 주요 값:

```text
file_disclosure:php_filter_wrapper
file_disclosure:base64_source_intent
file_disclosure:resource_parameter
suspicious_file_disclosure
policy_notes.file_disclosure_policy
```

해석:

```text
- file disclosure pattern/constants는 `src/prepare_llm_input.py`에 있다.
- detector 함수 `detect_file_disclosure_hints`는 reason_hints와 candidate scoring에 직접 연결된다.
- suspicious_file_disclosure verdict 결정 로직은 별도 위치에서 pattern 결과를 소비한다.
- Stage2 reporter와 expected fixture가 file_disclosure:* hints와 suspicious_file_disclosure wording을 직접 고정한다.
- 따라서 1차 분리는 pattern/constants와 detector helper만 좁게 검토하고, verdict/scoring/reporter/expected는 이동하거나 수정하지 않는다.
```

## 3. file disclosure evidence boundary

file disclosure hints는 Apache log surface에서 관찰 가능한 요청 구조를 다룬다. 아래 한계를 반드시 유지한다.

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

## 4. 이동 가능 범위

### 4.1 pattern/constants

1차 이동 가능:

```text
FILE_DISCLOSURE_PATTERNS
PHP_FILTER_CANONICAL_PATTERN
```

이동 방식:

```text
- `src/prepare/file_disclosure_hints.py`에 constants/patterns를 정의한다.
- `src/prepare_llm_input.py`의 동일 정의를 제거한다.
- `src/prepare_llm_input.py` import 블록에 동일 이름으로 import한다.
- 기존 내부 참조 이름은 그대로 둔다.
```

### 4.2 detector helper

1차 이동 가능 후보:

```text
detect_file_disclosure_hints
```

이유:

```text
- FILE_DISCLOSURE_PATTERNS와 PHP_FILTER_CANONICAL_PATTERN을 직접 소비하는 전용 detector다.
- file_disclosure:* reason_hints 생성 책임이 비교적 명확하다.
```

단, 실제 코드 이동 전에는 함수 body를 확인해야 한다. `append_unique_hint`, `build_decoded_variants`, variant structure, shared normalization helper에 강하게 의존하면 wrapper 인자 전달 또는 보류를 우선한다.

## 5. 1차에서 이동하지 않을 것

### 5.1 verdict 결정 로직

보류:

```text
suspicious_file_disclosure verdict 결정 로직
php_filter_wrapper_detected 기반 verdict 선택 로직
```

보류 이유:

```text
- Stage1 schema와 Stage2 reporter가 suspicious_file_disclosure를 직접 소비한다.
- expected fixture가 verdict와 policy guidance를 고정한다.
- detector 이동과 verdict 의미 변경을 같은 커밋에 섞으면 안 된다.
```

### 5.2 candidate scoring / filtering

보류:

```text
candidate scoring 로직
filtered_out / false positive suppression 로직
```

보류 이유:

```text
- file disclosure hints는 score boost와 직접 연결된다.
- scoring 의미 변경은 regression 영향 범위가 크다.
- 이번 분리는 hint detector 위치 이동으로만 제한한다.
```

### 5.3 Stage2 reporter / expected fixture

보류:

```text
src/llm_stage2_reporter.py
tests/expected/prepare_regression/*
tests/expected/stage_dryrun_regression/*
```

보류 이유:

```text
- Stage2 reporter는 file_disclosure_policy와 conservative disclosure wording을 직접 포함한다.
- expected fixture가 file_disclosure:* hints와 suspicious_file_disclosure를 고정한다.
- 이번 분리에서 reporter/expected를 수정하면 behavior 변경과 mechanical refactor가 섞인다.
```

### 5.4 sensitive path probe 경계

보류:

```text
sensitive_path_probe_summaries
DIR_PROBE_* constants
SENSITIVE_PATH_PROBE_* constants
sensitive_path_probe_supporting_event 로직
```

보류 이유:

```text
- sensitive path probe는 .env/phpinfo/server-status/backup/admin/wp-login path와 연결된다.
- file disclosure hints와 경계가 겹치지만, 둘은 같은 의미가 아니다.
- sensitive path probing context만으로 파일 노출을 단정하지 않아야 한다.
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
    from src.prepare.file_disclosure_hints import (
        FILE_DISCLOSURE_PATTERNS,
        PHP_FILTER_CANONICAL_PATTERN,
        detect_file_disclosure_hints as _detect_file_disclosure_hints,
    )
except ImportError:
    from prepare.file_disclosure_hints import (
        FILE_DISCLOSURE_PATTERNS,
        PHP_FILTER_CANONICAL_PATTERN,
        detect_file_disclosure_hints as _detect_file_disclosure_hints,
    )
```

`src/prepare_llm_input.py` wrapper 예시:

```python
def detect_file_disclosure_hints(
    combined_target: str,
    query_variants: List[Dict[str, Any]],
    raw_request_target_variants: List[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    return _detect_file_disclosure_hints(
        combined_target,
        query_variants,
        raw_request_target_variants,
    )
```

주의:

```text
- exact signature는 실제 코드의 `detect_file_disclosure_hints`와 동일하게 유지한다.
- existing names는 그대로 유지한다.
- suspicious_file_disclosure verdict 결정 로직은 이동하지 않는다.
- candidate scoring / verdict 로직은 이동하지 않는다.
- Stage2 reporter와 expected fixture는 수정하지 않는다.
```

## 7. 허용 범위

허용되는 변경:

```text
- `src/prepare/file_disclosure_hints.py` 생성
- file disclosure pattern/constants 이동
- `detect_file_disclosure_hints` 이동 또는 wrapper 유지
- `src/prepare_llm_input.py`에 import 추가
- 기존 공개 함수명 wrapper 유지
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- suspicious_file_disclosure verdict 결정 로직 이동 또는 변경
- candidate scoring 변경
- false positive suppression 의미 변경
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- file_disclosure pattern 값/score 변경
- file_disclosure reason_hints 이름 변경
- response body 원문 추정 로직 추가
- sensitive path probe 로직 이동
- SQLi/XSS/traversal/CMDI patterns 이동
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
suspicious_file_disclosure verdict 의미 변경 없음
file_disclosure_policy 의미 변경 없음
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

## 10. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_file_disclosure_hints_split_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 생성 파일: src/prepare/file_disclosure_hints.py
- 이동한 pattern/constants 목록
- 이동한 helper 여부
- 보류한 함수/로직 목록
- suspicious_file_disclosure verdict 결정 로직 변경 없음
- candidate/scoring/filtering 변경 없음
- Stage2 reporter 수정 없음
- expected/test fixture 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 11. 다음 작업

문서 작성 후 다음 작업은 Codex에 1차 file disclosure hint split을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan file disclosure hint split
2. refactor: extract file disclosure hint patterns
3. docs: record file disclosure hint split
```

코드 이동 커밋 후보 메시지:

```text
refactor: extract file disclosure hint patterns
```
