#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
PROTECTED_PATHS = (
    ".git",
    "lab",
    "docs",
    "src",
    "tests/fixtures",
    "tests/expected",
    "README.md",
    "scripts/check_prepare_regression.py",
    "scripts/check_stage_dryrun_regression.py",
)
REVIEW_NAME_MARKERS = (
    "error_dump",
    "raw_error",
    "stage1_errors",
    "stage2_errors",
)
STAGE_DRYRUN_ROOT_MARKER = "/tmp/stage-dryrun-regression"
STATUS_TEXT = "STATUS: list-only prototype; no files were deleted"
CANDIDATE_TEXT = "CLEANUP_CANDIDATE: candidate only; manual review required"
PROTECTED_TEXT = "DO_NOT_AUTO_DELETE: protected path"
APPLY_NOT_IMPLEMENTED = "--apply is not implemented in this list-only prototype"


@dataclass
class ScanEntry:
    path: str
    classification: str
    reason: str
    size_bytes: int
    modified_time: str
    is_dir: bool


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List-only output cleanup prototype with conservative path protection.",
    )
    parser.add_argument("--root", default=".", help="root directory to scan")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list-only scan mode (default behavior even when omitted)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="show REVIEW entries in text output")
    parser.add_argument("--apply", action="store_true", help="not implemented; always exits with status 1")
    return parser.parse_args(argv)


def normalize_rel_path(path: Path) -> str:
    text = path.as_posix().strip()
    if text in ("", "."):
        return "."
    return text.rstrip("/")


def matches_protected_path(normalized: str) -> Optional[str]:
    for protected in PROTECTED_PATHS:
        if normalized == protected or normalized.startswith(protected + "/"):
            return protected
    return None


def is_stage_dryrun_root(root_path: Path) -> bool:
    resolved = root_path.resolve()
    normalized_root = resolved.as_posix().rstrip("/")
    if normalized_root == STAGE_DRYRUN_ROOT_MARKER or normalized_root.startswith(STAGE_DRYRUN_ROOT_MARKER + "/"):
        return True
    return resolved.parent.as_posix() == "/tmp" and resolved.name.startswith("stage-dryrun-regression")


def has_stage_dryrun_path_hint(file_path: Path) -> bool:
    resolved = file_path.resolve()
    normalized = resolved.as_posix().rstrip("/")
    if normalized == STAGE_DRYRUN_ROOT_MARKER or normalized.startswith(STAGE_DRYRUN_ROOT_MARKER + "/"):
        return True
    for parent in (resolved,) + tuple(resolved.parents):
        if parent.parent.as_posix() == "/tmp" and parent.name.startswith("stage-dryrun-regression"):
            return True
    return False


def matches_review_name(name: str) -> bool:
    if any(marker in name for marker in REVIEW_NAME_MARKERS):
        return True
    return name.endswith("_errors.json") or name.endswith("_error.json")


def is_tmp_temp_segment(segment: str) -> bool:
    lowered = segment.lower()
    if lowered in {"tmp", "temp"}:
        return True
    if lowered.startswith("tmp_") or lowered.startswith("temp_"):
        return True
    if lowered.endswith("_tmp") or lowered.endswith("_temp"):
        return True
    return False


def is_dryrun_segment(segment: str) -> bool:
    return segment.lower() in {"dryrun", "dry-run", "dry_run"}


def matches_candidate_name(path: Path) -> Optional[str]:
    if path.suffix.lower() == ".tmp":
        return ".tmp extension"

    for part in path.parts:
        if is_dryrun_segment(part):
            return f"explicit dry-run segment: {part}"
        if is_tmp_temp_segment(part):
            return f"explicit temp segment: {part}"

    name = path.name
    stem = path.stem
    if is_dryrun_segment(name) or is_dryrun_segment(stem):
        return f"explicit dry-run name: {name}"
    if is_tmp_temp_segment(stem):
        return f"explicit temp name: {name}"
    return None


def classify_path(root_path: Path, file_path: Path, is_dir: bool, is_symlink: bool) -> Tuple[str, str]:
    rel_path = file_path.relative_to(root_path)
    normalized = normalize_rel_path(rel_path)

    if is_symlink:
        return "DO_NOT_AUTO_DELETE", "symlink; do not auto-delete"

    protected = matches_protected_path(normalized)
    if protected:
        return "DO_NOT_AUTO_DELETE", f"protected path: {protected}"

    if matches_review_name(file_path.name.lower()):
        return "REVIEW", "error-related artifact; manual review required"

    if is_stage_dryrun_root(root_path) and normalized != ".":
        return "CLEANUP_CANDIDATE", "under /tmp/stage-dryrun-regression root"

    if normalized != "." and has_stage_dryrun_path_hint(file_path):
        return "CLEANUP_CANDIDATE", "path is under /tmp/stage-dryrun-regression"

    candidate_reason = matches_candidate_name(rel_path)
    if candidate_reason:
        return "CLEANUP_CANDIDATE", candidate_reason

    return "KEEP", "default retention"


