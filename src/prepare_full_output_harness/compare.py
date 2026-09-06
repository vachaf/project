"""Strict typed-value comparison and input-mutation helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from .capture import TypedNode, encode_typed, validate_typed


class DifferenceKind(str, Enum):
    """Kinds emitted by strict comparison."""

    TYPE_CHANGED = "type_changed"
    VALUE_CHANGED = "value_changed"
    MISSING = "missing"
    ADDED = "added"
    LENGTH_CHANGED = "length_changed"
    SEQUENCE_CHANGED = "sequence_changed"
    DICT_ORDER_CHANGED = "dict_order_changed"
    INPUT_MUTATION = "input_mutation"
    EXCEPTION_CHANGED = "exception_changed"


class GateStatus(str, Enum):
    """Shared gate states; NOT RUN is distinct from successful validation."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT RUN"


@dataclass(frozen=True)
class Difference:
    """One strict difference without rendering raw values in its message."""

    kind: DifferenceKind
    path: str
    before_present: bool = True
    after_present: bool = True
    before_type: str | None = None
    after_type: str | None = None
    before_typed_value: TypedNode | None = None
    after_typed_value: TypedNode | None = None


@dataclass(frozen=True)
class SerializationOrderGate:
    """Separate gate for consumer or byte-serialization order validation."""

    status: GateStatus = GateStatus.NOT_RUN
    difference_count: int = 0
    reason_code: str = "consumer_dependency_not_evaluated"


@dataclass(frozen=True)
class ComparisonResult:
    """Compatibility value result plus the independent order gate."""

    compatibility_status: GateStatus
    compatibility_complete: bool
    differences: tuple[Difference, ...]
    serialization_order: SerializationOrderGate


@dataclass(frozen=True)
class ExceptionRecord:
    """Qualified exception type and exact message captured for error cases."""

    qualified_type: str
    message: str


def _pointer(path: str, token: str) -> str:
    escaped = token.replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}" if path else f"/{escaped}"


def _key_identity(node: TypedNode) -> tuple[str, str]:
    return node["type"], repr(node)


def _difference(
    kind: DifferenceKind,
    path: str,
    before: TypedNode | None,
    after: TypedNode | None,
    *,
    before_present: bool = True,
    after_present: bool = True,
) -> Difference:
    return Difference(
        kind=kind,
        path=path or "/",
        before_present=before_present,
        after_present=after_present,
        before_type=before.get("type") if before else None,
        after_type=after.get("type") if after else None,
        before_typed_value=before,
        after_typed_value=after,
    )


def compare_typed(before: TypedNode, after: TypedNode) -> tuple[Difference, ...]:
    """Recursively compare typed captures without sorting or normalizing values."""

    validate_typed(before)
    validate_typed(after)
    differences: list[Difference] = []

    def visit(left: TypedNode, right: TypedNode, path: str) -> None:
        left_type = left.get("type")
        right_type = right.get("type")
        if left_type != right_type:
            differences.append(_difference(DifferenceKind.TYPE_CHANGED, path, left, right))
            return
        if left_type in {"null"}:
            return
        if left_type in {"bool", "int", "float", "str"}:
            if left.get("value") != right.get("value"):
                differences.append(_difference(DifferenceKind.VALUE_CHANGED, path, left, right))
            return
        if left_type in {"list", "tuple"}:
            left_items = left.get("items", [])
            right_items = right.get("items", [])
            if len(left_items) != len(right_items):
                differences.append(_difference(DifferenceKind.LENGTH_CHANGED, path, left, right))
            for index in range(min(len(left_items), len(right_items))):
                visit(left_items[index], right_items[index], _pointer(path, str(index)))
            if left_items != right_items:
                differences.append(_difference(DifferenceKind.SEQUENCE_CHANGED, path, left, right))
            return
        if left_type == "dict":
            left_entries = left.get("entries", [])
            right_entries = right.get("entries", [])
            left_by_key = {
                _key_identity(entry["key"]): (index, entry)
                for index, entry in enumerate(left_entries)
            }
            right_by_key = {
                _key_identity(entry["key"]): (index, entry)
                for index, entry in enumerate(right_entries)
            }
            for identity, (index, entry) in left_by_key.items():
                entry_path = _pointer(_pointer(path, "entries"), str(index))
                if identity not in right_by_key:
                    differences.append(
                        _difference(
                            DifferenceKind.MISSING,
                            entry_path,
                            entry["value"],
                            None,
                            after_present=False,
                        )
                    )
                else:
                    visit(entry["value"], right_by_key[identity][1]["value"], entry_path)
            for identity, (index, entry) in right_by_key.items():
                if identity not in left_by_key:
                    differences.append(
                        _difference(
                            DifferenceKind.ADDED,
                            _pointer(_pointer(path, "entries"), str(index)),
                            None,
                            entry["value"],
                            before_present=False,
                        )
                    )
            left_order = [_key_identity(entry["key"]) for entry in left_entries]
            right_order = [_key_identity(entry["key"]) for entry in right_entries]
            if set(left_order) == set(right_order) and left_order != right_order:
                differences.append(_difference(DifferenceKind.DICT_ORDER_CHANGED, path, left, right))
            return
        differences.append(_difference(DifferenceKind.TYPE_CHANGED, path, left, right))

    visit(before, after, "")
    return tuple(differences)


def compare_captures(before: TypedNode, after: TypedNode) -> ComparisonResult:
    """Return value compatibility separately from the unexecuted order gate."""

    differences = compare_typed(before, after)
    blocking = tuple(diff for diff in differences if diff.kind != DifferenceKind.DICT_ORDER_CHANGED)
    order_count = sum(diff.kind == DifferenceKind.DICT_ORDER_CHANGED for diff in differences)
    return ComparisonResult(
        compatibility_status=GateStatus.PASS if not blocking else GateStatus.FAIL,
        compatibility_complete=False,
        differences=differences,
        serialization_order=SerializationOrderGate(difference_count=order_count),
    )


def compare_exceptions(
    before: ExceptionRecord | None, after: ExceptionRecord | None
) -> tuple[Difference, ...]:
    """Compare exact exception presence, qualified type, and message."""

    if before == after:
        return ()
    return (
        Difference(
            kind=DifferenceKind.EXCEPTION_CHANGED,
            path="/exception",
            before_present=before is not None,
            after_present=after is not None,
            before_type="dict" if before else None,
            after_type="dict" if after else None,
            before_typed_value=encode_typed(
                {"qualified_type": before.qualified_type, "message": before.message}
            )
            if before
            else None,
            after_typed_value=encode_typed(
                {"qualified_type": after.qualified_type, "message": after.message}
            )
            if after
            else None,
        ),
    )


T = TypeVar("T")


@dataclass(frozen=True)
class MutationProbe:
    """Fresh call input and its immutable pre-call capture."""

    call_input: Any
    before: TypedNode


def prepare_mutation_probe(value: T) -> MutationProbe:
    """Create the required fresh deep copy and capture it immediately."""

    call_input = copy.deepcopy(value)
    return MutationProbe(call_input=call_input, before=encode_typed(call_input))


def inspect_mutation(probe: MutationProbe) -> tuple[Difference, ...]:
    """Report post-call mutation without restoring or concealing the input."""

    after = encode_typed(probe.call_input)
    changes = compare_typed(probe.before, after)
    if not changes:
        return ()
    return (
        Difference(
            kind=DifferenceKind.INPUT_MUTATION,
            path="/",
            before_type=probe.before.get("type"),
            after_type=after.get("type"),
            before_typed_value=probe.before,
            after_typed_value=after,
        ),
        *changes,
    )
