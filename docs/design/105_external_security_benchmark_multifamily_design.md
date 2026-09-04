# Phase 6A — OWASP CRS multi-family external benchmark 조사·상세 설계

## 1. Purpose and recommendation

This is research and detailed design only. No production detector, Prepare, Stage1 prompt, mapper, benchmark manifest, schema, test, DB, or source is modified. No live model call or commit is made.

Recommendation: make frozen 930 plus new 932, 941, and 942 the primary source families. Use family manifests plus a reference-only suite. Keep 913 as an optional scanner-identification policy lane, not a primary attack class. Build a fixed 36-case four-class balanced exact core: nine each traversal, SQLi, XSS, and command injection. Keep the single clean 930 file-disclosure case in a separate path/file boundary addendum; do not falsely balance it as a fifth macro class.

| Item | Decision |
| --- | --- |
| Primary | 930 frozen component; new PL1-first 932 CMDi subset, 941 XSS, 942 SQLi |
| Optional | 913 scanner-identification policy lane |
| Deferred | 933, CSIC 2010, ECML/PKDD, generic suspicious_rce |
| Architecture | family manifests plus suite manifest |
| Matrices | separate Stage1-conditioned and end-to-end matrices |
| Smallest next unit | generic source bundle/loader plus family manifests; no detector change |

High benchmark performance is not real-world attack detection rate, vulnerability confirmation, exploit success, or WAF effectiveness.

## 2. Baseline and motivation

Frozen owasp_crs_path_file_access.v1 has 36 source cases: 27 direct, 3 partial, 6 out of scope; 19 expected candidates and 8 project negatives. Current Prepare recall is 9/19 and negative suppression 8/8. The controlled fixture reports Stage1 compatibility 9/9, E2E 9/19, negatives 8/8, mapping 9/9. Those are not live-model results.

930 cannot distinguish a Prepare omission from SQLi to XSS or traversal to file-disclosure confusion. The pipeline remains source → reviewed normalized case → isolated neutral Apache row → production Prepare → production Stage1 → deterministic mapper → evaluator. Source rule ID, family, expected verdict and ground truth never reach Stage1.

## 3. Pinned source and method

- Repository: https://github.com/coreruleset/coreruleset
- Revision: 96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a.
- Inspected pinned rules: REQUEST-932-APPLICATION-ATTACK-RCE.conf, REQUEST-941-APPLICATION-ATTACK-XSS.conf, REQUEST-942-APPLICATION-ATTACK-SQLI.conf, REQUEST-913-SCANNER-DETECTION.conf.
- Inspected their corresponding pinned regression directories.

Every YAML test/stage was counted and rule ID joined to its actual pinned paranoia-level tag. Every test in these directories is single-stage. expect_ids/no_expect_ids is CRS provenance only, never a project label.

Representative one-off investigation commands were: `git -C /tmp/crs-phase6a rev-parse --verify 96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a^{commit}`, `find /tmp/crs-phase6a/tests/regression/tests -path '*REQUEST-9*' -name '*.yaml'`, `rg -n "id:|paranoia-level" /tmp/crs-phase6a/rules/REQUEST-{913-SCANNER-DETECTION,932-APPLICATION-ATTACK-RCE,941-APPLICATION-ATTACK-XSS,942-APPLICATION-ATTACK-SQLI}.conf`, and a non-checked-in Python/PyYAML counter over every YAML test and first-stage request surface. The resulting counts are recorded in section 4; no production module was imported or changed by that counter.

For inventory, raw target/query, User-Agent and Referer are direct; Cookie or arbitrary-header-only is partial; body-only is out of scope. The neutral adapter preserves raw target/query, UA, Referer, Host and Content-Type but not Cookie or arbitrary headers, and creates status 200, zero-byte, zero-time rows. It never copies CRS blocking 403.

## 4. Source inventory and PL policy

