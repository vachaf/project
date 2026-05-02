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
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import llm_stage1_classifier as stage1_classifier  # noqa: E402
import llm_stage2_reporter as stage2_reporter  # noqa: E402


DEFAULT_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "prepare_regression"
DEFAULT_EXPECTED_DIR = ROOT / "tests" / "expected" / "stage_dryrun_regression"
DEFAULT_PIPELINE_SCRIPT = ROOT / "src" / "run_analysis_pipeline.py"
BANNED_PHRASE_CONTEXT_WINDOW = 120
REQUIRED_ARTIFACT_SUFFIXES = {
    "llm_input": ("data/processed", "_llm_input.json"),
    "stage1_results": ("data/processed", "_stage1_results.json"),
    "stage2_report_input": ("reports", "_stage2_report_input.json"),
    "stage2_report_json": ("reports", "_stage2_report.json"),
    "stage2_report_md": ("reports", "_stage2_report.md"),
    "pipeline_manifest": ("", "pipeline_manifest.json"),
}


@dataclass
class FixtureResult:
    name: str
    status: str
    details: List[str]
    output_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage1/Stage2 dry-run smoke regression checker")
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
        help="keep per-fixture dry-run outputs under this directory",
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
    if value is None:
        return []
    if isinstance(value, dict):
        values: List[str] = []
        for nested in value.values():
            values.extend(flatten_strings(nested))
        return values
    if isinstance(value, list):
        values = []
        for nested in value:
            values.extend(flatten_strings(nested))
        return values
    text = stringify(value)
    return [text] if text else []


def split_json_path(path: str) -> List[str]:
    return [token for token in path.split(".") if token]


_MISSING = object()


def resolve_json_path(payload: Any, path: str) -> Any:
    current = payload
    if not path:
        return current
    for token in split_json_path(path):
        if isinstance(current, list):
            if not token.isdigit():
                return _MISSING
            idx = int(token)
            if idx < 0 or idx >= len(current):
                return _MISSING
            current = current[idx]
            continue
        if not isinstance(current, dict):
            return _MISSING
        if token not in current:
            return _MISSING
        current = current[token]
    return current


def json_path_exists(payload: Any, path: str) -> bool:
    return resolve_json_path(payload, path) is not _MISSING


def value_contains(actual: Any, needle: str) -> bool:
    return any(needle in value for value in flatten_strings(actual))


def values_equal(actual: Any, expected: Any) -> bool:
    return actual == expected


def list_item_matches(item: Any, where: Dict[str, Any]) -> bool:
    if not where:
        return True
    if not isinstance(item, dict):
        return False
    for path, expected in where.items():
        if path.endswith("__contains"):
            actual = resolve_json_path(item, path[: -len("__contains")])
            if actual is _MISSING or not value_contains(actual, stringify(expected)):
                return False
            continue
        actual = resolve_json_path(item, path)
        if actual is _MISSING or actual != expected:
            return False
    return True


def load_file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_unallowed_occurrence(text: str, needle: str, allowed_contexts: List[str], window: int) -> bool:
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            return False
        left = max(0, idx - window)
        right = min(len(text), idx + len(needle) + window)
        context = text[left:right]
        if not any(allowed in context for allowed in allowed_contexts):
            return True
        start = idx + len(needle)


def resolve_artifact_paths(work_dir: Path, base_name: str) -> Dict[str, Path]:
    resolved: Dict[str, Path] = {}
    for alias, (subdir, suffix) in REQUIRED_ARTIFACT_SUFFIXES.items():
        if alias == "pipeline_manifest":
            resolved[alias] = work_dir / suffix
            continue
        resolved[alias] = work_dir / subdir / f"{base_name}{suffix}"
    return resolved


def run_pipeline_dry_run(fixture_path: Path, work_dir: Path) -> Dict[str, Path]:
    base_name = fixture_path.stem
    cmd = [
        sys.executable,
        str(DEFAULT_PIPELINE_SCRIPT),
        "--export-input",
        str(fixture_path),
        "--work-dir",
        str(work_dir),
        "--base-name",
        base_name,
        "--write-filtered-out",
        "--pretty",
        "--dry-run",
    ]
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "run_analysis_pipeline.py failed for "
            f"{fixture_path.name}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )

    paths = resolve_artifact_paths(work_dir, base_name=base_name)
    missing = [f"{name}={path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise RuntimeError(
            "dry-run output file resolution mismatch for "
            f"{fixture_path.name}. Expected files not found: {', '.join(missing)}"
        )
    return paths


