# 104 Shared Security Signal Extractor 회귀 기준 및 검증 계획

- 작성일: 2026-09-05
- 상태: D1~D4 승인 및 D5 구조 승인/성능 수치 미승인 결과를 반영한 검증 계획. 구현·검증 실행 승인이 아니며 이 문서의 명령은 이번 작업에서 실행하지 않았다.
- 기준 HEAD: `907c9d3b7cd3636ca309ae68d878a1d77bcbd34f`
- 상위 계약: [103 설계 명세](./103_shared_security_signal_extractor_design.md)
- 이번 변경: 승인 결과를 103·104에만 반영. 테스트 코드·production·설정·DB 변경, 테스트 실행, benchmark 조사·복원, harness 작성, baseline 생성 및 Git add/commit/push/branch 작업 없음.

## 1. 증거 상태와 두 기대값 계열

표기는 103과 같다. **확정 사실**은 코드·기존 문서에서 확인한 내용이고, **확정 요구**는 사용자 제약이다. **제안**은 향후 검증 방식이며, **미결정/blocker**는 아직 실행·합의되지 않은 사항이다.

### 1.1 승인 결과와 실행 경계

| 항목 | 승인 상태 | 회귀 계약에 반영할 내용 |
| --- | --- | --- |
| D1 | 승인 | 의미 signal ID / versioned rule ID / Live adoption rule ID 분리, source·decode·span·truncation provenance, 순서·중복 계약 |
| D2 | 승인 | 103 8.2절의 좁은 5종 최초 allowlist. traversal은 legacy boundary가 수정되는 별도 corrected 단계 전까지 임시 보류이며 최종 미지원 아님 |
| D3 | 승인 | processing_status / assessment 2축. complete + 신호 없음일 때만 no_signal |
| D4 | 승인 | items[] 각 행에 versioned observation 추가. observation 제거 후 기존 응답 전체 동등 |
| D5 구조 | 승인 | Live 전용 input/variant/output cap, 초과 시 partial/unavailable 및 undetermined 처리 |
| D5 성능 수치 | 미승인 / provisional target | 10ms/행·250ms/페이지·p95/p99·메모리 등은 측정 가설. harness와 baseline 측정 후 최종 acceptance 수치를 별도 확정 |

**설계 승인을 구현 승인으로 해석하지 않는다.** benchmark 조사·복원, harness 작성, baseline 생성, 테스트 실행은 여전히 별도 승인 대상이다. B1~B4는 승인 기록만으로 해소되지 않는다. provisional 수치만으로 성능 PASS/FAIL을 내리지 않는다.

### 1.2 기대값 계열의 분리

| 계열 | 목적 | 기대값 작성 방법 | 합격 기준 |
| --- | --- | --- | --- |
| `compatibility` | 공유 구조로 옮겨도 기존 결과가 같은지 검증 | 실제 현재 source tree에서 실행한 결과를 이후 별도 승인 단계에서 동결 | 변경 전후 차이 0. 알려진 오류도 여기서는 보존 |
| `corrected` | 향후 탐지 오류·taxonomy 정정의 의도 검증 | 별도 설계 결정 ID와 수정 revision, 영향을 받는 cases 및 기대 차이를 명시 | 승인된 차이만 발생하고 나머지 compatibility 유지 |
| `live_adoption` | 신규 Live가 약한/legacy signal을 판정으로 올리지 않는지 검증 | 103의 최초 allowlist·표시 계약을 독립 기대값으로 작성 | 기존 Prepare 결과와 별개로 채택 경계·read-only 보존 |

**확정 요구:** corrected 기대값으로 compatibility 파일을 덮어쓰지 않는다. 기존 fixture의 expectation을 바꿔 공용화 실패를 숨기지 않는다. 세 계열은 디렉터리·schema/version·결정 ID로 구분한다. 실제 신규 파일명은 아직 제안 단계다.

과거 [102 baseline review](./102_external_benchmark_prepare_baseline_review.md)의 `8/19`, `6/8`은 현재 재현 결과가 아니다. 성공률 목표, baseline acceptance 값, 통과 증거로 사용하지 않는다. 사용자 보고의 Live 기능 검증 완료와 이번에 테스트를 재실행했다는 주장은 구별한다.

## 2. Git revision과 사용자 변경 기록

### 2.1 이번 조사에서 확인한 시작 상태

**확정 사실:** HEAD는 위 revision이고 다음 기존 수정 4개가 있다.

```text
web/README.md
web/app.py
web/requirements.txt
web/templates/job_base.html
```

기존 untracked 14개는 다음과 같다. 전부 사용자 소유 변경으로 취급한다.

```text
Codex_Live_Monitoring_v3.1_20260905_작업요청_프롬프트.md
Live_Monitoring_MVP_v3.1_implementation.zip
Live_Monitoring_MVP_v3.1_배포_및_테스트_가이드.md
Live_Monitoring_v3.1_20260905_오늘_작업_가이드_정리본.md
live_monitoring_log_reader_check_20260904_170645.txt
tests/test_live_log_repository.py
tests/test_live_log_service.py
tests/test_web_live_routes.py
web/routes/live.py
web/services/live_log_service.py
web/services/live_log_repository.py
web/static/live-monitoring.css
web/static/live-monitoring.js
web/templates/live_dashboard.html
```

기준 manifest는 실제 `git ls-files` 결과로 생성하며 문서 목록을 실행 입력으로 사용하지 않는다.

### 2.2 향후 기준 동결 절차

**제안:** 구현 승인 후 다음 읽기 명령으로 revision과 상태를 다시 확인한다.

