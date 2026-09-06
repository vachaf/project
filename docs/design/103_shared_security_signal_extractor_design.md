# 103 Shared Security Signal Extractor 설계 명세

- 작성일: 2026-09-05
- 상태: D1~D4 설계 승인, D5 cap·초과 처리 구조 승인 / 성능 수치 미승인. 구현 승인 및 구현 완료를 의미하지 않는다.
- 조사 기준 HEAD: `907c9d3b7cd3636ca309ae68d878a1d77bcbd34f`
- 적용 기준: HEAD만이 아니라 기존 사용자 변경이 포함된 작업 트리. 기록 방법은 [104 회귀 계획](./104_shared_security_signal_extractor_regression_plan.md)을 따른다.
- 이번 작업: 사용자 승인 결과를 이 문서와 104에만 반영. production·테스트·설정·DB 변경, 테스트 실행, benchmark 조사·복원, harness 작성, baseline 생성 및 Git add/commit/push/branch 작업 없음.

## 1. 표기와 목적

| 표기 | 의미 |
| --- | --- |
| 확정 사실 | 현재 저장소를 읽어 확인한 동작·파일·계약. 테스트 재실행으로 확인했다는 뜻은 아니다. |
| 확정 요구 | 사용자 요청으로 고정된 설계 제약. 구현 전후 반드시 유지한다. |
| 승인된 설계 | 사용자가 채택한 D1~D5의 명시적 승인 범위. 구현·검증 실행·배포 승인이 아님 |
| provisional target | 미승인 성능 수치 / 측정 가설. harness와 baseline 측정 후 최종 acceptance를 별도 확정 |
| 제안 | 본 문서의 권장 구현 계약. 팀 검토 후 채택 여부를 기록해야 한다. |
| 미결정 / blocker | 합의·증거가 부족해 해당 구현 단계에 진입할 수 없는 사항. |

**확정 요구:** Prepare와 Live가 단일 요청의 deterministic 관찰 사실만 공유한다. Prepare 전체 또는 Prepare score를 Live에 연결하지 않는다. 기존 Prepare·Mapping 결과를 보존하는 공용화와 기존 탐지 오류 수정은 별도 변경으로 진행한다.

**승인 기록:** D1은 ID/provenance 계약, D2는 좁은 최초 allowlist, D3는 상태 2축, D4는 행별 additive observation 구조를 승인했다. D2 traversal은 corrected 단계의 legacy boundary 수정 전까지 임시 보류하며 최종 미지원 결정이 아니다. D5는 Live 전용 input/variant/output cap과 budget 초과 시 partial/unavailable 처리 구조를 승인했지만, 10ms/행·250ms/페이지·p95/p99 등 성능 수치는 승인하지 않았다. 이 설계 승인을 구현 승인으로 해석하지 않는다.

목적은 중복 탐지 구현을 줄이면서 원문 보존, 입력 관찰 한계, reason hint 호환성, Live read-only 조회를 명시적 계약으로 보호하는 것이다.

비목표는 새 공격 계열·CRS transform·대형 파일 wordlist 도입, 기존 regex 교정, score 재조정, candidate 성능 개선, 공격 확정·High 위험도·침해 판정, 분석 Job 생성, body나 서버 내부 상태 추정이다.

## 2. 현재 v3.1 범위와 근거

**확정 사실:** [Live route](../../web/routes/live.py)의 `live_snapshot` → [LiveLogService](../../web/services/live_log_service.py)의 `snapshot` → [LiveLogRepository](../../web/services/live_log_repository.py)의 `fetch_page`로 원천 로그를 조회한다. `apache_security_logs` 페이지와 전체 최신 시각을 SELECT한다. `_serialize_row`가 원문 필드를 응답에 옮기고 시간·숫자를 직렬화한다.

- 최대 페이지 50행, `log_time DESC, id DESC` 기준의 최신순과 양방향 커서.
- 기간·Status·Method·IP 정확 일치·URI/Request Target 문자열 검색.
- UTC DB 시간 해석 및 KST 표시, row ID와 request ID 분리, NULL 보존.
- [JS](../../web/static/live-monitoring.js)의 `AUTO_REFRESH_MS = 5000`, `renderRows`, `renderDetail`, `textContent` 기반 출력.
- 현재 Live 호출 경로에는 Prepare·Stage1·Mapping·Stage2·분석 Job 실행이 없다.
- 현재 SELECT에는 `raw_request`, 별도 `query_string`, `raw_log`, 요청 Content-Type, 요청/응답 body가 없다. 존재하지 않는 관찰 표면을 보완한 것처럼 만들 수 없다.

