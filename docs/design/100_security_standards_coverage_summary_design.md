# Security Standards Coverage Summary 상세 설계

## 1. 목적

이 문서는 finding별 `standards_mapping`을 전체 분석 단위로 집계하는 deterministic summary의 의미, artifact contract, 계산 경계, Viewer/report 통합 방식을 고정한다.

내부 기능명은 `security_standards_summary`를 사용한다. `coverage summary`는 개발 단계의 편의 명칭으로만 사용한다. 사용자 화면에서는 OWASP Top 10 전체를 검사했거나 compliance를 평가했다는 뜻으로 오해될 수 있으므로 `Security Standards Summary`, `OWASP-related Observed Categories`, `Observed Standards Mapping`을 사용한다.

핵심 목표는 다음과 같다.

- OWASP Top 10 category별로 연결된 distinct finding 수를 계산한다.
- `direct`, `conditional`, `related` relationship별 distinct finding 수를 계산한다.
- CWE와 WSTG 상세 breakdown을 같은 contract로 제공한다.
- 한 finding의 mapping item 수와 finding 수를 분리한다.
- Stage1 raw result row와 Stage2 deduplicated incident를 분리한다.
- Viewer, dashboard, deterministic report가 재사용할 수 있는 summary object를 정의한다.
- 어떤 count도 confirmed vulnerability, weakness, exploit success, compliance를 뜻하지 않도록 표현 경계를 고정한다.

## 2. Non-goals

이번 Phase 4A에서는 다음을 구현하지 않는다.

- Python summary module 또는 pipeline 코드
- Viewer HTML, CSS, JavaScript
- Stage1/Stage2 prompt 변경
- DB schema 또는 migration
- 새 OWASP/CWE/WSTG mapping rule
- L3 hint mapping
- incident 내부 여러 Stage1 row의 standards mapping union
- 외부 공개 dataset 평가
- precision, recall 또는 coverage score 계산

이 문서는 semantics, artifact contract, integration design, 향후 regression specification만 정의한다.

## 3. 현재 standards mapping 구조

최신 HEAD `8a7d18a`에서 확인한 실제 흐름은 다음과 같다.

```text
Prepare analysis_candidates
  -> Stage1 classification result row
  -> deterministic standards_mapping enrichment
  -> Stage2 request_id/fallback-key incident deduplication
  -> representative row selection
  -> top_incidents projection
  -> Viewer finding copy-through
  -> reports route sanitizer
  -> payload_detail.html finding detail
```

구체적인 책임은 다음과 같다.

- [`src/security_standards_mapping.py`](../../src/security_standards_mapping.py)는 `security_standards_mapping.v1`을 생성한다. 새 공격을 탐지하지 않고 Stage1 verdict와 Prepare reason hint를 taxonomy/test-scenario metadata로 변환한다. 동일 `(standard, id)`는 `direct > conditional > related`로 정리하고 `OWASP_TOP10`, `CWE`, `WSTG` 순으로 정렬한다.
- [`src/llm_stage1_classifier.py`](../../src/llm_stage1_classifier.py)는 classification 성공 row마다 `build_security_standards_mapping(row, candidate)`를 호출해 `standards_mapping`을 Stage1 artifact에 저장한다.
- [`src/llm_stage2_reporter.py`](../../src/llm_stage2_reporter.py)의 `dedup_stage1_results()`는 `request_id`를 우선하고, 없으면 `src_ip + method + uri + status_code + 1초 time bucket`으로 incident를 묶는다. `security > error > access`, severity, confidence, score, time 우선순위로 representative를 선택한다.
- Stage2는 representative의 `standards_mapping`만 `IncidentBrief`에 copy-through한다. 중복 row의 mapping을 union하지 않는다. 이 정책은 현재 test에서도 명시적으로 보호된다.
- `build_report_input()`은 전체 dedup 결과로 `distinct_incident_count`와 분포를 만들지만, 실제 `top_incidents`는 CLI `--top-incidents`에 의해 기본 12건으로 제한된다.
- [`src/viewer_payload_builder.py`](../../src/viewer_payload_builder.py)는 `stage2_report_input.top_incidents`가 있으면 이를 finding source로 사용한다. 없으면 Stage1 results, 그마저 없으면 Prepare candidates로 fallback한다. 따라서 현재 `viewer_payload.findings`는 정상 경로에서 전체 incident가 아니라 top-N일 수 있다.
- Viewer builder의 mapping normalization은 mapping object와 dict item을 보존하는 copy-through 수준이다. 새 mapping을 계산하지 않는다.
- [`web/routes/reports.py`](../../web/routes/reports.py)는 finding을 최대 200개까지 sanitize하며 유효한 `standards_mapping.items` list를 보존한다.
- DB-backed `/job/{id}/viewer`와 legacy `/report/{id}/payload`는 모두 [`web/templates/payload_detail.html`](../../web/templates/payload_detail.html)을 사용한다. 현재 finding detail의 `Interpretation Aid` 다음, `Evidence` 앞에 `Security Standards`가 표시된다.
- [`web/services/report_loader.py`](../../web/services/report_loader.py)의 Viewer summary는 finding/context/supporting event count와 preview만 추출한다. 전체 standards summary contract는 아직 없다.

따라서 다음 두 값은 현재 구조에서 다를 수 있다.

```text
pipeline_counts.distinct_incident_count
!= len(stage2_report_input.top_incidents)
== len(viewer_payload.findings)  # 정상 top_incidents 경로에서만
```

