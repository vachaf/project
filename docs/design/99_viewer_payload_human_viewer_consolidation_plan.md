# Viewer Payload Human Viewer Consolidation Plan

## 1. 목적과 범위

이 문서는 사람이 분석 결과를 읽는 주 화면을 `/payload` viewer 하나로 통합하기 위한 조사/설계 메모다.

현재 DB-backed job detail의 Artifact Summary는 LLM token usage, filtered reasons count, artifact availability 같은 운영/디버깅 요약을 제공한다. 반면 분석자가 최종 내용을 읽을 때는 `/job/{id}/viewer`, Stage2 JSON viewer, `stage2_report.md`, raw artifacts를 오가야 할 수 있다. 이 흐름은 사람이 읽는 주 화면이 분산되는 문제가 있다.

이번 결론은 새 Markdown/HTML renderer를 키우기보다 `viewer_payload.json`과 `/payload` viewer를 canonical human view로 강화하는 것이다. 코드, DB schema, worker/pipeline, Stage1/Stage2 prompt/schema는 이 문서 작업에서 변경하지 않는다.

## 2. 현재 Viewing Flow 문제

현재 화면 역할은 대체로 다음처럼 나뉜다.

| 화면/Artifact | 현재 역할 | 문제 |
| --- | --- | --- |
| `/job/{id}` Artifact Summary | token usage, filtered reasons, artifact link 같은 운영 요약 | 분석 본문을 읽는 화면은 아님 |
| `/job/{id}/viewer` | `viewer_payload.json` 기반 timeline/findings/context viewer | Stage2 report의 일부 human-facing section을 충분히 보여주지 않음 |
| `/job/{id}/report` 또는 legacy `/report/{report_id}` | Stage2 JSON 구조화 viewer | 별도 주 화면이 되면 human reading path가 분산됨 |
| `/job/{id}/artifact/stage2_report` | raw JSON | 디버깅용이어야 함 |
| `/job/{id}/artifact/stage2_report_md` | raw Markdown | 사람이 읽을 수는 있지만 Web 주 화면으로 키우면 renderer가 중복됨 |

`viewer_payload_builder.py`의 원래 역할은 Stage2 report, Stage2 input, Stage1 results, LLM input, noise summary, raw export reference를 read-only viewer용 payload로 정규화하는 것이다. 따라서 새 주 화면을 만들기보다 `/payload` viewer가 이 통합 payload를 더 잘 소비하게 하는 편이 더 일관된다.

## 3. 결론

`viewer_payload.json`을 canonical human-view artifact로 둔다.

권장 방향:

1. `viewer_payload.v1`을 additive 확장 또는 기존 `report` section 활용으로 유지한다.
2. `/payload` viewer가 `payload.report`의 Stage2 report sections를 더 많이 표시한다.
3. `payload.findings`는 request-level candidate timeline과 detail panel의 source of truth로 유지한다.
4. `/job/{id}` Artifact Summary는 운영/디버깅 요약으로 유지한다.
5. Stage2 JSON viewer와 Markdown artifact는 raw/debug/legacy inspection 역할로 둔다.

jobs/12 조사 기준으로 `viewer_payload.json`에는 이미 top-level `report` section이 있고, 그 안에 Stage2 report의 주요 human-facing field가 들어 있다. 즉 1차 구현은 builder schema를 크게 바꾸기보다 `/payload` template가 이미 들어 있는 `payload.report`를 표면화하는 작업이 우선이다.

## 4. Stage2 Report To Viewer Payload Mapping

jobs/12 기준 `stage2_report.json`은 `meta`, `report`를 top-level로 가진다. `report`에는 아래 field가 있다.

