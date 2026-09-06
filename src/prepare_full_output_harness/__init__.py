"""Prepare full-output comparison harness building blocks.

The package exposes data-only codecs and safety helpers.  It has no CLI and
does not start captures, child processes, corpus runs, or production stages.
"""

from .capture import CAPTURE_FORMAT_VERSION, CaptureCodecError, decode_typed, encode_typed, validate_typed
from .compare import (
    ComparisonResult,
    Difference,
    DifferenceKind,
    ExceptionRecord,
    GateStatus,
    MutationProbe,
    SerializationOrderGate,
    compare_captures,
    compare_exceptions,
    compare_typed,
    inspect_mutation,
    prepare_mutation_probe,
)
from .identity import (
    IdentityError,
    IdentityRecord,
    InputIdentity,
    SourceIdentity,
    require_matching_identity,
    require_sha256_digest,
    sha256_bytes,
    sha256_file,
)


__all__ = [
    "CAPTURE_FORMAT_VERSION",
    "CaptureCodecError",
    "ComparisonResult",
    "Difference",
    "DifferenceKind",
    "ExceptionRecord",
    "GateStatus",
    "IdentityError",
    "IdentityRecord",
    "InputIdentity",
    "MutationProbe",
    "SerializationOrderGate",
    "SourceIdentity",
    "compare_captures",
    "compare_exceptions",
    "compare_typed",
    "decode_typed",
    "encode_typed",
    "inspect_mutation",
    "prepare_mutation_probe",
    "require_matching_identity",
    "require_sha256_digest",
    "sha256_bytes",
    "sha256_file",
    "validate_typed",
]
