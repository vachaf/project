#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.prepare_llm_input import derive_base_name  # noqa: E402


DEFAULT_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "prepare_regression"
DEFAULT_EXPECTED_DIR = ROOT / "tests" / "expected" / "prepare_regression"
DEFAULT_PREPARE_SCRIPT = ROOT / "src" / "prepare_llm_input.py"
SUFFIXES = {
    "llm_input": "_llm_input.json",
    "analysis_candidates": "_analysis_candidates.json",
    "noise_summary": "_noise_summary.json",
    "filtered_out": "_filtered_out_rows.json",
}
COLLECTION_KEYS = {
    "analysis_candidates": "analysis_candidates",
    "supporting_events": "supporting_events",
    "false_positive_review_candidates": "false_positive_review_candidates",
    "probing_sequence_summaries": "probing_sequence_summaries",
}


@dataclass
class FixtureResult:
    name: str
    status: str
    details: List[str]
    output_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="prepare_llm_input smoke regression checker")
    parser.add_argument(
        "--fixtures",
        default=str(DEFAULT_FIXTURES_DIR),
        help="fixture directory containing *.json exports",
    )
    parser.add_argument(
        "--expected",
        default=str(DEFAULT_EXPECTED_DIR),
        help="expected rule directory containing *.expected.json",
    )
    parser.add_argument(
        "--keep-output",
        default=None,
        help="keep per-fixture prepare outputs under this directory",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def flatten_strings(value: Any) -> List[str]:
    values: List[str] = []
    if isinstance(value, dict):
        for nested in value.values():
            values.extend(flatten_strings(nested))
        return values
    if isinstance(value, list):
        for nested in value:
            values.extend(flatten_strings(nested))
        return values
    text = stringify(value)
    return [text] if text else []


def get_collection_payloads(llm_input: Dict[str, Any], filtered_out: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    payloads = {"filtered_out": filtered_out}
    for alias, llm_key in COLLECTION_KEYS.items():
        payloads[alias] = llm_input.get(llm_key, []) or []
    return payloads


def resolve_output_paths(out_dir: Path, fixture_path: Path, explicit_base_name: str) -> Dict[str, Path]:
    base_name = derive_base_name(str(fixture_path), explicit_base_name)
    return {
        name: out_dir / f"{base_name}{suffix}"
        for name, suffix in SUFFIXES.items()
    }


def run_prepare(fixture_path: Path, out_dir: Path) -> Dict[str, Path]:
    base_name = fixture_path.stem
    cmd = [
        sys.executable,
        str(DEFAULT_PREPARE_SCRIPT),
        "--input",
        str(fixture_path),
        "--out-dir",
        str(out_dir),
        "--base-name",
        base_name,
        "--pretty",
        "--write-filtered-out",
    ]
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "prepare_llm_input.py failed for "
            f"{fixture_path.name}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )

    paths = resolve_output_paths(out_dir, fixture_path, explicit_base_name=base_name)
    missing = [f"{name}={path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise RuntimeError(
            "prepare output file resolution mismatch for "
            f"{fixture_path.name}. Expected files not found: {', '.join(missing)}"
        )
    return paths


def entry_matches(entry: Dict[str, Any], where: Dict[str, Any]) -> bool:
    for key, expected in (where or {}).items():
        if key.endswith("__contains"):
            field = key[: -len("__contains")]
            haystacks = flatten_strings(entry.get(field))
            if not any(stringify(expected) in haystack for haystack in haystacks):
                return False
            continue
        if key.endswith("__startswith"):
            field = key[: -len("__startswith")]
            haystacks = flatten_strings(entry.get(field))
            if not any(haystack.startswith(stringify(expected)) for haystack in haystacks):
                return False
            continue
        actual = entry.get(key)
        if actual != expected:
            return False
    return True


def select_entries(payloads: Dict[str, List[Dict[str, Any]]], collection: str, where: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [entry for entry in payloads.get(collection, []) if entry_matches(entry, where)]


def field_contains(entries: List[Dict[str, Any]], field: str, needle: str) -> bool:
    for entry in entries:
        if any(needle in value for value in flatten_strings(entry.get(field))):
            return True
    return False


def evaluate_rule(payloads: Dict[str, List[Dict[str, Any]]], rule: Dict[str, Any]) -> bool:
    op = rule["op"]
    where = rule.get("where", {})
    if op == "exists":
        return bool(select_entries(payloads, rule["collection"], where))
    if op == "exists_in_any":
        return any(select_entries(payloads, collection, where) for collection in rule["collections"])
    if op == "field_contains":
        entries = select_entries(payloads, rule["collection"], where)
        return field_contains(entries, rule["field"], stringify(rule["contains"]))
    raise ValueError(f"Unsupported rule op: {op}")


def evaluate_expectations(
    fixture_name: str,
    expected: Dict[str, Any],
    payloads: Dict[str, List[Dict[str, Any]]],
    strict: bool,
) -> FixtureResult:
    failures: List[str] = []
    warnings: List[str] = []
    passes: List[str] = []

    for rule in expected.get("MUST", []):
        if evaluate_rule(payloads, rule):
            passes.append(rule["message"])
        else:
            failures.append(rule["message"])

    for rule in expected.get("MUST_NOT", []):
        if evaluate_rule(payloads, rule):
            failures.append(rule["message"])
        else:
            passes.append(f"not {rule['message']}")

    for rule in expected.get("SHOULD", []):
        if evaluate_rule(payloads, rule):
            passes.append(rule["message"])
        else:
            warnings.append(rule["message"])

    known_limitation_triggered = False
    for rule in expected.get("KNOWN_LIMITATION", []):
        if evaluate_rule(payloads, rule):
            warnings.append(rule["message"])
            known_limitation_triggered = True

    if strict and warnings:
        failures.extend(f"strict:{message}" for message in warnings)

    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    detail_parts: List[str] = []
    if status == "PASS":
        detail_parts = passes[:3] or ["all checks passed"]
    else:
        detail_parts.extend(failures)
        if warnings and not strict:
            detail_parts.extend(warnings)
    if known_limitation_triggered and status == "PASS":
        status = "WARN"
    return FixtureResult(name=fixture_name, status=status, details=detail_parts, output_dir=Path())


def iter_fixture_paths(fixtures_dir: Path) -> Iterable[Path]:
    return sorted(path for path in fixtures_dir.glob("*.json") if path.is_file())


def main() -> int:
    args = parse_args()
    fixtures_dir = Path(args.fixtures).resolve()
    expected_dir = Path(args.expected).resolve()

    if not fixtures_dir.exists():
        print(f"[FAIL] fixtures directory not found: {fixtures_dir}")
        return 1
    if not expected_dir.exists():
        print(f"[FAIL] expected directory not found: {expected_dir}")
        return 1

    fixture_paths = list(iter_fixture_paths(fixtures_dir))
    if not fixture_paths:
        print(f"[FAIL] no fixture JSON files found under {fixtures_dir}")
        return 1

    if args.keep_output:
        output_root = Path(args.keep_output).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        cleanup_root = False
    else:
        output_root = Path(tempfile.mkdtemp(prefix="prepare_regression_"))
        cleanup_root = True

    results: List[FixtureResult] = []
    try:
        for fixture_path in fixture_paths:
            fixture_name = fixture_path.stem
            expected_path = expected_dir / f"{fixture_name}.expected.json"
            if not expected_path.exists():
                results.append(
                    FixtureResult(
                        name=fixture_name,
                        status="FAIL",
                        details=[f"missing expected file: {expected_path.name}"],
                        output_dir=output_root / fixture_name,
                    )
                )
                continue

            fixture_output_dir = output_root / fixture_name
            fixture_output_dir.mkdir(parents=True, exist_ok=True)
            try:
                paths = run_prepare(fixture_path, fixture_output_dir)
                llm_input = load_json(paths["llm_input"])
                filtered_out = load_json(paths["filtered_out"])
                payloads = get_collection_payloads(llm_input, filtered_out)
                expected = load_json(expected_path)
                result = evaluate_expectations(
                    fixture_name=fixture_name,
                    expected=expected,
                    payloads=payloads,
                    strict=args.strict,
                )
                result.output_dir = fixture_output_dir
                results.append(result)
            except Exception as exc:
                results.append(
                    FixtureResult(
                        name=fixture_name,
                        status="FAIL",
                        details=[stringify(exc)],
                        output_dir=fixture_output_dir,
                    )
                )
    finally:
        if cleanup_root:
            for result in results:
                result.output_dir = output_root / result.name

    for result in results:
        summary = "; ".join(result.details[:3]) if result.details else "no details"
        print(f"[{result.status}] {result.name}: {summary}")

    counts = {
        "PASS": sum(1 for result in results if result.status == "PASS"),
        "WARN": sum(1 for result in results if result.status == "WARN"),
        "FAIL": sum(1 for result in results if result.status == "FAIL"),
    }
    print(
        "[SUMMARY] "
        f"pass={counts['PASS']} warn={counts['WARN']} fail={counts['FAIL']} "
        f"fixtures={len(results)} output_root={output_root}"
    )

    if cleanup_root:
        shutil.rmtree(output_root, ignore_errors=True)

    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