| Stage2 report field | 현재 viewer_payload 위치 | 현재 `/payload` 표시 | 권장 표시 위치 |
| --- | --- | --- | --- |
| `report_title` | `summary.report_title`, `report.report_title` | header meta 일부 | page title/subtitle로 유지 |
| `overall_assessment` | `summary.overall_assessment`, `report.overall_assessment` | 표시됨 | 현재 위치 유지 |
| `executive_summary` | `summary.executive_summary`, `report.executive_summary` | summary card에서는 직접 표시 안 됨 | Overall 아래 bullet section 추가 |
| `key_findings` | `report.key_findings` | 직접 표시 안 됨 | Findings timeline 위/옆에 report-level key findings panel 추가 |
| `notable_incidents` | `report.notable_incidents` | 직접 표시 안 됨. request-level `findings`는 별도 표시됨 | request-level findings와 연결되는 report-level incident summary로 표시 |
| `notable_source_ips` | `report.notable_source_ips` | 직접 표시 안 됨 | Source IP summary card/table 추가 |
| `noise_interpretation` | `report.noise_interpretation`, `noise.*` | 직접 표시 안 됨 | Candidate-excluded/context interpretation panel 추가 |
| `recommended_actions` | `report.recommended_actions` | finding-level actions만 technical details에 표시 | report-level actions section 추가 |
| `confidence_and_limitations` | `report.confidence_and_limitations` | guardrail footer와 별개로 직접 표시 안 됨 | Guardrails/limitations section에 표시 |
| `presentation_takeaway` | `report.presentation_takeaway` | 직접 표시 안 됨 | 마지막 summary/takeaway block으로 표시 |

주의:

- jobs/12의 Stage2 report에는 legacy wording 문제가 포함되어 있었다. 후속 구현은 Stage2 wording guardrail 이후 새 artifact에서 안전 표현을 기대하되, `/payload` renderer도 candidate-excluded를 safety verdict로 표현하지 않아야 한다.
- `/payload`는 Stage2 report text를 재계산하거나 새 verdict/severity/category를 만들지 않는다. 이미 artifact에 있는 text를 sanitizer를 거쳐 표시한다.

## 5. Stage1 Results To Viewer Payload Findings Mapping

`viewer_payload_builder.py`는 finding source 우선순위를 아래처럼 둔다.

1. `stage2_report_input.top_incidents`
2. `stage1_results.results`
3. `llm_input.analysis_candidates`

그 뒤 Stage1/candidate/raw export match를 `merge_missing()`으로 보강한다. jobs/12 기준 `stage1_results.results[0]`에는 아래 useful field가 있다.

| Stage1 result field | 현재 viewer_payload.findings 위치 | 현재 `/payload` 표시 | 권장 |
| --- | --- | --- | --- |
| `verdict` | `findings[].verdict` | badge/detail에 표시 | 유지 |
| `severity` | `findings[].severity` | timeline/detail badge에 표시 | 유지 |
| `confidence` | `findings[].confidence` | detail에 표시 | 유지 |
| `false_positive_possible` | 현재 finding에 명시 보존 안 됨 | 표시 안 됨 | additive field 후보. 단 safety verdict로 표현하지 않음 |
| `reasoning_summary` | `findings[].reasoning_summary` | Analysis Note에 표시 | 유지 |
| `evidence_fields` | `findings[].evidence_fields` | Evidence list에 표시 | 유지 |
| `recommended_actions` | `findings[].recommended_actions` | Technical details 안에 표시 | 더 읽기 쉬운 per-finding action block 후보 |
| `response_id` | 현재 finding에 명시 보존 안 됨 | 표시 안 됨 | 디버깅용으로 Artifact Summary/raw artifact에 가까움. `/payload` 기본 화면에는 비권장 |
| `request_id` | `findings[].request_id` | technical details에 표시 | 유지 |
| `llm_usage` | Stage1 artifact에는 있음, viewer finding에는 없음 | 표시 안 됨 | per-candidate detail은 `/payload` 기본 화면에 비권장 |
| `raw_output_text` | 제외 | 표시 안 됨 | 계속 제외 |

