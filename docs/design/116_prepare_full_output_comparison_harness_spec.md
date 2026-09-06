# Prepare 전체 반환값 비교 harness 명세 — B2-A

- 작성일: 2026-09-05
- 상태: B1.5 기준 결정 반영, B2-A 명세 작성 완료. 아래 CLI·schema·gate는 구현 제안이며 실행 결과가 아니다.
- 승인된 장기 구현 및 compatibility 기준: `f25cc0fbd65a628ad62129b4ba477f9cc2726807`.
- 사용자 변경 보존 기준 HEAD: `907c9d3b7cd3636ca309ae68d878a1d77bcbd34f` 및 해당 dirty tree의 Live v3.1 파일.
- 이번 범위: 사용자 변경 snapshot 및 이 명세만 작성. harness·extractor 구현, 테스트·benchmark 실행, baseline·결과 JSON 생성 없음.

## 1. 승인 사실, 소스 근거 및 번호

**승인 사실:** C는 현재 Live 사용자 작업을 보존하면서 최신 main으로 안전하게 전환하는 방식이다. 두 revision 사이 결과 동등성을 요구하는 장기 이중 구현이 아니다. 공용화 전후 차이 0은 동일한 최신 기준 source에서의 extractor 분리 전후에 적용한다.

**확인 사실:** `git rev-list --left-right --count HEAD...origin/main`은 `0 22`였다. `git show d412cb67c1f4aca593909c335f7e6feb752ff6c4`의 부모는 과거 benchmark commit `1f2acbb2ad4270d7f8d416124755269d87ee4f46`과 사용자 HEAD다. 최신 main의 traversal/resource 수정은 `c2092e925fd526ace1b653784fb8207f9ee54a76`, CMDi/XSS 및 substantive candidate gate 수정은 `9d299641195edee738f21b50d542c938b4bf3273`에 있다.

`git diff 1f2acbb f25cc0f -- src/external_benchmark_prepare.py benchmarks/schemas/external_security_benchmark_prepare_result.v1.schema.json`에는 차이가 없다. 그러나 production Prepare와 benchmark 테스트·manifest expectation은 달라졌다. 과거 `8/19`, `6/8`은 최신 baseline이 아니며 최신 main에 이미 반영된 수정은 extractor regression으로 기록하지 않는다.

**확인 사실:** 원격 `docs/design` 최대 번호는 113이다. 111의 빈 번호를 재사용하지 않고 이후 번호를 제안한다. 다음 114·115는 제안일 뿐 예약·생성하지 않았다. 현재 103·104는 수정하거나 삭제하지 않았다.

| 처리 | 경로 | 내용 |
| --- | --- | --- |
| 향후 생성 제안 | `114_shared_security_signal_extractor_design.md` | 기존 103 전체 내용·승인 이력 보존, 최신 source·B1.5·D2 재검토를 명시적으로 반영 |
| 향후 생성 제안 | `115_shared_security_signal_extractor_regression_plan.md` | 기존 104 전체 내용·승인 이력 보존, 최신 corpus와 세 기대값 계열 반영 |
| 이번 생성 | `116_prepare_full_output_comparison_harness_spec.md` | 이 명세 |

원격의 `103_external_benchmark_mapping_boundary_review.md`, `104_external_benchmark_930100_3_classification_review.md`, `105_external_security_benchmark_multifamily_design.md`와 로컬 설계 번호는 충돌하지만 파일 경로는 다르다. 향후 생성 직전 번호를 다시 검사한다. 원격 문서와 기존 로컬 문서는 덮어쓰지 않는다.

## 2. 사용자 변경 보존 결과

snapshot: `/tmp/live-v31-preservation-20260905-457a8rym`.

- `files/`: 허용된 Live 코드·테스트·문서 18개, 원래 상대 경로 유지.
- `source_manifest.tsv`, `snapshot_manifest.tsv`: 상대 경로·바이트 크기·mode·SHA-256·tracked 여부·원격 동일 경로 여부.
- 두 manifest의 SHA-256: `58feb41084d2f87d9f0b90f492818980332d1bb9956ceffae18e81ee4150a368`.
- `git_state_before.txt`: HEAD·branch·upstream·원격 SHA·status·unstaged/staged 목록·untracked 목록.
- `보존_안내.md`: 제외 범위·복원 조건·보관 한계.

