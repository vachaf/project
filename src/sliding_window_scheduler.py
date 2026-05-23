#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sliding Window scheduler planner.

Phase 1 scope
- Generate deterministic time windows.
- Resolve data/windowed and data/rollups artifact paths.
- Do not run export/prepare/stage1/stage2 yet.
- Do not create runs/ directories.

Later phases may add export/prepare execution, but the scheduler should own the
window/rollup artifact layout instead of requiring operators to manually combine
run_analysis_pipeline.py --processed-dir/--reports-dir/--run-dir options.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Seoul"
DEFAULT_WINDOW_OUTPUT_ROOT = "data/windowed"
DEFAULT_ROLLUP_OUTPUT_ROOT = "data/rollups"


@dataclass(frozen=True)
class WindowPlan:
    index: int
    window_id: str
    start: str
    end: str
    duration_minutes: int
    is_partial: bool
    window_dir: str
    export_path: str
    prepared_dir: str
    llm_input_path: str
    analysis_candidates_path: str
    noise_summary_path: str
    window_summary_path: str


def parse_datetime_text(text: str, tz: ZoneInfo) -> datetime:
    """Parse a KST-oriented datetime string and return a timezone-aware datetime."""
    value = text.strip()
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        )
        dt: Optional[datetime] = None
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            raise ValueError(
                f"invalid datetime: {text!r} "
                "(examples: 2026-05-23 09:00:00, 2026-05-23T09:00:00+09:00)"
            )

    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def fmt_dt(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def resolve_analysis_range(args: argparse.Namespace, tz: ZoneInfo) -> tuple[datetime, datetime]:
    if args.analysis_end:
        analysis_end = parse_datetime_text(args.analysis_end, tz)
    else:
        analysis_end = datetime.now(tz=tz).replace(second=0, microsecond=0)

    if args.analysis_start:
        analysis_start = parse_datetime_text(args.analysis_start, tz)
    else:
        analysis_start = analysis_end - timedelta(hours=args.lookback_hours)

    if analysis_start >= analysis_end:
        raise ValueError("analysis-start must be earlier than analysis-end")
    return analysis_start, analysis_end


def make_window_id(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"sw_{start.strftime('%H%M')}_{end.strftime('%H%M')}"
    return f"sw_{start.strftime('%Y%m%d_%H%M')}_{end.strftime('%Y%m%d_%H%M')}"


def resolve_under_work_dir(work_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (work_dir / path).resolve()


def path_for_display(path: Path, work_dir: Path) -> str:
    try:
        return str(path.relative_to(work_dir))
    except ValueError:
        return str(path)


def build_window_plan(
    *,
    index: int,
    start: datetime,
    end: datetime,
    nominal_window_minutes: int,
    window_output_root: Path,
    work_dir: Path,
) -> WindowPlan:
    window_id = make_window_id(start, end)
    date_dir = start.strftime("%Y-%m-%d")
    window_dir = window_output_root / date_dir / window_id
    prepared_dir = window_dir / "prepared"
    duration_minutes = int((end - start).total_seconds() // 60)

    return WindowPlan(
        index=index,
        window_id=window_id,
        start=fmt_dt(start),
        end=fmt_dt(end),
        duration_minutes=duration_minutes,
        is_partial=duration_minutes != nominal_window_minutes,
        window_dir=path_for_display(window_dir, work_dir),
        export_path=path_for_display(window_dir / "export.json", work_dir),
        prepared_dir=path_for_display(prepared_dir, work_dir),
        llm_input_path=path_for_display(window_dir / "llm_input.json", work_dir),
        analysis_candidates_path=path_for_display(window_dir / "analysis_candidates.json", work_dir),
        noise_summary_path=path_for_display(window_dir / "noise_summary.json", work_dir),
        window_summary_path=path_for_display(window_dir / "window_summary.json", work_dir),
    )


def generate_windows(
    *,
    analysis_start: datetime,
    analysis_end: datetime,
    window_minutes: int,
    stride_minutes: int,
    include_partial_final: bool,
) -> list[tuple[datetime, datetime]]:
    if window_minutes <= 0:
        raise ValueError("window-minutes must be positive")
    if stride_minutes <= 0:
        raise ValueError("stride-minutes must be positive")

    window_delta = timedelta(minutes=window_minutes)
    stride_delta = timedelta(minutes=stride_minutes)

    windows: list[tuple[datetime, datetime]] = []
    current = analysis_start
    while current < analysis_end:
        candidate_end = current + window_delta
        if candidate_end <= analysis_end:
            windows.append((current, candidate_end))
        elif include_partial_final:
            windows.append((current, analysis_end))
        break_if_next = current + stride_delta
        if break_if_next <= current:
            raise ValueError("stride did not advance window start")
        current = break_if_next
    return windows


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    tz = ZoneInfo(args.timezone)
    work_dir = Path(args.work_dir).expanduser().resolve()
    analysis_start, analysis_end = resolve_analysis_range(args, tz)
    window_output_root = resolve_under_work_dir(work_dir, args.window_output_root)
    rollup_output_root = resolve_under_work_dir(work_dir, args.rollup_output_root)

    raw_windows = generate_windows(
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        window_minutes=args.window_minutes,
        stride_minutes=args.stride_minutes,
        include_partial_final=args.include_partial_final,
    )

    window_plans = [
        build_window_plan(
            index=i,
            start=start,
            end=end,
            nominal_window_minutes=args.window_minutes,
            window_output_root=window_output_root,
            work_dir=work_dir,
        )
        for i, (start, end) in enumerate(raw_windows, start=1)
    ]

    warnings: list[str] = []
    if args.window_minutes < 10:
        warnings.append("window-minutes is below the current practical lower bound candidate of 10 minutes")
    if args.mode != "planner":
        warnings.append(f"mode={args.mode!r} is reserved for a later phase and is not implemented yet")

    return {
        "meta": {
            "mode": args.mode,
            "timezone": args.timezone,
            "work_dir": str(work_dir),
            "analysis_start": fmt_dt(analysis_start),
            "analysis_end": fmt_dt(analysis_end),
            "window_minutes": args.window_minutes,
            "stride_minutes": args.stride_minutes,
            "include_partial_final": bool(args.include_partial_final),
            "window_output_root": path_for_display(window_output_root, work_dir),
            "rollup_output_root": path_for_display(rollup_output_root, work_dir),
            "runs_dir_policy": "do_not_create_runs_for_window_prepare",
            "total_windows": len(window_plans),
        },
        "warnings": warnings,
        "windows": [asdict(plan) for plan in window_plans],
    }


def print_text_plan(plan: dict[str, Any]) -> None:
    meta = plan["meta"]
    print("[SW] planner mode")
    print(f"[SW] analysis range: {meta['analysis_start']} ~ {meta['analysis_end']} ({meta['timezone']})")
    print(
        f"[SW] window={meta['window_minutes']}min "
        f"stride={meta['stride_minutes']}min "
        f"include_partial_final={meta['include_partial_final']}"
    )
    print(f"[SW] window_output_root: {meta['window_output_root']}")
    print(f"[SW] rollup_output_root: {meta['rollup_output_root']}")
    print(f"[SW] total windows: {meta['total_windows']}")

    for warning in plan.get("warnings", []):
        print(f"[SW] WARN: {warning}")

    for item in plan["windows"]:
        partial_mark = " partial" if item["is_partial"] else ""
        print(
            f"[SW] #{item['index']:03d}{partial_mark} "
            f"{item['window_id']} {item['start']} ~ {item['end']} "
            f"-> {item['window_dir']}"
        )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sliding Window scheduler planner for Apache logs-only LLM pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", default=".", help="작업 루트 디렉터리")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE, help="window 계산 timezone (기본값: Asia/Seoul)")
    parser.add_argument("--analysis-start", default=None, help="분석 시작 시각 (미지정 시 analysis-end - lookback-hours)")
    parser.add_argument("--analysis-end", default=None, help="분석 종료 시각 (미지정 시 현재 시각, timezone 기준)")
    parser.add_argument("--lookback-hours", type=float, default=1.0, help="analysis-start 미지정 시 되돌아볼 시간")
    parser.add_argument("--window-minutes", type=int, default=60, help="window 크기, 분 단위")
    parser.add_argument("--stride-minutes", type=int, default=60, help="stride 크기, 분 단위")
    parser.add_argument(
        "--include-partial-final",
        action="store_true",
        help="마지막 partial window 포함 (기본값: full window only)",
    )
    parser.add_argument("--window-output-root", default=DEFAULT_WINDOW_OUTPUT_ROOT, help="window artifact root")
    parser.add_argument("--rollup-output-root", default=DEFAULT_ROLLUP_OUTPUT_ROOT, help="rollup artifact root")
    parser.add_argument(
        "--mode",
        choices=["planner", "export", "prepare"],
        default="planner",
        help="실행 모드. Phase 1에서는 planner만 구현됨",
    )
    parser.add_argument("--json", action="store_true", help="계획을 JSON으로 출력")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        plan = build_plan(args)
    except Exception as exc:
        print(f"[SW] ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2 if args.pretty else None))
    else:
        print_text_plan(plan)

    if args.mode != "planner":
        print(f"[SW] ERROR: mode={args.mode!r} is not implemented in Phase 1", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
