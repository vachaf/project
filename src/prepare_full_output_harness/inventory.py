"""Side-effect-free inventory completeness validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .compare import GateStatus
from .identity import InputIdentity


@dataclass(frozen=True)
class InventoryItem:
    """One required case identity with every suite membership preserved."""

    identity: InputIdentity
    suite_memberships: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.suite_memberships or any(not value for value in self.suite_memberships):
            raise ValueError("suite_memberships must contain non-empty values")


@dataclass(frozen=True)
class InventoryResult:
    """Completeness result distinguishing total inventory from successful cases."""

    status: GateStatus
    total_count: int
    successful_count: int
    duplicate_keys: tuple[tuple[str, ...], ...] = ()
    missing_corpus_ids: tuple[str, ...] = ()
    missing_case_keys: tuple[tuple[str, str, str], ...] = ()
    reason_codes: tuple[str, ...] = ()


def validate_inventory(
    items: Iterable[InventoryItem],
    *,
    required_corpus_ids: Iterable[str],
    required_case_keys: Iterable[tuple[str, str, str]],
    successful_keys: Iterable[tuple[str, str, str]] = (),
    csic_identity_available: bool = True,
) -> InventoryResult:
    """Detect duplicate identities and required omissions without auto-skipping."""

    materialized = tuple(items)
    identity_counts: dict[tuple[str, ...], int] = {}
    present_case_keys: set[tuple[str, str, str]] = set()
    present_corpora: set[str] = set()
    for item in materialized:
        key = item.identity.canonical_key()
        identity_counts[key] = identity_counts.get(key, 0) + 1
        present_corpora.add(item.identity.corpus_id)
        present_case_keys.add(
            (item.identity.corpus_id, item.identity.case_id, item.identity.parameter_id)
        )
    duplicates = tuple(key for key, count in identity_counts.items() if count > 1)
    missing_corpora = tuple(value for value in required_corpus_ids if value not in present_corpora)
    missing_cases = tuple(value for value in required_case_keys if value not in present_case_keys)
    success_set = set(successful_keys)
    reason_codes: list[str] = []
    if duplicates:
        reason_codes.append("duplicate_identity")
    if missing_corpora:
        reason_codes.append("required_corpus_missing")
    if missing_cases:
        reason_codes.append("required_case_missing")
    if not csic_identity_available:
        reason_codes.append("csic_identity_unavailable")
    prerequisites_incomplete = bool(missing_corpora or missing_cases) or not csic_identity_available
    if not csic_identity_available:
        status = GateStatus.BLOCKED
    elif prerequisites_incomplete:
        status = GateStatus.BLOCKED
    elif duplicates:
        status = GateStatus.FAIL
    else:
        status = GateStatus.PASS
    return InventoryResult(
        status=status,
        total_count=len(materialized),
        successful_count=len(success_set & present_case_keys),
        duplicate_keys=duplicates,
        missing_corpus_ids=missing_corpora,
        missing_case_keys=missing_cases,
        reason_codes=tuple(reason_codes),
    )