이 차이 때문에 전체 분석의 standards summary를 현재 Viewer finding 배열만으로 계산해서는 안 된다.

## 4. Coverage terminology

### 4.1 내부와 사용자-facing 명칭

내부 코드, schema, 설계 이슈에서는 `security_standards_summary` 또는 “coverage summary”를 사용할 수 있다. 사용자 화면에서는 다음을 권장한다.

- 전체 section: `Security Standards Summary`
- OWASP section: `OWASP-related Observed Categories`
- 한국어: `보안 표준 요약`, `OWASP 관련 관찰 범주`
- CWE: `CWE Mapping Breakdown`
- WSTG: `Related WSTG Test Scenarios`

다음 표현은 사용하지 않는다.

- `OWASP Coverage Score`
- `OWASP Compliance`
- `OWASP Test Coverage`
- `OWASP Vulnerabilities Detected`
- `Detected OWASP Vulnerabilities`
- `확인된 OWASP 취약점`
- `발견된 OWASP 취약점`
- `WSTG vulnerabilities`
- `WSTG issues detected`

### 4.2 Observed와 observable

`Observed category`는 실제 finding mapping item이 생성된 category다. `Observable by Apache logs-only`는 해당 category를 현재 로그 표면에서 어느 정도 평가할 수 있는지에 관한 별도 capability 문제다.

0건 또는 row 부재는 다음 어느 것도 뜻하지 않는다.

- 해당 취약점이 없다.
- 해당 category를 충분히 검사했다.
- target이 안전하다.
- 로그 기반 탐지 coverage가 완전하다.

Phase 4 summary는 observed mapping만 요약하며 observability capability matrix를 만들지 않는다.

## 5. Counting unit

### 5.1 후보 비교

| 후보 | 장점 | 문제 | 결정 |
| --- | --- | --- | --- |
| Stage1 raw result row | 모든 classification row를 직접 반영 | access/security duplicate로 inflation 가능, 사용자-facing incident 의미와 불일치 | 사용하지 않음 |
| Stage2 deduplicated incident | 기존 dedup 책임과 report 의미를 재사용, duplicate inflation 방지 | representative-only mapping 정책 영향을 받음 | canonical counting unit |
| Viewer finding | 현재 보이는 row와 가까움 | top-N cap과 fallback 때문에 전체 분석과 불일치, presentation layer 결합 | 계산 입력으로 사용하지 않음 |

### 5.2 최종 결정

```text
coverage counting unit
= one Stage2 deduplicated incident
= user-facing deduplicated finding
```

artifact의 canonical 값은 다음으로 한다.

```json
"counting_unit": "deduplicated_finding"
```

여기서 `deduplicated_finding`은 현재 Stage2 `dedup_stage1_results()`가 만든 incident 하나를 Viewer 용어로 표현한 것이다. raw row, context-only summary, supporting event, noise group은 count에 포함하지 않는다.

summary scope는 top-N이 아니라 전체 dedup 결과다.

```json
"scope": "all_stage2_deduplicated_incidents"
```

대표 row만 사용하는 현재 Stage2 정책을 그대로 따른다. 같은 incident의 비대표 row에만 있는 mapping은 합치지 않는다. incident-level standards mapping union은 별도 기능이며 이번 설계의 non-goal이다.

## 6. Finding identity

summary function의 입력은 이미 deduplicated된 finding sequence다. sequence의 각 유효 element가 하나의 distinct finding이다.

```text
input findings are already deduplicated incidents
one valid input element = one finding identity
```

summary layer는 `request_id`, `incident_ref`, `dedup_key`, fingerprint로 재-dedup하지 않는다. 이유는 다음과 같다.

- 기존 Stage2 dedup 정책을 single owner로 유지한다.
- summary module에 두 번째 incident grouping implementation을 만들지 않는다.
- Viewer ID 누락이나 old artifact shape 때문에 count가 달라지는 것을 피한다.
- future dedup 정책 변경 시 summary가 자동으로 그 결과를 따른다.

같은 finding object 또는 같은 `incident_ref`가 입력 sequence에 두 번 있으면 두 건으로 계산한다. 이는 summary가 고칠 오류가 아니라 caller contract 위반이다. integration test에서 Stage2 dedup 결과만 전달됨을 검증한다.

non-mapping element는 유효 finding으로 볼 수 없으므로 total에서 제외하고 diagnostics의 `invalid_finding_count`만 증가시킨다. 하나의 malformed element 때문에 전체 생성을 실패시키지 않는다.

## 7. Standard identity

finding 내부 distinct standard identity는 다음 tuple이다.

```text
(normalized standard, normalized id)
```

- `standard`: non-empty string, trim 후 uppercase. 예: `OWASP_TOP10`, `CWE`, `WSTG`, `ASVS`.
- `id`: non-empty string, trim만 수행하고 case는 보존한다.
- `name`: identity가 아니며 count를 분리하지 않는다.

예:

```text
(OWASP_TOP10, A01:2025)
(CWE, CWE-22)
(WSTG, WSTG-ATHZ-01)
```

동일 finding 안에서 같은 identity가 여러 번 나타나도 그 standard row의 `finding_count`에는 한 번만 반영한다.

known identity의 name은 current standards mapping registry의 canonical name을 우선한다. unknown identity는 관찰된 non-empty name 중 lexical minimum을 사용해 입력 순서 변화에도 deterministic하게 만들고, name이 전혀 없으면 id를 fallback으로 사용한다. 이름 차이는 identity를 분리하지 않는다.

