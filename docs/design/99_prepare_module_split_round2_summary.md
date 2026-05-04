# 99_prepare_module_split_round2_summary

- 문서 상태: prepare module split round2 완료 요약
- 기준 시점: 2026-05-04
- 목적: round2에서 분리한 context summary 계열 모듈 3개를 정리하고, regression 기준과 남은 보류 후보를 고정한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_module_split_round1_summary.md](./99_prepare_module_split_round1_summary.md)
- [99_prepare_module_split_round2_candidate_review.md](./99_prepare_module_split_round2_candidate_review.md)
- [99_prepare_ip_behavior_aggregates_split_plan.md](./99_prepare_ip_behavior_aggregates_split_plan.md)
- [99_prepare_probing_sequence_split_plan.md](./99_prepare_probing_sequence_split_plan.md)
- [99_prepare_mixed_baseline_scanner_split_plan.md](./99_prepare_mixed_baseline_scanner_split_plan.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)

## 1. 결론

prepare module split round2는 완료 상태로 본다.

round2의 목적은 round1 이후 남아 있던 context summary 계열 중 비교적 분리 범위를 좁힐 수 있는 항목을 추가로 분리하는 것이었다.

완료 모듈:

```text
src/prepare/ip_behavior.py
src/prepare/probing_sequence.py
src/prepare/mixed_baseline_scanner.py
```

round2 공통 원칙:

```text
- mechanical refactor만 수행
- 기존 공개 함수명은 wrapper로 유지
- constants 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 직접 변경 없음
- output key 의미 변경 없음
- policy wording 변경 없음
- Apache logs-only 해석 원칙 유지
```

현재 시점에서는 바로 constants.py 대량 분리나 SQLi/XSS/file disclosure hint 분리로 들어가기보다, 남은 후보의 evidence boundary와 constants ownership을 별도 문서로 정리하는 편이 안전하다.

## 2. round2 완료 모듈

### 2.1 ip_behavior.py

기준 커밋:

```text
30ac7d6e3fec31c6777dc124f295780b52bdb321
refactor: extract ip behavior aggregate helpers
```

생성 파일:

```text
src/prepare/ip_behavior.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동 완료 함수:

```text
is_sensitive_ip_behavior_path
finalize_ip_behavior_bucket
build_ip_behavior_aggregates
```

이동하지 않은 constants:

```text
IP_BEHAVIOR_WINDOW_SEC
IP_BEHAVIOR_SAMPLE_REQUEST_LIMIT
IP_BEHAVIOR_SENSITIVE_PATH_LIMIT
```

유지한 output/policy/count:

```text
ip_behavior_aggregates
counts.ip_behavior_aggregates
policy_notes.ip_behavior_aggregates_are_context_only
policy_notes.ip_behavior_window_sec
```

해석 제한:

```text
- 특정 IP를 attacker identity로 단정하지 않음
- source IP만으로 공격 의도, 공격 성공, 침해 성공을 단정하지 않음
- IP 단위 집계는 관찰된 요청 묶음이지 신원 식별 결과가 아님
- lab/source IP를 공격 근거로 사용하지 않음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

### 2.2 probing_sequence.py

기준 커밋:

```text
85a5508e5308d5bcdfc9f1fc14948ed233007f32
refactor: extract probing sequence summary helpers
```

생성 파일:

```text
src/prepare/probing_sequence.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동 완료 함수:

```text
finalize_probing_sequence_bucket
build_probing_sequence_summaries
```

이동하지 않은 constants:

```text
PROBING_SEQUENCE_PATH_PREFIX_HINTS
PROBING_SEQUENCE_PATH_SEGMENT_HINTS
PROBING_SEQUENCE_SUFFIX_HINTS
PROBING_SEQUENCE_WINDOW_SEC
PROBING_SEQUENCE_MIN_REQUESTS
PROBING_SEQUENCE_MIN_DISTINCT_PATHS
PROBING_SEQUENCE_SAMPLE_PATH_LIMIT
```

유지한 output/policy/count:

```text
probing_sequence_summaries
counts.probing_sequence_summaries
policy_notes.probing_sequence_summaries_are_context_only
policy_notes.probing_sequence_window_sec
```

해석 제한:

```text
- 여러 경로를 순회했다는 사실만으로 침해 성공을 단정하지 않음
- scanner-like sequence는 context이지 incident 확정 근거가 아님
- WordPress 존재, admin access, .env/phpinfo/server-status/backup 노출을 단정하지 않음
- status_code=200, content-type, response_body_bytes만으로 성공/노출/침해를 판단하지 않음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

