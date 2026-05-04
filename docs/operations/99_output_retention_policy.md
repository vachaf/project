# output retention / cleanup 정책

- 문서 상태: 운영 정책 문서
- 기준 시점: 2026-05-04
- 목적: 실험 산출물과 분석 산출물이 많아진 상태에서 무엇을 보존하고 무엇을 삭제 후보로 볼지 기준화한다.

이 문서는 재현성, 검증 가능성, 민감 정보 관리, 저장 공간 정리를 함께 고려하기 위한 운영 기준이다.

비목표:

```text
- 실제 삭제 스크립트
- 자동 차단 정책
- 로그 보존 관련 법적 정책
- 민감 정보 탐지 도구
```

## 1. 기본 원칙

- `lab/` 산출물은 기본 보존한다.
- 실험 비교에 사용된 raw export, processed JSON, reports, `pipeline_manifest.json`은 기본 보존한다.
- 삭제 자동화는 가장 나중에 검토한다.
- cleanup script를 만들더라도 기본 동작은 dry-run이어야 하며, `--apply`일 때만 실제 삭제한다.
- Apache logs-only 분석 재현에 필요한 파일은 삭제하지 않는다.
- 민감 정보가 들어갈 수 있는 파일은 공개 또는 공유 전에 별도 검토한다.

핵심 기준:

```text
먼저 보존 기준을 문서화하고,
그 다음에 수동 검토 절차를 만들며,
삭제 자동화는 가장 마지막에 검토한다.
```

## 2. 산출물별 정책

### 2.1 raw export JSON

예:

```text
security_2026-05-01_kst.json
security_2026-05-01T10-00_to_2026-05-01T12-00_kst.json
```

- 원본 로그 export이므로 재현성 근거다.
- 기본 보존 대상이다.
- `prepare` 이전 입력이므로 비교 실험의 시작점을 설명할 때 중요하다.
- IP, User-Agent, `request_id`, `query_string` 등 민감 정보 가능성이 있다.
- 공개 repo 반영 여부는 별도 검토한다.

정리 기준:

- 비교 문서, 리뷰, 발표, regression 재현에 사용된 export는 보존한다.
- 임시 확인용으로 만들었더라도 동일 구간의 더 명확한 export가 이미 있고 재현성이 유지되면 중복 여부를 검토할 수 있다.
- 공개 공유 전에는 민감 정보 포함 여부를 우선 확인한다.

### 2.2 processed JSON

대상 예:

```text
*_llm_input.json
*_analysis_candidates.json
*_filtered_out_rows.json
*_noise_summary.json
*_stage1_results.json
*_stage1_errors.json
*_stage2_report_input.json
```

- 실험 결과 비교에 실제로 쓰인 파일은 보존한다.
- `prepare -> stage1 -> stage2` 중간 근거이므로 재현과 검증에 중요하다.
- `*_filtered_out_rows.json`, `*_noise_summary.json`은 후보화와 제외 기준을 설명할 때 유용하다.
- `*_stage1_errors.json`은 실패 원인 분석 전에는 보존한다.

정리 기준:

- 비교 실험 문서, 샘플 리뷰, 발표 자료에서 인용되거나 근거로 사용된 processed JSON은 KEEP으로 본다.
- 단순 dry-run 확인용으로 생성했고 문서나 fixture에 반영되지 않은 파일은 cleanup 후보가 될 수 있다.
- 동일 입력에서 반복 생성된 중복 산출물은 최신본, 참조본, 비교본 여부를 검토한 뒤 정리 후보로 분류할 수 있다.

### 2.3 reports

대상 예:

```text
*_stage2_report.md
*_stage2_report.json
비교 Markdown
```

- 리뷰, 발표, 검증, 후속 문서 작성의 직접 근거이므로 기본 보존한다.
- Markdown 비교 문서는 사람이 읽는 판단 결과다.
- JSON 보고서는 보고서 생성 구조와 모델 출력 비교에 필요하다.

정리 기준:

- 비교 Markdown과 `*_stage2_report.md`는 기본 KEEP이다.
- 대응되는 JSON 보고서도 재현과 교차 검증 근거로 함께 보존한다.

### 2.4 `pipeline_manifest.json`

- 실행 재현성 근거다.
- 입력 시작점, 실행 단계, command, 산출물 경로, provider 정보 등을 추적할 수 있다.
- 기본 보존 대상이다.

정리 기준:

- 실험 비교나 보고에 사용된 run의 manifest는 삭제하지 않는다.
- processed JSON 또는 report만 있고 manifest가 없으면 실행 맥락이 약해지므로 가능한 함께 보존한다.

### 2.5 error / raw error dump

대상 예:

```text
*_stage2_report_error.json
*_stage2_report_raw_error.json
기타 provider raw error dump
```

- 원인 분석 전에는 보존한다.
- 문제가 문서화되었거나 재현 필요가 사라지면 삭제 후보가 될 수 있다.
- LLM raw response나 민감 정보가 포함될 수 있으므로 별도 주의가 필요하다.

정리 기준:

- 실패 원인 조사, provider 차이 분석, parse error 재현에 필요하면 KEEP 또는 REVIEW로 둔다.
- 문제 원인이 문서화되고 같은 실패를 다시 추적할 필요가 없으면 cleanup 후보가 될 수 있다.
- raw response 성격의 dump는 공개 저장소 반영 전에 민감 정보 검토를 먼저 한다.

