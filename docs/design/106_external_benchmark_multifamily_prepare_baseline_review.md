# Phase 6B-2R — Multi-family Prepare baseline root-cause review

## 1. Review status and conclusion

- Review date: 2026-09-04; checkout: `e89de63`.
- Input artifact: `/tmp/owasp_crs_multifamily_prepare_baseline.json`, SHA-256 `cf07ea945018a5b28a34764be49bb9cd06854fa7899c1c1df020c9708b053500` (verified).
- Source: pinned OWASP CRS `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`; source YAML, reviewed manifests, suite, adapter, and production Prepare were read. No network source was used.
- Scope: investigation/documentation only. No production detector, runner, schema, benchmark, suite, manifest, test, or commit was changed.

**Decision: Path B — perform a minimal 6B-2F Prepare fix, re-run this frozen baseline, then run 6B-3.** The reason is not the aggregate score: 105's current project contract explicitly includes shell chaining, shell invocation, and Windows chaining as exact command-injection semantics, while the current detector admits only a very small Unix vocabulary. The exact-core CMDi support is only `2/9`, too small to interpret a CMDi row/column of a Stage1 confusion matrix. In addition, four current candidate-selection defects are clear P1 boundaries (one generic-score CMDi negative and three XSS negatives).

No P0 semantic-correctness bug was found in this review. There are **four definite current production bugs (all A/P1)**. They are candidate-selection/false-positive-boundary bugs, not final Stage1 false positives: a selected Prepare candidate can still be corrected by Stage1.

## 2. Baseline interpretation

```text
reviewed/direct/not-scored                  93 / 83 / 10
attack-positive/project-negative            55 / 28
positive candidate recall                   27 / 55 = 49.09%
negative suppression                        24 / 28 = 85.71%

Traversal                                  9 / 19; negatives 8 / 8
CMDi                                       3 / 12; negatives 5 / 6
XSS                                        7 / 12; negatives 3 / 6
SQLi                                       8 / 12; negatives 8 / 8

balanced exact core: traversal/cmdi/xss/sqli 8/9, 2/9, 5/9, 7/9
selected exact-core cases                   22 / 36
macro candidate recall                      61.11%
```

`49.09%` is not CRS detection recall. Its denominator is the reviewed, direct, project-attack-positive requests whose observed request surface should be sent to Stage1; its numerator is only the deterministic Prepare prefilter. Conversely, an unexpected candidate is an avoidable Stage1 cost and misleading evidence opportunity, not proof that Stage1 would return an attack verdict. Specific `verdict_hint` is still stricter than candidate selection: the global threshold is 4, whereas `command_injection` and traversal require 6 and `xss`/`sqli` require 7. Thus a selected `suspicious` row can correctly support later exact Stage1 classification.

The ceiling for the current 6B-3 exact-class matrix is exactly **22 selected exact-core cases**, including only **2 CMDi**. This can expose some cross-family behavior, but cannot meaningfully compare CMDi classification quality. A practical non-score target is 4–6/9 CMDi for an exploratory row and 7–9/9 for a balanced comparison. The minimal scoped CMDi work below is expected to make 7 additional exact-core CMDi cases eligible (a 29/36 core), while keeping the benchmark label independent of detector behavior.

## 3. Method and trace conventions

The runner creates one isolated neutral `security` row per direct case: original method/target/request line, target-derived URI and query, source User-Agent/Referer/Host/Content-Type, status 200, no response body, zero duration/TTFB, no error linkage, and a deterministic documentation IP/time. It does not copy a CRS block status or decode payloads in the adapter.

For each table below, `score` for selected rows is the artifact's `candidate_score`. For a filtered row, the artifact serializes no score, so this review re-ran the same production `evaluate_row` scoring path with `min_score=0` **only as read-only diagnostic instrumentation**; the score and reason terms are unchanged, and the production threshold stays 4. All listed positive misses and all unexpected negatives have `filtered_out=true`/public filtered reason `low_signal_request` when they are not selected. There is no early socket/static/noise filter responsible for a listed miss.

`decoded` means `urllib.parse.unquote_plus` variants at depth 1 and 2. Raw and decoded target/query variants are included in `combined_target`; headers are not. Scores list only scoring terms, while context-only hints such as `xss:event_handler:onafe` are called out separately.

## 4. Current production detector inventory

### 4.1 Candidate path and normalization