```bash
git rev-parse HEAD
git status --short
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
.venv/bin/python --version
.venv/bin/python -m pip list --format=freeze
```

기대 결과: source identity, 기존 변경 목록, Python/dependency 버전을 확보한다. 실패 기준: 조사 이후 source drift를 설명하지 못하거나 사용자 변경을 기준 입력에서 누락한다. 비밀번호·API 키·환경 파일 내용·인증 정보를 기록하지 않는다.

별도 승인된 baseline 작업에서만 테스트에 필요한 tracked source/fixtures/expected와 untracked Live 파일의 경로·SHA-256·파일 mode를 기록한다. HEAD, dirty diff의 보존본, untracked 파일의 보존본, 명령/파라미터, Python·OS·timezone·의존성, 결정 ID를 함께 보관한다. 비밀 설정이나 운영 로그는 복사 대상에서 제외한다.

HEAD archive만으로는 Live v3.1을 재현할 수 없다. 복사 대상 manifest로 기존 사용자 변경을 포함한 실행 가능한 기준 스냅샷을 만들고 원본과 hash를 비교한다. exact snapshot 경로와 보관 위치는 팀 결정 전 생성하지 않는다. 기존 `.venv`는 source 대신 실행 환경으로 버전을 기록한다.

**확정 요구:** `git reset --hard`, 광범위 checkout/restore, stash에 의한 사용자 변경 은닉, `git clean`, 임의 commit으로 기준 고정하지 않는다. 기준 tree는 읽기 전용으로 두고 이후 구현 tree와 분리한다. 이번 단계에서는 이 스냅샷이나 baseline 파일도 생성하지 않는다.

## 3. 변경 전 baseline 확보 절차

모든 명령은 **향후 별도 승인 후** 실행한다. `/tmp/shared-signals-review-*` 경로는 제안된 결과 저장 위치이며 이번에 생성하지 않았다. 기존 결과 디렉터리를 재사용해 덮어쓰지 말고 실행별 고유 경로를 선택한다.

1. 별도 실행 승인 후 S0에서 source tree·환경·승인된 구조 계약을 동결한다. D5 성능 수치는 provisional로 별도 기록하고 초기 측정을 막는 선결 acceptance로 사용하지 않는다.
2. 기존 테스트를 변경 전 tree에서 실행하고 실패·경고·known limitation을 그대로 기록한다.
3. 아래 전체 반환값 비교 harness를 검토·구현한 뒤 같은 before tree에서 두 번 실행한다.
4. 정해진 시각과 입력에서 두 결과가 같은지 확인한다. 차이를 임의로 mask하지 않는다.
5. 수정 후 동일 환경·fixtures·파라미터로 실행해 before와 비교한다.
6. fixture expected 규칙 검사와 전체 반환값 동등성을 별개로 보고한다.

**확정 사실:** [check_prepare_regression.py](../../scripts/check_prepare_regression.py)는 MUST/MUST_NOT/SHOULD/KNOWN_LIMITATION 기반 검사이며 전체 `build_outputs` 동등성 harness가 아니다. [check_stage_dryrun_regression.py](../../scripts/check_stage_dryrun_regression.py)는 실제 LLM 호출 없는 pipeline dry-run 검증이다. 둘 다 향후 실행 시 artifact를 생성할 수 있으므로 이번 문서 작성 단계에서는 실행하지 않는다.

## 4. Prepare 전체 반환값 비교

### 4.1 비교 단위

**확정 사실:** [build_outputs](../../src/prepare_llm_input.py)는 다음 순서의 5-tuple을 반환한다.

```text
(llm_input, candidate_payload, noise_payload,
 filtered_reasons_payload, filtered_payload)
```

**확정 요구:** 다섯 반환값 전체를 비교한다. 성공한 candidate 몇 개만 비교해서 통과시키지 않는다.

| 내용 | 동등성 요구 |
| --- | --- |
| score / verdict_hint | 정수값, 문자열, 존재 여부 동일 |
| reason_hints | 문자열, `(+N)`, 순서, 중복 개수, 삭제·삽입 위치 동일 |
| 후보/탈락 | 건수·순서·ID·source·원문·NULL·noise category·public reason 모두 동일 |
| summary | 모든 summary/aggregate의 key, count, category, 시간, 표본, hint 동일 |
| supporting events | 선택·연결·정렬·reason 및 context-only 의미 동일 |
| dedup | 대표 후보, incident group, merged IDs/source tables, merged count 동일 |
| 메타데이터 | pipeline policy, 선택 source, analysis window 등 동일 |
| 나머지 필드 | whitelist 밖 필드를 버리지 않고 재귀적으로 비교 |

JSON object key 순서와 데이터 의미의 비교는 구별하되, 사용자 출력 byte 보존이 필요한 CLI artifact는 별도 byte 비교한다. 배열 순서는 절대 정렬해 비교하지 않는다. 누락/null/빈 문자열/0/false를 서로 같은 값으로 보지 않는다. Python의 `True == 1` 같은 느슨한 동등성을 피하도록 타입도 검사한다.

### 4.2 시각과 비교 harness

**확정 사실:** `llm_input.meta.prepared_at`은 `datetime.now().astimezone()`에서 생성되므로 자연 실행 간 달라진다.

**제안:** 테스트 harness가 두 실행의 해당 module datetime을 같은 고정 clock으로 주입하고 timezone도 동일하게 고정한다. production code에 테스트용 clock 옵션을 추가하지 않는다. 출력 전체 시간값 제거는 금지한다. clock을 고정할 수 없는 경우에만 `llm_input.meta.prepared_at` 한 경로의 대체 비교를 별도 결정으로 승인받고 원본도 보관한다.

