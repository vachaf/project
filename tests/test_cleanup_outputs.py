from __future__ import annotations

import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts import cleanup_outputs


class CleanupOutputsTest(unittest.TestCase):
    def test_docs_directory_is_protected(self) -> None:
        classification, reason = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/docs"),
            is_dir=True,
            is_symlink=False,
        )
        self.assertEqual(classification, "DO_NOT_AUTO_DELETE")
        self.assertIn("docs", reason)

    def test_docs_child_is_protected(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/docs/foo.md"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "DO_NOT_AUTO_DELETE")

    def test_lab_directory_is_protected(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/lab"),
            is_dir=True,
            is_symlink=False,
        )
        self.assertEqual(classification, "DO_NOT_AUTO_DELETE")

    def test_stage_dryrun_root_marks_children_as_candidates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-dryrun-regression-", dir="/tmp") as tmp_dir:
            root_path = Path(tmp_dir).resolve()
            child = root_path / "nested" / "artifact.json"
            child.parent.mkdir(parents=True)
            child.write_text("{}", encoding="utf-8")
            classification, reason = cleanup_outputs.classify_path(
                root_path,
                child,
                is_dir=False,
                is_symlink=False,
            )
            self.assertEqual(classification, "CLEANUP_CANDIDATE")
            self.assertIn("stage-dryrun-regression", reason)

    def test_template_name_is_not_candidate(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/template.md"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "KEEP")

    def test_temp_output_tmp_file_is_candidate(self) -> None:
        classification, reason = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/temp/output.tmp"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "CLEANUP_CANDIDATE")
        self.assertTrue(".tmp" in reason or "temp" in reason)

    def test_error_dump_is_review(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/error_dump.json"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "REVIEW")

    def test_apply_returns_exit_one(self) -> None:
        self.assertEqual(cleanup_outputs.main(["--root", ".", "--apply"]), 1)

    def test_json_output_contains_summary_and_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root_path = Path(tmp_dir)
            (root_path / "temp").mkdir()
            (root_path / "temp" / "output.tmp").write_text("x", encoding="utf-8")
            entries = cleanup_outputs.scan_entries(root_path.resolve())
            payload = json.loads(
                cleanup_outputs.render_json(
                    root_path.resolve(),
                    entries,
                    cleanup_outputs.summarize_entries(entries),
                )
            )
            self.assertIn("summary", payload)
            self.assertIn("entries", payload)
            self.assertTrue(any(entry["classification"] == "CLEANUP_CANDIDATE" for entry in payload["entries"]))

    def test_repo_root_docs_child_is_protected_when_root_is_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir).resolve()
            docs_root = repo_root / "docs"
            docs_root.mkdir()
            target = docs_root / "foo.md"
            target.write_text("doc", encoding="utf-8")
            with mock.patch.object(cleanup_outputs, "REPO_ROOT", repo_root):
                classification, reason = cleanup_outputs.classify_path(
                    docs_root,
                    target,
                    is_dir=False,
                    is_symlink=False,
                )
            self.assertEqual(classification, "DO_NOT_AUTO_DELETE")
            self.assertIn("docs", reason)

    def test_repo_root_lab_child_is_protected_when_root_is_lab(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir).resolve()
            lab_root = repo_root / "lab"
            lab_root.mkdir()
            target = lab_root / "result.json"
            target.write_text("{}", encoding="utf-8")
            with mock.patch.object(cleanup_outputs, "REPO_ROOT", repo_root):
                classification, reason = cleanup_outputs.classify_path(
                    lab_root,
                    target,
                    is_dir=False,
                    is_symlink=False,
                )
            self.assertEqual(classification, "DO_NOT_AUTO_DELETE")
            self.assertIn("lab", reason)

    def test_dry_run_output_prefix_is_candidate(self) -> None:
        classification, reason = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/reports/dry_run_output_2026-04-25/output.json"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "CLEANUP_CANDIDATE")
        self.assertIn("dry-run", reason)

    def test_nondryrun_name_is_not_candidate(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/nondryrun.json"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "KEEP")

    def test_mydryrunfile_name_is_not_candidate(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/mydryrunfile.json"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "KEEP")

    def test_timestamp_name_is_not_candidate(self) -> None:
        classification, _ = cleanup_outputs.classify_path(
            Path("/repo"),
            Path("/repo/timestamp.json"),
            is_dir=False,
            is_symlink=False,
        )
        self.assertEqual(classification, "KEEP")


if __name__ == "__main__":
    unittest.main()