| Surface or mechanism | Current behavior in production scoring | Consequence |
| --- | --- | --- |
| `combined_target` | raw request line, normalized URI, raw/normalized query, raw target, raw log, decoded query/target variants | Main SQLi/XSS/CMDi/traversal pattern surface |
| URL decoding | `unquote_plus`, maximum two passes, for query and raw target | encoded `%3B`, `%24`, `%3C`, etc. are seen |
| HTML entity decoding | `html.unescape`, only when numeric/named entity regex is present, for query/target variants | XSS entity support exists on target/query only |
| JavaScript/CSS decoding | none | `%uXXXX`, JS escapes/constructors, and CSS grammar are not normalized |
| NUL removal/canonicalization | none (a percent-decoded NUL is not removed or followed by further path canonicalization) | not CRS transform-chain equivalent |
| User-Agent/Referer | adapter preserves both fields and candidates carry them; neither joins `combined_target` or decoded variants | header-only attack text cannot score through SQLi/XSS/CMDi patterns |
| special-character score | query only; +1 at ratio >= .15, another +1 at >= .30 | can compose with a weak substantive signal; does not examine headers |
| generic context | HPP +1; length >=40 +1, >=80 another +1; error/timing/auth/UA paths as applicable | isolated suite has no status/timing/error bonus |
| final threshold | candidate at >=4 unless an earlier filter applies; family-specific hint gates as above | candidate and class hint must not be conflated |

The current Stage1 instruction further says User-Agent is a request-identification/trace aid and must not itself be attack evidence. That policy conflicts with the two suite annotations that currently call a preserved UA payload direct/exact; it is recorded as G rather than silently redefining either benchmark case.

### 4.2 `CMDI_PATTERNS` — complete inventory

All three patterns are searched against decoded `combined_target`; URL-decoded target/query variants therefore apply. They add four points each. None recognizes `&&`, shell invocation, Windows chaining, or a generic command token.

| Pattern name | Regex semantic | Recognized separators | Recognized commands | Score | Decoded variants |
| --- | --- | --- | --- | ---: | --- |
| `pipe_exec` | `\|\s*(cmd)\b` | one pipe only (a `||` text can incidentally start at its second pipe) | `whoami`, `id`, `cat`, `uname`, `ls`, `pwd` | 4 | yes |
| `semicolon_exec` | `;\s*(cmd)\b` | semicolon | `cat`, `id`, `whoami`, `uname`, `curl`, `wget`, `bash`, `sh` | 4 | yes |
| `subshell` | `$(cmd` or backtick followed by cmd | `$(` or backtick; no closing delimiter required by the regex | `id`, `whoami`, `uname`, `cat` | 4 | yes |

The allowlist suppresses bare `whoami`, `cat /etc/passwd`, and `curl ...` as desired, but it also omits exact project-supported `cmd`, `ps`, `who`, `iwr`, `iwmi`, `mshta`, and `dsmod`. It is therefore not sustainable as the *only* CMDi policy. It should remain a bounded vocabulary component (especially for separator-only one-word cases), combined with explicit shell grammar; it should not become an unbounded “any word after `;`” rule, because `;environment` is a present negative control.

### 4.3 XSS inventory and actual use

| Item | Pattern/semantic | Score effect | Actual candidate-path use |
| --- | --- | ---: | --- |
| `script_tag` / `SCRIPT_TAG_PATTERN` | `<\s*script\b` | +5 pattern | pattern scores; helper adds `xss:script_tag` only |
| `SCRIPT_TAG_CAPTURE_RE` / mixed-case helper | captures `<tag` and marks mixed-case `script` | 0 | `xss:mixed_case_script_tag` context hint / strong-structure flag only |
| `img_onerror` | `<img ... onerror=` | +5 | pattern scores |
| `svg_onload` | `<svg ... onload=` | +5 | pattern scores |
| `javascript_uri` / `JAVASCRIPT_PROTOCOL_RE` | `javascript\s*:` | +4 pattern | pattern scores; helper adds context hint |
| `event_handler` / `EVENT_HANDLER_ASSIGNMENT_RE` | `\bon\w+\s*=` / `\b(on[a-z0-9_]+)\s*=` | +3 pattern | pattern scores; helper records arbitrary event name; no tag/injection context is required |
| `alert_call` | `\balert\s*\(` | +3 | pattern scores |
| `document_cookie` / `BROWSER_DATA_ACCESS_RE` | `document.cookie`; helper also sees `localStorage`, `sessionStorage` | +4 for `document_cookie` | helper hints only beyond the pattern |
| `EXTERNAL_NAVIGATION_RE` | location/fetch/Image/beacon navigation forms | 0 | reason hint only; may combine with browser-data hint into `external_exfil_intent` |
| `EXTERNAL_URL_RE` | HTTP(S) URL | 0 | no direct score; participates only in browser-data plus external-URL exfil-intent hint |
| `XSS_QUOTE_BREAKOUT_PATTERN` | quote followed by `>`, `<`, or `on...=` | 0 | used for attack-structure / educational-search FP review, not direct score |
| `XSS_TAG_INJECTION_PATTERN` | script/img/svg/iframe/body/a opening tag | 0 | same: structure check, not direct score |
| educational XSS search context | natural-language search term plus XSS keyword | subtracts 4 only when XSS patterns have no strong structure | false-positive/search demotion; not a positive detector |

This distinction explains the XSS results: rich helper hints do not rescue a miss without an `XSS_PATTERNS` score (or other score). The broad `event_handler`, raw `javascript:` and bare `document.cookie` scoring patterns can each select a row without a tag or executable injection construction.

### 4.4 SQLi inventory and relative stability

