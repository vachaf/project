# Phase 6C-2 — CSIC 2010 Apache-Observable Projection & Isolated Prepare Baseline Review

## 1. Status and frozen provenance

**Status: complete.  6C-3 decision: GO.**

| Item | Value |
| --- | --- |
| Git HEAD | `faf5922afc19a66d05e40d477c43ca928347ec01` |
| Source manifest | `benchmarks/manifests/csic2010_source.v1.json` (`csic2010_source_manifest.v1`) |
| Prepare entry point | production `src.prepare_llm_input.build_outputs()` |
| Evaluation mode | `production_prepare_only` |
| Isolation | one parsed request → one projected security row → one `build_outputs()` call |
| Source ordering | not interpreted as user/session/scan/repeat sequence |
| Stage1/Stage2/LLM/OpenAI calls | 0 |

Frozen local source bytes:

| File | SHA-256 |
| --- | --- |
| `normalTrafficTraining.txt` | `d51de812d9201ef2b173b6ae3e3e740c309047ac85545c06c51d6fb1ddbc1e63` |
| `normalTrafficTest.txt` | `f05dfc312d5d14fd1ed8371de27a9e4deab3dc09265f5d7f9df2643df8385089` |
| `anomalousTrafficTest.txt` | `12fa4f0d496ceb859bb2652abf7f0f0ed8c59e1d9ce501b8a9a0ef38a625c046` |

These are selected-local-mirror consistency locks, not CSIC-issued checksums.

## 2. Projection contract and observability loss

The parser retains full source request fidelity, but this phase projects only fields observable in the current Apache security-row contract:

```text
preserved: method, protocol, raw request target, URI/query split, Host,
           User-Agent, Referer if present, request Content-Type/Length metadata,
           Cookie/Authorization presence
excluded: POST/multipart body, Cookie values, Authorization values,
          arbitrary unlogged headers
neutral:  documentation IP, fixed log time, status=200, bytes=0,
          empty response content type, zero timing, no error linkage
```

`raw_request` is request-line-only.  No body or header is appended to it.  The neutral `200` is a projection placeholder and does not represent source response success, exploit success, file access, database execution, browser execution, or command execution.

Projection loss accounting:

| Source-only field/loss | Count |
| --- | ---: |
| body omitted | 25,977 |
| Cookie value omitted | 97,065 |
| Authorization value omitted | 0 |
| unlogged arbitrary header present/omitted | 97,065 |

No Referer was synthesized.  PUT was preserved rather than coerced to GET/POST.

## 3. Corpus and isolation accounting

```text
parsed source requests:  97,065
projected rows:          97,065
Prepare evaluations:     97,065
evaluation failures:     0
complete:                true
```

The compact local index stores only source file/index/hash, source label, method, body-presence flag, projection-loss booleans, selected/score/verdict/reason/filter fields, and error type.  It contains no raw request, raw target, query text, body, Cookie value, Authorization value, or arbitrary header value.

## 4. Source-label selectivity baseline

| Group | Total | Selected | Suppressed | Candidate rate |
| --- | ---: | ---: | ---: | ---: |
| normal training | 36,000 | 1 | 35,999 | 0.00278% |
| normal test | 36,000 | 1 | 35,999 | 0.00278% |
| source_normal | 72,000 | 2 | 71,998 | 0.00278% |
| source_anomalous | 25,065 | 2,148 | 22,917 | 8.56972% |
| overall | 97,065 | 2,150 | 94,915 | 2.21501% |

```text
source-normal suppression rate:    99.99722%
source-anomalous suppression rate: 91.43028%
candidate anomaly proportion:      99.90698%
selection-rate ratio:              3085.09874
```

Formulas:

```text
candidate anomaly proportion = selected source_anomalous / all selected
selection-rate ratio = P(selected | source_anomalous) / P(selected | source_normal)
```

These are **source-label selectivity/enrichment metrics, not attack-detection accuracy metrics**.  `source_normal` is not proven benign; `source_anomalous` is not automatically project attack-positive.  Consequently, none of these values is recall, TPR, FPR, specificity, precision, or a true/false-positive measurement.

The identical normal-training and normal-test rates are a source-normal subset consistency observation, not an ML train/test performance result.

## 5. Method and body-presence breakdown

| Source label | Method | Total | Selected | Candidate rate |
| --- | --- | ---: | ---: | ---: |
| source_normal | GET | 56,000 | 2 | 0.00357% |
| source_normal | POST | 16,000 | 0 | 0.00000% |
| source_anomalous | GET | 15,088 | 2,148 | 14.23648% |
| source_anomalous | POST | 9,580 | 0 | 0.00000% |
| source_anomalous | PUT | 397 | 0 | 0.00000% |

