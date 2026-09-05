# Phase 6C-R — CSIC 2010 Source, Licensing, Observability & Taxonomy Review

## 1. Executive decision

- Review date: 2026-09-05 (Asia/Seoul)
- Scope: CSIC 2010 source/provenance, data-use constraints, raw-request observability, and a future benchmark contract
- Work performed: documentation/research and read-only inspection of the current Apache export/Prepare/Stage1 contracts
- Not performed: full dataset download/import, raw-data vendoring, parser implementation, benchmark execution, production changes, LLM/API calls, or commit

**Decision: CONDITIONAL GO.**  CSIC 2010 is useful as a large-corpus, Apache-observable Prepare selectivity/enrichment benchmark, complementary to CRS's reviewed exact-family benchmark.  It is not yet eligible for tracked raw vendoring or corpus-wide Stage1 scoring:

1. the original host is currently unavailable from this review environment;
2. public raw mirrors exist, but the original dataset's explicit redistribution license was not found;
3. the source label is normal/anomalous, not a per-request four-family attack label; and
4. raw HTTP contains POST bodies, Cookie values, and arbitrary headers that the current Apache logs-only contract does not fully expose.

Use local-only acquisition with exact-byte locks before implementation.  Retain **`source_normal`** and **`source_anomalous`** as source terms.  In particular:

```text
CSIC anomalous label is not automatically an attack-positive label.
CSIC source labels must not be used as four-family Stage1 ground truth.
```

## 2. Dataset identity and original provenance