def format_modified_time(stat_result: object) -> str:
    timestamp = getattr(stat_result, "st_mtime", None)
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def build_entry(root_path: Path, file_path: Path) -> ScanEntry:
    relative = file_path.relative_to(root_path)
    display_path = "." if normalize_rel_path(relative) == "." else relative.as_posix()
    is_symlink = file_path.is_symlink()

    try:
        stat_result = file_path.lstat() if is_symlink else file_path.stat()
    except OSError as exc:
        return ScanEntry(
            path=display_path,
            classification="REVIEW",
            reason=f"stat failed: {exc}",
            size_bytes=0,
            modified_time="",
            is_dir=False,
        )

    is_dir = file_path.is_dir() if not is_symlink else False
    classification, reason = classify_path(root_path, file_path, is_dir=is_dir, is_symlink=is_symlink)
    return ScanEntry(
        path=display_path,
        classification=classification,
        reason=reason,
        size_bytes=int(stat_result.st_size),
        modified_time=format_modified_time(stat_result),
        is_dir=is_dir,
    )


def should_skip_descendants(relative: Path) -> bool:
    normalized = normalize_rel_path(relative)
    return matches_protected_path(normalized) is not None


def iter_scan_paths(root_path: Path) -> Iterable[Path]:
    yield root_path
    for current_root, dirnames, filenames in root_path.walk(top_down=True, follow_symlinks=False):
        next_dirs: List[str] = []
        for dirname in dirnames:
            dir_path = current_root / dirname
            rel_dir = dir_path.relative_to(root_path)
            next_dirs.append(dirname)
            if should_skip_descendants(rel_dir):
                continue
        dirnames[:] = [name for name in dirnames if not should_skip_descendants((current_root / name).relative_to(root_path))]

        for dirname in next_dirs:
            yield current_root / dirname
        for filename in filenames:
            yield current_root / filename


def scan_entries(root_path: Path) -> List[ScanEntry]:
    entries: List[ScanEntry] = []
    for file_path in iter_scan_paths(root_path):
        try:
            file_path.relative_to(root_path)
        except ValueError:
            continue
        entries.append(build_entry(root_path, file_path))
    return sorted(entries, key=lambda entry: entry.path)


def summarize_entries(entries: Sequence[ScanEntry]) -> Dict[str, int]:
    summary = {
        "KEEP": 0,
        "REVIEW": 0,
        "CLEANUP_CANDIDATE": 0,
        "DO_NOT_AUTO_DELETE": 0,
        "TOTAL": len(entries),
    }
    for entry in entries:
        summary[entry.classification] = summary.get(entry.classification, 0) + 1
    return summary


def render_text(entries: Sequence[ScanEntry], summary: Dict[str, int], verbose: bool) -> str:
    lines = [
        STATUS_TEXT,
        CANDIDATE_TEXT,
        PROTECTED_TEXT,
        f"ROOT: {entries[0].path if entries and entries[0].path == '.' else '.'}",
        (
            "SUMMARY: "
            f"KEEP={summary['KEEP']} "
            f"REVIEW={summary['REVIEW']} "
            f"CLEANUP_CANDIDATE={summary['CLEANUP_CANDIDATE']} "
            f"DO_NOT_AUTO_DELETE={summary['DO_NOT_AUTO_DELETE']} "
            f"TOTAL={summary['TOTAL']}"
        ),
        "",
        "CLEANUP_CANDIDATE entries:",
    ]

    candidates = [entry for entry in entries if entry.classification == "CLEANUP_CANDIDATE"]
    if not candidates:
        lines.append("(none)")
    else:
        for entry in candidates:
            lines.append(f"- {entry.path} [{entry.reason}]")

    if verbose:
        lines.extend(["", "REVIEW entries:"])
        review_entries = [entry for entry in entries if entry.classification == "REVIEW"]
        if not review_entries:
            lines.append("(none)")
        else:
            for entry in review_entries:
                lines.append(f"- {entry.path} [{entry.reason}]")

    return "\n".join(lines)


def render_json(root_path: Path, entries: Sequence[ScanEntry], summary: Dict[str, int]) -> str:
    payload = {
        "status": "list-only prototype; no files were deleted",
        "root": str(root_path),
        "summary": summary,
        "entries": [asdict(entry) for entry in entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.apply:
        print(APPLY_NOT_IMPLEMENTED, file=sys.stderr)
        return 1

    root_path = Path(args.root).resolve()
    if not root_path.exists():
        print(f"root does not exist: {root_path}", file=sys.stderr)
        return 1
    if not root_path.is_dir():
        print(f"root is not a directory: {root_path}", file=sys.stderr)
        return 1

    entries = scan_entries(root_path)
    summary = summarize_entries(entries)

    if args.json:
        print(render_json(root_path, entries, summary))
    else:
        print(render_text(entries, summary, verbose=args.verbose))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
