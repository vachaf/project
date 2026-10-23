"""Select artifact timestamps without inventing times or conflating sources."""
from typing import Any, Dict


def provided_time(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() not in {"", "unknown", "n/a", "-"}


def viewer_timestamp_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    result = {
        "generated_at": None,
        "generated_at_source": "실제 생성 시각 미제공",
        "viewer_generated_at": meta.get("generated_at") if provided_time(meta.get("generated_at")) else None,
        "stage2_generated_at": None,
        "stage2_generated_at_source": "실제 Stage2 보고서 시각 미제공",
    }
    if provided_time(meta.get("generated_at")):
        result["generated_at"] = meta["generated_at"]
        result["generated_at_source"] = "payload.meta.generated_at (Viewer 자료 생성 시각)"
    elif provided_time(summary.get("generated_at")):
        result["generated_at"] = summary["generated_at"]
        result["generated_at_source"] = "summary.generated_at (기존 summary 제공 시각)"

    if provided_time(meta.get("stage2_generated_at")):
        result["stage2_generated_at"] = meta["stage2_generated_at"]
        result["stage2_generated_at_source"] = "payload.meta.stage2_generated_at ← stage2_report.meta.generated_at"
    elif provided_time(report.get("generated_at")):
        result["stage2_generated_at"] = report["generated_at"]
        result["stage2_generated_at_source"] = "payload.report.generated_at"
    return result
