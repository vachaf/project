# 99_pipeline_run_dir_phase1b_phase2_candidate_review

- 기준 시점: 2026-05-09
- 문서 목적: run_dir Phase 1A 구현/스모크 확인 이후 다음 후보(`--run-id`, `--overwrite`, Web UI run_dir scan Phase 2, legacy/lab opt-in scan)의 우선순위와 착수 시점을 비교한다.
- 결론 요약: 현재는 즉시 구현보다 관찰/설계 우선이 적절하다.

## 0. 현재 상태 업데이트 (2026-05-10)

- 본 문서는 Phase 1B/Phase 2 후보 비교를 위해 작성된 당시 기준 문서다.
- 이후 일부 후보는 구현/문서화가 완료되었다.
  - Phase 2A input model review 완료
  - Phase 2B fixture plan 완료
  - Phase 2C test plan + fixture helper/tests 완료
  - Phase 2D run_dir manifest default scan 완료
- 현재 Web UI 기본 scan은 run_dir manifest 기준(`REPORT_GLOBS=["runs/*/manifest.json"]`)이다.
- flat-only output은 분석 산출물로는 유효하지만, 현재 정책상 Web UI 기본 목록 기준은 아니다.
- 기본 운영 흐름은 `run_analysis_pipeline.py --run-dir runs/<run_id>` 사용이다.
- legacy flat/lab glob은 `LEGACY_REPORT_GLOBS`로 보존되며 기본 scan에서는 제외된다.
- 남은 후보(보류): archive opt-in, flat/run_dir dedupe, canonical_report_key, `--run-id`, `--overwrite` 필요성 관찰.
- Web UI read-only invariant는 유지된다.

## 배경

- Phase 1A 완료 상태
  - `--run-dir <path>` opt-in 병행 산출물 생성 구현 완료(커밋 `fd9a692ce1efe5a425691dc25dd2e73d9e40e59c`)
  - operations 반영 완료(커밋 `4e295879ab062d94716ef9b328519bd034b2e2bc`)
  - dry-run smoke 확인 완료: `security_2026-04-30_13-55-00_to_2026-04-30_13-56-00_kst` + `--run-dir /tmp/web-log-analysis-run-dir-smoke-2`
  - smoke 관찰: `pipeline complete`, flat output 유지, run_dir 표준 파일 생성, manifest dual-path(`flat_files`/`run_dir_files`) 기록 확인
- 현재 동작/제약
  - `--run-dir` 미지정 시 기존 flat output만 생성
  - `run_id=Path(run_dir).name`
  - run_dir 기존 경로 충돌 시 fail-fast
  - `--run-id`/`--overwrite` 미구현
  - Web UI loader run_dir scan 미구현
  - legacy/lab opt-in scan 미구현

다음 후보를 바로 구현하지 않는 이유는, Phase 1A의 실제 사용 빈도/불편 지점을 충분히 관찰하기 전에 옵션 조합 복잡도와 UI 회귀 리스크를 먼저 키울 가능성이 크기 때문이다.

## 후보 비교

| 후보 | 목적 | 장점 | 위험/복잡도 | 선행 조건 | 추천 시점 | 현재 판단 |
|---|---|---|---|---|---|---|
| `--run-id <name>` | `run_dir` 경로와 run 식별자 분리 | 반복 실행 추적성 개선, manifest 식별자 명시성 향상 | `--run-dir`와 조합 규칙 정의 필요, auto run_id 충돌 정책 필요, `run_id`/`run_dir` 의미 불일치 위험 | 실제 사용에서 경로 이름 의존이 불편한지 관찰 | Phase 1B 후보 | 보류. `--run-dir` 직접 지정이 불편해질 때 재검토 |
| `--overwrite` | 동일 run_dir 반복 실험 편의 제공 | 반복 smoke/실험 편의성 | 산출물 손실 위험, stale 파일 불일치 위험, cleanup/retention 정책 충돌 가능 | overwrite 정책 합의(A fail-fast 유지 / B 전체 삭제 / C known 파일만 덮어쓰기) | `--run-id` 필요성 확인 이후 | 보류. 현재는 fail-fast 유지가 안전 |
| Web UI loader run_dir scan (Phase 2) | `runs/*/manifest.json` 기반 로딩으로 run_dir 중심 전환 | active/current 구조 전환 기반, run manifest 중심 조회 가능 | flat+run_dir 동시 scan 시 dedupe 필요, report_id/run_id 규칙 필요, list/detail/compare/payload 회귀 위험 | loader/dedupe/scan mode 설계 선행 | Phase 2 핵심 | 추진 후보. 단, 설계 선행 없이는 즉시 구현 비권장 |
| legacy/lab opt-in scan | active runs와 legacy/lab archive 분리 | 기본 UI noise 감소, 운영 산출물과 실험 archive 분리 | 과거 실험 접근성 저하 가능, UI 라벨/필터 기준 필요, 중복/누락 판단 필요 | run_dir scan 설계와 연동된 mode 정책 정리 | Phase 2+ | Web UI run_dir scan과 묶어 검토 |

## 권장 우선순위

```text
P0. Phase 1A run_dir 실제 사용 관찰
P1. --run-id 필요성 판단
P2. --overwrite 정책 판단
P3. Web UI run_dir scan Phase 2 설계
P4. legacy/lab opt-in scan 설계
```

- 현재 권고: 즉시 구현 승격은 하지 않는다.
- 우선 관찰과 설계 합의를 통해 정책 충돌/회귀 위험을 낮춘 뒤 단계적으로 착수한다.

## Non-goals

- 이번 문서는 구현 작업을 수행하지 않는다.
- `--run-id`, `--overwrite`를 추가하지 않는다.
- Web UI loader를 수정하지 않는다.
- legacy/lab 산출물을 이동/삭제하지 않는다.
- 기존 flat output을 제거하지 않는다.
- 분석 로직/보안 판정(severity/category/verdict) 계산을 변경하지 않는다.
- context-only 항목을 finding/incident로 승격하지 않는다.

## 다음 액션

- `--run-dir` 실제 smoke/실험 사용을 추가 관찰해 불편 유형을 수집한다.
- 불편이 확인되면 `--run-id`부터 우선 검토한다.
- `--overwrite`는 손실/불일치 리스크가 커서 가장 늦게 판단한다.
- Web UI Phase 2는 별도 설계 문서에서 loader/dedupe/scan mode를 먼저 정의한다.

## 유지 원칙

- Apache logs-only 원칙 유지
- raw POST body/response body 원문/DB 결과/브라우저 실행 여부 기반 단정 금지
- status_code/text/html/response_body_bytes/route/UA/IP만으로 성공/침해/유출 단정 금지
- context-only 승격 금지
- 새 보안 판정 생성 금지