**확인 사실:** 원본과 복사본 18개 모두 경로·크기·mode·SHA-256이 일치했다. snapshot 생성 직후 Git 상태도 동일했다. tracked 변경 4개는 원격에도 존재하지만 HEAD와 원격 사이 해당 파일 diff는 없으며, 나머지 보존 파일은 원격에 동일 경로가 없다.

환경변수 실제 값, `.env`, 비밀 설정, `.venv`, 운영 로그, DB dump, 인증정보, Git 내부 파일, benchmark 원본은 수집하지 않았다. 배포 ZIP과 로그 점검 결과 파일도 제외했다. 테스트의 합성 오류 문자열과 문서의 자리표시자는 그대로 보존했다.

상위 snapshot 디렉터리는 0700이며 내부 파일 mode는 원본과 같다. 이는 전체 실행 tree나 환경 복제가 아닌 복원용 overlay이다. `/tmp`는 영구 보관소가 아니므로 향후 통합 전 승인된 장기 보관소에 복제하고 manifest를 재검증해야 한다. Git 기준 source 및 의존성 환경은 별도로 확보해야 한다. 이 문서는 복원·merge 실행 승인이 아니다.

### 후속 조치 완료 상태 (2026-09-06 확인)

작성 당시 `/tmp/live-v31-preservation-20260905-457a8rym`에 있던 임시 snapshot은 현재 존재하지 않는다. 장기 보존본 `/home/user/backups/live-v31-preservation-20260905`와 검증자료 `/home/user/backups/live-v31-preservation-20260905-verification`은 현재 존재한다. `/home/user/backups`와 확인한 두 보존 디렉터리의 mode는 모두 `700`이다.

검증 목록 `source_before.tsv`, `source_after.tsv`, `backup.tsv`는 각각 header를 제외한 22개 항목이며, 세 파일의 SHA-256은 모두 `e7dba358b4f704bec399bf7a90783e23f82aa6b81ff707e83dc246df2da77132`와 일치한다. B2-A 최종 판정은 `PASS`이다.

이 후속 확인은 위의 작성 당시 역사적 설명을 대체하지 않는다. 또한 복원, 통합, B2-B 구현 또는 baseline 실행 승인이 아니다.

## 3. 입력 세트와 식별 계약

**승인 범위:** 아래 다섯 corpus를 사용한다. 실입력 파일 및 baseline은 향후 실행 승인 후 생성한다. 파일 경로만으로 입력 identity를 확정하지 않는다.

| corpus | 실제 소스 근거 | B2 입력 방식 |
| --- | --- | --- |
| Prepare regression | 기준 revision의 `tests/fixtures/prepare_regression/*.json` 25개 | 전체 export payload 보존. 같은 revision의 `tests/expected/prepare_regression`은 별도 의미 검사에 사용 |
| CRS path/file-access | `benchmarks/manifests/owasp_crs_path_file_access.v1.json`, `src/external_benchmark_prepare.py` | 36개 전체 inventory 보존. 기존 adapter가 허용하는 direct 27개를 격리 평가. partial 3개·body 관찰 제외 6개는 미실행 사유 보존 |
| multi-family CRS | `benchmarks/suites/owasp_crs_multi_family.v1.json`, `src/external_benchmark_prepare_multifamily.py` | path/file 36, CMDi 18, XSS 19, SQLi 20의 93개 inventory. 위 36개와 중복 case를 한 번만 입력 등록하고 suite 소속은 모두 유지 |
| CSIC reviewed subset | `benchmarks/manifests/csic2010_source.v1.json`, `csic2010_reviewed_semantic_subset.v1.json`, `src/external_benchmark_csic2010_prepare.py` | 아래 재현 조건을 충족한 reviewed identity만 projection. corpus 전체를 자동 추가하지 않음 |
| Live 전용 경계 | 승인 D2와 본 명세의 case 목록 | 합성 입력만 사용. raw body를 관찰 입력으로 주입하지 않음. Prepare 측 compatibility와 Live 채택 기대값은 별개 |

CRS source revision은 `96d9f99043b89f07fb5a4fdad1d7effbbbbcec1a`다. `benchmarks/sources/owasp_crs/<revision>/` 및 `multi_family/SOURCE.json`의 파일 목록·checksum과 실제 source bytes를 검증해야 한다. 파일명이나 source rule ID를 detector 정답으로 해석하지 않는다.