| Source label | Body present | Total | Selected | Candidate rate |
| --- | --- | ---: | ---: | ---: |
| source_normal | no | 56,000 | 2 | 0.00357% |
| source_normal | yes | 16,000 | 0 | 0.00000% |
| source_anomalous | no | 15,088 | 2,148 | 14.23648% |
| source_anomalous | yes | 9,977 | 0 | 0.00000% |

The zero selected count for body-bearing requests is an observable-projection result.  It does **not** establish that those source-anomalous requests are body-only attacks, nor that any suppressed request is harmless.  That distinction belongs to 6C-3 review.

## 6. Prepare distributions

Selected verdict-hint distribution:

| Source label | Verdict hint | Count |
| --- | --- | ---: |
| source_anomalous | `sqli` | 833 |
| source_anomalous | `xss` | 752 |
| source_anomalous | `suspicious` | 563 |
| source_normal | `suspicious` | 2 |

Top selected reason hints (source-anomalous):

| Hint | Count |
| --- | ---: |
| `long_query(+1)` | 1,909 |
| `very_long_query(+1)` | 1,256 |
| `special_char_ratio_high(+1)` | 966 |
| `encoding:url_encoded_payload` | 946 |
| `sqli:sql_comment(+2)` | 917 |
| `sqli:quote_termination(+4)` | 829 |
| `xss:alert_call(+3)` | 579 |
| `xss:script_tag(+5)` | 575 |
| `encoding:double_decoded_payload` | 572 |
| `sqli:waitfor_delay(+5)` | 552 |

Source-anomalous selected score counts: score 4=298, 5=190, 6=75, 8=83, 9=310, 10=339, 11=119, 12=117, 13=319, 14=210, 15=88.  Source-normal selected requests both had score 6.  Scores are Prepare internals, not severity.

Suppression filtered-reason distribution:

| Source label | Filtered reason | Count |
| --- | --- | ---: |
| source_normal | `known_baseline_like` | 71,998 |
| source_anomalous | `known_baseline_like` | 22,914 |
| source_anomalous | `low_signal_request` | 3 |

The selected rows have no filtered reason.  Full reason-hint, score, and filter distributions are in the local baseline artifact; raw corpus text is not duplicated there.

## 7. Review pools and 6C-3 feasibility

```text
selected source_normal:       2
selected source_anomalous:    2,148
suppressed source_anomalous: 22,917
```

This provides a feasible stratified 6C-3 pool.  Select by stable identity/hash and strata including selected/suppressed status, method (including PUT), body presence, verdict hint, score bucket, and reason-hint family.  The two selected source-normal identities are review candidates, not false-positive cases.  The 22,917 suppressed source-anomalous identities are review candidates, not missed-attack cases.

6C-3 should create reviewed project-semantic annotations only after inspecting source evidence under the logs-only boundary.  It may create strict Traversal/CMDi/XSS/SQLi subsets only where review justifies them.  It must not turn corpus-level source labels or automated token matches into source-ground-truth families.

## 8. Determinism and artifacts

The required second local pass used the same frozen source/cache and production revision.  It was a reproducibility check, not a performance repeat.

```text
pass 1 request-index SHA-256: cf1311cee88a207798b4861b7f9e99757950c8ff62c2cc8215a79d056915cbda
pass 2 request-index SHA-256: cf1311cee88a207798b4861b7f9e99757950c8ff62c2cc8215a79d056915cbda
index equality: pass
aggregate equality excluding artifact paths: pass
```

| Artifact | SHA-256 |
| --- | --- |
| `/tmp/csic2010_prepare_baseline.json` | `34542956542ef2f4d1e435caa7f3aea2ccff75d29456220ca34ef3c4e2a76de9` |
| `/tmp/csic2010_prepare_request_index.jsonl` | `cf1311cee88a207798b4861b7f9e99757950c8ff62c2cc8215a79d056915cbda` |
| `/tmp/csic2010_prepare_baseline_repeat.json` | `c88e8498ac75ebf1b2934892973ab7bc326bd8c1ef2eb82e7a108b655aa9c0dd` |
| `/tmp/csic2010_prepare_request_index_repeat.jsonl` | `cf1311cee88a207798b4861b7f9e99757950c8ff62c2cc8215a79d056915cbda` |

Baseline JSON differs between passes only because each names its own index artifact path; normalized aggregates are equal.

## 9. Validation and impact

```text
py_compile: pass
focused CSIC parser/projection tests: pass
source manifest JSON parse and contract validation: pass
raw cache ignored and absent from Git index: pass
```

No production Prepare, Stage1 prompt/classifier, mapper, CRS suite, source manifest semantics, or LLM configuration changed.  This benchmark merely calls the existing production `build_outputs()` in isolated single-row mode.
