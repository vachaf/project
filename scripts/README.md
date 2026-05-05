# scripts/

## 목적

`scripts/`는 회귀 검증, 요약, 보조 점검 스크립트를 두는 폴더다.

주요 목적은 코드 변경 후 prepare / stage dry-run 결과가 기대 구조를 유지하는지 확인하고, Stage2 실제 보고서의 Apache logs-only wording risk를 review-only 방식으로 점검하는 것이다.

## 주요 검증 명령

```bash
python3 scripts/check_prepare_regression.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py
python3 scripts/check_stage_dryrun_regression.py --strict
python3 scripts/check_stage2_report_quality.py --input path/to/stage2_report.json --pretty
python3 -m pytest tests/test_stage2_report_quality.py
```

## 주요 스크립트

- `check_prepare_regression.py`
  - prepare output key, candidate 보존, filtered/context-only 구조를 fixture 기준으로 검증한다.
- `check_stage_dryrun_regression.py`
  - prepare -> stage1 dry-run -> stage2 dry-run 구조가 기대 schema와 policy를 유지하는지 검증한다.
- `check_stage2_report_quality.py`
  - Stage2 report JSON의 성공/침해/유출/실행 단정 wording risk를 Apache logs-only 기준으로 점검한다.
  - 기본 모드는 warning-only이며 exit code 0을 유지한다.
  - `--fail-on-blocker`를 지정한 경우에만 blocker가 있을 때 non-zero exit을 사용할 수 있다.
  - `--pretty`는 결과 JSON을 보기 좋게 stdout에 출력한다.
  - `--output`이 있을 때만 결과 JSON 파일을 저장한다.
  - strong negation과 weak conservative context를 구분해 safe negation blocker 과잉탐지를 줄인다.
- `cleanup_outputs.py`
  - output retention policy 기준의 list-only cleanup candidate inventory를 만든다.
  - 삭제 기능 없음, `--apply` 미구현.

## 현재 검증 기준

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
Stage2 report quality lint tests: 14 passed
```

최신 H R4 / E R2B actual report quality lint 기준:

```text
blocker_count=0
warning_count=0
info_count=6
verdict=PASS
```

## 관리 원칙

- regression check, dry-run check, 요약 helper처럼 개발/검증 보조 스크립트를 둔다.
- Stage2 report quality lint는 공격 성공 여부를 판정하는 도구가 아니라 wording review 도구다.
- warning은 사람이 검토해야 하는 후보이지 자동 실패가 아니다.
- `--fail-on-blocker`는 수동 확인 후 제한적으로 사용한다.
- 파이프라인 본체 코드는 `src/`에 둔다.
- 실험 산출물은 `lab/`에 둔다.
- expected fixture와 실제 출력의 차이는 코드 변경 의도와 함께 검토한다.

## 관련 문서

- 현재 상태: `../docs/진행상황.md`
- prepare regression 설계: `../docs/design/99_prepare_regression_fixture_설계.md`
- stage dry-run regression 설계: `../docs/design/99_stage_dryrun_regression_설계.md`
- Stage2 report quality lint 후보 검토: `../docs/design/99_stage2_report_quality_lint_candidate_review.md`
- Stage2 report quality lint tuning: `../docs/design/99_stage2_report_quality_lint_tuning_plan.md`
- Stage2 prompt compaction: `../docs/design/99_stage2_prompt_compaction_plan.md`
