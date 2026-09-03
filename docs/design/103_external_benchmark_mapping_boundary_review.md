# External Security Benchmark Phase 5B-3M — Traversal + Sensitive Resource Mapping Boundary Review

## 1. Review status and decision

- Review date: 2026-09-03 (Asia/Seoul)
- Repository baseline: `31e222c` (`feat: add Stage1 external benchmark evaluator`)
- Scope: targeted policy review; documentation only
- Production policy decision: **Policy B — Orthogonal evidence enrichment**
- Final recommendation: **A. production mapper 유지 + manifest case-specific correction**

Explicit directory escape와 direct-sensitive resource evidence가 함께 있으면 두 evidence axis를 모두 보존한다.

| Mapping | Decision | Relationship | Reason |
| --- | --- | --- | --- |
| `A01:2025` | yes, primary/required | `direct` | explicit traversal은 Broken Access Control의 traversal context와 직접 대응한다. |
| `CWE-22` | yes, primary/required | `direct` | 관찰된 directory-escape pattern과 직접 대응한다. |
| `WSTG-ATHZ-01` | yes, primary/required | `direct` | traversal/file-include test scenario와 직접 대응한다. |
| `CWE-552` | yes, optional enrichment | `conditional` | sensitive resource probe는 external accessibility weakness의 후보 맥락이지만 실제 접근 가능성은 확인하지 못한다. |
| `WSTG-CONF-04` | yes, optional enrichment | `related` | 민감한 unreferenced/config/system resource를 찾는 보조 test/review context다. |
| `A02:2025` | no, cross-category default 아님 | none | secondary sensitive hint만으로 상위 vulnerability category를 추가하지 않는 현재 보수 정책을 유지한다. |
| `WSTG-CONF-03` | no, cross-category default 아님 | none | generic direct-sensitive evidence가 곧 file-extension handling evidence는 아니다. |

따라서 `../../../etc/passwd`의 approved output은 primary traversal 세 ID와 optional sensitive-resource 두 ID를 함께 가질 수 있다. `CWE-552 conditional`은 CWE-552 weakness가 확인되었다는 뜻이 아니다. 이 결론은 benchmark 점수 개선이 아니라 공식 taxonomy 의미, Apache logs-only 경계, 기존 relationship 정의와 기존 설계 의도를 순서대로 적용한 결과다.

## 2. Scope and method

검토한 current production/benchmark surface는 다음과 같다.

- `src/security_standards_mapping.py`
- `src/external_benchmark_stage1.py`
- `benchmarks/manifests/owasp_crs_path_file_access.v1.json`
- pinned CRS source `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`
- `tests/test_security_standards_mapping.py`
- `tests/test_prepare_traversal_file_disclosure_semantics.py`
- `tests/test_external_benchmark_prepare.py`
- `tests/test_external_benchmark_stage1.py`
- OWASP mapping investigation/design, Security Standards Summary design, external benchmark design, Prepare baseline review
- mapping/manifest 관련 commit history와 blame

Current Prepare를 36개 normalized case에 다시 실행했다. 결과는 27 direct case, expected-candidate recall `9/19`, negative suppression `8/8`로 current tests와 일치했다. 아래 evidence와 mapping 표는 이 재현 결과를 사용한다. 임시 산출물만 `/tmp/phase5b3m_prepare.json`에 만들었고 repository artifact는 변경하지 않았다.

이번 review에서는 production code, manifest, Prepare, Stage1, tests, schemas를 수정하지 않는다.

## 3. Current production mapping contract

### 3.1 Rule flow

`build_security_standards_mapping()`은 verdict primary rule을 먼저 실행하고, `suspicious_scan`이 아니면 evidence-combination rule을 추가로 실행한다.

```text
suspicious_path_traversal
  -> _add_path_traversal()
     -> A01:2025 direct
     -> CWE-22 direct
     -> WSTG-ATHZ-01 direct

  -> _add_evidence_combination_rules()
     -> verdict != suspicious_file_disclosure
     -> structured sensitive evidence exists
     -> direct-sensitive file evidence exists
        -> CWE-552 conditional
        -> WSTG-CONF-04 related
```

Sensitive cross-category branch는 raw target의 `passwd`, `secret`, `/admin` 문자열을 새로 검색하지 않는다. 다음 Prepare evidence family가 있을 때만 동작한다.

