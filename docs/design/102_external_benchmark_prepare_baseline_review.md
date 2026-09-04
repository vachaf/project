# 102 External Benchmark Prepare Baseline Review

- 문서 상태: Phase 5B-2R 원인 조사 및 변경 우선순위 결정
- 분석 기준 production commit: `1f2acbb` (`feat: add Prepare-only OWASP CRS benchmark`)
- source revision: OWASP CRS `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`
- 작성일: 2026-09-01
- 구현 상태: 문서-only. Prepare, Stage1, mapping, manifest, adapter, threshold, regex, test는 변경하지 않았다.

## 결론

다음 단계는 **Path C: 5B-2F에서 P0/P1만 최소 수정한 뒤 5B-3 Stage1 benchmark로 진행**한다.

최소 수정 후보는 (1) single-backslash `..\` escape가 실제로 match하지 않는 regex bug, (2) embedded `foo../`와 `foo.../`를 segment escape로 오인하는 boundary bug, (3) direct `/etc/passwd|win.ini`를 `traversal:*`로 표시해 downstream CWE-22 branch까지 오염할 수 있는 Prepare hint taxonomy debt다. Semicolon traversal, query-value sensitive-resource 일반화, separator 없는 command-looking text는 같은 변경에 섞지 않는다.

### Correction note (2026-09-04)

이 문서의 `930100/3` 관련 “CRS transform/normalization” shorthand는 부정확했다. Pinned CRS 930100은 해당 encoded representation을 `t:none` rule regex로 직접 match한다. Project-side gap은 여전히 current Prepare의 normalization/evidence coverage이며, 아래 historical baseline analysis는 당시 기록으로 유지한다.

11 candidate miss의 분해는 다음과 같다.

| 구분 | 수 | cases |
| --- | ---: | --- |
| 명백한 production bug | 1 | `930110/8` |
| desirable coverage gap | 3 | `930120/4`, `/13`, `/14` |
| intentional/currently unsupported | 3 | `930110/12`, `930120/5`, `/6` |
| manifest/policy 재검토 | 4 | `930120/7`, `/8`, `/9`, `/18` |

두 unexpected Prepare candidate는 별도 P1 false-positive boundary 두 건이다. 아직 end-to-end false positive라고 부르지 않는다. Stage1이 `likely_false_positive` 또는 `inconclusive`로 교정할 가능성은 있지만, Prepare candidate 비용과 misleading hint는 이미 발생한다.

## 1. Baseline interpretation

```text
source total               36
directly eligible          27
partial                     3
out-of-scope                6
expected candidate         19
project negative            8

candidate recall          8 / 19 = 0.42105263157894735
negative suppression      6 / 8  = 0.75
```

42.1%는 “CRS 공격 탐지율”이 아니다. Apache logs-only surface에 decisive request text가 남고 project annotation이 candidate를 요구한 19건 중 Prepare가 8건을 Stage1 비용 경계로 올렸다는 뜻이다. 75%는 project-negative 8건 중 6건을 Prepare가 억제했다는 뜻이다. 후보가 됐다고 최종 공격 판정인 것도, filtered-out됐다고 benign인 것도 아니다.

recall이 낮은 핵심 이유는 current Prepare가 `../` 계열과 PHP wrapper에 좁게 맞춰져 있고, CRS 930120의 OS-file wordlist처럼 임의 query name/value의 resource token을 일반적으로 검사하지 않기 때문이다. 여기에 single-backslash escaping bug 1건과, project taxonomy가 command-looking standalone text를 injection으로 볼지에 대한 annotation 불확실성이 섞였다.

## 2. 재현과 실제 detection path

분석은 현재 checkout의 미완료 Stage1 작업과 분리하여 commit `1f2acbb` archive에서 수행했다.

```bash
python3 -m src.external_benchmark_prepare \
  --source-dir benchmarks/sources/owasp_crs/96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a \
  --manifest benchmarks/manifests/owasp_crs_path_file_access.v1.json \
  --output /tmp/prepare-baseline-1f2acbb.json
