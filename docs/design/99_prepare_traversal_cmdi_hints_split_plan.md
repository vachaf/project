# 99_prepare_traversal_cmdi_hints_split_plan

- 문서 상태: traversal/CMDI hints split 완료 기록
- 기준 시점: 2026-05-04
- 기준 커밋: `fdedb2ec1627cb9ef0a6d5feb115c6d6fc965a95`
- 목적: traversal/CMDI pattern constants를 `src/prepare/traversal_cmdi_hints.py`로 분리한 완료 범위, 유지한 계약, 보류한 영역, 검증 결과를 기록한다.

관련 문서:

- [99_prepare_attack_hints_shared_policy_candidate_review.md](./99_prepare_attack_hints_shared_policy_candidate_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_xss_hints_split_plan.md](./99_prepare_xss_hints_split_plan.md)
- [99_prepare_file_disclosure_hints_split_plan.md](./99_prepare_file_disclosure_hints_split_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 완료 결론

traversal/CMDI pattern constants 1차 분리는 완료했다.

생성 파일:

```text
src/prepare/traversal_cmdi_hints.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이번 작업은 mechanical refactor로 제한했다.

```text
- behavior 변경 없음
- traversal/CMDI evidence boundary 변경 없음
- false positive suppression 의미 변경 없음
- candidate/scoring/filtering 변경 없음
- normal search false-positive handling 변경 없음
- attack category extraction 변경 없음
- reason_hints category normalization 변경 없음
- supporting_events 생성/연결 로직 변경 없음
- output key 변경 없음
- policy wording 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
```

## 2. 이동 완료 pattern/constants

아래 pattern constants를 `src/prepare/traversal_cmdi_hints.py`로 이동했다.

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
```

`src/prepare_llm_input.py`에는 기존 내부 참조 이름을 그대로 유지하도록 import를 추가했다.

## 3. 이동하지 않은 함수/로직

아래 항목은 이동하거나 수정하지 않았다.

```text
AUTOMATION_UA_PATTERNS
detect_decoded_attack_hints
decoded variants helper/decoder 계열
candidate scoring/filtering 로직
normal search false-positive handling
attack category extraction 로직
reason_hints category normalization 로직
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
SQLi/XSS/file disclosure patterns
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

## 4. 유지한 traversal evidence boundary

이번 분리 이후에도 아래 한계를 유지한다.

```text
- path traversal 성공을 단정하지 않는다.
- 파일 읽기 성공을 단정하지 않는다.
- /etc/passwd 또는 win.ini 내용 노출을 단정하지 않는다.
- filesystem 존재 여부를 단정하지 않는다.
- response body 원문을 추정하지 않는다.
- decoded ../ 구조는 request text 관찰이지 filesystem access proof가 아니다.
- status_code=200, content-type, response_body_bytes만으로 file exposure를 확정하지 않는다.
```

허용되는 표현:

```text
- traversal-like pattern observed
- dot-dot-slash style path sequence observed
- sensitive file path token observed in request text
- possible traversal candidate based on Apache log surface
```

금지 표현:

```text
- traversal succeeded
- file was read
- /etc/passwd was exposed
- win.ini was retrieved
- filesystem access confirmed
- sensitive file contents leaked
```

## 5. 유지한 CMDI evidence boundary

이번 분리 이후에도 아래 한계를 유지한다.

```text
- command execution 성공을 단정하지 않는다.
- whoami/id/cat/uname/curl/wget/bash/sh 등이 실행되었다고 단정하지 않는다.
- shell access 또는 server compromise를 단정하지 않는다.
- command-like token은 request text 구조 관찰일 뿐이다.
- status_code=200, content-type, response_body_bytes만으로 command execution success를 확정하지 않는다.
```

허용되는 표현:

```text
- command-injection-like token observed
- shell metacharacter with command-like token observed
- possible CMDI candidate based on Apache log surface
- request text contains command-like payload structure
```

금지 표현:

```text
- command executed
- shell access obtained
- whoami/id/cat output returned
- server compromised
- reverse shell succeeded
```

## 6. 검증 결과

기준 커밋 `fdedb2ec1627cb9ef0a6d5feb115c6d6fc965a95`에서 아래 검증을 통과했다.

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
- TRAVERSAL_PATTERNS 값/score 변화
- CMDI_PATTERNS 값/score 변화
- traversal/cmdi reason_hints 이름 변화
- candidate_rows 변화
- filtered_out 변화
- supporting_events 변화
- normal search false-positive handling 변화
- decoded hints 변화
- output key 이름 변경
- traversal 성공 / 파일 읽기 성공 / command execution 성공 / server compromise 단정 문구 발생
```

## 8. 다음 작업

traversal/CMDI hints 1차 분리는 완료했다.

현재 prepare hint split에서 topic-specific pattern 분리는 아래 상태다.

```text
src/prepare/sqli_hints.py
src/prepare/xss_hints.py
src/prepare/file_disclosure_hints.py
src/prepare/traversal_cmdi_hints.py
```

계속 보류할 영역:

```text
AUTOMATION_UA_PATTERNS
shared attack/search policy constants
detect_decoded_attack_hints
candidate scoring/filtering
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
```

다음 작업은 `docs/design/99_prepare_hints_split_summary.md`를 갱신하여 traversal/CMDI 완료를 반영하고, automation UA / shared attack policy / decoded hints를 다음 검토 대상으로 정리한다.

문서 전용 커밋 후보:

```text
docs: record traversal CMDI hint split
```