- `sensitive_path:*`
- `dir_probe:*`
- `file_probe:*`
- `file_disclosure:sensitive_resource:*`

현재 네 failure에서는 모두 `file_disclosure:sensitive_resource:os_file`이 trigger다. `suspicious_path_traversal` verdict 자체는 CWE-552를 만들지 않는다.

### 3.2 File-disclosure branch와 차이

`suspicious_file_disclosure`는 별도의 priority decision tree를 사용한다.

1. `traversal:*` evidence가 있으면 A01/CWE-22/WSTG-ATHZ-01을 생성한다.
2. 아니면 PHP wrapper evidence를 평가한다.
3. 아니면 direct-sensitive evidence에 대해 다음을 생성한다.
   - `A02:2025 related`
   - `CWE-552 conditional`
   - `WSTG-CONF-04 related`
   - `WSTG-CONF-03 related`

그 후 generic evidence-combination rule은 verdict가 `suspicious_file_disclosure`이면 sensitive branch를 건너뛴다. 이는 duplicate 방지와 file-disclosure decision-tree priority를 보존한다.

Non-file-disclosure cross-category branch가 A02와 WSTG-CONF-03을 추가하지 않는 것은 의도된 보수 경계다.

- A02는 상위 vulnerability category다. 다른 primary verdict에 secondary sensitive evidence가 있다는 이유만으로 A02를 추가하지 않는다.
- WSTG-CONF-03은 extension/config handling에 더 구체적이다. 모든 `sensitive_path`/OS-file hint가 그 scenario를 지지하지는 않는다.
- CWE-552/WSTG-CONF-04만 resource accessibility/review라는 공통 맥락을 보조적으로 보존한다.

### 3.3 Boundary notes

Direct-sensitive file branch는 다음 boundary를 둔다.

```text
Direct sensitive file probing does not confirm external accessibility,
sensitive information exposure, or path traversal.
```

Cross-category sensitive branch는 더 일반적인 다음 boundary를 사용한다.

```text
Sensitive path probing is forced-browsing context only;
existence, access, and exposure are not confirmed.
```

두 문구 모두 actual accessibility, file read와 exposure를 부정한다. 네 case에서 CWE-552 item의 `basis`에는 trigger가 된 `file_disclosure:*` family가 직접 적히지 않고 `stage1_verdict:*`만 남지만, rule ID는 `STD-MAP-SENSITIVE-003`이고 boundary는 sensitive probe를 명시한다. 이는 taxonomy 결론을 바꾸지 않는 traceability 관찰 사항이다. 후속 relationship regression에서 basis까지 점검할 수 있으나 이번 alignment의 blocker나 code-change 권고는 아니다.

## 4. Production intent: intentional, not accidental

### 4.1 Historical design

| Revision | Date | Evidence |
| --- | --- | --- |
| `dfc9318` | 2026-09-01 | implementation 전 mapping design이 security-suspicious verdict + Prepare sensitive evidence의 cross-category 후보로 CWE-552 conditional과 WSTG-CONF-04 related를 명시했다. |
| `4228bb7` | 2026-09-01 | deterministic mapper가 `STD-MAP-SENSITIVE-003/005`를 구현했다. raw 문자열이 아니라 structured Prepare evidence만 허용하는 Phase 1.1 policy와 cross-category test도 같이 추가했다. |
| `23c07e5` | 2026-09-01 | benchmark manifest가 처음 추가될 때 모든 strict traversal mapping contract에 CWE-552 forbidden을 동일하게 넣었다. case note는 traversal strictness만 설명하고 sensitive-target별 CWE reasoning은 기록하지 않았다. |
| `c2092e9` | 2026-09-03 | Prepare가 traversal과 direct-sensitive OS-file evidence를 orthogonal하게 분리했다. `../../etc/passwd`가 두 evidence를 동시에 갖는 regression을 추가했다. |
| `31e222c` | 2026-09-03 | controlled Stage1 test가 production mapping과 blanket manifest forbidden의 충돌을 4건, `5/9`로 명시적으로 노출했다. |