**확정 요구:** SQL·WHERE·정렬·LIMIT·커서·DB 연결 계정·DB 스키마·분석 pipeline을 변경하지 않는다. 관찰 결과로 행을 제거하거나 순서를 바꾸지 않는다. 조회 성공/실패와 detector 처리 성공/실패를 구분한다.

근거 문서는 [현재 아키텍처](../00_current_architecture.md), [logs-only evidence boundary](../00_apache_logs_only_evidence_boundary.md), [Live 가이드 13절](../../Live_Monitoring_v3.1_20260905_오늘_작업_가이드_정리본.md)이다. Live 현행 동작은 사용자 변경이 포함된 실제 코드가 기준이다.

## 3. 전체 데이터 흐름과 역할

**승인된 설계:** 다음 의존성 방향을 고정한다.

```text
Prepare의 기존 row
  → Prepare 입력 어댑터 → 공용 정규화/관찰 extractor
                            → Prepare 호환 계층
                            → 기존 score / filtering / threshold / aggregation
                            → 기존 Stage1 → 기존 Mapping → 기존 Stage2

Live의 기존 SELECT 결과
  → Live 입력 어댑터 → 같은 공용 정규화/관찰 extractor
                       → Live 표시 정책 → 관찰 상태와 참고 정보

정적 taxonomy registry → 기존 Mapping 및 Live 참고 정보 adapter
CRS 원본·manifest → 오프라인 회귀 입력 (Live runtime 의존성 아님)
```

| 계층 | 책임 | 금지 |
| --- | --- | --- |
| 공용 extractor | 정해진 텍스트 표면의 규칙 일치, 구조 facts, 변환 provenance | DB·파일·네트워크 I/O, 현재 시각 의존, score·severity·verdict·candidate 결정 |
| Prepare 입력/호환 계층 | 기존 입력 조합 재현, facts를 기존 점수 기여·hint로 변환 | Live import, 기존 감산·분기·집계 순서 변경 |
| Prepare 정책 | score, threshold, filtering, 반복·선택·summary | Live로 정책 전달 |
| Live adapter | 실제 SELECT 필드 투영, 관찰 scope 기록, 명시적 채택 목록 적용 | Prepare 함수 호출, 없는 body/header/request line 합성 |
| Live 표시 정책 | 신호 검토 여부와 참고 정보 연결 | 공격·성공·정상·severity 판정, 후보 선정 |
| taxonomy registry | 버전이 고정된 ID·이름 등 정적 메타데이터 | verdict 해석, attack regex, evidence 조합 정책 |

공용 모듈은 `src.prepare_llm_input`, Stage1/2, Mapping, web 서비스, benchmark 모듈을 import하지 않는다. Prepare가 공용 모듈을 사용하고 Live도 공용 모듈을 사용한다. import 시 I/O도 금지한다.

## 4. 실제 분리 대상과 남겨둘 범위

**확정 사실:** 현재 위치는 다음과 같다.

| 내용 | 파일·함수 |
| --- | --- |
| 원문·정규화 | [prepare_llm_input.py](../../src/prepare_llm_input.py): `raw_text`, `normalize_text`, `extract_raw_request_target`, `build_analysis_texts` |
| decoded variants | [decoders.py](../../src/prepare/decoders.py): `build_decoded_variants`, `append_html_entity_variants` |
| SQLi | [sqli_hints.py](../../src/prepare/sqli_hints.py)의 상수, monolith의 `matches_sqli_pattern`, `get_matching_pattern_names`, `get_sqli_structure_flags` |
| XSS | [xss_hints.py](../../src/prepare/xss_hints.py)의 상수, monolith의 `get_xss_context_hints`, `get_xss_structure_flags`, `has_xss_attack_structure` |
| traversal/CMDi | [traversal_cmdi_hints.py](../../src/prepare/traversal_cmdi_hints.py)의 `(name, regex, points)`와 `evaluate_row`의 loop |
| file/resource | [file_disclosure_hints.py](../../src/prepare/file_disclosure_hints.py)의 `detect_file_disclosure_hints` 및 monolith wrapper |
| 민감 경로 | [sensitive_path_probe.py](../../src/prepare/sensitive_path_probe.py)의 `classify_sensitive_path_probe_category`, monolith의 `build_sensitive_path_reason_hints_for_row` |