현재 `sanitize_payload_findings()`는 `severity`, `verdict`, `category`, `src_ip`, `method`, `uri`, `status_code`, `request_id`, `confidence`, `reasoning_summary`, `evidence_fields`, `reason_hints`, `recommended_actions`, relation ids, raw export match만 통과시킨다. 따라서 `false_positive_possible`을 보여주려면 builder와 sanitizer 양쪽의 additive pass-through가 필요하다.

## 6. Artifact Summary 와 Viewer Payload 역할 분리

`/job/{id}` Artifact Summary:

- LLM token usage totals
- filtered reasons counts/top reasons
- artifact availability
- dry-run/unavailable operational state
- raw artifact links
- 운영/디버깅 요약

`/payload` viewer:

- report title/overall/executive summary
- report-level key findings
- request-level findings timeline
- selected finding detail
- related contexts/supporting events
- report-level notable source IPs
- report-level recommended actions
- confidence/limitations/guardrails
- candidate-excluded/context-only interpretation

이 분리는 비용/usage/파일 존재 여부 같은 운영 정보와 분석자가 읽는 incident narrative를 섞지 않기 위한 것이다.

## 7. Stage2 JSON/Markdown Viewer 권장 역할

Stage2 JSON viewer:

- 기존 route/template/helper를 유지한다.
- primary human reading path로 키우지 않는다.
- Stage2 artifact 구조를 직접 확인하는 debug/legacy viewer로 둔다.
- `/payload`에서 필요하면 "Open Stage2 JSON artifact" 또는 "Open Stage2 debug viewer" 정도의 보조 링크로 둔다.

Stage2 Markdown artifact:

- raw artifact로 유지한다.
- 별도 HTML Markdown renderer 구현은 보류한다.
- Markdown을 주 화면으로 키우면 `/payload`와 중복 renderer가 생기므로 후속 우선순위에서 낮게 둔다.

## 8. Schema 확장 방식

권장: `viewer_payload.v1` additive extension.

이유:

- jobs/12 기준 `viewer_payload.report`가 이미 Stage2 report 주요 field를 보존한다.
- 기존 top-level key와 finding/context/supporting_event contract를 깨지 않아도 된다.
- Web template는 없는 field를 graceful fallback할 수 있다.

`viewer_payload.v2`가 필요한 경우:

- `report` 구조를 대규모로 재배치할 때
- findings/context/supporting_events relation semantics를 바꿀 때
- 기존 v1 소비자가 오해할 수 있는 필드명 변경이 필요할 때

현재는 v2가 필요하지 않다.

## 9. 넣지 않을 필드

기본 `/payload` human viewer에 넣지 않을 필드:

- `raw_output_text`
- raw provider response
- prompt text/system/user message
- per-candidate full `llm_usage`
- cost estimate
- raw POST body
- response body
- DB result
- browser execution result
- raw log line by default

조건부/디버깅 후보:

- `response_id`: 기본 화면에는 숨기고 raw artifact나 debug details에 맡긴다.
- `llm_usage`: `/job/{id}` Artifact Summary aggregate가 적절하다. per-candidate usage는 기본 human viewer에 넣지 않는다.
- `false_positive_possible`: safety verdict로 표현하지 않는 additive display 후보. label은 "Review caveat" 또는 "False-positive caveat from Stage1"처럼 source-bound wording을 사용한다.

## 10. Web Template 변경 후보

`web/templates/payload_detail.html` 후보 변경:

1. Header 아래에 "Report Summary" band 추가
   - report title
   - overall assessment
   - executive summary bullets
   - presentation takeaway

2. Timeline 위에 "Key Findings" panel 추가
   - `payload.report.key_findings`
   - report-level severity는 표시하되 재계산하지 않음

3. "Notable Source IPs" section 추가
   - `payload.report.notable_source_ips`
   - IP masking mode와 동일한 display helper 적용