OWASP mapping investigation은 처음부터 direct sensitive file/backups를 CWE-552 conditional과 WSTG-CONF-04 related 후보로 구분했다. 상세 design은 rule evaluation을 “primary first, evidence-combination additive”로 정의하고, cross-category sensitive rule이 “security suspicious final verdict”에 적용된다고 명시한다.

따라서 generic rule 자체와 traversal verdict에 적용되는 범위는 설계된 동작이다. 다만 `traversal + file_disclosure:sensitive_resource:*` 조합을 이름으로 고정한 mapper unit test는 없었다. 기존 pure traversal tests는 sensitive hint가 없기 때문에 CWE-552 absence만 검증했고, existing cross-category test는 SQLi + admin evidence를 사용했다. 이 test gap 때문에 blanket manifest와의 충돌이 Stage1 controlled fixture 전까지 드러나지 않았다.

결론:

- **Rule intent:** intentional
- **Traversal-sensitive combination regression coverage:** incomplete
- **Manifest CWE-552 blanket forbidden:** production design 이후 독립적으로 들어온 over-broad annotation

## 5. Authoritative semantics

### 5.1 Sources

| Source | URL | Version/update noted at review | Accessed |
| --- | --- | --- | --- |
| MITRE CWE-552, Files or Directories Accessible to External Parties | <https://cwe.mitre.org/data/definitions/552.html> | CWE 4.20 page; page last updated 2026-04-30 | 2026-09-03 |
| OWASP WSTG-CONF-04, Review Old Backup and Unreferenced Files for Sensitive Information | <https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/04-Review_Old_Backup_and_Unreferenced_Files_for_Sensitive_Information> | WSTG `latest`; mutable latest documentation | 2026-09-03 |
| OWASP WSTG-ATHZ-01, Testing Directory Traversal File Include | <https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/01-Testing_Directory_Traversal_File_Include> | WSTG `latest`; mutable latest documentation | 2026-09-03 |
| OWASP Top 10:2025 A01 Broken Access Control | <https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/> | OWASP Top 10:2025 | 2026-09-03 |

공식 문구를 길게 인용하지 않고 의미만 요약한다.

### 5.2 CWE-552

MITRE definition의 subject는 request 문자열이 아니라 product weakness다. Product가 원래 제한해야 할 file/directory를 unauthorized actor에게 accessible하게 만드는 상태가 핵심이다. Extended description도 web root 아래 민감 파일을 access control 없이 두거나 public storage access를 허용하는 사례를 든다.

Apache request log에서 확인 가능한 것은 공격자가 민감 resource를 target했다는 사실이다. 다음은 확인할 수 없다.

- resource가 존재하는가
- application/web server가 그 경로를 resolve했는가
- unauthorized actor에게 accessible한가
- access-control check가 없거나 실패했는가
- response에 file content가 포함되었는가
- read가 성공했는가

따라서 CWE-552를 `direct` 또는 confirmed weakness로 쓰면 안 된다. 그러나 MITRE는 CWE-552에 system-file probing attack pattern도 연관시키고, 이 weakness가 실제로 확인되려면 accessibility 결과가 필요하다고 설명한다. Project `conditional` 정의는 바로 이 차이를 표현한다.

```text
observed: sensitive resource targeting
missing condition: unauthorized external accessibility / successful resolution
conditional candidate: CWE-552
```

즉 단순 request target은 CWE-552 weakness를 증명하지 않지만, security-suspicious verdict와 structured direct-sensitive evidence가 결합되면 CWE-552와의 조건부 semantic correspondence는 충분하다.

### 5.3 WSTG-CONF-04

WSTG-CONF-04는 vulnerability taxonomy가 아니라 testing/review scenario다. Old, backup, forgotten, unreferenced file뿐 아니라 web server가 접근 가능한 공간에 잘못 놓인 data/config/log 같은 application-related sensitive file을 찾고 분석하는 것을 다룬다.

`/etc/passwd`와 `WINDOWS/win.ini`는 전형적인 backup filename은 아니다. 그러므로 WSTG-CONF-04를 primary/direct traversal mapping으로 만들면 범위를 과장한다. 그러나 민감한 unreferenced/system resource가 web request surface를 통해 target되었다는 관찰은 해당 review scenario로 이어질 수 있으므로 `related`는 타당하다. Primary traversal test scenario는 여전히 WSTG-ATHZ-01이다.

