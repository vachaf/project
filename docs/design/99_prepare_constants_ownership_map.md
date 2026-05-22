# 99_prepare_constants_ownership_map

- 문서 상태: prepare constants ownership map
- 기준 시점: 2026-05-04
- 목적: `src/prepare_llm_input.py`에 남아 있는 주요 constants의 예상 owner, 공유 여부, 이동 가능성, 보류 이유를 정리한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_summary.md](./99_prepare_module_split_round2_summary.md)
- round2 candidate review 내용은 [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md)에 흡수
- sensitive path / probing / mixed baseline / ip behavior 세부 split 기록은 [99_prepare_module_split_summary.md](./99_prepare_module_split_summary.md)에 흡수

## 1. 결론

지금은 `constants.py` 대량 분리를 진행하지 않는다.

현재까지 round1/round2에서 분리한 모듈은 많지만, constants는 여전히 여러 summary/helper가 공유한다. 특히 sensitive path, probing sequence, mixed baseline scanner, file disclosure, SQLi/XSS hint 계열은 서로 의미 경계가 겹칠 수 있다.

따라서 다음 원칙을 적용한다.

```text
- constants.py 대량 분리 금지
- 단일 owner가 명확한 constants만 이후 소규모 이동 검토
- 공유 constants는 prepare_llm_input.py에 유지
- 새 모듈이 필요한 값은 wrapper 인자로 전달
- import cycle 위험이 있으면 이동하지 않음
- constants 이동과 behavior 변경을 같은 커밋에 섞지 않음
```

## 2. import 방향 원칙

현재 구조에서 권장 import 방향은 아래다.

```text
src/prepare_llm_input.py
  -> src/prepare/<topic_module>.py
```

보류할 방향:

```text
src/prepare/<topic_module>.py
  -> src/prepare_llm_input.py
```

이 방향은 import cycle을 만들 수 있으므로 피한다.

constants를 이동하려면 아래 조건을 충족해야 한다.

```text
- 한 constants group의 owner module이 명확함
- 다른 prepare module에서 직접 참조하지 않음
- wrapper 인자 전달보다 모듈 내부 소유가 더 단순함
- py_compile과 regression에서 원인 추적이 쉬움
- output key, policy_notes, counts 의미가 바뀌지 않음
```

## 3. ownership map 요약

| 그룹 | constants | 예상 owner | 공유 여부 | 현재 판단 |
|---|---|---|---|---|
| source ordering | `SOURCE_PRIORITY`, `SOURCE_ORDER` | `prepare_llm_input.py` | 높음 | 유지 |
| decode limit | `DECODE_VARIANT_MAX_CHARS` | `decoders.py` 후보 | 중간 | 보류 |
| supporting/time context | `SUPPORTING_EVENT_TIME_WINDOW_SEC`, `TEMPORAL_CONTEXT_BUCKET_SEC` | `prepare_llm_input.py` | 높음 | 유지 |
| probing sequence | `PROBING_SEQUENCE_*` | `probing_sequence.py` 후보 | 높음 | 보류 |
| static baseline | `STATIC_BASELINE_*`, `STATIC_EXTENSIONS`, `STATIC_PREFIXES`, `STATIC_BASELINE_IMAGE_EXTENSIONS`, `HEALTH_LIKE_PATHS` | `static_baseline.py` 후보 | 중간 | 보류 |
| crawler baseline | `CRAWLER_*`, `BROWSER_UA_HINTS` | `crawler_baseline.py` 후보 | 중간 | 보류 |
| sensitive path probe | `SENSITIVE_PATH_PROBE_*`, `DIR_PROBE_*` | `sensitive_path_probe.py` 후보 | 높음 | 보류 |
| mixed baseline scanner | `MIXED_BASELINE_SCANNER_*` | `mixed_baseline_scanner.py` 후보 | 중간 | 보류 |
| IP behavior | `IP_BEHAVIOR_*` | `ip_behavior.py` 후보 | 낮음~중간 | 소규모 이동 후보 |
| auth behavior | `AUTH_BEHAVIOR_*`, `LOGIN_URI_HINTS`, `AUTH_ENDPOINT_FAMILY_PATTERNS`, `AUTH_SUCCESS_ATTACK_HINT_PATTERN` | `auth_behavior.py` 후보 | 중간 | 보류 |
| method behavior | `METHOD_*`, `STANDARD_HTTP_METHODS` | `method_summaries.py` 후보 | 중간 | 보류 |
| protocol anomalies | `PROTOCOL_ANOMALY_*` | `protocol_anomalies.py` 후보 | 낮음~중간 | 소규모 이동 후보 |
| SQLi hints | `SQLI_*`, `EDUCATIONAL_SQL_SEARCH_TERMS`, `SUPPORTING_SQL_KEYWORDS` | SQLi hint module 후보 | 높음 | evidence-boundary 검토 후 |
| XSS hints | `XSS_*`, `SCRIPT_TAG_*`, `EVENT_HANDLER_*`, `JAVASCRIPT_*`, `BROWSER_DATA_ACCESS_*`, `EXTERNAL_*`, `EDUCATIONAL_XSS_*` | XSS hint module 후보 | 높음 | evidence-boundary 검토 후 |
| file disclosure | `FILE_DISCLOSURE_*`, `PHP_FILTER_CANONICAL_PATTERN` | file disclosure hint module 후보 | 높음 | evidence-boundary 검토 후 |
| traversal/cmdi/automation | `TRAVERSAL_*`, `CMDI_*`, `AUTOMATION_UA_*` | hint module 후보 | 중간 | 보류 |
| generic attack hint | `STRONG_ATTACK_*`, `ATTACK_ENCODED_PAYLOAD_RE`, `NORMAL_SEARCH_ATTACK_TEXT_RE`, `SEARCH_PARAM_NAMES`, `NORMAL_SEARCH_VALUE_RE` | shared hint policy 후보 | 높음 | 유지 |