## 8. Relationship counting

canonical relationship enum은 다음 세 값이다.

```text
direct
conditional
related
```

각 finding 안에서 identity별로 먼저 중복을 정리한다.

```text
direct > conditional > related
```

그 후 standard row마다 다음을 독립적으로 계산한다.

- `finding_count`: identity가 연결된 distinct input finding 수
- `relationship_counts.direct`: 최종 relationship이 direct인 distinct finding 수
- `relationship_counts.conditional`: 최종 relationship이 conditional인 distinct finding 수
- `relationship_counts.related`: 최종 relationship이 related인 distinct finding 수

예:

```json
{
  "id": "A05:2025",
  "name": "Injection",
  "finding_count": 7,
  "relationship_counts": {
    "direct": 6,
    "conditional": 0,
    "related": 1
  }
}
```

v1 producer는 유효 item과 strongest-wins 정규화 후 한 identity/finding에 relationship 하나를 부여하므로 세 relationship count의 합이 `finding_count`와 같아진다. 그러나 `finding_count`는 별도 distinct-finding 집계값이며 consumer는 relationship 합으로 이를 재구성하거나 future schema에서도 equality가 유지된다고 가정하지 않는다.

relationship은 trim 후 lowercase한다. enum 밖의 값은 의미를 추정하지 않고 해당 item을 skip하며 `skipped_mapping_item_count`에 반영한다. unknown relationship을 `related`로 낮춰 세면 원본 의미를 바꾸므로 금지한다.

UI 설명은 색상과 함께 텍스트로 제공한다.

- Direct: observed pattern과 taxonomy/test scenario의 직접 의미 대응. confirmed vulnerability나 success가 아님.
- Conditional: 추가 evidence가 있어야 weakness/category 연결이 강해짐.
- Related: 관련 category/test scenario 문맥이며 직접 vulnerability attribution이 아님.

## 9. Multi-category findings

하나의 finding이 서로 다른 standard 또는 같은 standard의 여러 ID에 연결되는 것은 정상이다.

```text
Finding X
  A01:2025 related
  A05:2025 direct
```

이 경우 다음처럼 계산한다.

```text
mapped_finding_count += 1
A01:2025 finding_count += 1
A05:2025 finding_count += 1
```

따라서 OWASP category별 `finding_count` 합은 `mapped_finding_count`보다 클 수 있다. 다음 계산은 금지한다.

```text
total OWASP findings = sum(each OWASP category finding_count)
```

UI에는 다음 help text를 항상 제공한다.

> A single finding may map to more than one standards category. Category counts should not be summed as a total incident count.

한국어 UI에서는 “하나의 finding이 둘 이상의 표준 범주에 연결될 수 있으므로 범주별 건수를 전체 incident 수로 합산하지 않습니다.”라는 의미를 유지한다.

## 10. Mapped/unmapped semantics

### 10.1 Top-level count 정의

- `total_finding_count`: summary에 전달된 유효 deduplicated finding 수
- `mapped_finding_count`: validation과 finding-local dedupe 이후 유효 mapping item이 하나 이상인 distinct finding 수
- `unmapped_finding_count`: 유효 mapping item이 하나도 없는 distinct finding 수

항상 다음 invariant를 만족한다.

```text
mapped_finding_count + unmapped_finding_count = total_finding_count
```

`standards_mapping.items=[]`, mapping field 부재, malformed mapping, 모든 item이 invalid인 finding은 모두 `unmapped_finding_count`에 포함된다. diagnostics로 원인을 구분할 수 있지만 사용자-facing primary metric에서는 안전 판정으로 표현하지 않는다.

### 10.2 Non-security verdict와 generic scan

Stage2 dedup 결과에 `benign_normal`, `likely_false_positive`, `inconclusive` 또는 유효 standards item이 없는 generic scan이 있으면 `total_finding_count`에는 포함하고 standard category count에는 포함하지 않는다. 유효 item이 없으므로 unmapped다.

다음 label은 사용하지 않는다.

- `safe_findings`
- `secure_findings`
- `non_vulnerable_findings`

`unmapped`의 정확한 의미는 “해당 deterministic standards enrichment layer에서 유효 item이 생성되지 않은 deduplicated finding”이다. 안전, 취약점 부재, 검사 완료를 뜻하지 않는다.

## 11. Observability counting

observability는 standard category count와 별개의 finding-level dimension이다. 한 finding이 여러 standard item을 가져도 한 번만 센다.

```json
"observability_counts": {
  "attempt_only": 6,
  "behavior_only": 3,
  "partial": 0,
  "not_applicable": 3
}
```

정책은 다음과 같다.

- mapping object의 `observability`를 trim/lowercase하여 현재 enum과 일치하면 해당 bucket에 finding 한 건을 더한다.
- mapping field 부재, malformed mapping, unknown observability는 보수적 fallback으로 `not_applicable`에 한 건을 더한다.
- unknown observability는 malformed diagnostics에도 반영한다.
- 네 bucket의 합은 `total_finding_count`와 같다.

이 값은 attack success나 severity가 아니라 Apache logs-only evidence scope를 설명한다. Viewer에서는 secondary breakdown 또는 help 영역으로 두고 OWASP category보다 강조하지 않는다.

## 12. OWASP summary

OWASP Top 10을 primary summary로 사용한다. category 수가 작고 presentation에서 이해하기 쉽기 때문이다.

