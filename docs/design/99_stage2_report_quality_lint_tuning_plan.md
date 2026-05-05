# 99_stage2_report_quality_lint_tuning_plan

- 문서 상태: Stage2 report quality lint tuning 완료 기록
- 기준 시점: 2026-05-05
- 기준 커밋: `4ee38b1966d226b0c6257c22dc704d2afedb92cc`
- 목적: `scripts/check_stage2_report_quality.py`의 blocker 과잉탐지를 완화하고 warning-only review tool로 안정화한 결과를 기록한다.

관련 문서:

- [99_stage2_report_quality_lint_candidate_review.md](./99_stage2_report_quality_lint_candidate_review.md)
- [99_stage2_prompt_compaction_plan.md](./99_stage2_prompt_compaction_plan.md)
- [../reviews/99_post_refactor_dry_run_spot_check.md](../reviews/99_post_refactor_dry_run_spot_check.md)
- [../reviews/99_post_refactor_LLM_output_spot_check.md](../reviews/99_post_refactor_LLM_output_spot_check.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 완료 결론

Stage2 report quality lint 1차 튜닝은 완료했다.

수정 파일:

```text
scripts/check_stage2_report_quality.py
tests/test_stage2_report_quality.py
```

이번 튜닝의 목적:

```text
- safe negation 문맥을 blocker로 과잉탐지하지 않음
- strong negation과 weak conservative context를 분리
- recommended_actions의 “확인 필요” 계열 표현을 blocker로 과잉탐지하지 않음
- 최신 actual LLM report의 안전한 보수 표현은 PASS로 평가
- 실제 강한 성공 단정 표현은 blocker 또는 warning 후보로 계속 포착
```

이번 작업에서도 아래 원칙은 유지했다.

```text
- warning-only review tool 성격 유지
- 기본 exit code 0 유지
- --fail-on-blocker 옵션에서만 blocker_count > 0일 때 non-zero 가능
- Stage2 reporter 수정 없음
- Stage2 prompt/schema 수정 없음
- tests/expected 수정 없음
- tests/fixtures 수정 없음
- prepare/stage regression 의미 변경 없음
```

## 2. 적용 내용

### 2.1 strong / weak context 분리

추가/정리한 개념:

```text
STRONG_NEGATION_PATTERNS
WEAK_CONSERVATIVE_PATTERNS
classify_assertion_context(text, start, end)
```

새 분류:

```text
strong_negation
weak_conservative
none
```

적용한 severity 강등 정책:

```text
blocker + strong_negation -> info
blocker + weak_conservative -> warning
warning + strong_negation -> info
warning + weak_conservative -> info
none -> 기존 severity 유지
```

예상 효과:

```text
- “파일 내용 노출 성공은 확인할 수 없습니다”는 info로 낮춤
- “로그인 성공은 확인되지 않았습니다”는 info로 낮춤
- “침해 성공으로 볼 근거는 부족합니다”는 info로 낮춤
- “로그인 성공 가능성을 시사”는 warning으로 유지
- “SQL injection 성공으로 DB 결과가 반환됐다”는 blocker로 유지
```

### 2.2 recommended_actions 완화

`report.recommended_actions[*].action` / `report.recommended_actions[*].why` 경로에서는 확인/검증 조치 문구가 자주 나온다.

추가한 safe action context:

```text
확인 필요
검증 필요
추가 확인
추가 분석
상관분석
교차 검증
원시 로그
raw log
애플리케이션 로그
WAF 로그
네트워크 추적
모니터링
```

정책:

```text
- recommended_actions에서 safe action 또는 strong negation 문맥이면 blocker를 info 또는 warning으로 낮춤
- “데이터 탈취 성공”, “명령 실행 성공”, “파일 내용이 반환”처럼 명백한 단정은 warning 이상으로 유지
```

### 2.3 테스트 보강

추가/확인한 테스트 범위:

```text
- report=null 처리
- 안전한 auth negation
- 안전한 account takeover negation
- 안전한 file disclosure negation
- 안전한 XSS negation
- “본 보고서에서 주장하지 않았습니다” 문맥
- weak possibility remains warning
- file disclosure blocker
- XSS blocker
- SQLi blocker
- IP attribution warning
- key_findings.detail path 검사
- recommended action check should not be blocker
- --fail-on-blocker exit code
```

검증 결과:

```text
python3 -m pytest tests/test_stage2_report_quality.py: 14 passed
```

## 3. 검증 결과

기준 커밋 `4ee38b1966d226b0c6257c22dc704d2afedb92cc`에서 아래 검증을 통과했다.

```text
python3 -m py_compile scripts/check_stage2_report_quality.py: 통과
python3 -m pytest tests/test_stage2_report_quality.py: 14 passed
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

수정하지 않은 영역:

```text
src/llm_stage2_reporter.py
src/llm_stage1_classifier.py
src/prepare_llm_input.py
src/prepare/*.py
tests/expected/*
tests/fixtures/*
Stage2 output schema
stage dry-run expected
prepare regression fixture
```

## 4. 샘플 lint 재확인 결과

### 4.1 H R4 actual LLM report

대상:

```text
lab/05-03_H세트R4_산출물/reports/openai-h_r4-check_stage2_report.json
```

결과:

```text
Verdict: PASS
checked_fields=28
blocker_count=0
warning_count=0
info_count=6
```

의미:

```text
- context-only 보수 표현은 info로 유지
- blocker/warning 없음
- server-status 노출/침해 성공 단정 없음
```

### 4.2 E R2B actual LLM report

대상:

```text
lab/04-30_E세트R2B_산출물/reports/openai-e_r2b-check_stage2_report.json
```

결과:

```text
Verdict: PASS
checked_fields=37
blocker_count=0
warning_count=0
info_count=6
```

의미:

```text
- “파일 내용 노출 성공은 확인할 수 없습니다” 같은 safe negation은 info로 낮아짐
- file disclosure success blocker 없음
- confirmed source/config disclosure 단정 없음
```

## 5. 현재 상태 평가

튜닝 후 상태는 의도에 맞다.

```text
- 최신 actual LLM report 2건은 PASS
- safe negation blocker 과잉탐지는 완화됨
- info signal은 남아 review context로 활용 가능
- 실제 강한 단정 표현은 여전히 blocker/warning 후보로 잡을 수 있음
```

과거 report JSON은 일괄 재작성하지 않는다.

```text
- 과거 보고서는 당시 모델/prompt 기준 산출물로 보존
- 발표/최종 보고서에 재사용할 산출물만 최신 pipeline으로 재생성
- lint는 과거 보고서 품질 회고와 warning/blocker 분포 파악용으로 사용
```

## 6. 남은 후보

현재는 추가 lint 튜닝을 바로 하지 않는다.

보류 후보:

```text
- Markdown parser 도입
- LLM judge 도입
- CI fail gate 승격
- --fail-on-warning 도입
- 과거 report JSON 일괄 재작성
```

향후 추가 튜닝 조건:

```text
- 최신 actual LLM report에서 blocker가 재발
- 실제 unsafe 단정 표현이 PASS로 누락
- warning/info가 너무 많아 review 효율이 떨어짐
- 특정 rule group이 반복적으로 과잉탐지
```

## 7. 다음 작업

현재는 stable 상태로 둔다.

권장:

```text
- 실제 운영/보고 단계에서 반복 wording 문제 관찰
- 필요 시 report lint rule을 소규모로 추가 튜닝
- CI fail gate는 아직 도입하지 않음
```

문서 전용 커밋 후보:

```text
docs: record Stage2 report quality lint tuning
```