**승인된 설계:** 규칙·flags 추출과 점수 변환을 분리한다. `detect_decoded_attack_hints` 및 `detect_file_disclosure_hints`의 기존 `(int, List[str])` 반환형은 Prepare wrapper에서 유지한다. 공용 extractor에는 이 점수 반환형을 옮기지 않는다.

**확정 요구:** 다음은 Prepare 소유로 남긴다.

- `evaluate_row`의 score 누적/감산, hit 보정, verdict_hint 분기와 threshold.
- `has_strong_sqli_structure`의 정책적 strong 기준, 교육용 검색 감산, upload SQL comment 완화 정책.
- `classify_filtered_noise_category`, `sanitize_filtered_reason_hints`, static/Socket.IO 제외.
- `aggregate_noise_rows`, 반복 auth/sensitive-path 후보 축소, `deduplicate_candidates`, incident group.
- supporting events, false-positive review, IP/time-window/response metadata 기반 summary.

부작용 없는 함수도 정책을 포함할 수 있다. 함수 전체가 pure Python이라는 이유만으로 공유하지 않는다. `build_filtered_row_payload` 등 후보 외 경로에서도 탐지·hint를 재구성하므로 모든 호출부의 동등성을 검증한다. 기존 [shared policy 보류 근거](./99_prepare_shared_attack_policy_boundary_review.md)를 해소하지 못하면 해당 함수 이동을 중단한다.

## 5. 공용 입력 계약

### 5.1 입력 모델

**승인된 설계(D1):** 공용 입력은 명시적 순서의 텍스트 표면과 관찰 범위를 갖는다. 다음 의미 계약을 승인했으며 Python 타입/모듈명 선택은 향후 구현 상세다. 구현은 아직 승인하지 않았다.

| 필드 | 의미 |
| --- | --- |
| `input_profile` | `prepare_compat_v1` 또는 `live_target_v1`. 입력 구성/관찰 범위 차이이며 점수 정책 선택자가 아니다. |
| `surfaces` | 입력 표면의 순서 있는 목록. `source_field`, 원문 텍스트, origin/derived 관계 포함 |
| `observation_scope` | 관찰 가능·선택·누락·제외 표면 및 제한 기록 |
| 변환 설정 | 버전으로 고정한 decode 동작. 요청자가 무제한 depth를 지정하지 못함 |

입력 row와 문자열을 수정하지 않는다. method 등 context가 필요하면 텍스트 표면과 구분된 관찰 facts로 제공한다. status, IP, response size는 최초 Live 채택 판단에 사용하지 않는다.

### 5.2 Prepare 호환 입력

**확정 사실:** `build_analysis_texts(raw_request, uri, query_string, raw_request_target, raw_log)`는 `(base_text, combined_text, query_variants, raw_request_target_variants)`를 반환한다. `normalize_text`는 `unquote_plus(...).strip()`이며, 호출자가 이미 정규화한 값을 넘기는 경로도 있다.

**확정 요구:** 기존 호출 순서와 호출 횟수, raw/normalized text 조합 순서, 공백·중복 제거를 보존한다. 이를 단순한 “모든 필드 2회 decode”로 대체하지 않는다. combined text에 걸친 legacy match도 compatibility 결과에서 임의로 제거하지 않는다.

원문→variant의 `depth`, `text`, `variant_type`, `source`, `source_text`, `source_variant_depth`는 기존 의미와 누락 키를 유지한다. 기존 depth는 해당 decode chain 기준이며, 이미 normalize된 입력까지 포함한 총 decode 횟수로 재해석하지 않는다.

### 5.3 Live 입력

**승인된 설계(D1/D5):** 원문 `request_target` 우선, `uri` 보조. query는 decode 전에 관찰 대상으로 제한한 target의 첫 literal `?`에서 분리하며 파생 표면임을 표시한다. target 관찰 범위 밖을 query 확보 목적으로 추가 탐색하지 않는다. target 누락 시 URI만 관찰하고 missing field 및 partial 상태를 기록한다. `%3F`를 query separator로 먼저 변환하지 않는다. target과 URI를 합쳐 가상의 실행 구문을 만들지 않는다.

양쪽 표면의 불일치는 각각의 source와 scope로 설명한다. 실제 SELECT에 없는 raw request, query column, body, 임의 header를 합성하지 않는다. 같은 문자열을 갖더라도 Prepare와 Live의 전체 결과가 같다고 요구하지 않는다. 동일한 관찰 표면·변환 설정의 facts에 대해서만 동등성을 요구한다.

## 6. 공용 출력 계약