| Pattern | Regex semantic | Score |
| --- | --- | ---: |
| `union_select` | word-bounded `union` followed by whitespace and `select` | 5 |
| `or_true` | optional quote then `or a=a` word/quoted operands | 4 |
| `and_true` | optional quote then `and a=a` word/quoted operands | 3 |
| `sql_comment` | `--`, `#`, or `/*` | 2 |
| `sleep_func`, `benchmark_func` | word-bounded function then `(` | 5 each |
| `waitfor_delay` | word-bounded `waitfor delay` | 5 |
| `information_schema` | word-bounded schema name | 5 |
| `select_from` | `select` followed later by `from` | 4 |
| `drop_table`, `insert_into`, `update_set`, `delete_from` | bounded DDL/DML keyword pairs with required whitespace | 5, 4, 4, 4 |
| `quote_termination` | quote or `%27` then `or`, `and`, `union`, `;`, or comment | 4 |

`matches_sqli_pattern()` treats `sql_comment` specially by first removing HTML entity strings so entity syntax does not supply a spurious semicolon/comment match; all other patterns search the same `combined_target` directly.

Additional SQL structure helpers are not an independent broad detector: `SQLI_BOOLEAN_CONDITION_PATTERN`, the exact-true variant, quote/parenthesis termination, comment, xclose, union-column, schema-access and `from users` flags chiefly add reason hints or suppress educational-search false positives. The SQLi relative result (8/12) follows from explicit coverage of UNION/SELECT, quotes/comments, `sleep(`, `benchmark(`, DML, and double-decoded SQLi—not from full CRS transform emulation. Only two selected SQLi rows meet the stricter score-7 `sqli` hint gate; the other selected rows rightly remain `suspicious` candidates.

## 5. CMDi: grammar, selected comparison, and all cases

105 §6.1 is decisive current project contract: exact `suspicious_command_injection` requires shell boundary plus command semantics, expressly including semicolon, pipe, **double-ampersand**, command substitution/backticks, shell invocation, or equivalent Windows chaining. It names semicolon `iwr`/`iwmi`, `$(cmd)`, `time sh -c whoami`, semicolon `ps`/`who`/`mshta`, and `image.jpg;dsmod` as clear Tier-1 examples. Therefore `&&` is in scope, and Windows/PowerShell CMDi is in scope. Current code has a coverage gap; absence of a current regex does not make these cases unsupported.

### 5.1 Selected positive comparison

| Case | Shell boundary | Command | Encoding/evasion | Current matched pattern | Score | Selected |
| --- | --- | --- | --- | --- | ---: | --- |
| `932130/18` | nested `$(` | `cat` | URL encoded | `subshell` | 6 | yes, `command_injection` |
| `932130/26` | `$(` | `whoami` | URL encoded/nested empty subshell | `subshell` | 5 | yes, `suspicious` |
| `932230/34` | `;` | `sh -c whoami` | encoded `;`, shell variable noise | `semicolon_exec` (`sh`) | 5 | yes, `suspicious` |

The exact-core numerator is only the first and third rows. The third selected CMDi positive is reserve case `932130/26`.

### 5.2 CMDi grammar matrix — all 12 positives

`Y` means an observed source semantic feature, not necessarily a current regex match. “Other” is a non-current-allowlist command.

| Case | `;` | `|` | `||` | `&&` | `$()` | backtick | shell `-c` | Windows chain | PowerShell | known Unix | known Windows | other | encoding/evasion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `932125/1` | Y | — | — | — | — | — | — | Y | Y | — | `iwr` | — | URL |
| `932125/2` | Y | — | — | — | — | — | — | Y | Y | — | `iwmi` | — | URL |
| `932130/1` | — | — | — | — | Y | — | — | Y | — | — | `cmd` | — | literal substitution |
| `932130/18` | — | — | — | — | Y | — | — | — | — | `cat` | — | — | nested URL |
| `932130/26` | — | — | — | — | Y | — | — | — | — | `whoami` | — | — | nested empty substitution/URL |
| `932230/31` | — | — | — | — | — | — | Y | — | — | `sh`, `whoami` | — | `time` carrier | plus-to-space |
| `932230/34` | Y | — | — | — | — | — | Y | — | — | `sh`, `whoami` | — | — | URL, `$XX` |
| `932230/36` | — | — | — | Y | — | — | shell grouping | — | — | `sh` | — | — | URL/redirection |
| `932340/1` | Y | — | — | — | — | — | — | — | — | `ps` | — | — | URL |
| `932340/21` | Y | — | — | — | — | — | — | — | — | `who` | — | — | literal |
| `932370/3` | Y | — | — | — | — | — | — | Y | — | — | `mshta` | — | URL |
| `932380/21` | Y | — | — | — | — | — | — | Y | — | — | `dsmod` | — | URL |

### 5.3 Required CMDi case table — 12 positive and 6 negative

Scores are final isolated-row scores. `—/0` means no score term and a threshold-filtered row.

