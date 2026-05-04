# 99_prepare_module_split_round1_summary

- 문서 상태: prepare module split round1 완료 요약
- 기준 시점: 2026-05-04
- 목적: `src/prepare_llm_input.py`에서 1차로 분리한 prepare helper/module 범위를 고정하고, regression 기준과 다음 round 후보를 정리한다.

관련 문서:

- [99_prepare_module_split_plan.md](./99_prepare_module_split_plan.md)
- [99_prepare_context_summary_contract.md](./99_prepare_context_summary_contract.md)
- [99_prepare_context_summary_split_candidate.md](./99_prepare_context_summary_split_candidate.md)
- [99_prepare_static_baseline_split_plan.md](./99_prepare_static_baseline_split_plan.md)
- [99_prepare_crawler_baseline_split_plan.md](./99_prepare_crawler_baseline_split_plan.md)
- [99_prepare_sensitive_path_probe_split_plan.md](./99_prepare_sensitive_path_probe_split_plan.md)

## 1. 결론

prepare module split round1은 완료 상태로 본다.

이번 round의 목적은 `prepare_llm_input.py`를 한 번에 전면 재작성하는 것이 아니라, 동작 변경 없이 비교적 경계가 분명한 helper와 summary builder를 작은 단위로 분리하는 것이었다.

round1의 공통 원칙:

```text
- mechanical refactor만 수행
- 기존 공개 함수명은 wrapper로 유지
- constants 대량 이동 없음
- expected/test fixture 수정 없음
- Stage2 reporter 수정 없음
- candidate/scoring/filtering 변경 없음
- output key 의미 변경 없음
- Apache logs-only 해석 원칙 유지
```

현재 시점에서는 바로 다음 코드 분리를 계속 진행하기보다, 이 문서로 round1을 고정한 뒤 round2 후보를 별도 비교하는 편이 안전하다.

## 2. 완료 모듈 목록

round1에서 분리 완료한 모듈은 아래 9개다.

```text
src/prepare/decoders.py
src/prepare/l3_hints.py
src/prepare/models.py
src/prepare/method_summaries.py
src/prepare/protocol_anomalies.py
src/prepare/auth_behavior.py
src/prepare/static_baseline.py
src/prepare/crawler_baseline.py
src/prepare/sensitive_path_probe.py
```

### 2.1 decoders.py

역할:

```text
- URL/HTML/중복 인코딩 등 decoded variant 생성 계열 helper 분리
- Stage1/Stage2 입력 전처리에서 공격 문자열을 Apache 로그 표면 안에서 복원 가능하게 보조
```

유지 조건:

```text
- raw POST body를 새로 추정하지 않음
- response body 원문을 사용하지 않음
- decoded text가 실행되었다고 단정하지 않음
- encoding descriptor는 분석 보조 정보로만 사용
```

### 2.2 l3_hints.py

역할:

```text
- L3 hint 또는 lower-level attack hint 분리
- 공격 구조를 설명하는 보조 신호 정리
```

유지 조건:

```text
- hint 존재만으로 성공/침해를 단정하지 않음
- lab-* User-Agent, 특정 IP, 특정 route를 공격 근거로 일반화하지 않음
- candidate 승격 기준 자체는 변경하지 않음
```

### 2.3 models.py

역할:

```text
- prepare 단계에서 사용하는 데이터 모델/구조 정의 계열 분리
- prepare_llm_input.py 내부의 구조 정의 부담 감소
```

유지 조건:

```text
- JSON output schema 의미 변경 없음
- Stage2 input 계약 변경 없음
- expected fixture 수정 없음
```

### 2.4 method_summaries.py

역할:

```text
- HTTP method 관련 summary builder 분리
- method distribution과 unusual method 관찰 정보를 context로 제공
```

유지 조건:

```text
- PUT 업로드 성공 단정 금지
- DELETE 삭제 성공 단정 금지
- TRACE/XST 성공 단정 금지
- OPTIONS/CORS 취약점 성공 단정 금지
- method 관찰은 Apache access log 표면 신호로만 해석
```