**승인된 설계(D1):** versioned envelope가 순서 있는 `matches`, `structure_facts`, `observation_scope`, 처리 상태를 반환한다. 원문 전체를 출력에 복제하지 않고 필요한 provenance만 제공한다. 공용 facts의 의미 ID, 탐지 규칙 ID, Live 채택 규칙 ID를 분리한다.

| 항목 | 정의 |
| --- | --- |
| `signal_id` | 관찰 사실의 안정적인 의미 ID. 예: `browser.data_access_token`, `html.event_handler_attribute`. SQLi/XSS verdict나 severity가 아님. 기존 ID를 다른 의미로 재사용하지 않음 |
| `rule_id` | 구체적인 탐지 규칙과 revision ID. 예: `legacy.xss.img_onerror.v1`. 일치 범위 변경 시 revision 변경. 의미가 같으면 signal ID는 유지 가능 |
| `adoption_rule_id` | Live가 facts를 채택한 조합 규칙 ID. 예: `live.html.event_handler.v1`. 공용 탐지 rule과 분리하여 Live adapter가 소유 |
| `source_field` | `uri`, `request_target`, `query_string`, `raw_request`, `raw_log` 등 실제 또는 명시적 파생 표면. compatibility combined match는 `combined_text`로 기록 |
| `decode_depth` | 해당 URL variant chain에서 수행된 decode 깊이. 정규화 전체 누적 횟수라는 주장 금지 |
| `decode_type` | raw / URL decode / HTML entity 등 변환 종류. HTML entity가 URL variant에서 파생되면 부모 depth도 보존 |
| `structure_facts` | 규칙 일치와 구조 관찰의 명명된 bool/enum facts. 예: quote termination, event-handler assignment, shell separator, wrapper/resource 조합. 실행/노출 성공 facts는 없음 |
| `observation_scope` | profile, 실제 관찰 필드, 누락·제외 필드, 적용 detector/version, 절단/미실행 사유, `complete/partial/unavailable/error` 처리 범위 |
| `processing_status` | 관찰 처리 완료/실패 상태. security verdict와 분리 |

출력 계약 변경은 schema version, Live allowlist 변경은 adoption policy version으로 관리한다. legacy 이름과 rule ID 대응표를 유지한다. ID 이름 변경으로 legacy taxonomy 문제를 수정하지 않는다.

provenance는 `source_field`, `surface`, `derived_from`, `variant_id`, `decode_type`, `decode_depth`, `transforms`, 좌표 종류를 명시한 `span`, 입력/variant truncation 정보를 포함한다. Live 파생 query는 `source_field=request_target`, `surface=query`로 구분하며 실제 DB query column인 것처럼 표기하지 않는다. HTML entity는 부모 URL depth도 보존한다. scope에는 profile, 대상/관찰/누락/제외 필드, detector/version, 원래 입력 길이·관찰 길이·절단 이유를 기록한다.

combined-text match의 source를 특정 필드로 단정하지 않는다. source가 모호한 사실은 최초 Live 채택에 쓰지 않는다. 위치 정보를 추가한다면 원문 offset과 decoded offset을 구별하며, 정확히 역변환할 수 없으면 원문 offset을 꾸며내지 않는다.

**확정 요구:** 출력에는 `score`, `score_boost`, 가중치, `severity`, `verdict`, `verdict_hint`, confidence, candidate 포함 여부가 없다. Live 응답에도 해당 필드를 도입하지 않는다.

**승인된 설계(D1):** matches의 순서는 고정 rule 순서→surface 순서→variant 생성 순서→일치 위치 순서다. 같은 rule/surface/variant/위치의 중복만 제거하고 별도 provenance는 보존한다. 기존 Prepare hint 순서는 이 신규 matches 순서에 맡기지 않고 호환 계층에서 기존 실행 순서와 중복을 재현한다. 출처가 모호한 combined facts는 compatibility에 보존하되 Live 채택 조합에 사용하지 않는다.

## 7. reason hint 호환 계약

**확정 요구:** Prepare 외부 계약을 그대로 유지한다.

- `sqli:*`, `xss:*`, `traversal:*`, `cmdi:*`의 `(+N)`을 포함한 문자열 byte 내용.
- encoding, file_disclosure, context, fp_hint 및 no-inference hint 문자열.
- 기존 `append`, `extend`의 중복과 `append_unique_hint`/`extend_unique_hints`의 최초 등장 순서 보존. 전역 set 변환·정렬·일괄 dedup 금지.
- upload 문맥에서 기존 hint 제거와 대체 hint 추가 시점 보존.
- SQLi/XSS 교육용 검색 감산, hit 수 변경, 부정 hint의 생성 조건 보존.
- `Candidate`, filtered row, supporting events, summaries 및 downstream reason 소비 경로 모두 비교.