```

결과:

```text
[OK] candidate recall: 8/19 (0.42105263157894735)
[OK] negative suppression: 6/8 (0.75)
```

각 direct case는 `external_benchmark_prepare.evaluate_prepare_case()`가 한 row씩 격리해 production `build_outputs(..., min_score=4, source_tables=["security"])`를 호출한다. 흐름은 다음과 같다.

```text
source request_target
  -> normalized case request.request_target (무변환)
  -> synthetic raw_request = METHOD + target + HTTP version
  -> extract_raw_request_target(raw_request)
  -> uri / raw query split (첫 literal ?만 사용)
  -> build_analysis_texts
       base: raw request, normalized raw request, uri, raw/normalized query, raw target
       variants: query와 raw target의 depth 0..2 unquote_plus 결과
  -> SQLi/XSS/TRAVERSAL/CMDI pattern score
  -> decoded/file-disclosure 및 기타 detector score
  -> generic context score
  -> threshold/guard
  -> Candidate 또는 filtered row
```

synthetic status는 200, response bytes/duration/TTFB는 0, referer/error linkage는 없고 case별 IP와 한 시간 간격 timestamp를 쓴다. 따라서 이 benchmark에서 error, timing, repetition 또는 cross-case context score는 없다. filtered rows의 실제 public reason은 전부 `low_signal_request`다. `dir_probe:burst` 같은 filtered reason hint는 filtered artifact 재구성용 분류 hint이며 candidate score contribution이 아니다.

### Adapter validation

대표 `930110/8`, `/12`, `930120/4`, `/7`, `/14`에서 다음 equality를 다시 확인했다.

```text
source request_target == normalized request_target
                      == synthetic raw_request에서 재추출한 raw_request_target