### 5.4 A01 context

OWASP Top 10:2025 A01은 CWE-22와 CWE-552를 모두 mapped CWE로 포함한다. 이는 둘이 A01 umbrella 안에서 함께 존재할 수 있음을 보여 주지만, 한 request에서 두 CWE를 자동 확정한다는 뜻은 아니다. 이 review의 coexistence 근거는 Top 10 목록 자체가 아니라 서로 다른 evidence와 relationship이다.

## 6. Relationship and boundary judgment

Current project definition을 그대로 사용한다.

| Relationship | Project meaning applied here |
| --- | --- |
| `direct` | observed attack pattern과 taxonomy/test scenario가 직접 대응한다. Exploit success나 deployed weakness confirmation은 아니다. |
| `conditional` | semantic candidate는 맞지만 additional evidence가 있어야 weakness/category가 확인된다. |
| `related` | 관련 testing/investigation context이지만 vulnerability taxonomy처럼 읽으면 과장된다. |

### 6.1 Keep-enrichment view

- `CWE-552 conditional`은 confirmation이 아니라 missing accessibility condition을 명시한 hypothesis다.
- boundary가 existence/access/exposure를 명시적으로 부정한다.
- Prepare가 raw token과 explicit traversal을 별도 structured evidence로 만들었으므로 mapper는 둘을 additive하게 표현할 수 있다.
- WSTG-CONF-04는 testing context라 `related`로 두는 것이 자연스럽다.

### 6.2 Remove-enrichment view

- CWE-552의 이름과 definition은 실제 accessibility 상태를 서술한다.
- ID만 보는 consumer는 `conditional`/boundary를 버리고 confirmed CWE처럼 오해할 수 있다.
- WSTG-CONF-04는 `/etc/passwd`/`win.ini` traversal보다 backup/unreferenced web-tree review에 더 가깝다.

### 6.3 Resolution

Keep-enrichment view를 선택한다. Project artifact는 relationship과 boundary를 first-class fields로 정의하고, Security Standards Summary도 relationship별 count와 “confirmed weakness 아님”을 보존한다. 이 contract 안에서는 CWE-552 conditional이 과장이 아니다. ID-only external benchmark도 production relationship을 바꾸지 않으며, ID presence가 valid인지를 우선 검사한다.

Boundary note는 현재 artifact에서 overclaim을 방지하기에 충분하다. 다만 relationship/boundary를 버리는 downstream consumer까지 안전하게 만들지는 못한다. 그 위험의 해법은 valid conditional ID를 금지하는 것이 아니라 consumer가 relationship/boundary를 보존하도록 하는 것이다.

CWE-552와 WSTG-CONF-04를 서로 다르게 취급할 근거는 relationship level에는 있다.

- CWE-552: actual weakness이므로 `conditional`
- WSTG-CONF-04: test/review scenario이므로 `related`

그러나 현재 evidence에서 한 ID는 절대 금지하고 다른 ID는 허용할 근거는 부족하다. Primary-taxonomy-only 정책이었다면 둘 다 금지해야 일관된다. 선택한 orthogonal-enrichment 정책에서는 둘 다 optional/non-forbidden이어야 한다.

## 7. Benchmark mapping contract semantics

Current evaluator는 actual compatible verdict의 `mapping_by_verdict`를 선택한 뒤 ID set만 비교한다.

```text
missing = required_ids - actual_ids
forbidden_present = forbidden_ids intersect actual_ids
pass = no missing and no forbidden_present
```

따라서 의미는 다음과 같아야 한다.

- `required_ids`: 이 verdict/case에서 반드시 존재해야 하는 ID
- `forbidden_ids`: 이 case에서 나타나면 의미상 잘못인 ID
- additional non-forbidden ID: 허용

`forbidden_ids`를 “primary expected mapping이 아닌 ID”라는 뜻으로 사용하면 안 된다. Evaluator 자체도 `EXTRA-VALID-ID`가 있더라도 pass하는 test로 additional non-forbidden semantics를 고정한다. Current contract는 deny-list가 아니라 must-not-appear assertion이다.

따라서 CWE-552가 optional but valid인 traversal-sensitive case에서 `forbidden_ids: ["CWE-552"]`는 지나치게 강하다.

### 7.1 Schema decision