| Family | YAML/rule IDs | tests | expect | no-expect | single/multi | direct | partial | OOS body | PL1 tests (positive/negative; direct positive) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 932 RCE | 48/48 | 1,019 | 718 | 301 | 1,019/0 | 581 | 86 | 352 | 561 (398/163; 253) |
| 941 XSS | 33/33 | 263 | 209 | 54 | 263/0 | 137 | 12 | 114 | 242 (188/54; 84) |
| 942 SQLi | 60/60 | 1,032 | 869 | 163 | 1,032/0 | 222 | 23 | 787 | 373 (322/51; 96) |
| 913 scanner | 1/1 | 7 | 5 | 2 | 7/0 | 7 | 0 | 0 | 7 (5/2; 5) |

Body-only is 34.5%, 43.3%, and 76.3% of full 932/941/942 inventory. Partial cookie/custom-header surface is 8.4%, 4.6%, and 2.2%. These are observability counts, not automatic project-positive counts.

| Family | PL1 | PL2 | PL3 | PL4 | Selection |
| --- | ---: | ---: | ---: | ---: | --- |
| 932 | 561 | 337 | 121 | 0 | PL1 primary; PL2/3 boundary-only |
| 941 | 242 | 21 | 0 | 0 | PL1 primary |
| 942 | 373 | 588 | 54 | 17 | PL1 primary; prevent PL2 volume imbalance |
| 913 | 7 | 0 | 0 | 0 | policy study only |

The reviewed file ranges are 932120–932390 (48), 941100–941400 (33), 942100–942560 (60), and 913100. A future inventory report must reproduce this table per rule/file. The review excluded all body-only cases from main score and did not infer project semantics merely because a direct CRS rule matched.

## 5. Observability and annotation policy

Each annotation must include source family/rule/test, source expectation, method, surface, observability, project ground truth, candidate_expected, classification policy, allowed/forbidden verdicts, mapping contract, encoding tier, and control type.

Use existing direct/partial/out_of_scope plus exact/compatible_set/forbidden_only/not_scored. Never move body/XML/multipart into query text. Cookie remains partial unless canonical project logging independently changes. UA/Referer payloads are direct; arbitrary headers are not.

Current Prepare has structured SQLi, XSS, CMDi/traversal patterns, decoded variants and special-character scoring. That is only an anticipated coverage aid. Candidate expectation follows reviewed project semantics; failure to select is a benchmark miss.

## 6. Taxonomy boundaries

### 6.1 932 RCE to CMDi

932 is RCE by CRS name but the project lacks generic suspicious_rce. Exact suspicious_command_injection requires a shell boundary plus command semantics: semicolon, pipe, double-ampersand, command substitution/backticks, shell invocation, or equivalent Windows chaining.

Clear Tier-1 examples are semicolon iwr, dollar-parenthesis cmd, time sh -c whoami, semicolon ps/who/mshta, and image.jpg semicolon dsmod. Framework/expression/serialized exploits, Log4j payloads, bare command words/binaries and body-only RCE remain compatible/boundary, inconclusive, out-of-project-taxonomy, partial or OOS. A bare cat /etc/passwd, whoami or curl without boundary is command-looking negative/boundary.

### 6.2 941 XSS

Exact XSS is direct execution-oriented syntax: script tag including source-preserved encoding/entity form, SVG onload, event assignment in injection context, or JavaScript URI/style execution. Logs do not prove reflection, persistence, browser execution, or cookie theft.

Bare location text, HTML-ish/base64 text, tag words, normal HTTP CSS URLs and event-looking words without executable construction are controls. This preserves the current external-navigation false-positive boundary.

### 6.3 942 SQLi and SQLi/CMDi

Exact SQLi requires injection grammar: UNION SELECT, quote/boolean tautology, comment/query structure, stacked DML/DDL, time/blind syntax, schema/query construction, or clear SQL-specific evasion. A database word, function, select, quote, or identifier alone is not enough.

For xp_cmdshell/exec/system/semicolon, choose by observed grammar. Semicolon INSERT, UNION SELECT and WAITFOR are SQLi and forbid CMDi in strict cases; a shell boundary leading to OS command is CMDi. Genuine dual semantics goes to compatible/boundary, never a forced strict row.

