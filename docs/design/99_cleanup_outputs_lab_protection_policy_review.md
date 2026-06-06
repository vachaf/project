# 99 Cleanup Outputs Lab Protection Policy Review

- 문서 상태: design review / cleanup_outputs lab protection policy
- 기준 시점: runner migration 이후
- 적용 범위: `scripts/cleanup_outputs.py`, `tests/test_cleanup_outputs.py`, lab artifact cleanup policy
- 비범위: cleanup_outputs 코드 변경, lab artifact 삭제, `.gitignore` 변경

## 1. 배경

runner code는 `lab/*_set/*.py`에서 `scripts/lab_runners/{set}/`로 이동했다.

이동 후 `lab/*_set/*.py` 실행 code와 generated artifact가 같은 영역에 섞여 있던 문제는 줄었다. 그러나 `lab/`에는 아직 다음 항목이 남아 있다.

- `lab/observability`
- `lab/*_산출물`
- `lab/LLM샘플검증`
- `lab/*_set/README.md`
- `lab/ABCDE_비교실험_요약.md`
- 단일 viewer payload JSON
- ignored/untracked generated artifact

따라서 runner 이동만으로 `lab` 전체를 cleanup candidate로 바꿀 수 없다. runner migration과 lab artifact cleanup은 별도 정책과 PR로 분리한다.

## 2. 현재 cleanup_outputs 정책

`scripts/cleanup_outputs.py`는 list-only prototype이다.

- `--dry-run`은 기본 동작이다.
- `--apply`는 구현되어 있지 않다.
- 실제 삭제는 수행하지 않는다.
- 출력도 cleanup 가능 확정이 아니라 candidate 목록과 보호 목록을 보여주는 용도다.

현재 `PROTECTED_PATHS`에는 다음이 포함된다.

```text
.git
lab
docs
src
tests/fixtures
tests/expected
README.md
scripts/check_prepare_regression.py
scripts/check_stage_dryrun_regression.py
```

현재 보호 동작은 다음과 같다.

- `lab` 또는 `lab/...`는 `DO_NOT_AUTO_DELETE`로 분류된다.
- repo-relative 보호 판정도 있어 scan root가 `lab` 자체여도 child가 보호된다.
- protected path는 하위 탐색도 skip된다.

이 정책의 목적은 cleanup 후보 탐색 중 실험 산출물, docs, source, regression fixture를 오삭제하지 않도록 하는 것이다.

## 3. 테스트 영향

`tests/test_cleanup_outputs.py`에는 lab 보호를 직접 검증하는 테스트가 2개 있다.

- `test_lab_directory_is_protected`: lab directory 보호
- `test_repo_root_lab_child_is_protected_when_root_is_lab`: scan root가 lab일 때 repo-root lab child 보호

runner migration은 이 테스트와 직접 충돌하지 않는다. runner code의 위치가 `scripts/lab_runners/{set}/`로 바뀌었더라도, cleanup policy 관점에서 `lab/`은 아직 legacy artifact와 observability input/output을 포함한다.

현재 cleanup policy 변경 없이 이 테스트는 유효하다. lab artifact removal policy가 확정되기 전에는 이 테스트를 바꾸지 않는다.

## 4. lab 하위 구조별 판단

| lab 경로 | 현재 성격 | 판단 | cleanup 후보 여부 | 후속 조치 |
| --- | --- | --- | --- | --- |
| `lab/observability` | observability scenario/catalog/run summary 원본 및 script input/output 구조 | `KEEP_PROTECTED` | 지금 cleanup 후보 아님 | 후속 `lab/observability` 경로 정책 검토 필요 |
| `lab/*_산출물` | A~H legacy experiment artifact, reports, processed JSON, runner logs | `KEEP_PROTECTED_TEMPORARILY` | docs/fixture 의존성 확인 후 cleanup 후보 | 후속 PR에서 untrack/remove 검토 |
| `lab/LLM샘플검증` | LLM sample validation legacy review source | `KEEP_PROTECTED_TEMPORARILY` | docs summary와 대체 관계 확인 후 판단 | review summary 의존성 확인 |
| `lab/*_set/README.md` | runner 이동 후 legacy set note | `KEEP_PROTECTED_TEMPORARILY` | 지금 cleanup 후보 아님 | docs/experiments로 흡수 여부 후속 검토 |
| `lab/ABCDE_비교실험_요약.md` | A~E/A~H historical summary | `KEEP_PROTECTED_TEMPORARILY` | docs summary와 중복 여부 확인 후 archive/remove 검토 | historical source 유지 여부 판단 |
| 단일 viewer payload JSON | sample fixture 가능성 있음 | `NEEDS_REVIEW` | 판단 전 cleanup 후보 아님 | fixture 사용 여부 확인 |
| untracked/ignored generated artifact | `.gitignore` 대상이거나 git tracking 밖 생성물 | `IGNORE_REMOVE_CANDIDATE` | cleanup 후보 가능 | tracked 여부와 재현성 의존성 분리 |
| `__pycache__`, `.pyc` | Python cache | `DELETE_CANDIDATE` | cleanup 후보 | tracked 아님 |