def build_stage1_request_plan(llm_input_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = llm_input_payload.get("meta") or {}
    request_plan: List[Dict[str, Any]] = []
    for idx, candidate in enumerate(llm_input_payload.get("analysis_candidates") or []):
        messages = stage1_classifier.build_messages(meta, candidate, max_evidence_items=8)
        request_plan.append(
            {
                "candidate_index": idx,
                "request_id": stringify(candidate.get("request_id")),
                "incident_group_key": stringify(candidate.get("incident_group_key")),
                "verdict_hint": stringify(candidate.get("verdict_hint")),
                "message_preview": {
                    "system_prompt": messages[0]["content"],
                    "user_payload": json.loads(messages[1]["content"]),
                },
            }
        )
    return request_plan


def build_virtual_docs(artifacts: Dict[str, Path]) -> Dict[str, Any]:
    llm_input_payload = load_json(artifacts["llm_input"])
    stage2_report_input = load_json(artifacts["stage2_report_input"])
    stage1_request_plan = build_stage1_request_plan(llm_input_payload)
    stage2_messages = stage2_reporter.build_messages(stage2_report_input)
    docs: Dict[str, Any] = {
        "llm_input": llm_input_payload,
        "stage1_results": load_json(artifacts["stage1_results"]),
        "stage2_report_input": stage2_report_input,
        "stage2_report_json": load_json(artifacts["stage2_report_json"]),
        "pipeline_manifest": load_json(artifacts["pipeline_manifest"]),
        "stage1_schema": stage1_classifier.build_schema(),
        "stage1_request_plan": stage1_request_plan,
        "stage1_prompt_bundle": stage1_request_plan[0]["message_preview"] if stage1_request_plan else {},
        "stage2_schema": stage2_reporter.build_schema(),
        "stage2_prompt_bundle": {
            "system_prompt": stage2_messages[0]["content"],
            "user_payload": json.loads(stage2_messages[1]["content"]),
        },
    }
    return docs


def evaluate_rule(rule: Dict[str, Any], docs: Dict[str, Any], artifacts: Dict[str, Path]) -> bool:
    op = rule["op"]

    if op in {"json_path_exists", "json_path_equals", "json_path_contains"}:
        payload = docs[rule["file"]]
        actual = resolve_json_path(payload, rule["path"])
        if op == "json_path_exists":
            return actual is not _MISSING
        if actual is _MISSING:
            return False
        if op == "json_path_equals":
            return values_equal(actual, rule["equals"])
        return value_contains(actual, stringify(rule["contains"]))

    if op in {"list_any_contains", "list_any_equals"}:
        payload = docs[rule["file"]]
        list_value = resolve_json_path(payload, rule.get("path", ""))
        if not isinstance(list_value, list):
            return False
        field = rule["field"]
        where = rule.get("where", {})
        for item in list_value:
            if not list_item_matches(item, where):
                continue
            actual = resolve_json_path(item, field)
            if actual is _MISSING:
                continue
            if op == "list_any_contains" and value_contains(actual, stringify(rule["contains"])):
                return True
            if op == "list_any_equals" and values_equal(actual, rule["equals"]):
                return True
        return False

    if op in {"file_contains", "file_not_contains", "file_contains_unless_context"}:
        text = load_file_text(artifacts[rule["file"]])
        needle = stringify(rule["contains"])
        if op == "file_contains":
            return needle in text
        if op == "file_not_contains":
            return needle not in text
        allowed_context = rule.get("allowed_context_contains", [])
        if isinstance(allowed_context, str):
            allowed_contexts = [allowed_context]
        else:
            allowed_contexts = [stringify(item) for item in allowed_context]
        return find_unallowed_occurrence(
            text,
            needle=needle,
            allowed_contexts=allowed_contexts,
            window=int(rule.get("context_window", BANNED_PHRASE_CONTEXT_WINDOW)),
        )

    raise ValueError(f"Unsupported rule op: {op}")


def evaluate_expectations(
    fixture_name: str,
    expected: Dict[str, Any],
    docs: Dict[str, Any],
    artifacts: Dict[str, Path],
    strict: bool,
    output_dir: Path,
) -> FixtureResult:
    failures: List[str] = []
    warnings: List[str] = []
    passes: List[str] = []

    for rule in expected.get("MUST", []):
        if evaluate_rule(rule, docs, artifacts):
            passes.append(rule["message"])
        else:
            failures.append(rule["message"])

    for rule in expected.get("MUST_NOT", []):
        if evaluate_rule(rule, docs, artifacts):
            failures.append(rule["message"])
        else:
            passes.append(f"not {rule['message']}")

    for rule in expected.get("SHOULD", []):
        if evaluate_rule(rule, docs, artifacts):
            passes.append(rule["message"])
        else:
            warnings.append(rule["message"])

    if strict and warnings:
        failures.extend(f"strict:{message}" for message in warnings)

    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    details = failures if failures else (warnings if warnings else (passes[:3] or ["all checks passed"]))
    return FixtureResult(name=fixture_name, status=status, details=details, output_dir=output_dir)


def iter_expected_fixture_pairs(fixtures_dir: Path, expected_dir: Path) -> Iterable[tuple[Path, Path]]:
    expected_paths = sorted(path for path in expected_dir.glob("*.expected.json") if path.is_file())
    for expected_path in expected_paths:
        fixture_name = expected_path.name.replace(".expected.json", "")
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        if not fixture_path.exists():
            raise FileNotFoundError(f"fixture for expected rules not found: {fixture_path}")
        yield fixture_path, expected_path


def resolve_fixture_output_dir(parent: Path, fixture_name: str) -> Path:
    out_dir = parent / fixture_name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def print_fixture_result(result: FixtureResult) -> None:
    print(f"[{result.status}] {result.name}")
    for detail in result.details:
        print(f"  - {detail}")
    print(f"  - output_dir={result.output_dir}")


def main() -> int:
    args = parse_args()
    fixtures_dir = Path(args.fixtures).expanduser().resolve()
    expected_dir = Path(args.expected).expanduser().resolve()
    keep_output_dir = Path(args.keep_output).expanduser().resolve() if args.keep_output else None

    if not fixtures_dir.exists():
        print(f"[ERROR] fixtures dir not found: {fixtures_dir}", file=sys.stderr)
        return 2
    if not expected_dir.exists():
        print(f"[ERROR] expected dir not found: {expected_dir}", file=sys.stderr)
        return 2

    fixture_pairs = list(iter_expected_fixture_pairs(fixtures_dir, expected_dir))
    if not fixture_pairs:
        print(f"[ERROR] no expected fixture pairs found under: {expected_dir}", file=sys.stderr)
        return 2

    if keep_output_dir:
        keep_output_dir.mkdir(parents=True, exist_ok=True)

    temp_parent_ctx: Optional[tempfile.TemporaryDirectory[str]] = None
    temp_parent: Optional[Path] = None
    if not keep_output_dir:
        temp_parent_ctx = tempfile.TemporaryDirectory(prefix="stage-dryrun-regression-")
        temp_parent = Path(temp_parent_ctx.name)

    results: List[FixtureResult] = []
    for fixture_path, expected_path in fixture_pairs:
        fixture_output_dir = (
            resolve_fixture_output_dir(keep_output_dir, fixture_path.stem)
            if keep_output_dir
            else resolve_fixture_output_dir(temp_parent or ROOT / ".tmp", fixture_path.stem)
        )
        try:
            artifacts = run_pipeline_dry_run(fixture_path, fixture_output_dir)
            docs = build_virtual_docs(artifacts)
            expected = load_json(expected_path)
            result = evaluate_expectations(
                fixture_name=fixture_path.stem,
                expected=expected,
                docs=docs,
                artifacts=artifacts,
                strict=bool(args.strict),
                output_dir=fixture_output_dir,
            )
        except Exception as exc:
            result = FixtureResult(
                name=fixture_path.stem,
                status="FAIL",
                details=[repr(exc)],
                output_dir=fixture_output_dir,
            )
        results.append(result)
        print_fixture_result(result)

    if temp_parent_ctx:
        temp_parent_ctx.cleanup()

    pass_count = sum(1 for item in results if item.status == "PASS")
    warn_count = sum(1 for item in results if item.status == "WARN")
    fail_count = sum(1 for item in results if item.status == "FAIL")
    print(f"pass={pass_count} warn={warn_count} fail={fail_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
