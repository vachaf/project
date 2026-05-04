# scripts/

## 목적

`scripts/`는 회귀 검증, 요약, 보조 점검 스크립트를 두는 폴더다.

주요 목적은 코드 변경 후 prepare / stage dry-run 결과가 기대 구조를 유지하는지 확인하는 것이다.

## 주요 검증 명령

```bash
python3 scripts/check_prepare_regression.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py
python3 scripts/check_stage_dryrun_regression.py --strict
```

## 관리 원칙

- regression check, dry-run check, 요약 helper처럼 개발/검증 보조 스크립트를 둔다.
- cleanup_outputs.py: output retention policy 기준의 list-only cleanup candidate inventory. 삭제 기능 없음, `--apply` 미구현.
- 파이프라인 본체 코드는 `src/`에 둔다.
- 실험 산출물은 `lab/`에 둔다.
- expected fixture와 실제 출력의 차이는 코드 변경 의도와 함께 검토한다.

## 관련 문서

- 현재 상태: `../docs/진행상황.md`
- prepare regression 설계: `../docs/design/99_prepare_regression_fixture_설계.md`
- stage dry-run regression 설계: `../docs/design/99_stage_dryrun_regression_설계.md`