향후 작성할 harness는 다음 기능을 가져야 한다. 아직 파일·명령 인터페이스가 없으므로 실행 가능한 현재 도구라고 취급하지 않는다.

- 기존 `tests/fixtures/prepare_regression/*.json` 전부와 승인된 경계 fixtures 입력.
- default `min_score=4`, `min_repeat_aggregate=3`, `source_tables=['security']` 및 실제 지원 source 조합.
- threshold 전후, 반복 횟수 2/3/4 등 승인된 파라미터 matrix. 서로 다른 파라미터 결과끼리 비교하지 않음.
- `access`, `security`, `error`의 정책 차이, candidate/filtered/aggregate 경로 모두 포함.
- input deepcopy 전후 비교로 mutation 검출, 동일 입력 반복 호출, 입력 처리 순서의 재현성 확인.
- 반환 tuple의 타입·길이 검사 후 JSON-compatible 전체 내용을 capture.
- 차이의 case/파라미터/JSON path/old/new/type을 보고. 후보 감소를 성능 개선으로 합격 처리하지 않음.

**승인된 D1 회귀 기준:** signal ID의 의미 재사용 금지, 일치 범위 변경 시 rule revision 변경, Live 채택 정책 version 분리를 검사한다. matches는 rule→surface→variant→일치 위치 순서이며 같은 rule/surface/variant/위치 중복만 제거한다. 서로 다른 provenance와 Prepare reason 중복은 보존한다. source_field/surface/derived_from, URL depth와 HTML entity 부모 depth, 변환 순서, offset 좌표 종류, 원래 길이/관찰 길이/절단 이유를 검사한다. combined-text facts를 특정 필드의 근거로 위장하거나 다른 입력/parameter의 facts를 Live 조합으로 합치면 실패다. ID/provenance는 기존 Prepare 외부 출력에 임의로 추가하지 않는다.

**blocker B2:** harness 명세 검토·구현과 clock 통제 검증 전 S1/S2 전체 동등성 증거가 없다. 다음은 **향후 도구 인터페이스 제안**이며 현재 실행 금지다.

```text
<승인된 capture 도구> --source-root <before snapshot> --clock <fixed> --output <compatibility/before-1>
<동일 capture 도구>   --source-root <before snapshot> --clock <fixed> --output <compatibility/before-2>
<동일 capture 도구>   --source-root <after snapshot>  --clock <fixed> --output <compatibility/after>
<승인된 compare 도구> <before-1> <before-2>
<동일 compare 도구>   <before-1> <after>
```

기대 결과: before 반복 차이 0, before/after 차이 0. 실패 기준: 미승인 차이 하나 이상, input mutation, 누락된 반환값, 실행하지 않은 case를 pass로 기록.

## 5. normalization 및 decode 회귀

**확정 요구:** [decoders.py](../../src/prepare/decoders.py)와 `build_analysis_texts`의 실제 순서를 보호한다.

| 입력/상황 | 비교 기준 |
| --- | --- |
| None·빈 문자열·공백 | 기존 raw/normalized 값과 빈 variant 반환 동일 |
| `+`, `%2B`, `%20` | `unquote_plus` 의미와 호출 횟수 동일; plus와 공백을 임의 동치 처리하지 않음 |
| 0/1/2회 및 더 깊은 encoding | 기존 base/variant 경로 전체 결과를 보존; 공유 단계에서 decode pass 확장 없음 |
| 잘못된 percent encoding·Unicode | 예외/문자 보존과 순서 동일 |
| HTML entity | 숫자 entity 인식, HTML decode 적용 조건과 parent/source depth 동일 |
| URL→HTML entity | `variant_type`, `source`, `source_text`, `source_variant_depth` 값과 누락 여부 동일 |
| 동일 text가 여러 variant에 존재 | 기존 중복 제거 및 append 순서 동일. rule evidence dedup과 legacy hint dedup 구별 |
| 길이 4095/4096/4097 | variant 절단 경계, decode 전후 길이 처리, 경계를 가로지르는 payload 확인 |
| 긴 base/combined text | 기존에는 variant 4096자 제한과 다름. Prepare 전역 truncation 추가 금지 |
| URI/target 충돌 | Prepare 기존 조합 유지, Live는 source별 관찰·scope 기록 |

같은 text만 비교하지 않고 variant 배열과 provenance 전체를 비교한다. numeric HTML entity의 `#`가 SQL comment로 새로 잡히지 않도록 `strip_html_entities_for_sql_comment_scan` 경계도 검사한다.

Live 전용 cap과 별개로 Prepare의 기존 normalization/decode 결과는 차이 0을 유지한다. Live cap·2축 상태 계약의 승인이 Prepare에 새 전역 입력 제한을 적용할 권한을 주지 않는다.

## 6. 계열별 true-positive / false-positive 경계

여기서 TP는 승인된 관찰 구조를 찾아야 한다는 뜻이며 공격·취약점·실행 성공의 정답 label이 아니다. FP는 문맥 없이 관찰 의미를 과도하게 승격시키는 경계다. 다음 사례의 현재 전체 Prepare 결과는 아직 실행하지 않았으므로 수치·후보 여부를 추정해 고정하지 않는다.

