# 99_prepare_traversal_cmdi_hints_split_plan

- 문서 상태: traversal/CMDI hints split plan
- 기준 시점: 2026-05-04
- 목적: SQLi/XSS/file disclosure hint 1차 분리 이후 남은 traversal/CMDI hint 계열을 실제 코드 분리 대상으로 볼 수 있는지, 이동 가능 범위와 보류 범위, evidence boundary, 검증 기준을 고정한다.

관련 문서:

- [99_prepare_attack_hints_shared_policy_candidate_review.md](./99_prepare_attack_hints_shared_policy_candidate_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_hints_split_candidate_review.md](./99_prepare_hints_split_candidate_review.md)
- [99_prepare_sqli_hints_split_plan.md](./99_prepare_sqli_hints_split_plan.md)
- [99_prepare_xss_hints_split_plan.md](./99_prepare_xss_hints_split_plan.md)
- [99_prepare_file_disclosure_hints_split_plan.md](./99_prepare_file_disclosure_hints_split_plan.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)

## 1. 결론

traversal/CMDI hint 계열은 1차 분리 후보로 검토 가능하다.

다만 candidate scoring, normal search false-positive handling, decoded attack hints와 연결되어 있으므로 1차 범위는 pattern/constants 이동으로 제한한다.

권장 신규 모듈 후보:

```text
src/prepare/traversal_cmdi_hints.py
```

