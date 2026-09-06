from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.prepare_full_output_harness.artifacts import (
    ArtifactError,
    ArtifactWriter,
    require_completed_read_only_baseline,
    validate_distinct_run_paths,
    validate_new_output_root,
)
from src.prepare_full_output_harness.capture import CaptureCodecError, decode_typed, encode_typed
from src.prepare_full_output_harness.compare import (
    DifferenceKind,
    ExceptionRecord,
    GateStatus,
    compare_captures,
    compare_exceptions,
    compare_typed,
    inspect_mutation,
    prepare_mutation_probe,
)
from src.prepare_full_output_harness.identity import (
    IdentityError,
    IdentityRecord,
    InputIdentity,
    SourceIdentity,
    require_matching_identity,
)
from src.prepare_full_output_harness.inventory import (
    InventoryItem,
    validate_inventory,
)


def difference_kinds(before: object, after: object) -> set[DifferenceKind]:
    return {diff.kind for diff in compare_typed(encode_typed(before), encode_typed(after))}


def input_identity(**changes: str) -> InputIdentity:
    values = {
        "corpus_id": "synthetic",
        "case_id": "case-1",
        "source_revision": "revision-1",
        "source_file_sha256": "a" * 64,
        "adapter_version": "adapter.v1",
        "parameter_id": "default",
        "raw_source_hash": "b" * 64,
        "projected_payload_hash": "c" * 64,
    }
    values.update(changes)
    return InputIdentity(**values)


def identity_record(**changes: str) -> IdentityRecord:
    return IdentityRecord(
        source=SourceIdentity("revision-1", "d" * 64, "e" * 64, "f" * 64),
        input=input_identity(**changes),
    )


def test_identical_typed_object_has_zero_differences() -> None:
    value = {"reasons": ["same", "same"], "slot": (None, False, 1, 1.0, "1")}
    captured = encode_typed(value)
    assert decode_typed(captured) == value
    assert compare_typed(captured, captured) == ()


def test_field_deletion_and_addition_are_distinct() -> None:
    kinds = difference_kinds({"kept": 1, "deleted": 2}, {"kept": 1, "added": 3})
    assert DifferenceKind.MISSING in kinds
    assert DifferenceKind.ADDED in kinds


def test_none_replacement_is_type_change() -> None:
    assert DifferenceKind.TYPE_CHANGED in difference_kinds({"value": ""}, {"value": None})


def test_bool_and_int_are_not_equal() -> None:
    assert DifferenceKind.TYPE_CHANGED in difference_kinds(True, 1)
    assert decode_typed(encode_typed(False)) is False


@pytest.mark.parametrize("after", [1.0, "1"])
def test_int_float_and_string_are_not_equal(after: object) -> None:
    assert DifferenceKind.TYPE_CHANGED in difference_kinds(1, after)


def test_large_integer_round_trip_is_lossless() -> None:
    value = 10**200 + 123456789
    node = encode_typed(value)
    assert node == {"type": "int", "value": str(value)}
    assert decode_typed(node) == value


def test_negative_zero_round_trip_preserves_sign() -> None:
    value = decode_typed(encode_typed(-0.0))
    assert math.copysign(1.0, value) == -1.0
    assert DifferenceKind.VALUE_CHANGED in difference_kinds(-0.0, 0.0)


def test_tuple_and_list_are_not_equal() -> None:
    assert DifferenceKind.TYPE_CHANGED in difference_kinds((1, 2), [1, 2])


def test_list_order_change_is_sequence_change() -> None:
    kinds = difference_kinds(["first", "second"], ["second", "first"])
    assert DifferenceKind.SEQUENCE_CHANGED in kinds


def test_reason_duplicate_deletion_is_blocking() -> None:
    result = compare_captures(
        encode_typed({"reason_hints": ["reason", "reason"]}),
        encode_typed({"reason_hints": ["reason"]}),
    )
    assert result.compatibility_status == GateStatus.FAIL
    assert DifferenceKind.LENGTH_CHANGED in {diff.kind for diff in result.differences}