현재 `required_ids`와 `forbidden_ids`로 충분하다.

- required primary traversal IDs는 그대로 둔다.
- optional valid sensitive IDs는 forbidden에 넣지 않는다.
- pure traversal에서 의미상 invalid인 sensitive ID는 forbidden으로 유지할 수 있다.

`allowed_optional_ids`, `conditional_allowed_ids`, relationship-specific exception list는 필요 없다.

### 7.2 Relationship-level metric

이번에는 schema/evaluator를 확장하지 않는다. `CWE-552`가 반드시 `conditional`이어야 한다는 production contract는 mapper unit test에서 고정하는 편이 우선이다. External benchmark에 relationship-level scoring을 추가하는 일은 ID boundary가 안정된 뒤 별도 phase에서 검토한다.

## 8. Exact manifest annotation and current Prepare evidence

아래 8건은 모두 manifest상 `classification_policy=exact`, expected verdict `suspicious_path_traversal`, required mapping `A01:2025`, `CWE-22`, `WSTG-ATHZ-01`, forbidden mapping `CWE-552`다. 즉 CWE-552 forbidden은 case별 reasoning이 아니라 strict traversal contract 9건 전체에 일괄 적용되어 있다. Review note도 CWE-552 의미를 case별로 설명하지 않는다.

| Case | Request target | Stage1 expected verdict | Required IDs | Forbidden IDs | Prepare direct-sensitive evidence | Prepare traversal evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `930100/2` | `/get?foo=.../.../WINDOWS/win.ini` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | `file_disclosure:sensitive_resource:os_file` | `traversal:triple_dot_slash(+4)` |
| `930100/3` | `/get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | `file_disclosure:sensitive_resource:os_file` | none |
| `930110/2` | `/get?arg=../../../etc/passwd` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | `file_disclosure:sensitive_resource:os_file` | `traversal:dotdot_slash(+4)` |
| `930110/8` | `/get?arg=..\pineapple` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | none | `traversal:dotdot_slash(+4)` |
| `930110/9` | `/get?foo=.../.../WINDOWS/win.ini` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | `file_disclosure:sensitive_resource:os_file` | `traversal:triple_dot_slash(+4)` |
| `930120/1` | `/get/index.php?file=News&op=../../../../../boot.ini%00` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | none | `traversal:dotdot_slash(+4)` |
| `930120/3` | `/get/index.php?file=News&op=../../../../../../../../../../usr/local/apps/apache2/conf/httpd.conf%00` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | none | `traversal:dotdot_slash(+4)` |
| `930120/15` | `/get?code=../.history` | exact `suspicious_path_traversal` | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 | none | `traversal:dotdot_slash(+4)` |

`930120/1`, `/3`, `/15`의 target 이름이 잠재적으로 흥미로워 보여도 current Prepare는 structured direct-sensitive evidence를 만들지 않는다. Mapping layer는 raw target을 다시 분류하지 않으므로 이 review에서는 pure traversal controls로 취급한다.

## 9. Why the four controlled cases produce CWE-552

| Case | Current Prepare reason hints | Why CWE-552 appears |
| --- | --- | --- |
| `930100/2` | `traversal:triple_dot_slash(+4)`; `file_disclosure:sensitive_resource:os_file` | triple-dot primary traversal mapping 후 OS-file evidence가 cross-category `STD-MAP-SENSITIVE-003`을 trigger한다. |
| `930100/3` | `file_disclosure:sensitive_resource:os_file` | controlled fixture가 manifest의 traversal verdict를 선택한다. 실제 Prepare에는 traversal hint가 없지만 OS-file evidence가 cross-category rule을 trigger한다. |
| `930110/2` | `traversal:dotdot_slash(+4)`; `file_disclosure:sensitive_resource:os_file`; `special_char_ratio_high(+1)` | explicit traversal과 `/etc/passwd` sensitive-resource evidence가 orthogonal하게 존재한다. |
| `930110/9` | `traversal:triple_dot_slash(+4)`; `file_disclosure:sensitive_resource:os_file` | `930100/2`와 동일 target이며 source provenance만 다르다. |

네 case의 production mapping은 모두 다음 ID/relationship을 갖는다.

```text
A01:2025       direct       STD-MAP-TRAVERSAL-001
CWE-22         direct       STD-MAP-TRAVERSAL-002
CWE-552        conditional  STD-MAP-SENSITIVE-003
WSTG-ATHZ-01   direct       STD-MAP-TRAVERSAL-003
WSTG-CONF-04   related      STD-MAP-SENSITIVE-005
```

Manifest는 CWE-552만 forbidden으로 두고 WSTG-CONF-04는 이미 additional non-forbidden ID로 허용한다. 따라서 current failure의 직접 원인은 CWE-552 ID intersection 하나다.

## 10. Pure traversal comparison

동일한 forced `suspicious_path_traversal` verdict로 production mapper를 재실행한 결과다.

| Case | Direct-sensitive evidence | Traversal evidence | Produced IDs | CWE-552/WSTG-CONF-04 |
| --- | --- | --- | --- | --- |
| `930110/8` | none | `traversal:dotdot_slash(+4)` | A01:2025; CWE-22; WSTG-ATHZ-01 | neither produced |
| `930120/1` | none | `traversal:dotdot_slash(+4)` | A01:2025; CWE-22; WSTG-ATHZ-01 | neither produced |
| `930120/3` | none | `traversal:dotdot_slash(+4)` | A01:2025; CWE-22; WSTG-ATHZ-01 | neither produced |
| `930120/15` | none | `traversal:dotdot_slash(+4)` | A01:2025; CWE-22; WSTG-ATHZ-01 | neither produced |

증명되는 boundary는 명확하다.

```text
traversal verdict alone
  != CWE-552