legacy `traversal:etc_passwd(+5)`와 `xss:external_exfil_intent`도 공용화 중 이름을 교정하지 않는다. Live는 이 문자열을 그대로 사용자 판정으로 노출하지 않는다. 오류 정정은 corrected expectation과 별도 revision에서 다룬다.

## 8. Live 상태와 최초 채택 경계

### 8.1 표시 조건

**승인된 설계(D3):** 처리 상태 `processing_status=complete|partial|unavailable|error`와 검토 상태 `assessment=review_required|no_signal|undetermined`를 독립 축으로 관리한다.

| processing_status | 채택 신호 | assessment | 화면 표시 |
| --- | --- | --- | --- |
| complete | 있음 | review_required | `검토 필요` |
| complete | 없음 | no_signal | `관찰 신호 없음` |
| partial | 확인 완료한 신호 있음 | review_required | `검토 필요 · 부분 관찰` |
| partial | 없음 | undetermined | `부분 관찰 · 신호 유무 확인 미완료` |
| unavailable | 해당 없음 | undetermined | `관찰 불가` |
| error | 해당 없음 | undetermined | `detector 오류` |

`no_signal`은 complete이며 채택 신호가 없을 때만 허용한다. 이는 현재 detector/allowlist/관찰 범위에서 신호를 발견하지 못했다는 뜻이며 정상·안전 판정이 아니다. `review_required`도 공격·High·침해·취약점 존재 판정이 아니다.

target 누락으로 URI만 관찰하면 partial, 둘 다 없으면 unavailable이다. body/임의 header 등 원래 profile 제외 필드만으로 partial을 만들지는 않는다. 입력/variant 절단 및 처리 도중 budget 초과는 partial, page budget으로 미착수한 행은 unavailable과 `page_budget_exceeded`다. output cap 초과는 partial과 `output_truncated`로 표시하고 확인된 채택 신호를 모두 잃도록 절단하지 않는다. 예기치 않은 detector 예외는 해당 행의 중간 결과를 공개하지 않고 error/undetermined로 처리한다. reason_codes로 원인을 구분한다. DB 조회 성공과 detector 상태를 분리하고 원문 행을 유지한다.

### 8.2 승인된 좁은 최초 allowlist와 제외

**승인된 설계(D2):** 최초 allowlist는 다음 다섯 관찰 구조로 제한한다. 공격 성공의 TP 정의가 아니다.

| signal_id | 채택 조건 |
| --- | --- |
| `sql.termination_boolean_structure` | 같은 구조의 quote 종료 + boolean true 조건 |
| `sql.termination_union_structure` | 같은 구조의 quote 종료 + UNION SELECT + 열 열거 |
| `html.event_handler_attribute` | 현행 `img_onerror` 또는 `svg_onload`가 찾은 태그 내 이벤트 속성 |
| `shell.separator_command_structure` | 현행 `pipe_exec` 또는 `semicolon_exec`의 구분자 + 지원 command |
| `php.filter_resource_structure` | 같은 구조의 PHP filter wrapper + base64 filter + resource 지정 |

여러 입력/variant에서 합친 기존 flags만으로 동일 구조를 추정하지 않는다. 같은 source/variant 내 하나의 구조라는 provenance를 확인하고 별도 parameter의 facts를 조합하지 않는다. 보장이 구현·검증되기 전 해당 조합을 활성화하지 않는다. 교육 자료/인용에도 구조가 있을 수 있으므로 공격 의도는 단정하지 않는다. allowlist 승인은 구현·Live 활성화 승인이 아니다.

**확정 요구:** 최초 채택에서 다음 단독 신호는 제외한다.

- `;environment`: 세미콜론만으로 CMDi로 단정하지 않는다.
- bare `document.cookie`: browser-data token fact가 있어도 XSS 검토 신호로 올리지 않는다.
- bare `url(javascript:alert())`: protocol/alert token만으로 XSS로 단정하지 않는다.
- SQL `;INSERT`: SQL 구문을 CMDi 신호로 오염시키지 않는다.
- 단독 `resource=`, SQL comment, encoding marker, 교육용 키워드, UA·HTTP 오류·status 200·응답 크기.
- bare `cat /etc/...`, isolated `>/tmp/...`와 실행 경계 없는 command-looking text.

