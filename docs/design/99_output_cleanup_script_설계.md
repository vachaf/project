# output cleanup script 설계

- 문서 상태: 설계 문서
- 기준 시점: 2026-05-04
- 목적: 향후 output cleanup script를 구현할 때 따라야 할 설계 원칙, 보호 범위, 안전장치를 먼저 정의한다.

이 문서는 cleanup script 구현 자체가 아니라, 삭제 자동화로 인한 재현성 훼손과 오삭제를 막기 위한 설계 기준을 정리한다.

관련 운영 정책은 [../operations/99_output_retention_policy.md](../operations/99_output_retention_policy.md)를 우선한다.

## 1. 문서 목적

- [../operations/99_output_retention_policy.md](../operations/99_output_retention_policy.md)를 바탕으로 향후 cleanup script를 만들 때 지켜야 할 설계 기준을 정의한다.
- 저장 공간 정리와 재현성 보존 사이의 균형을 명확히 한다.
- 실험 산출물, regression fixture, 문서, reports를 실수로 삭제하지 않도록 하는 안전장치를 정의한다.

이 문서의 범위:

- cleanup script가 무엇을 기본 보호해야 하는지 정리
- 어떤 출력만 제한적으로 cleanup 후보가 될 수 있는지 정리
- dry-run 중심 CLI와 로그 기록 원칙 정리

이 문서의 비범위:

- 실제 파일 삭제
- `lab/` 산출물 이동 또는 정리
- 민감 정보 자동 탐지 또는 자동 삭제

## 2. 기본 원칙

반드시 지킬 원칙:

```text
- 기본 동작은 dry-run
- 실제 삭제는 명시적 --apply 옵션이 있을 때만 수행
- 삭제 후보 목록을 먼저 출력
- 삭제 로그를 남김
- lab/ 정식 산출물은 기본 삭제 대상에서 제외
- docs/는 삭제 대상에서 제외
- tests/fixtures, tests/expected는 삭제 대상에서 제외
- regression과 sample review 재현에 필요한 파일은 삭제하지 않음
- 민감 정보 정리는 별도 검토이며, cleanup script가 자동 판단하지 않음
```

보충 원칙:

- retention 정책은 먼저 보존 기준을 정의하고, cleanup은 가장 마지막에 제한적으로 도입한다.
- 기본 동작은 "삭제"가 아니라 "후보 나열과 검토 지원"이다.
- 파일명 패턴만으로 즉시 삭제 결정을 내리지 않는다.
- 재현 경로를 끊을 수 있는 파일은 보수적으로 보호한다.

## 3. 대상 범위

향후 cleanup script가 다룰 수 있는 후보:

```text
- temporary dry-run output
- 명시적 임시 work-dir 산출물
- 실패 원인 분석 완료 후 남은 raw error dump
- 중복된 stage2 raw error dump
- 문서나 fixture에 반영된 일회성 debug output
```

cleanup script가 기본적으로 다루면 안 되는 대상:

```text
- lab/ 하위 정식 실험 산출물
- docs/
- tests/fixtures/
- tests/expected/
- README류
- scripts/check_*_regression.py
- src/
- pipeline 재현에 필요한 manifest
- sample review에 사용된 Stage1/Stage2 산출물
```

설계 해석:

- 기본 보호 대상은 "삭제 금지"로 본다.
- cleanup candidate는 임시성, 중복성, 원인 분석 종료 여부가 분명한 경우에만 제한적으로 분류한다.
- `lab/`은 장기 보존 및 수동 검토 영역이며 초기 cleanup 범위에 넣지 않는다.

## 4. 권장 CLI 설계

초기 list-only prototype 기준 명령 형태:

```bash
python3 scripts/cleanup_outputs.py --root . --dry-run
python3 scripts/cleanup_outputs.py --root /tmp/stage-dryrun-regression --dry-run
python3 scripts/cleanup_outputs.py --root . --dry-run --json
python3 scripts/cleanup_outputs.py --root . --dry-run --verbose
python3 scripts/cleanup_outputs.py --root . --apply
```

