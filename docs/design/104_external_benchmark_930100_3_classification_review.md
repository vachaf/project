# External Security Benchmark Phase 5B-3C — CRS 930100/3 Classification Annotation Review

## 1. Review status and final decision

- Review date: 2026-09-03 (Asia/Seoul)
- Repository baseline: `66a3d4f` (`docs: review traversal sensitive-resource mapping boundary`)
- Scope: `owasp_crs.930100.3` project classification annotation only
- Change scope: documentation only
- Final decision: **A. exact `suspicious_path_traversal` 유지**

Current manifest의 classification policy는 유지한다.

```text
project_ground_truth = attack_positive
candidate_expected = true
observability.status = direct
classification_policy = exact

allowed_stage1_verdicts:
- suspicious_path_traversal
```

`suspicious_file_disclosure`는 current Prepare가 제공하는 direct-sensitive evidence에 부합하는 plausible fallback interpretation이지만, 이 case의 source와 raw request 자체가 encoded directory escape를 명시하므로 project primary verdict로 허용하지 않는다. Current Prepare가 이를 traversal hint로 만들지 못하는 사실은 annotation 변경 사유가 아니라 normalization/evidence-enrichment coverage gap이다.

Phase 5B-3M 결론에 따라 classification은 유지하되 mapping contract는 후속 Phase 5B-3M-F에서 다음과 같이 정렬해야 한다.

```text
suspicious_path_traversal:
  required_ids:
  - A01:2025
  - CWE-22
  - WSTG-ATHZ-01

  forbidden_ids: []
```

Structured direct-sensitive evidence로 생성되는 `CWE-552 conditional`과 `WSTG-CONF-04 related`는 optional/non-forbidden이다.

## 2. Reviewed sources

### 2.1 Pinned source

- Repository: <https://github.com/coreruleset/coreruleset>
- Revision: `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`
- Vendored regression source: `benchmarks/sources/owasp_crs/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/930100.yaml`
- Upstream path: `tests/regression/tests/REQUEST-930-APPLICATION-ATTACK-LFI/930100.yaml`
- Pinned rule: <https://github.com/coreruleset/coreruleset/blob/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf>
- Upstream rule inspected: 2026-09-03

### 2.2 Project contracts

- `docs/design/101_external_security_benchmark_design.md`
- `docs/design/102_external_benchmark_prepare_baseline_review.md`
- `docs/design/103_external_benchmark_mapping_boundary_review.md`
- `src/prepare/decoders.py`
- `src/prepare/traversal_cmdi_hints.py`
- `src/prepare/file_disclosure_hints.py`
- `src/prepare_llm_input.py`
- `src/llm_stage1_classifier.py`
- relevant Prepare/Stage1/external benchmark tests

## 3. Source semantics

### 3.1 Pinned test meaning

The pinned test is explicit.

```text
rule_id: 930100
test_id: 3
description: Path Traversal Attack Triple Dot (/.../) encoded
request target:
  /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini
source expectation:
  expect_ids: [930100]
```

`expect_ids:[930100]` alone is not automatically a project Stage1 label. However, the pinned rule and request were also inspected. Their content independently establishes encoded directory-escape semantics, so this is not a rule-ID-to-verdict shortcut.

### 3.2 Rule 930100 does not rely on a hidden transformation chain

Rule 930100 is the CRS “Encoded `/../` Payloads” rule. Its relevant properties at the pinned revision are:

- target collections include `REQUEST_URI_RAW`, `ARGS`, request headers except Referer, files and XML values/attributes;
- transformation is `t:none`;
- the regular expression itself enumerates encoded separator and dot representations;
- `0x2f` and `0x5c` are accepted separator forms;
- `0x2e` is an accepted dot form;
- a literal dot may carry an optional `%00`/`%01`-style insertion;
- two or three dot atoms between separator atoms are accepted;
- message semantics cover both `/../` and `/.../` traversal;
- the rule is paranoia level 1, not a higher-paranoia-only sibling.

For this payload, the decisive substring can be understood as follows.

