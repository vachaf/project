# Phase 6C-1 — CSIC 2010 Local Acquisition, Integrity & Raw HTTP Parser Review

## 1. Decision and scope

- Review date: 2026-09-05 (Asia/Seoul)
- Repository HEAD at start: `56d1561 docs: design CSIC 2010 benchmark boundaries`
- Scope: ignored local acquisition, two-mirror byte comparison, provenance lock, raw HTTP framing/parser, and source accounting
- Excluded: Apache projection, Prepare, Stage1, LLM/API calls, family annotation, project attack-positive labels, production detector changes, raw-data vendoring, and commit

**6C-2 decision: GO.**  The selected primary and complete comparison mirrors returned byte-identical copies of all three expected files.  The streaming/mmap parser accounted for every primary byte, produced the documented request counts, and reported no malformed framing or content-length error.

This is source and parser integrity only.  It does **not** claim that `source_anomalous` means attack-positive, that `source_normal` is proven benign, or that any request has a four-family attack label.

## 2. Local-only acquisition and tracking safety

Raw data is held only in the ignored local cache:

```text
benchmarks/cache/csic2010/
  primary/
  comparison_sunbeam/
  acquisition_receipts.json
```

The tracked `.gitignore` rule is `/benchmarks/cache/csic2010/`.  `git check-ignore` confirms the raw files are ignored, `git ls-files benchmarks/cache` is empty, and no raw corpus appears in the repository index.  The tracked source provenance is metadata only:

- `benchmarks/manifests/csic2010_source.v1.json`
- `benchmarks/schemas/csic2010_source_manifest.v1.schema.json`
- local-only `/tmp/csic2010_source_inventory.json`

The original CSIC host remains unavailable as documented in [108_external_benchmark_csic2010_source_observability_design.md](./108_external_benchmark_csic2010_source_observability_design.md).  Acquisition therefore uses a selected local source mirror, not language implying that a mirror is the original canonical source.

## 3. Acquisition and mirror integrity

Primary acquisition: `msudol/Web-Application-Attack-Datasets`, `OriginalDataSets/csic_2010/`.

Complete comparison acquisition: `sunbeamdotpt/csic-dataset`, branch `mainline`.

All six explicit binary downloads returned HTTP 200 on 2026-09-05.  SHA-256 is calculated over downloaded bytes; no decoding, newline conversion, or text-mode write occurred.

| File | Primary bytes / SHA-256 | Comparison bytes / SHA-256 | Whole-file match |
| --- | --- | --- | --- |
| `normalTrafficTraining.txt` | 20,148,988 / `d51de812d9201ef2b173b6ae3e3e740c309047ac85545c06c51d6fb1ddbc1e63` | 20,148,988 / same | yes |
| `normalTrafficTest.txt` | 20,151,204 / `f05dfc312d5d14fd1ed8371de27a9e4deab3dc09265f5d7f9df2643df8385089` | 20,151,204 / same | yes |
| `anomalousTrafficTest.txt` | 15,734,523 / `12fa4f0d496ceb859bb2652abf7f0f0ed8c59e1d9ce501b8a9a0ef38a625c046` | 15,734,523 / same | yes |

```text
mirror_consistency=verified
whole-file comparison=3/3 identical
```

The originally proposed `Monkey-D-Groot/Machine-Learning-on-CSIC-2010` comparison mirror supplied training and anomalous files but returned 404 for `normalTrafficTest.txt`; its two available files also had different byte sizes/SHA due to their CRLF variant.  It is retained only as an ignored local observation, not as the complete comparison acquisition.  The GSI GitLab mirror could not establish HTTPS connectivity during this run.  These failures are recorded as availability/layout facts; no mismatch was normalized with `dos2unix` or equivalent.

The matching SHA values are **mirror-consistency evidence, not CSIC-issued checksums**.  Original data redistribution status remains `unclear`; raw files remain untracked.

## 4. Parser contract

`src/external_benchmark_csic2010.py` provides explicit commands:

```text
acquire --download  # network opt-in; binary-safe writes and receipts
verify              # SHA comparison + parser inventory
inventory           # local accounting only
```

`acquire` refuses to use the network without `--download`.  Tests do not invoke it.

The parser's source of truth is `bytes`, and file scanning uses `mmap` plus callback-based accounting so the full corpus is not retained as parsed request objects.  It uses a stateful sequence equivalent to:

```text
SEEK_REQUEST_LINE -> READ_HEADERS -> READ_BODY -> SEEK_NEXT_REQUEST
```