1차 이동 후보:

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
```

1차에서 이동하지 않을 것:

```text
AUTOMATION_UA_PATTERNS
detect_decoded_attack_hints
candidate scoring/filtering 로직
normal search false-positive handling
supporting_events 생성/연결 로직
Stage1/Stage2 reporter
expected/test fixture
shared attack/search policy constants
SQLi/XSS/file disclosure patterns
```

이번 split plan의 기본 방향:

```text
- mechanical refactor only
- behavior 변경 없음
- traversal/CMDI evidence boundary 변경 없음
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
grep -n "TRAVERSAL_PATTERNS\|CMDI_PATTERNS\|traversal:\|cmdi:" src/prepare_llm_input.py src/prepare/*.py

grep -n "AUTOMATION_UA_PATTERNS\|automation:ua\|sqlmap\|nikto\|nmap\|python-requests" src/prepare_llm_input.py src/prepare/*.py src/llm_stage1_classifier.py src/llm_stage2_reporter.py

grep -n "SEARCH_PARAM_NAMES\|NORMAL_SEARCH_VALUE_RE\|NORMAL_SEARCH_ATTACK_TEXT_RE\|STRONG_ATTACK_HINT_PREFIXES\|STRONG_ATTACK_HINTS\|ATTACK_ENCODED_PAYLOAD_RE" src/prepare_llm_input.py src/prepare/*.py

grep -n "def detect_decoded_attack_hints\|detect_decoded_attack_hints\|encoding:double_decoded\|encoding:html_entity" src/prepare_llm_input.py src/prepare/*.py tests/expected -R
```

요약 결과:

```text
src/prepare_llm_input.py:280:TRAVERSAL_PATTERNS
src/prepare_llm_input.py:285:CMDI_PATTERNS
src/prepare_llm_input.py:491:"traversal:" shared hint prefix
src/prepare_llm_input.py:493:"cmdi:" shared hint prefix
src/prepare_llm_input.py:711:XSS/TRAVERSAL/CMDI pattern group
src/prepare_llm_input.py:1312~1317:traversal:/cmdi: reason_hints 생성
src/prepare_llm_input.py:1389~1397:attack category extraction
src/prepare_llm_input.py:2923~2925:normal search / false positive 계열 판단과 연결 가능
src/prepare_llm_input.py:3331:traversal pattern 기반 판단
src/prepare_llm_input.py:3452~3462:candidate scoring과 직접 연결
src/prepare_llm_input.py:3731~3738:additional traversal reason_hints
src/prepare_llm_input.py:3857:SQLi/XSS/traversal/CMDI 통합 pattern check
```

같은 grep에서 확인된 계속 보류 대상:

```text
AUTOMATION_UA_PATTERNS: src/prepare_llm_input.py:291
SEARCH_PARAM_NAMES / NORMAL_SEARCH_VALUE_RE / STRONG_ATTACK_HINT_PREFIXES / STRONG_ATTACK_HINTS / ATTACK_ENCODED_PAYLOAD_RE / NORMAL_SEARCH_ATTACK_TEXT_RE: src/prepare_llm_input.py:486~509
detect_decoded_attack_hints: src/prepare_llm_input.py:715
encoding:* expected fixture 고정: tests/expected 일부
```

해석:

```text
- TRAVERSAL_PATTERNS와 CMDI_PATTERNS는 아직 `src/prepare_llm_input.py`에 집중되어 있다.
- traversal/CMDI pattern은 reason_hints, attack category extraction, candidate scoring, normal search/false-positive 계열 판단과 연결된다.
- 따라서 1차 분리는 pattern/constants 이동으로 제한하고 scoring/FP/supporting/decoded logic은 유지해야 한다.
- AUTOMATION_UA_PATTERNS는 lab-* / tool UA 과해석 금지와 연결되어 이번 split에서는 제외한다.
- shared attack/search policy constants와 detect_decoded_attack_hints는 계속 보류한다.
```

## 3. traversal evidence boundary

traversal hints는 Apache log surface에서 관찰 가능한 경로 문자열 구조를 다룬다. 아래 한계를 반드시 유지한다.

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

## 4. CMDI evidence boundary

CMDI hints는 Apache log surface에서 관찰 가능한 command-like token 구조를 다룬다. 아래 한계를 반드시 유지한다.

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

## 5. 이동 가능 범위

### 5.1 pattern/constants

1차 이동 가능:

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
```

이동 방식:

```text
- `src/prepare/traversal_cmdi_hints.py`에 constants/patterns를 정의한다.
- `src/prepare_llm_input.py`의 동일 정의를 제거한다.
- `src/prepare_llm_input.py` import 블록에 동일 이름으로 import한다.
- 기존 내부 참조 이름은 그대로 둔다.
```

### 5.2 narrow helper

1차 이동 가능한 helper는 이번 문서에서는 확정하지 않는다.

이유:

```text
- traversal/CMDI pattern 사용 위치가 candidate scoring, false-positive handling, decoded hints와 연결되어 있다.
- 별도 detector helper가 독립적으로 존재하는지 먼저 확인해야 한다.
- 1차는 pattern/constants 이동만 권장한다.
```

## 6. 1차에서 이동하지 않을 것

### 6.1 automation UA patterns

보류:

```text
AUTOMATION_UA_PATTERNS
```

보류 이유:

```text
- automation/tool User-Agent는 lab-* / experiment-like UA guard와 직접 연결된다.
- sqlmap/nikto/nmap/curl/wget/python-requests UA는 trace aid일 수 있지만 성공 증거가 아니다.
- Stage1/Stage2 wording guard와 함께 별도 검토해야 한다.
```

### 6.2 decoded attack hints

보류:

```text
detect_decoded_attack_hints
```

보류 이유:

```text
- SQLi, XSS, traversal, file disclosure, CMDI와 모두 연결된다.
- decoders.py의 decoded variants와도 연결된다.
- encoding descriptors와 hint generation을 동시에 다룬다.
- topic-specific module로 옮기면 경계가 흐려진다.
```

### 6.3 candidate scoring / false positive / category extraction

보류:

```text
candidate scoring/filtering 로직
normal search false-positive handling
attack category extraction 로직
reason_hints category normalization 로직
```

보류 이유:

```text
- scoring과 false positive suppression은 behavior 변경 위험이 크다.
- traversal/CMDI pattern 이동과 scoring 의미 변경을 같은 커밋에 섞으면 안 된다.
- reason_hints 이름/의미를 유지해야 한다.
```

### 6.4 supporting context

보류:

```text
supporting_events 생성/연결 로직
```

보류 이유:

```text
- supporting_events 보존/연결 기준은 여러 공격군과 공유될 수 있다.
- traversal/CMDI hint 이동과 supporting event 의미 변경을 같은 커밋에 섞으면 안 된다.
```

### 6.5 shared attack/search policy constants

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

## 7. 예상 구현 방식

권장 import 패턴:

```python
try:
    from src.prepare.traversal_cmdi_hints import (
        CMDI_PATTERNS,
        TRAVERSAL_PATTERNS,
    )
except ImportError:
    from prepare.traversal_cmdi_hints import (
        CMDI_PATTERNS,
        TRAVERSAL_PATTERNS,
    )
```

주의:

```text
- existing names는 그대로 유지한다.
- `AUTOMATION_UA_PATTERNS`는 이동하지 않는다.
- `detect_decoded_attack_hints`는 이동하지 않는다.
- candidate scoring / false-positive / category extraction 로직은 이동하지 않는다.
- shared attack/search policy constants는 이동하지 않는다.
```

## 8. 허용 범위

허용되는 변경:

```text
- `src/prepare/traversal_cmdi_hints.py` 생성
- traversal/CMDI pattern constants 이동
- `src/prepare_llm_input.py`에 import 추가
- 기존 내부 참조 이름 유지
- py_compile / regression 통과를 위한 import 정렬 수준의 최소 수정
```

허용되지 않는 변경:

```text
- AUTOMATION_UA_PATTERNS 이동
- detect_decoded_attack_hints 이동
- decoded variants helper 이동
- candidate scoring 변경
- false positive suppression 의미 변경
- normal search handling 변경
- attack category extraction 변경
- supporting_events 생성/연결 로직 변경
- Stage2 reporter 수정
- expected/test fixture 수정
- policy wording 변경
- output key 변경
- TRAVERSAL_PATTERNS 값/score 변경
- CMDI_PATTERNS 값/score 변경
- traversal/cmdi reason_hints 이름 변경
- SQLi/XSS/file disclosure patterns 이동
- shared attack/search policy constants 이동
```

## 9. 검증 계획

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
normal search false-positive handling 의미 변경 없음
attack category extraction 의미 변경 없음
output key 의미 변경 없음
policy_notes 의미 변경 없음
expected/test fixture 수정 없음
Stage2 reporter 수정 없음
```

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 분리 커밋을 수정하거나 롤백한다.

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

## 11. 완료 후 문서 반영

이동 완료 후 아래 문서를 갱신한다.

```text
docs/design/99_prepare_traversal_cmdi_hints_split_plan.md
docs/planning/99_비교실험_후속개선_TODO.md
```

완료 기록에 포함할 항목:

```text
- 생성 파일: src/prepare/traversal_cmdi_hints.py
- 이동한 pattern/constants 목록
- 보류한 함수/로직 목록
- AUTOMATION_UA_PATTERNS 이동 없음
- detect_decoded_attack_hints 이동 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 변경 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- py_compile / prepare regression / stage dry-run regression 결과
```

## 12. 다음 작업

문서 작성 후 다음 작업은 Codex에 1차 traversal/CMDI hint split을 맡기는 것이다.

권장 커밋 순서:

```text
1. docs: plan traversal CMDI hint split
2. refactor: extract traversal CMDI hint patterns
3. docs: record traversal CMDI hint split
```

코드 이동 커밋 후보 메시지:

```text
refactor: extract traversal CMDI hint patterns
```