4. "Candidate-Excluded / Context Notes" section 추가
   - `payload.report.noise_interpretation`
   - `payload.noise.filtered_out_breakdown`
   - candidate-excluded is not safety verdict 문구 유지

5. "Recommended Actions" section 추가
   - `payload.report.recommended_actions`
   - per-finding action과 report-level action을 구분

6. "Confidence And Limitations" section 추가
   - `payload.report.confidence_and_limitations`
   - Apache logs-only guardrails와 함께 표시

7. Finding detail panel polish
   - current `recommended_actions`를 technical details에서 한 단계 위로 올리는 후보
   - `false_positive_possible`을 추가할 경우 source-bound caveat로 표시

## 11. Builder 변경 후보

1차 구현에서는 builder 변경이 거의 필요 없다.

이미 있음:

- `payload.report`: Stage2 human-facing report fields
- `payload.summary`: title/overall/executive/counts
- `payload.findings`: Stage1/top incident/candidate fields merge
- `payload.contexts`
- `payload.supporting_events`
- `payload.noise`
- `payload.policies.guardrails`

후속 additive 후보:

- `findings[].false_positive_possible`
- `findings[].response_id`는 기본 미표시/디버그 only 여부 결정 후 보류
- `report_display` 같은 derived section은 불필요. template가 `payload.report`를 읽으면 충분하다.

## 12. Tests 후보

Builder tests:

- `viewer_payload.report`가 Stage2 report fields를 보존하는지 확인
- `viewer_payload.summary.executive_summary`가 유지되는지 확인
- `raw_output_text`와 raw provider response가 포함되지 않는지 확인
- `false_positive_possible`을 추가한다면 finding에 additive pass-through 되는지 확인

Web route/template tests:

- `/job/{id}/viewer`에 executive summary가 표시되는지
- key findings가 표시되는지
- report-level recommended actions가 표시되는지
- confidence/limitations가 표시되는지
- notable source IPs가 표시되는지
- raw snake_case guardrail key 또는 unsafe candidate-excluded wording이 기본 화면에 노출되지 않는지
- Stage2 JSON/raw Markdown link는 보조 링크로 유지되는지
- Web route가 verdict/severity/category/relation을 새로 만들지 않는지

Regression tests:

- `contexts`는 context-only로 표시되고 finding으로 승격되지 않음
- `supporting_events`는 related drill-down으로만 표시됨
- raw POST body/response body/DB result/browser execution success를 표시하거나 추론하지 않음
- `mask_src_ip` mode가 새 source IP section에도 적용됨

## 13. Do-Not-Change List

- DB schema 변경 금지
- worker/pipeline 변경 금지
- Stage1/Stage2 prompt/schema 변경 금지
- candidate selection logic 변경 금지
- viewer_payload relation contract 변경 금지
- Web UI에서 새 security verdict/relation/success inference 생성 금지
- raw POST body, response body, DB result, browser execution 결과 추론 금지
- raw provider response 표시 금지
- cost estimate 표시 금지
- retry/requeue/cancel 같은 destructive action 추가 금지

## 14. 다음 구현 커밋 후보

1. `/payload` report summary section 추가
   - `payload.report`와 `payload.summary`만 소비
   - builder 변경 없음

2. `/payload` report-level tables 추가
   - key findings
   - notable source IPs
   - recommended actions
   - confidence/limitations

3. candidate-excluded/context notes 추가
   - `payload.report.noise_interpretation`
   - `payload.noise.filtered_out_breakdown`
   - filtered reasons artifact summary는 `/job/{id}` Artifact Summary에 유지

4. optional Stage1 caveat pass-through
   - `false_positive_possible`만 additive로 검토
   - raw output, full usage, response id는 기본 화면에서 제외

5. Stage2 JSON/Markdown viewer 정리
   - primary link label을 debug/raw로 명확히 조정
   - 새 Markdown renderer는 계속 보류