기본 제목은 `OWASP-related Observed Categories`다. row는 id, canonical name, distinct finding count, relationship counts를 표시한다.

0 count category는 artifact row로 만들지 않고 화면에도 기본 표시하지 않는다. A01~A10을 모두 표시하면 “모든 category를 검사했으며 나머지는 발견되지 않았다”는 잘못된 인상을 줄 수 있다.

이 summary는 OWASP Top 10 risk/category 관계 요약이며 취약점 탐지 결과, 검사 coverage, compliance 결과가 아니다.

## 13. CWE summary

CWE는 primary dashboard score가 아니라 상세 breakdown으로 제공한다.

권장 표현:

```text
CWE Mapping Breakdown
CWE-89 · SQL Injection
Findings: 3
Direct: 3
```

help text는 다음 의미를 유지한다.

> CWE mappings represent taxonomy relationships to observed patterns, not confirmed weaknesses in the target application.

CWE row count는 confirmed weakness count가 아니다.

## 14. WSTG summary

WSTG는 반드시 test-scenario 관계로 표현한다.

권장 표현:

```text
Related WSTG Test Scenarios
WSTG-INPV-05
Testing for SQL Injection
Findings: 3
Direct: 3
```

WSTG ID를 vulnerability ID 또는 detected issue로 표현하지 않는다.

## 15. Artifact schema

### 15.1 권장 contract

summary는 Stage2 report input과 Viewer payload에서 같은 object shape를 사용한다.

```json
{
  "security_standards_summary": {
    "schema_version": "security_standards_summary.v1",
    "source": "deterministic_security_standards_summary",
    "counting_unit": "deduplicated_finding",
    "scope": "all_stage2_deduplicated_incidents",
    "total_finding_count": 12,
    "mapped_finding_count": 9,
    "unmapped_finding_count": 3,
    "observability_counts": {
      "attempt_only": 6,
      "behavior_only": 3,
      "partial": 0,
      "not_applicable": 3
    },
    "standards": {
      "OWASP_TOP10": [
        {
          "id": "A01:2025",
          "name": "Broken Access Control",
          "finding_count": 4,
          "relationship_counts": {
            "direct": 3,
            "conditional": 0,
            "related": 1
          }
        }
      ],
      "CWE": [],
      "WSTG": [],
      "ASVS": [
        {
          "id": "V5.3.1",
          "name": "V5.3.1",
          "finding_count": 1,
          "relationship_counts": {
            "direct": 0,
            "conditional": 0,
            "related": 1
          }
        }
      ]
    },
    "diagnostics": {
      "invalid_finding_count": 0,
      "missing_mapping_finding_count": 0,
      "malformed_mapping_finding_count": 0,
      "skipped_mapping_item_count": 0
    }
  }
}
```

### 15.2 구조 선택

`standards`를 array of groups가 아니라 standard key의 object로 둔다.

- known consumer가 `OWASP_TOP10`, `CWE`, `WSTG`를 직접 찾기 쉽다.
- unknown future standard를 같은 shape로 보존할 수 있다.
- row에 standard 값을 반복하지 않아도 된다.
- 세 known key는 row가 없어도 빈 array로 항상 제공한다. 이는 category 0 row를 만든다는 뜻이 아니다.

`source`는 mapping source인 `deterministic_stage1_enrichment`와 구분하기 위해 `deterministic_security_standards_summary`로 한다.

diagnostics는 artifact/debug metadata이며 기본 UI에는 표시하지 않는다. count 이름은 finding-level invalid와 item-level skip을 구분한다.

### 15.3 Contract invariants

```text
mapped + unmapped = total
sum(observability_counts values) = total
each standards row finding_count <= total
each relationship count <= row finding_count
no duplicate id inside one standards group
no zero-count standards row
```

category row count의 standard 간 또는 category 간 합에는 global invariant를 두지 않는다.

## 16. Summary generation location comparison

### 16.1 Stage2 reporter 내부 계산

장점:

- 전체 `deduped_results`가 이미 존재한다.
- existing dedup 및 representative 정책과 정확히 일치한다.
- top-N cap 전에 계산할 수 있다.
- Stage2 artifact와 Viewer가 공유할 수 있다.

단점:

- summary를 `report_input`에 넣으면 현재 `build_messages()`가 전체 report input을 JSON으로 직렬화하므로 LLM에도 자동 전달된다.
- reporter 안에 집계 구현을 직접 넣으면 taxonomy summary 책임이 커진다.

### 16.2 Viewer payload builder 계산

장점:

- 최종 표시 artifact를 만들 때 계산한다.
- Stage2 LLM 입력에 summary를 넣지 않을 수 있다.

단점:

- 현재 Viewer source인 `top_incidents`는 기본 12건 cap이 있다.
- top_incidents가 비면 Stage1 raw row fallback을 사용하므로 counting unit이 바뀔 수 있다.
- 전체 분석 summary가 presentation artifact에 종속된다.
- report/dashboard consumer가 별도로 재계산해야 한다.

전체 summary의 canonical 계산 위치로는 부적합하다.

### 16.3 별도 pure module

장점:

- deterministic semantics와 presentation을 분리한다.
- malformed/unknown/ordering을 집중적으로 unit test할 수 있다.
- Stage2, Viewer, future deterministic Markdown에서 동일 contract를 재사용한다.
- 네트워크, DB, LLM 의존성이 없다.

단점:

- module 하나가 추가된다.
- caller가 반드시 dedup 완료 sequence를 전달해야 한다.

### 16.4 최종 권고

[`src/security_standards_summary.py`](../../src/security_standards_summary.py)라는 pure module을 추가하고, Stage2 `build_report_input()`에서 전체 `deduped_results`가 만들어진 직후 호출한다.

```text
Stage2 dedup owner
  -> all deduped representative incidents
  -> pure security standards summary
  -> stage2_report_input.security_standards_summary
  -> viewer_payload.security_standards_summary copy-through
```

project 규모에 비해 과한 추상화가 아니다. current mapping 자체가 이미 별도 deterministic module이고, Viewer finding 배열의 top-N cap 때문에 집계 위치와 표시 위치를 분리해야 하기 때문이다.

## 17. Recommended module/function contract

권장 public function은 다음이다.

```python
def build_security_standards_summary(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ...
```

`summarize_security_standards()`도 가능하지만 기존 `build_security_standards_mapping()` naming과 맞추기 위해 `build_..._summary`를 우선한다.

입력 contract:

- sequence는 이미 Stage2 policy로 deduplicated되어 있다.
- 각 finding의 mapping 위치는 `finding["standards_mapping"]`이다.
- context-only object와 supporting event는 전달하지 않는다.
- representative-only mapping을 사용하며 sibling row union을 수행하지 않는다.
- generator가 아니라 `Sequence`를 받는 이유는 total count와 deterministic multi-pass test를 명확히 하기 위함이다.

처리 순서:

1. 유효 mapping finding을 순회하고 non-mapping finding을 skip한다.
2. mapping object, `items` list, mapping-level observability를 validate한다.
3. finding-local identity map을 만든다.
4. 동일 identity conflict에 strongest relationship precedence를 적용한다.
5. finding-local 결과를 global standard buckets에 한 번씩 반영한다.
6. mapped/unmapped와 observability를 finding 단위로 반영한다.
7. canonical name을 결정하고 stable order로 materialize한다.
8. 항상 완전한 v1 object를 반환한다.

함수는 입력을 mutate하지 않으며 예외를 finding 단위로 격리한다. 예상하지 못한 programming error까지 광범위하게 숨기기보다는 known type/normalization error만 방어한다.

## 18. Stable ordering

artifact order와 UI presentation sort를 분리한다.

artifact order:

1. standard group: `OWASP_TOP10`, `CWE`, `WSTG`, 이후 unknown standard name lexical ascending
2. OWASP: `A01`, `A02`, ... category number ascending, year ascending, raw id lexical fallback
3. CWE: `CWE-N`의 N numeric ascending, 형식이 다른 id는 뒤에서 lexical ascending
4. WSTG: id lexical ascending
5. unknown standard: id lexical ascending
6. `relationship_counts` key: `direct`, `conditional`, `related`
7. `observability_counts` key: `attempt_only`, `behavior_only`, `partial`, `not_applicable`

JSON object key order는 semantic contract가 아니지만 producer는 위 순서로 직렬화해 diff와 snapshot을 안정화한다.

UI는 이해하기 쉽게 각 group을 `finding_count` descending, artifact id order tie-break로 표시할 수 있다. UI sort는 artifact를 mutate하거나 summary JSON 의미를 바꾸지 않는다.

## 19. Unknown/malformed handling

### 19.1 Unknown future standard

다음 item은 valid generic mapping으로 보존한다.

```json
{
  "standard": "ASVS",
  "id": "V5.3.1",
  "relationship": "related"
}
```

unknown standard는 known group 뒤에 별도 key로 저장하고 mapped finding으로 센다. UI는 `Other Standards Mappings` 아래 known group 뒤에 표시할 수 있다. unknown standard 때문에 generation이 실패하거나 item을 버리지 않는다.

### 19.2 Malformed finding/mapping

| 입력 | 처리 |
| --- | --- |
| sequence element가 Mapping 아님 | total에서 제외, `invalid_finding_count += 1` |
| `standards_mapping` field 없음 | unmapped, `missing_mapping_finding_count += 1` |
| `standards_mapping`이 `None` | old/missing과 같이 unmapped, missing count 증가 |
| mapping이 dict가 아님 | unmapped, malformed count 증가 |
| `items`가 list가 아님 | unmapped, malformed count 증가 |
| item이 dict가 아님 | item skip, skipped item count 증가 |
| standard 또는 id 누락/empty/non-string | item skip |
| relationship 누락 또는 enum 밖 | item skip |
| name 누락 | canonical registry 또는 id fallback |
| observability enum 밖 | `not_applicable`, malformed count 증가 |

`standards_mapping={}`는 mapping object는 있으나 `items`가 없으므로 malformed로 분류한다. valid empty v1 mapping은 반드시 `items: []`를 가진다.

malformed mapping에 valid item과 invalid item이 섞여 있으면 valid item은 보존한다. finding은 valid item이 하나 이상이면 mapped다. `malformed_mapping_finding_count`는 finding당 최대 한 번 증가하고 `skipped_mapping_item_count`는 skip한 item 수를 센다.

## 20. Backward compatibility