| 계열 | 구조 관찰을 보호할 positive 후보 | negative/약한 경계 | 계열별 적용 |
| --- | --- | --- | --- |
| SQLi | quote 종료+boolean, UNION SELECT, schema 접근, 2중 encoding | 교육용 검색, comment 단독, multipart/upload 문맥, HTML entity | Prepare는 기존 결과 capture, Live는 승인된 조합만 채택 |
| XSS | script/tag 내부 event handler, quote breakout+태그 구조, 실제 JS navigation 구문 | Apache `Location`, 교육 문구, bare browser token/protocol | compatibility facts 보존. 최초 Live는 img_onerror/svg_onload만 채택 |
| CMDi | `;whoami`, `|cat`, `$(id)` 등 기존 지원 경계 | `;environment`, SQL `;INSERT`, bare `cat ...`, isolated redirect | compatibility 보존. 최초 Live는 pipe_exec/semicolon_exec만 채택, subshell 보류 |
| Traversal | 기존 plain/encoded `../` 일치 | `foo../`, `foo.../`, `/..foo`, `/..`, 단일 backslash | compatibility 보존. Live는 corrected boundary 수정 전 임시 보류, 최종 미지원 아님 |
| file/resource | PHP filter+base64/resource 조합, 기존 직접 config category | `resource=` 단독, 일반 metadata path, `.dockery`, `history.history` | token·scope·taxonomy 분리, 새 wordlist 금지 |

**승인된 D2 Live 회귀 대상:** `sql.termination_boolean_structure`(quote 종료+boolean true), `sql.termination_union_structure`(quote 종료+UNION SELECT+열 열거), `html.event_handler_attribute`(img_onerror/svg_onload), `shell.separator_command_structure`(pipe_exec/semicolon_exec), `php.filter_resource_structure`(wrapper+base64 filter+resource)의 다섯 종류다. 조합은 동일 source/variant의 하나의 구조라는 provenance를 요구한다. 전체 flags가 참인 것만으로 통과하지 않는다. 각 positive/negative pair 및 unrelated parameter 조합 방지를 검사한다.

직접 민감 path category, 일반 script-tag/navigation, subshell은 최초 allowlist에서 제외한다. 해당 compatibility positive를 Live positive로 복사하지 않는다. bare token의 내부 fact 존재도 Live 채택을 의미하지 않는다.

### 6.1 반드시 독립 case로 둘 네 경계

| case | compatibility baseline | Live 최초 채택 / 향후 corrected expectation |
| --- | --- | --- |
| `;environment` | 현재 exact regex와 전체 출력 capture 후 보존 | CMDi로 단정하지 않음. `env`를 substring으로 확대 매칭하지 않음 |
| bare `document.cookie` | 현재 `XSS_PATTERNS.document_cookie`가 존재함. 기존 score/hint/candidate를 강제로 제거하지 않음 | browser-data token fact는 허용하되 XSS 검토 신호·XSS taxonomy로 승격하지 않음 |
| bare `url(javascript:alert())` | 현재 javascript_uri/alert_call 규칙이 있으므로 no-match 기대를 기존 Prepare에 강제하지 않음 | CSS/protocol/alert token만으로 XSS 단정·채택하지 않음 |
| SQL `;INSERT` | 기존 SQL/다른 계열 결과를 capture 후 동일하게 유지 | CMDi 오염 없음. CMDi rules에 generic semicolon 또는 SQL verb를 추가하지 않음 |

query 원문·URL encoded·double encoded, 다른 정상 문자열과 함께 있을 때를 포함한다. negative case에 명시적 별도 XSS/CMDi payload를 추가한 positive pair도 필요하다. bare-token 제외 때문에 실제 구조가 있는 pair까지 빠지면 실패다. Prepare corrected 동작은 아직 미결정이며 Live 채택 기대값을 그대로 production corrected 기대값으로 복사하지 않는다.

### 6.2 알려진 traversal/taxonomy 부채

**확정 사실:** 현재 traversal regex는 embedded `../` substring과 `/etc/passwd|win.ini`를 함께 취급한다. 단일 backslash 지원 문제도 102에서 지적되며 현재 정규식에 남아 있다.

**확정 요구:** 공용화 단계에서 정규식·hint 이름·file branch priority를 수정하지 않는다. corrected 계열에 다음 의도를 별도 기록하되 승인 전 구현하지 않는다.

**D2 승인된 보류 범위:** traversal은 legacy boundary가 수정되는 corrected 단계 전까지의 임시 보류다. 최종 미지원 expectation을 만들지 않는다. 현재 live_adoption에서는 legacy traversal 채택/CWE-22 연결이 없음을 검사하되, 별도 corrected 수정·검증 후 채택 재검토가 가능함을 기록한다. 이번 승인으로 boundary/backslash/resource taxonomy 수정을 시작하지 않는다.

- explicit segment escape와 embedded lookalike 구별.
- single-backslash의 의도한 지원과 실제 compiled match 교정.
- 직접 파일 token을 traversal evidence와 분리하고 CWE-22 오염 방지.
- 영향받는 candidate 변화와 기준 수치 변화는 별도 before/after로 설명.

현재 [CRS 테스트](../../tests/test_external_benchmark_crs.py)의 `test_direct_etc_passwd_guardrail_records_current_mapping_mismatch`는 stale traversal hint가 CWE-22를 만드는 현재 동작을 기록한다. 이 테스트를 수정해야만 통과하는 공용화는 실패다.

## 7. Mapping 및 downstream 회귀

**확정 요구:** [Mapping 테스트](../../tests/test_security_standards_mapping.py)와 [summary 테스트](../../tests/test_security_standards_summary.py)를 보호한다.

