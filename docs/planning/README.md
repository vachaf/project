# planning

## 목적

- `planning/`은 후속 작업 계획, TODO, 우선순위, 장기 후보를 둔다.
- 아직 끝나지 않은 설계 후속 작업과 개선 큐를 짧게 추적할 때 사용한다.
- 현재 구조 기준은 [../00_current_architecture.md](../00_current_architecture.md)와 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)를 따른다.

## 현재 후속 작업 기준

- [99_비교실험_후속개선_TODO.md](./99_비교실험_후속개선_TODO.md): 현재 후속 개선 작업, 우선순위, 장기 후보를 보는 anchor 문서
- [99_비교실험_후속개선_history.md](./99_비교실험_후속개선_history.md): TODO에서 분리한 완료 기록 요약

## 해석 기준

- `full_report`는 DB-backed MVP의 direct pipeline mode다.
- `sliding_window / rollup / operator_queue`는 `full_report` 안에 자동 포함되는 단계가 아니라 후속 `windowed_triage` 흐름으로 본다.
- `analysis_jobs` queue는 분석 실행 queue이고, `operator_queue`는 rollup 결과를 사람이 검토하기 위한 queue다.
- Web UI read-only는 보안 결과 해석 read-only를 뜻하며, `analysis_jobs` 등록/조회 같은 제한된 DB-backed MVP write/read와 충돌하지 않는다.
- Apache logs-only evidence boundary를 약화하는 TODO는 현재 기준 문서와 함께 재검토한다.

## 읽는 순서

1. [99_비교실험_후속개선_TODO.md](./99_비교실험_후속개선_TODO.md)
2. 현재 구조 확인은 [../00_current_architecture.md](../00_current_architecture.md)
3. Apache logs-only 경계 확인은 [../00_apache_logs_only_evidence_boundary.md](../00_apache_logs_only_evidence_boundary.md)
4. 완료 이력은 [99_비교실험_후속개선_history.md](./99_비교실험_후속개선_history.md)
5. 관련 설계는 [../design/README.md](../design/README.md)
6. 관련 평가는 [../reviews/README.md](../reviews/README.md)
7. 관련 실험 세트는 [../experiments/README.md](../experiments/README.md)

## 관리 원칙

- 아직 해야 할 일, 우선순위, 장기 후보는 `planning/`에 둔다.
- 완료된 검토 문서는 `reviews/` 또는 별도 archive 후보로 분리한다.
- 구현 설계와 보류 결정은 `design/`에 둔다.
- TODO 본문에서 완료 항목과 남은 항목이 섞여 있으면 README에서는 현재 후속 작업 기준만 강조한다.