| Case | Expected | Raw semantic | Shell boundary | Command token | Encoding | Matched current pattern | Score | Candidate | Root cause | Priority | Recommended action |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `932125/1` | positive | `cmd=;iwr http://…ps1` | `;` | iwr | URL | none | 1 | no | B vocabulary | P2 | bounded Windows/PS vocabulary |
| `932125/2` | positive | `cmd=;iwmi -class … Create …` | `;` | iwmi | URL | none | 1 | no | B vocabulary | P2 | same |
| `932130/1` | positive | `932130-1=$(cmd)` | `$()` | cmd | literal | none | 1 | no | B substitution vocabulary | P2 | substitution grammar + bounded cmd |
| `932130/18` | positive | `echo $(echo $(cat /etc/passwd))` | `$()` | cat | URL | `subshell` | 6 | yes | pass | — | keep |
| `932130/26` | positive | `$(whoami$())` | `$()` | whoami | URL | `subshell` | 5 | yes | pass | — | keep |
| `932230/31` | positive | `time sh -c whoami` | shell invocation | sh/whoami | plus-space | none | 0 | no | B grammar | P2 | recognize bounded shell `-c` form |
| `932230/34` | positive | `a; sh$XX -c whoami` | `;`, shell | sh/whoami | URL/$XX | `semicolon_exec` | 5 | yes | pass | — | keep |
| `932230/36` | positive | `d=/dev&&(sh)0>$d/tcp/…` | `&&` | sh | URL/redirection | none | 2 | no | B grammar | P2 | add `&&`/grouped-shell grammar |
| `932340/1` | positive | `arg=;ps` | `;` | ps | URL | none | 1 | no | B vocabulary | P2 | bounded Unix utility vocabulary |
| `932340/21` | positive | `x=;who` | `;` | who | literal | none | 1 | no | B vocabulary | P2 | same |
| `932370/3` | positive | `cmd=; mshta http://…` | `;` | mshta | URL | none | 0 | no | B Windows vocabulary | P2 | bounded Windows vocabulary |
| `932380/21` | positive | `view=image.jpg;dsmod user` | `;` | dsmod | URL | none | 0 | no | B Windows vocabulary | P2 | bounded Windows vocabulary |
| `932130/10` | negative | `hello [text in brackets]` | none | none | URL | none | 0 | no | pass | — | retain |
| `932230/30` | negative | `time warner` | none | word lookalike | plus-space | none | 0 | no | pass | — | retain |
| `932230/47` | negative | `args=;environment` | `;` | non-command word | literal | none | 0 | no | pass | — | regression: reject generic-token rule |
| `932340/19` | negative | search `w=hello world` | none | none | plus-space | none | 0 | no | pass | — | retain |
| `932370/2` | negative | bare `regedit` | none | Windows word | URL | none | 0 | no | pass | — | retain bare-command boundary |
| `932380/5` | negative | duplicated `e/ex/page/sort` in two embedded URLs | none | none | URL | **none** | 4 | **yes** | A generic score gate | P1 | require substantive signal before generic-score candidate |

### 5.4 Nine miss traces and cause count

All nine use an observable target/query surface, all URL-decoded variants shown in the raw semantic column where applicable are present, none matches any CMDI pattern, and none gets a family/context score. Final terms are: `932125/1` +long query; `/2` +long query; `932130/1` +special ratio; `932230/31` 0; `/36` +long +special; `932340/1` +special; `/21` +special; `932370/3` 0; `932380/21` 0. Each is filtered only because final score is below 4.

Primary cause count for the nine misses is **B=9 (P2=9)**: separator/substitution/shell grammar is missing in two cases (`932230/31`, `/36`); separator/substitution is present but the command vocabulary is too narrow in seven (`932125/1`, `/2`, `932130/1`, `932340/1`, `/21`, `932370/3`, `932380/21`). There are **zero A, C, D, E, F, or G** CMDi positive misses. In particular, none is an adapter issue, and none should be relabeled just because today’s regex lacks it.

`932380/5` is not a CMDi hit: its score is exactly `hpp:duplicate_param_names(+1)` + `long_query(+1)` + `very_long_query(+1)` + `special_char_ratio_high(+1)`. It has no `cmdi:*` reason. This is a candidate selectivity bug (A/P1), not a Stage1 CMDi false-positive conclusion and not a command-regex false positive.

## 6. XSS: positive misses, negative boundary, and all cases

### 6.1 Positive miss traces

| Case | Raw target/header | Decoded/evidence actually available | Current result | Primary cause |
| --- | --- | --- | --- | --- |
| `941100/8` | `/?id=%u00abscript%u00bballert(1)%u00ab/script%u00bb` | `%uXXXX` remains literal; no best-fit `%u00ab/%u00bb` to angle-bracket transform | score 2 (length + special), no XSS pattern | B/P3 nonstandard Unicode/best-fit normalization |
| `941110/3` | target `/get`; UA `&#60;script+&#62;alert(1);&#60;/script&#62;=value` | UA is preserved byte-for-byte by source/adapter, but never enters query/target variants or `combined_target`; entity helper is target/query only | score 0, no XSS pattern | G/P2 header-evidence policy conflict |
| `941140/8` | `STYLE=X:URL(JAVASCRIPT` | URL decoding yields same incomplete CSS/JS token; no `javascript:` colon | score 0 | B/P3 CSS legacy/evasion grammar |
| `941390/2` | `x";setTimeout(name, 1)//` | URL decoding yields JS method call, but no `setTimeout`/quote-breakout scoring pattern | score 1 special | B/P3 JS execution grammar |
| `941400/1` | `[].sort.call\`${alert}1337\`` | URL decoding yields tagged-template/call form; no direct `alert(` | score 0 | B/P3 JS grammar |

