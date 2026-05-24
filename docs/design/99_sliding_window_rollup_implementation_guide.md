# 99_sliding_window_rollup_implementation_guide

- 문서 상태: 구현 가이드 / v1 정렬본
- 기준 시점: 2026-05-24
- 기준 문서: `docs/design/99_sliding_window_rollup_input_review.md`
- 대상 모듈: `src/sliding_window_rollup.py`

## 1. 구현 목표

`src/sliding_window_rollup.py`는 여러 `window_summary.json`을 읽어 summary-only rollup artifact를 생성한다.

출력:

```text
data/rollups/<date>/<rollup_id>/
  ├── rollup_input.json
  ├── dedup_candidates.json
  └── rollup_summary.json
```

v1은 Stage1/Stage2를 실행하지 않는다.

## 2. 핵심 제한

```text
- raw log 재분석 금지
- raw_request/raw query string 복제 금지
- 새 score 생성 금지
- 새 verdict_hint 생성 금지
- confidence_score / threat_level 생성 금지
- uri_family / low_and_slow를 Stage1 후보로 승격 금지
- false_positive_review_candidates 자동 필터링 금지
```

## 3. 파일명

초안의 `rolling_window_rollup.py`는 사용하지 않는다.

```text
src/sliding_window_rollup.py
tests/test_sliding_window_rollup.py
```

## 4. 함수 구조

```python
from pathlib import Path
from typing import Any, Dict, List, Tuple


def discover_window_summary_paths(
    *,
    work_dir: Path,
    analysis_start: str,
    analysis_end: str,
    window_minutes: int,
    stride_minutes: int,
) -> List[Path]:
    """analysis range에 해당하는 window_summary.json 후보 경로를 계산한다."""
    raise NotImplementedError


def load_window_summaries(
    window_summary_paths: List[Path],
    *,
    strict: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """window_summary.json들을 로드하고 window load status를 반환한다."""
    raise NotImplementedError


def merge_candidate_index(
    window_summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """각 window의 candidate_index를 평탄화한다. request_id가 없어도 후보를 버리지 않는다."""
    raise NotImplementedError


def dedup_candidates_by_request_id(
    candidates: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """request_id가 같은 후보만 merge한다. fallback duplicate는 표시만 한다."""
    raise NotImplementedError


def aggregate_distributions(
    window_summaries: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """window별 distributions를 합산한다."""
    raise NotImplementedError


def build_uri_family_hints(
    candidates: List[Dict[str, Any]],
    *,
    min_occurrences: int = 3,
) -> List[Dict[str, Any]]:
    """uri family 관찰 hint를 만든다. analysis candidate를 만들지 않는다."""
    raise NotImplementedError


def build_low_and_slow_hints(
    candidates: List[Dict[str, Any]],
    *,
    min_windows: int = 3,
    min_inter_request_gap_sec: int = 60,
) -> List[Dict[str, Any]]:
    """low-and-slow 관찰 hint를 만든다. analysis candidate를 만들지 않는다."""
    raise NotImplementedError


def build_rollup_input(
    *,
    rollup_id: str,
    analysis_start: str,
    analysis_end: str,
    timezone: str,
    window_summaries: List[Dict[str, Any]],
    window_load_status: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """sliding_window_rollup_input_v1 객체를 생성한다."""
    raise NotImplementedError
```

## 5. candidate merge 규칙

window summary의 후보:

```json
{
  "request_id": "req_abc",
  "src_ip": "192.168.56.1",
  "method": "GET",
  "uri": "/admin/config.php",
  "status_code": 403,
  "score": 85,
  "verdict_hint": "sensitive_path_probe",
  "reason_hint_prefixes": ["sensitive_path_probe"]
}
```

rollup candidate_index 항목:

```json
{
  "request_id": "req_abc",
  "src_ip": "192.168.56.1",
  "method": "GET",
  "uri": "/admin/config.php",
  "status_code": 403,
  "score": 85,
  "verdict_hint": "sensitive_path_probe",
  "reason_hint_prefixes": ["sensitive_path_probe"],
  "source_window_ids": ["sw_0200_0300"],
  "aggregation_type": "single_window_existing_candidate"
}
```

주의:

```text
- score는 prepare 값 그대로 둔다.
- verdict_hint는 prepare/window_summary 값 그대로 둔다.
- rollup 단계에서 새 verdict_hint를 만들지 않는다.
```

## 6. request_id dedup 예시