case identity는 `corpus_id + case_id + source_revision + source_file_sha256 + adapter_version + parameter_id`로 고정한다. adapter 코드 SHA와 projection 이후 payload SHA도 기록한다. raw 입력 hash와 projection hash를 구분한다. byte가 같은 CRS case도 source identity가 다르면 합치지 않는다. suite 소속 중복만 제거한다.

외부 benchmark는 단일 행 입력 투영을 재사용할 수 있지만 축약 결과를 full-output baseline으로 재사용할 수 없다. `evaluate_prepare_case()`는 반환값 중 `_llm_input`, `_noise`를 버리고 일부 reason을 정리하므로 B2는 `build_outputs()` 호출 경계에서 5개 반환값 전체를 직접 capture해야 한다.

## 4. case와 parameter matrix

**명세 제안:** 각 행을 고유 parameter ID로 확정하고 before/after에서 동일 matrix를 실행한다. 무의미한 전체 직교곱이나 누락 case 자동 건너뛰기를 금지한다.

| 계열 | matrix |
| --- | --- |
| 기준 실행 | 모든 지원 입력에 `min_score=4`, `min_repeat_aggregate=3`; 원본 fixture의 지원 source를 명시. CRS/CSIC는 `source_tables=['security']` |
| score 경계 | 합성 의미 case에 `min_score=3,4,5,6`. 검사하려는 기존 score S가 이 범위 밖이면 S-1/S/S+1을 case manifest에 명시하여 추가 |
| aggregation 경계 | 같은 그룹의 2/3/4행과 `min_repeat_aggregate=2,3,4`. 반복·대표 후보·supporting events가 발생하도록 기존 group key와 시간 창을 보존 |
| source 경계 | 실제 export schema에 맞춘 `access`, `security`, `error` 개별 및 세 source 혼합. 혼합 source 순서의 정방향/역방향을 각각 독립 case로 등록 |
| 순서·중복 | 같은 timestamp, 중복 request ID, 다른 source의 동일 ID, 동일 원문 반복, 원래 순서/역순. 순서 변경 입력끼리 결과 같음을 요구하지 않음 |
| 값·형태 | 빈 payload의 지원 형태, 빈 행 목록, 누락 field, NULL, 빈 문자열, 숫자형/문자열 ID, naive/offset 시간. 지원하지 않는 형태는 명시적 오류 case |
| normalization | 원문·단일/이중 URL decode·HTML entity·혼합 변환·중복 variant·plus·잘못된 escape·Unicode. 4095/4096/4097 code point 및 경계 직전/직후 signal |
| Live 제한 | 0/1/50행, 누락 target/URI, 파생 query, 긴 문자열, variant/output cap 초과, 부분 처리·detector 오류. 51행은 기존 서비스 제한 계약 확인용 별도 case |

CRS와 CSIC의 단일 행 source 순서를 공격 반복·session으로 해석하지 않는다. aggregation 합성 case는 외부 benchmark 지표와 별도 집계한다. 파라미터를 생략하여 CLI 기본값에 의존하지 않는다.

Live 전용 case에는 다음을 명시적으로 포함한다.

- 같은 source/variant/구조의 quote 종료+boolean 조건, quote 종료+UNION SELECT+열 열거.
- `img_onerror`, `svg_onload`가 찾는 태그 속성; 서로 다른 parameter의 조각을 합친 가짜 구조는 제외.
- 구분자+지원 command. 최신 main에서 확장된 `pipe_exec`/`semicolon_exec` 어휘를 별도 목록으로 고정하고 adoption 범위를 검토한다. `and_exec`, `shell_invocation`, `subshell`은 기존 최초 allowlist로 자동 편입하지 않는다.
- 동일 구조의 PHP filter wrapper+base64 filter+resource.
- `;environment`, bare `document.cookie`, bare `url(javascript:alert())`, SQL `;INSERT`의 false-positive 경계. SQL 문자열에서 CMDi를 새로 만들지 않는다.
- traversal 후보 검토용 `../foo`, 단일 backslash 경로, 명시적 triple-dot, embedded `foo../bar`·`foo.../bar`, 직접 `/etc/passwd`·`win.ini`, `930100.3`의 encoded 경계.

