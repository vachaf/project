#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
웹 로그 LLM 분석 파이프라인 실행기.

역할
- export JSON -> prepare_llm_input.py -> llm_stage1_classifier.py -> llm_stage2_reporter.py
  흐름을 한 번에 실행한다.
- 이미 생성된 llm_input.json 또는 stage1_results.json 에서도 재개할 수 있다.
- routine / milestone / presentation 모드와 dry-run 흐름을 한 번에 제어한다.
- 실행 결과 manifest 를 남겨 산출물 경로를 한눈에 확인할 수 있게 한다.

권장 위치
- 별도 분석 VM 의 파이프라인 디렉터리
- 예: /opt/web_log_analysis/src/run_analysis_pipeline.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from llm_client import SUPPORTED_PROVIDERS, normalize_provider
from llm_stage2_reporter import resolve_known_asset_ips

ALLOWED_MODES = {"routine", "milestone", "presentation"}
ALLOWED_STOP_AFTER = {"prepare", "stage1", "stage2"}
KNOWN_SOURCE_TABLES = ["security", "access", "error"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "LLM 분석 파이프라인 실행기\n"
            "기본 권장 흐름: --export-input 1개로 prepare -> stage1 -> stage2 one-shot 실행"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    input_group_container = parser.add_argument_group("Input")
    input_group = input_group_container.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--export-input",
        help="사용자용 기본 입력: export_db_logs_cli.py가 만든 export JSON에서 전체 pipeline 실행",
    )
    input_group.add_argument(
        "--llm-input",
        help="[advanced/resume] prepare 결과 <base>_llm_input.json에서 재개",
    )
    input_group.add_argument(
        "--stage1-results",
        help="[advanced/resume] Stage1 결과 <base>_stage1_results.json에서 재개",
    )

    paths_output = parser.add_argument_group("Paths / output")
    paths_output.add_argument(
        "--scripts-dir",
        default=None,
        help="개별 파이프라인 스크립트 디렉터리 (기본값: 현재 스크립트 디렉터리)",
    )
    paths_output.add_argument(
        "--work-dir",
        default=".",
        help="작업 루트 디렉터리 (기본 output root, 기본값: 현재 디렉터리)",
    )
    paths_output.add_argument(
        "--processed-dir",
        default=None,
        help="중간 산출물 디렉터리 override (기본값: <work-dir>/data/processed)",
    )
    paths_output.add_argument(
        "--reports-dir",
        default=None,
        help="최종 보고서 디렉터리 override (기본값: <work-dir>/reports)",
    )
    paths_output.add_argument(
        "--base-name",
        default=None,
        help="산출물 파일명 접두어 (미지정 시 입력 파일 stem 기반 자동 추론)",
    )
    paths_output.add_argument(
        "--run-dir",
        default=None,
        help="opt-in run 단위 병행 산출물 디렉터리 (미지정 시 비활성)",
    )

    run_mode = parser.add_argument_group("Run mode")
    run_mode.add_argument("--mode", default="routine", choices=sorted(ALLOWED_MODES), help="모델 사용 모드")
    run_mode.add_argument("--stop-after", default="stage2", choices=sorted(ALLOWED_STOP_AFTER), help="어느 단계까지 실행할지 지정")
    run_mode.add_argument(
        "--llm-provider",
        choices=SUPPORTED_PROVIDERS,
        default=None,
        help="stage1/stage2 LLM provider (기본값: LLM_PROVIDER 또는 openai)",
    )
    run_mode.add_argument(
        "--known-asset-ips",
        default=None,
        help="stage2 에 전달할 known asset IP 쉼표 목록 (.env 의 KNOWN_ASSET_IPS fallback 사용 가능)",
    )
    run_mode.add_argument("--pretty", action="store_true", help="산출 JSON pretty 출력")
    run_mode.add_argument("--dry-run", action="store_true", help="실제 LLM API 호출 없이 파이프라인 구조/산출물 검증")
    run_mode.add_argument("--keep-going", action="store_true", help="오류가 나도 가능한 범위까지 manifest를 남기고 종료")

    viewer_output = parser.add_argument_group("Viewer payload output")
    viewer_output.add_argument(
        "--viewer-payload",
        dest="viewer_payload",
        action="store_true",
        help="Stage2 이후 Web UI용 viewer_payload 생성 (기본값: enabled)",
    )
    viewer_output.add_argument(
        "--no-viewer-payload",
        dest="viewer_payload",
        action="store_false",
        help="viewer_payload 생성 생략",
    )
    viewer_output.add_argument(
        "--include-raw-log",
        action="store_true",
        help="[debug] viewer_payload에 raw_export raw_log 포함 (기본값: disabled)",
    )

    prepare_advanced = parser.add_argument_group("Prepare advanced options")
    prepare_advanced.add_argument("--prepare-min-score", type=int, default=4, help="prepare_llm_input.py --min-score")
    prepare_advanced.add_argument("--prepare-min-repeat-aggregate", type=int, default=3, help="prepare_llm_input.py --min-repeat-aggregate")
    prepare_advanced.add_argument(
        "--prepare-source-tables",
        default="auto",
        help=(
            "prepare 단계에서 포함할 source table 쉼표 목록 "
            "(기본값: auto, export JSON meta.table_option/counts/data 기반 자동 결정)"
        ),
    )
    prepare_advanced.add_argument("--write-filtered-out", action="store_true", help="prepare 단계에서 filtered_out_rows 저장")

    stage1_advanced = parser.add_argument_group("Stage1 advanced options")
    stage1_advanced.add_argument("--stage1-model", default=None, help="1차 분류 모델 override")
    stage1_advanced.add_argument("--stage1-candidate-limit", type=int, default=0, help="1차 분류 상위 N개 후보만 처리 (0은 전체)")
    stage1_advanced.add_argument("--stage1-max-evidence-items", type=int, default=8, help="1차 분류 evidence_fields 최대 개수")
    stage1_advanced.add_argument("--stage1-sleep-sec", type=float, default=0.0, help="1차 분류 API 호출 사이 대기 시간")
    stage1_advanced.add_argument("--stage1-timeout-sec", type=int, default=180, help="1차 분류 HTTP 타임아웃")

    stage2_advanced = parser.add_argument_group("Stage2 advanced options")
    stage2_advanced.add_argument("--stage2-model", default=None, help="2차 보고서 모델 override")
    stage2_advanced.add_argument("--stage2-top-incidents", type=int, default=12, help="2차 보고서 상위 incident 수")
    stage2_advanced.add_argument("--stage2-top-noise-groups", type=int, default=8, help="2차 보고서 상위 noise group 수")
    stage2_advanced.add_argument("--stage2-top-ips", type=int, default=8, help="2차 보고서 상위 src_ip 수")
    stage2_advanced.add_argument("--stage2-timeout-sec", type=int, default=180, help="2차 보고서 HTTP 타임아웃")

    llm_api_debug = parser.add_argument_group("LLM/API debug options")
    llm_api_debug.add_argument("--store", action="store_true", help="Responses API store=true 사용")
    llm_api_debug.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh"], default="none", help="선택적 reasoning effort")

    parser.epilog = """
Typical usage:
python3 src/run_analysis_pipeline.py \
  --llm-provider openai \
  --export-input data/raw/security_2026-04-30_13-55-00_to_2026-04-30_13-56-00_kst.json \
  --work-dir /opt/web_log_analysis \
  --mode routine \
  --pretty

Default outputs:
data/processed/<base>_llm_input.json
data/processed/<base>_analysis_candidates.json
data/processed/<base>_noise_summary.json
data/processed/<base>_filtered_reasons.json
data/processed/<base>_stage1_results.json
reports/<base>_stage2_report.json
reports/<base>_stage2_report.md
reports/<base>_viewer_payload.json
reports/<base>_pipeline_manifest.json
pipeline_manifest.json

Notes:
- --export-input is the normal one-shot entry point.
- --llm-input and --stage1-results are advanced resume inputs.
- viewer_payload is a read-only Web UI artifact; it does not create new security meaning.
- Web UI remains read-only; this runner does not add a web execution console.
"""
    parser.set_defaults(viewer_payload=True)
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="milliseconds")