```

| case | source/normalized/raw target | synthetic query_string | 보존 결과 |
| --- | --- | --- | --- |
| `930110/8` | `/get?arg=..\pineapple` | `?arg=..\pineapple` | single backslash 1 byte(`0x5c`) 보존 |
| `930110/12` | `/get?a=..;.\.;\.` | `?a=..;.\.;\.` | semicolon/backslash 보존 |
| `930120/4` | `/get?foo=arg&path_comp=.ssh/id_rsa` | `?foo=arg&path_comp=.ssh/id_rsa` | resource token 보존 |
| `930120/7` | `/get?code=cat+%2Fetc%2Fsubuid` | `?code=cat+%2Fetc%2Fsubuid` | raw percent form 및 decoded `cat /etc/subuid` variant 존재 |
| `930120/14` | `/get?code=backup.sql.zip` | `?code=backup.sql.zip` | filename 보존 |

이 대표 miss들은 E(adapter artifact)나 F(Apache/log observability mismatch)가 아니다. decisive text가 raw target과 query 및 필요한 경우 decoded variant에 존재한다.

## 3. Pattern inventory와 scoring

### TRAVERSAL_PATTERNS 전체

| name | compiled expression | score | 실제 의미 |
| --- | --- | ---: | --- |
| `dotdot_slash` | `(?i)(?:\.\./|\.\.\\\\|%2e%2e%2f|%2e%2e/|\.\.%2f|%252e%252e%252f)` | 4 | unbounded `../`; **두 개의 literal backslash** 뒤의 `..`; 일부 raw encoded/double-encoded slash |
| `etc_passwd` | `(?i)/etc/passwd|win\.ini` | 5 | directory escape가 아니라 direct sensitive resource token까지 traversal group으로 점수화 |

`combined_target` 전체에 `search()`하므로 `dotdot_slash` 앞뒤 segment boundary는 없다. 또한 `build_analysis_texts()`의 decoded variants 때문에 encoded slash는 pattern 자체와 decode 후 plain form 양쪽에서 관찰될 수 있지만 같은 named pattern은 main scoring loop에서 한 번만 점수화된다.

Standalone 결과:

```text
pattern.search(r"..\pineapple")          -> no match
pattern.search(".." + "\\"*2 + "pineapple") -> match "..\\"
pattern.search("foo../1234")             -> match "../"
pattern.search("foo.../1234")            -> match "../"
pattern.search("/..foo")                 -> no match
pattern.search("/..")                    -> no match
```

Python raw string에서 regex source `r"\.\.\\"`가 single literal backslash를 뜻한다. 현재 source의 `r"\.\.\\\\"`는 regex engine에 `\\`를 전달하여 **두 literal backslashes**를 요구한다. 즉 intended Stage1/current taxonomy의 Windows `..\` semantics와 compiled regex가 불일치한다.

### CMDI_PATTERNS 전체

| name | score | 요구 구조 | examples |
| --- | ---: | --- | --- |
| `pipe_exec` | 4 | `|` 뒤 allowlisted command | `| id`, `| cat` |
| `semicolon_exec` | 4 | `;` 뒤 allowlisted command | `; cat`, `; curl` |
| `subshell` | 4 | `$(` 또는 backtick 뒤 allowlisted command | `$(id)`, `` `cat`` |

quote 자체는 요구하지 않지만 shell boundary/separator는 요구한다. bare `cat /etc/subuid`와 leading redirection `>/tmp/curl`은 어느 pattern에도 속하지 않는다. `&&`, `||`의 명시적 allowlist branch나 generic `>` branch도 없다.

### FILE_DISCLOSURE_PATTERNS 전체

| pattern | score | surface | intended signal | examples/support |
| --- | ---: | --- | --- | --- |
| `php_filter_wrapper` | 5 | combined target + query/raw-target decoded variants | PHP stream wrapper | `php://filter`, encoded/double encoded form |
| `base64_source_filter` | 2 | same | source encoding intent | `convert.base64-encode` |
| `resource_parameter` | 2 | same | wrapper resource selector | `resource=` at `?`, `&`, `/` boundary; encoded forms |
| `admin_config_php` | 2 | same, only resource context에서 가산 | named sensitive PHP target | `resource=admin/config.php` |
| `config_php` | 2 | same, only resource context에서 가산 | named sensitive PHP target | `resource=config.php` |
| `index_php` | 1 | same, only resource context에서 가산 | named PHP target | `resource=index.php` |

현재 file-disclosure detector는 PHP wrapper/source-disclosure family다. direct OS resource, generic hidden file, backup filename, dependency metadata pattern은 없다. `FILE_DISCLOSURE_PATTERNS`가 query value를 검사하지 않는 것이 아니라, query/decoded target을 검사하되 해당 family의 pattern 자체가 없다.

### Sensitive path probe

`build_sensitive_path_probe_summaries()`의 effective path는 raw request target의 `?` 앞 path를 우선하고 없으면 `uri`를 쓴다. query name/value는 category classifier 입력이 아니다. 지원 path는 `/wp-login.php`, `/wp-admin/`, `/.env`, `/phpinfo.php`, `/server-status`, `/backup.zip`, `/config.php`, `/admin/config.php`, `/backup/`, `/admin/`다.

단일 요청에 공격 score를 주는 detector가 아니라 같은 IP/time-window의 context-only summary다. 반복 path, 둘 이상의 category 또는 errorish status가 있어야 emit하며 `should_promote_to_candidate=false`다. 따라서 isolated 200 benchmark row의 `.ssh`, `/sys`, `.docker`, backup filename, node metadata query value에는 candidate route를 만들지 않는다.

## 4. Required 27-case table

분류 코드는 A production detection bug, B production coverage gap, C intentional current scope limitation, D benchmark expectation/annotation issue, E adapter artifact, F observability mismatch, G policy decision이다. `pass`는 baseline failure root cause가 없다는 뜻이다.

| Case | Family | Expected | Actual | Score | Verdict hint | Key reason hints | Filtered reason | Root cause | Recommended action |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `930100/2` | strict traversal | yes | yes | 9 | `path_traversal` | `dotdot_slash(+4)`, `etc_passwd(+5)` | — | pass | keep |
| `930100/3` | strict/encoded risk | yes | yes | 5 | `suspicious` | `etc_passwd(+5)` | — | pass; CRS transform는 미지원이나 resource token으로 선택 | keep; Stage1 관찰 |
| `930110/2` | strict traversal | yes | yes | 10 | `path_traversal` | `dotdot_slash(+4)`, `etc_passwd(+5)`, special ratio +1 | — | pass | keep |
| `930110/4` | negative | no | yes | 4 | `suspicious` | `dotdot_slash(+4)` | — | A / FP boundary | tighten_fp_boundary |
| `930110/5` | negative | no | yes | 4 | `suspicious` | `dotdot_slash(+4)` | — | A / FP boundary | tighten_fp_boundary |
| `930110/6` | negative | no | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst`, `sensitive_path` | `low_signal_request` | pass | keep |
| `930110/7` | negative | no | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst`, `sensitive_path` | `low_signal_request` | pass | keep |
| `930110/8` | strict traversal | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | A: backslash over-escaped | fix_bug |
| `930110/9` | strict traversal | yes | yes | 9 | `path_traversal` | `dotdot_slash(+4)`, `etc_passwd(+5)` | — | pass | keep |
| `930110/12` | strict traversal | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | C: transform-specific alternate syntax unsupported | consider_coverage_expansion |
| `930120/1` | strict traversal | yes | yes | 5 | `suspicious` | `dotdot_slash(+4)`, special ratio +1 | — | pass | keep |
| `930120/2` | direct resource | yes | yes | 6 | `path_traversal` | `etc_passwd(+5)`, special ratio +1 | — | pass selection; P0 semantic debt | fix_bug |
| `930120/3` | strict traversal | yes | yes | 7 | `path_traversal` | `dotdot_slash(+4)`, long +2, special ratio +1 | — | pass | keep |
| `930120/4` | direct resource | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | B: strong `.ssh/id_rsa` query family absent | consider_coverage_expansion |
| `930120/5` | direct resource | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | C: `/sys/class` argument-name token outside scope | review_manifest |
| `930120/6` | direct resource | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | C: `/sys/class` generic value outside scope | review_manifest |
| `930120/7` | command-like | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | D/G: command text without injection boundary | review_manifest |
| `930120/8` | command-like | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | D/G: same as `/7` | review_manifest |
| `930120/9` | command-like | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | D/G: isolated redirection fragment | review_manifest |
| `930120/10` | negative | no | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | pass | keep |
| `930120/11` | negative | no | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | pass | keep |
| `930120/12` | negative | no | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | pass | keep |
| `930120/13` | direct resource | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | B: strong `.docker/secrets` query family absent | consider_coverage_expansion |
| `930120/14` | direct resource | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | B: moderate backup artifact family absent | consider_coverage_expansion |
| `930120/15` | strict traversal | yes | yes | 4 | `suspicious` | `dotdot_slash(+4)` | — | pass | keep |
| `930120/16` | negative | no | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | pass | keep |
| `930120/18` | direct resource | yes | no | pre-filter 0 | — | filtered artifact: `dir_probe:burst` | `low_signal_request` | D/G: weak/context-dependent metadata token | review_manifest |

“pre-filter 0”은 benchmark가 내부 score를 serialize해서가 아니라, production scoring branches를 동일 `combined_target`과 neutral row fields에 대입한 결과다. 이 cases에는 SQLi/XSS/traversal/CMDI/file-disclosure/decoded attack hit, length, special-ratio, HPP, error/timing/auth/source context 점수가 모두 없다. 즉 score 1~3 뒤 threshold miss가 아니라 pattern/route 부재다.

## 5. Strict traversal 9 cases

| case | request | candidate | score | verdict | key hint | matched representation | result | root-cause family |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| `930100/2` | `.../.../WINDOWS/win.ini` | yes | 9 | path traversal | dotdot + win.ini | inner `../` substring + resource | pass | supported plain substring |
| `930100/3` | `0x2e.%000x2f.../win.ini` | yes | 5 | suspicious | win.ini only | direct resource only; CRS 0x/NUL transform 미지원 | pass candidate, semantic weak | normalization boundary |
| `930110/2` | `../../../etc/passwd` | yes | 10 | path traversal | dotdot + passwd | `../` | pass | supported plain |
| `930110/8` | `..\pineapple` | no | 0 | — | — | single backslash preserved, regex requires two | fail | regex bug |
| `930110/9` | `.../.../WINDOWS/win.ini` | yes | 9 | path traversal | dotdot + win.ini | inner `../` substring | pass | supported substring |
| `930110/12` | `..;.\.;\.` | no | 0 | — | — | CRS transform-specific semicolon/backslash form | fail | unsupported alternate syntax |
| `930120/1` | `../../../../../boot.ini%00` | yes | 5 | suspicious | dotdot | `../`; special ratio | pass | supported plain |
| `930120/3` | `../../.../httpd.conf%00` | yes | 7 | path traversal | dotdot | `../`; length/special context | pass | supported plain |
| `930120/15` | `../.history` | yes | 4 | suspicious | dotdot | `../` | pass | supported plain |

현재 실제 coverage boundary는 plain `../`, 그 substring을 포함하는 triple-dot, 일부 percent/double-percent form이다. single `..\`는 의도와 달리 미지원이고, semicolon/Tomcat/CRS transform chain은 명시적 지원 근거가 없다. `930110/12`는 adapter/decoder bug가 아니라 currently unsupported syntax(C)다. observable하므로 P2로 검토할 수 있지만 CRS transform을 통째로 복제할 의무는 없다.

### 930110/4와 /5

`930110/4`의 exact match는 `/get/foo../1234` 안의 `../`다. 앞의 `foo`와 분리되는 boundary를 요구하지 않아 score 4 전부가 `traversal:dotdot_slash(+4)`에서 왔다. 다른 context signal은 없다.

`930110/5`도 별도 detector가 아니라 같은 root cause다. `foo.../1234`의 세 dots 중 마지막 두 dots와 slash가 `../` substring을 이루므로 exact match는 역시 `../`다. current project가 명시하는 “directory escape” semantics에는 segment에 붙은 이 lookalike를 high-signal candidate로 올릴 근거가 없으므로 intentional behavior가 아니라 P1 boundary bug다.

반면 `/get/..foo`와 `/get/..`에는 slash/backslash가 dots 뒤에 없으므로 alternation 자체가 성립하지 않는다. boundary guard가 있어서 통과한 것이 아니라 required trailing separator가 없어 우연히 억제된 것이다.

## 6. Direct resource family 7 cases

| case | resource | current route | 판단 |
| --- | --- | --- | --- |
| `930120/2` | LFI-like `op=/etc/passwd%00` | traversal group `etc_passwd` +5, special ratio +1 | candidate는 맞지만 taxonomy 잘못됨 |
| `930120/4` | `.ssh/id_rsa` | 없음 | strong selected-resource coverage gap |
| `930120/5` | arg name `/sys/class` | 없음 | generic kernel path token; current scope 밖 |
| `930120/6` | value `/sys/class` | 없음 | same; application context 없이 broad |
| `930120/13` | `.docker/secrets` | 없음 | strong selected-resource coverage gap |
| `930120/14` | `backup.sql.zip` | 없음 | moderate backup-artifact coverage gap |
| `930120/18` | `node_modules/.../package.json` | 없음 | weak/context-dependent; annotation review |

권고는 Option C다.

- `.ssh/id_rsa`, `.docker/secrets`: credential/secret location으로 강하다. bounded query-value detector를 P2 coverage 후보로 둔다.
- `backup.sql.zip`: project가 request-path `/backup.zip`과 backup probe taxonomy를 이미 갖고 있어 moderate gap이다. 확장 시 filename boundary와 file-read-like parameter context를 함께 요구한다.
- `/sys/class`: directory 자체는 정상 application input일 수 있고 file도 secret도 아니다. argument name까지 global scan하는 CRS semantics를 그대로 복제하지 않는다.
- `node_modules/package.json`: 공개 dependency metadata endpoint가 실제로 존재할 수 있어 단발 token만으로 candidate를 강제하지 않는다. manifest `candidate_expected=true`를 재검토한다.

대형 filesystem wordlist를 모든 query에 적용하지 않는다. 작은 high-confidence family, parameter context, token boundary를 사용하고 existing decoded variants를 재사용해야 한다. URL decode pass를 늘릴 필요는 없다.

## 7. Command-like family 3 cases

`930120/7`과 `/8`은 `unquote_plus` 후 `cat /etc/subuid[-]`가 정확히 보존된다. 그러나 current CMDI는 `| cat`, `; cat`, `$(cat`, backtick `cat`처럼 host command boundary를 깨는 구조를 요구한다. bare query value의 `cat ...`는 command text일 수 있지만 injection primitive라는 증거는 아니다.

`930120/9`의 `>/tmp/curl`도 redirection operator와 path는 보이지만 실행할 command, preceding shell boundary 또는 shell sink context가 없다. `/10`의 `>/tmp` negative와 차이는 filename token뿐이다. 이 한 쌍만으로 generic `>` detector를 추가하면 정상 비교/검색/templating input FP 비용이 크다.

따라서 세 건 모두 detector bug가 아니다. manifest의 `candidate_expected=true` 및 compatible verdict set을 재검토한다. `/7,/8`은 policy가 single-request sensitive file-read intent를 candidate로 삼기로 결정한다면 `suspicious_file_disclosure` 또는 `suspicious_scan`만 남길 수 있지만 `suspicious_command_injection`은 separator/sink evidence 없이는 너무 넓다. `/9`는 `suspicious_scan`조차 low confidence여서 candidate expectation 자체를 내리는 쪽이 우세하다.

## 8. Negative controls 8 cases

| case | request token | result | 해석 |
| --- | --- | --- | --- |
| `930110/4` | `foo../` | unexpected candidate | unbounded `../` substring FP |
| `930110/5` | `foo.../` | unexpected candidate | same regex, inner `../` FP |
| `930110/6` | `/..foo` | filtered | trailing separator 없음 |
| `930110/7` | `/..` | filtered | trailing separator 없음 |
| `930120/10` | `>/tmp` | filtered | redirection 미지원; expected suppression |
| `930120/11` | `>/test.environment` | filtered | hidden-name substring detector 없음 |
| `930120/12` | `.dockery` email | filtered | `.docker` detector 없음; future boundary guardrail |
| `930120/16` | `history.history` | filtered | `.history` generic substring detector 없음 |

현재 negative suppression 6/8의 손실은 모두 `930110/4,/5` 한 regex root cause다. 이것은 Prepare selectivity issue이며 end-to-end FP 여부는 Stage1 전까지 unknown이다.

## 9. Critical semantic issue: 930120/2

`/etc/passwd`와 `win.ini`가 `TRAVERSAL_PATTERNS`에 들어간 이유를 commit history에서 명시적으로 설명하는 기록은 찾지 못했다. 해당 두 patterns와 CMDI patterns는 원래 monolith에 있었고 `fdedb2e`에서 mechanical extraction됐을 뿐이다. 과거 D-set 문서는 `/etc/passwd` 직접 접근을 “sensitive file intent” 및 broad high-signal traversal 시도로 함께 다뤘다. 이후 Stage1/mapping 설계는 다음처럼 계약을 좁혔다.

```text
direct sensitive path != traversal
explicit directory escape가 있어야 suspicious_path_traversal/CWE-22
```

Prepare side의 old broad signal만 그대로 남은 semantic debt로 판단한다.

`930120/2`에는 `../`, `..\` 또는 encoded equivalent가 없다. 그럼에도 `etc_passwd(+5)`가 `traversal_hits=1`을 만들고 special ratio +1과 합쳐 score 6, `verdict_hint=path_traversal`이 된다. Stage1 prompt는 direct sensitive path만으로 traversal을 고르지 말라고 하지만 `traversal:*` hint 자체를 explicit evidence 예로 제시한다. 모델 교정은 가능하나 입력이 자기모순적이다. deterministic post-parse normalization은 PHP-wrapper three-hint set에만 적용되어 이 case를 보장하지 않는다.

영향은 verdict 표현에 그치지 않는다. standards mapping의 file-disclosure branch도 `traversal:*` hint를 최우선으로 보고 A01/CWE-22/WSTG-ATHZ-01을 붙인다. 따라서 Stage1이 file disclosure로 교정해도 stale Prepare hint가 forbidden CWE-22를 유발할 수 있다. P0 semantic correctness 문제로 분리해야 한다. 수정 방향은 direct sensitive resource signal을 없애는 것이 아니라 traversal group에서 의미상 분리하여 file-disclosure/direct-sensitive evidence로 제공하는 것이다.

`930100/3`도 encoded traversal을 실제로 인식하지 못하고 `win.ini`만으로 candidate가 된다는 점을 함께 회귀 검토해야 한다. semantic 분리 후 이 case가 candidate에서 빠질 수 있는데, 그것은 CRS transform coverage를 별도 P2로 결정할 문제이지 잘못된 traversal hint를 유지할 이유가 아니다.

## 10. Root-cause summary

실패 13건(11 miss + 2 unexpected candidate)을 primary root cause로 mutually exclusive하게 센 결과다.

| classification | count | note |
| --- | ---: | --- |
| production bug | 1 | single-backslash escaping |
| FP boundary | 2 | embedded `../` substring |
| coverage gap | 3 | selected `.ssh`, `.docker`, backup family |
| intentional scope | 3 | semicolon traversal, `/sys/class` name/value |
| annotation review | 4 | 3 command-like + node metadata |
| adapter issue | 0 | representative equality verified |
| observability mismatch | 0 | all 27 direct decisive text preserved |

`930120/2` semantic debt는 candidate-selection pass이므로 위 13 failure count 밖의 P0 1건이다. Category G는 D와 결합 표기했으며 policy 결정 결과에 따라 manifest 또는 future coverage queue로 이동한다.

## 11. Recommended changes (구현하지 않음)

### P0 — semantic correctness

1. `dotdot_slash`의 intended single-backslash form을 compiled semantics에 맞춘다. 일반 규칙은 “dot-dot 뒤 literal path separator”이며 benchmark ID/path special case가 아니다.
2. `/etc/passwd|win.ini` direct tokens를 traversal evidence와 분리한다. LFI-like parameter context에서는 direct-sensitive/file-disclosure hint와 candidate score를 줄 수 있지만 explicit escape 없이는 `traversal_hits`와 CWE-22 route를 만들지 않는다.

### P1 — false-positive boundary

`../` 앞에 path-segment boundary를 요구하되 실제 supported forms(`../../../`, query value 시작, slash-separated segment)을 보존한다. triple-dot을 지원할 것이라면 `.../`를 명시적 semantic branch로 정의하고, `foo.../` embedded lookalike와 구분해야 한다. 단순 negative lookbehind 하나가 URL/query boundary 전체에 맞는지는 fixture로 검증한다.

### P2 — desirable but unsupported

- `930110/12` semicolon/Tomcat-style canonicalization은 bounded transform 또는 explicit regex로 검토한다. CRS transform 전체 복제와 반복 decode 증가는 피한다.
- `.ssh/id_rsa`, `.docker/secrets`, boundary가 분명한 backup artifact를 작은 high-confidence resource family로 검토한다. query value 전체에 대형 wordlist를 스캔하지 않는다.

### P3 — optional / low confidence

- `/sys/class`, `node_modules/.../package.json`
- separator/shell sink가 없는 `cat /etc/...`
- isolated `>/tmp/curl`

이들은 먼저 annotation/policy review를 끝내고, 실제 production corpus FP/cost 자료 없이 detector를 확장하지 않는다.

모든 제안은 request semantics에 일반화되어야 한다. benchmark UA, `bench-*` request ID, exact case path 조건은 금지한다.

## 12. Existing regression impact

| fix candidate | 보호/영향 테스트 | 확인할 behavior |
| --- | --- | --- |
| traversal separator regex | `tests/test_prepare_scanner_probe_candidate_policy.py::test_probe_with_explicit_traversal_payload_remains_payload_candidate`, `tests/test_prepare_status_error_only_candidate_policy.py::test_500_with_explicit_traversal_payload_remains_payload_candidate`, `tests/test_prepare_xss_external_navigation.py` traversal cases | plain `../` candidate와 score/hint 유지 |
| backslash + substring boundary | `tests/test_external_benchmark_prepare.py` full inventory/family/failure tests, 신규 standalone pattern cases 필요 | `/4,/5` suppress, `/8` select, `/6,/7` unchanged |
| direct resource semantic split | `tests/test_llm_stage1_classifier.py::test_stage1_prompt_requires_explicit_traversal_evidence_for_path_traversal`, `::test_stage1_prompt_does_not_allow_weak_context_alone_as_traversal_evidence`, `tests/test_security_standards_mapping.py::test_direct_private_secret_is_not_traversal`, `::test_traversal_based_file_disclosure_uses_traversal_branch`, `::test_direct_sensitive_file_disclosure_probe` | direct resource에 CWE-22 금지, explicit traversal에는 유지 |
| selected resource coverage | `tests/test_external_benchmark_crs.py::test_compatible_resource_and_command_cases_are_case_specific`, sensitive path fixtures `h_r3_sensitive_path_probe_context`, `e_r2_direct_config_path` | single candidate vs context-only 경계 |
| CMDI expansion(현재 비권고) | `tests/test_security_standards_mapping.py::test_cmdi_maps_cwe78_not_cwe77`, external benchmark `/7`~`/12` | separator evidence 및 negative pair 유지 |

현재 tests는 plain traversal, Stage1 direct-path guardrail, mapping branch를 보호하지만 single-backslash compiled match와 embedded-dot negative boundary를 production unit level에서 직접 고정하지 않는다. 5B-2F에서는 before/after benchmark와 focused unit regression을 함께 추가해야 한다.

## 13. Stage1 go/no-go와 질문별 답

1. **42.1%의 핵심 이유:** CRS OS-file-access surface와 current narrow Prepare scope의 차이이며, 11 miss 중 10건은 single regex malfunction이 아니다.
2. **11 miss 중 명백한 bug:** 1건(`930110/8`).
3. **intentional/unsupported coverage:** 6건(coverage gap 3 + current-scope limitation 3). 이 중 확장 권고는 우선 3건이다.
4. **manifest expectation 재검토:** 4건(`930120/7,/8,/9,/18`). `/5,/6`도 annotation note/향후 score lane은 재검토하되 primary count는 current-scope limitation에 뒀다.
5. **`930110/4,/5` 원인:** boundary 없는 `\.\./` search가 각각 literal `../` 및 `.../` 안의 inner `../`를 match하여 traversal score 4만으로 candidate를 만든다.
6. **`930110/8` 원인:** adapter/normalization은 single `0x5c`를 보존하지만 current raw regex가 two consecutive backslashes를 요구한다.
7. **`930110/12`:** bug가 아니라 현재 unsupported CRS/Tomcat-style alternate syntax. P2 후보이다.
8. **930120 direct resources:** Option C. `.ssh`, `.docker`, bounded backup family는 고려하고 `/sys/class`, node metadata의 broad global matching은 보류한다.
9. **`930120/2` traversal hint:** 수정해야 할 semantic problem이다. Stage1 correction에 맡기면 mapping까지 오염될 수 있다.
10. **Stage1로 지금 바로 이동:** baseline 가치 때문에 Stage1 evaluator 작업 자체는 유효하지만, headline baseline 전에 P0/P1 최소 fix가 우선이다. 최종 경로는 **5B-2F 최소 Prepare fix → before/after Prepare baseline → 5B-3**이다.

## 14. 변경 범위와 검증

이 review에서는 production code, tests, manifest, adapter를 수정하지 않았다. 문서와 design index만 변경한다. commit은 만들지 않는다.