```text
0x2f  0x2e  .%00  /
  |      |     |   |
separator dot   dot separator
```

The earlier `0x2e.%00` forms the preceding encoded dot segment. CRS does not first convert the whole request into a canonical plain path for rule 930100; the raw-pattern regex recognizes these encodings directly. Therefore the older shorthand “CRS `0x`/NUL transform” in project docs is imprecise. The accurate statement is:

```text
CRS 930100 recognizes the encoded representation directly with a raw regex;
the current project decoder and traversal patterns do not implement that
rule-specific encoded representation.
```

The source test description says triple-dot, while the rule itself deliberately covers two- or three-dot traversal forms. That wording distinction does not affect the project family: the decisive source semantic is encoded directory escape.

## 4. Rule 930100 versus 930110

The two CRS rules are siblings in the same LFI rule file, but they cover different representations.

| Property | CRS 930100 | CRS 930110 |
| --- | --- | --- |
| Rule role | encoded `/../` or `/.../` representations | decoded/canonical `/../`, `/.../` and semicolon variants |
| Detection shape | large regex enumerating encoded slash/backslash/dot forms | compact segment regex around two or three literal dots |
| Transform chain | `t:none` | `t:none`, `t:utf8toUnicode`, `t:urlDecodeUni`, `t:removeNulls`, `t:cmdLine` |
| Regex boundary | encoded or literal separator + 2/3 encoded/literal dots + encoded or literal separator | start or `/`, `;`, backslash + 2/3 literal dots + `/`, `;`, backslash |
| `multiMatch` | no | yes |
| Paranoia level | 1 | 1 |
| Shared semantics | LFI-tagged path traversal attempt; no exploit/file-read success claim | same |

Rule 930100 is not “stricter because its number is lower” and is not a different project vulnerability class. It recognizes encoding evasions directly. Rule 930110 simplifies matching after ModSecurity transforms have exposed a decoded path-like representation.

For comparison:

- `930100/3` is expected to trigger the encoded-representation rule 930100.
- `930110/2` contains plain `../../../etc/passwd` and triggers decoded/plain traversal rule 930110.
- `930110/9` contains literal triple-dot segments and also triggers 930110.

## 5. Project observable surface

### 5.1 Level 1 synthetic row

Current source adapter preserves the request in the fields used by Prepare and Stage1.

| Field | Value/meaning |
| --- | --- |
| `raw_request` | `GET /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini HTTP/1.1` |
| `raw_request_target` | `/get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini` |
| `uri` | `/get` |
| `query_string` | `?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini` |
| request body dependency | none |
| arbitrary-header dependency | none |

The decisive encoded text is therefore directly observable in the Level 1 Apache-shaped row and reaches the Stage1 candidate. This case is not analogous to POST body, XML attribute or unavailable arbitrary-header exclusions.

### 5.2 Apache logs-only distinction

The project log contract can preserve the raw request line through `%r`, from which `raw_request_target` is extracted. The benchmark adapter also preserves the exact source representation. Thus:

```text
observable raw representation = yes
currently recognized as traversal by Prepare = no
```

These are separate questions. `observability.status=direct` concerns whether the decisive request representation exists on the project input surface, not whether the current detector already understands it.

Actual local Apache request acceptance/log fidelity remains a Level 2 realism check. It does not justify marking this Level 1 request `partial` or `out_of_scope`; the source representation is present in the scored surface.

## 6. Current project decoder contract

### 6.1 URL decoding

`build_decoded_variants()` starts with depth 0 and repeatedly calls `urllib.parse.unquote_plus`, with default maximum depth 2. It stops when the decoded text no longer changes.

Current reproduction for the query string:

```text
depth 0:
  ?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini

depth 1:
  ?foo=0x2e.<NUL>0x2f0x2e.<NUL>/WINDOWS/win.ini

depth 2:
  not emitted because another unquote_plus call makes no change
```

The behavior is:

| Representation | Current project handling |
| --- | --- |
| `%00` | decoded by `unquote_plus` to `\x00` |
| `0x2e` | left as literal text; not converted to `.` |
| `0x2f` | left as literal text; not converted to `/` |
| repeated percent decoding | at most depth 2; this case stabilizes at depth 1 |
| NUL removal | none in the decoder/traversal path |
| `utf8toUnicode` equivalent | none |
| `cmdLine` equivalent | none |
| slash/backslash/path canonicalization | none in this traversal detection path |
| CRS rule-specific encoded regex | none |

### 6.2 Traversal and file evidence

Current `TRAVERSAL_PATTERNS` supports bounded plain `../`/`..\`, literal triple-dot slash, selected percent-encoded dot/slash forms and one selected double-encoded form. It does not support the 930100 `0x2e`/`0x2f` plus NUL-insertion representation.

The raw and depth-1 variants therefore produce no `traversal:*` hint.

`FILE_DISCLOSURE_PATTERNS`, independently, recognizes `WINDOWS/win.ini` with a resource boundary. That adds score 5 and:

```text
file_disclosure:sensitive_resource:os_file
```

Current Prepare reproduction is:

```text
candidate_selected = true
candidate_score = 5
verdict_hint = suspicious_file_disclosure
reason_hints = [file_disclosure:sensitive_resource:os_file]
traversal evidence = none
```

Prepare candidate recall remains `9/19`; `930100/3` remains selected.

## 7. Architecture boundary: Prepare versus Stage1

The pipeline is:

```text
raw Apache evidence
  -> Prepare candidate selection and deterministic evidence enrichment
  -> Stage1 conservative classification
```

Prepare hints are clues, not ground truth, and Stage1 receives the raw request fields as well as hints. Stage1 is allowed to reason from `raw_request` and `raw_request_target`; it is not contractually limited to copying `verdict_hint`.

However, the absence of a traversal hint matters operationally. It means the current deterministic layer has not exposed the encoded escape in a stable, auditable form. Relying on the LLM to reproduce CRS's large encoded regex is not the preferred production fix.

These two statements can both be true:

1. Exact traversal is the correct external benchmark annotation.
2. A robust production improvement, if prioritized later, belongs in bounded Prepare normalization/evidence rather than an instruction that asks Stage1 to emulate all CRS transforms and regexes.

The exact annotation evaluates the end-to-end pipeline and does not prescribe which component must close the gap. If Stage1 chooses `suspicious_file_disclosure`, the classification failure should be attributed diagnostically to encoded traversal normalization/evidence transfer, not automatically to model negligence.

## 8. Stage1 verdict semantics

### 8.1 `suspicious_path_traversal`

Current Stage1 contract requires explicit directory-escape evidence and lists `../`, encoded equivalents and `traversal:*` hints as examples. A hint is one way to carry the evidence, not the only one. Here the raw request contains an encoded equivalent confirmed by the pinned 930100 rule semantics.

The case therefore meets the project meaning of `suspicious_path_traversal` even though current Prepare does not recognize it.

### 8.2 `suspicious_file_disclosure`

The `WINDOWS/win.ini` target is a valid sensitive OS-file targeting signal. It supports an attempt-only file-disclosure interpretation and does not claim that the file exists or was returned.

Nevertheless, project annotation needs one primary verdict. Existing project policy gives explicit traversal structure priority over the direct-sensitive target:

- `.../.../WINDOWS/win.ini` is exact traversal, not compatible traversal/file disclosure.
- `../../../etc/passwd` is exact traversal, not compatible traversal/file disclosure.
- direct `/etc/passwd` without escape is exact file disclosure.

Once the 930100 raw encoding is recognized as explicit directory escape, `930100/3` belongs with the first two cases. The sensitive target is preserved orthogonally in standards mapping rather than promoted to a second primary verdict.

## 9. Benchmark ground-truth policy

Phase 5A separates three layers.

```text
source expectation/provenance
  != project classification annotation
  != Apache logs-only observability