The first, fourth and fifth are not ordinary URL-decoding misses. The implementation already does percent decode; they require additional representation/JavaScript grammar coverage. `941140/8` is a deliberately broad legacy CSS token form and should remain P3. `941110/3` is a policy decision: 105 treats preserved UA/entity syntax as direct/exact, while current Stage1 says UA is trace aid only. The source case and adapter are faithful; the benchmark does not change in this phase.

### 6.2 Required XSS case table — 12 positive, 6 negative, 1 OOS

| Case | Expected | Surface | Execution-oriented syntax | Encoding | Current XSS matches | Score | Candidate | Root cause | Priority | Recommended action |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `941100/1` | positive | target query | script + JS URI | literal/plus | script_tag, javascript_uri | 12 | yes | pass | — | keep |
| `941100/8` | positive | target query | best-fit script/alert | `%uXXXX` | none | 2 | no | B | P3 | defer normalization expansion |
| `941110/2` | positive | target query | script + alert | plus | script_tag, alert_call | 10 | yes | pass | — | keep |
| `941110/3` | positive | User-Agent | entity script + alert | HTML entity | none | 0 | no | G | P2 | resolve header-evidence policy first |
| `941110/5` | positive | target path | closing/opening script + alert | URL | script_tag, alert_call | 8 | yes | pass | — | keep |
| `941120/6` | positive | target path | SVG `onload=alert()` | URL | svg_onload, event_handler, alert_call | 11 | yes | pass | — | keep |
| `941140/5` | positive | target query | assigned CSS `url(javascript:alert())` | URL | javascript_uri, alert_call | 8 | yes | pass | — | keep |
| `941140/8` | positive | target query | case-insensitive CSS URL token | URL | none | 0 | no | B | P3 | defer CSS grammar |
| `941160/1` | positive | target query | script + JS URI | literal/plus | script_tag, javascript_uri | 12 | yes | pass | — | keep |
| `941170/3` | positive | target query | JS URI/backslashes | URL | javascript_uri | 4 | yes | pass | — | keep |
| `941390/2` | positive | target query | quote then `setTimeout()` | URL | none | 1 | no | B | P3 | defer JS grammar |
| `941400/1` | positive | target query | tagged-template alert form | URL | none | 0 | no | B | P3 | defer JS grammar |
| `941120/3` | negative | target query | `onab=`, no executable context | URL | event_handler | 3 | no | pass | — | retain as boundary regression |
| `941120/9` | negative | target query | base64 tail decodes to `onafe=` | URL/base64 text | event_handler | 5 | **yes** | A | P1 | contextual/event-name boundary |
| `941140/11` | negative | target query | benign CSS declarations | URL | none | 0 | no | pass | — | retain |
| `941140/12` | negative | target query | CSS HTTP URL | URL | none | 1 | no | pass | — | retain |
| `941140/14` | negative | target query | bare `url(javascript:alert())`, no assignment/injection construction | URL | javascript_uri, alert_call | 8 | **yes** | A | P1 | require executable CSS/injection context |
| `941180/7` | negative | path | manual path includes `document.cookie` | literal | document_cookie | 4 | **yes** | A | P1 | require browser code/construction context |
| `941120/11` | OOS | request body form | PayPal `verify_sign` source control | body | not evaluated | — | not scored | pass | — | retain OOS; never leak body into query |

### 6.3 Unexpected-negative traces and P1 interpretation

| Case | Raw/decoded evidence | Matched/scoring signals | Final score and hint | Why this is a P1 candidate boundary |
| --- | --- | --- | --- | --- |
| `941120/9` | URL-decoded base64-like string contains `onafe=` | broad `event_handler(+3)`; context hints `xss:event_handler:onafe`; +long query, +very long query | 5, `suspicious` | arbitrary `on<word>=` in non-executable data is treated as event handler; weak signal is promoted by **two length terms**, not by special-character score |
| `941140/14` | `url(javascript:alert(1))` but no CSS property assignment/tag/quote breakout | `javascript_uri(+4)`, `alert_call(+3)`, +special ratio; JS protocol hint | 8, `xss` | protocol and alert substrings are presented as high-confidence XSS without the benchmark’s required injection/executable CSS context |
| `941180/7` | path `/get/javascript-manual/document.cookie` | `document_cookie(+4)` and browser-data hints | 4, `suspicious` | documentation/path text is enough to select although it contains no JavaScript execution construction |