**승인된 임시 보류(D2):** legacy traversal `dotdot_slash`, `etc_passwd`는 legacy boundary가 수정되는 별도 corrected 단계 전까지 최초 Live allowlist에서 보류한다. 이는 traversal의 최종 미지원 결정이 아니다. `foo../`, `foo.../`, backslash 및 직접 파일 token의 taxonomy 문제를 이번 공용화에서 수정하지 않는다. compatibility에는 기존 match/hint를 보존하며, corrected 단계의 boundary 수정·검증 후 Live 채택을 별도로 검토한다. 그 전 legacy 규칙으로 CWE-22 참고 정보를 만들지 않는다.

직접 `.env`/config/backup 등 민감 경로 category, 현행 `subshell`, 일반 script-tag/navigation 조합도 최초 allowlist에서 보류한다. 해당 Prepare detector를 삭제·교정한다는 뜻이 아니다. Live scope에는 최초 채택 범위가 제한적임을 명시한다.

이 제외 정책은 기존 Prepare XSS 규칙에 `document_cookie`, `javascript_uri`, `alert_call`이 존재한다는 사실을 변경하지 않는다. 기존 candidate 결과를 suppress하는 테스트로 바꾸지 않는다.

## 9. 공통 taxonomy registry와 기존 Mapping

**확정 사실:** [security_standards_mapping.py](../../src/security_standards_mapping.py)의 `build_security_standards_mapping`은 Stage1 verdict와 Prepare hints를 사용한다. `STANDARD_NAMES`는 OWASP Top 10:2025/CWE/WSTG 메타데이터다. Stage1이 호출하고 Stage2의 standards summary가 소비한다.

**제안:** registry 최초 범위는 기존 ID·이름·표준 식별자/판본 등 정적 데이터다. 이름·버전을 갱신하는 작업은 이번 분리와 별개다. 링크를 새로 넣을 경우 공식 참조와 버전을 별도 검증하며 미검증 URL을 만들지 않는다.

**확정 요구:** 기존 Mapping은 verdict별 조건, NON_SECURITY_VERDICTS, evidence 조합, file branch 우선순위, `direct/conditional/related`, rule ID, basis, boundary note, observability, empty mapping, dedup·정렬을 계속 소유한다. registry 이동만으로 기존 출력이 바뀌면 실패다.

Live signal→reference 연결은 별도 adapter 정책이다. 기존 Mapping을 가상 Stage1 verdict로 호출하지 않는다. `source=deterministic_stage1_enrichment`를 재사용하지 않는다. OWASP/CWE/WSTG는 관련 관찰 신호의 참고 자료이며 일치하는 취약점이 존재한다는 선언이 아니다. 직접 파일 token에 CWE-22, wrapper token 단독에 CWE-98을 자동 부여하지 않는다.

## 10. Live API, 입력 제한 및 provisional 성능 목표

### 10.1 승인된 additive API 구조(D4)

기존 `items[]` 각 행에 versioned `observation` 객체만 추가한다. 기존 top-level/행 필드를 삭제·변경하거나 NULL을 다른 값으로 바꾸지 않는다. observation을 제거한 기존 응답 projection은 전체 동등해야 한다. 기존 응답 전체의 byte 동일성을 뜻하지는 않는다.

다음은 승인 구조를 설명하는 예시이며 현재 API 응답이나 구현 완료 증거가 아니다.

```json
{
  "observation": {
    "schema_version": "live_observation.v1",
    "detector_version": "security_signals.v1",
    "adoption_policy_version": "live_allowlist.v1",
    "processing_status": "complete",
    "assessment": "no_signal",
    "reason_codes": [],
    "scope": {
      "profile": "live_target_v1",
      "observed_fields": ["request_target", "uri"],
      "missing_fields": [],
      "excluded_fields": ["request_body", "response_body", "other_headers"],
      "input_truncated": false,
      "variant_truncated": false,
      "output_truncated": false
    },
    "signals": []
  }
}
```

채택 signal은 `signal_id`, `adoption_rule_id`, `rule_ids`, bounded `evidence`와 `references`를 갖는다. evidence는 6절 provenance를 사용한다. 원문/decoded 전문을 복제하지 않는다. 참고 정보는 standard/id/name과 `usage=reference_only`를 사용하고 기존 Mapping의 direct 관계 등을 재사용하지 않는다. 미승인 참고 연결은 빈 목록이다. score/severity/verdict/confidence를 추가하지 않는다.