**승인 유지:** D1·D3·D4·D5 구조는 유지한다. D2 traversal은 최신 main의 corrected 사례 중 검증된 subset만 향후 adoption 후보로 정한다. 이번에 활성화하지 않으며, 테스트 파일 존재만으로 검증 완료라고 표시하지 않는다. 직접 resource token을 traversal/CWE-22로 올리지 않는다. `930100.3`의 현재 sensitive-only 결과와 의미상 traversal 기대값은 서로 다른 계열에서 관리한다.

## 5. clock 및 실행 격리

**확인 사실:** 기준 `build_outputs()`의 `llm_input.meta.prepared_at`은 `datetime.now().astimezone().isoformat(timespec='milliseconds')`로 생성된다.

**명세 제안:** production을 수정하지 않고 harness 전용 별도 process에서 `src.prepare_llm_input.datetime`에 실제 datetime의 파싱·산술을 유지하는 고정 clock 대체 타입을 주입한다. 기준 instant는 `2026-01-01T00:00:00+09:00`, process timezone은 `Asia/Seoul`로 고정한다. `now(tz=None)`와 `now(tz=...)` 계약을 구분하고 실제 반환 timestamp를 확인한다. 환경 전체를 dump하지 않고 Python·OS·의존성 버전, timezone, seed, locale처럼 승인된 비밀 아닌 항목만 기록한다.

입력의 log_time·analysis window·exported_at은 제거하거나 현재 시각으로 바꾸지 않는다. 다른 wall-clock 의존이 발견되면 목록을 확정하고 통제 전 BLOCKED로 둔다. 시간 field 전체 삭제나 정규식 mask는 금지한다. monotonic clock은 성능 측정용으로 별도 유지하며 결정적 출력 비교에 넣지 않는다. patch는 process 종료 또는 finally로 해제한다.

before와 after는 각각 고정된 별도 source 경로와 독립 process에서 import한다. import origin과 실제 source SHA를 확인하며 현재 tree의 모듈이 섞이면 중단한다. 실행 준비는 별도 승인 대상이며 현재 branch를 전환하지 않는다. bytecode·결과 파일은 원본 source에 쓰지 않도록 구성한다. DB·네트워크·LLM 호출은 차단하고 Stage1·Mapping·Stage2·Job 실행을 harness 흐름에 포함하지 않는다. Stage1용 `external_benchmark_stage1_multifamily_live.py`는 Live Monitoring runtime도, B2 실행 경로도 아니다.

## 6. capture schema

**확인 사실:** 반환 순서는 아래 5-tuple이다. **제안 schema**는 다섯 slot 전체와 타입 정보를 보존한다.

```text
capture_schema_version: prepare_full_output_capture.v1
source_identity: revision, source_tree_digest, harness_digest, adapter_digest
input_identity: corpus_id, case_id, source_hash, projected_payload_hash
parameters: parameter_id, min_score, min_repeat_aggregate, source_tables
clock: fixed_instant, process_timezone
execution: returned | raised
input_before: typed_node
input_after: typed_node
input_mutated: boolean
return_value:
  type: tuple
  items:
    0: llm_input                 # dict
    1: candidate_payload         # list
    2: noise_payload             # list
    3: filtered_reasons_payload   # dict
    4: filtered_payload          # list
exception: null | {qualified_type, message}
```

typed_node은 `null`, `bool`, `int`, `float`, `str`, `list`, `tuple`, `dict`를 구분한다. dict는 key/value node의 순서 있는 entry 배열로 capture하여 원래 삽입 순서도 잃지 않는다. int는 십진 문자열, float는 `float.hex()`를 사용하여 큰 정수·음수 0을 손실 없이 보존한다. 비유한 float 또는 지원하지 않는 객체는 임의 문자열 변환 대신 capture 오류로 중단한다. 문자열 escape는 저장 표현이며 비교 전 원래 문자열로 복원한다. 예상 tuple 길이·각 slot 타입이 다르면 계약 위반이다.

이는 향후 JSON artifact의 논리 구조 제안이다. 이번에는 schema 파일이나 JSON을 만들지 않았다. raw 원문이 포함되는 capture는 허용 corpus에 한정하고 접근을 제한한다. 터미널 요약에는 원문 대신 case ID와 경로를 표시한다.