```python
def dedup_candidates_by_request_id(candidates):
    by_request_id = {}
    without_request_id = []
    duplicate_request_ids = []

    for cand in candidates:
        req_id = str(cand.get("request_id") or "").strip()

        if not req_id:
            preserved = dict(cand)
            preserved["dedup_status"] = "preserved_missing_request_id"
            without_request_id.append(preserved)
            continue

        if req_id not in by_request_id:
            kept = dict(cand)
            kept["source_window_ids"] = sorted(set(cand.get("source_window_ids", [])))
            kept["aggregation_type"] = "single_window_existing_candidate"
            by_request_id[req_id] = kept
            continue

        kept = by_request_id[req_id]
        kept_windows = set(kept.get("source_window_ids", []))
        kept_windows.update(cand.get("source_window_ids", []))
        kept["source_window_ids"] = sorted(kept_windows)
        kept["aggregation_type"] = "cross_window_same_request_id"

        duplicate_request_ids.append({
            "request_id": req_id,
            "source_window_ids": sorted(kept_windows),
            "action": "merged_by_request_id"
        })

    deduped = list(by_request_id.values()) + without_request_id

    report = {
        "primary_key": "request_id",
        "input_count": len(candidates),
        "output_count": len(deduped),
        "removed_by_request_id": len(candidates) - len(deduped),
        "missing_request_id_preserved": len(without_request_id),
        "duplicate_request_ids": duplicate_request_ids,
    }

    return deduped, report
```

## 7. fallback duplicate

fallback key는 제거에 쓰지 않는다.

```json
{
  "fallback_key": "192.168.56.1|GET|/admin|404|sensitive_path_probe",
  "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
  "action": "marked_only_not_removed"
}
```

## 8. uri_family hint

초안의 uri_family candidate 생성 로직은 v1에서 사용하지 않는다.  
대신 hint만 만든다.

```json
{
  "src_ip": "192.168.56.1",
  "uri_prefix": "/api/v1/admin/*",
  "uri_variants": ["/api/v1/admin/users", "/api/v1/admin/roles"],
  "occurrences": 3,
  "source_window_ids": ["sw_0200_0300", "sw_0300_0400"],
  "derived_from_request_ids": ["req_1", "req_2", "req_3"],
  "hint_only": true
}
```

주의:

```text
- score 없음
- verdict_hint 없음
- candidate_id 없음
- analysis_candidates에 추가하지 않음
```

## 9. low_and_slow hint

출력:

```json
{
  "src_ip": "192.168.56.2",
  "reason_hint_prefix": "sqli_hint",
  "source_window_ids": [
    "sw_0200_0300",
    "sw_0300_0400",
    "sw_0400_0500"
  ],
  "occurrences": 3,
  "derived_from_request_ids": ["req_a", "req_b", "req_c"],
  "hint_only": true
}
```

주의:

```text
- low_and_slow_candidate=true를 candidate_index에 넣지 않는다.
- score/verdict_hint를 만들지 않는다.
- Stage1 후보가 아니라 rollup_context hint다.
```

## 10. rollup_input 생성

```python
def build_rollup_input(...):
    merged_candidates = merge_candidate_index(window_summaries)
    deduped_candidates, dedup_report = dedup_candidates_by_request_id(merged_candidates)

    distributions = aggregate_distributions(window_summaries)
    uri_family_hints = build_uri_family_hints(deduped_candidates)
    low_and_slow_hints = build_low_and_slow_hints(deduped_candidates)

    return {
        "schema": "sliding_window_rollup_input_v1",
        "rollup": {
            "rollup_id": rollup_id,
            "start": analysis_start,
            "end_exclusive": analysis_end,
            "timezone": timezone,
        },
        "source_windows": window_load_status,
        "counts": {
            "window_count": len(window_load_status),
            "windows_successfully_loaded": len(window_summaries),
            "candidate_rows_total": len(merged_candidates),
            "candidate_index_count": len(deduped_candidates),
            "dedup_removed_by_request_id": dedup_report["removed_by_request_id"],
        },
        "dedup": dedup_report,
        "distributions": distributions,
        "candidate_index": deduped_candidates,
        "rollup_context": {
            "uri_family_hints": uri_family_hints,
            "low_and_slow_hints": low_and_slow_hints,
            "notes": [
                "context_only_no_candidate_promotion",
                "no_new_security_verdict"
            ],
        },
        "guardrails": {
            "summary_only": True,
            "apache_logs_only": True,
            "no_new_security_verdict": True,
            "no_success_inference": True,
            "no_body_inference": True,
            "no_context_promotion": True,
            "no_policy_recalculation": True,
            "preserve_prepare_scores": True,
        },
    }
```

## 11. CLI 옵션 후보

```text
--work-dir
--analysis-start
--analysis-end
--window-minutes
--stride-minutes
--out-dir
--timezone Asia/Seoul
--strict
--pretty
--min-uri-family-occurrences 3
--min-low-and-slow-windows 3
--min-inter-request-gap-sec 60
```

## 12. 테스트 전략

```text
test_request_id_dedup_merges_same_request_across_windows
test_missing_request_id_is_preserved
test_fallback_duplicate_is_marked_not_removed
test_uri_family_hint_does_not_increase_candidate_index
test_low_and_slow_hint_does_not_increase_candidate_index
test_no_new_score_or_verdict_hint
test_missing_window_is_recorded
```

## 13. 완료 기준

```text
- py_compile 통과
- tests/test_sliding_window_rollup.py 통과
- fixture 기반 rollup_input.json 생성
- candidate_index count가 derived hint 때문에 증가하지 않음
- dedup report가 request_id merge를 설명함
- missing window 상태가 source_windows에 남음
```
