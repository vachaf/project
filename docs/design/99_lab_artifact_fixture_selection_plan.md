# 99 Lab Artifact Fixture Selection Plan

- 문서 상태: design plan / lab artifact fixture selection
- 기준 시점: runner migration 및 cleanup_outputs lab protection review 이후
- 적용 범위: `lab/*_산출물` 대표 fixture 후보
- 비범위: 실제 fixture 복사/이동, lab artifact 삭제, `.gitignore` 수정, `git rm`

## 1. 목적

이 문서는 `lab/*_산출물` artifact를 정리하기 전에 어떤 대표 샘플을 fixture 또는 docs example로 승격할지 정리한다.

목적은 다음이다.

- lab artifact 제거 전에 보존할 대표 fixture 후보를 확정한다.
- 어떤 파일을 fixture로 승격할지, 어떤 파일은 generated artifact로 untrack/remove 후보가 되는지 판단 기준을 세운다.
- docs 직접 참조를 `tests/fixtures` 또는 `docs/examples` 경로로 대체하기 위한 선행 계획을 만든다.

이번 단계에서는 파일을 복사, 이동, 삭제하지 않는다. `git rm`, `git rm --cached`, `.gitignore` 수정도 하지 않는다.

## 2. 배경

runner code는 `lab/*_set/*.py`에서 `scripts/lab_runners/{set}/`로 이동했다. 따라서 `lab/*_산출물`은 더 이상 runner code 위치가 아니라 legacy/generated experiment artifact 위치로 보는 것이 맞다.

최근 조사 기준은 다음이다.

- tracked `lab/**` 파일은 총 256개다.
- `lab/*_산출물`은 총 210개 tracked 파일이다.
- 대표 후보 범위의 tracked 파일은 JSON 47개, JSONL 5개, Markdown 34개다.
- `lab/observability`는 아직 scripts 기본 input/output 구조와 연결되어 있어 별도 보호 대상이다.
- E R2B와 H R4 `stage2_report.json`은 일부 design 문서에서 직접 참조 중이다.
- tests가 특정 tracked lab artifact를 직접 읽는 증거는 낮지만, 대표 fixture 승격 전까지는 보수적으로 본다.

관련 기준 문서는 다음이다.

- [99_cleanup_outputs_lab_protection_policy_review.md](./99_cleanup_outputs_lab_protection_policy_review.md)
- [../reviews/99_lab_experiment_set_summaries.md](../reviews/99_lab_experiment_set_summaries.md)
- [../reviews/99_llm_sample_validation_review.md](../reviews/99_llm_sample_validation_review.md)
- [../reviews/99_A-F세트_대표샘플_6선.md](../reviews/99_A-F세트_대표샘플_6선.md)

## 3. 대표 Fixture 후보 목록