So the answer is nuanced but firm: `3/6` suppression is not merely an acceptable high-recall-prefilter trade-off for these three *reviewed controls*. All three are **clear A/P1 candidate-selection bugs** under 105’s stated boundary. They are not yet three confirmed Stage1 false positives. There is a weak-signal composition issue in `941120/9`, but it is `event_handler + length + length`, not the hypothesized `event_handler + special-character` pair. The P1 remediation should tighten semantic context first; changing only threshold/scoring would leave `941140/14` (score 8) and `941180/7` (score 4 direct pattern) unresolved.

The former `bare location=` external-navigation correction is the same general lesson—context-free substring evidence in Apache text. These cases use different constants, so no existing regression should be weakened; they need paired regression cases instead.

## 7. SQLi: four misses and all cases

### 7.1 Miss traces

| Case | Raw semantic | Current matches / score | Root cause and action |
| --- | --- | --- | --- |
| `942280/1` | decoded `select pg_sleep` | none, 0 | B/P2: explicit time-function family omits `pg_sleep`; bounded time-function expansion is useful, but does not require CRS transform parity |
| `942280/4` | UA contains `waitfor delay '0:0:15' --` | none, 0 | G/P2: same UA evidence-policy conflict as XSS; adapter preserved it, production scan intentionally does not consume it |
| `942350/6` | decoded `;DROP/*test*/TABLE test;` | `sql_comment(+2)` + special +1 = 3 | B/P3: comment/evasion interrupts `drop\\s+table`; current generic comment evidence remains below threshold |
| `942500/3` | decoded `or /*+optimizer hint */ true` | `sql_comment(+2)` = 2 | B/P3: optimizer-hint/evasion grammar is not a boolean tautology or existing explicit SQL pattern |

### 7.2 Required SQLi case table — 12 positive and 8 negative

| Case | Expected | SQL grammar family | Encoding/evasion | Current SQLi matches | Score | Candidate | Root cause | Priority | Recommended action |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `942160/1` | positive | time `sleep()` | URL | sleep_func | 5 | yes | pass | — | keep |
| `942160/10` | positive | path time `sleep()` | literal | sleep_func | 5 | yes | pass | — | keep |
| `942170/1` | positive | BENCHMARK | URL/double decode observation | benchmark_func | 5 | yes | pass | — | keep |
| `942270/1` | positive | UNION SELECT FROM | URL | union_select, select_from | 9 | yes | pass | — | keep |
| `942280/1` | positive | PostgreSQL time function | URL | none | 0 | no | B | P2 | bounded `pg_sleep` coverage |
| `942280/4` | positive | SQL Server WAITFOR | User-Agent | none | 0 | no | G | P2 | resolve header policy |
| `942320/6` | positive | quote/boolean/comment | URL | sql_comment, quote_termination | 8 | yes | pass | — | keep |
| `942350/1` | positive | stacked INSERT | URL | insert_into | 4 | yes | pass | — | keep |
| `942350/6` | positive | stacked DROP TABLE | URL/comment | sql_comment | 3 | no | B | P3 | optional comment-aware DDL grammar |
| `942350/7` | positive | comment-obfuscated INSERT | URL/comment | sql_comment | 4 | yes | pass | — | keep |
| `942500/1` | positive | portability comment/evasion | URL/comment | sql_comment | 5 | yes | pass | — | keep |
| `942500/3` | positive | optimizer hint/evasion | URL/comment | sql_comment | 2 | no | B | P3 | optional optimizer/evasion grammar |
| `942170/3` | negative | ordinary “sleep well” | URL | none | 0 | no | pass | — | retain |
| `942230/3` | negative | ordinary “like” | URL | none | 0 | no | pass | — | retain |
| `942230/5` | negative | ordinary “having” | URL | none | 0 | no | pass | — | retain |
| `942230/8` | negative | ordinary “behaving” | URL | none | 0 | no | pass | — | retain |
| `942350/2` | negative | insertion word | URL | none | 0 | no | pass | — | retain |
| `942550/38` | negative | natural-language `?` | URL | none | 0 | no | pass | — | retain |
| `942550/43` | negative | orphan `<3` | URL | none | 0 | no | pass | — | retain |
| `942550/44` | negative | natural-language `->` | URL | none | 1 | no | pass | — | retain |

SQLi is relatively stable because it recognizes several bounded SQL grammars directly. The remaining misses are a narrow time function, a header-policy case, and two intentional CRS-style comment/evasion expansions. None is a demonstrated common SQL syntax correctness bug; only `pg_sleep` is high-value P2. Do not treat the lower score as a reason to mutate annotations.

## 8. Traversal, contamination, and paired boundaries

### 8.1 Frozen 930 summary

The 930 source is not re-reviewed here. The inherited current result is `9/19` positive selection and `8/8` negative suppression; exact core is `8/9`. The ten remaining positive misses retain their documented historical primary categories: `930110/12` C (transform-specific alternate syntax), `930120/4`, `/13`, `/14` B (desirable sensitive-resource coverage), `930120/5`, `/6` C (generic `/sys/class` scope), and `930120/7`, `/8`, `/9`, `/18` G (command-looking/weak metadata policy and annotation review). The earlier traversal P0/P1 work is deliberately not reopened.