def test_dict_insertion_order_is_separate_not_run_gate() -> None:
    before = {"first": 1, "second": 2}
    after = {"second": 2, "first": 1}
    result = compare_captures(encode_typed(before), encode_typed(after))
    assert result.compatibility_status == GateStatus.PASS
    assert result.compatibility_complete is False
    assert result.serialization_order.status == GateStatus.NOT_RUN
    assert result.serialization_order.difference_count == 1
    assert {diff.kind for diff in result.differences} == {DifferenceKind.DICT_ORDER_CHANGED}


def test_new_nested_field_is_added() -> None:
    assert DifferenceKind.ADDED in difference_kinds({"meta": {}}, {"meta": {"new": 0}})


def test_comparator_rejects_malformed_typed_node() -> None:
    with pytest.raises(CaptureCodecError) as raised:
        compare_typed({"type": "list", "items": "not-an-array"}, encode_typed([]))
    assert raised.value.code == "invalid_node"


def test_comparator_rejects_duplicate_encoded_dict_key() -> None:
    duplicate_key_node = {
        "type": "dict",
        "entries": [
            {"key": encode_typed("same"), "value": encode_typed(1)},
            {"key": encode_typed("same"), "value": encode_typed(2)},
        ],
    }
    with pytest.raises(CaptureCodecError) as raised:
        compare_typed(duplicate_key_node, encode_typed({"same": 1}))
    assert raised.value.code == "duplicate_encoded_key"


def test_exception_diff_preserves_exact_type_and_message_as_typed_values() -> None:
    before = ExceptionRecord("package.BeforeError", "before: exact message")
    after = ExceptionRecord("package.AfterError", "after: exact message")
    difference = compare_exceptions(before, after)[0]

    assert decode_typed(difference.before_typed_value) == {
        "qualified_type": "package.BeforeError",
        "message": "before: exact message",
    }
    assert decode_typed(difference.after_typed_value) == {
        "qualified_type": "package.AfterError",
        "message": "after: exact message",
    }


@pytest.mark.parametrize("value", [object(), float("inf"), float("nan")])
def test_unsupported_or_non_finite_value_is_rejected(value: object) -> None:
    with pytest.raises(CaptureCodecError):
        encode_typed(value)


def test_input_mutation_is_reported_without_restoring_input() -> None:
    original = {"reason_hints": ["one", "one"]}
    probe = prepare_mutation_probe(original)
    probe.call_input["reason_hints"].pop()
    differences = inspect_mutation(probe)
    assert differences[0].kind == DifferenceKind.INPUT_MUTATION
    assert probe.call_input == {"reason_hints": ["one"]}
    assert original == {"reason_hints": ["one", "one"]}


def test_missing_identity_field_is_rejected() -> None:
    with pytest.raises(IdentityError, match="identity field is required"):
        input_identity(case_id="")


def test_identity_mismatch_is_rejected_even_when_payload_hash_matches() -> None:
    with pytest.raises(IdentityError) as raised:
        require_matching_identity(identity_record(), identity_record(source_revision="revision-2"))
    assert raised.value.code == "identity_mismatch"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_file_sha256", "A" * 64),
        ("raw_source_hash", "a" * 63),
        ("projected_payload_hash", "g" * 64),
    ],
)
def test_input_identity_rejects_noncanonical_sha256(field: str, value: str) -> None:
    with pytest.raises(IdentityError) as raised:
        input_identity(**{field: value})
    assert raised.value.code == "invalid_sha256"


@pytest.mark.parametrize("field", ["source_tree_digest", "harness_digest", "adapter_digest"])
def test_source_identity_rejects_noncanonical_digest(field: str) -> None:
    values = {
        "source_revision": "revision-1",
        "source_tree_digest": "d" * 64,
        "harness_digest": "e" * 64,
        "adapter_digest": "f" * 64,
    }
    values[field] = "0X" + "a" * 62
    with pytest.raises(IdentityError) as raised:
        SourceIdentity(**values)
    assert raised.value.code == "invalid_sha256"