현재 prototype 상태:

- `--dry-run`은 기본 동작이다.
- `--apply`는 NOT IMPLEMENTED로 종료하며 실제 삭제를 수행하지 않는다.
- `--json`은 summary와 entries를 구조화해 출력한다.
- `--verbose`는 REVIEW 항목까지 출력한다.

후속 옵션 후보:

```text
--kind
--older-than-days
--include
--exclude
--write-log
```

CLI 설계 주의:

- `--dry-run`은 기본값이어야 한다.
- `--apply`가 없으면 삭제를 수행하면 안 된다.
- `--include lab` 같은 위험 옵션은 초기 버전에서 제공하지 않는 편이 안전하다.
- 초기 버전의 `--kind`는 `temp-dryrun`처럼 범위를 강하게 제한한 값부터 시작하는 편이 안전하다.
- 실제 삭제 기능을 열기 전에는 repo-root 보호 판정, symlink 처리, `/tmp/stage-dryrun-regression` 후보 분류를 테스트로 고정해야 한다.

## 5. 삭제 후보 판정 기준

예시 등급:

```text
CLEANUP_CANDIDATE:
- /tmp 또는 명시적 temp output
- stage dry-run keep-output 중 문서/fixture 반영 완료된 것
- 실패 원인 분석 완료 후 불필요한 raw error dump

REVIEW:
- reports/raw_error
- stage1_errors
- 중복 processed JSON
- 공개 repo 포함 여부가 애매한 raw export

DO_NOT_DELETE:
- lab 정식 산출물
- docs
- tests/fixtures
- tests/expected
- reports/stage2_report.md
- sample review 근거 파일
- pipeline_manifest.json
```

현재 prototype의 실제 분류:

```text
KEEP
REVIEW
CLEANUP_CANDIDATE
DO_NOT_AUTO_DELETE
```

판정 기준 해석:

- `CLEANUP_CANDIDATE`는 바로 삭제하지 않고 dry-run 목록에 먼저 표시한다.
- `REVIEW`는 자동 삭제가 아니라 사람이 별도 판단해야 하는 영역이다.
- `DO_NOT_AUTO_DELETE`는 초기 버전 cleanup script의 기본 보호 영역이다.

## 6. 안전장치

반드시 포함할 보호 장치:

```text
- 삭제 전 대상 경로, 크기, reason 출력
- allowlist보다 denylist 우선
- path traversal / symlink 안전성 고려
- repo root 밖 경로 삭제 금지
- .git, src, docs, tests, lab 기본 보호
- 삭제 로그 JSONL 또는 Markdown 기록
- --apply 사용 시에도 2단계 확인 또는 explicit flag 검토
```

현재 list-only prototype에 반영된 안전장치:

- 삭제 기능 없음
- `--apply` 미구현 및 exit(1)
- symlink는 `DO_NOT_AUTO_DELETE`
- `lab`, `docs`, `src`, `tests/fixtures`, `tests/expected`, `.git` 보호
- root-relative 보호 판정과 repo-root 기준 보호 판정을 함께 사용
- `/tmp/stage-dryrun-regression` 계열 경로는 cleanup 후보로 분류
- `tmp` / `temp` / `dryrun` 계열은 명시적 segment 또는 prefix 중심으로만 후보 처리
- `template`, `attempt`, `timestamp`, `nondryrun`, `mydryrunfile` 같은 substring 오탐을 테스트로 방지

적용 후보 예:

```text
--apply --confirm-cleanup
```

초기 버전 판단 후보:

- `--apply`만으로 충분한지
- `--apply`와 별도의 `--confirm-cleanup`를 함께 요구할지

현재 설계 방향:

- 초기 list-only 단계에서는 실제 삭제 경로를 열지 않는다.
- `--apply` 지원을 나중에 추가하더라도 symlink, 상대경로, repo 밖 대상, 보호 디렉터리 매칭을 먼저 차단해야 한다.
- allowlist보다 denylist를 우선하는 이유는 초기 버전에서 "보호해야 할 영역"이 더 명확하기 때문이다.

## 7. 출력 형식

dry-run 출력 예시:

```text
[CLEANUP_CANDIDATE] /tmp/stage-dryrun-regression/e_r2_php_wrapper reason=temp dry-run output size=...
[SKIP] lab/04-30_E세트R2B_산출물 reason=protected lab artifact
[SKIP] tests/expected/stage_dryrun_regression/e_r2_php_wrapper.expected.json reason=protected regression expected
```

현재 prototype 출력 원칙:

- summary와 `CLEANUP_CANDIDATE` 목록을 기본 출력한다.
- `--verbose`일 때 REVIEW 항목도 출력한다.
- `--json`일 때 summary와 entries를 JSON으로 출력한다.
- 출력 문구는 `safe to delete` 같은 승인 표현을 쓰지 않고 `candidate only; manual review required`로 제한한다.

JSON output 후보:

- 현재 `--json`은 candidate 목록뿐 아니라 전체 entries를 출력한다.
- 이후 JSONL 로그와 연계 가능하도록 entry 단위를 단순하게 유지한다.

## 8. 구현 순서 제안

기존 설계상 구현 순서:

```text
1. list-only prototype
2. dry-run candidate scanner
3. JSONL log output
4. restricted --kind temp-dryrun only
5. regression or self-test fixture 추가
6. --apply 지원
```

현재 상태:

- 1단계 list-only prototype 완료
- 단위 테스트 15개 추가 완료
- 기존 prepare/stage dry-run regression 통과 유지

이후 권장 순서:

1. 실제 필요 시점에 JSONL log output 검토
2. 실제 필요 시점에 `--kind temp-dryrun` 필터 검토
3. 실제 필요 시점에 `--older-than-days` 필터 검토
4. `--apply`와 실제 삭제 기능은 별도 승인 전까지 보류

## 9. 보류할 것

현재는 하지 않는 것:

```text
- 자동 삭제
- lab/ 산출물 정리
- 민감 정보 자동 탐지
- 공개 repo 정리 자동화
- 오래된 문서 archive 이동 자동화
- Git history rewrite
```

추가 보류 메모:

- `lab/` 정리는 retention 정책과 별도 수동 검토 절차가 있어야 한다.
- 공개 여부 판단과 삭제 여부 판단을 같은 자동화에 섞지 않는다.
- 문서 archive 이동 자동화는 현재 cleanup script 범위에 넣지 않는다.

## 10. 관련 문서 링크

- [../operations/99_output_retention_policy.md](../operations/99_output_retention_policy.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)
- [../operations/06_통합_스크립트_설명_정리본.md](../operations/06_통합_스크립트_설명_정리본.md)
- [../../scripts/README.md](../../scripts/README.md)
- [../../scripts/cleanup_outputs.py](../../scripts/cleanup_outputs.py)
- [../../lab/README.md](../../lab/README.md)

## 11. 다음 단계 제안

현재 list-only prototype은 추가된 상태다.

다음 단계는 실제 삭제 구현이 아니라, 필요 시점에 아래 보강을 검토하는 것이다.

1. JSONL 로그 출력이 필요한지 검토
2. `--kind temp-dryrun` 필터가 필요한지 검토
3. `--older-than-days` 필터가 필요한지 검토

실제 삭제 기능 착수 전 확인 항목:

- `lab/`, `docs/`, `tests/fixtures`, `tests/expected`, `src/`, `.git` 보호 규칙이 테스트로 유지되는가
- sample review와 regression 재현에 필요한 산출물 예시를 더 보강할 필요가 없는가
- `--apply` 외에 추가 확인 플래그가 필요한가