- schema/source/observability/items/unmapped_reason 전체 출력 동일.
- rule ID, 표준 ID·이름, relationship, basis, boundary note와 items 순서 동일.
- dedup precedence와 입력 reason 중복 처리 동일.
- `benign_normal`, `likely_false_positive`, `inconclusive`의 empty mapping 유지.
- invalid/unknown verdict 처리 유지.
- direct sensitive file, traversal, PHP wrapper 분기 우선순위와 현재 알려진 mismatch도 compatibility에서는 유지.
- Stage1 reason 전달, Stage2 standards summary·dry-run 결과 보호. 실제 LLM 호출은 이 회귀 계획에 포함하지 않음.

registry 분리는 정적 정보의 소유 위치만 바꾼다. taxonomy 버전/명칭 갱신이나 신규 연결 추가가 기존 Mapping 출력을 바꾸면 S3 실패다.

## 8. Live 기능·격리·안전 출력 회귀

### 8.1 기존 read-only 조회

기존 [repository 테스트](../../tests/test_live_log_repository.py), [service 테스트](../../tests/test_live_log_service.py), [route 테스트](../../tests/test_web_live_routes.py)가 출발점이다.

| 보호 대상 | 기대 결과 |
| --- | --- |
| 필터 | 기간/Status/Method/IP 정확 일치/URI·target keyword의 validation·SQL params 동일 |
| SELECT | 기존 페이지와 latest 조회 횟수·SQL·계정 제한 동일. 신호를 위한 추가 쿼리 0 |
| 최신순 | 동일 시각의 id tie-break, newer 페이지 역순 복원 동일 |
| 커서 | encode/decode, invalid cursor, older/newer 및 페이지 경계 동일 |
| 시간 | UTC naive 해석·KST 표시·고정 now 기준 동일 |
| NULL·ID | null 그대로, row_id와 request_id 독립, 원문 필드 동일 |
| 오류 | 기존 validation 400, DB 503, 일반 snapshot 500의 status/code/안전 메시지 동일 |
| 신규 observation | items[] 각 행의 versioned observation만 추가. 이를 제거한 기존 응답 projection은 전체 동등 |
| detector 오류 | DB 조회 결과를 버리거나 no-signal로 위장하지 않고 행별 observation 오류. 기존 DB 실패 처리는 변경하지 않음 |

명시적으로 허용한 신규 observation 외에 기존 API 필드를 수정하지 않는다. UI state 때문에 filtering·sort·pagination을 observation 순서로 바꾸지 않는다.

**승인된 D4 검사:** schema_version/detector_version/adoption_policy_version, processing_status/assessment/reason_codes/scope/signals 구조를 검사한다. signals의 rule IDs·adoption rule·bounded evidence·reference_only 정보는 Prepare score/verdict 또는 기존 Mapping 실행 결과로 대체하지 않는다. 원문/decoded 전문 복제, score/severity/confidence 추가는 실패다. object가 없는 구버전 응답은 관찰 정보 미제공으로 처리하며 no_signal로 해석하지 않는다.

**승인된 D3/D5 상태 matrix:**

| processing_status | assessment | 검증 조건/표시 |
| --- | --- | --- |
| complete | review_required | 완료한 관찰에서 채택 신호 있음 / 검토 필요 |
| complete | no_signal | 완료한 관찰에서 채택 신호 없음 / 관찰 신호 없음, 정상 판정 아님 |
| partial | review_required | 부분 관찰이지만 완료된 채택 근거 있음 / 검토 필요 · 부분 관찰 |
| partial | undetermined | 절단/처리 중 budget 초과 및 채택 신호 없음 / 부분 관찰 |
| unavailable | undetermined | 관찰 표면 전무 또는 page budget 미착수 / 관찰 불가 |
| error | undetermined | detector 예외 / detector 오류, 해당 행 중간 signal 공개 안 함 |

target 누락·URI만 관찰은 partial, 둘 다 누락은 unavailable을 기대한다. 원래 profile 제외 body/header만으로 partial을 만들지 않는다. input/variant/output truncation과 budget reason을 구별한다. output cap 도달 시 확인된 신호를 모두 버려 no_signal로 만들지 않는다. 부분 관찰·예외·미착수는 어떤 경우에도 no_signal이 될 수 없다.

### 8.2 금지 호출 0회

**확정 요구:** snapshot 조회·자동 갱신·행 선택·상세 표시를 각각 검증한다.

- `prepare_llm_input`의 평가/출력/score 경로, Stage1, 기존 Mapping builder, Stage2, pipeline/worker/Job API 호출 0회.
- runtime 파일 생성·artifact 쓰기·캐시 파일 쓰기·DB INSERT/UPDATE/DELETE/DDL·commit 호출 0회.
- 공용 extractor 자체는 DB·파일·네트워크 호출 0회.
- 공통 registry 읽기는 순수 메모리 메타데이터 접근만 허용. Live에서 기존 Mapping 실행은 허용하지 않음.

정적 import/호출 검사와 동적 spy를 병행한다. 금지 module을 instrumentation 때문에 import하지 말고 import guard 또는 서비스 경계 sentinel을 사용한다. open/write 계측은 테스트 결과 파일 생성 등 harness 자체와 혼동하지 않도록 Live 요청 실행 구간에 한정한다. startup static/template 읽기는 허용하지만 요청으로 새 쓰기가 발생하면 실패다. DB는 fake connection으로 SELECT allowlist를 검사한다. 실제 DB 시험은 별도 승인 전 실행하지 않는다.