### 8.2 Cross-family contamination

No current selected SQLi row matched `CMDI_PATTERNS`; current CMDi vocabulary is too narrow. This is a future regression risk, not evidence that a generic CMDi expansion is safe. In particular `942350/1` (`;INSERT`), `942350/6` (`;DROP/*…*/TABLE`), `942350/7` (comment-obfuscated `;INSERT`) and SQL-server `WAITFOR` must stay SQLi / CMDi-forbidden under 105 §6.3. A future CMDi implementation must either exclude SQL grammar/verbs from a shell-boundary branch or ensure SQL evidence has priority, with tests proving it.

Useful paired controls already in the suite are:

| Future rule boundary | positive side | negative side | Required property |
| --- | --- | --- | --- |
| CMDi semicolon | `;ps`, `;who`, `;mshta`, `;dsmod` | `;environment`, bare `regedit` | do not make a bare word or arbitrary token a command injection |
| shell invocation | `time sh -c whoami`, `&&(sh)…` | `time warner` | recognize actual shell grammar, not carrier words |
| XSS event assignment | SVG `onload=alert()` | `onab=`, base64 `onafe=` | require executable/injection context or a credible event name/context |
| XSS JS/CSS | assigned `style=…url(javascript:alert())` | bare `url(javascript:alert())` | preserve the assignment/injection boundary |
| browser data | executable script forms | `/javascript-manual/document.cookie` | do not treat a pathname word as browser code |

## 9. Adapter, observability, and manifest validation

There is **no E synthetic-adapter artifact and no F Apache/log observability mismatch** among the reviewed new-family cases. The adapter preserves each relevant request target exactly; it preserves `941110/3` User-Agent exactly as `&#60;script+&#62;alert(1);&#60;/script&#62;=value` and `942280/4` User-Agent including `waitfor delay '0:0:15' --`; it does not transform either. The product’s scorer simply does not inspect header values as attack text. `941120/11` remains correctly not-scored because its decisive `verify_sign` is body-only; no body/cookie leakage was found.

Confirmed benchmark annotation errors are **0**. The observed detector misses never justify annotation relaxation. There are, however, **2 annotation-policy reconciliation items**, `941110/3` and `942280/4` (both primary G, not D): 105 labels UA direct/exact, while Stage1 currently prohibits using UA itself as attack evidence. Before any manifest edit, choose one policy deliberately: (a) preserve the existing direct/exact contract and add a carefully bounded header-evidence path, or (b) make the established Stage1 UA-only-as-trace policy authoritative and then re-review source semantics/observability. This review makes neither change.

## 10. Root-cause counts

Counts below assign exactly one primary category per reviewed failure. `pass` controls are excluded. Priority is shown where the finding is actionable; inherited 930 G/C categories retain their historical status rather than being re-prioritized here.

| Family / failure population | A | B | C | D | E | F | G | Priority split |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CMDi positive misses (9) | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 9 P2 |
| CMDi unexpected negative (1) | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 P1 |
| XSS positive misses (5) | 0 | 4 | 0 | 0 | 0 | 0 | 1 | 1 G/P2, 4 P3 |
| XSS unexpected negatives (3) | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 P1 |
| SQLi positive misses (4) | 0 | 3 | 0 | 0 | 0 | 0 | 1 | 1 B/P2, 1 G/P2, 2 B/P3 |
| Traversal positive misses, inherited (10) | 0 | 3 | 3 | 0 | 0 | 0 | 4 | historical B/C/G categories |
| **Total current review failures (32)** | **4** | **19** | **3** | **0** | **0** | **0** | **6** | **P0: 0; P1: 4** |

Thus the direct answers are: CMDi’s nine misses are primarily a project-supported grammar/vocabulary coverage gap, not an annotation or adapter problem; there are zero definite A bugs among those nine. The definite production-bug count across the review is four A/P1 items. Manifest annotation correction is not currently warranted (zero confirmed errors), and adapter fidelity issues are zero.

## 11. Priority-ordered minimal-fix options (not implemented)

### P0 — none

No present mismatch was identified where existing production code plainly fails its own implemented semantic rule. Do not manufacture a P0 category from a desired coverage expansion.

### P1 — clear false-positive candidate boundaries

1. Require a substantive security signal before HPP + length + special-character accumulation can independently cross 4 (`932380/5`).
2. Give `event_handler` executable/injection context or a constrained credible-event policy, preventing base64 `onafe=` (`941120/9`) while retaining SVG `onload=alert()`.
3. Require construction context for JavaScript URI/CSS and browser-data patterns, suppressing bare `url(javascript:alert())` (`941140/14`) and pathname `document.cookie` (`941180/7`) without losing assigned CSS/real script cases.

### P2 — high-value supported-scope CMDi and narrow SQLi work

