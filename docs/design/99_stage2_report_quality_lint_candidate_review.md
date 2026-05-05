# 99_stage2_report_quality_lint_candidate_review

- 문서 상태: Stage2 report quality lint 후보 검토
- 기준 시점: 2026-05-05
- 목적: Stage2 실제 LLM 보고서(JSON/Markdown)에서 Apache logs-only 위반 가능 표현을 자동 탐지하는 QA lint 도구를 도입할지 검토하고, 초기 구현 범위와 금지 범위, 검증 기준을 정한다.

관련 문서:

- [99_stage2_prompt_compaction_plan.md](./99_stage2_prompt_compaction_plan.md)
- [99_prepare_shared_attack_policy_boundary_review.md](./99_prepare_shared_attack_policy_boundary_review.md)
- [99_prepare_hints_split_summary.md](./99_prepare_hints_split_summary.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_file_disclosure_verdict_taxonomy_검토.md](./99_file_disclosure_verdict_taxonomy_검토.md)
- [../reviews/99_post_refactor_dry_run_spot_check.md](../reviews/99_post_refactor_dry_run_spot_check.md)
- [../reviews/99_post_refactor_LLM_output_spot_check.md](../reviews/99_post_refactor_LLM_output_spot_check.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

Stage2 report quality lint는 도입 후보로 적절하다.

다만 초기에는 production gate가 아니라 **warning-only review tool**로 시작한다.

이유:

```text
- 실제 LLM 출력은 prompt guard만으로 완전히 보장하기 어렵다.
- Apache logs-only 위반 가능 문구를 자동으로 빠르게 찾는 보조 도구가 유용하다.
- 하지만 regex 기반 lint는 false positive/false negative가 생길 수 있다.
- 따라서 초기 버전은 fail gate가 아니라 사람이 검토할 warning을 만드는 용도로 둔다.
```

권장 신규 스크립트 후보:

```text
scripts/check_stage2_report_quality.py
```

권장 테스트 후보:

```text
tests/test_stage2_report_quality.py
```

공유된 prototype 스크립트는 아래 방향으로 재정리한다.

```text
- run_qa_check_production_v4.py는 production checker라기보다 prototype으로 간주
- 점수형 PASS/FAIL보다 blocker/warning/info 구조를 우선
- Stage2 report JSON 전체 field를 path 기반으로 검사
- 처음에는 warning-only mode로 동작
```

## 2. 현재 prototype 평가

공유된 prototype의 장점:

```text
- ASSERT_PATTERN / DEF_PATTERN으로 단정 표현과 보수 표현을 구분하려는 방향이 좋음
- --debug로 개별 가점/감점 history를 볼 수 있음
- notable_incidents 단위로 빠르게 볼 수 있음
- strict/normal/lenient weight를 둔 점은 운영 모드 확장에 유리함
```

보완할 점:

```text
- report가 null이면 data.get("report", {}) 이후 .get 호출에서 에러 가능
- 실제 파일 저장 로직이 없는데 "Results saved"라고 출력함
- notable_incidents만 검사하면 overall_assessment, executive_summary, key_findings, notable_source_ips, noise_interpretation 등을 놓침
- ASSERT_PATTERN이 실제 위험 표현을 충분히 포괄하지 못함
- 점수형 PASS/FAIL은 품질 보증처럼 오해될 수 있음
- regex만으로 문맥 부정 표현을 완벽히 판단하기 어려움
```

따라서 초기 구현은 다음 설계로 제한한다.

```text
- JSON 전체 주요 text field를 검사
- blocker/warning/info로 분류
- 기본 exit code는 0
- --strict 또는 --fail-on-blocker에서만 non-zero exit 검토
- Markdown은 2차 지원으로 둠
```

## 3. lint 대상 파일

1차 대상:

```text
*_stage2_report.json
```

선택 대상:

```text
*_stage2_report.md
```

초기 구현은 JSON을 우선한다. 이유는 path 기반으로 위치를 특정할 수 있기 때문이다.

입력 예시:

```bash
python3 scripts/check_stage2_report_quality.py \
  --input lab/.../reports/openai-e_r2b-check_stage2_report.json \
  --mode warning \
  --pretty
```

## 4. 검사할 JSON field 후보

아래 field는 우선 검사한다.

```text
report.report_title
report.overall_assessment
report.executive_summary[]
report.key_findings[].title
report.key_findings[].detail
report.notable_incidents[].why_it_matters
report.notable_source_ips[].reason
report.noise_interpretation
report.recommended_actions[].action
report.recommended_actions[].why
report.confidence_and_limitations
report.presentation_takeaway
```

Stage1 raw output도 선택적으로 검사할 수 있다.

```text
report_input.top_incidents[].reasoning_summary
stage1_results.results[].reasoning_summary
stage1_results.results[].raw_output_text
```

하지만 초기 스크립트는 Stage2 report JSON 하나만 받아 검사한다.

## 5. rule 분류

### 5.1 blocker 후보

Blocker는 Apache logs-only 원칙에 직접 위배될 가능성이 큰 표현이다.

예시:

```text
SQLi 성공
DB 결과 반환
인증 우회 성공
데이터 탈취 성공
XSS 실행
브라우저에서 실행
쿠키 탈취
세션 탈취
외부 전송 성공
파일 내용 노출
PHP source 노출 성공
.env 내용 유출
server-status 노출 성공
backup 다운로드 성공
path traversal 성공
파일 읽기 성공
command execution 성공
shell access 획득
server compromise confirmed
WordPress 존재 확정
실제 crawler 확인
site structure 확인
product/category page 존재 확정
```

단, 주변 문맥에 아래 같은 부정/제한 표현이 있으면 blocker가 아니라 warning/info로 낮춘다.

```text
단정하지 않는다
확인되지 않았다
근거가 부족하다
확정할 수 없다
가능성만 있다
시도 정황
관찰된 패턴
context-only
```

### 5.2 warning 후보

Warning은 직접 위반은 아니지만 더 보수적으로 바꾸는 것이 좋은 표현이다.

예시:

```text
파일/소스 공개 시도
외부에서 접근
공격자 IP
실제 공격
스캐너가 사이트를 훑음
크롤러가 확인됨
차단 성공
노출 실패
```

설명:

```text
- "파일/소스 공개 시도"는 대체로 허용 가능하지만, "파일/소스 공개를 노린 것으로 보이는 요청 패턴"이 더 안전할 수 있음
- "외부에서 접근"은 known asset IP가 섞인 경우 "출발지 IP에서"가 더 안전함
- "공격자 IP"는 IP attribution 단정 위험이 있음
```

### 5.3 info 후보

Info는 품질 개선 또는 가독성 개선 신호다.

예시:

```text
근거 수치 부족
recommended_actions가 너무 일반적
key_findings에 context-only만 있음
known_asset IP인데 caution 문구 부족
filtered_out_breakdown이 있는데 후보 밖 문맥 설명 없음
```

## 6. Apache logs-only rule groups

초기 lint rule group은 아래로 둔다.

```text
sql_success_assertion
xss_execution_assertion
file_disclosure_success_assertion
traversal_cmdi_success_assertion
auth_success_assertion
method_protocol_success_assertion
static_crawler_presence_assertion
ip_ua_attribution_assertion
context_only_escalation
known_asset_caution_missing
```

각 group은 처음에는 regex 기반 warning/blocker 후보로만 동작한다.

## 7. 출력 형식

권장 JSON 출력:

```json
{
  "verdict": "WARN",
  "blockers": [],
  "warnings": [
    {
      "rule": "file_disclosure_success_assertion",
      "path": "report.key_findings[0].detail",
      "excerpt": "...",
      "suggestion": "성공/노출 단정이 아니라 시도/관찰 패턴으로 표현"
    }
  ],
  "info": [],
  "summary": {
    "checked_fields": 0,
    "blocker_count": 0,
    "warning_count": 0,
    "info_count": 0
  }
}
```

CLI 출력은 사람이 읽기 쉬운 축약본으로 둔다.

```text
[WARN] report.key_findings[0].detail file_disclosure_success_assertion
[INFO] checked_fields=24 blocker=0 warning=1 info=2
```

## 8. exit code 정책

초기 기본값:

```text
- blocker 있음: exit 0, verdict=FAIL 또는 WARN으로 출력만 함
- warning 있음: exit 0
- info만 있음: exit 0
```

옵션:

```text
--fail-on-blocker
```

이 옵션이 있을 때만 blocker가 있으면 non-zero exit code를 반환한다.

이유:

```text
- 초기 regex lint는 오탐 가능성이 있음
- CI fail gate로 바로 쓰면 정상 보고서도 막을 수 있음
- 먼저 review assistant 역할로 안정화한다.
```

## 9. 구현 범위

1차 구현 허용:

```text
- scripts/check_stage2_report_quality.py 생성
- JSON field traversal helper 작성
- block/warning/info regex rule 작성
- negation/context window 처리
- --input, --pretty, --debug, --fail-on-blocker 옵션
- stdout 요약 출력
- JSON 결과 파일 저장 옵션은 선택
```

1차 구현 금지:

```text
- Stage2 reporter 수정
- Stage2 output schema 수정
- expected fixture 수정
- regression expected 수정
- 실제 LLM 호출
- 복잡한 NLP/LLM 기반 judge 추가
- fail-on-warning 기본값 적용
```

## 10. 테스트 계획

권장 테스트 파일:

```text
tests/test_stage2_report_quality.py
```

테스트 케이스:

```text
- report=null이어도 에러 없이 처리
- 안전한 부정 표현: "파일 내용 노출은 확인되지 않았다"는 blocker가 아님
- 위험 단정 표현: "파일 내용이 노출됐다"는 blocker 후보
- XSS: "쿠키가 탈취됐다"는 blocker 후보
- SQLi: "DB rows returned" 또는 "DB 결과가 반환됐다"는 blocker 후보
- known asset IP인데 "공격자 IP" 표현이 있으면 warning
- notable_incidents 외 key_findings / overall_assessment도 검사
- --fail-on-blocker일 때만 exit code non-zero
```

## 11. 검증 계획

스크립트 추가 후 실행:

```bash
python3 -m py_compile scripts/check_stage2_report_quality.py
python3 -m pytest tests/test_stage2_report_quality.py
```

기존 회귀 검증:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

샘플 확인:

```bash
python3 scripts/check_stage2_report_quality.py \
  --input lab/05-03_H세트R4_산출물/reports/openai-h_r4-check_stage2_report.json \
  --pretty

python3 scripts/check_stage2_report_quality.py \
  --input lab/04-30_E세트R2B_산출물/reports/openai-e_r2b-check_stage2_report.json \
  --pretty
```

## 12. 성공 기준

```text
- safe reports에서 blocker가 과도하게 나오지 않음
- 명백한 성공/유출/실행 단정 표현을 blocker 후보로 잡음
- report=null dry-run JSON을 안전하게 처리함
- notable_incidents뿐 아니라 key_findings, overall_assessment도 검사함
- 기본 모드에서는 CI를 깨지 않음
- --fail-on-blocker 모드에서만 blocker를 exit code로 반영함
```

## 13. 현재 결론

QA lint 도구는 도입 가치가 있다.

다만 현재 공유된 prototype은 바로 production gate로 쓰기보다, 아래 형태로 재작성하는 것이 적절하다.

```text
scripts/check_stage2_report_quality.py
warning-only JSON report quality lint
```

다음 작업은 Codex에 prototype을 참고하게 하되, 새 스크립트와 테스트를 1차 구현하게 하는 것이다.

문서 전용 커밋 후보:

```text
docs: review Stage2 report quality lint candidate
```

코드 커밋 후보:

```text
feat: add Stage2 report quality lint
```