def test_inventory_detects_duplicate_identity() -> None:
    item = InventoryItem(input_identity(), ("suite-a", "suite-b"))
    result = validate_inventory(
        [item, item],
        required_corpus_ids=["synthetic"],
        required_case_keys=[("synthetic", "case-1", "default")],
    )
    assert result.status == GateStatus.FAIL
    assert result.reason_codes == ("duplicate_identity",)
    assert item.suite_memberships == ("suite-a", "suite-b")


def test_inventory_detects_required_corpus_and_case_omissions() -> None:
    result = validate_inventory(
        [],
        required_corpus_ids=["synthetic"],
        required_case_keys=[("synthetic", "case-1", "default")],
    )
    assert result.status == GateStatus.BLOCKED
    assert result.total_count == 0
    assert result.successful_count == 0
    assert result.reason_codes == ("required_corpus_missing", "required_case_missing")


def test_inventory_duplicate_is_blocked_when_required_case_is_missing() -> None:
    item = InventoryItem(input_identity(), ("suite-a",))
    result = validate_inventory(
        [item, item],
        required_corpus_ids=["synthetic"],
        required_case_keys=[("synthetic", "missing", "default")],
    )
    assert result.status == GateStatus.BLOCKED
    assert result.reason_codes == ("duplicate_identity", "required_case_missing")


def test_inventory_can_block_on_missing_csic_identity() -> None:
    result = validate_inventory(
        [], required_corpus_ids=[], required_case_keys=[], csic_identity_available=False
    )
    assert result.status == GateStatus.BLOCKED
    assert result.reason_codes == ("csic_identity_unavailable",)


def test_existing_artifact_root_is_rejected(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ArtifactError) as raised:
        validate_new_output_root(existing)
    assert raised.value.code == "output_exists"


def test_symlink_artifact_path_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ArtifactError) as raised:
        validate_new_output_root(linked / "run")
    assert raised.value.code == "symlink_path"


@pytest.mark.parametrize(
    "paths",
    [
        {
            "before-1": "runs/shared",
            "before-2": "runs/shared/child",
            "after": "runs/after",
            "comparison": "runs/comparison",
        },
        {
            "before-1": "runs/before-1/child",
            "before-2": "runs/before-2",
            "after": "runs/before-1",
            "comparison": "runs/comparison",
        },
    ],
)
def test_run_paths_reject_parent_child_nesting(paths: dict[str, str]) -> None:
    with pytest.raises(ArtifactError) as raised:
        validate_distinct_run_paths(paths)
    assert raised.value.code == "run_paths_overlap"


def test_incomplete_run_has_no_completion_marker(tmp_path: Path) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("comparison/summary.json", {"status": "NOT RUN"})
    assert not (writer.root / "completion.json").exists()
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "baseline_incomplete"


def test_finalize_checksum_mismatch_leaves_retryable_incomplete_run(tmp_path: Path) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_bytes("captures/case.json", b"original\n")
    (writer.root / "captures/case.json").write_bytes(b"tampered\n")

    with pytest.raises(ArtifactError) as raised:
        writer.finalize()

    assert raised.value.code == "checksum_mismatch"
    assert not (writer.root / "checksums.sha256").exists()
    assert not (writer.root / "completion.json").exists()


def test_finalize_checksum_publish_failure_rolls_back_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("comparison/summary.json", {"status": "NOT RUN"})
    original_write_bytes = writer.write_bytes
    failed_once = False

    def fail_checksum_once(relative_path: str, payload: bytes) -> str:
        nonlocal failed_once
        if relative_path == "checksums.sha256" and not failed_once:
            failed_once = True
            raise OSError("injected checksum publication failure")
        return original_write_bytes(relative_path, payload)

    monkeypatch.setattr(writer, "write_bytes", fail_checksum_once)
    with pytest.raises(OSError, match="injected checksum publication failure"):
        writer.finalize()

    assert not (writer.root / "checksums.sha256").exists()
    assert not (writer.root / "completion.json").exists()
    writer.finalize()
    assert (writer.root / "completion.json").is_file()


