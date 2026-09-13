# Live Selected Logs UX v1 구현 보고

## 기준 commit / branch / worktree

- 기준 commit: `d2455418f756b198e5d530712fc7008f18845685`
- branch: `live-selected-logs-ux-v1`
- worktree: `/home/user/worktrees/live-selected-logs-ux-v1`
- 작업 범위: Live template/JavaScript/CSS와 UX contract test만 변경

## 변경 요약

- 각 Live row에 분석 입력용 checkbox를 추가하고 기존 detail-row click/keyboard 동작과 분리했다.
- session-memory의 ordered selection과 `선택 N / 50건`, clear/submit controls를 추가했다.
- filter, pagination, manual/auto refresh 후에도 selection을 유지한다. browser hard reload에서는 초기화되고 storage API를 쓰지 않는다.
- `POST /api/live/jobs/create` 호출과 PENDING, partial missing, duplicate, NO_DATA, 400/503/500/network response UX를 추가했다.
- submit 동안 checkbox, filter, pager, manual refresh, auto-refresh toggle/tick, clear와 중복 submit을 잠근다.
- PENDING 성공에서만 active selection을 clear하고, 강제 redirect 없이 `/job/{id}` primary link를 제공한다.
- 공격 성공·침해·위험도 확정으로 오해하지 않도록 exact-ID input boundary 문구와 neutral feedback을 사용한다.

## UX contract 구현 결과

selection authority는 `state.selectedOrder` 배열이다. 최초 선택 순서대로 append하고 deselect 시 해당 ID만 제거하므로 deselect/reselect된 ID는 마지막 순서로 이동한다. snapshot/filter/pager handlers는 이 배열을 교체하지 않는다. `localStorage`와 `sessionStorage`는 사용하지 않는다.

submit은 배열의 copy를 `selected_log_ids`로 전송한다. response에 포함된 `job_id`/`existing_job_id`만 Job link에 사용하며 UI-side diagnostic/request ID를 생성하지 않는다. 기존 Live row의 Request ID 표시는 snapshot backend가 제공하는 raw-log field이므로 유지했다.

## acceptance 항목별 PASS/보류/근거

| # | 항목 | 결과 | 근거 |
| --- | --- | --- | --- |
| 1 | checkbox/detail interaction | PASS | checkbox click/keydown propagation 차단, row click target guard, 기존 Enter/Space detail 동작 보존 |
| 2 | max-50 / zero disabled / backend 400 | PASS | constant 50, 50건에서 unselected checkbox disable, zero clear/submit disable, neutral 400 branch |
| 3 | ordered selection | PASS | ordered array append/filter/copy; deselect/reselect는 append-at-end로 고정 |
| 4 | cross-page/filter persistence | PASS | snapshot/filter/pager에서 ordered selection 미초기화, visible checkbox만 current items에서 render |
| 5 | auto-refresh persistence/lock | PASS | auto tick은 selection 미변경, submitting guard와 disabled toggle 적용 |
| 6 | submit locking | PASS | form controls, checkbox, pager, manual/auto refresh, clear/submit lock; success-only clear |
| 7 | PENDING | PASS | POST 처리, neutral success, no location redirect, backend job ID link |
| 8 | partial missing | PASS | job success와 별도 neutral missing count; export 완료 단정 없음 |
| 9 | duplicate 409 | PASS | 진행 중 동일 작업 안내, backend existing job link, selection 유지 |
| 10 | NO_DATA | PASS | job 미생성 안내, neutral wording, selection 유지 |
| 11 | 400/503/500/network | PASS | status별 neutral feedback, selection 유지, client-generated request ID 없음 |
| 12 | forbidden certainty wording | PASS | exact-ID input boundary 문구; 금지 확정/차단 표현 test |
| 13 | existing Live observation regression | PASS | snapshot/raw detail/filter/pager/status color/observation route-service tests 통과 |

실제 browser click 및 runtime job 생성 E2E는 migration과 UX가 모두 승인되기 전까지 HOLD이므로 이 보고서의 PASS는 route/service 및 static UX contract test 기준이다.

## 실행한 테스트와 결과

```text
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 \
  /tmp/live-selected-input-clean-venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_live_selected_input_v1.py \
  tests/test_live_log_repository.py \
  tests/test_live_log_service.py \
  tests/test_live_security_observation.py \
  tests/test_web_live_routes.py \
  tests/test_live_selected_logs_ux.py

73 passed in 2.24s
```

신규 UX와 기존 route focused run은 `14 passed in 1.51s`였다. 신규 Python test의 `py_compile`과 `git diff --check`도 PASS했다. 전체 pytest는 실행하지 않았다.

## 변경 파일 목록

- `web/templates/live_dashboard.html`
- `web/static/live-monitoring.js`
- `web/static/live-monitoring.css`
- `tests/test_live_selected_logs_ux.py`
- `docs/reports/live-selected-logs-ux-v1-implementation-2026-09-13.md`

## backend contract/exporter/repository semantics 미변경 확인

기준 commit과 비교해 `web/routes`, `web/services`, `src`, `docs/operations/sql`에는 diff가 없다. 따라서 backend selected-input contract, repository duplicate semantics, exact-ID exporter semantics, migration SQL은 변경하지 않았다.

## /opt/web_log_analysis 미접근/미수정 확인

`/opt/web_log_analysis`를 command workdir 또는 source path로 사용하지 않았고 해당 dirty worktree를 수정하지 않았다. 모든 작업은 별도 worktree에서 수행했다.

## 남은 DB migration HOLD 항목

DB migration SQL은 실행하지 않았고 DB DDL/DML도 실행하지 않았다. migration 적용, physical child constraint 확인, deployed APP least-privilege grant 확인은 별도 승인 gate로 남는다.

## E2E HOLD 상태

runtime E2E는 시작하지 않았다. migration과 UX branch가 각각 검토·PASS된 후에만 Live selection부터 viewer까지의 controlled E2E 및 same-time unselected-row exclusion 증거를 수행해야 한다.