## 4. 세부 그룹별 판단

### 4.1 source ordering

Constants:

```text
SOURCE_PRIORITY
SOURCE_ORDER
```

현재 판단: 유지.

이유:

```text
- row collection, dedup, source preference 등 prepare 전체 흐름과 연결될 수 있음
- 특정 summary module 소유가 아님
- 이동 효과보다 import/coupling 위험이 큼
```

### 4.2 decode limit

Constants:

```text
DECODE_VARIANT_MAX_CHARS
```

예상 owner:

```text
src/prepare/decoders.py
```

현재 판단: 보류.

이유:

```text
- decoders.py 소유로 볼 수 있지만, decoded attack hint와 candidate extraction 쪽에서도 의미를 공유할 수 있음
- decoding depth/length 제한은 SQLi/XSS/file disclosure hint 탐지와 연결됨
- hints evidence-boundary 검토 전에는 이동하지 않음
```

### 4.3 supporting/time context

Constants:

```text
SUPPORTING_EVENT_TIME_WINDOW_SEC
TEMPORAL_CONTEXT_BUCKET_SEC
```

현재 판단: 유지.

이유:

```text
- supporting_events 생성/연결 로직은 아직 이동하지 않았음
- temporal context는 여러 후보와 연결됨
- candidate/supporting 관계에 영향을 줄 수 있으므로 constants 이동만으로도 원인 추적이 어려움
```

### 4.4 probing sequence

Constants:

```text
PROBING_SEQUENCE_WINDOW_SEC
PROBING_SEQUENCE_MIN_REQUESTS
PROBING_SEQUENCE_MIN_DISTINCT_PATHS
PROBING_SEQUENCE_SAMPLE_PATH_LIMIT
PROBING_SEQUENCE_PATH_PREFIX_HINTS
PROBING_SEQUENCE_PATH_SEGMENT_HINTS
PROBING_SEQUENCE_SUFFIX_HINTS
```

예상 owner:

```text
src/prepare/probing_sequence.py
```

현재 판단: 보류.

이유:

```text
- path prefix/segment/suffix hints는 sensitive path probe와 mixed scanner가 의미 경계를 공유할 수 있음
- 이미 probing_sequence.py 분리 시 constants 이동을 하지 않았음
- sensitive path/probing/mixed scanner 경계가 더 안정화된 뒤 소규모 이동 검토
```

추후 이동 가능 조건:

```text
- grep 결과 PROBING_SEQUENCE_*가 probing_sequence.py wrapper 경로 외에는 쓰이지 않음
- sensitive_path_probe.py와 mixed_baseline_scanner.py가 직접 참조하지 않음
- wrapper 인자 전달보다 module-local constants가 더 단순함
```

