# 99_stage_dryrun_regression_설계

- 작성일: 2026-05-02
- 문서 역할: Stage1/Stage2 dry-run smoke regression 범위와 검증 방식을 정리

---

## 1. 목적

- 실제 LLM API 호출 없이 Stage1/Stage2 산출물 골격이 깨졌는지 빠르게 확인한다.
- `run_analysis_pipeline.py --dry-run` 흐름을 재사용해 prepare 이후 Stage1/Stage2 연결부를 함께 점검한다.
- schema, prompt guidance, `stage2_report_input.json`, Markdown 초안의 핵심 안전장치를 조건 기반으로 검증한다.

---

## 2. 비목표

- 실제 모델의 분류 품질이나 최종 verdict 품질을 평가하지 않는다.
- OpenAI/Anthropic 응답 품질 비교 실험을 대체하지 않는다.
- 전체 JSON snapshot 비교를 하지 않는다.

---

## 3. LLM API 호출 금지

- 회귀 스크립트는 반드시 `run_analysis_pipeline.py --dry-run` 만 사용한다.
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 가 없어도 통과해야 한다.
- dry-run 산출물, Stage1 prompt 재구성, Stage2 prompt 재구성만 사용하고 외부 API는 호출하지 않는다.

---

## 4. Stage1 검증 범위

- `llm_stage1_classifier.build_schema()` verdict enum 보존 여부
- `build_messages()` 기준 후보 payload 보존 여부
- `reason_hints`, `raw_request_target`, HPP/SQLi/XSS/traversal/file disclosure 관련 candidate 필드 누락 여부
- `suspicious_file_disclosure` label guidance 보존 여부
- `php://filter`, `convert.base64-encode`, `resource=` 관련 설명 보존 여부
- `status_code=200`, `text/html`, `response_body_bytes` 만으로 성공 단정 금지 문구 보존 여부
- raw POST body visibility 한계 문구 보존 여부

Stage1 dry-run 결과 파일 자체는 placeholder 결과일 수 있으므로, 회귀 스크립트는 `llm_input.json` 기반으로 Stage1 request payload를 직접 재구성해 함께 검증한다.

---

## 5. Stage2 검증 범위

- `*_stage2_report_input.json` 생성 여부
- `policy_notes.file_disclosure_policy` 보존 여부
- `policy_notes.ip_behavior_aggregate_policy` 보존 여부
- `pipeline_counts.ip_behavior_aggregate_count` 보존 여부
- `ip_behavior_aggregates`의 context-only 필드 보존 여부
- normal baseline / reference baseline 분리 문맥 유지 여부
- dry-run Markdown 초안에 context-only, conservative file disclosure 설명이 유지되는지 여부

Stage2 prompt guidance 검증은 `llm_stage2_reporter.build_messages()`를 dry-run 산출물의 `report_input`으로 다시 호출해 수행한다.

---

## 6. expected JSON 조건 기반 검증 방식

- fixture마다 `tests/expected/stage_dryrun_regression/<fixture>.expected.json` 파일을 둔다.
- 각 expected 파일은 `MUST`, `MUST_NOT`, `SHOULD` 규칙을 가진다.
- 지원 op:
  - `json_path_exists`
  - `json_path_equals`
  - `json_path_contains`
  - `list_any_contains`
  - `list_any_equals`
  - `file_contains`
  - `file_not_contains`
  - `file_contains_unless_context`
- 전체 snapshot diff 대신 필요한 필드와 문구만 조건식으로 고정한다.

---

## 7. 성공 단정 금지 표현 검증 원칙

- `공격 성공`, `침해 성공`, `파일 노출`, `XSS 실행`, `DB 유출`, `compromised`, `attacker IP` 같은 표현은 직접 단정으로 쓰이지 않아야 한다.
- 다만 “단정하지 마라”, “근거로 사용하지 마라” 같은 금지 문맥 안에서의 언급은 허용한다.
- 따라서 금지 표현 검증은 단순 substring hard fail 대신 `file_contains_unless_context` 방식으로 구현한다.

---

## 8. prepare regression과의 차이

- prepare regression은 `prepare_llm_input.py` 산출 분류 구조만 검증한다.
- stage dry-run regression은 prepare 이후 Stage1/Stage2 연결부까지 포함한다.
- prepare regression은 collection 중심이고, stage dry-run regression은 아래를 추가로 본다.
  - Stage1 schema
  - Stage1 prompt guidance
  - Stage2 report input
  - Stage2 prompt guidance
  - Stage2 Markdown 초안

---

## 9. 현재 fixture 범위

- `e_r2_php_wrapper`
- `ip_behavior_multi_signal_context`
- `e_r3_search_attack_and_baseline`
- `b_r2b_double_encoded_sqli`
- `l3_log4shell_ssrf_context`

초기 범위는 5개로 유지하고, 이후 필요 시 direct config path, HTML entity XSS, XSS false positive review 등을 확장한다.