Key invariants:

- request lines accept generic HTTP token methods; the actual anomaly file contains PUT in addition to GET/POST;
- raw target, percent encoding, header order/case, duplicate headers, body bytes, raw request bytes, offsets, and request SHA-256 are retained in the in-memory request object;
- header storage is ordered `Header` entries, not a lossy dictionary;
- `Content-Length` is parsed as a non-negative byte count; duplicate, invalid, negative, and truncated values raise explicit parse errors;
- body bytes are consumed before blank lines can be interpreted as inter-request separators;
- CRLF and LF framing are supported; acquired primary bytes are LF-only;
- raw bytes remain canonical.  Display decoding is deferred instead of assuming UTF-8; and
- parser code creates only `source_normal` / `source_anomalous` file labels.  It never generates security-family, attack, benign, or malicious labels.

The checked synthetic fixtures cover consecutive GET, CRLF/LF, POST body framing, body-internal blank lines, duplicate headers/query parameters, absolute-form targets, encoded/non-ASCII bytes, Content-Length failures, offsets, deterministic hashes, and no-network acquire refusal.  They contain no CSIC raw payload.

## 5. Actual source accounting

| File | Documented | Parsed | Difference | GET | POST | Other | With body | Parse errors | Unaccounted bytes |
| --- | ---: | ---:| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `normalTrafficTraining.txt` | 36,000 | 36,000 | 0 | 28,000 | 8,000 | 0 | 8,000 | 0 | 0 |
| `normalTrafficTest.txt` | 36,000 | 36,000 | 0 | 28,000 | 8,000 | 0 | 8,000 | 0 | 0 |
| `anomalousTrafficTest.txt` | 25,065 | 25,065 | 0 | 15,088 | 9,580 | 397 PUT | 9,977 | 0 | 0 |

```text
actual total:              97,065
source_normal total:       72,000
source_anomalous total:    25,065
total source bytes:        56,034,715
total parse errors:        0
```

Byte-consumption invariants hold for every file:

```text
request bytes + recognized separator bytes + unaccounted bytes = source file bytes
unaccounted bytes = 0
```

`Content-Length` is present for every body-bearing request and absent for all bodyless requests in these acquired bytes.  There were no observed duplicate, invalid, negative, or truncated content lengths.

## 6. Encoding, header, and duplicate diagnostics

All selected primary files are UTF-8-valid at byte level, have zero literal NUL bytes, zero high-bit bytes, and LF-only line endings.  This does not authorize text normalization: source hash and parser framing continue to operate on raw bytes, while human display decoding remains a separate future decision.

Across the three files, all requests have Cookie and User-Agent headers; no request has an Authorization or Referer header in the current accounting.  The parser records only aggregate header-presence counts in the inventory; it does not emit Cookie, Authorization, body, or raw request text in result artifacts.

Duplicate analysis:

```text
within-file duplicate raw requests: 0
cross-file duplicate raw requests:  0
cross-label identical requests:     0
```

Requests are never deduplicated.  Identity remains `(source_file, request_index, raw_request_sha256)`, with a human-readable form such as `csic2010:normalTrafficTraining.txt:000001`.

## 7. Provenance manifest and validation

`csic2010_source.v1.json` records source label, role, primary/comparison URLs, receipt timestamps, HTTP 200 status, size, primary/comparison SHA-256, documented count, parsed count, and whole-file comparison result for each file.  It also fixes:

```text
redistribution_status: unclear
raw_files_tracked: false
```

The repository currently has no JSON Schema runtime dependency.  Instead, the CLI and focused tests run a network-free manifest-contract validator that checks the same required schema fields, filename order, SHA format, HTTP status, acquisition policy, and inventory numeric fields; raw JSON parsing also passed.  The JSON Schema remains tracked for external validator use.

## 8. 6C-2 gate and production impact

6C-2 is authorized to implement only the next separation layer:

```text
parsed CSIC raw request -> Apache-observable neutral synthetic row -> isolated Prepare corpus baseline
```

It must continue to discard body/Cookie-value/arbitrary-header evidence only during projection, not during raw parsing; must not run Stage1 over the corpus; and must report only `source_normal`/`source_anomalous` selection terminology until a reviewed semantic subset exists.

Production impact is **none**.  No Prepare, Apache projection, detector, mapper, prompt, Stage1, suite, or family annotation changed in 6C-1.  LLM/API calls: **0**.
