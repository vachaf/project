"""Frozen additive contract for honest Stage E cross-revision verification."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path, PurePosixPath
from typing import Iterable

from .identity import require_sha256_digest
from .isolation import FIXED_INSTANT, PROCESS_TIMEZONE

BEFORE_REVISION = "4eab95703e00373428e7ea3ec8ca58e0f09ae7c2"
BEFORE_TREE = "3547c35e6127807bd1e37029ac5dead60832b619"
BEFORE_SOURCE_DIGEST = "d3fe53cf3970d9ea02614d2b7c126adb866ecce0914cb990c187ccb9f917a841"
BEFORE_VERIFICATION_REVISION = "7d9a4929939eba037e4a6029862114664b01ca71"
AFTER_REVISION = "8ae1cf125c77b58f0f848847f889d92fe9006f52"
AFTER_TREE = "2235ebb8d662a69674ce4fe5a3d6626023b48e19"
PARAMETER_ID = "prepare-security-score4-repeat3.v1"
MIN_SCORE = 4
MIN_REPEAT_AGGREGATE = 3
SOURCE_TABLES = ("security",)
CORPUS_ID = "prepare_regression"
PROTOCOL_VERSION = "prepare_after_capture_child.v1"
OUTPUT_SLOT_NAMES = ("llm_input", "candidate_payload", "noise_payload", "filtered_reasons_payload", "filtered_payload")
CANONICAL_FIXTURES = (
    "b_r2b_double_encoded_sqli.json", "b_r2b_educational_sql_fp.json", "c_html_entity_xss.json",
    "c_xss_fp_review.json", "d_r3_directory_probing.json", "e_r2_direct_config_path.json",
    "e_r2_php_wrapper.json", "e_r3_search_attack_and_baseline.json", "f_r1_auth_behavior_context.json",
    "g_r1_method_behavior_context.json", "g_r2_protocol_anomaly_context.json", "h_r1_static_baseline_context.json",
    "h_r2_crawler_baseline_context.json", "h_r3_sensitive_path_probe_context.json",
    "h_r4_mixed_baseline_scanner_context.json", "ip_behavior_multi_signal_context.json",
    "l3_graphql_introspection_context.json", "l3_log4shell_obfuscated_payload_context.json",
    "l3_log4shell_ssrf_context.json", "l3_open_redirect_external_url_context.json",
    "l3_ssrf_metadata_endpoint_context.json", "l3_ssti_template_expression_context.json",
    "l3_ssti_webshell_context.json", "l3_webshell_admin_tool_probe_context.json",
    "l3_xxe_external_entity_context.json",
)
AFTER_SOURCE_FILES = (
    "src/prepare/__init__.py", "src/prepare/apache_observability_context.py", "src/prepare/auth_behavior.py",
    "src/prepare/crawler_baseline.py", "src/prepare/decoders.py", "src/prepare/file_disclosure_hints.py",
    "src/prepare/ip_behavior.py", "src/prepare/l3_hints.py", "src/prepare/method_summaries.py",
    "src/prepare/mixed_baseline_scanner.py", "src/prepare/models.py", "src/prepare/probing_sequence.py",
    "src/prepare/protocol_anomalies.py", "src/prepare/sensitive_path_probe.py", "src/prepare/sqli_hints.py",
    "src/prepare/static_baseline.py", "src/prepare/traversal_cmdi_hints.py", "src/prepare/xss_hints.py",
    "src/prepare_llm_input.py", "src/prepare/shared_signal_adapter.py", "src/security_signals/__init__.py",
    "src/security_signals/extractor.py",
)

class ExitCode(IntEnum):
    PASS = 0
    FAIL = 1
    BLOCKED = 2

class AfterContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message); self.code = code

def digest_files(root: str | Path, names: Iterable[str]) -> str:
    base = Path(root).resolve(strict=True); digest = hashlib.sha256(); paths = tuple(names)
    if not paths or len(paths) != len(set(paths)):
        raise AfterContractError("invalid_inventory", "inventory must be non-empty and unique")
    for name in paths:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or str(pure) != name:
            raise AfterContractError("unsafe_inventory", "inventory path is unsafe")
        path = base.joinpath(*pure.parts)
        if not path.is_file() or path.is_symlink():
            raise AfterContractError("inventory_file_missing", f"inventory file missing: {name}")
        data = path.read_bytes(); encoded = name.encode()
        digest.update(len(encoded).to_bytes(8, "big")); digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return digest.hexdigest()

def after_source_digest(root: str | Path) -> str:
    return digest_files(root, AFTER_SOURCE_FILES)

@dataclass(frozen=True)
class AfterIdentity:
    subject_revision: str
    subject_tree: str
    verification_revision: str
    source_tree_digest: str
    runner_digest: str
    harness_digest: str
    adapter_digest: str
    def __post_init__(self) -> None:
        if self.subject_revision != AFTER_REVISION or self.subject_tree != AFTER_TREE:
            raise AfterContractError("subject_identity_mismatch", "After revision or tree is not approved")
        if not re.fullmatch(r"[0-9a-f]{40}", self.verification_revision):
            raise AfterContractError("invalid_verification_revision", "verification revision must be a SHA")
        for name in ("source_tree_digest", "runner_digest", "harness_digest", "adapter_digest"):
            require_sha256_digest(name, getattr(self, name))
    def as_dict(self) -> dict[str, str]: return dict(self.__dict__)

@dataclass(frozen=True)
class AfterCaptureRequest:
    run_role: str
    subject_root: str
    input_path: str
    case_id: str
    identity: AfterIdentity
    def __post_init__(self) -> None:
        if self.run_role not in {"after-1", "after-2"}: raise AfterContractError("invalid_run_role", "invalid After role")
        if not self.subject_root or not self.input_path or not self.case_id: raise AfterContractError("invalid_request", "request fields are required")
    def as_dict(self) -> dict[str, object]:
        return {"protocol_version": PROTOCOL_VERSION, "run_role": self.run_role, "subject_root": self.subject_root,
                "input_path": self.input_path, "corpus_id": CORPUS_ID, "case_id": self.case_id,
                "parameter_id": PARAMETER_ID, "parameters": {"min_score": MIN_SCORE, "min_repeat_aggregate": MIN_REPEAT_AGGREGATE, "source_tables": list(SOURCE_TABLES)},
                "clock": {"fixed_instant": FIXED_INSTANT, "process_timezone": PROCESS_TIMEZONE}, "identity": self.identity.as_dict()}
    def to_json(self) -> str: return json.dumps(self.as_dict(), ensure_ascii=False, separators=(",", ":"))