### 2.5 protocol_anomalies.py

역할:

```text
- malformed request, protocol anomaly, suspicious request-line 계열 summary/helper 분리
```

유지 조건:

```text
- protocol bypass 성공 단정 금지
- malformed request exploit success 단정 금지
- 서버 침해 성공 단정 금지
- status_code나 error log 존재만으로 exploit 성공을 판단하지 않음
```

### 2.6 auth_behavior.py

역할:

```text
- login/auth 관련 behavior summary 분리
- credential stuffing 또는 brute-force처럼 보일 수 있는 요청 패턴을 context로 보존
```

유지 조건:

```text
- 로그인 성공 단정 금지
- 계정 탈취 단정 금지
- credential stuffing 성공 단정 금지
- lockout 발동 단정 금지
- 200/302/401/403만으로 계정 상태를 단정하지 않음
```

### 2.7 static_baseline.py

역할:

```text
- static asset baseline summary 분리
- 정적 리소스 요청 패턴을 baseline/context로 제공
```

유지 조건:

```text
- static file 존재 단정 금지
- JS 실행 단정 금지
- robots/sitemap 내용 단정 금지
- file exposure 단정 금지
- 200/text/html 또는 response_body_bytes만으로 파일 노출을 판단하지 않음
```

### 2.8 crawler_baseline.py

역할:

```text
- crawler-like baseline summary 분리
- bot/crawler처럼 보이는 요청 문맥을 context로 보존
```

유지 조건:

```text
- 실제 crawler identity 단정 금지
- site structure 단정 금지
- product/category page existence 단정 금지
- User-Agent 문자열을 신원 증명으로 사용하지 않음
```

### 2.9 sensitive_path_probe.py

역할:

```text
- sensitive path probe summary builder 계열 분리
- .env, .git, phpinfo, server-status, backup/config, admin/wp-login path probing 문맥을 context로 보존
```

이동 완료 함수:

```text
classify_sensitive_path_probe_category
finalize_sensitive_path_probe_bucket
build_sensitive_path_probe_summaries
build_sensitive_path_probe_summary_contexts
```

유지한 구조:

```text
- src/prepare_llm_input.py에 기존 함수명 wrapper 유지
- supporting event 관련 함수는 이동하지 않음
- supporting event 생성/연결 로직은 이동하지 않음
- sensitive path/probing sequence 관련 constants는 이동하지 않음
```

유지 조건:

```text
- WordPress 존재 단정 금지
- admin access 성공 단정 금지
- .env 노출 단정 금지
- phpinfo 노출 단정 금지
- server-status 노출/차단 단정 금지
- backup 노출 단정 금지
- 공격 성공 단정 금지
- status_code=200, content-type, response_body_bytes만으로 노출/성공을 판단하지 않음
```

## 3. regression 기준

round1 진행 중 유지한 기준은 아래다.

