# CSIC 2010 semantic validation review (6C-3C)

Date: 2026-09-05

## Scope and review provenance

This document records the validation and canonicalization of the frozen 222-case
CSIC review sample.  It does not call the resulting decisions independent model
ground truth.  The first pass was `llm_assisted_explicit_case_review`; the
second pass was recorded as `independent_blind_case_review`, with provenance
`blind second-pass validation; not independent model ground truth`.

The second-pass decision view supplied only a digest token, method, raw request
target, URI, query, logged-field metadata, Content-Type/Content-Length
presence, and body presence.  It excluded source file/label, sampling pool and
stratum, Prepare information, and every provisional decision/rationale/confidence.
Body was revealed separately only for the frozen not-scored observability audit.
The validation decision artifact was frozen before the provisional artifact was
opened for comparison.

The primary validation queue had 129 identities.  The not-scored audit queue
had 10 identities; overlap was 0, so the deduplicated validation population was
139.  The 83 non-queue cases were not second-reviewed and remain explicitly
`provisional_unvalidated`.

## Table A — validation accounting

Queue categories overlap by design; rows are not summed.

| Queue category | Provisional count | Validated count | Full agreement | Disagreement | Routed to adjudication |
|---|---:|---:|---:|---:|---:|
| A: exact four-family positive | 113 | 113 | 110 | 3 | 3 |
| B: observable Prepare miss | 14 | 14 | 10 | 4 | 4 |
| C: selected project-negative | 2 | 2 | 2 | 0 | 0 |
| D: ambiguous | 2 | 2 | 1 | 1 | 2 |
| E: medium/low confidence | 17 | 17 | 11 | 6 | 7 |
| F: selected source-normal | 2 | 2 | 2 | 0 | 0 |
| Not-scored body audit | 10 | 10 | 10 | 0 | 0 |

Comparison totals: 133 full agreements, 3 semantic-agreement/policy
disagreements, and 3 semantic disagreements.  There were no family or
observability disagreements.

## Table B — semantic agreement

Rows are provisional outcomes; columns are frozen second-pass outcomes before
adjudication.

| Provisional \ Validation | Positive | Negative | Not-scored | Ambiguous |
|---|---:|---:|---:|---:|
| Positive | 123 | 0 | 0 | 2 |
| Negative | 0 | 2 | 0 | 0 |
| Not-scored | 0 | 0 | 10 | 0 |
| Ambiguous | 0 | 1 | 0 | 1 |

Semantic agreement was 136/139 (97.84%).  Family agreement among cases that
both reviewers called attack-positive was 123/123 (100%).  Exact-policy
agreement was 110/113 (97.35%) among cases where either reviewer used `exact`.
Observability agreement (not-scored versus not not-scored) was 139/139 (100%).
These are reviewer-agreement metrics, not detector-performance metrics; kappa
is deliberately not reported for this stratified validation sample.

Confidence cross-tab: high/high full agreement 122; medium/medium full
agreement 10; medium/medium policy disagreement 3; medium/medium semantic
disagreement 2; low/low full agreement 1; low/low semantic disagreement 1.

## Table C — family agreement

| Provisional family | Validation same family | Validation ambiguous | Family disagreement |
|---|---:|---:|---:|
| SQLi | 46 | 0 | 0 |
| XSS | 40 | 0 | 0 |
| Command injection | 27 | 0 | 0 |
| Information gathering | 10 | 2 | 0 |

The two information-gathering reclassifications were semantic (positive to
ambiguous), not alternate-family calls.  File-disclosure cases were outside the
validation union and therefore remain provisional-unvalidated.

## Table D — adjudication

| Identity | Provisional | Validation | Final | Reason |
|---|---|---|---|---|
| anomalousTrafficTest.txt:13181:02bb7019… | SQLi/exact | SQLi/compatible | SQLi/exact | Visible boolean predicate is sufficient injection grammar. |
| anomalousTrafficTest.txt:7158:0dc61716… | ambiguous | negative | ambiguous | Isolated quote-plus-text credential fragment is not stable injection grammar. |
| anomalousTrafficTest.txt:9724:3f8e09d9… | SQLi/exact | SQLi/compatible | SQLi/exact | Standalone boolean comparison is sufficient SQLi request-pattern grammar. |
| anomalousTrafficTest.txt:19852:bbbd2444… | SQLi/exact | SQLi/compatible | SQLi/exact | Boolean comparison in the submitted target supports exact SQLi. |
| anomalousTrafficTest.txt:2300:003991ba… | information gathering | ambiguous | ambiguous | Nested `.OLD` target is not distinguishable from malformed routing. |
| anomalousTrafficTest.txt:6874:003f3f9f… | information gathering | ambiguous | ambiguous | Bare tilde path is insufficient to establish a resource-probing family. |
| anomalousTrafficTest.txt:15558:0043bcd0… | ambiguous/low | ambiguous/low | ambiguous | Preserved because both reviews were ambiguous and low confidence blocks forced-family treatment. |