## 7. 비교·mutation·반복 규칙

1. 타입부터 재귀 비교한다. `True`, `1`, `1.0`, `'1'`은 다르다. 누락 key, NULL, 빈 문자열, 빈 list, 0은 서로 다르다.
2. list/tuple 순서와 중복 횟수는 반드시 같아야 한다. reason 문자열의 공백·대소문자·`(+N)`·삽입 위치를 그대로 비교한다. set 변환·정렬·공백 정규화는 금지한다.
3. dict key의 존재와 값은 엄격 비교한다. 삽입 순서는 별도 차이로 보존·보고하되 의미 동등성 gate와 구분한다. key 순서까지 보호할 직렬화 산출물이 있다면 별도 byte-order gate를 명시적으로 추가하며 조용히 무시하지 않는다.
4. score·verdict_hint, 후보·탈락 행, noise, 모든 summary, supporting events, dedup 대표·merged ID, source·시간·메타데이터를 포함한다. 이름을 모르는 신규 field도 버리지 않는다.
5. 호출 직전 typed capture와 호출 직후 payload를 비교해 input mutation을 검사한다. 매 호출마다 fresh deep copy를 사용하고 재사용 입력 연속 호출도 별도로 확인한다. input mutation 발견은 source 동등성 여부와 무관하게 BLOCKED 후 원인 검토한다. production을 조용히 수정하지 않는다.
6. before 두 번은 동일 source·환경·matrix·clock으로 독립 process에서 실행하고 전체 결과가 같아야 한다. 동일 process 연속 호출 및 case 실행 순서 역전은 상태 누출 확인용 추가 검사다. comparison artifact 자체의 실행 ID·실행 시간은 출력 capture와 분리한다.
7. unexpected exception은 실패다. 명시된 오류 case만 exception 타입·메시지·input mutation을 비교한다. 두 번 모두 오류였다는 이유로 일반 case를 통과시키지 않는다. 성공 case 수와 전체 inventory를 함께 검사한다.

기존 `scripts/check_prepare_regression.py`의 MUST/MUST_NOT/SHOULD/KNOWN_LIMITATION 결과는 독립 보고한다. 그것만으로 5개 반환값 동등성을 선언하지 않으며, 현재 expected와 최신 코드가 충돌하면 별도 검토한다.

## 8. 기대값 계열과 diff

| 계열 | 기준 | 합격 의미 |
| --- | --- | --- |
| compatibility | `f25cc0f…`의 실제 변경 전 전체 반환값 | 같은 입력에서 공용화 전후 타입·값·배열 순서·중복·누락 차이 0 |
| corrected | 별도로 승인한 의미상 기대값 및 변경 기록 | 알려진 오류·coverage gap을 별도 변경에서 검증. compatibility 기대값을 덮어쓰지 않음 |
| live_adoption | Live의 제한된 입력·allowlist·provenance·표시 계약 | 공격 verdict 없이 관찰 신호와 상태·참고 taxonomy만 올바르게 제공 |

최신 main에 이미 들어간 traversal/resource/CMDi/XSS 수정은 compatibility의 일부다. 과거 HEAD 결과와 비교한 이동은 역사적 source 차이이며 extractor regression으로 집계하지 않는다. Live의 `processing_status=complete|partial|unavailable|error`와 `assessment=review_required|no_signal|undetermined`는 별도 축이다. `no_signal`은 complete이고 채택 신호가 없을 때만 가능하다. budget 초과·관찰 누락을 신호 없음으로 치환하지 않는다. Mapping의 verdict 정책을 Live에서 실행하지 않는다.

diff record 제안:

```text
expectation_family, corpus_id, case_id, parameter_id
slot_name, json_pointer, difference_kind
before_present, after_present, before_type, after_type
before_typed_value, after_typed_value
```

`difference_kind`는 `type_changed`, `value_changed`, `missing`, `added`, `length_changed`, `sequence_changed`, `dict_order_changed`, `input_mutation`, `exception_changed`를 구분한다. JSON Pointer escape 규칙을 따른다. 배열 중간 삽입을 정렬로 숨기지 않으며 전체 diff는 artifact에 보존하고 터미널에는 개수와 위치만 표시한다. 요약 잘림이 실제 diff 유실로 이어지면 중단한다.