### 6.4 Traversal/file and scanner

Reuse frozen 930 annotations by reference. There are nine direct exact traversal cases but one direct exact file-disclosure case, 930120.2. Broad 930120 resources stay compatible/boundary; do not promote them to balance a chart. 933 is deferred, not assumed file disclosure.

913100 is PL1 known scanner UA. UA is observable but current Stage1 policy treats it as identification helper, not sufficient attack evidence. Recommend separate scanner-identification lane; do not put suspicious_scan in primary attack matrix.

## 7. Tiers and controls

| Tier | Use |
| --- | --- |
| 1 | direct, clear exact project class; strict core |
| 2 | source-preserved encoded/evasion variant; robustness lane |
| 3 | taxonomy/boundary ambiguity; compatible/policy lane |
| 4 | project-negative lookalike |
| excluded | partial/OOS or unsupported taxonomy |

Include plain plus source-preserved URL/transformed/case-whitespace/family evasion where available. Do not normalize away an encoded gap. Project negatives use project_negative plus forbidden_only, never forced benign_normal. Cross-family controls are the other positive rows: a SQLi request is expected SQLi while forbidden to XSS/CMDi/traversal, not benign.

## 8. Proposed exact pool and controls

These are selected design candidates, not manifest entries. All listed new positives are PL1 direct expect cases. Q means raw target/query.

| IDs | CRS rule | surface | project policy | tier/control | review reason |
| --- | --- | --- | --- | --- | --- |
| 932125.1/.2 | 932125 | GET Q | exact CMDi | T1 positive | semicolon iwr/iwmi |
| 932130.1/.18/.26 | 932130 | GET Q | exact CMDi | T1/T2 positive | substitutions and nested substitution |
| 932230.31/.34/.36 | 932230 | GET Q | exact CMDi | T1/T2 positive | sh -c, encoded shell, && |
| 932340.1/.21; 932370.3; 932380.21 | 932340/370/380 | GET Q | exact CMDi | T1 positive | semicolon ps/who/mshta/dsmod |
| 932130.10; 932230.30/.47; 932340.19; 932370.2; 932380.5 | 932 | GET Q | project-negative forbidden-only | T4 CMDi negative | bracket/search/time/bare-resource lookalikes |
| 941100.1/.8 | 941100 | GET Q | exact XSS | T1/T2 positive | script/XML and best-fit encoded script |
| 941110.2/.3/.5 | 941110 | GET Q, UA/R | exact XSS | T1/T2 positive | script, entity header, path XSS |
| 941120.6; 941140.5/.8; 941160.1; 941170.3; 941390.2; 941400.1 | 941 | GET Q | exact XSS | T1/T2 positive | SVG/event/JS URI/JS execution |
| 941120.3/.9; 941140.11/.12/.14; 941180.7 | 941 | GET Q | project-negative forbidden-only | T4 XSS negative | short event/base64/benign CSS/JS text |
| 941120.11 | 941 | POST body | not-scored | excluded OOS | pinned-source recheck: decisive PayPal verify_sign is body-only, not a direct negative |
| 942160.1/.10; 942170.1 | 942160/170 | GET Q/path | exact SQLi | T1 positive | sleep/blind and benchmark query |
| 942270.1; 942280.1/.4; 942320.6 | 942270/280/320 | GET Q, UA | exact SQLi | T1/T2 positive | union/time/quote boolean |
| 942350.1/.6/.7; 942500.1/.3 | 942350/500 | GET Q | exact SQLi; CMDi forbidden | T1/T2 positive | stacked SQL, comments/optimizer |
| 942170.3; 942230.3/.5/.8; 942350.2; 942550.38/.43/.44 | 942 | GET Q/path | project-negative forbidden-only | T4 SQLi negative | ordinary vocabulary/operator text |
| 930100.2/.3, 930110.2/.8/.9/.12, 930120.1/.3/.15 | frozen 930 | direct Q/path | exact traversal | T1/T2 positive | existing approved annotations |
| 930120.2 | frozen 930 | direct Q | exact file disclosure | T1 boundary | one clean support case |