### 8.3 브라우저 안전성

`<script>`, `<img onerror=...>`, quote, ampersand, Unicode, 긴 문자열을 row·signal 설명·reference 이름에 넣어 literal text로 표시되는지 확인한다. 동적 DB/signal 값은 `textContent`를 사용하고 `innerHTML`, `document.write`, event attribute·javascript URL로 전달하지 않는다. reference 링크를 추가하면 고정 registry의 검증된 주소만 허용한다.

기존 JS source assertion만으로 실제 DOM 실행 안전성을 모두 증명했다고 하지 않는다. 향후 browser harness에서 popup/script/event 실행 0, 원문 표시, row 선택 유지, 빈 결과와 오류 상태를 검사한다. browser harness는 현재 미구현 blocker B4다.

## 9. 승인된 cap 검증과 미승인 성능 측정 가설

### 9.1 승인된 D5 구조의 기능 회귀

**확정 사실:** 최대 50행과 5초 polling은 기존 기능 조건이다. 다음은 승인된 Live 전용 cap의 검증 기준이며 Prepare 경로에는 적용하지 않는다.

| 대상 | 승인된 cap / 검증 |
| --- | --- |
| raw 입력 | request_target와 uri 각각 앞 4096 Unicode code points. 조기 bounded slice, 원문 응답 보존 |
| query/surface | 제한된 target의 첫 literal `?`에서 파생, 관찰 범위 밖 추가 탐색 금지, 최대 3 surfaces |
| 변환 | raw/decode1/decode2 + 각 variant의 HTML entity 최대 1개. entity 후 URL 재decode 없음 |
| variant | raw 포함 surface당 최대 6개, 행당 최대 18개, 각각 4096 code points, 총 73,728 code points 이하 |
| 공개 signal/evidence | 최대 16종, signal당 evidence 최대 4개 |
| observation 출력 | UTF-8 JSON 행당 최대 16KiB, 50행 최대 800KiB |
| cap/budget 초과 | 처리 중 partial, 미착수 unavailable. 신호 없음이면 undetermined이며 no_signal 금지 |

4095/4096/4097자, Unicode, 64KiB/1MiB 원문 stress에서 cap·scope·원문 보존을 검사한다. 절단 끝에서 인위적으로 생긴 word boundary나 미관찰 끝 문맥 의존 match가 채택되지 않아야 한다. output cap은 확인된 신호를 전부 버리는 방식으로 지키지 않는다. 시간 budget 상태 전이는 나중에 승인된 test clock/budget 주입으로 검증할 수 있으며, 기능 전이의 승인이 10ms/250ms 숫자의 승인은 아니다.

### 9.2 provisional target — 아직 최종 acceptance가 아님

**D5 성능 수치는 미승인이다.** 다음은 측정 가설/provisional target으로만 보존한다. **별도 승인된 harness와 baseline 측정 후 최종 acceptance 수치를 확정한다.** 측정 전 숫자를 pass/fail gate로 사용하거나 측정 가설을 맞추기 위해 baseline을 변경하지 않는다.

| 항목 | provisional target (미승인) | 향후 측정 계획 후보 |
| --- | --- | --- |
| 협력적 budget | 10ms/행, 250ms/페이지 | 단조 clock으로 rule/variant 경계에서 확인; 강제 timeout 아님 |
| observation 증분 비용 | 50행 p95 ≤ 100ms, p99 ≤ 250ms, 1초 초과 0회 | 동일 row의 기존 직렬화와 observation 포함 처리 비교, fake DB |
| 전체 snapshot | fake DB p95 ≤ 500ms | 고정 now/입력, warm-up 20회 후 1000 samples |
| 추가 메모리 peak | 페이지당 ≤ 16MiB | 행별 순차 처리와 peak 증분 관찰 |
| 지속 메모리 | 첫/마지막 20회 RSS 중앙값 차이 ≤ 10MiB | warm-up 후 120poll 비교 |

5초 polling에서 중첩·누적을 만들지 않는 구조를 유지한다. 120회·1/5세션 검증은 환경/부하 측정 계획 후보이며 완료한 시험이나 승인된 처리 용량이 아니다. actual 환경·측정 방법·표본 규모와 최종 acceptance는 별도 기록으로 확정한다.

추가 시간은 같은 런의 paired samples로 계산하고 OS/CPU/RAM/Python/동시 세션 수, p50/p95/p99/max, RSS와 원문 크기를 기록한다. DB RTT·원문 전송/render와 detector 증분 비용을 분리한다. 초기 측정이 provisional 가설과 다르면 측정 결과로 보고하고 수용 수치를 재검토한다. 원문 무단 truncation이나 Prepare regex/threshold 변경으로 목표를 맞추지 않는다.

협력적 clock 확인은 Live adapter가 소유하고 pure extractor에 현재 시각 의존을 넣지 않는다. 단일 regex 실행 중에는 사후 budget 확인이 강제 중단을 보장하지 않는다. 최악 입력의 지연을 통제할 수 없다면 공개를 중단하고 실행 방식을 별도 검토한다. harness 작성·baseline 측정은 이번 승인에 포함되지 않는다.

## 10. 단계별 실행 명령·기대 결과·gate

아래 shell 명령은 **향후 구현/검증 승인 후**, source root에서 실행한다. 이번 문서 작성 중에는 실행하지 않는다. 기존 도구와 신규 미구현 도구를 분리한다. `PYTHONDONTWRITEBYTECODE=1`과 pytest cache 비활성화는 불필요한 source tree 쓰기를 줄이지만 테스트 artifact까지 읽기 전용으로 만든다는 뜻은 아니다.