- 기존 `security_standards_mapping.v1` item을 그대로 입력으로 지원한다.
- standards mapping field가 없는 old Stage1/Stage2 finding은 unmapped로 처리하고 generation을 중단하지 않는다.
- 기존 old `viewer_payload.v1`에 `security_standards_summary`가 없으면 Viewer는 section을 숨긴다. 이를 “0 mapped”로 합성하지 않는다. field 부재는 summary가 계산되지 않았다는 뜻이지 관찰 category가 0이라는 뜻이 아니다.
- summary는 자체 `schema_version`을 가지므로 additive optional top-level field만 추가할 때 parent `viewer_payload.v1`을 즉시 올릴 필요는 없다. 실제 구현 시 strict external consumer가 없는지 compatibility test로 확인한다.
- consumer는 unknown standard group과 unknown future fields를 무시하되 known data는 계속 표시해야 한다.
- consumer는 모르는 `security_standards_summary` major version을 임의로 해석하지 않고 section을 안전하게 숨기거나 unsupported state로 표시한다.
- Stage2 representative-only policy는 유지한다. old/future artifact의 sibling mapping union을 암묵적으로 도입하지 않는다.

## 21. UI terminology

권장 summary 예시는 다음과 같다.

```text
Security Standards Summary

Mapped findings        9 / 12 deduplicated findings

OWASP-related Observed Categories

A01:2025 Broken Access Control
4 findings
Direct 3 · Related 1

A05:2025 Injection
7 findings
Direct 6 · Related 1
```

필수 boundary/help text:

- Mappings describe relationships between observed patterns and standards taxonomies/test scenarios.
- They do not confirm vulnerabilities, weaknesses, compliance, or successful exploitation.
- A single finding may map to multiple categories; category counts must not be summed as total incidents.
- Unmapped means this enrichment layer assigned no valid standards item, not that the finding or target is safe.

relationship은 badge 색상만으로 전달하지 않는다. label과 설명을 함께 제공하고 keyboard/screen-reader에서도 같은 정보를 읽을 수 있어야 한다.

`Mapped findings 9 / 12`의 denominator는 Viewer에 현재 표시된 top-N row 수가 아니라 `total_finding_count`다. Viewer finding list가 cap되었다면 “Summary covers all 12 deduplicated findings; timeline displays 10 selected findings.”처럼 scope 차이를 표시한다.

## 22. Viewer placement

현재 layout에서 가장 자연스러운 위치는 상단 summary cards 다음, LLM `Report Summary`와 `Event Timeline` 앞이다.

```text
Viewer header
-> existing total/findings/contexts/supporting cards
-> Security Standards Summary (new deterministic section)
-> Report Summary (existing LLM artifact text)
-> Event Timeline + selected finding detail
```

이 위치를 권고하는 이유는 다음과 같다.

- 전체 분석 metadata라는 성격이 finding detail보다 상위다.
- deterministic summary와 LLM narrative를 시각적으로 구분할 수 있다.
- finding list와 가까워 drill-down 문맥을 유지한다.
- 새 navigation이나 tab 없이 current responsive layout을 확장할 수 있다.

OWASP는 section에서 바로 표시한다. CWE/WSTG는 같은 card의 접을 수 있는 detail로 시작한다. observability와 unknown standards도 secondary detail로 둔다. 별도 Standards tab은 category filtering/drill-down 요구가 커질 때 future extension으로 남긴다.

현재 `reports.py` sanitizer와 DB-backed/legacy route가 같은 template에 서로 다른 summary path로 진입하므로, 구현 시 `sanitize_security_standards_summary()`를 공용으로 두고 template context에 정규화된 object를 명시적으로 전달한다. raw top-level dict를 template이 직접 신뢰하지 않는다. artifact 자체는 semantic truncation을 하지 않되 web display sanitizer는 비정상적으로 큰 unknown group/row 입력을 bounded하게 처리하고 integrity warning을 남길 수 있다.

## 23. Stage2 integration policy

summary 계산 hook은 Stage2의 전체 `deduped_results` 직후가 canonical이다. 그러나 Phase 4 first implementation에서는 summary를 Stage2 LLM narrative 입력으로 보내지 않는다.

현재 `build_messages()`는 `report_input` 전체를 user payload에 넣으므로 단순히 field를 추가하면 자동 전달된다. 구현 시 다음 projection 경계를 명시적으로 둔다.

```text
artifact report_input
  includes security_standards_summary

LLM report_input projection
  excludes security_standards_summary
  keeps existing top_incidents[].standards_mapping behavior unchanged
```

즉 per-finding mapping에 대한 현재 interpretation boundary는 유지하되 새 aggregate summary는 LLM에 추가하지 않는다. summary는 deterministic UI metadata이며 LLM이 category 합을 incident total로 오해하거나 narrative를 과장할 필요가 없다. 이를 위해 prompt 문구를 추가하는 대신 message 직렬화 전에 aggregate field를 제외하는 explicit projection을 사용한다.

Stage2 report input artifact에는 summary를 저장하고 Viewer builder는 이를 top-level `security_standards_summary`로 exact copy-through한다. Viewer builder가 current top-N findings에서 다시 계산하지 않는다.

## 24. Markdown/report policy

Phase 4 첫 구현은 Viewer summary를 우선한다.

- Stage2 LLM-generated paragraph: 도입하지 않음
- Stage2 LLM output schema의 narrative field: 추가하지 않음
- deterministic Markdown section: Phase 4B-4에서 선택적으로 추가
- report/dashboard reuse: 동일 summary object를 읽는 deterministic consumer로만 확장

향후 Markdown에 넣을 경우 LLM에 서술을 맡기지 않고 `security_standards_summary`를 deterministic renderer가 표/목록으로 출력한다. Viewer와 같은 label, relationship 설명, multi-category 합산 금지 문구를 사용한다.