Support is CMDi 12, XSS 12, SQLi 12, traversal 9, file disclosure 1. Named direct negatives are CMDi 6, XSS 6, SQLi 8 plus frozen 930 negatives; 941120.11 is retained as an approved body-only not-scored provenance record. Full per-family benchmark means all direct cases approved by case-level review, not every direct CRS positive.

## 9. Balanced suite

| Class | exact | compatible/boundary | named negatives | balanced target |
| --- | ---: | --- | ---: | --- |
| traversal | 9 | 930 resource cases | 8 | 9 |
| file disclosure | 1 | file/scan and CMDi/file/scan 930 cases | boundary | no macro row |
| SQLi | 12 | further direct PL1 review | 8 | 9 |
| XSS | 12 | further direct PL1 review; one OOS provenance record | 6 | 9 |
| CMDi | 12 | broad RCE/command-word Tier 3 | 6 | 9 |

Use a deterministic 36-case core: nine each traversal, SQLi, XSS and CMDi. Keep a ten-case path/file boundary addendum (nine traversal plus one file). The three unselected candidates per new class are a fixed Tier-2 reserve. An expanded chart may show file disclosure n=1 but must label it unsupported and exclude it from macro metrics.

## 10. Family manifest and source architecture

Choose family manifests plus suite:

~~~text
benchmarks/manifests/
  owasp_crs_path_file_access.v1.json  # frozen
  owasp_crs_cmdi.v1.json
  owasp_crs_xss.v1.json
  owasp_crs_sqli.v1.json
benchmarks/suites/owasp_crs_multi_family.v1.json
~~~

The suite references component manifests and explicit IDs; it never duplicates frozen 930 annotations. Current source verifier/loader is deliberately fixed to exactly three root 930 YAML files and fixed benchmark/rule patterns. Do not append new files or metadata to that root. Preserve it and add an independently verified bundle:

~~~text
benchmarks/sources/owasp_crs/<revision>/              # existing 930 untouched
benchmarks/sources/owasp_crs/<revision>/multi_family/
  SOURCE.json  LICENSE  932/*.yaml  941/*.yaml  942/*.yaml
~~~

New SOURCE.json records repository, revision, license, retrieval date, relative/upstream path, rule ID, raw SHA-256 and source test count per vendored YAML. Vendor only reviewed YAMLs. New generic loader verifies this bundle; legacy 930 verification stays unchanged. No network at benchmark runtime.

## 11. Mapping policy

Mapping is classification-gated: required IDs must exist, forbidden IDs must not, extra semantically valid IDs are allowed.

| Compatible actual class | required IDs | current relation |
| --- | --- | --- |
| traversal | A01:2025, CWE-22, WSTG-ATHZ-01 | direct/direct/direct |
| SQLi | A05:2025, CWE-89, WSTG-INPV-05 | direct/direct/direct |
| XSS | A05:2025, CWE-79, WSTG-INPV-01 | direct/direct/related |
| CMDi | A05:2025, CWE-78, WSTG-INPV-12 | direct/direct/direct |
| file disclosure | existing case-specific branch | traversal, PHP-wrapper, or direct-sensitive branch |

Mapping consistency by class denominator is direct scored + selected + completed + classification-compatible. Wrong class is not_scored_due_to_classification, not a mapping failure.

## 12. Matrices and metrics

Stage1-conditioned matrix: strict exact expected rows and actual Stage1 verdict columns; denominator direct/scored/selected/completed. It excludes NOT_SELECTED and STAGE1_ERROR.

End-to-end matrix: same exact rows but all direct scored attack positives, adding NOT_SELECTED for Prepare misses and STAGE1_ERROR for incomplete calls. This distinguishes Prepare omission from an off-diagonal Stage1 error.

Compatible sets are outside strict matrices and use compatibility/boundary results. Negatives retain suppression and forbidden-verdict metrics.

| Metric | Denominator |
| --- | --- |
| candidate recall by class/macro | direct scored attack positives |
| Stage1 compatibility | selected, completed direct positives |
| E2E compatibility | all direct scored positives |
| negative suppression/pass | direct project negatives |
| cross-family confusion | strict-core off-class completed verdicts / strict-core completed |
| mapping consistency | class-compatible completed cases |

Calculate per-class precision/recall/F1 and macro values only on fixed four-class exact core, with selected/completed disclosure and separate E2E pseudo-column view. Do not headline micro accuracy or treat curated composition as prevalence. Reuse existing case-level results; add per_class, support counts, exact_core_metrics, compatibility_metrics and stable-label keyed matrix aggregates.

## 13. Isolation, safety and LLM policy

Regression must prove per-case Prepare isolation, no cross-family contamination, no metadata leak to Stage1, no body-to-query relocation, UA/Referer direct behavior, Cookie/custom-header limitation, neutral response values, unique suite resolution and source-drift failure.

Logs never prove DB execution/data extraction, reflection/browser execution/cookie theft, shell/process execution/compromise, file read/access bypass, or vulnerability. Status 200 is not success evidence.

After implementation: controlled fixture, then one complete live run, then review. Repeat three runs only for observed confusion, boundary instability, or a stability publication claim. Never prompt-tune against benchmark examples; use general semantic fixes with before/after comparison.

## 14. Future datasets, phases and wording

CRS is curated semantic regression for family separation/boundary/evasion/mapping. CSIC 2010 remains broad HTTP candidate-suppression/false-positive evaluation. ECML/PKDD 2007 stays auxiliary multi-class/context evaluation. Preserve historical Phase 5C CSIC and 5D ECML; call this Phase 6A and implementation 6B.

| Phase | Deliverable |
| --- | --- |
| 6B-1 | reviewed YAML vendor, generic multifamily loader/integrity, family manifests |
| 6B-2 | isolated neutral Apache multi-family Prepare evaluator |
| 6B-3 | controlled Stage1 evaluator, two matrices, mapping aggregates |
| 6B-4 | single complete live baseline |
| 6B-5 | conditional repeated stability |

Safe wording: “On an externally sourced, logs-only eligible OWASP CRS benchmark, the classifier separated selected SQLi/XSS/CMDi/traversal patterns with X/Y compatibility.” Do not claim OWASP attacks detected, attacks blocked, or vulnerabilities detected.

## 15. Required-question answers and scope

1. 932/941/942 have 1,019/263/1,032 tests and 48/33/60 YAML/rule IDs.
2. PL1 direct positives are 253/84/96; reviewed usable exact pools are 12/12/12.
3. Body-only rates are 34.5%/43.3%/76.3%; partial rates 8.4%/4.6%/2.2%.
4. Exact CMDi, XSS and SQLi subsets are the named 12-case groups in section 8.
5. Credible direct controls are 6 CMDi, 6 XSS, 8 SQLi plus frozen 930 controls; 941120.11 is body-only and not scored.
6. File disclosure is insufficient: one clean exact support case.
7. 913 is separate scanner policy lane.
8. Family manifests plus suite is recommended.
9. Balanced exact core is 36 cases, nine times four.
10. Matrix 1 is selected/completed Stage1; matrix 2 adds Prepare misses/errors.
11. Compatible cases are compatibility-only, not strict rows.
12. P/R/F1 is fixed-core and not prevalence-weighted.
13. Mapping is classification-gated and class-aware.
14. Prepare miss is NOT_SELECTED; classifier confusion is off-diagonal.
15. Encoded gaps remain raw observable gaps.
16. Taxonomy mismatches become boundary/compatible/inconclusive/OOS/excluded.
17. Repeats require observed instability/confusion or a stability claim.
18. Smallest next unit is 6B-1.

Generated document: this file. Not implemented: vendoring, loaders/schemas, manifests/suite, evaluator, fixtures/live execution, matrices/tests, mapping, Prepare, Stage1, DB, or model tuning. No commit.