def normalize_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return str(Path(path).expanduser().resolve())


def derive_base_name_from_input(path: str, suffixes: List[str]) -> str:
    name = Path(path).stem
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def ensure_script(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"필수 스크립트를 찾을 수 없습니다: {path}")
    return path


def build_paths(base_name: str, processed_dir: Path, reports_dir: Path, write_filtered_out: bool) -> Dict[str, Optional[Path]]:
    return {
        "llm_input": processed_dir / f"{base_name}_llm_input.json",
        "analysis_candidates": processed_dir / f"{base_name}_analysis_candidates.json",
        "noise_summary": processed_dir / f"{base_name}_noise_summary.json",
        "filtered_reasons": processed_dir / f"{base_name}_filtered_reasons.json",
        "filtered_out_rows": processed_dir / f"{base_name}_filtered_out_rows.json" if write_filtered_out else None,
        "stage1_results": processed_dir / f"{base_name}_stage1_results.json",
        "stage1_errors": processed_dir / f"{base_name}_stage1_errors.json",
        "stage2_report_input": reports_dir / f"{base_name}_stage2_report_input.json",
        "stage2_report_json": reports_dir / f"{base_name}_stage2_report.json",
        "stage2_report_md": reports_dir / f"{base_name}_stage2_report.md",
        "stage2_report_error": reports_dir / f"{base_name}_stage2_report_error.json",
        "viewer_payload": reports_dir / f"{base_name}_viewer_payload.json",
        "pipeline_manifest_run": reports_dir / f"{base_name}_pipeline_manifest.json",
    }