```

It also prohibits automatically translating a CRS rule ID into a Stage1 verdict. This case still qualifies as exact traversal because all of the following hold after independent review:

1. the source test explicitly exercises rule 930100;
2. the pinned rule's raw regex directly recognizes an encoded separator-dot-dot-separator structure;
3. the encoded text is preserved in the project raw target;
4. encoded directory escape is within the existing `suspicious_path_traversal` definition;
5. no response/exploit-success fact is added.

When an externally meaningful attack representation is observable but current normalization does not recognize it, the benchmark should retain external semantic ground truth and record the miss as coverage. Restricting ground truth to already-supported normalization would make the benchmark unable to reveal normalization gaps.

This is **Policy 1: external semantic ground truth 유지**. It is case-specific: source meaning must be manually shown to map to a project verdict, and the decisive representation must remain observable.

## 10. Options review

| Option | Strength | Problem | Decision |
| --- | --- | --- | --- |
| A — exact traversal | preserves verified source semantics; keeps encoded normalization gap measurable; matches explicit-traversal precedence and Phase 5A design | a live Stage1 model must interpret raw encoding without a traversal hint until Prepare coverage improves | **select** |
| B — exact file disclosure | aligns with current Prepare hint and the observable `win.ini` token | turns current detector coverage into ground truth; discards verified encoded traversal semantics; contradicts intentional normalization-risk case role | reject |
| C — compatible traversal/file disclosure | acknowledges source traversal and current fallback evidence | treats an implementation/evidence-enrichment gap as inherent taxonomy ambiguity; weakens the exact normalization coverage metric | reject |

`compatible_set` is appropriate when the project taxonomy itself has multiple defensible primary interpretations. Here the two interpretations are not symmetric: traversal is established by source rule semantics and raw text, while file disclosure becomes primary only because the current deterministic normalization misses that structure. Model uncertainty is not a reason to widen the allowed set.

## 11. Comparison with strong controls

| Case | Raw traversal structure | Current Prepare traversal hint | Direct-sensitive hint | Project primary verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| `930100/2` | literal triple-dot escape | `traversal:triple_dot_slash(+4)` | OS file | exact traversal | both project detector and source expose escape directly |
| `930100/3` | CRS 930100 raw-encoded escape | none | OS file | exact traversal | source/raw semantics are explicit; project normalization gap remains measurable |
| `930110/2` | literal `../../../` | `traversal:dotdot_slash(+4)` | OS file | exact traversal | unambiguous plain directory escape |

The difference justifies different diagnostic status, not different classification ground truth.

- `930100/2`, `930110/2`: supported explicit traversal
- `930100/3`: observable but currently unsupported explicit traversal representation

All three retain direct-sensitive evidence as orthogonal context.

## 12. Mapping implications

### 12.1 Selected Option A contract

Current production mapping for a forced traversal verdict plus this Prepare hint is:

```text
A01:2025       direct
CWE-22         direct
CWE-552        conditional
WSTG-ATHZ-01   direct
WSTG-CONF-04   related
```

The reviewed manifest contract should be:

```json
{
  "classification_policy": "exact",
  "allowed_stage1_verdicts": [
    "suspicious_path_traversal"
  ],
  "forbidden_stage1_verdicts": [
    "suspicious_sqli",
    "suspicious_xss",
    "suspicious_file_disclosure"
  ],
  "mapping_by_verdict": {
    "suspicious_path_traversal": {
      "required_ids": [
        "A01:2025",
        "CWE-22",
        "WSTG-ATHZ-01"
      ],
      "forbidden_ids": []
    }
  }
}
```

No optional-ID schema is needed. CWE-552 and WSTG-CONF-04 are allowed because they are not forbidden.

### 12.2 Rejected Option B contract

If exact file disclosure had been selected, current direct-sensitive production mapping would support:

```text
required:
  A02:2025
  CWE-552
  WSTG-CONF-04
  WSTG-CONF-03
forbidden:
  CWE-22