### S0 — 기준 확인

```bash
git rev-parse HEAD
git status --short
git diff --name-only
git ls-files '*external*benchmark*'
rg --files src tests benchmarks scripts
```

합격: 별도 실행 승인 후 source snapshot에 사용자 변경이 포함되고 D1~D4 및 D5 구조 승인/수치 미승인을 분리 기록. 실패/중단: 실행 승인 없음, source drift 미설명, 누락 파일을 존재한다고 가정. B1은 실제 위치·revision·실행법을 확인한 증거로만 닫는다. 이번에는 이 조사 명령도 실행하지 않는다.

### S1 — 변경 전 기존 테스트

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_prepare_*.py tests/test_eval_prepare_candidate_selection.py tests/test_explain_prepare_candidates.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_security_standards_mapping.py tests/test_security_standards_summary.py tests/test_llm_stage1_classifier.py tests/test_llm_stage2_reporter.py tests/test_llm_stage2_reporter_enrichment.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_live_log_repository.py tests/test_live_log_service.py tests/test_web_*.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_external_benchmark_crs.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_prepare_regression.py --strict --keep-output /tmp/shared-signals-review-before-prepare
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_stage_dryrun_regression.py --strict --keep-output /tmp/shared-signals-review-before-stage
```

기대: 각 exit code 0, 실패 없음. 실제 테스트 건수와 warnings/known limitations는 실행 출력으로 기록하며 과거 `23 passed`/`120 passed`를 이번 결과로 적지 않는다. 변경 전부터 실패하면 원인·case·승인된 처리 방향을 기록하고 baseline-ready를 선언하지 않는다. dependency 설치나 네트워크 접근은 이 명령에 포함하지 않으며 준비되지 않으면 중단한다.

전체 반환값 capture/compare는 4.2의 아직 미구현 harness로 별도 수행한다. 위 기존 테스트 통과만으로 전체 동등성 통과를 대신하지 않는다.

### S2 — extractor / Prepare 호환

S1의 Prepare pytest 명령을 변경 후 source에서 다시 실행한다. 출력 보관 경로는 다음처럼 before와 분리한다.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_prepare_regression.py --strict --keep-output /tmp/shared-signals-review-after-prepare
```

4.2의 before 반복 비교와 before/after 전체 비교를 수행한다. 신규 extractor·normalization·네 경계 테스트는 구현 이후 실제 파일명을 확정해 다음 인터페이스로 실행한다.

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider <승인 후 생성된 extractor/compatibility 테스트 파일 목록>
```

이 placeholder는 현재 실행 명령이 아니다. 합격: 전체 동등성 차이 0, input mutation 0, boundaries 통과, 금지 의존성 0. 실패: regex/score/hint/순서 변경으로 기대값 수정 필요, 전역 cap 도입, 기존 버그 수정 혼합.

### S3 — registry / Mapping

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_security_standards_mapping.py tests/test_security_standards_summary.py tests/test_llm_stage1_classifier.py tests/test_llm_stage2_reporter.py tests/test_llm_stage2_reporter_enrichment.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_stage_dryrun_regression.py --strict --keep-output /tmp/shared-signals-review-after-stage
```

신규 Mapping 전체 출력 before/after 비교도 별도 수행한다. 합격: schema·정렬·내용 전체 차이 0. 실패: 이름/버전 갱신, stale hint branch를 수정해 compatibility 변화, Live가 Mapping builder 호출.