def run_cmd(cmd: List[str], step_name: str) -> int:
    print(f"\n[RUN] {step_name}")
    print("      " + " ".join(cmd))
    completed = subprocess.run(cmd)
    return int(completed.returncode)


def dump_json(path: Path, payload: Any, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_table_list(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for key in KNOWN_SOURCE_TABLES:
        if key in values and key not in seen:
            seen.add(key)
            ordered.append(key)
    for key in values:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _resolve_tables_from_all_export(payload: Dict[str, Any]) -> List[str]:
    def _as_count(value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    counts = payload.get("counts")
    if isinstance(counts, dict):
        from_counts = [name for name in KNOWN_SOURCE_TABLES if _as_count(counts.get(name)) > 0]
        if from_counts:
            return from_counts

    data = payload.get("data")
    if isinstance(data, dict):
        from_data = [name for name in KNOWN_SOURCE_TABLES if isinstance(data.get(name), list) and len(data.get(name)) > 0]
        if from_data:
            return from_data
    return []


def resolve_prepare_source_tables(
    source_input: str,
    requested_prepare_source_tables: Optional[str],
    resume_from: str,
) -> tuple[str, str]:
    requested = (requested_prepare_source_tables or "").strip()
    if requested and requested.lower() != "auto":
        return requested, "user_requested_explicit"

    if resume_from != "export":
        return "security", f"resume_from_{resume_from}_fallback_security"

    try:
        payload = load_json(Path(source_input))
    except Exception:
        return "security", "export_json_unreadable_fallback_security"
    if not isinstance(payload, dict):
        return "security", "export_json_not_dict_fallback_security"

    meta = payload.get("meta")
    table_option = ""
    if isinstance(meta, dict):
        table_option = str(meta.get("table_option") or "").strip().lower()

    if table_option in {"security", "access", "error"}:
        return table_option, f"resolved_from_table_option_{table_option}"
    if table_option == "all":
        resolved = _resolve_tables_from_all_export(payload)
        if resolved:
            return ",".join(_normalize_table_list(resolved)), "resolved_from_table_option_all_counts_or_data"
        return "security", "table_option_all_but_empty_fallback_security"

    return "security", "missing_or_unknown_table_option_fallback_security"


def save_manifests(manifest_path: Path, run_manifest_path: Optional[Path], payload: Any, pretty: bool) -> None:
    dump_json(manifest_path, payload, pretty=pretty)
    if run_manifest_path:
        dump_json(run_manifest_path, payload, pretty=pretty)


def build_flat_files(manifest_path: Path, run_manifest_path: Optional[Path], paths: Dict[str, Optional[Path]]) -> Dict[str, Optional[str]]:
    return {
        "export": None,
        "llm_input": str(paths["llm_input"]) if paths.get("llm_input") else None,
        "analysis_candidates": str(paths["analysis_candidates"]) if paths.get("analysis_candidates") else None,
        "filtered_reasons": str(paths["filtered_reasons"]) if paths.get("filtered_reasons") else None,
        "stage1_results": str(paths["stage1_results"]) if paths.get("stage1_results") else None,
        "stage2_report_input": str(paths["stage2_report_input"]) if paths.get("stage2_report_input") else None,
        "stage2_report_json": str(paths["stage2_report_json"]) if paths.get("stage2_report_json") else None,
        "stage2_report_md": str(paths["stage2_report_md"]) if paths.get("stage2_report_md") else None,
        "viewer_payload": str(paths["viewer_payload"]) if paths.get("viewer_payload") else None,
        "noise_summary": str(paths["noise_summary"]) if paths.get("noise_summary") else None,
        "pipeline_manifest_latest": str(manifest_path),
        "pipeline_manifest": str(run_manifest_path) if run_manifest_path else None,
    }


def sync_run_dir_outputs(
    run_dir: Path,
    run_dir_enabled: bool,
    source_input: str,
    resume_from: str,
    manifest: Dict[str, Any],
    paths: Dict[str, Optional[Path]],
    pretty: bool,
) -> Dict[str, Optional[str]]:
    if not run_dir_enabled:
        return {}

    run_dir.mkdir(parents=True, exist_ok=False)
    run_dir_files: Dict[str, Optional[str]] = {
        "export": None,
        "llm_input": None,
        "analysis_candidates": None,
        "filtered_reasons": None,
        "stage1_results": None,
        "stage2_report_input": None,
        "stage2_report_json": None,
        "stage2_report_md": None,
        "viewer_payload": None,
        "noise_summary": None,
        "manifest": str(run_dir / "manifest.json"),
    }

    copy_plan: List[tuple[str, Optional[Path], str]] = [
        ("llm_input", paths.get("llm_input"), "llm_input.json"),
        ("analysis_candidates", paths.get("analysis_candidates"), "analysis_candidates.json"),
        ("filtered_reasons", paths.get("filtered_reasons"), "filtered_reasons.json"),
        ("stage1_results", paths.get("stage1_results"), "stage1_results.json"),
        ("stage2_report_input", paths.get("stage2_report_input"), "stage2_report_input.json"),
        ("stage2_report_json", paths.get("stage2_report_json"), "stage2_report.json"),
        ("stage2_report_md", paths.get("stage2_report_md"), "stage2_report.md"),
        ("viewer_payload", paths.get("viewer_payload"), "viewer_payload.json"),
        ("noise_summary", paths.get("noise_summary"), "noise_summary.json"),
    ]
    if resume_from == "export":
        copy_plan.insert(0, ("export", Path(source_input), "export.json"))

    for alias, src, dst_name in copy_plan:
        if not src or not src.exists():
            continue
        dst = run_dir / dst_name
        shutil.copy2(src, dst)
        run_dir_files[alias] = str(dst)

    dump_json(run_dir / "manifest.json", manifest, pretty=pretty)
    return run_dir_files


def build_stage1_dry_run_placeholder(llm_input_path: Path, output_path: Path, pretty: bool, mode: str, selected_model: Optional[str]) -> None:
    payload = load_json(llm_input_path)
    candidates = payload.get("analysis_candidates") or []
    prepared_meta = payload.get("meta") or {}

    def map_verdict(verdict_hint: str) -> str:
        v = (verdict_hint or "").strip().lower()
        mapping = {
            "sqli": "likely_sqli",
            "xss": "likely_xss",
            "traversal": "likely_path_traversal",
            "cmdi": "likely_command_injection",
            "automation": "suspicious_scan",
            "bruteforce": "suspicious_bruteforce",
            "suspicious": "suspicious_scan",
        }
        return mapping.get(v, "inconclusive")

    def map_severity(score: int) -> str:
        if score >= 10:
            return "high"
        if score >= 7:
            return "medium"
        if score >= 4:
            return "low"
        return "info"

    results = []
    for idx, c in enumerate(candidates):
        score = int(c.get("score") or 0)
        verdict_hint = str(c.get("verdict_hint") or "")
        results.append({
            "candidate_index": idx,
            "request_id": str(c.get("request_id") or ""),
            "model": selected_model or "dry-run-placeholder",
            "source_table": str(c.get("source_table") or ""),
            "log_id": c.get("log_id"),
            "src_ip": str(c.get("src_ip") or ""),
            "uri": str(c.get("uri") or ""),
            "log_time": str(c.get("log_time") or ""),
            "status_code": int(c.get("status_code") or 0),
            "score": score,
            "verdict": map_verdict(verdict_hint),
            "severity": map_severity(score),
            "confidence": "low",
            "false_positive_possible": True,
            "reasoning_summary": "dry-run placeholder generated from analysis_candidates without live API call",
            "evidence_fields": list(c.get("reason_hints") or [])[:8],
            "recommended_actions": ["manual_review"],
        })

    dry_payload = {
        "meta": {
            "generated_at": iso_now(),
            "mode": mode,
            "selected_model": selected_model or "dry-run-placeholder",
            "dry_run": True,
            "source_prepared_at": prepared_meta.get("prepared_at"),
            "source_exported_at": prepared_meta.get("exported_at"),
            "source_query_timezone": prepared_meta.get("query_timezone"),
            "source_window": prepared_meta.get("analysis_window"),
            "source_counts": prepared_meta.get("counts"),
            "processed_candidate_count": len(candidates),
            "success_count": len(results),
            "error_count": 0,
        },
        "results": results,
    }
    dump_json(output_path, dry_payload, pretty=pretty)


def main() -> int:
    args = parse_args()

    scripts_dir = Path(args.scripts_dir).expanduser().resolve() if args.scripts_dir else Path(__file__).resolve().parent
    work_dir = Path(args.work_dir).expanduser().resolve()
    llm_provider = normalize_provider(args.llm_provider)
    known_asset_ips = resolve_known_asset_ips(args.known_asset_ips, extra_env_roots=[work_dir])
    known_asset_ips_csv = ",".join(known_asset_ips)
    processed_dir = Path(args.processed_dir).expanduser().resolve() if args.processed_dir else work_dir / "data" / "processed"
    reports_dir = Path(args.reports_dir).expanduser().resolve() if args.reports_dir else work_dir / "reports"
    manifest_path = work_dir / "pipeline_manifest.json"
    run_dir_path = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
    run_dir_enabled = run_dir_path is not None
    run_id = run_dir_path.name if run_dir_path else None

    if run_dir_enabled and run_dir_path.exists():
        print(
            f"[ERROR] run_dir already exists: {run_dir_path}\n"
            "Use a different --run-dir path. --overwrite is not implemented in Phase 1A.",
            file=sys.stderr,
        )
        return 2

    source_input: str
    if args.export_input:
        source_input = normalize_path(args.export_input)  # type: ignore[assignment]
        base_name = args.base_name or derive_base_name_from_input(source_input, suffixes=[])
        resume_from = "export"
    elif args.llm_input:
        source_input = normalize_path(args.llm_input)  # type: ignore[assignment]
        base_name = args.base_name or derive_base_name_from_input(source_input, suffixes=["_llm_input"])
        resume_from = "llm_input"
    else:
        source_input = normalize_path(args.stage1_results)  # type: ignore[assignment]
        base_name = args.base_name or derive_base_name_from_input(source_input, suffixes=["_stage1_results"])
        resume_from = "stage1_results"

    if not source_input or not Path(source_input).exists():
        print("[ERROR] 시작 입력 파일을 찾을 수 없습니다.", file=sys.stderr)
        return 2

    work_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    prepare_script = ensure_script(scripts_dir / "prepare_llm_input.py")
    stage1_script = ensure_script(scripts_dir / "llm_stage1_classifier.py")
    stage2_script = ensure_script(scripts_dir / "llm_stage2_reporter.py")

    resolved_prepare_source_tables, prepare_resolution_reason = resolve_prepare_source_tables(
        source_input=source_input,
        requested_prepare_source_tables=args.prepare_source_tables,
        resume_from=resume_from,
    )
    print(f"[INFO] prepare_source_tables resolved: {resolved_prepare_source_tables} ({prepare_resolution_reason})")

    paths = build_paths(base_name, processed_dir=processed_dir, reports_dir=reports_dir, write_filtered_out=args.write_filtered_out)
    run_manifest_path = paths["pipeline_manifest_run"]

    if resume_from == "llm_input":
        paths["llm_input"] = Path(source_input)
    elif resume_from == "stage1_results":
        paths["stage1_results"] = Path(source_input)
        inferred_llm_input = Path(source_input).with_name(Path(source_input).name.replace("_stage1_results.json", "_llm_input.json"))
        inferred_stage1_errors = Path(source_input).with_name(Path(source_input).name.replace("_stage1_results.json", "_stage1_errors.json"))
        if inferred_llm_input.exists():
            paths["llm_input"] = inferred_llm_input
        if inferred_stage1_errors.exists():
            paths["stage1_errors"] = inferred_stage1_errors

    manifest: Dict[str, Any] = {
        "meta": {
            "generated_at": iso_now(),
            "resume_from": resume_from,
            "mode": args.mode,
            "stop_after": args.stop_after,
            "dry_run": bool(args.dry_run),
            "store": bool(args.store),
            "reasoning_effort": args.reasoning_effort,
            "scripts_dir": str(scripts_dir),
            "work_dir": str(work_dir),
            "processed_dir": str(processed_dir),
            "reports_dir": str(reports_dir),
            "prepare_source_tables_requested": args.prepare_source_tables,
            "prepare_source_tables_resolved": resolved_prepare_source_tables,
            "prepare_source_tables_resolution_reason": prepare_resolution_reason,
            "prepare_source_tables": resolved_prepare_source_tables,
            "llm_provider": llm_provider,
            "known_asset_ips": known_asset_ips,
            "manifest_role": "latest_and_run_copy",
            "latest_manifest_path": str(manifest_path),
            "run_manifest_path": str(run_manifest_path) if run_manifest_path else None,
            "viewer_payload_enabled": bool(args.viewer_payload),
            "python": sys.executable,
        },
        "inputs": {
            "source_input": source_input,
            "base_name": base_name,
        },
        "run_dir_enabled": run_dir_enabled,
        "run_id": run_id,
        "run_dir": str(run_dir_path) if run_dir_path else None,
        "run_dir_collision_policy": "fail_fast" if run_dir_enabled else None,
        "source_export_path": source_input if resume_from == "export" else None,
        "steps": [],
        "artifacts": {k: (str(v) if v else None) for k, v in paths.items()},
        "flat_files": {},
        "run_dir_files": {},
    }
    manifest["flat_files"] = build_flat_files(manifest_path, run_manifest_path, paths)
    manifest["flat_files"]["export"] = source_input if resume_from == "export" else None

    rc = 0

    def persist_all() -> None:
        save_manifests(manifest_path, run_manifest_path, manifest, pretty=args.pretty)
        if run_dir_enabled and run_dir_path:
            manifest["run_dir_files"] = sync_run_dir_outputs(
                run_dir=run_dir_path,
                run_dir_enabled=run_dir_enabled,
                source_input=source_input,
                resume_from=resume_from,
                manifest=manifest,
                paths=paths,
                pretty=args.pretty,
            )
            save_manifests(manifest_path, run_manifest_path, manifest, pretty=args.pretty)
            dump_json(run_dir_path / "manifest.json", manifest, pretty=args.pretty)

    try:
        if resume_from == "export":
            cmd = [
                sys.executable,
                str(prepare_script),
                "--input", source_input,
                "--out-dir", str(processed_dir),
                "--base-name", base_name,
                "--min-score", str(args.prepare_min_score),
                "--min-repeat-aggregate", str(args.prepare_min_repeat_aggregate),
                "--include-source-tables", resolved_prepare_source_tables,
            ]
            if args.write_filtered_out:
                cmd.append("--write-filtered-out")
            if args.pretty:
                cmd.append("--pretty")
            step_rc = run_cmd(cmd, "prepare")
            manifest["steps"].append({"name": "prepare", "return_code": step_rc, "cmd": cmd})
            if step_rc != 0:
                rc = step_rc
                raise RuntimeError("prepare 단계 실패")
            if args.stop_after == "prepare":
                persist_all()
                print(f"\n[OK] manifest: {manifest_path}")
                if run_manifest_path:
                    print(f"[OK] run_manifest: {run_manifest_path}")
                return 0

        if resume_from in {"export", "llm_input"}:
            llm_input_path = paths["llm_input"]
            if not llm_input_path or not llm_input_path.exists():
                raise FileNotFoundError("llm_input 산출물을 찾을 수 없습니다.")

            cmd = [
                sys.executable,
                str(stage1_script),
                "--input", str(llm_input_path),
                "--out-dir", str(processed_dir),
                "--base-name", base_name,
                "--mode", args.mode,
                "--candidate-limit", str(args.stage1_candidate_limit),
                "--max-evidence-items", str(args.stage1_max_evidence_items),
                "--sleep-sec", str(args.stage1_sleep_sec),
                "--timeout-sec", str(args.stage1_timeout_sec),
                "--reasoning-effort", args.reasoning_effort,
            ]
            if args.llm_provider:
                cmd.extend(["--provider", args.llm_provider])
            if args.stage1_model:
                cmd.extend(["--model", args.stage1_model])
            if args.store:
                cmd.append("--store")
            if args.pretty:
                cmd.append("--pretty")
            if args.dry_run:
                cmd.append("--dry-run")

            step_rc = run_cmd(cmd, "stage1")
            manifest["steps"].append({"name": "stage1", "return_code": step_rc, "cmd": cmd})
            rc = step_rc if step_rc != 0 else rc
            if args.dry_run and step_rc == 0:
                stage1_payload_path = Path(paths["stage1_results"])
                try:
                    stage1_payload = load_json(stage1_payload_path)
                except Exception:
                    stage1_payload = {}
                if not isinstance(stage1_payload, dict) or "results" not in stage1_payload:
                    build_stage1_dry_run_placeholder(
                        llm_input_path=Path(paths["llm_input"]),
                        output_path=stage1_payload_path,
                        pretty=args.pretty,
                        mode=args.mode,
                        selected_model=args.stage1_model,
                    )
                    manifest["steps"][-1]["post_processed"] = "dry_run_placeholder_stage1_results_created"
            if step_rc != 0 and not args.keep_going:
                raise RuntimeError("stage1 단계 실패")
            if args.stop_after == "stage1":
                persist_all()
                print(f"\n[OK] manifest: {manifest_path}")
                if run_manifest_path:
                    print(f"[OK] run_manifest: {run_manifest_path}")
                return rc

        stage1_results_path = paths["stage1_results"]
        if not stage1_results_path or not stage1_results_path.exists():
            raise FileNotFoundError("stage1_results 산출물을 찾을 수 없습니다.")

        cmd = [
            sys.executable,
            str(stage2_script),
            "--stage1-results", str(stage1_results_path),
            "--out-dir", str(reports_dir),
            "--base-name", base_name,
            "--mode", args.mode,
            "--top-incidents", str(args.stage2_top_incidents),
            "--top-noise-groups", str(args.stage2_top_noise_groups),
            "--top-ips", str(args.stage2_top_ips),
            "--timeout-sec", str(args.stage2_timeout_sec),
            "--reasoning-effort", args.reasoning_effort,
        ]
        if args.llm_provider:
            cmd.extend(["--provider", args.llm_provider])
        if paths["llm_input"] and Path(paths["llm_input"]).exists():
            cmd.extend(["--llm-input", str(paths["llm_input"])])
        if paths["stage1_errors"] and Path(paths["stage1_errors"]).exists():
            cmd.extend(["--stage1-errors", str(paths["stage1_errors"])])
        if known_asset_ips_csv:
            cmd.extend(["--known-asset-ips", known_asset_ips_csv])
        if args.stage2_model:
            cmd.extend(["--model", args.stage2_model])
        if args.store:
            cmd.append("--store")
        if args.pretty:
            cmd.append("--pretty")
        if args.dry_run:
            cmd.append("--dry-run")

        step_rc = run_cmd(cmd, "stage2")
        manifest["steps"].append({"name": "stage2", "return_code": step_rc, "cmd": cmd})
        rc = step_rc if step_rc != 0 else rc
        if step_rc != 0 and not args.keep_going:
            raise RuntimeError("stage2 단계 실패")

        if step_rc == 0 and args.viewer_payload:
            viewer_payload_script = ensure_script(scripts_dir / "viewer_payload_builder.py")
            stage2_report_input_path = paths["stage2_report_input"]
            stage2_report_json_path = paths["stage2_report_json"]
            viewer_payload_path = paths["viewer_payload"]
            if not stage2_report_input_path or not stage2_report_input_path.exists():
                viewer_cmd = [
                    sys.executable,
                    str(viewer_payload_script),
                    "--stage2-report-input", str(stage2_report_input_path) if stage2_report_input_path else "",
                    "--out", str(viewer_payload_path) if viewer_payload_path else "",
                ]
                step_rc = 1
                manifest["steps"].append(
                    {
                        "name": "viewer_payload",
                        "return_code": step_rc,
                        "cmd": viewer_cmd,
                        "error": "stage2_report_input 산출물을 찾을 수 없습니다.",
                    }
                )
                rc = step_rc if rc == 0 else rc
                if not args.keep_going:
                    raise RuntimeError("viewer_payload 단계 실패")
                manifest.setdefault("warnings", []).append("viewer_payload skipped because stage2_report_input artifact is missing")
            else:
                viewer_cmd = [
                    sys.executable,
                    str(viewer_payload_script),
                    "--stage2-report", str(stage2_report_json_path),
                    "--stage2-report-input", str(stage2_report_input_path),
                    "--out", str(viewer_payload_path),
                ]
                if paths["stage1_results"] and Path(paths["stage1_results"]).exists():
                    viewer_cmd.extend(["--stage1-results", str(paths["stage1_results"])])
                if paths["llm_input"] and Path(paths["llm_input"]).exists():
                    viewer_cmd.extend(["--llm-input", str(paths["llm_input"])])
                if paths["noise_summary"] and Path(paths["noise_summary"]).exists():
                    viewer_cmd.extend(["--noise-summary", str(paths["noise_summary"])])
                if resume_from == "export" and Path(source_input).exists():
                    viewer_cmd.extend(["--raw-export", source_input])
                if args.include_raw_log:
                    viewer_cmd.append("--include-raw-log")
                if args.pretty:
                    viewer_cmd.append("--pretty")

                step_rc = run_cmd(viewer_cmd, "viewer_payload")
                manifest["steps"].append({"name": "viewer_payload", "return_code": step_rc, "cmd": viewer_cmd})
                rc = step_rc if step_rc != 0 and rc == 0 else rc
                if step_rc != 0:
                    if args.keep_going:
                        manifest.setdefault("warnings", []).append("viewer_payload generation failed")
                    else:
                        raise RuntimeError("viewer_payload 단계 실패")

    except Exception as e:
        manifest["error"] = {
            "type": e.__class__.__name__,
            "message": str(e),
        }
        if rc == 0:
            rc = 1
        if not args.keep_going:
            persist_all()
            print(f"\n[ERROR] {e}", file=sys.stderr)
            print(f"[INFO] manifest: {manifest_path}")
            if run_manifest_path:
                print(f"[INFO] run_manifest: {run_manifest_path}")
            return rc

    persist_all()

    print("\n[OK] pipeline complete")
    print(f"[OK] manifest:            {manifest_path}")
    if run_manifest_path:
        print(f"[OK] run_manifest:        {run_manifest_path}")
    if paths["llm_input"]:
        print(f"[OK] llm_input:           {paths['llm_input']}")
    if paths["stage1_results"]:
        print(f"[OK] stage1_results:      {paths['stage1_results']}")
    if paths["stage2_report_md"]:
        print(f"[OK] stage2_report_md:    {paths['stage2_report_md']}")
    if paths["stage2_report_json"]:
        print(f"[OK] stage2_report_json:  {paths['stage2_report_json']}")
    if args.viewer_payload and paths["viewer_payload"] and Path(paths["viewer_payload"]).exists():
        print(f"[OK] viewer_payload:      {paths['viewer_payload']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
