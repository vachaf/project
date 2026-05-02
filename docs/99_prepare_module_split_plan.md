# 99_prepare_module_split_plan

## 1. 배경

`src/prepare_llm_input.py`는 현재 전처리 파이프라인의 핵심 역할을 한 파일에 많이 모아두고 있다. 기능이 안정화되는 동안에는 한 파일에 유지하는 편이 변경 추적에 유리했지만, 이제는 책임이 커져 장기 유지보수성이 떨어지는 구간에 들어왔다.

현재 이 파일이 포함하는 대표 책임은 아래와 같다.

- URL decode depth 1/2
- HTML entity decode
- SQLi / XSS / traversal / HPP / file disclosure hint 생성
- L3 hint: Log4Shell, SSRF, SSTI, webshell
- false positive review
- `supporting_events`
- `probing_sequence_summaries`
- `ip_behavior_aggregates`
- output JSON 생성
- CLI

현재 regression이 안정화되어 있으므로 모듈 분리를 검토할 수 있는 시점은 맞다. 다만 지금 한 번에 많은 파일을 동시에 분리하면 regression 실패 시 원인 추적 범위가 너무 넓어지고, mechanical refactor인지 동작 변경인지 구분하기 어려워진다.

이 문서의 목적은 전면 리팩터링 계획이 아니라, 회귀 안전성을 유지하는 점진적 모듈 분리 계획을 정리하는 것이다.

## 2. 현재 안전장치

현재 prepare 관련 안전장치는 이미 갖춰져 있다.

- prepare regression
  - `python3 scripts/check_prepare_regression.py`
  - `python3 scripts/check_prepare_regression.py --strict`
  - 현재 11 fixtures / 0 fail

- stage dry-run regression
  - `python3 scripts/check_stage_dryrun_regression.py`
  - `python3 scripts/check_stage_dryrun_regression.py --strict`
  - 현재 5 fixtures / 0 fail

- py_compile
  - `src/prepare_llm_input.py`
  - `scripts/check_prepare_regression.py`
  - `scripts/check_stage_dryrun_regression.py`
  - `src/llm_stage1_classifier.py`
  - `src/llm_stage2_reporter.py`
  - `src/run_analysis_pipeline.py`

이 상태 덕분에 “작게 나누고, 매 단계마다 회귀를 통과시키는 방식”의 분리가 가능하다.

## 3. 핵심 원칙

- 동작 변경 없는 mechanical refactor 우선
- 한 번에 한 모듈만 분리
- 분리와 기능 개선을 같은 커밋에 섞지 않음
- regression 실패 시 원인 범위가 1개 모듈로 좁혀져야 함
- output JSON 의미와 key 구조를 바꾸지 않음
- `reason_hints` 이름을 바꾸지 않음
- score / candidate / filtering 기준을 바꾸지 않음
- Stage1 / Stage2 prompt나 schema는 이번 분리와 무관하게 유지
- Apache logs-only 원칙 유지
- response body 원문, DB 결과, 브라우저 실행 여부 사용 금지
- `status_code=200`, `text/html`, `response_body_bytes`만으로 성공 단정 금지
- 실험환경 특화 rule 금지
  - `lab-*` User-Agent
  - 특정 IP
  - 특정 response size
  - OpenCart / Juice Shop 이름
  - 특정 route 문자열

## 4. 잘못된 접근: 5개 파일 동시 분리

아래 구조는 장기 목표로는 자연스럽지만, 1차 작업으로는 위험하다.

```text
src/prepare/
├── decoders.py
├── l3_hints.py
├── sqli_hints.py
├── xss_hints.py
└── file_disclosure_hints.py
```

문제는 다음과 같다.

- regression 실패 시 원인 추적이 어려움
- import 변경 범위가 큼
- circular import 가능성 증가
- SQLi / XSS / file disclosure는 scoring / candidate 판정과 강하게 결합되어 있음
- 함수만 옮기면 구조적 이득은 작고 위험만 커질 수 있음