```

This mapping is internally coherent but rests on the rejected classification policy.

### 12.3 Rejected Option C contract

A compatible set would need separate mapping contracts:

- traversal: require A01/CWE-22/WSTG-ATHZ-01; allow CWE-552/WSTG-CONF-04
- file disclosure: require A02/CWE-552/WSTG-CONF-03/04; forbid CWE-22

The evaluator supports this shape, but schema capability is not a reason to use a semantically weaker policy.

## 13. Candidate expectation and eligibility

### 13.1 `candidate_expected=true` remains

The raw request has two independent security signals.

- verified encoded traversal representation from source semantics
- direct `WINDOWS/win.ini` targeting visible to the current project

Even without current traversal normalization, the direct-sensitive OS-file targeting is sufficient to require Stage1 review. Candidate expectation is not justified merely because current Prepare happens to select it; it is justified by the security-relevant request content.

### 13.2 `observability.status=direct` remains

The decisive source representation is in a GET query/raw target. No missing body or arbitrary header is required. Unsupported normalization is not lost observability. Therefore:

```text
eligible = true
status = direct
exclusion_reason = null
```

## 14. Preserving the normalization-risk diagnostic

Changing the classification annotation is unnecessary to preserve source provenance because the current benchmark already records:

- source rule ID `930100`
- source test ID `3`
- source description and `expect_ids`
- exact raw request target
- Prepare reason hints and verdict hint
- `strict_traversal` family membership
- dedicated `encoded_normalization_risk` family membership

The family metric currently reports candidate selection, not successful traversal normalization. The case-level absence of `traversal:*`, the Prepare verdict hint and the exact Stage1 result together provide the needed diagnostic.

No new `normalization_risk` or `source_semantic_family` schema fields are needed now. If future reporting needs a dedicated normalization-success numerator, it should be a reporting-only metric derived from existing provenance and reason hints, not a relaxation of classification ground truth.

## 15. Frozen manifest and version policy

“Frozen” means reproducible and reviewed, not immutable forever. A documented taxonomy or observability error can be corrected before a publishable baseline.

This review finds no classification annotation error, so the exact verdict stays unchanged. Phase 5B-3M-F still needs a mapping-boundary correction and a clearer review note.

The following remain unchanged:

```text
benchmark = owasp_crs_path_file_access.v1
schema_version = external_security_benchmark_manifest.v1
annotation.version = owasp_crs_path_file_access.v1
manifest filename = owasp_crs_path_file_access.v1.json
```

Repository policy explicitly calls for annotation-version review on source drift. Here source revision, checksums, case inventory and schema shape do not change. A single pre-live reviewed mapping correction and note clarification do not justify a version bump. Commit history, review note and this document provide correction provenance.

## 16. Metric and live-baseline impact

### 16.1 Prepare

Classification annotation and mapping-contract alignment do not affect Prepare execution.

```text
candidate recall remains 9/19
930100/3 remains selected
encoded_normalization_risk remains 1/1 candidate-selected
```

### 16.2 Controlled Stage1

The controlled fixture already chooses exact traversal, so classification compatibility does not change. Removing the outdated CWE-552 mapping forbidden will turn this case's mapping result from fail to pass. When the other three Phase 5B-3M cases are aligned, the current controlled mapping metric should move from `5/9` to `9/9` without changing production mapper output.

### 16.3 Live Stage1 fairness

No live Stage1 benchmark artifact or live verdict was present during this review. The decision is made before observing a live output and retains the stricter exact label even though current Prepare points toward file disclosure. Therefore it does not optimize annotation around model behavior.

If a future live run returns `suspicious_file_disclosure`, it should fail this exact classification contract. The result is useful: it exposes an observable encoded-traversal coverage/evidence-transfer gap. That failure must not be “fixed” by widening the manifest after seeing the score.

## 17. Answers to the required questions

1. **930100/3은 Apache logs-only에서 directly observable한가?** Yes. The decisive text is in the GET raw request target/query, with no body or unavailable-header dependency.
2. **Current project가 그 raw encoding을 directory escape로 normalize하는가?** No. `%00` becomes NUL, but `0x2e`/`0x2f` remain literal and no NUL removal or path canonicalization follows.
3. **Normalize하지 못해도 Stage1 exact traversal을 요구하는 것이 architecture상 타당한가?** Yes as an end-to-end benchmark contract. It measures the gap; it does not prescribe LLM-only decoding as the production remedy.
4. **Current evidence에서 `suspicious_file_disclosure`는 의미상 타당한가?** It is a plausible attempt-only fallback based on `win.ini`, but not the correct primary verdict after verified encoded traversal semantics are considered.
5. **Exact traversal / exact file disclosure / compatible set 중 무엇이 가장 타당한가?** **A. exact `suspicious_path_traversal`.**
6. **`candidate_expected=true`를 유지해야 하는가?** Yes. The request has sufficient security signal independently of current detector behavior.
7. **`eligibility=direct`를 유지해야 하는가?** Yes. Observable and normalized-by-project are separate properties.
8. **선택한 verdict policy의 mapping contract는 무엇인가?** Require A01:2025, CWE-22 and WSTG-ATHZ-01; no forbidden mapping IDs; allow CWE-552 conditional and WSTG-CONF-04 related as extras.
9. **이 correction이 benchmark score chasing이 아닌 이유는 무엇인가?** No live output has been measured, source/rule semantics were inspected first, and the selected exact label is stricter than the current Prepare hint.
10. **Publishable live baseline 전에 manifest를 어떻게 수정해야 하는가?** Keep exact traversal/candidate/direct eligibility, remove CWE-552 from mapping forbidden, and update the review note to record raw-rule semantics and the known project normalization gap.

## 18. Phase 5B-3M-F follow-up scope

### 18.1 Manifest

`benchmarks/manifests/owasp_crs_path_file_access.v1.json`

- keep `930100/3` exact `suspicious_path_traversal`;
- keep `suspicious_file_disclosure` in forbidden Stage1 verdicts;
- keep candidate expected and direct eligibility;
- change traversal mapping `forbidden_ids` from `["CWE-552"]` to `[]`;
- clarify `review.note`: pinned 930100 raw encoded regex establishes traversal while current Prepare emits only direct-sensitive evidence.

The same mapping phase should remove CWE-552 forbidden from `930100/2`, `930110/2` and `930110/9` as decided in Phase 5B-3M.

### 18.2 Tests

- `tests/test_external_benchmark_crs.py`
  - retain `930100/3` in the exact strict-traversal set;
  - assert the reviewed case-specific mapping forbidden policy.
- `tests/test_external_benchmark_prepare.py`
  - lock raw-target fidelity, no traversal hint and direct-sensitive hint for `930100/3`.
- `tests/test_external_benchmark_stage1.py`
  - rename the “frozen expectation” regression to the reviewed exact policy;
  - update controlled mapping failures/metric after all four 5B-3M alignments.
- `tests/test_security_standards_mapping.py`
  - lock traversal verdict + direct-sensitive evidence as primary traversal plus CWE-552 conditional/WSTG-CONF-04 related.

### 18.3 Canonical docs

- `docs/design/101_external_security_benchmark_design.md`
  - retain exact traversal;
  - correct “CRS transform” shorthand to raw encoded-regex semantics;
  - align CWE-552 optional mapping.
- `docs/design/102_external_benchmark_prepare_baseline_review.md`
  - add a correction note distinguishing CRS 930100 raw matching from current project decoding.
- `docs/design/103_external_benchmark_mapping_boundary_review.md`
  - mark the `930100/3` classification question resolved as exact traversal.

No production source, evaluator, schema or manifest version bump is required.

## 19. Live baseline go/no-go

**Current state: no-go for a publishable live baseline until Phase 5B-3M-F lands.**

The classification annotation itself is approved unchanged. The remaining blocker is the known mapping contradiction and its tests/docs alignment. After Phase 5B-3M-F produces a clean controlled baseline, a single live Stage1 baseline may proceed. A live `930100/3` classification failure, if observed, must remain visible as the intended normalization-risk result.

## 20. Final decision

```text
A. exact suspicious_path_traversal 유지
```

Source semantic and project semantic are aligned once the raw 930100 encoding is interpreted correctly. Current Prepare evidence is incomplete, not contradictory ground truth. Exact classification preserves the benchmark's ability to measure an observable but unsupported normalization representation.
