"""Lossless typed capture codec for Prepare harness values."""

from __future__ import annotations

import math
from typing import Any, TypeAlias


CAPTURE_FORMAT_VERSION = "prepare_full_output_capture.v1"
TypedNode: TypeAlias = dict[str, Any]


class CaptureCodecError(ValueError):
    """Raised when a value cannot be represented by the typed codec."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def encode_typed(value: Any) -> TypedNode:
    """Encode a supported value without modifying it or losing type details."""

    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CaptureCodecError("non_finite_float", "non-finite float is not supported")
        return {"type": "float", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, list):
        return {"type": "list", "items": [encode_typed(item) for item in value]}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [encode_typed(item) for item in value]}
    if isinstance(value, dict):
        return {
            "type": "dict",
            "entries": [
                {"key": encode_typed(key), "value": encode_typed(item)}
                for key, item in value.items()
            ],
        }
    raise CaptureCodecError(
        "unsupported_type",
        f"unsupported value type: {type(value).__module__}.{type(value).__qualname__}",
    )


def _require_exact_keys(node: TypedNode, expected: set[str]) -> None:
    if set(node) != expected:
        raise CaptureCodecError("invalid_node", "typed node has invalid fields")


def decode_typed(node: TypedNode) -> Any:
    """Decode a validated typed node to its original supported Python type."""

    if not isinstance(node, dict) or not isinstance(node.get("type"), str):
        raise CaptureCodecError("invalid_node", "typed node must be a mapping with a type")
    node_type = node["type"]
    if node_type == "null":
        _require_exact_keys(node, {"type"})
        return None
    if node_type == "bool":
        _require_exact_keys(node, {"type", "value"})
        if not isinstance(node["value"], bool):
            raise CaptureCodecError("invalid_node", "bool node value must be bool")
        return node["value"]
    if node_type == "int":
        _require_exact_keys(node, {"type", "value"})
        value = node["value"]
        if not isinstance(value, str):
            raise CaptureCodecError("invalid_node", "int node must use canonical decimal text")
        try:
            decoded_int = int(value)
        except ValueError as exc:
            raise CaptureCodecError("invalid_node", "int node has invalid decimal text") from exc
        if str(decoded_int) != value:
            raise CaptureCodecError("invalid_node", "int node must use canonical decimal text")
        return decoded_int
    if node_type == "float":
        _require_exact_keys(node, {"type", "value"})
        value = node["value"]
        if not isinstance(value, str):
            raise CaptureCodecError("invalid_node", "float node value must be text")
        try:
            decoded = float.fromhex(value)
        except ValueError as exc:
            raise CaptureCodecError("invalid_node", "float node has invalid hexadecimal text") from exc
        if not math.isfinite(decoded) or decoded.hex() != value:
            raise CaptureCodecError("invalid_node", "float node must be finite and canonical")
        return decoded
    if node_type == "str":
        _require_exact_keys(node, {"type", "value"})
        if not isinstance(node["value"], str):
            raise CaptureCodecError("invalid_node", "str node value must be text")
        return node["value"]
    if node_type in {"list", "tuple"}:
        _require_exact_keys(node, {"type", "items"})
        items = node["items"]
        if not isinstance(items, list):
            raise CaptureCodecError("invalid_node", "sequence node items must be an array")
        decoded_items = [decode_typed(item) for item in items]
        return decoded_items if node_type == "list" else tuple(decoded_items)
    if node_type == "dict":
        _require_exact_keys(node, {"type", "entries"})
        entries = node["entries"]
        if not isinstance(entries, list):
            raise CaptureCodecError("invalid_node", "dict node entries must be an array")
        result: dict[Any, Any] = {}
        encoded_keys: list[TypedNode] = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"key", "value"}:
                raise CaptureCodecError("invalid_node", "dict entry must contain key and value")
            if any(entry["key"] == previous for previous in encoded_keys):
                raise CaptureCodecError(
                    "duplicate_encoded_key", "typed dict contains a duplicate encoded key"
                )
            encoded_keys.append(entry["key"])
            key = decode_typed(entry["key"])
            try:
                if key in result:
                    raise CaptureCodecError("duplicate_key", "decoded dict contains a duplicate key")
                result[key] = decode_typed(entry["value"])
            except TypeError as exc:
                raise CaptureCodecError("unhashable_key", "decoded dict key is not hashable") from exc
        return result
    raise CaptureCodecError("invalid_node", "typed node has an unknown type")


def validate_typed(node: TypedNode) -> None:
    """Reject malformed captures, including duplicate encoded dictionary keys."""

    decode_typed(node)