All seven required adjudications are resolved.  Prepare metadata was not used
to select any semantic outcome.

## PUT and observability consistency

| Suppressed stratum | Positive | Negative | Not-scored | Ambiguous | Validation coverage |
|---|---:|---:|---:|---:|---:|
| GET/no body (40) | 14 | 25 | 0 | 1 | 14 |
| POST/body (40) | 0 | 30 | 10 | 0 | 10 |
| PUT/body (20) | 0 | 20 | 0 | 0 | 0 |

Suppressed PUT reviewed: 20.  Provisional PUT not-scored: 0.  The frozen
not-scored audit queue therefore correctly contains 0 PUT cases; this is not a
queue-generation defect.  PUT method alone was not treated as an attack or an
observability outcome.

## Selected source-normal results

| Identity | Final status | Final outcome |
|---|---|---|
| normalTrafficTraining.txt:20583:9c22c7c6… | validated_agreement | project_negative |
| normalTrafficTest.txt:27627:adfc562f… | validated_agreement | project_negative |

These are canonical reviewed selected project-negatives.  They are audit-sample
findings and must not be described as corpus false-positive rate.

## Prepare-miss results

The 14 provisional observable Prepare misses received validation/adjudication:
12 remain canonical reviewed observable misses, 0 were reclassified negative,
0 not-scored, and 2 ambiguous.

Canonical positive misses: anomalousTrafficTest.txt request indices 9724,
19852, 18346, 20323, 8725, 2969, 1716, 4613, 24797, 20757, 18832, and
18032.  Ambiguous after adjudication: request indices 2300 and 6874.  Full
digest identities are retained in the local comparison and summary artifacts.
This is an audit-sample finding, not corpus attack recall.

## Table E — future Stage1 eligibility

Only `validated_agreement` or `adjudicated` positives that were Prepare-selected
and use `exact` or `compatible_set` are eligible.  `provisional_unvalidated`
records are deliberately excluded.

| Family | Exact selected | Compatible selected | Exact suppressed | Provisional-unvalidated |
|---|---:|---:|---:|---:|
| SQLi | 44 | 0 | 2 | 0 |
| XSS | 40 | 0 | 0 | 0 |
| Command injection | 27 | 0 | 0 | 0 |
| Path traversal | 0 | 0 | 0 | 0 |
| File disclosure | 0 | 0 | 0 | 8 |
| Information gathering | 0 | 0 | 0 | 0 |

The frozen Stage1-scored eligibility count is 111.  Exact traversal support is
zero, so a CSIC strict traversal metric is not reported; CRS remains the
traversal-coverage benchmark.

## Canonical aggregates and decision

Validated/adjudicated canonical outcomes: attack-positive 123, project-negative
2, not-scored-observability 10, ambiguous 4.  Provisional-unvalidated outcomes:
attack-positive 8 and project-negative 75 (83 total).

6C-4 decision: **CONDITIONAL GO**.  Validated selected exact support is
sufficient for SQLi (44), XSS (40), and command injection (27).  Traversal has
zero support, file disclosure remains provisional-unvalidated, and
information-gathering is reviewed but not a Stage1 strict family.  No balancing,
resampling, detector tuning, Stage1 calls, or API benchmark calls occurred.

## Artifacts and controls

- Canonical manifest: `benchmarks/manifests/csic2010_reviewed_semantic_subset.v1.json`
- Local validation review: `/tmp/csic2010_validation_review.json`
- Local comparison: `/tmp/csic2010_review_comparison.json`
- Local summary: `/tmp/csic2010_validation_canonicalization_summary.json`

The canonical manifest contains no raw request line, body, Cookie value, or
Authorization value.  The review helper tests cover blind validation view,
comparison/adjudication routing, canonical Stage1 eligibility, manifest raw
content exclusion, and network-free validation.