1. Compose explicit shell grammar with a deliberately bounded cross-platform command vocabulary: semicolon/pipe/`||`/`&&`, command substitution/backticks, and `sh -c`-style invocation. Add the reviewed tokens needed by the project contract (`cmd`, `ps`, `who`, `iwr`, `iwmi`, `mshta`, `dsmod`) rather than a huge command-name list. Guard SQL grammar and retain `;environment`/bare-command negatives.
2. Consider bounded `pg_sleep` support after the same regression review.
3. Resolve—not silently implement around—the two UA/header evidence-policy G cases.

### P3 — broad optional expansion

- `%uXXXX` best-fit normalization, large HTML/JS/CSS decoding chains, `setTimeout`/tagged-template JavaScript grammar, incomplete legacy CSS token recognition.
- SQL comment-aware DDL and optimizer-hint/evasion grammar.
- Full CRS transform-chain parity or broad arbitrary command-name recognition.

The recommended CMDi P2 is intentionally not “all command names” or “all shell-looking words.” Separator + arbitrary token would immediately threaten `;environment`; bare `whoami`, `cat /etc/passwd`, `curl …`, and bare `regedit` remain non-injection controls. A small vocabulary plus independently strong shell forms preserves that principle.

## 12. Expected regression corpus and before/after estimate

Any later 6B-2F must run, at minimum, all 12 CMDi positives/6 negatives, all 12 XSS positives/6 negatives/one OOS, all 12 SQLi positives/8 negatives, and frozen 930. It must also verify no SQLi-to-CMDi contamination for the SQLi semicolon/DML/comment cases listed above.

Without changing code, the intended effects of the minimal proposal are:

| Change class | Expected case movement |
| --- | --- |
| CMDi P2 grammar/vocabulary | `932125/1`, `/2`, `932130/1`, `932230/31`, `/36`, `932340/1`, `/21`, `932370/3`, `932380/21`: miss -> selected; seven are exact-core |
| CMDi P1 generic-score gate | `932380/5`: candidate -> suppressed |
| XSS P1 contexts | `941120/9`, `941140/14`, `941180/7`: candidate -> suppressed; retain `941120/6`, `941140/5`, script positives |
| deferred header policy | no asserted movement until policy decision (`941110/3`, `942280/4`) |
| deferred P3 | no asserted movement for the four XSS or two SQLi broad-evasion/grammar cases |

If the scoped CMDi P2 behaves as intended, full CMDi candidate support becomes 12/12 and its exact core 9/9; the balanced selected core becomes 29/36 before any deferred header/P3 work. These are expected effects to test, not a benchmark target and not authorization to special-case CRS IDs.

## 13. Final go/no-go answers

1. **CMDi nine-miss primary cause:** missing explicit shell grammar in two and too-narrow command vocabulary in seven; B/P2 for all nine.
2. **Definite production bugs among CMDi misses:** 0; current definite production bugs overall: 4 A/P1 boundaries.
3. **`&&` scope:** yes, explicitly current exact CMDi contract.
4. **Windows/PowerShell scope:** yes, explicitly current contract; no production support today.
5. **Allowlist:** retain a small cross-platform vocabulary as one guard, but do not rely on it alone or expand it without bound.
6. **`932380/5`:** no CMDi regex hit; `HPP + long + very-long + special = 4` generic candidate.
7. **XSS misses:** four broad normalization/JS/CSS coverage gaps and one UA-evidence policy conflict; not one uniform normalization problem.
8. **XSS unexpected signals:** broad `onafe=`, context-free JS URI+alert, and bare pathname `document.cookie`, exactly as traced in §6.3.
9. **XSS 3/6 suppression:** three clear P1 candidate-boundary bugs, not final-Stage1 conclusions.
10. **Weak composition:** yes for `941120/9`, but weak event + two length bonuses, not special-character bonus.
11. **SQLi misses:** `pg_sleep` coverage, one UA policy case, and two optional comment/evasion grammars.
12. **Manifest error:** none confirmed; two header policy reconciliations need a decision before any annotation change.
13. **Adapter fidelity:** no issue; body OOS remains correct.
14. **Clear P0/P1:** P0=0, P1=4.
15. **High-value CMDi P2:** bounded shell grammar plus reviewed cross-platform vocabulary, with SQL/negative guards.
16. **Broad P3:** full transform emulation, JS/CSS grammar, broad command vocab, and SQL evasion grammar.
17. **Run Stage1 at CMDi 2/9?:** no for an interpretable balanced CMDi comparison; it is only a two-case exploratory sample.
18. **Minimal 6B-2F scope:** the four P1 boundaries plus the P2 CMDi grammar/vocabulary gap; do not include P3 or header-policy changes.
19. **Expected movements:** listed in §12, subject to generic semantic regression tests.
20. **Recommendation:** **Path B** — minimal 6B-2F, frozen baseline rerun, then 6B-3.

## 14. Git

This phase intentionally changes only this document and the design index link. It creates no commit. Final verification is:

```bash
git diff --check
git diff --stat
git status --short
```
