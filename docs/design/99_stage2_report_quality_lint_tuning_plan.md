# 99_stage2_report_quality_lint_tuning_plan

- 문서 상태: Stage2 report quality lint tuning plan
- 기준 시점: 2026-05-05
- 목적: `scripts/check_stage2_report_quality.py`를 전체 과거 `stage2_report.json`에 적용한 결과를 바탕으로, blocker 과잉탐지를 줄이고 warning-only review tool로 안정화하기 위한 튜닝 방향을 정한다.

관련 문서:

- [99_stage2_report_quality_lint_candidate_review.md](./99_stage2_report_quality_lint_candidate_review.md)
- [99_stage2_prompt_compaction_plan.md](./99_stage2_prompt_compaction_plan.md)
- [../reviews/99_post_refactor_dry_run_spot_check.md](../reviews/99_post_refactor_dry_run_spot_check.md)
- [../reviews/99_post_refactor_LLM_output_spot_check.md](../reviews/99_post_refactor_LLM_output_spot_check.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

옛날 Stage2 보고서를 일괄 재작성하지 않는다.

대신 `check_stage2_report_quality.py`의 lint rule을 튜닝한다.

현재 판단:

```text
- 과거 보고서는 당시 모델/prompt 기준 산출물로 보존한다.
- 발표/최종 보고서에 재사용할 산출물만 최신 pipeline으로 재생성한다.
- lint는 과거 보고서까지 포함한 전체 batch에서 warning/blocker 분포를 보는 보조 도구로 사용한다.
- 현재 blocker 중 일부는 실제 위험 표현이지만, 일부는 안전한 부정문을 과잉탐지한 것이다.
```

권장 다음 작업:

```text
1. blocker 과잉탐지 완화
2. safe negation pattern 보강
3. recommended_actions의 "확인 필요" 계열은 success assertion blocker에서 완화
4. 최신 H/E actual LLM 보고서에는 blocker가 없어야 한다는 기준 유지
```

## 2. 전체 batch 결과 요약

실행 대상:

```bash
find lab -path "*reports*" -name "*stage2_report.json" | sort
```

lint batch 요약:

```text
- PASS/WARN/FAIL이 모두 발생
- dry-run report 중 report=null인 파일은 PASS checked_fields=0으로 처리됨
- FAIL은 주로 과거 보고서 또는 강한 표현이 포함된 보고서에서 발생
- 최신 H R4 / E R2B actual report는 blocker 없이 warning 중심으로 처리됨
```

warning rule 분포:

```text
auth_success_assertion: 21
xss_execution_assertion: 17
file_disclosure_success_assertion: 17
context_only_escalation: 6
sql_success_assertion: 5
method_protocol_success_assertion: 2
traversal_cmdi_success_assertion: 1
ip_ua_attribution_assertion: 1
```

해석:

```text
- auth/file_disclosure/XSS 계열은 안전한 부정문에도 많이 반응한다.
- 이 자체는 useful signal이지만 blocker로 남으면 review 효율이 떨어진다.
- regex lint의 1차 목표는 자동 실패가 아니라 위험 후보 위치를 빠르게 찾는 것이다.
```

## 3. 실제 blocker 성격 분류

### 3.1 실제로 고쳐야 할 수 있는 과거 표현

아래 표현은 현재 Apache logs-only 기준으로 강하다.

```text
- "로그인 성공 응답 형태에 부합"
- "인증 우회 성공 정황"
- "SQLi 성공을 암시"
- "데이터 탈취 기록 확인"
- "브라우저 XSS 실행 확인"
```

판단:

```text
- 과거 보고서 산출물에서는 그대로 보존 가능
- 최신 보고서나 발표자료에 쓰려면 재생성 또는 수동 수정 필요
- lint가 blocker/warning으로 잡는 것이 타당함
```

### 3.2 safe negation인데 blocker/warning으로 잡힌 표현

아래 표현은 오히려 보수적 문장이다.

```text
- "로그인 성공은 확인되지 않았습니다"
- "계정 탈취로는 해석하지 않았습니다"
- "침해 성공으로 볼 근거는 부족합니다"
- "파일 내용 노출 성공은 확인할 수 없습니다"
- "XSS 실행 ... 확인하지 않았습니다"
- "본 보고서에서 주장하지 않았습니다"
- "입증할 근거가 없습니다"
```

판단:

```text
- blocker로 두면 안 됨
- warning도 과할 수 있음
- info로 낮추는 것이 적절함
```

## 4. 튜닝 목표

1차 튜닝 목표:

```text
- 명확한 부정/제한 문맥은 blocker가 아니라 info로 낮춘다.
- "가능성", "시사", "정황", "암시"는 warning으로 유지한다.
- 실제 성공 단정은 blocker로 유지한다.
- 기본 모드는 계속 exit code 0을 유지한다.
- --fail-on-blocker는 유지하지만, blocker 기준을 더 보수적으로 만든다.
```

성공 기준:

```text
- H R4 actual report: blocker_count=0 유지
- E R2B actual report: blocker_count=0 유지
- safe negation 문장 대부분 info로 하향
- 과거의 강한 성공 단정은 blocker 또는 warning으로 유지
- tests/test_stage2_report_quality.py 통과
- 기존 prepare/stage regression 통과
```

## 5. 권장 코드 변경

### 5.1 conservative context severity 조정

현재 개념:

```text
blocker expression + conservative context -> warning
warning expression + conservative context -> info
```

권장 변경:

```text
strong negation context가 있으면 blocker expression도 info로 낮춘다.
weak conservative context이면 blocker -> warning으로 낮춘다.
```

구분 예:

```text
strong negation:
- 확인되지 않았다
- 확인할 수 없다
- 확정할 수 없다
- 단정할 수 없다
- 근거가 부족하다
- 증거가 없다
- 해석하지 않았다
- 주장하지 않았다
- 입증할 근거가 없다
- 본 보고서에서 주장하지 않았다
- no evidence
- not confirmed

weak conservative:
- 가능성
- 시도
- 정황
- 의심
- 관찰
- 추정
- review 필요
```

권장 구현:

```text
- STRONG_NEGATION_PATTERNS 추가
- WEAK_CONSERVATIVE_PATTERNS 분리
- has_conservative_context() 대신 classify_context() 형태 검토
```

예시 판정:

```text
"파일 내용 노출 성공은 확인할 수 없습니다" -> info
"로그인 성공 가능성을 시사" -> warning
"SQLi 성공을 암시" -> warning 또는 blocker 후보
"SQL injection 성공" -> blocker
```

### 5.2 recommended_actions 완화

`recommended_actions`는 본질적으로 확인/검증을 요구하는 섹션이다. 이 섹션에서 나오는 "확인" 표현은 실제 단정이라기보다 조치일 수 있다.

권장:

```text
- path가 report.recommended_actions[*]이면 blocker를 warning으로 낮추는 옵션 검토
- 단, "데이터 탈취 성공"처럼 명확한 성공 단정은 warning보다 강하게 남길 수 있음
```

예:

```text
"브라우저 XSS 실행 여부 확인" -> warning 또는 info
"브라우저에서 스크립트가 실행되었다" -> blocker
```

### 5.3 pattern 정교화

`auth_success_assertion`에서 아래처럼 부정문 전체를 blocker로 잡는 것을 줄인다.

추가 negation 후보:

```text
- 해석하지 않았
- 주장하지 않았
- 입증할 근거
- 볼 근거는 부족
- 확인되지 않아
- 확인할 수 없어
```

`file_disclosure_success_assertion`에서 아래는 info로 낮춘다.

```text
- 실제 파일 내용 노출 성공은 확인되지 않음
- 파일 내용 노출 성공은 확인할 수 없음
- file exposure not confirmed
```

`xss_execution_assertion`에서 아래는 info로 낮춘다.

```text
- XSS 실행은 확인되지 않음
- 브라우저 실행 여부를 확인할 수 없음
- 실행으로 해석하지 않음
```

## 6. 테스트 추가/수정 계획

기존 테스트에 아래 케이스를 추가한다.

```text
- "로그인 성공은 확인되지 않았습니다" -> blocker_count=0, warning_count=0 또는 info 허용
- "계정 탈취로는 해석하지 않았습니다" -> blocker_count=0
- "파일 내용 노출 성공은 확인할 수 없습니다" -> blocker_count=0, info 허용
- "XSS 실행 성공으로 해석할 수 있는 증거는 제공되지 않았습니다" -> blocker_count=0
- "본 보고서에서 주장하지 않았습니다" 문맥 -> blocker_count=0
- "로그인 성공 가능성을 시사" -> warning 유지
- "SQLi 성공을 암시" -> warning 또는 blocker 유지
- recommended_actions의 "브라우저 XSS 실행 여부 확인" -> blocker_count=0
```

기존 blocker 테스트는 유지한다.

```text
- "SQL injection 성공으로 DB 결과가 반환됐다" -> blocker
- "브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다" -> blocker
- "config 파일 내용이 반환됐다" -> blocker
```

## 7. 검증 계획

코드 변경 후 실행:

```bash
python3 -m py_compile scripts/check_stage2_report_quality.py
python3 -m pytest tests/test_stage2_report_quality.py
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

샘플 lint 재확인:

```bash
python3 scripts/check_stage2_report_quality.py \
  --input lab/05-03_H세트R4_산출물/reports/openai-h_r4-check_stage2_report.json \
  --pretty

python3 scripts/check_stage2_report_quality.py \
  --input lab/04-30_E세트R2B_산출물/reports/openai-e_r2b-check_stage2_report.json \
  --pretty
```

전체 batch는 선택 실행:

```bash
mkdir -p /tmp/stage2_quality_lint
for f in $(find lab -path "*reports*" -name "*stage2_report.json" | sort); do
  safe_name=$(echo "$f" | sed 's#[/ ]#_#g')
  python3 scripts/check_stage2_report_quality.py \
    --input "$f" \
    --output "/tmp/stage2_quality_lint/${safe_name}.json" \
    > "/tmp/stage2_quality_lint/${safe_name}.txt"
done
```

## 8. 성공 기준

```text
- 최신 H/E actual reports: blocker_count=0 유지
- safe negation blocker 대부분 제거
- 실제 강한 단정 표현은 여전히 blocker 또는 warning으로 잡힘
- 테스트 통과
- 기존 prepare/stage regression 통과
- 기본 모드는 warning-only exit 0 유지
```

## 9. 하지 않을 것

이번 튜닝에서 하지 않을 것:

```text
- 과거 report JSON 재작성
- Stage2 reporter 수정
- Stage2 prompt 추가 수정
- expected fixture 수정
- lint를 CI fail gate로 승격
- LLM judge 도입
- Markdown parser 도입
```

## 10. 다음 작업

이 문서 작성 후 다음 작업은 Codex에 lint 튜닝을 맡기는 것이다.

문서 전용 커밋 후보:

```text
docs: plan Stage2 report quality lint tuning
```

코드 커밋 후보:

```text
refactor: tune Stage2 report quality lint
```