`LiveLogService.snapshot`의 `fetch_page` 이후 `_serialize_row` 부근에서 메모리 내 row에 부가한다. `LiveLogRepository`, SQL, route 파라미터, 원문, 커서를 유지하고 추가 SELECT/Job/파일 쓰기를 하지 않는다. UI는 고정 라벨과 `textContent`를 사용한다. observation이 없는 구버전 응답은 `관찰 정보 미제공`이며 no-signal이 아니다. 유효화된 버전은 모든 행에 observation을 반환하되, 이번 설계 승인만으로 구현·유효화를 시작하지 않는다.

### 10.2 승인된 Live 전용 input/variant/output cap(D5)

**확정 사실:** 현행 decoder variant에는 4096자 제한이 있지만 base/combined text 전체의 동일 상한은 아니다. 다음 cap은 Live 전용이며 Prepare 입력·decode·score·hint에 적용하지 않는다.

| 대상 | 승인된 cap/구조 |
| --- | --- |
| 페이지 / polling | 기존 최대 50행 / 5초 유지 |
| raw 입력 | request_target와 uri 각각 앞 4096 Unicode code points를 조기에 bounded slice로 확보 |
| query | 제한된 target의 첫 literal `?`에서 파생. 관찰 범위 밖을 추가 탐색하지 않음 |
| surface | target/파생 query/URI 최대 3개 |
| URL 변환 | raw + decode1 + decode2 |
| HTML entity | 위 각 variant에서 최대 1개. entity 이후 URL 재decode 없음 |
| variant 수/길이 | raw 포함 surface당 최대 6개, 행당 최대 18개, 각각 4096 code points |
| 총 variant 문자 | 행당 최대 73,728 code points |
| 공개 signal/evidence | 최대 16종, signal당 최대 4 evidence |
| observation 응답 | UTF-8 JSON 행당 최대 16KiB, 50행 최대 800KiB |

원문 API/UI 필드는 절단하지 않는다. cap은 detector 추가 처리/출력의 범위이며 기존 원문 전송·render 전체 상한이 아니다. 행 단위 순차 처리로 variant 보유 기간을 제한한다. 절단으로 인위적으로 생긴 word boundary 등 끝 문맥 의존 match는 채택 근거로 쓰지 않는다.

**승인된 초과 처리 구조:** 처리 중 input/variant/time/output budget 초과는 partial로 기록한다. 완료한 채택 근거가 있으면 review_required, 없으면 undetermined다. page budget으로 미착수한 행은 unavailable/undetermined와 `page_budget_exceeded`를 반환한다. 예외는 error/undetermined다. 어떤 초과/미실행도 no-signal로 바꾸지 않는다. 각 제한과 reason_codes를 scope에 남긴다.

### 10.3 성능 수치 — 미승인 provisional target / 측정 가설

**D5 조건부 승인 범위:** 위 cap·초과 상태 구조는 승인됐지만 다음 성능 수치는 아직 승인되지 않았다. **harness와 baseline 측정 후 최종 acceptance 수치를 별도로 확정한다.** 그 전 provisional 숫자로 PASS/FAIL 또는 공개 가능 판정을 내리지 않는다.

| 항목 | provisional target (미승인) |
| --- | --- |
| 협력적 시간 budget | 10ms/행, 250ms/페이지 |
| 50행 observation 추가 시간 | p95 ≤ 100ms, p99 ≤ 250ms |
| 전체 snapshot | fake DB p95 ≤ 500ms |
| 긴 지연 검토 가설 | observation 1초 초과 페이지 0 |
| 추가 메모리 peak | 페이지당 16MiB 이하 |
| 지속 메모리 | warm-up 후 첫/마지막 20poll RSS 중앙값 차이 10MiB 이하 |

50행/5초는 기존 기능 조건이며 새 성능 acceptance 승인이 아니다. warm-up 20회, 1000 samples, 120poll, 1/5세션 비교는 향후 측정 계획 후보다. 요구/작업 누적을 만들지 않는 구조를 유지하되 해당 횟수·환경에서 검증했다는 뜻은 아니다. DB RTT·원문 render와 detector 증분 비용을 분리해 보고한다.

협력적 budget의 clock은 Live adapter 측 단조 clock으로 rule/variant 경계에서 확인한다. 공용 extractor에 현재 시각 의존을 넣지 않는다. 이는 실행 중인 Python regex의 강제 timeout이 아니다. 단일 규칙의 최악 입력 지연을 통제하지 못하면 공개를 중단하고 실행 방식을 별도 검토한다. 그 해결을 위해 이번 단계에서 Prepare regex를 바꾸지 않는다. harness 작성·baseline 측정 자체도 별도 승인 전 실행하지 않는다.