Stage2 JSON report에 copy할 필요가 생기면 LLM `report` object 내부가 아니라 deterministic top-level sibling으로 둔다. DB column이나 migration은 필요하지 않으며 artifact reader가 optional field를 읽는다.

## 25. Regression test specification

### 25.1 Pure summary unit tests

| Test | 핵심 기대값 |
| --- | --- |
| single SQLi finding | A05/CWE-89/WSTG-INPV-05 각각 finding 1, direct 1, mapped 1/total 1 |
| two Injection findings | A05 finding 2, direct 2; mapping item 수가 아니라 finding 수 |
| one finding, multiple OWASP categories | mapped 1, A01 1, A05 1; category 합 2 허용 |
| duplicate standard/id | finding-local A01 두 item을 한 건으로 계산 |
| relationship precedence | A01 related + conditional + direct면 A01 finding 1/direct 1 |
| empty mapping | mapped 0, unmapped 1, standards row 없음 |
| missing mapping field | unmapped 1, missing diagnostic 1 |
| `standards_mapping=None` | generation 성공, missing/unmapped 처리 |
| mapping dict without items | malformed/unmapped 처리 |
| items string | malformed/unmapped 처리 |
| non-dict item | item skip, generation 지속 |
| missing standard/id | item skip |
| unknown standard | generic group 보존, mapped count 증가 |
| unknown relationship | item skip, related로 임의 변환하지 않음 |
| valid + invalid mixed items | valid row 보존, mapped finding, diagnostics 증가 |
| stable ordering | 입력 finding/item 순서를 뒤섞어도 동일 serialized logical output |
| numeric CWE ordering | CWE-22가 CWE-89보다 앞섬 |
| distinct finding vs item count | 한 finding의 5개 ID가 total/mapped 1임 |
| mapped/unmapped totals | mapped + unmapped = total |
| observability counts | finding당 한 bucket, 합이 total |
| invalid observability | not_applicable fallback 및 malformed diagnostic |
| invalid finding element | total 제외, invalid finding diagnostic |
| input immutability | 원본 finding/mapping을 변경하지 않음 |
| unknown name conflicts | 입력 순서와 무관한 deterministic name 선택 |

같은 `incident_ref`를 의도적으로 두 번 전달했을 때 summary가 재-dedup하지 않는 contract test도 둔다. 기대값은 2이며 caller 책임 분리를 문서화한다.

### 25.2 Stage2 integration tests

- access/security duplicate row가 하나의 incident로 집계된다.
- representative row mapping만 반영되고 sibling mapping은 union되지 않는다.
- `top_incidents=1`인데 전체 dedup incident가 3이면 summary `total_finding_count=3`이다.
- `pipeline_counts.distinct_incident_count`와 summary total이 일치한다.
- Stage2 report input artifact에는 summary가 있다.
- `build_messages()`의 serialized LLM payload에는 aggregate `security_standards_summary`가 없다.
- 기존 `top_incidents[].standards_mapping` copy-through와 interpretation boundary는 유지된다.

### 25.3 Viewer payload/route tests

- Viewer builder가 Stage2 summary를 값 변경 없이 top-level에 copy한다.
- Viewer finding top-N 수와 summary total이 달라도 warning/label이 정확하다.
- old Stage2 input에 summary가 없으면 Viewer payload field를 생략한다.
- Viewer builder가 finding list 또는 Stage1 fallback에서 summary를 재계산하지 않는다.
- run-dir loader, DB-backed job route, legacy report route가 같은 sanitized summary를 전달한다.
- malformed summary root/group/row/relationship counts가 template rendering을 실패시키지 않는다.
- unknown standard group을 known group 뒤에 표시한다.
- summary field가 없는 old Viewer artifact에서는 entire section을 숨기며 “0 observed”로 표시하지 않는다.
- sanitizer가 count를 non-negative integer로 제한하고 arbitrary nested content를 그대로 template에 넘기지 않는다.

### 25.4 UI tests

- section이 summary cards 다음, report overview/event timeline 앞에 표시된다.
- OWASP row, CWE detail, WSTG test-scenario label이 표시된다.
- Direct/Conditional/Related 설명이 색상 없이도 존재한다.
- multi-category 합산 금지 help text가 존재한다.
- vulnerability detected/compliance/coverage score 금지 문구가 나타나지 않는다.
- light/dark theme, mobile width, long unknown standard/id, zero/empty groups를 검증한다.
- keyboard로 CWE/WSTG details를 열 수 있고 accessible name이 제공된다.

### 25.5 Backward compatibility tests

- mapping field 없는 old Stage1 artifact
- `standards_mapping.v1` valid empty mapping
- summary field 없는 `viewer_payload.v1`
- unknown summary fields와 unknown standards group
- unsupported summary major version safe-hide
- existing security standards finding-detail regression 전부 통과

## 26. E2E-derived edge cases

최근 encoded traversal E2E에서 한 finding에 다음 item이 동시에 존재할 수 있었다.

```text
CWE-22 direct
CWE-552 conditional
WSTG-ATHZ-01 direct
WSTG-CONF-04 related
```

이는 네 mapping item이지 네 finding이 아니다.

```text
total_finding_count contribution = 1
mapped_finding_count contribution = 1
CWE-22 finding_count contribution = 1
CWE-552 finding_count contribution = 1
WSTG-ATHZ-01 finding_count contribution = 1
WSTG-CONF-04 finding_count contribution = 1
```

