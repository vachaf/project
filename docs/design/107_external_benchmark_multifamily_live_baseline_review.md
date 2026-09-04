# Phase 6B-4R — CRS 930100/3 Live Traversal/File-Disclosure Boundary Review

## 1. Status, scope, and decision

- Review date: 2026-09-04 (Asia/Seoul)
- Scope: the sole exact-core live classification mismatch, `owasp_crs.930100.3`
- Frozen live baseline: Phase 6B-4 canonical single-live (`gpt-5.4-mini`)
- Source revision: `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`
- Method: source, manifest, production regeneration path, prompt, and frozen records read only
- API/model calls: **0**; benchmark reruns: **0**; production/benchmark changes: **0**

**Decision: Path B — systematic evidence/policy boundary.**  The source payload, synthetic adapter, and live sanitization all preserve the relevant raw representation, so this is not a harness/fidelity defect.  However, current Prepare does not materialize that representation as explicit traversal evidence.  It instead supplies an OS-file disclosure hint and `suspicious_file_disclosure` verdict hint.  Under the current conservative Stage1 prompt, the live file-disclosure result is a natural outcome of the classifier-visible representation.

Accordingly, a 6B-5 three-run repetition of this unchanged input is low-value.  The exact traversal annotation remains defensible as external semantic ground truth, while the gap is recorded as a project evidence-transfer/normalization limitation.  No production change is proposed or made in this review; CSIC work may proceed.

## 2. Frozen case and source semantics

Pinned source: `benchmarks/sources/owasp_crs/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/930100.yaml`.

```text
rule_id: 930100
test_id: 3
description: Path Traversal Attack Triple Dot (/.../) encoded
method: GET
uri: /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini
expect_ids: [930100]
```

The source semantics are encoded directory escape, not merely a request for a sensitive filename:

- `0x2e` is the dot atom representation recognized by the pinned CRS 930100 raw regex.
- `0x2f` is the separator atom representation recognized by that rule.
- `%00` is an interposed NUL encoding; it is part of the source representation.
- `WINDOWS/win.ini` is a sensitive OS-file target, but it is orthogonal context rather than the source test's primary traversal semantic.

The earlier case review remains controlling: CRS 930100 uses an encoded raw-pattern rule (`t:none`), rather than depending on a hidden whole-request canonicalization.  Thus source-level traversal semantics are clear even though current project normalization does not recognize that exact representation.  See [104_external_benchmark_930100_3_classification_review.md](./104_external_benchmark_930100_3_classification_review.md).

## 3. Manifest and historical annotation decision

The frozen 930 manifest records:

```text
classification_policy: exact
allowed Stage1 verdict: suspicious_path_traversal
forbidden verdicts: suspicious_sqli, suspicious_xss, suspicious_file_disclosure
required mapping IDs for traversal: A01:2025, CWE-22, WSTG-ATHZ-01
boundary: attempt_pattern_only_no_file_read_or_exploit_success
```

Its approved note says that pinned CRS raw encoded-regex semantics establish traversal and that missing Prepare traversal evidence is a known normalization coverage gap.  The prior review considered and rejected exact file disclosure and compatible traversal/file-disclosure: allowing the current detector's coverage to redefine ground truth would hide the observable encoded-normalization gap.  The live result does not revise that decision.

## 4. Evidence path

| Stage | Traversal-relevant evidence | File-disclosure-relevant evidence | Fidelity/result |
| --- | --- | --- | --- |
| Source | `0x2e.%000x2f0x2e.%00/` encoded dot/separator/NUL escape | `WINDOWS/win.ini` target | CRS test expects rule 930100 |
| Synthetic Apache | `GET /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini HTTP/1.1`; raw target unchanged | `win.ini` unchanged | method `GET`, URI `/get`, status `200`, source UA and `Host`/`Accept` preserved by source row adapter |
| Prepare | raw target unchanged; query/raw-request variants decode `%00` to NUL but retain literal `0x2e` and `0x2f`; no `traversal:*` | `file_disclosure:sensitive_resource:os_file` | selected, score `5`, verdict hint `suspicious_file_disclosure` |
| Classifier-facing | same raw target; decoded query/raw request contain NUL but no canonical `../` or `.../`; no traversal hint | same file-disclosure hint and verdict hint | only `request_id`/incident key neutralized and fixture UA changed to `Mozilla/5.0` |
| Stage1 output | no materialized explicit escape cited | `win.ini`, encoded separator form, status `200`, absent body/content type | `suspicious_file_disclosure`, medium confidence |