### 4.5 static baseline

Constants:

```text
STATIC_BASELINE_WINDOW_SEC
STATIC_BASELINE_MIN_STATIC_PATHS
STATIC_BASELINE_SAMPLE_REQUEST_LIMIT
STATIC_EXTENSIONS
STATIC_PREFIXES
STATIC_BASELINE_IMAGE_EXTENSIONS
HEALTH_LIKE_PATHS
```

예상 owner:

```text
src/prepare/static_baseline.py
```

현재 판단: 보류.

이유:

```text
- static baseline은 mixed scanner, crawler baseline, health-like path 해석과 경계가 있음
- static file 존재/JS 실행/health 정상 여부를 단정하지 않는 policy와 연결됨
- STATIC_EXTENSIONS/STATIC_PREFIXES는 다른 helper에서 재사용될 가능성이 있음
```

### 4.6 crawler baseline

Constants:

```text
CRAWLER_BASELINE_WINDOW_SEC
CRAWLER_BASELINE_SAMPLE_REQUEST_LIMIT
BROWSER_UA_HINTS
CRAWLER_BROWSE_PRODUCT_SEGMENTS
CRAWLER_BROWSE_CATEGORY_SEGMENTS
CRAWLER_BROWSE_GENERIC_SEGMENTS
```

예상 owner:

```text
src/prepare/crawler_baseline.py
```

현재 판단: 보류.

이유:

```text
- User-Agent와 browse path 판단은 crawler identity/site structure/product/category existence 과해석 위험과 연결됨
- mixed scanner와 일부 경계가 겹침
- UA hint는 공격 근거로 쓰면 안 되므로 wording/policy와 함께 관리해야 함
```

### 4.7 sensitive path probe

Constants:

```text
SENSITIVE_PATH_PROBE_WINDOW_SEC
SENSITIVE_PATH_PROBE_SAMPLE_REQUEST_LIMIT
SENSITIVE_PATH_PROBE_REPRESENTATIVE_CANDIDATE_LIMIT
DIR_PROBE_PATH_HINTS
DIR_PROBE_FILE_HINTS
```

예상 owner:

```text
src/prepare/sensitive_path_probe.py
```

현재 판단: 보류.

이유:

```text
- DIR_PROBE_*는 probing sequence, mixed scanner, file disclosure와 의미 경계가 겹침
- representative candidate limit은 candidate/supporting context와 연결될 수 있음
- sensitive path supporting event 생성/연결 로직은 아직 이동하지 않았음
```

### 4.8 mixed baseline scanner

Constants:

```text
MIXED_BASELINE_SCANNER_WINDOW_SEC
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT
```

예상 owner:

```text
src/prepare/mixed_baseline_scanner.py
```

현재 판단: 보류.

이유:

```text
- mixed scanner는 static/crawler/sensitive/probing/IP context가 섞인 영역
- context-only 경계를 안정화하는 것이 먼저임
- module-local constants 이동은 나중에 단일 커밋으로 검토 가능
```

### 4.9 IP behavior

Constants:

```text
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

예상 owner:

```text
src/prepare/ip_behavior.py
```

현재 판단: 소규모 이동 후보.

이유:

```text
- round2 후보 중 비교적 독립적인 편
- IP behavior aggregate helper는 이미 별도 모듈로 분리됨
- 다만 sensitive path sample limit은 sensitive path/probing 경계와 연결될 수 있어 즉시 이동은 보류
```

검토 조건:

```text
- grep 결과 IP_BEHAVIOR_*가 ip_behavior wrapper 외에는 쓰이지 않음
- Stage2 policy/count 의미가 변하지 않음
- IP를 attacker identity로 단정하지 않는 해석 제한 유지
```

### 4.10 auth behavior

Constants:

```text
AUTH_BEHAVIOR_WINDOW_SEC
AUTH_BEHAVIOR_RAPID_WINDOW_SEC
AUTH_BEHAVIOR_SAMPLE_REQUEST_LIMIT
AUTH_BEHAVIOR_REPRESENTATIVE_CANDIDATE_LIMIT
LOGIN_URI_HINTS
AUTH_ENDPOINT_FAMILY_PATTERNS
AUTH_SUCCESS_ATTACK_HINT_PATTERN
```

예상 owner:

```text
src/prepare/auth_behavior.py
```

현재 판단: 보류.

이유:

```text
- auth behavior는 login success/account takeover/lockout 과해석 금지와 직접 연결됨
- representative candidate limit은 candidate/supporting context와 연결될 수 있음
- auth payload/content-type 처리와 연결될 가능성이 있어 단순 constants 이동으로 보기 어려움
```

### 4.11 method behavior

Constants:

```text
METHOD_BEHAVIOR_WINDOW_SEC
METHOD_BEHAVIOR_SAMPLE_REQUEST_LIMIT
METHOD_RISKY_FAMILIES
METHOD_BASELINE_FAMILIES
METHOD_DESTRUCTIVE_FAMILIES
STANDARD_HTTP_METHODS
```

예상 owner:

```text
src/prepare/method_summaries.py
```

현재 판단: 보류.

이유:

```text
- method semantics는 PUT/DELETE/TRACE/OPTIONS 성공 단정 금지와 연결됨
- STANDARD_HTTP_METHODS는 protocol anomaly와도 경계가 있을 수 있음
- method constants는 module-local 후보지만 ownership을 한 번 더 grep으로 확인해야 함
```

### 4.12 protocol anomalies

Constants:

```text
PROTOCOL_ANOMALY_WINDOW_SEC
PROTOCOL_ANOMALY_SAMPLE_REQUEST_LIMIT
PROTOCOL_ANOMALY_LONG_PATH_MIN_LEN
```

예상 owner:

```text
src/prepare/protocol_anomalies.py
```

현재 판단: 소규모 이동 후보.

이유:

```text
- protocol anomaly 모듈은 이미 분리됨
- constants 수가 적고 비교적 topic-local일 가능성이 있음
- 다만 malformed request exploit success/protocol bypass 성공 단정 금지와 연결되므로 grep 확인 후 별도 커밋으로만 검토
```

### 4.13 SQLi hints

Constants/patterns:

```text
SQLI_PATTERNS
SQLI_BOOLEAN_CONDITION_PATTERN
SQLI_BOOLEAN_TRUE_CONDITION_PATTERN
SQLI_QUOTE_TERMINATION_STRUCTURE_PATTERN
SQLI_PAREN_TERMINATION_PATTERN
SQLI_XCLOSE_PATTERN
SQLI_UNION_COLUMN_ENUM_PATTERN
SQLI_SCHEMA_ACCESS_PATTERN
SQLI_FROM_USERS_PATTERN
SQLI_COMMENT_PATTERN
REPEATED_QUOTE_PATTERN
EDUCATIONAL_SQL_SEARCH_TERMS
SUPPORTING_SQL_KEYWORDS
```

예상 owner:

```text
future src/prepare/sqli_hints.py 후보
```

현재 판단: evidence-boundary 검토 후.

이유:

```text
- SQLi hints는 candidate selection, false positive suppression, supporting context와 연결됨
- Boolean blind/time-based 해석은 DB 결과 없이 Apache logs-only로 제한해야 함
- educational SQL search false positive 처리와 결합되어 있음
```

선행 문서 후보:

```text
docs/design/99_prepare_hints_split_candidate_review.md
```

### 4.14 XSS hints

Constants/patterns:

```text
XSS_PATTERNS
SCRIPT_TAG_PATTERN
SCRIPT_TAG_CAPTURE_RE
EVENT_HANDLER_ASSIGNMENT_RE
JAVASCRIPT_PROTOCOL_RE
BROWSER_DATA_ACCESS_RE
EXTERNAL_NAVIGATION_RE
EXTERNAL_URL_RE
XSS_QUOTE_BREAKOUT_PATTERN
XSS_TAG_INJECTION_PATTERN
EDUCATIONAL_XSS_SEARCH_TERMS
EDUCATIONAL_XSS_KEYWORDS
HTML_ENTITY_RE
```

예상 owner:

```text
future src/prepare/xss_hints.py 후보
```

현재 판단: evidence-boundary 검토 후.

이유:

```text
- XSS는 브라우저 실행 여부를 Apache 로그만으로 단정할 수 없음
- decoded payload reconstruction과 exploit success wording을 분리해야 함
- educational XSS query false positive 처리와 결합됨
```

선행 문서 후보:

```text
docs/design/99_prepare_hints_split_candidate_review.md
```

### 4.15 file disclosure hints

Constants/patterns:

```text
FILE_DISCLOSURE_PATTERNS
PHP_FILTER_CANONICAL_PATTERN
```

예상 owner:

```text
future src/prepare/file_disclosure_hints.py 후보
```

현재 판단: evidence-boundary 검토 후.

이유:

```text
- suspicious_file_disclosure verdict와 연결됨
- status/content-type/bytes만으로 file exposure를 단정하면 안 됨
- sensitive path probe와 경계가 겹침
```

선행 문서 후보:

```text
docs/design/99_prepare_hints_split_candidate_review.md
```

### 4.16 traversal/cmdi/automation hints

Constants/patterns:

```text
TRAVERSAL_PATTERNS
CMDI_PATTERNS
AUTOMATION_UA_PATTERNS
```

예상 owner:

```text
future src/prepare/attack_hints.py 또는 topic-specific hint modules 후보
```

현재 판단: 보류.

이유:

```text
- traversal/cmdi는 candidate scoring과 직접 연결될 수 있음
- automation UA는 lab-* / tool UA 과해석 금지와 연결됨
- hint 계열 전체 후보 비교 후 분리하는 편이 안전함
```

### 4.17 generic attack hint/search policy

Constants/patterns:

```text
SEARCH_PARAM_NAMES
NORMAL_SEARCH_VALUE_RE
NORMAL_SEARCH_ATTACK_TEXT_RE
STRONG_ATTACK_HINT_PREFIXES
STRONG_ATTACK_HINTS
ATTACK_ENCODED_PAYLOAD_RE
```

현재 판단: 유지.

이유:

```text
- SQLi/XSS/file_disclosure/traversal/cmdi 등 여러 hint 계열이 공유할 수 있음
- false positive suppression과 candidate preservation의 경계에 있음
- shared hint policy 모듈을 새로 만들기 전에는 이동하지 않음
```

## 5. 이동 가능성 우선순위

현재 기준의 소규모 이동 후보 우선순위는 아래다.

```text
1. PROTOCOL_ANOMALY_* constants
2. IP_BEHAVIOR_* constants 중 non-sensitive-path limit
3. METHOD_BEHAVIOR_* constants, 단 STANDARD_HTTP_METHODS 공유 여부 확인 후
4. STATIC_BASELINE_* constants, 단 STATIC_EXTENSIONS/STATIC_PREFIXES 공유 여부 확인 후
```

현재 기준의 보류 우선순위는 아래다.

```text
1. PROBING_SEQUENCE_* constants
2. SENSITIVE_PATH_PROBE_* / DIR_PROBE_* constants
3. MIXED_BASELINE_SCANNER_* constants
4. SQLi/XSS/file_disclosure hint patterns
5. generic attack/search policy constants
```

## 6. 다음 작업 후보

이 문서 이후 권장 작업은 두 갈래다.

### A. safe constants mini-move 검토

선행 확인:

```bash
grep -n "PROTOCOL_ANOMALY_" src/prepare_llm_input.py src/prepare/*.py
grep -n "IP_BEHAVIOR_" src/prepare_llm_input.py src/prepare/*.py
grep -n "METHOD_BEHAVIOR_\|STANDARD_HTTP_METHODS\|METHOD_RISKY_FAMILIES" src/prepare_llm_input.py src/prepare/*.py
```

문서 후보:

```text
docs/design/99_prepare_constants_mini_move_candidate_review.md
```

### B. hints split candidate review

권장 문서:

```text
docs/design/99_prepare_hints_split_candidate_review.md
```

비교 대상:

```text
SQLi hints
XSS hints
file_disclosure hints
traversal/cmdi/automation hints
shared attack/search policy constants
```

## 7. 현재 권장 결론

바로 constants.py 대량 분리를 하지 않는다.

권장 다음 단계는 아래 중 하나다.

```text
1. docs/design/99_prepare_constants_mini_move_candidate_review.md 작성
2. docs/design/99_prepare_hints_split_candidate_review.md 작성
```

더 안전한 순서는 constants mini-move candidate review를 먼저 작성하는 것이다. 그 문서에서 정말 단일 owner가 명확한 constants만 골라 한 커밋 단위로 이동 여부를 판단한다.

문서 전용 커밋 후보:

```text
docs: map prepare constants ownership
```