| 후보 | 현재 lab 경로 | 보존 목적 | 필요한 최소 파일 | 이관 후보 위치 | 현재 direct docs 참조 | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
| B R2B 대표 샘플 | `lab/04-25_B세트R2B_산출물` | SQLi R2B 판단 품질 대표. double decode, supporting context, educational FP bait 분리 검증 | `data/processed/openai-b_r2b_dry-run_stage1_results.json`, `reports/openai-b_r2b_dry-run_stage2_report.json` 또는 `.md`, 필요 시 `2026-04-25_B세트R2B_비교.md` 요약 | `tests/fixtures/lab_artifacts/b_r2b/` 또는 `docs/examples/lab_artifacts/b_r2b/` | `docs/reviews/99_lab_experiment_set_summaries.md`에서 legacy artifact와 fixture 후보로 언급 | `FIXTURE_CANDIDATE` |
| C 대표 샘플 | `lab/04-25_C세트_산출물` | HTML entity XSS와 browser execution 단정 금지, tutorial/onerror FP bait 분리 검증 | `data/processed/openai-c_set_dry-run_stage1_results.json`, `reports/openai-c_set_dry-run_stage2_report.json` 또는 `.md` | `tests/fixtures/lab_artifacts/c_html_entity_xss/` 또는 `docs/examples/lab_artifacts/c_html_entity_xss/` | `docs/reviews/99_lab_experiment_set_summaries.md`, spot check 문서에서 raw path 언급 | `FIXTURE_CANDIDATE` |
| E R2B 대표 샘플 | `lab/04-30_E세트R2B_산출물` | PHP wrapper/file disclosure intent, front-controller response guardrail, 200/large body overclaim 방지 검증 | `reports/openai-e_r2b-check_stage2_report.json`, 필요 시 `data/processed/openai-e_r2b-check_stage1_results.json`과 `.md` report | `tests/fixtures/lab_artifacts/e_r2b_php_wrapper/` 또는 `docs/examples/lab_artifacts/e_r2b_php_wrapper/` | `docs/design/99_stage2_report_quality_lint_candidate_review.md`, `docs/design/99_stage2_report_quality_lint_tuning_plan.md`가 `stage2_report.json` 직접 참조 | `FIXTURE_CANDIDATE`; docs direct reference replacement 필요 |
| F R2B 대표 샘플 | `lab/05-02_F세트R2B_산출물` | auth response delta, POST body visibility 한계, login/account/lockout success 단정 금지 검증 | `data/processed/openai-f_r2b_response_delta_stage1_results.json`, `reports/openai-f_r2b_response_delta_stage2_report.json` 또는 `.md`; runner log는 보존 필요성 별도 판단 | `tests/fixtures/lab_artifacts/f_r2b_auth_response_delta/` 또는 `docs/examples/lab_artifacts/f_r2b_auth_response_delta/` | `docs/reviews/99_lab_experiment_set_summaries.md`에서 fixture 후보로 언급 | `FIXTURE_CANDIDATE` |
| G R2 대표 샘플 | `lab/05-03_G세트R2_산출물` | protocol anomaly/raw socket context-only 대표. malformed/protocol request와 exploit success 분리 검증 | `data/processed/openai-g_r2_protocol_anomaly_stage1_results.json`, `reports/openai-g_r2_protocol_anomaly_stage2_report.json` 또는 `.md`; raw socket context 설명은 docs에 보존 | `tests/fixtures/lab_artifacts/g_r2_protocol_anomaly/` 또는 `docs/examples/lab_artifacts/g_r2_protocol_anomaly/` | `docs/reviews/99_lab_experiment_set_summaries.md`에서 raw socket 재현성 때문에 보존 필요 언급 | `FIXTURE_CANDIDATE` |
| H R2 crawler baseline | `lab/05-03_H세트R2_산출물` | crawler-like UA, robots/sitemap/product/category baseline이 candidate로 과승격되지 않는지 검증 | `data/processed/openai-h_r2_crawler_baseline_stage1_results.json`, `reports/openai-h_r2_crawler_baseline_stage2_report.json` 또는 `.md` | `tests/fixtures/lab_artifacts/h_r2_crawler_baseline/` 또는 `docs/examples/lab_artifacts/h_r2_crawler_baseline/` | `docs/experiments/H_set/...`, `docs/reviews/99_lab_experiment_set_summaries.md`에서 legacy artifact 언급 | `FIXTURE_CANDIDATE` |
| H R3 scanner low-signal | `lab/05-03_H세트R3_산출물` | scanner-like sensitive path, `/server-status` low severity, WordPress/file exposure/admin success 단정 금지 검증 | `data/processed/openai-h_r3_scanner_low_signal_stage1_results.json`, `reports/openai-h_r3_scanner_low_signal_stage2_report.json` 또는 `.md` | `tests/fixtures/lab_artifacts/h_r3_scanner_low_signal/` 또는 `docs/examples/lab_artifacts/h_r3_scanner_low_signal/` | `docs/experiments/H_set/...`, `docs/reviews/99_lab_experiment_set_summaries.md`에서 legacy artifact 언급 | `FIXTURE_CANDIDATE` |
| H R4 mixed baseline scanner | `lab/05-03_H세트R4_산출물` | normal baseline과 scanner-like context를 단일 attack chain으로 합치지 않는지 검증 | `reports/openai-h_r4-check_stage2_report.json`, 필요 시 `data/processed/openai-h_r4-check_stage1_results.json`; runner log는 보존 필요성 별도 판단 | `tests/fixtures/lab_artifacts/h_r4_mixed_baseline_scanner/` 또는 `docs/examples/lab_artifacts/h_r4_mixed_baseline_scanner/` | `docs/design/99_stage2_report_quality_lint_candidate_review.md`, `docs/design/99_stage2_report_quality_lint_tuning_plan.md`, `docs/design/99_web_ui_report_viewer_phase1a_template_contract.md`가 `stage2_report.json` 직접 참조 | `FIXTURE_CANDIDATE`; docs direct reference replacement 필요 |
| 단일 viewer payload JSON | `lab/op-security_2026-05-02_12-40-00_to_2026-05-02_12-46-00_kst_viewer_payload.json` | Web UI viewer sample payload 가능성 | 실제 viewer fixture로 쓸 경우 payload JSON 1개만 최소 보존 | `tests/fixtures/lab_artifacts/viewer_payload/` 또는 Web UI 전용 fixture 위치 | `docs/design/99_finding_context_supporting_events_investigation.md`에서 조사 대상 중 하나로 언급. tests는 tmp viewer payload를 생성하며 이 lab 파일을 직접 읽는 증거는 낮음 | `NEEDS_REVIEW` |

## 4. Fixture 위치 선택 기준

| 후보 위치 | 장점 | 단점 | 사용 기준 |
| --- | --- | --- | --- |
| `tests/fixtures/lab_artifacts/{case}/` | regression/test fixture 성격이 명확하다. lab 제거 후에도 tests가 안정적으로 참조할 수 있다. | 테스트에서 실제 사용하지 않으면 fixtures가 비대해진다. | regression에서 실제 읽을 파일만 둔다. |
| `docs/examples/lab_artifacts/{case}/` | 문서 예시/설명용 artifact로 적합하다. 테스트 fixture와 분리된다. | repo에 큰 JSON을 계속 보관할 수 있다. | docs에서만 참조하는 sample이나 CLI 예시 입력을 둔다. |
| `docs/reviews`에 summary만 유지 | repo를 가장 가볍게 유지할 수 있다. | machine-readable sample이 사라진다. | 단순 historical artifact이며 재현 fixture 가치가 낮을 때 사용한다. |