## 9. CLI 및 artifact 제안

아래 `prepare-full-output-harness`는 아직 존재하지 않는 **제안 CLI**이며 실행 명령이 아니다.

```text
prepare-full-output-harness inventory --source-root PATH --revision SHA --case-manifest PATH
prepare-full-output-harness capture --source-root PATH --revision SHA --case-manifest PATH --matrix PATH --clock ISO8601 --timezone Asia/Seoul --expectation-family compatibility --run-id ID --output-root NEW_PATH
prepare-full-output-harness compare --before RUN_PATH --after RUN_PATH --expectation-family compatibility --output-root NEW_PATH
prepare-full-output-harness self-check --output-root NEW_PATH
```

source-root·revision·case manifest·matrix·clock은 필수이며 compare는 identity 불일치를 거부한다. 허용된 after source 변경 목록은 별도 승인 기록으로 연결한다. baseline 저장 경로가 존재하면 실패하고 `--force`·덮어쓰기 옵션은 제공하지 않는다. symlink 경로와 before/after 동일 output 경로를 거부한다. 실행 실패 산출물은 미완료로 남기고 baseline으로 승격하지 않는다. corpus 제외를 CLI에서 조용히 허용하지 않는다.

향후 디렉터리 제안:

```text
<approved-artifact-root>/<unique-run-id>/
  run_manifest.json
  inventory.json
  environment.json
  checksums.sha256
  compatibility/
    captures/<case-key>/<parameter-id>.json
    gate.json
  corrected/
    expectations.json
    gate.json
  live_adoption/
    expectations.json
    gate.json
  comparison/
    differences.jsonl
    summary.json
  completion.json
```

before-1, before-2, after는 별개의 run 디렉터리다. 기대값만 있고 구현이 없는 계열은 `NOT RUN`으로 기록한다. comparison은 기존 run에 쓰지 않고 새 디렉터리에 생성한다. 파일 checksum·완료 marker를 최종 작성하고 기존 baseline은 읽기 전용으로 사용한다. 이 구조의 파일은 이번에 생성하지 않았다.

## 10. CSIC 재현 조건

**확인 사실:** source manifest에는 세 원문 파일이 Git 미추적이며 재배포 상태가 불명확하다고 기록되어 있다. 미러 URL의 branch 이름은 고정 revision이 아니므로 URL만으로 재현성을 주장하지 않는다. 현재 tree의 `benchmarks/` 조사에서 CSIC cache 디렉터리는 없었다.

| 파일 | manifest의 SHA-256 |
| --- | --- |
| `normalTrafficTraining.txt` | `d51de812d9201ef2b173b6ae3e3e740c309047ac85545c06c51d6fb1ddbc1e63` |
| `normalTrafficTest.txt` | `f05dfc312d5d14fd1ed8371de27a9e4deab3dc09265f5d7f9df2643df8385089` |
| `anomalousTrafficTest.txt` | `12fa4f0d496ceb859bb2652abf7f0f0ed8c59e1d9ce501b8a9a0ef38a625c046` |

이는 CSIC가 발행한 공식 checksum이 아니라, 해당 manifest에 기록된 미러 내용의 고정값이다.

실행 전에 source bytes의 크기와 checksum, parser revision, review manifest checksum, 각 request의 source file/index/raw_request_sha256를 대조한다.

**실행 조건:** 위 원문 전체 파일과 reviewed case의 source file/index/raw request hash가 일치해야 한다. parser·projection 코드 및 두 manifest를 모두 `f25cc0f…`에 고정한다. bytes 크기도 source manifest와 대조한다. hash 불일치·누락·parse 오류·review identity 미해결 시 CSIC gate는 BLOCKED다. 자동 다운로드·다른 미러 대체·재주석을 수행하지 않는다.

`project_request()`가 보존하는 method·raw target·URI/query·로그에 보이는 metadata만 입력으로 사용한다. body·Cookie 값·Authorization 값·기타 미관찰 header를 raw_request에 붙이지 않는다. source label·review label은 Prepare 입력에 유입하지 않는다. source_normal/source_anomalous를 자동 TP/FP label로 쓰지 않는다.

