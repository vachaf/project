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
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ALLOWED_MODES = {"routine", "milestone", "presentation"}
ALLOWED_STOP_AFTER = {"prepare", "stage1", "stage2"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM 분석 파이프라인 실행기")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--export-input", help="export_db_logs_cli.py 결과 JSON 에서 시작")
    input_group.add_argument("--llm-input", help="prepare_llm_input.py 결과 <base>_llm_input.json 에서 시작")
    input_group.add_argument("--stage1-results", help="llm_stage1_classifier.py 결과 <base>_stage1_results.json 에서 시작")

    parser.add_argument("--scripts-dir", default=None, help="개별 파이프라인 스크립트가 있는 디렉터리 (기본값: 현재 스크립트 디렉터리)")
    parser.add_argument("--work-dir", default=".", help="작업 루트 디렉터리")
    parser.add_argument("--processed-dir", default=None, help="중간 산출물 디렉터리 (기본값: <work-dir>/processed)")
    parser.add_argument("--reports-dir", default=None, help="최종 보고서 디렉터리 (기본값: <work-dir>/reports)")
    parser.add_argument("--base-name", default=None, help="산출물 파일명 접두어")
    parser.add_argument("--mode", default="routine", choices=sorted(ALLOWED_MODES), help="모델 사용 모드")
    parser.add_argument("--stop-after", default="stage2", choices=sorted(ALLOWED_STOP_AFTER), help="어느 단계까지 실행할지 지정")

    parser.add_argument("--prepare-min-score", type=int, default=4, help="prepare_llm_input.py --min-score")
    parser.add_argument("--prepare-min-repeat-aggregate", type=int, default=3, help="prepare_llm_input.py --min-repeat-aggregate")
    parser.add_argument("--prepare-source-tables", default="security", help="prepare 단계에서 포함할 source table 쉼표 목록 (기본값: security)")
    parser.add_argument("--write-filtered-out", action="store_true", help="prepare 단계에서 filtered_out_rows 저장")

    parser.add_argument("--stage1-model", default=None, help="1차 분류 모델 override")
    parser.add_argument("--stage1-candidate-limit", type=int, default=0, help="1차 분류 상위 N개 후보만 처리 (0은 전체)")
    parser.add_argument("--stage1-max-evidence-items", type=int, default=8, help="1차 분류 evidence_fields 최대 개수")
    parser.add_argument("--stage1-sleep-sec", type=float, default=0.0, help="1차 분류 API 호출 사이 대기 시간")
    parser.add_argument("--stage1-timeout-sec", type=int, default=180, help="1차 분류 HTTP 타임아웃")

    parser.add_argument("--stage2-model", default=None, help="2차 보고서 모델 override")
    parser.add_argument("--stage2-top-incidents", type=int, default=12, help="2차 보고서 상위 incident 수")
    parser.add_argument("--stage2-top-noise-groups", type=int, default=8, help="2차 보고서 상위 noise group 수")
    parser.add_argument("--stage2-top-ips", type=int, default=8, help="2차 보고서 상위 src_ip 수")
    parser.add_argument("--stage2-timeout-sec", type=int, default=180, help="2차 보고서 HTTP 타임아웃")
    parser.add_argument("--known-asset-ips", default=os.getenv("KNOWN_ASSET_IPS", ""), help="stage2 에 전달할 known asset IP 쉼표 목록")

    parser.add_argument("--store", action="store_true", help="Responses API store=true 사용")
    parser.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh"], default="none", help="선택적 reasoning effort")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    parser.add_argument("--dry-run", action="store_true", help="실제 API 호출 없이 dry-run 산출물만 생성")
    parser.add_argument("--keep-going", action="store_true", help="오류가 나도 가능한 범위까지 manifest 를 남기고 종료")
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
        "filtered_out_rows": processed_dir / f"{base_name}_filtered_out_rows.json" if write_filtered_out else None,
        "stage1_results": processed_dir / f"{base_name}_stage1_results.json",
        "stage1_errors": processed_dir / f"{base_name}_stage1_errors.json",
        "stage2_report_input": reports_dir / f"{base_name}_stage2_report_input.json",
        "stage2_report_json": reports_dir / f"{base_name}_stage2_report.json",
        "stage2_report_md": reports_dir / f"{base_name}_stage2_report.md",
        "stage2_report_error": reports_dir / f"{base_name}_stage2_report_error.json",
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
    processed_dir = Path(args.processed_dir).expanduser().resolve() if args.processed_dir else work_dir / "processed"
    reports_dir = Path(args.reports_dir).expanduser().resolve() if args.reports_dir else work_dir / "reports"
    manifest_path = work_dir / "pipeline_manifest.json"

    work_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    prepare_script = ensure_script(scripts_dir / "prepare_llm_input.py")
    stage1_script = ensure_script(scripts_dir / "llm_stage1_classifier.py")
    stage2_script = ensure_script(scripts_dir / "llm_stage2_reporter.py")

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

    paths = build_paths(base_name, processed_dir=processed_dir, reports_dir=reports_dir, write_filtered_out=args.write_filtered_out)

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
            "prepare_source_tables": args.prepare_source_tables,
            "known_asset_ips": args.known_asset_ips,
            "python": sys.executable,
        },
        "inputs": {
            "source_input": source_input,
            "base_name": base_name,
        },
        "steps": [],
        "artifacts": {k: (str(v) if v else None) for k, v in paths.items()},
    }

    rc = 0

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
                "--include-source-tables", args.prepare_source_tables,
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
                dump_json(manifest_path, manifest, pretty=args.pretty)
                print(f"\n[OK] manifest: {manifest_path}")
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
                dump_json(manifest_path, manifest, pretty=args.pretty)
                print(f"\n[OK] manifest: {manifest_path}")
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
        if paths["llm_input"] and Path(paths["llm_input"]).exists():
            cmd.extend(["--llm-input", str(paths["llm_input"])])
        if paths["stage1_errors"] and Path(paths["stage1_errors"]).exists():
            cmd.extend(["--stage1-errors", str(paths["stage1_errors"])])
        if args.known_asset_ips:
            cmd.extend(["--known-asset-ips", args.known_asset_ips])
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

    except Exception as e:
        manifest["error"] = {
            "type": e.__class__.__name__,
            "message": str(e),
        }
        if rc == 0:
            rc = 1
        if not args.keep_going:
            dump_json(manifest_path, manifest, pretty=args.pretty)
            print(f"\n[ERROR] {e}", file=sys.stderr)
            print(f"[INFO] manifest: {manifest_path}")
            return rc

    dump_json(manifest_path, manifest, pretty=args.pretty)

    print("\n[OK] pipeline complete")
    print(f"[OK] manifest:            {manifest_path}")
    if paths["llm_input"]:
        print(f"[OK] llm_input:           {paths['llm_input']}")
    if paths["stage1_results"]:
        print(f"[OK] stage1_results:      {paths['stage1_results']}")
    if paths["stage2_report_md"]:
        print(f"[OK] stage2_report_md:    {paths['stage2_report_md']}")
    if paths["stage2_report_json"]:
        print(f"[OK] stage2_report_json:  {paths['stage2_report_json']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