The original identity is **HTTP DATASET CSIC 2010**, developed at the Information Security Institute of the Spanish National Research Council (CSIC).  The original description identifies Carmen Torrano Giménez, Alejandro Pérez Villegas, and Gonzalo Álvarez Marañón as authors, describes automatically generated HTTP requests against a Spanish e-commerce application, and notes that the generated values can include Latin characters.  [Archived CSIC description PDF](https://petescully.co.uk/wp-content/uploads/2018/04/http_dataset_csic_2010.pdf)

The archived description defines three corpus files/subsets:

| File | Source label / role | Reported request count |
| --- | --- | ---: |
| `normalTrafficTraining.txt` | source-normal training | 36,000 |
| `normalTrafficTest.txt` | source-normal test | 36,000 |
| `anomalousTrafficTest.txt` | source-anomalous test | 25,065 |

The exact counts are independently reported by a raw-mirror README and research material, but this review did not download full source bytes or run a parser.  They are acquisition-time expectations, **not hard-coded implementation constants**.  Phase 6C-1 must count parsed request objects from acquired bytes and report any blank-line/parser variance.  [Raw-mirror inventory](https://github.com/msudol/Web-Application-Attack-Datasets/blob/master/OriginalDataSets/csic_2010/README.md)

### 2.1 Original-host availability

The historically cited source is `http://www.isi.csic.es/dataset/` (the archived description also names `iec.csic.es/dataset/`).  On 2026-09-05, bounded HTTP HEAD checks timed out for HTTP and failed to connect for HTTPS; browser retrieval of the `iec` URL also failed.  This is an availability observation, not proof that no archival access exists.

IMPACT's current record is useful provenance metadata, not a hosted canonical copy: it assigns DS-0940 / DOI `10.23721/100/1478804`, names the Information Security Institute as host, and explicitly calls it a **non-IMPACT record** whose access and legal terms are external to IMPACT.  Its restriction is shown as unrestricted, but commercial permission is `Unknown` and no data-use terms are supplied.  [IMPACT dataset record](https://impactcybertrust.org/dataset_view?idDataset=940)

## 3. Sources, mirrors, and licensing

### Table A — source comparison

| Source | Authority | Raw files available | Counts / raw fidelity evidence | Hash/provenance | License statement | Recommended use |
| --- | --- | --- | --- | --- | --- | --- |
| Original CSIC/ISI description (archived PDF) | primary descriptive material | download links historically listed; host currently unavailable | describes the three subsets, normal/anomalous labels, and corpus-level categories | original authors and institutional identity; no current raw-file hash | no explicit dataset redistribution license found | primary citation and semantic provenance |
| IMPACT DS-0940 | durable catalog metadata, not data host | no IMPACT-controlled file access | repeats identity, subsets, categories, and source description | DOI `10.23721/100/1478804`; external source record | data terms external; commercial status unknown | provenance/supporting catalog only |
| `msudol/Web-Application-Attack-Datasets` | public raw mirror | all three named `.txt` files | README calls them original-format data and reports 36,000/36,000/25,065; training file page reports 19.2 MB | no source-issued SHA-256 published | mirror README does not establish original-data license | preferred **candidate** acquisition mirror, contingent on local hash comparison |
| `Monkey-D-Groot/Machine-Learning-on-CSIC-2010` | independent public raw mirror | named raw corpus files | a range-limited first 4 KiB read of training data matched the first 4 KiB from the msudol mirror byte-for-byte | no full-file comparison or original hash performed | no original-data license established | independent raw-fidelity cross-check |
| Redata `WebRequests` | DOI-backed derivative archive | CSIC-named materials listed, but study states it retained only URIs for merged feature processing | derived/URI-oriented artifact, not full canonical HTTP input | DOI `10.60895/redata/RWUUSV` | archive metadata does not establish CSIC redistribution right | provenance/derivative comparison only; not canonical raw input |

The range reads above were intentionally capped at 4 KiB and were not stored.  They demonstrated that both public GitHub locations begin with the same raw HTTP sequence, including GET and POST requests, headers, Cookie values, and an `application/x-www-form-urlencoded` body.  They do **not** establish whole-file equality.  The Redata study itself says it retained only request URIs for its merged representation, which disqualifies it as canonical input for this Apache-observable benchmark.  [Redata metadata](https://redata.anii.org.uy/api/datasets/export?exporter=html&persistentId=doi:10.60895/redata/RWUUSV)

### 3.1 License and redistribution decision

**Decision: C — publicly accessible but redistribution terms unclear.**

- The original descriptive material describes a publicly available academic dataset but does not state an explicit dataset license or redistribution grant.
- IMPACT says its record is external and subject to external terms; it does not supply those terms or say commercial use is allowed.
- A mirror's repository license, or a mirror's self-described fair-use notice, does not grant rights to the underlying CSIC raw files.  For example, one mirror states that its Apache-2.0 license excludes dataset files and that original terms are unstated.  [Mirror licensing notice](https://github.com/sunbeamdotpt/csic-dataset)

Therefore:

```text
downloadable/public != redistributable
mirror repository license != underlying dataset license
```

Do **not** commit raw CSIC files under `benchmarks/sources/csic2010/` unless an explicit original permission is found and recorded.  This review creates no cache directory.  The future architecture is:

```text
tracked repository:
  source metadata, acquisition instructions, expected hashes,
  parser, manifest/schema, and tiny synthetic parser fixtures

local ignored cache:
  benchmarks/cache/csic2010/
    normalTrafficTraining.txt
    normalTrafficTest.txt
    anomalousTrafficTest.txt
```

Each local acquisition must lock filename, retrieval URL, retrieval date, byte size, SHA-256, and mirror identifier.  Acquire the same filename from two raw mirrors where possible, compute SHA-256 over original bytes, and investigate any mismatch as a newline conversion, normalization, or source variant before choosing a canonical local source.  Converted CSV, decoded feature vectors, URI-only, or packet-flattened forms are supporting artifacts only.

## 4. Labels and taxonomy boundary

### Table C — label semantics

| Source concept | Meaning | Can be used directly as project ground truth? |
| --- | --- | --- |
| `normal` | source-generated application-normal request | no; call it `source_normal`, not proven benign |
| `anomalous` | source anomaly-set membership | no; call it `source_anomalous`, not `project_attack_positive` |
| static attack | hidden/nonexistent resource, obsolete/config/default resources, URL-rewrite session IDs | corpus-level source description only; individual semantics need review |
| dynamic attack | modified valid arguments, including SQLi, CRLF, XSS, buffer overflow, etc. | corpus-level source description only; no source per-request family label |
| unintentional illegal request | non-malicious request not following normal application behavior (for example letters in a telephone field) | explicitly not malicious by source description; never auto-label attack-positive |

The original description says requests are labeled **normal or anomalous** and lists attack kinds at corpus level.  The raw request files are grouped by subset; they do not carry a per-request `SQLi`/`XSS`/`CMDi`/`Traversal` field.  Do not infer that a string match is an original source label.

The description uses both “anomalous” and, for its test split summary, “malicious” wording.  The explicit unintentional-illegal category resolves the benchmark contract: anomalous is the authoritative broad source grouping, not a universal malicious-intent claim.  This follows the source's anomaly-detection purpose, where behavior outside the normal application model is anomalous.  [Archived CSIC description](https://petescully.co.uk/wp-content/uploads/2018/04/http_dataset_csic_2010.pdf), [IMPACT description](https://impactcybertrust.org/dataset_view?idDataset=940)

Future reviewed taxonomy may use `sqli`, `xss`, `path_traversal`, `file_disclosure`, `command_injection`, `crlf_header_injection`, `parameter_tampering`, `information_gathering`, `other_anomalous`, `non_malicious_illegal`, `ambiguous`, and `body_only_not_scored`.  This is project review taxonomy, not retroactive source metadata.

CRLF/header injection has no current dedicated Stage1 verdict and must not be forced into XSS/CMDi/SQLi.  Parameter tampering must not be auto-mapped to auth abuse.  Information gathering/hidden-resource requests require a reviewed boundary among `suspicious_scan`, `suspicious_file_disclosure`, compatible handling, and exclusion.

## 5. Raw HTTP format and parser contract

Range-limited reads from two raw mirrors show HTTP/1.1 request lines, GET and POST, absolute-form targets, headers including `Host`, `User-Agent`, `Referer`-like fields where present, `Cookie`, `Content-Type`, and `Content-Length`, plus form POST bodies.  The source description also warns that Spanish/Latin characters occur.  No response status, response body, timing, or server error linkage is in this request corpus.

Phase 6C-1 must preserve raw bytes and implement a streaming state machine.  It must not use a universal `split("\\n\\n")` rule: a body may contain blank lines, line endings can be CRLF or LF, and `Content-Length` is byte—not Unicode-character—length.  The minimum parser requirements are:

1. retain source bytes and per-request byte boundaries;
2. parse request line and headers using HTTP line delimiters while retaining original raw bytes;
3. consume exactly `Content-Length` body bytes when it is present;
4. treat inter-request blank separators only after body consumption;
5. preserve duplicate headers and duplicate parameters; do not silently deduplicate requests;
6. record source-file, request index, and `raw_request_sha256`; and
7. report total requests, unique raw-request count, and duplicate count without deleting duplicates.

For presentation/feature extraction, do not blindly assume UTF-8.  Keep bytes canonical; record the validated display decoding strategy after inspecting acquired bytes (including any Latin-1/Windows-1252 versus UTF-8 question).  Percent encoding, NUL/invalid bytes, and raw request text must remain distinguishable from a decoded display form.

Corpus order is not evidence of real user timing or a reliable session sequence.  The primary scan is one-request isolated mode; it must not manufacture repeated-request, brute-force, or temporal semantics from file order.

## 6. Apache logs-only observability

Current project authority is the Apache security/export schema and Prepare input, not the CSIC request format.  The project retains request-line fields and selected security-log fields such as host, User-Agent, Referer, Origin, selected forwarding headers, request content type/length, and presence flags for Cookie/Authorization.  It does **not** preserve raw POST bodies, raw Cookie values, or arbitrary header values.  The Apache evidence boundary also prohibits using access-log response metadata as response-body evidence.  See [Apache logs-only evidence boundary](../00_apache_logs_only_evidence_boundary.md).

### Table B — observability

| HTTP field | Present in CSIC? | Logged by project? | Main benchmark status | Reason |
| --- | --- | --- | --- | --- |
| request line, method, HTTP version | yes | yes (`raw_request`, method/protocol) | directly observable | current input surface preserves the request line |
| target / URI / query | yes | yes (`raw_request_target`, URI, query string) | directly observable | primary request evidence surface |
| Host | yes | selected value | directly observable when present | current security schema has `req_host` |
| User-Agent | commonly present | selected value | partial/context only | Stage1 treats UA as trace aid, not attack proof |
| Referer / Origin / selected forwarding headers | may be present | selected values | partial/context only | schema-dependent and not sufficient attack evidence alone |
| `Content-Type` / `Content-Length` | POST samples show both | selected metadata | partial | describes body framing, not body contents |
| Cookie value | samples show `JSESSIONID` | presence flag only | out of scope for cookie-value semantics | current export intentionally avoids sensitive cookie value retention |
| Authorization value | may occur | presence flag only | out of scope for value semantics | value is not exported |
| arbitrary headers | yes | generally no | out of scope unless a specific logged field exists | do not copy them into query/UA fields |
| POST/multipart body | yes | no raw body | body-only decisive evidence is not scored | current logs-only contract forbids reconstruction |
| response status/body/bytes/content type/timing/error | no source truth | production may have fields, but CSIC does not | neutral synthetic metadata only | never invent source response evidence |

### 6.1 Body, header, and cookie policy

- A POST body must never be moved into query string or URI.
- A body-only decisive anomaly is `not_scored_observability` for the main logs-only semantic benchmark.
- A POST with independent decisive request-target/query evidence may be reviewed from that observable evidence alone; the body cannot support its expectation.
- Cookie-only decisive anomalies are not scored because only a presence flag is available.  Arbitrary-header-only anomalies are likewise out of scope unless a future production logging profile explicitly retains the exact relevant field.
- UA-only/header-only source anomalies may remain `source_anomalous` but require a reviewed policy outcome (`partial`, `not_scored`, or a narrow compatible context); they are not Stage1 attack evidence by default.

## 7. Neutral synthetic Apache projection

Phase 6C-2 should map one parsed raw request to one isolated neutral Apache security row, reusing the existing external-benchmark adapter conventions:

```text
preserve: request line, target, percent encoding, URI/query split,
          selected logged headers only
assign:   documentation-range source IP, neutral status_code=200,
          response_body_bytes=0, resp_content_type="",
          duration/TTFB neutral, no error linkage
exclude:  POST/multipart body, Cookie/Authorization values, arbitrary unlogged headers
```

The neutral `200` is an adapter placeholder, not a source response observation and never evidence of successful attack execution, file access, database modification, browser execution, or command execution.  All CSIC payload interpretations remain attempt/pattern-only.

## 8. Corpus role, metrics, and reviewed subset

CSIC's primary role is **large-corpus candidate selectivity and enrichment**, while CRS remains the reviewed exact-family/confusion benchmark.  Do not send the roughly 97k raw requests to Stage1.

### Table D — metric contract

| Metric | Numerator | Denominator | Interpretation | Forbidden interpretation |
| --- | --- | --- | --- | --- |
| source-normal candidate rate | selected `source_normal` | evaluated/observable `source_normal` | Prepare selection rate for source-generated normal traffic | model false-positive rate or proven-benign FPR |
| source-normal suppression rate | not selected `source_normal` | evaluated/observable `source_normal` | Prepare suppression behavior | specificity |
| source-anomalous candidate rate | selected `source_anomalous` | evaluated/observable `source_anomalous` | Prepare selection rate for the source anomaly set | attack recall/TPR |
| candidate anomaly proportion | selected `source_anomalous` | all selected source-normal + source-anomalous | composition of selected candidates | precision |
| selection-rate ratio | `P(selected | source_anomalous)` | `P(selected | source_normal)` | anomaly-set enrichment relative to source-normal selection | likelihood of maliciousness |

Report direct-observability eligibility counts separately from source-file totals.  Never call these corpus metrics attack recall, false-positive rate, true-positive rate, or specificity without reviewed project-semantic annotations.

The future evaluation layers are:

- **Layer A — corpus Prepare scan:** all directly projectable source-normal/source-anomalous requests; no LLM; isolated request mode; selection, suppression, and hint distributions only.
- **Layer B — reviewed semantic subset:** manually/source-backed stratified sample across GET/POST, target/query/body/header/cookie location, selected/missed status, hint family, URI/resource pattern, encoding complexity, and request length.  This is the only layer that may assign `project_attack_positive`, `project_negative`, `not_scored`, family expectation, or compatible policy.
- **Layer C — Stage1 subset:** reviewed, project-attack-positive, Prepare-selected cases only.  Use strict four-family matrices only for reviewed traversal/CMDi/XSS/SQLi cases; file disclosure is an addendum and other categories require a separate compatibility/exclusion policy.

Pattern-assisted review is permitted, but `contains UNION -> source SQLi label` and similar automatic source-ground-truth assignments are prohibited.

## 9. Source acquisition architecture and risks

If later approved, commit metadata—not raw data—such as:

```text
benchmarks/manifests/csic2010_source.v1.json
benchmarks/schemas/csic2010_source_manifest.v1.schema.json
```

The manifest should contain expected filenames, retrieval references, hashes captured at acquisition, citation, `redistribution_status: unclear`, and parser compatibility metadata.  Test fixtures must be tiny synthetic raw HTTP samples, not extracted corpus material.  Large result artifacts should avoid copying raw request bodies repeatedly; use source-file/index/hash plus the minimum reviewed evidence necessary for audit.  Treat user-like names, emails, addresses, and cookies conservatively even though the dataset was generated.

Risks requiring explicit 6C-1 gates:

1. source mirror changes or full-byte mismatch;
2. absent original redistribution permission;
3. CRLF/LF/body-boundary parser defects;
4. character decoding that changes source bytes or percent encodings;
5. overclaiming source-anomalous as malicious/project attack-positive; and
6. accidental body/header leakage into a logs-only projection.

## 10. Recommended phases

### Table E — future phases

| Phase | Scope | LLM? | Production changes? | Output |
| --- | --- | --- | --- | --- |
| 6C-1 | local source acquisition, two-mirror hash comparison, streaming parser, source accounting | no | no | ignored local cache, integrity report, parser tests with synthetic fixtures |
| 6C-2 | Apache-observable neutral projection and isolated Prepare corpus baseline | no | no | source-normal/source-anomalous selection metrics and hint distributions |
| 6C-3 | stratified, source-backed semantic review | no | no | reviewed manifest/subset policy: attack-positive, negative, compatible, not-scored |
| 6C-4 | controlled/replay Stage1 on reviewed selected subset | only controlled fixture if applicable | no | reviewed subset matrices and mapping policy evidence |
| 6C-5 | optional single live Stage1 | reviewed selected subset only | no | one separately identified live diagnostic/baseline |

No repeated live corpus run is implied.  Move to 6C-1 only after accepting the local-only acquisition and license posture; do not vendor raw files as a convenience.

## 11. Final go/no-go statement

**CONDITIONAL GO:** CSIC 2010 can become a reproducible local, non-vendored external corpus benchmark if 6C-1 verifies exact raw bytes, parser accounting, and the local data-use posture.  It is a strong candidate for corpus-scale Prepare behavior, but it is not an automatically labeled four-family Stage1 benchmark.  The source/license ambiguity is handled by local ignored acquisition and tracked provenance metadata rather than repository redistribution.