structured direct-sensitive evidence
  -> CWE-552 conditional + WSTG-CONF-04 related
```

Pure traversal case에서는 CWE-552 forbidden을 유지한다. 향후 pure traversal boundary를 대칭적으로 강화하려면 WSTG-CONF-04도 forbidden으로 추가할 수 있다. 반대로 direct-sensitive evidence가 있는 case에서는 두 ID 모두 non-forbidden이어야 한다.

## 11. Orthogonal evidence versus taxonomy validity

Phase 5B-2F의 Prepare contract는 directory escape와 sensitive resource target을 별도 evidence로 보존한다.

```text
../../../etc/passwd
  -> traversal:dotdot_slash(+4)
  -> file_disclosure:sensitive_resource:os_file
```

Evidence orthogonality가 모든 taxonomy를 자동 생성한다는 뜻은 아니다. 각 mapping은 별도로 semantic threshold를 통과해야 한다.

- CWE-22 direct: explicit directory escape가 threshold를 충족한다.
- CWE-552 conditional: sensitive resource targeting이 relevant hypothesis를 만들며, accessibility라는 missing condition이 명확하므로 threshold를 충족한다.
- WSTG-CONF-04 related: resource review/test context로는 관련되므로 threshold를 충족한다.
- A02 related: cross-category secondary evidence만으로 상위 category를 추가하는 것은 과하므로 threshold를 충족하지 않는다.
- WSTG-CONF-03 related: generic OS-file evidence만으로 extension handling을 말하기에는 구체성이 부족하다.

즉 orthogonal evidence를 보존하되 taxonomy validity를 개별 판단하는 것이 Policy B의 의미다.

## 12. Re-evaluation of the four controlled failures

| Case | Classification | Primary traversal IDs | Extra sensitive IDs | Current manifest | Recommended policy | Expected mapping result after policy |
| --- | --- | --- | --- | --- | --- | --- |
| `930100/2` | compatible/pass | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 conditional; WSTG-CONF-04 related | CWE-552 forbidden -> fail | remove CWE-552 from forbidden | pass |
| `930100/3` | controlled fixture에서는 compatible/pass; production evidence classification은 별도 문제 | A01:2025; CWE-22; WSTG-ATHZ-01 (forced verdict) | CWE-552 conditional; WSTG-CONF-04 related | CWE-552 forbidden -> fail | mapping boundary상 CWE-552는 valid; classification annotation을 먼저 재검토 | current forced traversal contract에서 forbidden 제거 시 pass; final result는 classification review contract에 따름 |
| `930110/2` | compatible/pass | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 conditional; WSTG-CONF-04 related | CWE-552 forbidden -> fail | remove CWE-552 from forbidden | pass |
| `930110/9` | compatible/pass | A01:2025; CWE-22; WSTG-ATHZ-01 | CWE-552 conditional; WSTG-CONF-04 related | CWE-552 forbidden -> fail | remove CWE-552 from forbidden | pass |

네 mapping failure는 mapper bug가 아니라 manifest mismatch다. 다만 `930100/3`은 mapping mismatch와 별개로 manifest classification annotation이 current Prepare evidence와 충돌한다.

## 13. The separate 930100/3 classification issue

Current Prepare after Phase 5B-2F:

```text
raw target:
  /get?foo=0x2e.%000x2f0x2e.%00/WINDOWS/win.ini

