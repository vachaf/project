# CSIC 2010 reviewed Stage1 controlled/replay review (6C-4)

Date: 2026-09-05

## Status and provenance

6C-4 is complete.  The evaluator is deliberately network-free and exposes
only `controlled` and `replay` modes; it has no live mode and does not import
or call `classify_candidate()`.  The controlled run is a deterministic
evaluator regression fixture, not an external-model result.

The reviewed manifest SHA-256 gate is
`30c67e6d1ddeb6cb890cd1446ea0e2da87e4c61c3ff9144bee7c3596e6d846bf`.
Source hashes and parser inventories were checked against the 6C-1 source
manifest before raw request rehydration.  No raw request line, body, Cookie, or
Authorization content is stored in the evaluator result.

## Eligibility contract and frozen reviewed support

Scored positives require validated/agreed or adjudicated status, attack-positive
semantics, Prepare selection, `exact` or `compatible_set` policy, and a strict
family in SQLi/XSS/CMDi/traversal.  Provisional-unvalidated (83), ambiguous
(4), not-scored (10), file-disclosure (8 provisional-unvalidated), and
information-gathering records are excluded from strict Stage1 scoring.

| Family | Selected exact | Suppressed exact | Full exact |
|---|---:|---:|---:|
| SQLi | 44 | 2 | 46 |
| XSS | 40 | 0 | 40 |
| Command injection | 27 | 0 | 27 |
| Traversal | 0 | 0 | 0 |
| Total | 111 | 2 | 113 |

Reviewed selected project-negative controls: 2.  They are isolated controls,
not a corpus specificity/FPR estimate.

## Prepare fidelity

All 222 canonical identities were rehydrated from local frozen raw source and
matched the frozen Prepare index identity, method, raw-request hash, and
selected state.  Production `build_outputs()` was regenerated through the
existing isolated CSIC Prepare path for 115 records: 113 full exact positives
plus two selected negative controls.  Regenerated selected, score,
verdict-hint, and reason-hint values matched the frozen Prepare index.

The two suppressed exact SQLi records were regenerated but deliberately have
no Stage1 input/result.  They are recorded as `NOT_SELECTED` only in the E2E
matrix.

## Controlled Stage1 matrix

The controlled fixture produced the canonical strict verdict for every selected
strict positive.  Cross-family confusion and Stage1 errors were both zero.

| Family | Selected support | Compatible | Other | Error |
|---|---:|---:|---:|---:|
| SQLi | 44 | 44 | 0 | 0 |
| XSS | 40 | 40 | 0 | 0 |
| CMDi | 27 | 27 | 0 | 0 |
| Traversal | 0 | N/A | N/A | N/A |
| Total | 111 | 111 | 0 | 0 |

Primary metric: **Stage1 compatibility given reviewed Prepare-selected case** =
111/111.  This is not a corpus precision claim.

## Controlled E2E

| Family | Full exact | Compatible | NOT_SELECTED |
|---|---:|---:|---:|
| SQLi | 46 | 44 | 2 |
| XSS | 40 | 40 | 0 |
| CMDi | 27 | 27 | 0 |
| Traversal | 0 | N/A | N/A |
| Total | 113 | 111 | 2 |

Controlled E2E compatibility is 111/113.  This is the Prepare selection ceiling
on the reviewed exact subset: even a perfect controlled Stage1 fixture cannot
make SQLi 46/46 because two reviewed SQLi cases are not selected.

## Reviewed negative controls

| Metric | Support | Compatible outcome | Result |
|---|---:|---|---:|
| `reviewed_negative_control_compatibility` | 2 | `likely_false_positive` | 2/2 |

The explicit evaluator policy accepts `likely_false_positive` for these two
reviewed controls.  They are not included in positive denominators, strict
matrices, standards-mapping scoring, specificity, FPR, or true-negative-rate
metrics.

## Mapping consistency

Mapping runs only after a classification-compatible positive result.  The
controlled fixture passed all contracts; mismatch would produce
`not_scored_due_to_classification` rather than invoking mapping.

| Family | Classification-compatible | Mapping passed | Mapping failed | Not scored due to classification |
|---|---:|---:|---:|---:|
| SQLi | 44 | 44 | 0 | 0 |
| XSS | 40 | 40 | 0 | 0 |
| CMDi | 27 | 27 | 0 | 0 |
| Traversal | 0 | N/A | N/A | N/A |
| Total | 111 | 111 | 0 | 0 |

Required current mapper contracts are SQLi: A05/CWE-89/WSTG-INPV-05; XSS:
A05/CWE-79/WSTG-INPV-01; and CMDi: A05/CWE-78/WSTG-INPV-12.

## Traversal and benchmark roles

CSIC strict traversal support is zero.  Traversal recall is therefore not
reported, not `0%`; traversal coverage remains CRS-covered.

CRS is the curated four-family semantic/regression benchmark, including
traversal coverage.  CSIC is the natural-corpus reviewed audit subset plus the
corpus-scale Prepare selectivity/enrichment benchmark.

## Replay contract and determinism

Replay accepts only saved records with source identity, completed known Stage1
verdict, numeric confidence, and optional reasoning/evidence.  It rejects
unknown, missing, and duplicate identities.  The controlled replay fixture
reproduces the controlled result after normalizing the mode field.  Two
controlled runs were byte-identical.

## 6C-5 decision

**6C-5 = OPTIONAL GO.**  A future live decision is separate and must not be
inferred from controlled results.  It may evaluate the frozen 111 selected
exact positives plus two reviewed negative controls, or a separately approved
smaller frozen live subset.  No detector, prompt, mapper, or Prepare tuning is
authorized by this phase.