## 11. 구현 단계와 중단 조건

모든 실행 명령과 회귀 상세는 [104](./104_shared_security_signal_extractor_regression_plan.md)를 따른다. 설계 승인은 아래 단계의 실행 승인이 아니다. 이번 문서 작업 중 실행하지 않는다.

| 단계 | 산출물 | 중단 조건 |
| --- | --- | --- |
| S0 기준 확정 | 사용자 변경 포함 source identity, 테스트 환경, 승인된 D1~D5 구조와 D5 미승인 수치 구분 | 별도 실행 승인 없음, 기존 변경 보존 방법 미확정 |
| S1 baseline | compatibility 전체 출력과 기존 테스트 결과 | 반복 실행 결과 불안정, 실패 원인 미분리, 비교 harness 없음 |
| S2 공용화 | facts extractor와 Prepare wrapper | score/hint/후보/filtered/summary 변화 1건 이상, import cycle |
| S3 registry | 정적 메타데이터 이동 | 기존 Mapping 출력 또는 정렬 변화 |
| S4 Live adapter | scope·채택 목록·관찰 처리 상태 | 약한 token 승격, legacy taxonomy 오염, pipeline 호출·쓰기 발생 |
| S5 UI/비기능 | 안전 출력, 원래 조회 동등성, 측정 후 별도 승인한 성능 acceptance 증거 | 원문/커서/SQL 변경, HTML 실행, polling 누적, D5 최종 수치 미승인 |
| 별도 corrected 변경 | 수정 규칙·새 expectation·before/after 설명 | 공용화 patch와 혼합하거나 baseline 덮어쓰기 |

S2를 통과해도 S4 승인을 의미하지 않는다. CRS Prepare benchmark blocker가 남으면 해당 benchmark 동등성 완료 및 전체 release 승인을 선언하지 않는다.

## 12. 승인 결과와 남은 blocker

| ID | 상태 | 결정/증거 | 막히는 단계 |
| --- | --- | --- | --- |
| D1 | 승인 | 의미 ID / versioned rule ID / adoption rule ID, provenance·순서·중복 계약(5~6절) | 설계 결정 해소. S2 실행은 별도 승인 필요 |
| D2 | 승인 | 5종 좁은 최초 allowlist. traversal은 corrected 단계 boundary 수정 전 임시 보류이며 최종 미지원 아님(8.2절) | S4 실행·활성화는 별도 승인 필요 |
| D3 | 승인 | processing_status와 assessment 2축, partial/error와 no-signal 분리(8.1절) | S4 실행은 별도 승인 필요 |
| D4 | 승인 | 기존 items[] 각 행의 versioned observation만 추가, 기존 응답 projection 보존(10.1절) | 구현·유효화는 별도 승인 필요 |
| D5 | 조건부 승인 / 수치 미승인 | Live input/variant/output cap 및 초과 partial/unavailable 구조 승인. 성능 수치는 provisional이며 harness/baseline 측정 후 최종 acceptance 확정(10.2~10.3절) | S5 최종 합격 판정은 수치 확정 전 차단 |
| B1 | blocker | 현재 없는 `src/external_benchmark_prepare.py`, `tests/test_external_benchmark_prepare.py`의 실제 위치/기준 revision과 재현 절차 확인 | CRS Prepare baseline·전체 완료 판정 |
| B2 | blocker | 전체 `build_outputs` 비교 harness 및 `prepared_at` 고정 방법은 아직 구현·실행되지 않음 | S1/S2 동등성 판정 |
| B3 | blocker | compatibility baseline은 아직 생성하지 않았고 신규 true/false boundary 검증도 미실행 | S2 진입 |

[102 문서](./102_external_benchmark_prepare_baseline_review.md)의 `8/19`, `6/8`은 과거 기록이다. 현재 재현된 baseline으로 사용하지 않는다. 그 문서의 과거 commit 표기를 누락 파일의 현재 위치/복구 revision으로 확정하지 않는다. B1은 조사 후 별도 기록으로 닫는다.

예상 신규 모듈명은 `src/security_signals/*`, `src/prepare/signal_adapter.py`, `web/services/live_signal_observation.py`, `src/security_taxonomy_registry.py`이며 모두 **제안명**이다. 현재 존재하는 구현으로 취급하지 않는다. 실제 변경 목록은 구현 승인 단계에서 좁히며 기존 사용자 파일은 승인 범위 외에 수정하거나 되돌리지 않는다.
