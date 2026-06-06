# Prepare Candidate Selection Minimal Evaluation Plan

- Status: phase 1 local smoke metric
- Date: 2026-06-06
- Scope: prepare candidate selection only
- Non-goal: Stage1/Stage2 detection accuracy, exploit success, compromise success, DB/Web changes

## 목적

prepare 단계의 candidate selection이 작은 라벨셋에서 의심 요청을 얼마나 일관되게 후보로 올리는지 측정한다. 이 평가는 `analysis_candidates.json`에 특정 `request_id`가 포함됐는지만 비교한다.

이 평가는 project-local smoke metric이다. 공개 benchmark나 intrusion detection success metric이 아니다. 발표/Q&A에서 "후보 선별 기준을 작은 라벨셋으로 regression guard한다"는 설명 근거로 사용한다.

## 비범위

- Stage1 LLM classification accuracy 평가
- Stage2 report quality/wording 평가
- 공격 성공, 침해 성공, 계정 탈취 성공 라벨링
- response body, raw POST body, DB result, browser execution 기반 판단
- prepare candidate selection logic 변경
- DB schema, Web UI, viewer payload 변경

## 라벨 정책

허용 label:

- `candidate_expected`: 사람이 prepare가 이 request를 candidate로 포함하길 기대한다.
- `candidate_not_expected`: 사람이 prepare가 이 request를 candidate로 포함하지 않길 기대한다.
- `unsure`: Apache log evidence만으로 평가 기대값을 정하기 어렵다. metric 계산에서 제외한다.

금지 label:

- `benign`
- `normal`
- `malicious_success`
- `attack_success`
- `compromised`
- `account_takeover_success`

중요한 해석 한계:

- `candidate_expected`는 attack success, browser execution, data disclosure, compromise를 의미하지 않는다.
- `candidate_not_expected`는 benign/normal 확정이 아니다.
- excluded row는 candidate 분석 대상에서 제외된 것일 뿐 무해 판정이 아니다.
- `status_code=200`, response size, route, user agent만으로 success/benign을 단정하지 않는다.

## 데이터셋

초기 데이터셋:

- `data/eval/prepare_candidate_selection_minimal.json`
- schema_version: `prepare_candidate_selection_eval.v1`
- 30 rows
- label 분포:
  - `candidate_expected`
  - `candidate_not_expected`
  - `unsure`

최소 item field:

```json
{
  "request_id": "eval_req_001",
  "source": "minimal_manual_fixture",
  "method": "GET",
  "uri": "/search.php?q=<script>alert(1)</script>",
  "status_code": 200,
  "human_label": "candidate_expected",
  "reason": "xss_probe",
  "notes": "Probe-like request target; does not imply browser execution or exploit success."
}
```

Reason taxonomy:

- `xss_probe`
- `sqli_probe`
- `path_traversal_probe`
- `sensitive_path_probe`
- `auth_behavior_signal`
- `protocol_anomaly_signal`
- `static_asset_like`
- `crawler_or_baseline_like`
- `low_signal_request`
- `duplicate_low_signal`
- `insufficient_log_evidence`
- `unsure`

## Metric 정의

입력:

- labels JSON
- prepare output `analysis_candidates.json`
- optional `filtered_reasons.json`

비교 기준:

- `candidate_expected` and request_id in candidates: TP
- `candidate_expected` and request_id not in candidates: FN
- `candidate_not_expected` and request_id in candidates: FP
- `candidate_not_expected` and request_id not in candidates: TN
- `unsure`: metric 계산 제외, count만 보고

계산:

- precision = `TP / (TP + FP)`
- recall = `TP / (TP + FN)`
- f1 = harmonic mean of precision and recall
- denominator가 0이면 해당 metric은 `null`

이름은 반드시 "candidate selection precision/recall"로 제한한다. intrusion detection precision/recall 또는 attack detection recall이라고 부르지 않는다.

## Script

스크립트:

- `scripts/eval_prepare_candidate_selection.py`

예시:

```bash
python3 scripts/eval_prepare_candidate_selection.py \
  --labels data/eval/prepare_candidate_selection_minimal.json \
  --analysis-candidates path/to/analysis_candidates.json \
  --filtered-reasons path/to/filtered_reasons.json
```

JSON 출력:

```bash
python3 scripts/eval_prepare_candidate_selection.py \
  --labels data/eval/prepare_candidate_selection_minimal.json \
  --analysis-candidates path/to/analysis_candidates.json \
  --json
```

출력 field:

- `total_labeled`
- `evaluated_count`
- `unsure_count`
- `tp`, `fp`, `fn`, `tn`
- `precision`, `recall`, `f1`
- `false_positives`
- `false_negatives`
- `true_negatives_with_filtered_reasons`
- `warnings`

Validation:

- label file의 missing `request_id`는 error
- duplicate label `request_id`는 error
- forbidden/unsupported `human_label`은 error
- candidate artifact의 missing `request_id` row는 warning 후 metric에서 무시

## filtered_reasons join

`--filtered-reasons`가 제공되면 FN과 filtered reason이 있는 TN에 `reason`/`reason_detail`을 붙인다. 이는 "왜 candidate가 아니었는지"를 운영자가 확인하기 위한 설명 보조 정보다.

이 join도 benign/normal 판정으로 해석하면 안 된다.

## 운영 사용 방식