### 2.3 mixed_baseline_scanner.py

기준 커밋:

```text
447779f94041c47713ad3bf68a31d7125a223675
refactor: extract mixed baseline scanner summary helpers
```

생성 파일:

```text
src/prepare/mixed_baseline_scanner.py
```

수정 파일:

```text
src/prepare_llm_input.py
```

이동 완료 함수:

```text
build_mixed_baseline_scanner_row_context
finalize_mixed_baseline_scanner_bucket
build_mixed_baseline_scanner_summaries
```

이동하지 않은 constants:

```text
MIXED_BASELINE_SCANNER_WINDOW_SEC
MIXED_BASELINE_SCANNER_MIN_REQUEST_COUNT
MIXED_BASELINE_SCANNER_SAMPLE_REQUEST_LIMIT
```

유지한 output/policy/count:

```text
mixed_baseline_scanner_summaries
counts.mixed_baseline_scanner_summaries
policy_notes.mixed_baseline_scanner_summaries_are_context_only
policy_notes.mixed_baseline_scanner_window_sec
```

해석 제한:

```text
- scanner-like context만으로 침해 성공을 단정하지 않음
- static/crawler/sensitive/probing/IP context가 섞였다는 이유만으로 공격 확정을 하지 않음
- static file 존재, JS 실행, site structure, crawler identity를 단정하지 않음
- WordPress 존재, admin access, .env/phpinfo/server-status/backup 노출을 단정하지 않음
- status_code=200, content-type, response_body_bytes만으로 성공/노출/침해를 판단하지 않음
```