def test_finalize_completion_publish_failure_rolls_back_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("comparison/summary.json", {"status": "NOT RUN"})
    original_write_json = writer.write_json
    failed_once = False

    def fail_completion_once(relative_path: str, value: object) -> str:
        nonlocal failed_once
        if relative_path == "completion.json" and not failed_once:
            failed_once = True
            raise OSError("injected completion publication failure")
        return original_write_json(relative_path, value)

    monkeypatch.setattr(writer, "write_json", fail_completion_once)
    with pytest.raises(OSError, match="injected completion publication failure"):
        writer.finalize()

    assert not (writer.root / "checksums.sha256").exists()
    assert not (writer.root / "completion.json").exists()
    writer.finalize()
    assert (writer.root / "completion.json").is_file()


def test_finalize_success_writes_verified_manifest_then_completion(tmp_path: Path) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    payload_digest = writer.write_json(
        "comparison/summary.json", {"status": "NOT RUN"}
    )

    writer.finalize()

    assert (writer.root / "checksums.sha256").read_text(encoding="utf-8") == (
        f"{payload_digest}  comparison/summary.json\n"
    )
    assert (writer.root / "completion.json").read_text(encoding="utf-8") == (
        '{"complete":true,"checksum_ready":true}\n'
    )
    assert require_completed_read_only_baseline(writer.root) == writer.root
    with pytest.raises(ArtifactError) as raised:
        writer.write_bytes("late.json", b"{}\n")
    assert raised.value.code == "run_completed"


def test_baseline_rejects_invalid_completion_content(tmp_path: Path) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("capture.json", {"case": "one"})
    writer.finalize()
    (writer.root / "completion.json").write_text(
        '{"complete":false,"checksum_ready":true}\n', encoding="utf-8"
    )
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "invalid_completion"


@pytest.mark.parametrize(
    "manifest_line",
    [
        "not-a-digest  capture.json\n",
        f"{'a' * 64} capture.json\n",
        f"{'A' * 64}  capture.json\n",
        f"{'a' * 64}  capture.json",
    ],
)
def test_baseline_rejects_malformed_checksum_manifest(
    tmp_path: Path, manifest_line: str
) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("capture.json", {"case": "one"})
    writer.finalize()
    (writer.root / "checksums.sha256").write_text(manifest_line, encoding="utf-8")
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "invalid_checksums"


@pytest.mark.parametrize("unsafe_path", ["../capture.json", "nested\\capture.json"])
def test_baseline_rejects_unsafe_checksum_relative_path(
    tmp_path: Path, unsafe_path: str
) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    digest = writer.write_json("capture.json", {"case": "one"})
    writer.finalize()
    (writer.root / "checksums.sha256").write_text(
        f"{digest}  {unsafe_path}\n", encoding="utf-8"
    )
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "unsafe_checksum_path"


def test_baseline_rejects_payload_checksum_mismatch(tmp_path: Path) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("capture.json", {"case": "one"})
    writer.finalize()
    (writer.root / "capture.json").write_bytes(b"tampered\n")
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "checksum_mismatch"


def test_baseline_rejects_unrecorded_payload(tmp_path: Path) -> None:
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("capture.json", {"case": "one"})
    writer.finalize()
    (writer.root / "unrecorded.json").write_bytes(b"{}\n")
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "checksum_inventory_mismatch"


def test_baseline_rejects_symlinked_payload(tmp_path: Path) -> None:
    external = tmp_path / "external.json"
    external.write_bytes(b"external\n")
    writer = ArtifactWriter.create(tmp_path / "run")
    writer.write_json("capture.json", {"case": "one"})
    writer.finalize()
    (writer.root / "capture.json").unlink()
    (writer.root / "capture.json").symlink_to(external)
    with pytest.raises(ArtifactError) as raised:
        require_completed_read_only_baseline(writer.root)
    assert raised.value.code == "symlink_path"