권장 기준은 다음이다.

- regression에서 실제 읽을 파일은 `tests/fixtures/lab_artifacts/{case}/`로 승격한다.
- 문서에서만 참조하는 예시는 `docs/examples/lab_artifacts/{case}/`로 승격한다.
- 단순 historical artifact는 docs summary로 대체한 뒤 lab 원본을 untrack/remove 후보로 본다.
- 큰 JSON/JSONL은 최소 파일만 남긴다.
- runner logs의 `request_results.jsonl`은 runner 재현성 검토가 필요한 case에서만 보존 후보로 둔다.

## 5. Direct Docs Reference Replacement 계획

| docs 문서 | 현재 lab 참조 | 대체 후보 | 필요한 후속 작업 |
| --- | --- | --- | --- |
| `docs/design/99_stage2_report_quality_lint_candidate_review.md` | `lab/05-03_H세트R4_산출물/reports/openai-h_r4-check_stage2_report.json`, `lab/04-30_E세트R2B_산출물/reports/openai-e_r2b-check_stage2_report.json` | `tests/fixtures/lab_artifacts/h_r4_mixed_baseline_scanner/openai-h_r4-check_stage2_report.json`, `tests/fixtures/lab_artifacts/e_r2b_php_wrapper/openai-e_r2b-check_stage2_report.json` 또는 `docs/examples/...` | fixture/examples 복사 후 command 예시 경로 갱신 |
| `docs/design/99_stage2_report_quality_lint_tuning_plan.md` | H R4와 E R2B `stage2_report.json` | quality lint regression fixture 또는 docs example | PASS 결과 설명은 유지하되 input path만 새 위치로 교체 |
| `docs/design/99_web_ui_report_viewer_phase1a_template_contract.md` | H R4 `stage2_report.json` 표시 예시 | `docs/examples/lab_artifacts/h_r4_mixed_baseline_scanner/openai-h_r4-check_stage2_report.json` | viewer 예시가 lab artifact 제거 후에도 깨지지 않게 path 교체 |
| `docs/design/99_finding_context_supporting_events_investigation.md` | 단일 lab viewer payload JSON을 조사 대상 중 하나로 언급 | Web UI viewer fixture로 승격하거나 historical mention으로 유지 | 실제 test fixture로 쓸지 결정. 단순 historical mention이면 lab 원본 제거 전 문구 정리 |
| `docs/experiments/*`, `docs/reviews/99_lab_experiment_set_summaries.md` | legacy comparison MD와 lab output path | docs summary 또는 fixture/examples path | historical artifact 참조와 active fixture 참조를 분리 |

이번 작업에서는 위 참조를 실제로 바꾸지 않는다. 후속 PR에서 fixture/examples 복사와 docs link 교체를 같은 변경으로 수행한다.

## 6. Untrack/Remove 전제 조건

JSON/JSONL/log artifact를 untrack/remove 후보로 전환하려면 다음 조건을 모두 충족해야 한다.

- 대표 fixture 후보가 확정되어 fixture/examples 위치가 정해졌다.
- E R2B와 H R4처럼 docs에서 직접 참조하는 `stage2_report.json`이 fixture/examples 경로로 대체됐다.
- tests/src/scripts가 lab artifact를 직접 읽지 않음이 확인됐다.
- `lab/observability`는 별도 정책으로 계속 보호된다.
- `.gitignore` 후보 패턴이 `lab/observability`와 legacy README/MD를 과도하게 덮지 않도록 보수적으로 작성됐다.
- `cleanup_outputs.py`의 lab 보호 정책은 유지하거나, 별도 PR에서 tests와 함께 변경했다.

## 7. 권장 후속 PR

PR 4C-4B-1:

- fixture selection plan 문서 작성
- 실제 파일 이동 없음

PR 4C-4B-2:

- 선정된 소수 artifact를 `tests/fixtures/lab_artifacts` 또는 `docs/examples/lab_artifacts`로 복사
- docs direct reference를 새 경로로 갱신
- lab 원본 삭제 없음

PR 4C-4C:

- generated JSON/JSONL/log untrack/remove
- `.gitignore` 정리
- docs 링크 검증

PR 4C-4D:

- lab legacy MD archive/remove 검토

## 8. 최종 결론

```text
lab artifact를 정리하기 전에 대표 fixture 후보를 먼저 확정한다.
E R2B와 H R4처럼 docs에서 직접 참조하는 stage2_report.json은 fixture/examples 경로를 만든 뒤 대체한다.
JSON/JSONL/log artifact는 fixture 선별과 direct reference 해소 후 보수적으로 untrack/remove한다.
MD historical artifact는 docs summary와 대체 관계를 더 확인한 뒤 별도 판단한다.
```