검증 결과:

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py: 통과
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
```

## 3. round2에서 유지한 계약

round2 전체에서 아래 계약을 유지했다.

```text
- `src/prepare_llm_input.py`의 기존 공개 함수명 wrapper 유지
- 기존 import fallback 패턴 유지
- constants 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- supporting_events 생성/연결 로직 직접 변경 없음
- output key 의미 변경 없음
- counts 의미 변경 없음
- policy_notes 의미 변경 없음
```

특히 아래 context-only 성격을 유지했다.

```text
ip_behavior_aggregates
probing_sequence_summaries
mixed_baseline_scanner_summaries
```

이 세 항목은 incident 확정 근거가 아니라 Stage2 해석을 보조하는 context summary다.

## 4. Apache logs-only 해석 기준

round2 이후에도 아래 해석 제한은 유지한다.

```text
- raw POST body 내용 추정 금지
- response body 원문 추정 금지
- DB query 결과 추정 금지
- 브라우저 실행 여부 추정 금지
- 로그인 성공 / 계정 탈취 / credential stuffing 성공 / lockout 발동 단정 금지
- PUT 업로드 성공 / DELETE 삭제 성공 / TRACE/XST 성공 / CORS 취약점 성공 단정 금지
- protocol bypass / malformed request exploit success / 서버 침해 성공 단정 금지
- static file 존재 / robots/sitemap 내용 / JS 실행 / file exposure / health 정상 여부 단정 금지
- 실제 crawler 여부 / site structure / product/category page existence 단정 금지
- WordPress 존재 / admin access / .env/phpinfo/server-status/backup 노출 단정 금지
- status_code=200, text/html, response_body_bytes만으로 성공·침해·유출 확정 금지
```

실험환경 특화 rule도 계속 금지한다.

```text
- lab-* UA를 공격 근거로 쓰지 않음
- 특정 IP에 과적합하지 않음
- 특정 response size에 과적합하지 않음
- 특정 제품명에 과적합하지 않음
- 특정 route에 과적합하지 않음
```

## 5. round2에서 의도적으로 하지 않은 것

아래 작업은 round2 범위에서 제외했다.

```text
- constants.py 대량 분리
- SQLi hints 분리
- XSS hints 분리
- file_disclosure hints 분리
- Stage2 reporter 구조 변경
- expected fixture 수정
- regression expected 재생성
- candidate/scoring/filtering 기준 변경
- supporting_events 생성/연결 로직 변경
- 새로운 verdict/taxonomy 추가
- policy wording 변경
```

제외 이유:

```text
- constants는 여러 summary/helper에 걸쳐 공유되어 import cycle 위험이 큼
- SQLi/XSS/file_disclosure hints는 evidence boundary와 false positive 처리에 직접 영향을 줄 수 있음
- candidate/scoring/filtering 또는 supporting_events와 결합된 영역은 mechanical refactor 실패 시 영향 범위가 큼
- round2는 context summary 계열 분리를 마무리하는 범위로 제한하는 편이 안전함
```

## 6. 남은 보류 후보

round2 이후 남은 주요 후보는 아래다.

```text
constants.py 대량 분리
SQLi hints
XSS hints
file_disclosure hints
```

### 6.1 constants.py 대량 분리

현재 판단: 바로 진행하지 않음.

이유:

```text
- 여러 summary/helper가 constants를 공유함
- import cycle 위험이 큼
- constants 이동은 behavior 변경이 없어도 regression 실패 시 원인 추적을 어렵게 함
- sensitive/probing/mixed/file disclosure 경계가 아직 완전히 고정되지 않음
```

선행 권장 문서:

```text
docs/design/99_prepare_constants_ownership_map.md
```

### 6.2 SQLi hints

현재 판단: evidence-boundary 검토 후 진행.

이유:

```text
- SQLi hint는 candidate selection, false positive suppression, supporting context와 연결될 가능성이 큼
- Boolean blind/time-based 해석에서 Apache logs-only 한계가 중요함
- DB 결과를 볼 수 없으므로 hint wording과 evidence boundary를 함께 관리해야 함
```

선행 권장 문서:

```text
docs/design/99_prepare_sqli_hints_split_candidate_review.md
```

### 6.3 XSS hints

현재 판단: evidence-boundary 검토 후 진행.

이유:

```text
- XSS는 브라우저 실행 여부를 Apache 로그만으로 단정할 수 없음
- URL/HTML decoding은 필요하지만 실행/impact 단정은 금지해야 함
- Stage2 wording guard와 함께 검토해야 함
```

선행 권장 문서:

```text
docs/design/99_prepare_xss_hints_split_candidate_review.md
```

### 6.4 file_disclosure hints

현재 판단: evidence-boundary 검토 후 진행.

이유:

```text
- suspicious_file_disclosure verdict와 연결됨
- status/content-type/bytes만으로 file exposure를 단정하면 안 됨
- sensitive path probe와 경계가 겹침
```

선행 권장 문서:

```text
docs/design/99_prepare_file_disclosure_hints_split_candidate_review.md
```

## 7. 다음 후보 결정 기준

다음 후보는 아래 기준으로 선택한다.

```text
1. import cycle 위험이 낮을 것
2. constants ownership이 명확할 것
3. candidate/scoring/filtering에 직접 영향을 덜 줄 것
4. supporting_events와 강하게 결합되어 있지 않을 것
5. Apache logs-only evidence boundary를 문서로 먼저 고정할 수 있을 것
6. false positive 처리 의미를 바꾸지 않을 것
7. 실패 시 롤백 범위가 작을 것
```

현재 추천 순서:

```text
1. constants ownership map 작성
2. SQLi/XSS/file_disclosure hints 후보 비교
3. 그 결과에 따라 다음 코드 분리 후보 결정
```

바로 constants.py 대량 분리로 들어가지는 않는다. 먼저 ownership map으로 어떤 constants가 어느 모듈에 속하는지 확인한다.

## 8. 권장 다음 작업

권장 신규 문서:

```text
docs/design/99_prepare_constants_ownership_map.md
```

포함할 내용:

```text
- constants 이름
- 현재 위치
- 현재 사용 함수
- 예상 owner module
- 공유 여부
- 이동 가능 여부
- 이동 금지/보류 이유
- import 방향 원칙
```

그 다음 후보:

```text
docs/design/99_prepare_hints_split_candidate_review.md
```

이 문서는 SQLi/XSS/file_disclosure hints를 한 번에 비교하는 용도로 둘 수 있다.

## 9. 커밋/검증 메모

이 문서는 round2 summary 기록용이다.

문서 작성 시 기대 변경 범위:

```text
docs/design/99_prepare_module_split_round2_summary.md
```

코드 변경은 없다.

문서 전용 커밋 후보:

```text
docs: summarize prepare module split round2
```