verdict_hint:
  suspicious_file_disclosure

reason_hints:
  file_disclosure:sensitive_resource:os_file

traversal evidence:
  none
```

Manifest는 이 case를 exact `suspicious_path_traversal`로 고정한다. Controlled fixture는 allowed verdict 첫 값을 의도적으로 사용하므로 classification-compatible이지만, 이는 current production evidence가 traversal을 지지한다는 증거가 아니다.

따라서 다음을 분리한다.

- Mapping boundary: forced traversal verdict + direct-sensitive evidence에서도 CWE-552 conditional은 valid다.
- Classification boundary: current decoder/evidence contract에서 이 encoding을 traversal로 볼 수 있는지는 별도 annotation review가 필요하다.

이 review는 `930100/3`을 억지로 traversal 또는 file disclosure로 재분류하지 않는다. 후속 review에서는 source transform semantics, current decoder scope와 exact/compatible policy를 다시 판단해야 한다. Current evidence만 보면 `suspicious_file_disclosure`가 더 잘 정렬되지만, 이는 이 문서의 manifest change 결정으로 확정하지 않는다.

## 14. Recommended follow-up

### 14.1 Phase 5B-3M-F — Benchmark Mapping Manifest Alignment

Production mapper는 유지한다. Case-specific manifest policy를 적용한다.

- `930100/2`, `930110/2`, `930110/9`: traversal required IDs 유지, CWE-552를 forbidden에서 제거한다.
- `930100/3`: classification review 결과와 함께 mapping contract를 갱신한다. Exact traversal을 유지한다면 CWE-552 forbidden을 제거한다. File disclosure로 바꾸면 해당 verdict의 direct-sensitive mapping contract를 사용한다.
- Pure traversal controls (`930110/8`, `930110/12`, `930120/1`, `930120/3`, `930120/15`): CWE-552 forbidden을 유지한다. 필요하면 WSTG-CONF-04도 함께 forbidden으로 추가해 no-sensitive-evidence boundary를 대칭적으로 고정한다.

Expected files:

- `benchmarks/manifests/owasp_crs_path_file_access.v1.json`
- `tests/test_external_benchmark_crs.py`
- `tests/test_external_benchmark_stage1.py`
- `tests/test_security_standards_mapping.py` — traversal + direct-sensitive relationship regression 추가
- `docs/design/101_external_security_benchmark_design.md`

`src/security_standards_mapping.py`, Stage1 evaluator와 schemas는 변경하지 않는다.

### 14.2 Separate 930100/3 classification annotation review

Mapping alignment와 논리적으로 분리된 작은 follow-up으로 처리한다. 같은 manifest/test 파일을 만질 수 있어 implementation 순서는 classification review를 먼저 끝내고 Phase 5B-3M-F를 한 번에 적용하는 편이 churn이 적다.

### 14.3 No schema expansion

Current semantics로 충분하다.

```text
required must exist
forbidden must not exist
additional non-forbidden is allowed
```

Optional IDs를 열거하는 새 field나 relationship-specific exception list는 만들지 않는다.

## 15. Downstream impact

### 15.1 Recommended manifest-only correction

- Production `standards_mapping` output: unchanged
- Security Standards Summary CWE-552/WSTG-CONF-04 count: unchanged
- Stage2 copy-through: unchanged
- Viewer: unchanged
- Detection verdict/severity/confidence: unchanged
- External benchmark mapping metric: corrected to measure approved taxonomy semantics rather than blanket primary-only policy

### 15.2 Rejected mapper-refinement alternative

Mapper에서 cross-category enrichment를 제거했다면 다음 chain이 모두 달라졌을 것이다.

```text
Stage1 standards_mapping
  -> Stage2 copy-through
  -> Security Standards Summary aggregation
  -> Viewer rows/counts