### 4.1 Synthetic Apache projection

The adapter splits the source request target without rewriting it:

```text
method: GET
raw_request_target: /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini
uri: /get
query_string: ?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini
raw_request: GET /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini HTTP/1.1
status_code: 200
user_agent: OWASP CRS test agent
Host: localhost; Accept: source fixture value
```

Neither `0x2e` nor `0x2f` is changed by this adapter.  This is correct adapter fidelity; it is not a source-projection loss.

### 4.2 Prepare and classifier-facing representation

Prepare's decoded variants use URL decoding, which converts `%00` to NUL but does not interpret `0x2e` as `.` or `0x2f` as `/`.  The selected candidate is:

```text
candidate_selected: true
candidate_score: 5
verdict_hint: suspicious_file_disclosure
reason_hints: [file_disclosure:sensitive_resource:os_file]
raw_request_target: /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini
uri: /get
query_string/raw_request: contain NUL where %00 was decoded; 0x2e and 0x2f remain text
status_code: 200
response_body_bytes: 0
resp_content_type: ""
```

The live executor's `_stage1_candidate()` changed only synthetic identity values and the exact fixture UA prefix:

```text
request_id: bench-owasp-crs-930100-3 -> live-row-001
incident_group_key: rid:bench-owasp-crs-930100-3 -> rid:live-row-001
user_agent: OWASP CRS test agent -> Mozilla/5.0
```

It did not alter raw request, raw target, URI, query string, status, score, verdict hint, or reason hints.  The classifier did not receive rule ID, test ID, expected family, ground truth, suite group, or benchmark identity.

## 5. Evidence inventories and prompt treatment

### Table B — policy comparison

| Evidence | Supports traversal | Supports file disclosure | Production prompt treatment |
| --- | --- | --- | --- |
| Literal `../` or `..\\` | absent | no | explicit directory escape required for traversal |
| Percent-encoded traversal (`..%2f`-style) | absent | no | can be an encoded equivalent when recognizable |
| `0x2e`/`0x2f` text with interposed NUL | source-level yes; classifier-visible **present-but-not-normalized** | indirect only | prompt says encoded equivalent, but does not define this CRS-specific hexadecimal/NUL grammar |
| Normalized directory escape | absent | no | would directly support traversal |
| `traversal:*` reason hint | absent | no | explicit structured traversal evidence |
| `WINDOWS/win.ini` | no by itself | present | sensitive-looking direct path alone cannot substitute for traversal |
| `file_disclosure:sensitive_resource:os_file` | no | present | structured sensitive-resource evidence; supplied to the model |
| Wrapper/resource evidence (`php://filter`, `resource=`, base64) | absent | absent | these are the prompt's strongest explicit file-disclosure preference examples |

The Stage1 system prompt requires `../`, an encoded equivalent, or a `traversal:*` hint as explicit directory-escape evidence for `suspicious_path_traversal`.  It also says that a sensitive-looking path, status/error, or UA cannot replace that evidence.  The prompt reserves explicit file-disclosure priority for wrapper/resource combinations, which this case lacks, but its general file-disclosure definition includes LFI-like file disclosure and Stage1 receives a direct OS-file structured hint plus file-disclosure verdict hint.

Therefore:

- **Did Prepare produce explicit traversal evidence? No.** There is no literal/canonical escape and no `traversal:*` hint.
- **Did Prepare produce file-disclosure evidence? Yes.** It produced the OS-file hint and matching verdict hint.
- **Did the classifier-facing input contain explicit directory escape? No, not in the materialized project representation.** The raw CRS encoding survives, but it remains literal `0x2e`/`0x2f` text with NULs rather than a recognizable/canonical escape form or structured traversal evidence.
- **Is the actual file-disclosure verdict consistent with the current Stage1 prompt? Yes.** It is conservative and consistent with the supplied structured evidence, although it does not change the source-ground-truth annotation.

The file-disclosure structured signal is stronger than the traversal structured signal: the latter is absent.  The answer to whether structured hints favor file disclosure over traversal is therefore **Yes**.

## 6. Fidelity and root-cause classification

### Table C — root cause