같은 finding이 여러 standard ID와 relationship에 연결되는 것은 정상이다. mapping item count를 finding count로 표시하거나 standard row 합을 incident total로 사용하지 않는다.

필수 예시는 다음과 같다.

### Case A: 같은 OWASP category의 두 finding

```text
Finding 1: A05 direct, CWE-89 direct, WSTG-INPV-05 direct
Finding 2: A05 direct, CWE-79 direct, WSTG-INPV-01 related
```

Expected:

```text
A05 finding_count=2, direct=2
CWE-89=1, CWE-79=1
WSTG-INPV-05 direct=1
WSTG-INPV-01 related=1
mapped_finding_count=2
```

### Case B: old duplicate relationship

```text
Finding: A01 direct, A01 related
```

Expected: `A01 finding_count=1`, `direct=1`, `related=0`.

### Case C: empty mapping

```text
Finding: items=[]
```

Expected: total 1, mapped 0, unmapped 1.

### Case D: multi-category

```text
Finding: A01 direct, A05 related
```

Expected: total/mapped 1, A01 1, A05 1.

## 27. Performance

summary generation은 다음 제약을 지킨다.

- LLM 호출 없음
- network 없음
- DB access 없음
- small in-memory aggregation
- 입력 mutation 없음

finding 수를 `F`, 전체 mapping item 수를 `M`, unique standard identity 수를 `U`라 하면 예상 시간 복잡도는 aggregation `O(F + M)`, materialization sort `O(U log U)`다. 메모리는 global bucket과 한 finding의 local dedupe map에 대해 `O(U + max items per finding)` 수준이다.

전체 row를 standard별 set으로 장기 보관할 필요는 없다. input이 이미 distinct finding sequence이므로 finding-local dedupe 후 integer counter를 증가시키면 된다.

## 28. Future extensions

다음은 v1 이후 별도 설계 대상으로 남긴다.

- category row에서 matching finding filter/drill-down
- deterministic Markdown standards section
- dashboard list의 compact OWASP badges
- observability capability matrix와 observed summary의 병렬 표시
- incident-level sibling mapping union 정책
- ASVS 등 새 standard 전용 renderer
- time-window 간 observed mapping trend
- zero category를 검사 가능성/불가능성과 함께 설명하는 별도 capability matrix

외부 dataset 평가와 이 summary를 혼합하지 않는다. OWASP CRS/WSTG, CSIC 2010 HTTP, ECML/PKDD 2007, CICIDS2017 기반 benchmark precision/recall은 모델/파이프라인 평가 지표다. `OWASP-related Observed Categories`는 현재 pipeline finding metadata 요약이다.

## 29. Implementation phases

### Phase 4B-1: pure contract implementation

- `src/security_standards_summary.py`
- `build_security_standards_summary()`
- identity/relationship/malformed/order unit tests
- schema invariant tests

### Phase 4B-2: Stage2 boundary와 artifact integration

- Stage2 전체 `deduped_results`에서 summary 계산
- `stage2_report_input.security_standards_summary` 저장
- LLM message projection에서 aggregate summary 제외
- Viewer payload top-level exact copy-through
- loader/routes sanitizer와 old artifact compatibility tests
- full dedup count와 top-N Viewer finding count 차이 검증

### Phase 4B-3: Viewer UI

- summary cards 아래 `Security Standards Summary` section
- OWASP primary rows
- CWE/WSTG secondary details
- relationship/help/boundary text
- unknown group fallback
- responsive, accessibility, light/dark regression

### Phase 4B-4: optional deterministic consumers

- optional deterministic Markdown section
- optional finding filter/drill-down
- optional report/dashboard compact projection
- LLM narrative 사용 여부는 별도 재검토

## 30. Final recommendation

최종 권고를 요약하면 다음과 같다.

1. counting unit은 Stage1 raw row나 current Viewer top-N row가 아니라 전체 Stage2 deduplicated incident다.
2. artifact에서는 이를 `counting_unit: deduplicated_finding`, `scope: all_stage2_deduplicated_incidents`로 명시한다.
3. `finding_count`는 해당 `(standard, id)`가 연결된 distinct input finding 수이며 mapping item 수가 아니다.
4. finding 내부 동일 identity는 `direct > conditional > related` strongest relationship 하나만 반영한다.
5. 한 finding이 여러 OWASP category에 연결되면 각 category에 한 건씩 반영하되 category count를 전체 incident total로 합산하지 않는다.
6. mapped/unmapped는 enrichment item 유무이며 취약점 확인/부재 또는 안전 판정이 아니다.
7. observability는 finding-level secondary dimension으로 포함한다.
8. pure summary module을 만들고 Stage2의 full dedup 직후 계산한다.
9. Stage2 artifact에서 Viewer로 exact copy-through하며 Viewer top-N 배열에서 재계산하지 않는다.
10. aggregate summary는 Phase 4 first implementation에서 LLM에 전달하지 않는다.
11. Viewer에서는 상단 metric cards 다음, LLM Report Summary와 Event Timeline 앞에 표시한다.
12. OWASP observed category만 기본 노출하고 CWE/WSTG는 상세 breakdown으로 제공한다.
13. old artifact에 summary가 없으면 0으로 합성하지 않고 section을 숨긴다.
14. optional Markdown은 같은 object를 deterministic하게 render하는 후속 단계로 둔다.