### S4 — Live service / UI

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_live_log_repository.py tests/test_live_log_service.py tests/test_web_*.py
```

`tests/test_web_live_routes.py`는 위 `tests/test_web_*.py`에 포함된다. 신규 관찰·격리 테스트와 browser harness의 명령은 실제 도구 채택 후 기록한다.

```text
<승인된 Live 관찰/격리 테스트 명령> --fixtures <live_adoption cases>
<승인된 browser harness 명령> --scenario safe-text-and-polling
```

합격: 기존 response projection·SQL·cursor 동일, 금지 호출 0, 안전 출력, 상태 경계 통과. 실패: 신규 observation을 제외한 기존 key/value 변화, detector 오류가 no-signal로 표시, 약한 token 승격, 파일/DB 쓰기, 공격/High/침해 문구.

### S5 — 성능 및 전체 완료 판정

```text
<승인된 성능 harness 명령> --rows 50 --warmup 20 --samples 1000 --profile fake-db
<승인된 polling harness 명령> --interval-ms 5000 --cycles 120
```

아직 도구가 없으며 이번 실행 승인이 없으므로 현재 NOT RUN이다. 위 sample/cycle 수는 측정 계획 후보이고 acceptance 수치가 아니다. 향후 별도 승인 후 먼저 harness와 baseline을 측정하고 D5 최종 acceptance를 확정한다. 이후 합격은 9.1절 승인 cap·상태 계약 및 별도 승인된 최종 성능 기준 충족, 필요한 기능 suite/full-output comparison 증거 연결로 판단한다. 수치 미확정 상태의 전체 성능 합격 판정은 BLOCKED이며 provisional target 초과만으로 FAIL 처리하지 않는다. 최종 승인 기준 위반은 FAIL, harness 미구현·CRS Prepare baseline B1 미해결은 BLOCKED다. 코드가 바뀌지 않은 suite를 반복 실행해 증거 수만 늘리지 않는다.

### 별도 corrected 변경

별도 승인된 rule fix와 corrected fixtures로 해당 focused tests를 실행하고 S1의 관련 suite 및 full-output 비교를 반복한다. 명령/fixture 경로는 그 변경에서 실제 생성 후 확정한다. 합격: 결정 ID별 허용 diff만 발생. 실패: compatibility baseline 덮어쓰기, 무관한 score/threshold 조정, benchmark case ID/UA/IP에 특화한 처리.

## 11. CRS 범위와 현재 blocker

**확정 사실:** 현재 [external_benchmark_crs.py](../../src/external_benchmark_crs.py), [CRS 테스트](../../tests/test_external_benchmark_crs.py), pinned source와 [manifest](../../benchmarks/manifests/owasp_crs_path_file_access.v1.json)가 있다. adapter는 원본과 project annotation을 분리한다. 36건 원본 inventory와 direct/partial/out_of_scope 계약은 기존 테스트로 보호한다.

**확정 요구:** 원본 checksum·license·revision·manifest·CRS expectation을 변경하지 않는다. `expect_ids`를 Live/Stage1 verdict로 자동 변환하지 않는다. body/header에만 decisive signal이 있는 사례를 request-target detector의 miss로 집계하지 않는다. signal match rate와 Prepare candidate recall은 다른 지표다.

공용 detector 회귀에는 원본 target/query 보존, positive/negative pairs, source/decode provenance를 사용한다. candidate 숫자뿐 아니라 rule/fact 변화까지 비교한다. 의미가 미정인 `.ssh`, `.docker`, backup, `/sys/class`, node metadata, bare command-like 사례는 coverage 확대 승인을 대신하지 않는다.

| ID | 현재 상태 | 해제 조건 |
| --- | --- | --- |
| B1 | 현재 `src/external_benchmark_prepare.py`, `tests/test_external_benchmark_prepare.py` 없음 | 실제 위치/기준 revision, 현재 입력과의 관계, 실행 명령, 재현 결과 확인. 추측으로 checkout/복구하지 않음 |
| B2 | 전체 출력 capture/compare와 clock 통제 미구현 | 승인된 harness, before 반복 동등성, 전체 5-tuple 및 타입·순서 검증 |
| B3 | 이번에는 baseline·신규 경계 테스트 미실행 | 별도 승인 이후 기존 tree에서 실제 실행 결과 확보 |
| B4 | browser·write/import spy·성능 harness 미구현 | 도구/명령/환경 확정 및 요구 범위 계측 가능 증거 |

B1은 CRS Prepare baseline 검증과 전체 완료 판정의 blocker다. 알려진 adapter 테스트나 제한된 설계 작업까지 중단해야 한다는 뜻은 아니다. 누락 파일을 이 문서에서 새 production/test 코드로 만들어 해결하지 않는다.

## 12. rollback 및 구현 중단

**확정 요구:** 사용자 변경을 되돌리는 rollback은 금지한다. rollback은 이번 구현이 만든 변경만 대상으로 한다.

1. 한 gate가 실패하면 다음 gate/Live 활성화로 진행하지 않는다.
2. before·after 결과, 실패 JSON path, source identity, 명령·환경을 보존한다. 기대값을 통과용으로 갱신하지 않는다.
3. 변경이 격리된 구현 commit이면 그 commit 범위만 검토해 역변경한다. 미커밋 변경이면 작성한 hunk만 확인해 되돌린다. 기존 사용자 hunk와 겹치면 자동 복원하지 않고 중단·조정한다.
4. 되돌린 후 기준 manifest와 기존 사용자 파일 hash를 비교하고 관련 gate를 다시 검증한다.
5. 기존 SQL·DB 스키마·pipeline을 변경하지 않으므로 DB migration rollback은 설계에 없다. 그런 변경이 필요해졌다면 scope 위반으로 재설계한다.

중단 사유는 compatibility 차이 1건 이상, 출처 불명 signal, 금지 쓰기/호출 1회 이상, 안전 출력 실패, 불확실성을 정상으로 표시, 승인 cap 위반, 미승인 provisional 성능 수치로 합격 선언, 누락 benchmark를 재현했다고 주장하는 경우다. D5 최종 수치 미확정은 전체 성능 acceptance 판정 blocker이며 승인 후 초기 측정 자체를 막는 조건은 아니다.

## 13. 완료 보고 형식과 다음 단계

향후 각 gate 보고에는 상태(PASS/FAIL/BLOCKED/NOT RUN), source revision+dirty snapshot ID, 실행 명령·환경·exit code·case 수, artifact 위치, baseline 비교 diff, known limitation, 미결정 ID를 포함한다. 실행하지 않은 항목은 NOT RUN으로 남긴다.

현 단계는 D1~D4 및 D5 구조 승인 결과의 문서 반영만 완료했으며 S1~S5는 NOT RUN이다. D5 성능 수치는 미승인 provisional target이다. 다음 활동은 사용자의 별도 작업 승인 후에만 시작한다. 이후 B1 조사·해소, harness/baseline 확보와 측정, D5 최종 acceptance 수치 확정이 필요하며, 설계 승인만으로 benchmark 조사·복원이나 구현·시험을 시작하지 않는다. B1~B4는 여전히 미해결이며 과거 수치를 현재 baseline으로 사용할 수 없다.

작업 전후 `git status --short`, `git diff --name-only`를 확인한다. untracked 문서는 `git diff --name-only`에 나타나지 않으므로 status와 함께 해석한다. 이번 문서 2개 외 기존 tracked/untracked 파일의 내용이 유지됐는지도 확인하며, 문서 index를 포함한 제3 파일을 수정하지 않는다.