1. 고정된 label dataset을 준비한다.
2. prepare를 실행해 `analysis_candidates.json`과 가능하면 `filtered_reasons.json`을 만든다.
3. eval script를 실행한다.
4. TP/FP/FN/TN과 false positive/false negative 목록을 검토한다.
5. prepare logic 변경 PR에서는 metric 변화와 false list 변화를 함께 확인한다.

이 평가는 regression guard로 사용한다. 작은 데이터셋 점수만으로 policy 품질을 일반화하지 않는다.

## Smoke result: minimal manual labels against actual run artifact

2026-06-06에 실제 run artifact를 대상으로 스크립트 smoke를 수행했다.

Input:

- labels: `data/eval/prepare_candidate_selection_minimal.json`
- analysis candidates: `runs/jobs/12/analysis_candidates.json`
- filtered reasons: `runs/jobs/12/filtered_reasons.json`

Command:

```bash
python3 scripts/eval_prepare_candidate_selection.py \
  --labels data/eval/prepare_candidate_selection_minimal.json \
  --analysis-candidates runs/jobs/12/analysis_candidates.json \
  --filtered-reasons runs/jobs/12/filtered_reasons.json \
  --json
```

Result:

- `candidate_count`: 5
- `total_labeled`: 30
- `evaluated_count`: 26
- `unsure_count`: 4
- `tp`: 0
- `fp`: 0
- `fn`: 14
- `tn`: 12
- `precision`: `null`
- `recall`: 0.0
- `f1`: `null`
- `warnings`: none

False positives:

- none

False negatives:

- `eval_req_001`: `xss_probe`
- `eval_req_002`: `sqli_probe`
- `eval_req_003`: `path_traversal_probe`
- `eval_req_004`: `sensitive_path_probe`
- `eval_req_005`: `auth_behavior_signal`
- `eval_req_006`: `protocol_anomaly_signal`
- `eval_req_007`: `sensitive_path_probe`
- `eval_req_008`: `sqli_probe`
- `eval_req_009`: `path_traversal_probe`
- `eval_req_010`: `sensitive_path_probe`
- `eval_req_011`: `protocol_anomaly_signal`
- `eval_req_012`: `sensitive_path_probe`
- `eval_req_013`: `protocol_anomaly_signal`
- `eval_req_014`: `path_traversal_probe`

Interpretation:

- This is a script smoke only prepare candidate selection result, not an intrusion detection success metric.
- The minimal label dataset currently uses `minimal_manual_fixture` request IDs, while `runs/jobs/12` contains actual run request IDs. Therefore the score mainly confirms script execution, artifact parsing, and guardrail reporting against a real run artifact.
- `candidate_expected` does not mean attack success.
- `candidate_not_expected` does not mean benign/normal.
- This smoke does not evaluate Stage1/Stage2 accuracy.

## Metric result: jobs/12 request-id aligned labelset

2026-06-06에 `runs/jobs/12` 실제 request_id를 사용하는 small labelset을 추가하고, 같은 run artifact를 대상으로 candidate selection metric을 산출했다.

Input:

- labels: `data/eval/prepare_candidate_selection_jobs12.json`
- analysis candidates: `runs/jobs/12/analysis_candidates.json`
- filtered reasons: `runs/jobs/12/filtered_reasons.json`

Labelset:

- `total_labeled`: 14
- `candidate_expected`: 5
- `candidate_not_expected`: 8
- `unsure`: 1
- `unsure` row: `/missing-file` 404, `insufficient_log_evidence`

Command:

```bash
python3 scripts/eval_prepare_candidate_selection.py \
  --labels data/eval/prepare_candidate_selection_jobs12.json \
  --analysis-candidates runs/jobs/12/analysis_candidates.json \
  --filtered-reasons runs/jobs/12/filtered_reasons.json \
  --json
```

Result:

- `candidate_count`: 5
- `total_labeled`: 14
- `evaluated_count`: 13
- `unsure_count`: 1
- `tp`: 5
- `fp`: 0
- `fn`: 0
- `tn`: 8
- `precision`: 1.0
- `recall`: 1.0
- `f1`: 1.0
- `warnings`: none

False positives:

- none

False negatives:

- none

Interpretation:

- This is a prepare candidate selection metric for one small project-local run artifact, not an intrusion detection success metric.
- The labels evaluate request inclusion in `analysis_candidates.json`; they do not evaluate Stage1/Stage2 accuracy.
- `candidate_expected` does not mean attack success, browser execution, data disclosure, or compromise.
- `candidate_not_expected` does not mean benign/normal.
- `filtered_reasons.json` rows are used only to explain candidate exclusion, not to assert harmlessness.

## 후속 TODO

- 기존 prepare regression fixture에서 request_id 안정성을 확보해 label source를 실제 fixture와 연결한다.
- 라벨셋을 30개에서 50-100개로 확대한다.
- reason taxonomy별 최소 coverage를 둔다.
- prepare output을 자동 생성하고 eval까지 실행하는 CI smoke command를 검토한다.
- false negative의 filtered reason 분포를 summary로 추가할지 검토한다.
- Stage1/Stage2 accuracy 평가는 별도 문서/별도 라벨 정책으로 분리한다.
- Stage2 report wording은 `candidate_not_expected != benign/normal` 정책을 따라야 하며, candidate-excluded/baseline-like/context-only baseline-like 표현을 사용한다.

## Do-not-change list

이번 평가 기반 도입은 다음을 변경하지 않는다.

- prepare candidate selection logic
- Stage1/Stage2 prompt/schema
- viewer_payload schema
- DB schema
- Web UI
- attack success / compromise success label policy
- benign / normal 확정 label policy