결론적으로 “개념적으로 예쁜 구조”와 “지금 안전하게 할 수 있는 구조”는 다르다. 현재는 후자를 우선해야 한다.

## 5. 권장 접근: 2개 모듈 순차 분리

### Step 1-A: `decoders.py` 분리

목표는 decoded variant 생성 관련 순수 함수만 먼저 떼어내는 것이다.

예상 파일:

```text
src/prepare/__init__.py
src/prepare/decoders.py
```

분리 대상 예:

- URL decode 1회
- URL decode 2회
- HTML entity decode
- decoded variants 생성 보조 함수

이 단계의 원칙:

- 로직 변경 금지
- decode 결과가 기존과 byte-for-byte 또는 JSON-equivalent로 같아야 함
- exception 처리 방식도 기존과 동일해야 함
- lowercase 변환, plus 처리 변경, empty string 처리 변경 같은 부수 개선 금지

검증:

- `python3 scripts/check_prepare_regression.py --strict`
- `python3 scripts/check_stage_dryrun_regression.py --strict`
- `python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py`
- 가능하면 output JSON diff 확인

성공 기준:

- prepare regression 11개 pass
- stage dry-run regression 5개 pass
- 기존 fixture의 `reason_hints` 변화 없음

### Step 1-B: `l3_hints.py` 분리

전제:

- Step 1-A가 별도 커밋으로 완료되어 있어야 함
- regression이 모두 통과해야 함

목표는 Log4Shell / SSRF / SSTI / webshell L3 hint 로직만 별도 모듈로 분리하는 것이다.

예상 파일:

```text
src/prepare/l3_hints.py
```

분리 대상:

- `l3:log4shell`
- `log4shell:jndi_lookup`
- `log4shell:ldap_callback`
- `log4shell:rmi_callback`
- `log4shell:dns_callback`
- `l3:ssrf`
- `ssrf:url_parameter`
- `ssrf:metadata_ip`
- `ssrf:localhost_target`
- `ssrf:internal_ip_target`
- `ssrf:cloud_metadata_target`
- `l3:ssti`
- `ssti:template_expression`
- `ssti:jinja_expression`
- `ssti:freemarker_expression`
- `l3:webshell_probe`
- `webshell:script_filename`
- `webshell:cmd_parameter`
- `webshell:known_shell_name`

이 단계의 원칙:

- L3 탐지 조건 변경 금지
- 고신호 조건을 넓히지 않음
- 새 L3 패턴 추가 금지
- 기존 fixture `l3_log4shell_ssrf_context`, `l3_ssti_webshell_context`가 동일하게 통과해야 함

검증:

- `python3 scripts/check_prepare_regression.py --strict`
- `python3 scripts/check_stage_dryrun_regression.py --strict`
- 특히 L3 fixture 2개와 stage dry-run L3 fixture 확인
- `py_compile`

성공 기준:

- prepare regression 11개 pass
- stage dry-run regression 5개 pass
- L3 `reason_hints` 변화 없음

## 6. 보류 대상

### SQLi / XSS hint 분리 보류

이유:

- scoring과 candidate 판정에 강하게 결합되어 있음
- 단순 함수 이동만으로는 구조적 이득이 작음
- 현재 SQLi quote / parenthesis / xclose hint가 막 안정화된 상태
- educational SQL / XSS false positive 완화를 깨뜨릴 위험이 있음

향후 분리 조건:

- SQLi / XSS rule weight 구조를 도입할 때
- hint scoring을 별도 rule engine으로 재설계할 때
- FP rule과 attack structure rule을 명확히 분리할 때

### file_disclosure hint 분리 보류

이유:

- `suspicious_file_disclosure` Stage1 verdict와 Stage2 설명 보강이 최근 완료됨
- direct config path와 PHP wrapper candidate 구분이 중요함
- 지금 분리하면 과승격 / 과소탐지 회귀 위험이 있음

향후 분리 조건:

- file disclosure rule set을 source disclosure / local file read / direct sensitive path로 나눌 때

### ip_behavior / probing / supporting_events 분리 보류

이유:

- 메인 candidate / `supporting_events` 구조와 의존성이 큼
- context-only 원칙이 중요함
- aggregation 결과가 Stage2 문맥에도 연결되어 있음
- 분리 전 candidate 구조 표준화가 필요함

향후 분리 조건:

- candidate data model을 표준화한 뒤
- `ip_behavior_aggregates`가 더 안정화된 뒤
- `probing_sequence_summaries`와 `supporting_events` 입력 / 출력을 명확히 정의한 뒤

## 7. 권장 최종 구조

아래는 장기 목표일 뿐이며, 지금 당장 모두 구현하는 계획이 아니다.

```text
src/
├── prepare/
│   ├── __init__.py
│   ├── decoders.py
│   ├── l3_hints.py
│   ├── sqli_hints.py        # future
│   ├── xss_hints.py         # future
│   ├── file_disclosure.py   # future
│   ├── ip_behavior.py       # future
│   ├── probing.py           # future
│   └── models.py            # future, optional
└── prepare_llm_input.py
```

`prepare_llm_input.py`의 장기 역할:

- CLI
- input / output file handling
- pipeline orchestration
- backwards-compatible output format 유지

## 8. 단계별 커밋 계획

### Commit 1

```bash
git commit -m "Add prepare module split plan"
```

내용:

- `docs/99_prepare_module_split_plan.md`만 추가
- 코드 변경 없음

### Commit 2

```bash
git commit -m "Extract prepare decoders"
```

내용:

- `src/prepare/__init__.py`
- `src/prepare/decoders.py`
- `prepare_llm_input.py` import / call site 최소 수정
- 동작 변경 없음

검증:

- prepare regression strict pass
- stage dry-run strict pass
- `py_compile`
- 가능하면 output JSON diff

### Commit 3

```bash
git commit -m "Extract L3 prepare hints"
```

내용:

- `src/prepare/l3_hints.py`
- `prepare_llm_input.py` import / call site 최소 수정
- 동작 변경 없음

검증:

- prepare regression strict pass
- stage dry-run strict pass
- `py_compile`
- L3 fixture `reason_hints` 동일

## 9. 체크리스트

### 분리 전

- `git status` clean
- prepare regression strict pass
- stage dry-run regression strict pass
- `py_compile` pass
- `docs/99_prepare_module_split_plan.md` 승인
- feature branch 사용 권장

### 각 분리 후

- 새 파일 `py_compile` pass
- import cycle 없음
  - `python3 -c "from src.prepare import *"`
- prepare regression strict pass
- stage dry-run regression strict pass
- 기존 output JSON 구조 변화 없음
- `reason_hints` 이름 변화 없음
- score / candidate count 변화 없음
- 문서 업데이트는 최소화

## 10. 실패 시 롤백 기준

아래 중 하나라도 발생하면 해당 분리 커밋은 롤백 또는 수정해야 한다.

- prepare regression fail
- stage dry-run regression fail
- candidate 수 변화
- `reason_hints` 누락
- decoded view 변화
- L3 fixture hint 변화
- educational SQL / XSS FP fixture 실패
- normal baseline fixture 실패
- PHP wrapper / direct config path fixture 실패
- `ip_behavior_aggregates` fixture 실패
- import cycle 발생
- CLI output filename 변화

## 11. 다음 의사결정

- 현재는 근본 리팩터링을 검토할 시점이 맞다.
- 단, 전면 리팩터링이 아니라 회귀 안전성을 유지하는 점진적 분리가 맞다.
- 첫 실제 구현은 `decoders.py` 분리부터 시작한다.
- `l3_hints.py`는 `decoders.py` 분리 후 별도 커밋으로 진행한다.
- SQLi / XSS / file disclosure / ip_behavior / probing 분리는 지금 하지 않는다.
