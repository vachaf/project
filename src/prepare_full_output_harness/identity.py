"""Canonical source and input identity records for the Prepare harness."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


class IdentityError(ValueError):
    """Raised for missing, malformed, or mismatched identity evidence."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def sha256_bytes(value: bytes) -> str:
    """Return the lowercase SHA-256 digest of exact bytes."""

    if not isinstance(value, bytes):
        raise IdentityError("invalid_bytes", "SHA-256 input must be bytes")
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash file content; a path alone is never treated as identity."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(label: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise IdentityError("missing_identity", f"identity field is required: {label}")
    return value


def require_sha256_digest(label: str, value: str) -> str:
    """Require the canonical lowercase hexadecimal representation of SHA-256."""

    _require(label, value)
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise IdentityError(
            "invalid_sha256", f"SHA-256 field must be 64 lowercase hexadecimal characters: {label}"
        )
    return value


@dataclass(frozen=True)
class SourceIdentity:
    """Content-backed identity of source, harness, and adapter code."""

    source_revision: str
    source_tree_digest: str
    harness_digest: str
    adapter_digest: str

    def __post_init__(self) -> None:
        _require("source_revision", self.source_revision)
        for name in ("source_tree_digest", "harness_digest", "adapter_digest"):
            require_sha256_digest(name, getattr(self, name))


@dataclass(frozen=True)
class InputIdentity:
    """Input provenance with raw-source and projected-payload hashes separated."""

    corpus_id: str
    case_id: str
    source_revision: str
    source_file_sha256: str
    adapter_version: str
    parameter_id: str
    raw_source_hash: str
    projected_payload_hash: str

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _require(name, value)
        for name in ("source_file_sha256", "raw_source_hash", "projected_payload_hash"):
            require_sha256_digest(name, getattr(self, name))

    def canonical_key(self) -> tuple[str, ...]:
        """Return all provenance axes; equal bytes never erase source identity."""

        return (
            self.corpus_id,
            self.case_id,
            self.source_revision,
            self.source_file_sha256,
            self.adapter_version,
            self.parameter_id,
            self.raw_source_hash,
            self.projected_payload_hash,
        )


@dataclass(frozen=True)
class IdentityRecord:
    """Canonical identity envelope for one captured case."""

    source: SourceIdentity
    input: InputIdentity


def require_matching_identity(before: IdentityRecord, after: IdentityRecord) -> None:
    """Reject any identity mismatch rather than comparing unrelated captures."""

    if before != after:
        raise IdentityError("identity_mismatch", "capture identities do not match")