| Category | Supported? | Evidence |
| --- | --- | --- |
| A. Stochastic/borderline model variation | weakly supported only | medium confidence is not evidence of stochasticity; the live output follows the supplied file-disclosure-oriented representation |
| B. Systematic evidence/policy mismatch | **yes** | source escape survives but is not normalized/recognized by Prepare; no traversal hint; OS-file and file-disclosure hints are supplied |
| C. Annotation/policy reconciliation | not presently required | historical source and observable-raw evidence support exact traversal; one model output does not invalidate the approved annotation |
| D. Harness/fidelity issue | **no** | source target and adapter output match; sanitization neutralizes identifiers/fixture UA only and preserves payload/evidence fields |

**Fidelity answer:** Prepare's traversal-relevant raw evidence was not lost in sanitization.  It was preserved as raw text, but was never converted into a classifier-materialized traversal signal by current Prepare normalization/hints.  D is excluded; this is B, not a live harness bug.

## 7. Source semantics versus project observable semantics

| Layer | Conclusion |
| --- | --- |
| Source semantics | Clear encoded directory escape; CRS rule 930100 directly recognizes the raw representation. |
| Project observable surface | The raw representation is directly observable in the Apache-shaped request target. |
| Current project classifier-visible semantics | Weak traversal signal: raw hex/NUL text is preserved but not canonicalized or tagged; direct sensitive-file evidence is explicit and structured. |

Thus source-level traversal semantics are clear while project classifier-visible traversal evidence is weak.  This distinction is exactly why the annotation remains useful: it measures an observable production normalization/evidence-transfer limitation rather than silently redefining the external semantic label.

## 8. Actual live reasoning and counterfactuals

Frozen live record summary:

```text
verdict: suspicious_file_disclosure
confidence: medium
reasoning: win.ini and encoded separator-shaped input suggest a file/config disclosure attempt;
           no wrapper, response body, or content type establishes actual disclosure.
evidence fields: win.ini target; encoded separator form; status 200; missing body/content type.
```

It did not claim successful file access.  Its cited evidence follows the file-disclosure-oriented candidate rather than identifying a normalized traversal sequence.

Counterfactuals, evaluated without changing code/prompt or calling a model:

1. If a bounded canonical `../`/`.../` representation or a `traversal:*` hint were present, the current Stage1 contract would make traversal the clearer primary selection.  This is a policy inference, not a proposal to implement a change.
2. With the actual combination—uninterpreted `0x2e`/`0x2f` text, NULs, `win.ini`, and a structured OS-file/file-disclosure hint—file disclosure is a reasonable conservative Stage1 result under the current prompt.

## 9. Stability value and annotation decision

1. **Could three identical calls plausibly differ?** Any generative output may vary, but the current evidence shape gives no affirmative reason to expect a different verdict; the structured signal is consistently file-disclosure-oriented.
2. **Does medium confidence establish stochasticity? No.** It is an output confidence label, not a variance measurement.
3. **What would repetition add if the policy/evidence structure is systematic?** At most a frequency estimate for this representation; it would not resolve the absence of materialized traversal evidence or change the diagnosis.

**6B-5 decision: skip.** The expected information value of a three-run stability check is low under the current frozen input.  This is not a conclusion that the model can never vary; it is a prioritization decision for this benchmark roadmap.

**Annotation decision: annotation remains defensible.** It is neither an annotation error nor a present reconciliation blocker.  No manifest update is made.

## 10. Mapping, broader live context, and next work

`930100/3` correctly records `mapping = not_scored_due_to_classification`; mapper behavior was not evaluated or changed here.

The issue is isolated:

```text
CMDi exact-core Stage1: 9/9
XSS exact-core Stage1:  5/5
SQLi exact-core Stage1: 7/7
Traversal selected:     7/8
cross-family confusion: 0
mapping on compatible cases: 35/35
```

Exact-core E2E has one Stage1 mismatch and seven Prepare `NOT_SELECTED` cases.  The larger E2E ceiling is therefore Prepare candidate selection, not this single Stage1 boundary result.

No production code change should be made before broader benchmarking on the basis of this one review.  Preserve this documented limitation, keep the frozen annotation, and proceed with CSIC work next.  Any later normalization/evidence work must be independently scoped and evaluated, not retrofitted to this live result.

## 11. Validation

Documentation-only change set:

```text
docs/design/107_external_benchmark_multifamily_live_baseline_review.md
docs/design/README.md
```

No API call, benchmark rerun, production code, prompt, manifest, suite, source, mapper, or annotation change was made.