### 2.6 temporary dry-run output

대상 예:

```text
/tmp 하위 산출물
명시적 임시 work-dir 하위 dry-run 결과
```

- repo 또는 `lab/`의 정식 산출물과 구분한다.
- 결과가 문서, fixture, 비교 산출물에 반영되면 삭제 후보가 될 수 있다.

정리 기준:

- 구조 확인만을 위해 만든 임시 dry-run 산출물은 장기 보존 대상이 아니다.
- 다만 regression 기대값 또는 문서 근거로 승격된 경우에는 정식 보존 대상으로 전환한다.

## 3. 보존 등급 제안

| 등급 | 의미 | 예시 |
|---|---|---|
| `KEEP` | 실험 재현, 리뷰, 발표, 비교 근거로 기본 보존 | raw export, 비교에 사용된 processed JSON, report, manifest |
| `REVIEW` | 민감 정보 또는 중복 여부 검토 후 보존/삭제 판단 | raw export, raw error dump, 일부 중복 processed JSON |
| `CLEANUP_CANDIDATE` | 임시 dry-run, 중복 output, 원인 분석 완료된 raw error | `/tmp` 산출물, 문서 미반영 dry-run 결과 |
| `DO_NOT_AUTO_DELETE` | 자동 삭제 대상에서 기본 제외 | `lab/` 정식 산출물, regression fixtures, expected files, `docs/` |

운영 해석:

- `KEEP`는 수동 정리 전까지 기본 보존한다.
- `REVIEW`는 삭제보다 검토가 먼저다.
- `CLEANUP_CANDIDATE`도 즉시 삭제하지 않고 목록 확인 후 판단한다.
- `DO_NOT_AUTO_DELETE`는 향후 cleanup script가 생겨도 기본 제외 영역으로 본다.

## 4. cleanup script 설계 원칙

이 문서는 cleanup script를 만들지 않는다.

나중에 설계할 경우의 최소 원칙:

- 기본은 dry-run이다.
- `--apply`일 때만 실제 삭제한다.
- 삭제 대상 목록을 먼저 출력한다.
- `lab/` 정식 산출물은 기본 제외한다.
- `tests/fixtures`, `tests/expected`, `docs/`는 삭제 대상에서 제외한다.
- 최소 1회 수동 검토 후 적용한다.
- 삭제 로그를 남긴다.

추가 원칙:

- 단순 파일명 패턴만으로 바로 삭제하지 않는다.
- `pipeline_manifest.json`이나 비교 문서와 연결된 파일은 우선 보존 후보로 본다.
- Apache logs-only 분석 재현 경로를 끊는 삭제는 금지한다.

## 5. 공개 repo / 민감 정보 주의

- raw export와 processed JSON에는 IP, User-Agent, `request_id`, `query_string`이 들어갈 수 있다.
- `query_string`에는 credential, token, API key가 포함될 가능성을 고려한다.
- 공개 전에는 민감 정보 grep 또는 동등한 수동 점검이 필요하다.
- LLM raw response 또는 error dump도 민감 정보 포함 가능성을 검토한다.
- `docs/가상환경_구성_요약.txt` 같은 환경 요약 파일은 과거 삭제한 상태이므로, 유사 파일을 다시 생성하거나 커밋하지 않도록 주의한다.

핵심 메시지:

```text
보존 여부 판단과 공개 가능 여부 판단은 같은 문제가 아니다.
재현성 때문에 보존할 수는 있지만, 공개 전 검토는 별도로 필요하다.
```

## 6. 권장 운영 흐름

### 6.1 실험 직후

- 모든 산출물을 우선 보존한다.
- raw export, processed JSON, reports, manifest를 한 번에 삭제하지 않는다.

### 6.2 비교 문서 작성 후

- 실제 비교와 리뷰에 사용된 핵심 파일을 표시한다.
- 가능하면 Markdown 비교 문서 또는 메모에 기준 파일을 남긴다.

### 6.3 리뷰 완료 후

- 임시 dry-run output만 cleanup 후보로 이동한다.
- 정식 `lab/` 산출물과 혼동하지 않도록 분리해서 본다.

### 6.4 발표/보고 전

- `*_stage2_report.md`, 비교 문서, sample review 문서는 보존한다.
- 발표 근거가 되는 export, processed JSON, manifest도 함께 유지한다.

### 6.5 장기 정리 시

- cleanup script가 있더라도 우선 dry-run으로 후보 목록만 확인한다.
- 실제 삭제는 수동 검토 이후에만 수행한다.

## 7. 이 문서가 아닌 것

- 실제 삭제 스크립트가 아니다.
- 자동 차단 정책이 아니다.
- 로그 보존 관련 법적 정책이 아니다.
- 민감 정보 탐지 도구가 아니다.

## 8. 관련 문서

- [05_Export_LLM_분석_전략.md](./05_Export_LLM_분석_전략.md)
- [06_통합_스크립트_설명_정리본.md](./06_통합_스크립트_설명_정리본.md)
- [../reviews/99_llm_sample_review_plan.md](../reviews/99_llm_sample_review_plan.md)
- [../standards/99_analysis_quality_criteria.md](../standards/99_analysis_quality_criteria.md)
- [../../lab/README.md](../../lab/README.md)
