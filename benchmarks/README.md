# External security benchmarks

This directory contains deterministic, repository-local benchmark inputs. It is
separate from production Prepare, Stage1, standards mapping, and viewer code.
An upstream OWASP CRS `expect_ids` or `no_expect_ids` value is provenance for a
CRS regression test; it is never converted automatically into a project Stage1
verdict.

## OWASP CRS path/file-access snapshot

The first source is pinned to OWASP CRS revision
`96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`. The unmodified `930100.yaml`,
`930110.yaml`, and `930120.yaml` files, upstream Apache-2.0 `LICENSE`, retrieval
date, original paths, and raw-byte SHA-256 checksums are stored under
`sources/owasp_crs/<revision>/`. That upstream revision has no root `NOTICE`,
`NOTICE.txt`, or `NOTICE.md` file.

The source adapter inventories all 36 upstream tests without URL decoding,
canonicalization, NUL removal, slash normalization, header filtering, or body
loss. The reviewed manifest separately owns logs-only observability and project
taxonomy expectations. Its status groups are:

- `direct`: the signal is in the canonical raw request target/query and is
  eligible for the future main lane.
- `partial`: a capability such as arbitrary request-header logging is missing;
  the case is retained but not scored.
- `out_of_scope`: the decisive signal is in a request body or multipart filename
  unavailable to the canonical Apache logs-only input.

CRS observes HTTP surfaces that the project does not log. None of these cases
establish file-read, command-execution, vulnerability, or exploit success. The
synthetic replay/live distinction and execution artifacts belong to later
phases; Phase 5B-1 only freezes source, annotation, schema, and join contracts.

Install the adapter's isolated parser dependency with:

```bash
.venv/bin/pip install -r benchmarks/requirements.txt
```

## Updating the source

Source updates are manual and review-gated:

1. Create a new directory named for the exact upstream revision.
2. Download raw source files and preserve the upstream license/provenance.
3. Record and independently verify SHA-256 checksums over raw bytes.
4. Run the source adapter inventory tests and review test IDs/source diffs.
5. Re-review every project annotation; never infer it from CRS rule IDs.
6. Update the manifest version or pinned revision as appropriate.
7. Do not automatically mix results from different source revisions into one
   benchmark series.

No benchmark runtime or test fetches data from the network.

## OWASP CRS multi-family source bundle and suite

Phase 6B-1 adds a separate, pinned multi-family bundle below the frozen 930
source root:

```text
sources/owasp_crs/<revision>/multi_family/
  SOURCE.json  LICENSE  932/*.yaml  941/*.yaml  942/*.yaml
```

The legacy `SOURCE.json`, three root 930 YAML files, and
`src/external_benchmark_crs.py` remain a frozen full-inventory contract.  The
multi-family bundle is a raw upstream-source **superset**: its YAML files are
unmodified and include every test in each reviewed upstream rule file.  Its
own `SOURCE.json` carries provenance, counts, and SHA-256 values, while the
separate Python lock in `src/external_benchmark_crs_multifamily.py` prevents a
YAML and metadata edit from silently changing the pinned source.

The three reviewed family-manifest subsets are:

```text
manifests/owasp_crs_cmdi.v1.json
manifests/owasp_crs_xss.v1.json
manifests/owasp_crs_sqli.v1.json
```

They contain project observability/taxonomy annotations only for selected
cases.  Unlike the legacy 930 manifest, they are intentionally not required to
cover every raw source test.  The suite at
`suites/owasp_crs_multi_family.v1.json` composes references to those manifests
and the frozen 930 manifest without copying annotations.  Its exact core is
36 cases: nine each traversal, command injection, XSS, and SQLi.  File
disclosure remains a separate path/file boundary addendum because the frozen
930 source has only one clean exact file-disclosure case; it is not included in
the four-class macro core.  913 scanner and 933 PHP are deliberately deferred.

Source facts, project annotations, and suite composition remain separate.
Neither source family/rule nor expected project verdict is a Stage1 candidate
field.  This phase contains no Prepare/Stage1 runner or network behavior.

For a future CRS revision, create a new revision directory or bundle; retrieve
raw YAML bytes; calculate and review SHA-256/count/provenance; review source
inventory; review family annotations; review deterministic suite selection;
then add regression coverage.  Never overwrite an existing revision's source
metadata or silently accept an unregistered YAML file.  The pinned revision
used here has no root `NOTICE`, `NOTICE.txt`, or `NOTICE.md`; the multi-family
`SOURCE.json` records this as an empty `notice_files` list.
