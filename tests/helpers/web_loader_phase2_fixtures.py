from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


FIXTURE_TIMESTAMP = "2026-05-10T00:00:00+09:00"


def build_web_loader_phase2_fixture_root(tmp_path: Path) -> Path:
    """
    Create the minimal Phase 2C fixture tree under tmp_path and return project_root-like root.
    Expected structure:
      <tmp_path>/web_loader_phase2/
        runs/
          run_dir_valid_basic/
          run_dir_missing_viewer_payload/
          run_dir_malformed_viewer_payload/
          run_dir_malformed_manifest/
          run_dir_missing_stage2_report/
        archive/
          flat_legacy_without_viewer_payload/
    """
    root = tmp_path / "web_loader_phase2"
    (root / "runs").mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(parents=True, exist_ok=True)

    write_run_dir_case(root, "run_dir_valid_basic")
    write_run_dir_case(root, "run_dir_missing_viewer_payload", include_payload=False)
    write_run_dir_case(root, "run_dir_malformed_viewer_payload", malformed_payload=True)
    write_run_dir_case(root, "run_dir_malformed_manifest", malformed_manifest=True)
    write_run_dir_case(root, "run_dir_missing_stage2_report", include_stage2=False)
    write_legacy_archive_case(root)
    return root


def write_run_dir_case(
    root: Path,
    run_id: str,
    *,
    include_stage2: bool = True,
    include_payload: bool = True,
    malformed_manifest: bool = False,
    malformed_payload: bool = False,
) -> Path:
    """
    Create a single run_dir fixture case.
    """
    run_dir = root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = run_dir / "manifest.json"
    if malformed_manifest:
        manifest_path.write_text("{malformed_manifest_json", encoding="utf-8")
    else:
        _write_json(
            manifest_path,
            {
                "run_id": run_id,
                "run_dir_enabled": True,
                "run_dir": str(run_dir),
                "run_dir_files": {
                    "manifest": "manifest.json",
                    "stage2_report": "stage2_report.json" if include_stage2 else None,
                    "stage2_report_markdown": "stage2_report.md",
                    "viewer_payload": "viewer_payload.json" if include_payload else None,
                    "export": "export.json",
                    "noise_summary": "noise_summary.json",
                },
                "meta": {
                    "generated_at": FIXTURE_TIMESTAMP,
                    "provider": "openai",
                    "selected_model": "fixture-model",
                },
            },
        )

    (run_dir / "stage2_report.md").write_text("# Fixture report\n", encoding="utf-8")
    _write_json(run_dir / "export.json", {"meta": {"fixture": True}})
    _write_json(run_dir / "noise_summary.json", {"noise_count": 0})

    if include_stage2:
        _write_json(run_dir / "stage2_report.json", _stage2_report_payload())

    if include_payload:
        payload_path = run_dir / "viewer_payload.json"
        if malformed_payload:
            payload_path.write_text("{malformed_viewer_payload_json", encoding="utf-8")
        else:
            _write_json(payload_path, _viewer_payload())

    return run_dir


def write_legacy_archive_case(root: Path) -> Path:
    """
    Create a legacy flat report fixture that must be excluded by default scan.
    """
    archive_root = root / "archive" / "flat_legacy_without_viewer_payload" / "reports"
    archive_root.mkdir(parents=True, exist_ok=True)
    _write_json(archive_root / "legacy_stage2_report.json", _stage2_report_payload())
    return archive_root.parent


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _stage2_report_payload() -> Dict[str, Any]:
    return {
        "meta": {
            "provider": "openai",
            "selected_model": "fixture-model",
            "generated_at": FIXTURE_TIMESTAMP,
            "source_window": {
                "start": "2026-05-10T00:00:00+09:00",
                "end_exclusive": "2026-05-10T00:05:00+09:00",
            },
        },
        "report": {
            "overall_assessment": "Potential suspicious activity was observed within Apache access log fields only. No successful compromise is inferred.",
            "executive_summary": [],
            "key_findings": [],
            "notable_incidents": [
                {
                    "incident_ref": "fixture-incident-001",
                    "severity": "medium",
                    "verdict": "suspicious",
                    "title": "Fixture suspicious request pattern",
                    "why_it_matters": "The request pattern is used only as a loader fixture and does not imply successful exploitation.",
                    "src_ip": "192.0.2.10",
                    "request_count": 1,
                    "recommended_action": "Review the request pattern using Apache log evidence only.",
                }
            ],
            "notable_source_ips": [],
            "recommended_actions": [],
            "confidence_and_limitations": "Fixture data is limited to Apache access log style fields. No browser execution, response body, DB result, or compromise success is inferred.",
            "presentation_takeaway": "Loader fixture only.",
        },
    }


def _viewer_payload() -> Dict[str, Any]:
    return {
        "schema_version": "viewer_payload.v1",
        "meta": {
            "generated_at": FIXTURE_TIMESTAMP,
            "source_of_truth": {
                "stage2_report": "stage2_report.json",
            },
        },
        "summary": {
            "report_title": "Fixture report",
            "overall_assessment": "Fixture payload for Web UI loader testing.",
            "finding_count": 1,
            "context_count": 1,
            "supporting_event_count": 0,
        },
        "report": {
            "report_title": "Fixture report",
            "overall_assessment": "Fixture payload for Web UI loader testing.",
        },
        "findings": [
            {
                "request_id": "fixture-request-001",
                "log_time": "2026-05-10T00:01:00+09:00",
                "severity": "medium",
                "verdict": "suspicious",
                "category": "sqli_candidate",
                "src_ip": "192.0.2.10",
                "method": "GET",
                "uri": "/search?q=test",
                "status_code": 200,
                "confidence": "medium",
                "reasoning_summary": "Fixture-only suspicious request pattern. No success is inferred.",
                "evidence_fields": ["method", "uri", "status_code"],
                "reason_hints": ["fixture_hint"],
                "recommended_actions": ["Review Apache log evidence only."],
            }
        ],
        "contexts": [
            {
                "context_type": "probing_sequence",
                "src_ip": "192.0.2.10",
                "request_count": 1,
                "context_only": True,
                "should_promote_to_candidate": False,
                "reason_hints": ["fixture_context"],
            }
        ],
        "supporting_events": [],
        "integrity": {
            "warnings": [],
        },
        "policies": {
            "guardrails": ["Apache logs-only", "No success inferred"],
        },
    }