```text
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

최근 sensitive path probe split 기준 검증 결과:

```text
py_compile: 통과
python3 scripts/check_prepare_regression.py --strict: pass=18 warn=0 fail=0
python3 scripts/check_stage_dryrun_regression.py --strict: pass=12 warn=0 fail=0
import check: sensitive path probe imports ok
```

round1 summary 작성 자체는 문서 추가만 수행한다. 코드, fixture, expected, Stage2 reporter는 수정하지 않는다.

## 4. 유지해야 할 prepare/Stage2 계약

round2에서도 아래 계약은 깨면 안 된다.

```text
- Stage2 report input key 의미 유지
- pipeline_counts 의미 유지
- policy_notes 의미 유지
- supporting_events 구조 유지
- candidate_rows 의미 유지
- filtered_out 의미 유지
- context-only summary를 incident로 승격하지 않음
- Apache logs-only 해석 한계 유지
```

특히 아래 영역은 과잉 해석 금지를 계속 유지한다.

```text
- raw POST body 내용
- response body 원문
- DB query 결과
- 브라우저 실행 여부
- 로그인 성공 / 계정 탈취 / credential stuffing 성공 / lockout 발동
- PUT 업로드 성공 / DELETE 삭제 성공 / TRACE/XST 성공 / CORS 취약점 성공
- protocol bypass / malformed request exploit success / 서버 침해 성공
- static file 존재 / robots/sitemap 내용 / JS 실행 / file exposure / health 정상 여부
- 실제 crawler 여부 / site structure / product/category page existence
- WordPress 존재 / admin access / .env/phpinfo/server-status/backup 노출
- status_code=200, text/html, response_body_bytes만으로 성공·침해·유출 확정
```

실험환경 특화 rule도 계속 금지한다.

```text
- lab-* UA를 공격 근거로 쓰지 않음
- 특정 IP에 과적합하지 않음
- 특정 response size에 과적합하지 않음
- 특정 제품명에 과적합하지 않음
- 특정 route에 과적합하지 않음
```

## 5. round1에서 의도적으로 하지 않은 것

아래 작업은 round1 범위에서 제외했다.

```text
- prepare_llm_input.py 전면 재작성
- constants.py 대량 분리
- Stage2 reporter 구조 변경
- expected fixture 수정
- regression expected 재생성
- candidate/scoring/filtering 기준 변경
- policy wording 변경
- 새로운 verdict/taxonomy 추가
- 실제 LLM provider별 품질 비교 재수행
```

이 제외 범위는 단순 보류가 아니라 regression 원인 추적성을 위한 제한이다.

## 6. round2 보류 후보

round2 후보는 아래 영역이다.

```text
mixed_baseline_scanner_summaries
probing_sequence_summaries
ip_behavior_aggregates
constants.py 대량 분리
SQLi hints
XSS hints
file_disclosure hints
```

각 후보의 현재 판단은 아래와 같다.

### 6.1 mixed_baseline_scanner_summaries

현재 판단: 보류.

이유:

```text
- 여러 baseline/context 신호가 섞이는 영역일 가능성이 높음
- scanner-like 문맥을 candidate로 과승격할 위험이 있음
- sensitive path probe, crawler/static baseline, probing sequence와 경계가 겹칠 수 있음
```

다음 검토 시 확인할 것:

```text
- output key
- pipeline_counts 영향
- candidate_rows / supporting_events 영향
- context-only summary와 incident 후보의 경계
```

### 6.2 probing_sequence_summaries

현재 판단: round2 후보로 검토 가능하지만 바로 분리하지 않는다.

이유:

```text
- sensitive path/probing constants와 일부 경계가 겹침
- sequence 판단이 scanner-like context와 candidate/supporting 판단에 영향을 줄 수 있음
- path prefix/segment/suffix hint constants 이동 여부를 별도로 판단해야 함
```

다음 검토 시 확인할 것:

```text
- PROBING_SEQUENCE_* constants 사용 위치
- sensitive_path_probe.py와의 의존 방향
- mixed scanner summary와의 중복 여부
- output key와 expected fixture 고정 지점
```

### 6.3 ip_behavior_aggregates

현재 판단: 후보로 검토 가능.

이유:

```text
- 기능 경계가 독립적이면 분리 효과가 큼
- 다만 IP 단위 집계는 특정 IP 과적합으로 오해될 수 있어 문구/해석 제한이 필요함
```

다음 검토 시 확인할 것:

```text
- IP 집계가 candidate scoring에 직접 영향을 주는지
- lab/source IP를 공격 근거로 사용하지 않는지
- supporting_events와 연결되는지
- Stage2 prompt/report에서 IP 해석 제한이 유지되는지
```

### 6.4 constants.py 대량 분리

현재 판단: 비추천. 후순위.

이유:

```text
- 여러 summary/helper가 constants를 공유함
- import cycle 위험이 큼
- constants 이동은 behavior 변경이 없어도 regression 실패 시 원인 추적이 어려움
- round2 초반에는 작은 기능 단위 분리를 우선하는 편이 안전함
```

다음 검토 시 확인할 것:

```text
- constants ownership map 작성
- sensitive/probing/mixed/file disclosure 공유 여부
- import 방향 원칙
- one-module-at-a-time 이동 가능성
```

### 6.5 SQLi hints

현재 판단: 보류.

이유:

```text
- SQLi hint는 candidate selection, false positive suppression, supporting context와 연결될 가능성이 큼
- Boolean blind/time-based 해석에서 logs-only 한계가 중요함
- DB 결과를 볼 수 없으므로 hint wording과 evidence boundary를 함께 관리해야 함
```

다음 검토 시 확인할 것:

```text
- decoded attack hint와 SQLi 구조 hint의 경계
- educational SQL search false positive 처리와의 결합도
- xclose/boolean/time-based evidence boundary
- Stage1/Stage2 carryover 영향
```

### 6.6 XSS hints

현재 판단: 보류.

이유:

```text
- XSS는 브라우저 실행 여부를 Apache 로그만으로 단정할 수 없음
- URL/HTML decoding은 필요하지만 실행/impact 단정은 금지해야 함
- Stage2 wording guard와 함께 검토해야 함
```

다음 검토 시 확인할 것:

```text
- decoded payload reconstruction과 exploit success wording의 분리
- javascript: protocol, event handler, entity encoding 처리 경계
- false positive educational query 처리
```

### 6.7 file_disclosure hints

현재 판단: 보류.

이유:

```text
- suspicious_file_disclosure verdict와 연결됨
- status/content-type/bytes만으로 file exposure를 단정하면 안 됨
- sensitive path probe와 경계가 겹침
```

다음 검토 시 확인할 것:

```text
- sensitive_path_probe_summaries와 file disclosure candidate의 분리 기준
- suspicious_file_disclosure taxonomy와의 연결
- .env/phpinfo/server-status/backup 노출 단정 방지 문구
```

## 7. round2 후보 결정 기준

다음 코드 분리 후보는 아래 기준으로 고른다.

```text
1. output key와 expected fixture 영향이 작을 것
2. candidate/scoring/filtering에 직접 영향을 덜 줄 것
3. supporting_events와 강하게 결합되어 있지 않을 것
4. constants 이동을 최소화할 수 있을 것
5. Apache logs-only 해석 제한을 독립적으로 문서화할 수 있을 것
6. 실패 시 롤백 범위가 작을 것
```

현재 우선순위 초안:

```text
1. ip_behavior_aggregates 검토
2. probing_sequence_summaries 검토
3. mixed_baseline_scanner_summaries 검토
4. constants.py 대량 분리 검토
5. SQLi/XSS/file_disclosure hints는 별도 evidence-boundary 문서 이후 검토
```

단, 이 우선순위는 코드 grep과 호출부 확인 전의 문서상 초안이다. 실제 round2 작업 전에는 각 후보의 함수명, 호출 위치, output key, expected fixture 의존성을 먼저 확인한다.

## 8. 권장 다음 작업

바로 다음 작업은 코드 분리가 아니라 round2 후보 비교 문서 작성이다.

권장 신규 문서:

```text
docs/design/99_prepare_module_split_round2_candidate_review.md
```

포함할 내용:

```text
- mixed/probing/ip/constants 후보별 함수명과 호출 위치
- output key / pipeline_counts / supporting_events 영향
- constants 의존성
- regression fixture 영향
- Apache logs-only 해석 제한
- 최종 next split candidate 결정
```

그 다음에야 실제 코드 분리 계획 문서를 하나 선택해서 작성한다.

가능한 다음 split plan 후보:

```text
docs/design/99_prepare_ip_behavior_aggregates_split_plan.md
docs/design/99_prepare_probing_sequence_split_plan.md
docs/design/99_prepare_mixed_baseline_scanner_split_plan.md
```

## 9. 커밋/검증 메모

이 문서는 round1 summary 기록용이다.

문서 작성 시 기대 변경 범위:

```text
docs/design/99_prepare_module_split_round1_summary.md
```

코드 변경은 없다.

문서 전용 커밋 후보:

```text
docs: summarize prepare module split round1
```