## 5. 정책 전략 비교

| 전략 | 장점 | 단점 | 현재 판단 |
| --- | --- | --- | --- |
| A. `lab` 전체 보호 유지 | 현재 tests와 retention 정책에 부합한다. 오삭제 위험이 가장 낮다. | cleanup script가 `lab/*_산출물` 후보를 세분화하지 못한다. | 현재 단계에서 안전 |
| B. `lab/observability`와 selected `.md`만 보호하고 `lab/*_산출물`은 cleanup candidate로 전환 | artifact cleanup 후보를 script가 직접 식별할 수 있다. | fixture 후보와 historical artifact를 누락하거나 오분류할 위험이 크다. | 아직 이르다 |
| C. `lab` 전체 보호 유지 + 별도 tracked artifact 제거 PR 진행 | cleanup script 안전성을 유지하면서 artifact 정리를 git 단위로 명확히 처리할 수 있다. | cleanup_outputs policy 개선은 뒤로 밀린다. | 권장 |
| D. cleanup policy 보류 + `.gitignore` / `git rm --cached` 별도 수행 | tracked/untracked 문제를 정확히 분리할 수 있다. | ignore 패턴과 보존 기준을 별도로 설계해야 한다. | PR 4C-4 후보 |
| E. lab 전체 제거 전까지 cleanup_outputs 미변경 | 가장 보수적이며 기존 테스트 안정성이 높다. | cleanup_outputs가 lab 정리에 관여하지 않는다. | 현재 단계에 적합 |

현재 단계에서는 A, C, E 조합이 안전하다. B는 아직 이르다. D는 PR 4C-4 후보로 남긴다.

## 6. .gitignore / tracked artifact 관계

`.gitignore`에는 이미 일부 lab generated artifact 패턴이 있다.

예시는 다음이다.

```text
/lab/**/raw/
/lab/**/*noise_summary.json
/lab/**/*stage1_errors.json
/lab/**/*analysis_candidates.json
/lab/**/*llm_input.json
/lab/**/*stage2_report_input.json
lab/observability/runs/**/*
```

그러나 tracked 파일에는 `.gitignore`가 소급 적용되지 않는다. 따라서 tracked `lab/*_산출물` JSON/JSONL/Markdown은 별도 `git rm --cached` 또는 remove 판단이 필요하다.

정리 기준은 다음이다.

- cleanup_outputs 정책 변경과 `.gitignore`/untrack 변경을 같은 PR에 묶지 않는다.
- JSON/JSONL/log artifact는 docs/fixture 의존성 확인 후 별도 처리한다.
- 공개 repo에 남기지 않을 generated artifact라면 `git rm --cached`가 실제 삭제보다 보수적인 선택일 수 있다.
- historical comparison artifact와 docs summary 대체 관계가 분명해진 뒤 remove 여부를 판단한다.

## 7. 권장 후속 PR 순서

PR 4C-3B:

- cleanup_outputs protected path 변경 여부 최종 결정
- 변경한다면 `tests/test_cleanup_outputs.py` 갱신
- `python3 -m pytest -q tests/test_cleanup_outputs.py` 실행

PR 4C-4:

- lab artifact JSON/JSONL/log untrack/remove 후보 처리
- `.gitignore` 정리
- tracked artifact와 ignored artifact 분리

PR 4C-5:

- `lab/observability` 경로 정책 별도 검토
- observability scripts 기본 input/output 경로 변경 여부 판단

## 8. 최종 결론

```text
현재는 cleanup_outputs의 lab 전체 보호 정책을 유지한다.
cleanup_outputs는 list-only prototype이고, lab/observability와 legacy lab artifacts가 남아 있으므로
runner migration 직후 lab 보호를 풀지 않는다.
artifact untrack/remove, .gitignore 정리, cleanup policy 변경은 별도 PR로 분리한다.
```