reviewed manifest의 222개 inventory는 identity와 validation 상태를 보존한다. provisional_unvalidated는 canonical corrected 정답으로 승격하지 않는다. validated/adjudicated, ambiguous, not-scored를 구분한다. Stage1 eligibility 111개는 B2의 입력 개수 정의가 아니다. traversal exact support가 없다는 기존 review 기록을 근거로 CSIC를 CRS traversal 대체물로 쓰지 않는다. CSIC raw source가 없어도 B2-A 명세는 작성할 수 있지만, 승인 corpus 전체의 실행 PASS는 선언할 수 없다.

## 11. harness 자체 검증과 gate

**향후 자체 검증 기준:** fixture 복제 없이 작은 합성 반환 객체로 한 field 삭제, NULL 치환, bool/int 변경, reason 중복 삭제, list 순서 변경, 큰 정수 변형, tuple/list 변형, 신규 field 삽입을 각각 주입했을 때 올바른 diff가 나와야 한다. 동일 capture는 diff 0이어야 한다. input mutation·고정 clock·case 누락·checksum 변경·잘못된 import origin·미완료 artifact·baseline 덮어쓰기를 각각 검출해야 한다. 허용되지 않은 네트워크·DB·LLM 호출 및 source 쓰기가 0회인지 독립적으로 검증한다. 이 검증 코드는 아직 구현·실행하지 않았다.

| gate | PASS | BLOCKED 또는 중단 |
| --- | --- | --- |
| 보존 | 18개 원본/복사본 manifest 일치 | source 변경 감지, 누락·해시 불일치. 통합 전 장기 보관 미확보 |
| source/corpus 준비 | 고정 revision·identity·matrix·모든 필수 source 검증 | CSIC 누락, 잘못된 source import, corpus identity 변경 |
| harness 신뢰성 | 자체 검증·clock 통제·input 불변성 확인 | 검증 미실행, mutation, 지원하지 않는 capture 타입 |
| before 반복 | 두 before 전체 동등·inventory 완전 | 비결정적 출력·예상치 못한 예외·누락 case |
| compatibility | 같은 최신 기준에서 전체 반환값 차이 0 | 실제 차이는 FAIL, 비교 전제 부족은 BLOCKED. 코드·기대값 수정으로 자동 봉합 금지 |
| corrected/live_adoption | 각 계열 별도 승인 기대값 충족 | 미승인 기대값, traversal 자동 활성화, 부정확한 no_signal |

CLI 종료값 제안은 PASS=0, FAIL=1, BLOCKED=2다. 실행하지 않은 gate는 NOT RUN이며 PASS로 취급하지 않는다. STOP은 작업 제어 결정이고 원인에 따라 FAIL 또는 BLOCKED를 기록한다. 한 계열 PASS가 다른 계열을 해제하지 않는다.

**성능:** 최대 50행·5초 polling 조건을 보존한다. 10ms/행·250ms/페이지·p95/p99·메모리 수치는 provisional target 또는 측정 가설이며 acceptance가 아니다. correctness clock과 성능 측정을 분리한다. 성능 harness·baseline 측정 후 환경과 최종 수치를 별도 승인한다. regex 실행 중 강제 시간 제한을 보장하지 못하는 협력적 budget의 한계를 유지한다.

## 12. 다음 단계의 미결정 사항

1. 임시 snapshot의 장기 보관 위치와 별도 source 실행 경로. 현재 tree 자동 전환은 승인하지 않음.
2. 제안한 114·115 생성 및 전체 승인 이력을 보존하는 갱신 범위 승인.
3. 최신 CMDi 어휘의 Live 최초 채택 subset과 corrected traversal의 후보별 검증·추후 활성화 승인. ID 의미는 유지하되 규칙 경계 변경에는 rule revision, 채택 변경에는 adoption policy version을 적용.
4. corpus case manifest·parameter matrix의 구체 목록과 source 확보. CSIC 미확보 상태를 별도 BLOCKED로 유지하며 필수 corpus 축소에는 별도 승인 필요.
5. 제안 capture/CLI/gate 계약 검토 후 harness 구현·자체 검증·baseline 실행을 각각 승인. 이번 명세 작성은 그 실행 승인이 아님.
6. D5 성능 acceptance는 측정 후 결정. Prepare score·threshold·filter·aggregation 및 Mapping verdict 정책은 Live에 연결하지 않음.
