#!/usr/bin/env python3
"""Local-only CSIC 2010 acquisition, integrity, and raw HTTP accounting.

This module deliberately stops before Apache projection, Prepare, Stage1, or
semantic attack annotation.  Raw corpus bytes belong in an ignored local cache;
the tracked manifest records provenance and accounting but never request text.
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import mmap
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.request import Request, urlopen


SCHEMA_VERSION = "csic2010_source_manifest.v1"
DATASET_NAME = "HTTP DATASET CSIC 2010"
INVENTORY_SCHEMA_VERSION = "external_security_benchmark_csic2010_source_inventory.v1"
DOCUMENTED_COUNTS = {
    "normalTrafficTraining.txt": 36000,
    "normalTrafficTest.txt": 36000,
    "anomalousTrafficTest.txt": 25065,
}
FILE_SPECS = (
    {
        "filename": "normalTrafficTraining.txt",
        "source_label": "source_normal",
        "role": "training",
        "primary_url": "https://raw.githubusercontent.com/msudol/Web-Application-Attack-Datasets/master/OriginalDataSets/csic_2010/normalTrafficTraining.txt",
        "comparison_url": "https://raw.githubusercontent.com/sunbeamdotpt/csic-dataset/mainline/normalTrafficTraining.txt",
    },
    {
        "filename": "normalTrafficTest.txt",
        "source_label": "source_normal",
        "role": "test",
        "primary_url": "https://raw.githubusercontent.com/msudol/Web-Application-Attack-Datasets/master/OriginalDataSets/csic_2010/normalTrafficTest.txt",
        "comparison_url": "https://raw.githubusercontent.com/sunbeamdotpt/csic-dataset/mainline/normalTrafficTest.txt",
    },
    {
        "filename": "anomalousTrafficTest.txt",
        "source_label": "source_anomalous",
        "role": "test",
        "primary_url": "https://raw.githubusercontent.com/msudol/Web-Application-Attack-Datasets/master/OriginalDataSets/csic_2010/anomalousTrafficTest.txt",
        "comparison_url": "https://raw.githubusercontent.com/sunbeamdotpt/csic-dataset/mainline/anomalousTrafficTest.txt",
    },
)
REQUEST_LINE_RE = re.compile(rb"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+ [^ ]+ HTTP/[0-9]+\.[0-9]+$")
HEADER_NAME_RE = re.compile(rb"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class Header:
    """One case-preserving raw header; duplicate names are intentionally retained."""

    name: bytes
    value: bytes
    raw_line: bytes


@dataclass(frozen=True)
class RawHttpRequest:
    source_file: str
    source_label: str
    request_index: int
    start_offset: int
    end_offset: int
    raw_request_sha256: str
    request_line: bytes
    method: str
    raw_target: bytes
    http_version: bytes
    headers: tuple[Header, ...]
    body_bytes: bytes
    raw_request_bytes: bytes

    @property
    def request_id(self) -> str:
        return f"csic2010:{self.source_file}:{self.request_index:06d}"


@dataclass(frozen=True)
class ParseAccounting:
    source_bytes: int
    request_bytes: int
    separator_bytes: int
    unaccounted_bytes: int
    parsed_requests: int


class RawHttpParseError(ValueError):
    def __init__(self, error_type: str, offset: int, request_index: int, data: bytes | mmap.mmap):
        self.error_type = error_type
        self.offset = offset
        self.request_index = request_index
        self.context_sha256 = hashlib.sha256(bytes(data[offset : offset + 64])).hexdigest()
        super().__init__(f"{error_type} at byte {offset} before request {request_index}")


def _read_line(data: bytes | mmap.mmap, position: int, request_index: int) -> tuple[bytes, int]:
    newline = data.find(b"\n", position)
    if newline < 0:
        raise RawHttpParseError("unterminated_line", position, request_index, data)
    line_end = newline - 1 if newline > position and data[newline - 1] == 13 else newline
    return bytes(data[position:line_end]), newline + 1


def _skip_separators(data: bytes | mmap.mmap, position: int) -> tuple[int, int]:
    start = position
    while position < len(data) and data[position] in (10, 13):
        position += 1
    return position, position - start


def _content_length(headers: Sequence[Header], data: bytes | mmap.mmap, offset: int, request_index: int) -> int | None:
    values = [header.value.strip() for header in headers if header.name.lower() == b"content-length"]
    if not values:
        return None
    if len(values) != 1:
        raise RawHttpParseError("duplicate_content_length", offset, request_index, data)
    value = values[0]
    if value.startswith(b"-"):
        raise RawHttpParseError("negative_content_length", offset, request_index, data)
    if not value or not value.isdigit():
        raise RawHttpParseError("invalid_content_length", offset, request_index, data)
    return int(value)


def parse_raw_http_stream(
    data: bytes | mmap.mmap,
    *,
    source_file: str,
    source_label: str,
    on_request: Callable[[RawHttpRequest], None],
) -> ParseAccounting:
    """Parse raw HTTP bytes with Content-Length framing and byte offsets.

    A blank line is considered an inter-request separator only after a request
    body has been consumed.  The callback model lets corpus inventory remain
    bounded-memory even though each request retains its own source bytes.
    """

    position = 0
    separator_bytes = 0
    request_bytes = 0
    request_index = 0
    while position < len(data):
        position, skipped = _skip_separators(data, position)
        separator_bytes += skipped
        if position >= len(data):
            break
        start = position
        request_index += 1
        request_line, position = _read_line(data, position, request_index)
        if not REQUEST_LINE_RE.fullmatch(request_line):
            raise RawHttpParseError("invalid_request_line", start, request_index, data)
        method_bytes, raw_target, http_version = request_line.split(b" ", 2)
        headers: list[Header] = []
        while True:
            header_offset = position
            line, position = _read_line(data, position, request_index)
            if not line:
                break
            if b":" not in line:
                raise RawHttpParseError("malformed_header", header_offset, request_index, data)
            name, value = line.split(b":", 1)
            if not HEADER_NAME_RE.fullmatch(name):
                raise RawHttpParseError("invalid_header_name", header_offset, request_index, data)
            headers.append(Header(name=name, value=value.lstrip(b" \t"), raw_line=line))
        length = _content_length(headers, data, position, request_index)
        if length is None:
            body = b""
        else:
            if position + length > len(data):
                raise RawHttpParseError("truncated_body", position, request_index, data)
            body = bytes(data[position : position + length])
            position += length
        end = position
        raw_request = bytes(data[start:end])
        request_bytes += end - start
        on_request(
            RawHttpRequest(
                source_file=source_file,
                source_label=source_label,
                request_index=request_index,
                start_offset=start,
                end_offset=end,
                raw_request_sha256=hashlib.sha256(raw_request).hexdigest(),
                request_line=request_line,
                method=method_bytes.decode("ascii"),
                raw_target=raw_target,
                http_version=http_version,
                headers=tuple(headers),
                body_bytes=body,
                raw_request_bytes=raw_request,
            )
        )
    return ParseAccounting(
        source_bytes=len(data),
        request_bytes=request_bytes,
        separator_bytes=separator_bytes,
        unaccounted_bytes=len(data) - request_bytes - separator_bytes,
        parsed_requests=request_index,
    )


def parse_raw_http_requests(data: bytes, *, source_file: str = "fixture.txt", source_label: str = "source_normal") -> tuple[list[RawHttpRequest], ParseAccounting]:
    """Small-input helper used by network-free tests."""

    requests: list[RawHttpRequest] = []
    accounting = parse_raw_http_stream(data, source_file=source_file, source_label=source_label, on_request=requests.append)
    return requests, accounting


def _file_facts(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    high_bit_bytes = 0
    nul_bytes = 0
    crlf = 0
    lf = 0
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    utf8_valid = True
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            high_bit_bytes += sum(value >= 128 for value in chunk)
            nul_bytes += chunk.count(b"\0")
            crlf += chunk.count(b"\r\n")
            lf += chunk.count(b"\n")
            if utf8_valid:
                try:
                    decoder.decode(chunk, final=False)
                except UnicodeDecodeError:
                    utf8_valid = False
    if utf8_valid:
        try:
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            utf8_valid = False
    stat = path.stat()
    return {
        "byte_size": stat.st_size,
        "sha256": digest.hexdigest(),
        "retrieved_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "encoding": {
            "utf8_valid": utf8_valid,
            "high_bit_byte_count": high_bit_bytes,
            "literal_nul_byte_count": nul_bytes,
            "crlf_line_ending_count": crlf,
            "lf_only_line_ending_count": lf - crlf,
            "display_decoding_policy": "raw bytes canonical; presentation decoding deferred until source-byte review",
        },
    }


def _header_present(request: RawHttpRequest, name: bytes) -> bool:
    return any(header.name.lower() == name for header in request.headers)


def scan_source_file(path: Path, *, source_label: str) -> dict[str, Any]:
    """Return aggregate parser diagnostics without retaining corpus request text."""

    facts = _file_facts(path)
    methods: Counter[str] = Counter()
    headers: Counter[str] = Counter()
    content_length: Counter[str] = Counter()
    request_hashes: set[str] = set()
    request_hash_sequence: list[str] = []
    has_body = 0
    parse_errors: list[dict[str, Any]] = []
    accounting: ParseAccounting | None = None

    def observe(request: RawHttpRequest) -> None:
        nonlocal has_body
        methods[request.method] += 1
        request_hashes.add(request.raw_request_sha256)
        request_hash_sequence.append(request.raw_request_sha256)
        if request.body_bytes:
            has_body += 1
        for key, header in (("cookie", b"cookie"), ("authorization", b"authorization"), ("user_agent", b"user-agent"), ("referer", b"referer"), ("content_type", b"content-type")):
            if _header_present(request, header):
                headers[key] += 1
        content_length["present" if _header_present(request, b"content-length") else "missing"] += 1

    with path.open("rb") as handle:
        if facts["byte_size"] == 0:
            parse_errors.append({"error_type": "empty_source_file", "byte_offset": 0, "request_index_candidate": 1, "context_sha256": hashlib.sha256(b"").hexdigest()})
            accounting = ParseAccounting(0, 0, 0, 0, 0)
        else:
            with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
                try:
                    accounting = parse_raw_http_stream(data, source_file=path.name, source_label=source_label, on_request=observe)
                except RawHttpParseError as error:
                    parse_errors.append({"error_type": error.error_type, "byte_offset": error.offset, "request_index_candidate": error.request_index, "context_sha256": error.context_sha256})
                    accounting = ParseAccounting(len(data), 0, 0, len(data), 0)

    assert accounting is not None
    parsed = accounting.parsed_requests
    return {
        **facts,
        "parsed_requests": parsed,
        "unique_raw_request_sha256": len(request_hashes),
        "duplicate_raw_requests": parsed - len(request_hashes),
        "request_hashes": request_hash_sequence,
        "parse_errors": parse_errors,
        "parse_error_count": len(parse_errors),
        "byte_consumption": {
            "request_bytes": accounting.request_bytes,
            "recognized_separator_bytes": accounting.separator_bytes,
            "unaccounted_bytes": accounting.unaccounted_bytes,
            "complete": accounting.unaccounted_bytes == 0 and not parse_errors,
        },
        "methods": {"GET": methods["GET"], "POST": methods["POST"], "other": sum(count for method, count in methods.items() if method not in {"GET", "POST"}), "all": dict(sorted(methods.items()))},
        "body": {"with_body": has_body, "without_body": parsed - has_body},
        "content_length": {"present": content_length["present"], "missing": content_length["missing"], "duplicate": 0, "invalid": 0, "negative": 0, "truncated": 0},
        "headers": {"with_cookie": headers["cookie"], "with_authorization": headers["authorization"], "with_user_agent": headers["user_agent"], "with_referer": headers["referer"], "with_content_type": headers["content_type"]},
    }


def _safe_file_facts(path: Path, *, source_label: str) -> dict[str, Any]:
    if not path.is_file():
        return {"source_label": source_label, "missing": True}
    return scan_source_file(path, source_label=source_label)


def _load_receipts(cache_dir: Path) -> dict[str, dict[str, Mapping[str, Any]]]:
    receipt_path = cache_dir / "acquisition_receipts.json"
    if not receipt_path.is_file():
        return {}
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    mirrors = value.get("mirrors") if isinstance(value, Mapping) else None
    if not isinstance(mirrors, Mapping):
        return {}
    result: dict[str, dict[str, Mapping[str, Any]]] = {}
    for mirror, entries in mirrors.items():
        if not isinstance(mirror, str) or not isinstance(entries, list):
            continue
        result[mirror] = {str(item.get("filename")): item for item in entries if isinstance(item, Mapping) and isinstance(item.get("filename"), str)}
    return result


def build_inventory(cache_dir: Path) -> dict[str, Any]:
    primary_root = cache_dir / "primary"
    comparison_root = cache_dir / "comparison_sunbeam"
    files: list[dict[str, Any]] = []
    all_hashes: dict[str, set[str]] = defaultdict(set)
    all_labels: dict[str, set[str]] = defaultdict(set)
    total_bytes = total_requests = total_unique_within_files = total_duplicates = total_errors = 0
    all_complete = True
    receipts = _load_receipts(cache_dir)

    for spec in FILE_SPECS:
        filename = str(spec["filename"])
        label = str(spec["source_label"])
        primary = _safe_file_facts(primary_root / filename, source_label=label)
        comparison = _safe_file_facts(comparison_root / filename, source_label=label)
        primary_receipt = receipts.get("primary", {}).get(filename, {})
        comparison_receipt = receipts.get("comparison_sunbeam", {}).get(filename, {})
        if primary_receipt:
            primary["http_status"] = primary_receipt.get("http_status")
        if comparison_receipt:
            comparison["http_status"] = comparison_receipt.get("http_status")
        match = not primary.get("missing") and not comparison.get("missing") and primary["sha256"] == comparison["sha256"]
        primary_hashes = primary.pop("request_hashes", [])
        comparison.pop("request_hashes", None)
        for request_hash in primary_hashes:
            all_hashes[request_hash].add(filename)
            all_labels[request_hash].add(label)
        if primary.get("missing"):
            all_complete = False
        else:
            total_bytes += int(primary["byte_size"])
            total_requests += int(primary["parsed_requests"])
            total_unique_within_files += int(primary["unique_raw_request_sha256"])
            total_duplicates += int(primary["duplicate_raw_requests"])
            total_errors += int(primary["parse_error_count"])
            all_complete = all_complete and bool(primary["byte_consumption"]["complete"])
        all_complete = all_complete and match
        files.append({
            "filename": filename,
            "source_label": label,
            "role": spec["role"],
            "documented_request_count": DOCUMENTED_COUNTS[filename],
            "primary": {"mirror": "msudol/Web-Application-Attack-Datasets", "source_url": spec["primary_url"], **primary},
            "comparison": {"mirror": "sunbeamdotpt/csic-dataset", "source_url": spec["comparison_url"], **comparison},
            "whole_file_matches_comparison": match,
        })

    cross_file = sum(len(names) > 1 for names in all_hashes.values())
    cross_label = sum(len(labels) > 1 for labels in all_labels.values())
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "complete": all_complete and total_errors == 0,
        "dataset": DATASET_NAME,
        "redistribution_status": "unclear",
        "raw_files_tracked": False,
        "mirror_consistency": "verified" if all_complete and total_errors == 0 else "unverified",
        "files": files,
        "totals": {
            "source_files": len(files),
            "total_bytes": total_bytes,
            "total_requests": total_requests,
            "source_normal_requests": sum(int(item["primary"].get("parsed_requests", 0)) for item in files if item["source_label"] == "source_normal"),
            "source_anomalous_requests": sum(int(item["primary"].get("parsed_requests", 0)) for item in files if item["source_label"] == "source_anomalous"),
            "total_unique_within_file_sum": total_unique_within_files,
            "total_duplicate_within_file_sum": total_duplicates,
            "cross_file_duplicate_raw_requests": cross_file,
            "cross_label_identical_requests": cross_label,
            "total_parse_errors": total_errors,
        },
        "acquisition_notes": [
            "Primary and comparison byte hashes are mirror-consistency evidence, not a CSIC-issued checksum.",
            "The initially reviewed Monkey-D-Groot mirror lacked normalTrafficTest.txt; it is not the complete comparison acquisition.",
            "The GSI GitLab comparison endpoint was unreachable during this acquisition and is not used for canonical local selection.",
        ],
    }


def source_manifest(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Transform local inventory into tracked metadata without raw request text."""

    files: list[dict[str, Any]] = []
    for item in inventory["files"]:
        primary = item["primary"]
        comparison = item["comparison"]
        files.append({
            "filename": item["filename"],
            "source_label": item["source_label"],
            "role": item["role"],
            "source_url": primary["source_url"],
            "comparison_source_url": comparison["source_url"],
            "retrieved_at": primary.get("retrieved_at"),
            "comparison_retrieved_at": comparison.get("retrieved_at"),
            "http_status": primary.get("http_status"),
            "comparison_http_status": comparison.get("http_status"),
            "byte_size": primary.get("byte_size"),
            "sha256": primary.get("sha256"),
            "comparison_byte_size": comparison.get("byte_size"),
            "comparison_sha256": comparison.get("sha256"),
            "documented_request_count": item["documented_request_count"],
            "parsed_request_count": primary.get("parsed_requests"),
            "whole_file_matches_comparison": item["whole_file_matches_comparison"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_NAME,
        "redistribution_status": "unclear",
        "raw_files_tracked": False,
        "original_description_url": "https://petescully.co.uk/wp-content/uploads/2018/04/http_dataset_csic_2010.pdf",
        "impact_doi": "10.23721/100/1478804",
        "source_status": "original_host_unavailable_at_review; acquired_from_public_mirrors",
        "canonical_acquisition": {"mirror": "msudol/Web-Application-Attack-Datasets", "files": files},
        "comparison_acquisition": {"mirror": "sunbeamdotpt/csic-dataset", "mirror_consistency": inventory["mirror_consistency"]},
        "parser_inventory": {
            "complete": inventory["complete"],
            "total_requests": inventory["totals"]["total_requests"],
            "total_parse_errors": inventory["totals"]["total_parse_errors"],
            "cross_file_duplicate_raw_requests": inventory["totals"]["cross_file_duplicate_raw_requests"],
            "cross_label_identical_requests": inventory["totals"]["cross_label_identical_requests"],
        },
    }


def validate_source_manifest_contract(manifest: Mapping[str, Any]) -> list[str]:
    """Network-free validator for the tracked schema contract.

    The project does not currently ship a JSON Schema runtime dependency, so
    this validates the same required provenance fields in tests and CLI output.
    """

    errors: list[str] = []
    required = {"schema_version", "dataset", "redistribution_status", "raw_files_tracked", "original_description_url", "impact_doi", "source_status", "canonical_acquisition", "comparison_acquisition", "parser_inventory"}
    if set(manifest) != required:
        errors.append("root keys differ from csic2010_source_manifest.v1")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if manifest.get("dataset") != DATASET_NAME:
        errors.append("invalid dataset")
    if manifest.get("redistribution_status") != "unclear" or manifest.get("raw_files_tracked") is not False:
        errors.append("invalid redistribution/raw tracking policy")
    acquisition = manifest.get("canonical_acquisition")
    if not isinstance(acquisition, Mapping) or acquisition.get("mirror") != "msudol/Web-Application-Attack-Datasets" or not isinstance(acquisition.get("files"), list):
        errors.append("invalid canonical acquisition")
        return errors
    expected_names = [str(spec["filename"]) for spec in FILE_SPECS]
    if [item.get("filename") for item in acquisition["files"] if isinstance(item, Mapping)] != expected_names:
        errors.append("canonical acquisition filenames/order differ")
    file_keys = {"filename", "source_label", "role", "source_url", "comparison_source_url", "retrieved_at", "comparison_retrieved_at", "http_status", "comparison_http_status", "byte_size", "sha256", "comparison_byte_size", "comparison_sha256", "documented_request_count", "parsed_request_count", "whole_file_matches_comparison"}
    for item in acquisition["files"]:
        if not isinstance(item, Mapping) or set(item) != file_keys:
            errors.append("invalid canonical acquisition file keys")
            continue
        if not SHA256_RE.fullmatch(str(item.get("sha256", ""))) or not SHA256_RE.fullmatch(str(item.get("comparison_sha256", ""))):
            errors.append(f"invalid SHA-256 for {item.get('filename')}")
        if item.get("http_status") != 200 or item.get("comparison_http_status") != 200:
            errors.append(f"missing successful retrieval status for {item.get('filename')}")
        if not isinstance(item.get("byte_size"), int) or not isinstance(item.get("parsed_request_count"), int):
            errors.append(f"invalid numeric accounting for {item.get('filename')}")
    comparison = manifest.get("comparison_acquisition")
    if not isinstance(comparison, Mapping) or comparison.get("mirror") != "sunbeamdotpt/csic-dataset" or comparison.get("mirror_consistency") not in {"verified", "unverified"}:
        errors.append("invalid comparison acquisition")
    parser = manifest.get("parser_inventory")
    if not isinstance(parser, Mapping) or not isinstance(parser.get("complete"), bool) or not all(isinstance(parser.get(key), int) for key in ("total_requests", "total_parse_errors", "cross_file_duplicate_raw_requests", "cross_label_identical_requests")):
        errors.append("invalid parser inventory")
    return errors


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _download(url: str, destination: Path, *, force: bool) -> dict[str, Any]:
    if destination.exists() and not force:
        raise ValueError(f"refusing to overwrite {destination}; use --force")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(url, headers={"User-Agent": "web-log-analysis-csic2010-acquirer/1"}), timeout=60) as response:
        status = int(getattr(response, "status", response.getcode()))
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            shutil.copyfileobj(response, handle)
    temporary.replace(destination)
    return {"source_url": url, "http_status": status, "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "byte_size": destination.stat().st_size, "sha256": _file_facts(destination)["sha256"]}


def acquire(cache_dir: Path, *, force: bool) -> list[dict[str, Any]]:
    """Download only when the caller selected the explicit acquire --download path."""

    results: list[dict[str, Any]] = []
    for spec in FILE_SPECS:
        filename = str(spec["filename"])
        results.append({"mirror": "msudol/Web-Application-Attack-Datasets", "filename": filename, **_download(str(spec["primary_url"]), cache_dir / "primary" / filename, force=force)})
        results.append({"mirror": "sunbeamdotpt/csic-dataset", "filename": filename, **_download(str(spec["comparison_url"]), cache_dir / "comparison_sunbeam" / filename, force=force)})
    mirrors: dict[str, list[dict[str, Any]]] = {"primary": [], "comparison_sunbeam": []}
    for result in results:
        destination = "primary" if result["mirror"] == "msudol/Web-Application-Attack-Datasets" else "comparison_sunbeam"
        mirrors[destination].append({key: result[key] for key in ("filename", "source_url", "http_status", "retrieved_at", "byte_size", "sha256")})
    _write_json(cache_dir / "acquisition_receipts.json", {"schema_version": "csic2010_acquisition_receipts.v1", "mirrors": mirrors})
    return results


def _summary(inventory: Mapping[str, Any]) -> Iterable[str]:
    for item in inventory["files"]:
        primary = item["primary"]
        yield " ".join((
            f"file={item['filename']}",
            f"bytes={primary.get('byte_size')}",
            f"sha256={primary.get('sha256')}",
            f"parsed_requests={primary.get('parsed_requests')}",
            f"mirror_match={str(item['whole_file_matches_comparison']).lower()}",
        ))
    totals = inventory["totals"]
    yield f"complete={str(inventory['complete']).lower()} total_requests={totals['total_requests']} parse_errors={totals['total_parse_errors']}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSIC 2010 local acquisition, integrity verification, and raw HTTP accounting")
    parser.add_argument("command", choices=("acquire", "verify", "inventory"))
    parser.add_argument("--cache-dir", type=Path, default=Path("benchmarks/cache/csic2010"))
    parser.add_argument("--download", action="store_true", help="Required explicit opt-in for acquire network traffic")
    parser.add_argument("--force", action="store_true", help="Allow acquire to replace an existing local cache file")
    parser.add_argument("--output", type=Path, default=Path("/tmp/csic2010_source_inventory.json"))
    parser.add_argument("--manifest", type=Path, help="Optional tracked provenance manifest destination")
    args = parser.parse_args(argv)
    try:
        if args.command == "acquire":
            if not args.download:
                raise ValueError("acquire requires explicit --download")
            for result in acquire(args.cache_dir, force=args.force):
                print(" ".join(f"{key}={value}" for key, value in result.items()))
            return 0
        inventory = build_inventory(args.cache_dir)
        _write_json(args.output, inventory)
        if args.manifest:
            manifest = source_manifest(inventory)
            contract_errors = validate_source_manifest_contract(manifest)
            if contract_errors:
                raise ValueError("invalid source manifest: " + "; ".join(contract_errors))
            _write_json(args.manifest, manifest)
        for line in _summary(inventory):
            print(line)
        return 0 if inventory["complete"] else 1
    except (OSError, ValueError, RawHttpParseError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
