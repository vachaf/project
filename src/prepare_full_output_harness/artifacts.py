"""Exclusive, symlink-safe artifact writer skeleton."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .identity import require_sha256_digest


class ArtifactError(RuntimeError):
    """Raised when artifact safety or completion rules are violated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactError("symlink_path", "artifact path contains a symlink")
        if not current.exists():
            break


def validate_new_output_root(path: str | Path) -> Path:
    """Validate an absent output root without creating it."""

    root = Path(path)
    _reject_symlink_components(root)
    if root.exists() or root.is_symlink():
        raise ArtifactError("output_exists", "output root already exists")
    parent = root.parent.resolve(strict=True)
    return parent / root.name


def validate_distinct_run_paths(paths: dict[str, str | Path]) -> None:
    """Require separate before-1, before-2, after, and comparison paths."""

    required = {"before-1", "before-2", "after", "comparison"}
    if set(paths) != required:
        raise ArtifactError("run_paths_missing", "all four artifact paths are required")
    resolved = [Path(value).resolve(strict=False) for value in paths.values()]
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise ArtifactError(
                    "run_paths_overlap", "artifact run paths must be distinct and non-nested"
                )


@dataclass
class ArtifactWriter:
    """Writer for one brand-new run; no force or overwrite operation exists."""

    root: Path
    _checksums: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _completed: bool = field(default=False, init=False, repr=False)

    @classmethod
    def create(cls, path: str | Path) -> "ArtifactWriter":
        """Exclusively create a private run root."""

        root = validate_new_output_root(path)
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
        return cls(root=root)

    def _target(self, relative_path: str) -> Path:
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or not pure.parts or ".." in pure.parts:
            raise ArtifactError("path_escape", "artifact path must stay below its root")
        target = self.root.joinpath(*pure.parts)
        _reject_symlink_components(target)
        if target.exists() or target.is_symlink():
            raise ArtifactError("artifact_exists", "artifact target already exists")
        if target.parent.resolve(strict=False) == self.root or self.root in target.parent.resolve(
            strict=False
        ).parents:
            return target
        raise ArtifactError("path_escape", "artifact path escapes its root")

    def write_bytes(self, relative_path: str, payload: bytes) -> str:
        """Atomically write one new payload with private file permissions."""

        if self._completed:
            raise ArtifactError("run_completed", "completed runs are read-only")
        target = self._target(relative_path)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pending-", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        digest = hashlib.sha256(payload).hexdigest()
        self._checksums[relative_path] = digest
        return digest

    def write_json(self, relative_path: str, value: Any) -> str:
        """Write deterministic JSON; callers must supply pre-redacted content."""

        payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        return self.write_bytes(relative_path, payload)

    def finalize(self) -> None:
        """Verify payloads and publish completion metadata as a retryable transaction."""

        if self._completed:
            raise ArtifactError("run_completed", "run is already complete")
        payload_checksums = dict(self._checksums)
        try:
            for relative_path, expected in payload_checksums.items():
                actual = hashlib.sha256((self.root / relative_path).read_bytes()).hexdigest()
                if actual != expected:
                    raise ArtifactError(
                        "checksum_mismatch", "artifact checksum verification failed"
                    )
            lines = [f"{digest}  {path}\n" for path, digest in payload_checksums.items()]
            self.write_bytes("checksums.sha256", "".join(lines).encode("utf-8"))
            self.write_json("completion.json", {"complete": True, "checksum_ready": True})
        except BaseException:
            # Completion metadata is transactional: payloads remain available for
            # inspection, while a failed finalize can be retried by the caller.
            (self.root / "completion.json").unlink(missing_ok=True)
            (self.root / "checksums.sha256").unlink(missing_ok=True)
            self._checksums.clear()
            self._checksums.update(payload_checksums)
            raise
        self._completed = True


def require_completed_read_only_baseline(path: str | Path) -> Path:
    """Validate completion metadata and every checksummed baseline payload."""

    supplied = Path(path)
    _reject_symlink_components(supplied)
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        raise ArtifactError("baseline_incomplete", "baseline path is not a directory")
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise ArtifactError("symlink_path", "baseline contains a symlink")
    completion_path = root / "completion.json"
    checksums_path = root / "checksums.sha256"
    if not completion_path.is_file() or not checksums_path.is_file():
        raise ArtifactError("baseline_incomplete", "baseline has no completion marker")
    try:
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("invalid_completion", "completion marker is invalid") from exc
    if completion != {"complete": True, "checksum_ready": True}:
        raise ArtifactError("invalid_completion", "completion marker content is invalid")
    try:
        checksum_text = checksums_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ArtifactError("invalid_checksums", "checksum manifest is unreadable") from exc
    if checksum_text and not checksum_text.endswith("\n"):
        raise ArtifactError("invalid_checksums", "checksum manifest must end with a newline")
    records: dict[str, str] = {}
    for line in checksum_text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ArtifactError("invalid_checksums", "checksum manifest line is malformed")
        digest, relative_path = match.groups()
        require_sha256_digest("artifact_sha256", digest)
        pure = PurePosixPath(relative_path)
        if (
            pure.is_absolute()
            or not pure.parts
            or ".." in pure.parts
            or "." in pure.parts
            or str(pure) != relative_path
            or "\\" in relative_path
            or relative_path in {"checksums.sha256", "completion.json"}
        ):
            raise ArtifactError("unsafe_checksum_path", "checksum path is not a safe relative path")
        if relative_path in records:
            raise ArtifactError("invalid_checksums", "checksum manifest contains a duplicate path")
        records[relative_path] = digest
    payload_files = {
        candidate.relative_to(root).as_posix()
        for candidate in root.rglob("*")
        if candidate.is_file()
        and candidate not in {completion_path, checksums_path}
    }
    if set(records) != payload_files:
        raise ArtifactError("checksum_inventory_mismatch", "checksum inventory is incomplete")
    for relative_path, expected in records.items():
        target = root.joinpath(*PurePosixPath(relative_path).parts)
        _reject_symlink_components(target)
        if not target.is_file():
            raise ArtifactError("checksum_inventory_mismatch", "checksummed artifact is not a file")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise ArtifactError("checksum_mismatch", "baseline artifact checksum does not match")
    return root