```

CWE-552 conditional과 WSTG-CONF-04 related counts가 줄어들며 detection verdict/severity/confidence는 변하지 않아야 한다. 이 wider regression cost는 mapper 변경을 피하는 결정 근거가 아니라 영향 설명이다. Mapper를 유지하는 핵심 근거는 taxonomy/relationship semantics다.

## 16. Answers to the required questions

1. **CWE-552 conditional은 traversal + sensitive target에 의미상 타당한가?** Yes. Sensitive-target axis가 accessibility weakness hypothesis를 만들고, actual accessibility는 missing condition으로 남는다.
2. **단순 sensitive target 요청만으로도 CWE-552 conditional이 타당한가?** Raw 문자열 하나만으로는 no. Security-suspicious verdict와 structured direct-sensitive Prepare evidence가 있으면 conditional relationship으로는 yes; confirmed weakness로는 no.
3. **WSTG-CONF-04 related는 같은 case에서 타당한가?** Yes. Primary traversal scenario는 WSTG-ATHZ-01이지만, 민감한 unreferenced/system resource review context는 related enrichment로 유효하다.
4. **CWE-552와 WSTG-CONF-04를 서로 다르게 취급할 근거가 있는가?** Relationship은 다르게 해야 한다: CWE weakness는 conditional, WSTG test scenario는 related. 그러나 하나만 forbidden으로 만들 근거는 없다.
5. **Current mapper cross-category rule은 intentional인가 accidental인가?** Intentional이다. Implementation 전 design, implementation commit과 cross-category policy가 이를 명시한다. Traversal-sensitive 전용 unit test가 없었던 것은 coverage gap이다.
6. **Current manifest의 CWE-552 forbidden은 너무 강한가?** Direct-sensitive evidence가 있는 case에서는 yes. Pure traversal에서는 유지 가능하다.
7. **Pure traversal과 sensitive-target traversal의 forbidden policy를 다르게 해야 하는가?** Yes. Case-specific policy가 evidence contract와 일치한다.
8. **4 controlled mapping failures는 mapper bug인가 manifest mismatch인가?** Manifest mismatch다. `930100/3`에는 별도의 classification annotation 문제도 있다.
9. **930100/3 classification problem은 별도 review로 분리해야 하는가?** Yes. Mapping policy를 classification annotation에 끌려가게 해서는 안 된다.
10. **Live Stage1 baseline 전에 무엇을 수정해야 하는가?** Phase 5B-3M-F manifest/test/docs alignment와 `930100/3` classification annotation review를 먼저 완료해야 한다.

## 17. Live baseline go/no-go

**Current state: no-go for a publishable single live baseline.**

Runner를 기술적으로 실행할 수는 있지만, known manifest contradiction 때문에 mapping metric이 오염되고 `930100/3` exact annotation도 current Prepare evidence와 충돌한다. 다음 순서가 맞다.

1. `930100/3` classification annotation review를 완료한다.
2. Phase 5B-3M-F에서 case-specific mapping forbidden을 정렬한다.
3. Controlled fixture가 compatible cases의 mapping contract를 모두 만족하는지 확인한다.
4. 그 다음 single live Stage1 baseline을 실행한다.

이 alignment가 끝나면 production mapper/Stage1 code 변경 없이 single live baseline으로 진행할 수 있다.

## 18. Final recommendation

```text
A. production mapper 유지 + manifest case-specific correction
```

정책 이름으로는 **Policy B — Orthogonal evidence enrichment**다. Primary traversal mapping을 required로 유지하고, structured direct-sensitive evidence가 있는 case에서 CWE-552 conditional과 WSTG-CONF-04 related를 optional/non-forbidden으로 허용한다. Pure traversal의 CWE-552 forbidden은 유지한다.

Benchmark manifest는 production output snapshot을 따라가는 것이 아니라 project-approved semantics를 표현해야 한다. 이번에는 production output과 independent taxonomy review가 같은 결론을 가리킨다. Mapper가 현재 CWE-552를 출력한다는 사실이나 controlled score가 올라간다는 사실은 결정 근거로 사용하지 않는다.
