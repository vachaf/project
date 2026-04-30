# 99_비교실험_후속개선_TODO

- 작성일: 2026-04-30
- 문서 역할: A/B/C/D/E 비교실험 이후 남은 후속 개선 과제 정리
- 기준: Apache 로그 표면 기반 LLM 분석 파이프라인

---

## 1. 현재 우선순위 요약

| 우선순위 | 과제 | 이유 |
|---|---|---|
| P1 | 회귀 fixture 정리 | B/C/D/E 개선이 누적되어 다음 수정 때 기존 기능이 깨질 가능성이 커짐 |
| Done | `suspicious_file_disclosure` verdict 정식화 | Stage1 enum/prompt에 verdict 추가, PHP wrapper 3종 hint 조합에서 좁은 정규화 반영 |
| Done | benign normal search hint 정리 | `benign_normal_search` baseline row의 `dir_probe:*` hint 제거 및 회귀 `MUST_NOT` 반영 완료 |
| P2 | SQLi xclose/quote termination hint 추가 | B/E SQLi payload 설명력 강화 |
| P2 | Stage2 PHP wrapper 설명 보강 | `php://filter/convert.base64-encode` source disclosure 의미를 더 안정적으로 설명 |
| P3 | F세트 Auth/Login abuse 설계 | 새 공격 유형 확장 후보. POST body visibility 한계 주의 필요 |
| P3 | G세트 HTTP method/protocol anomaly 설계 | 앱 의존도가 낮은 reconnaissance/anomaly 후보 |

---

## 2. P1 — 회귀 fixture 정리

### 배경

현재까지 다음 코드 개선이 누적되었다.

- URL decode depth 1/2
- HTML entity decode
- educational SQL/XSS false positive 완화
- `supporting_events`
- `false_positive_review_candidates`
- `probing_sequence_summaries`
- PHP file disclosure hint
- normal search baseline/reference baseline 분리

수정이 많아졌으므로, 이후 작은 개선이 B/C/D/E 중 하나를 깨뜨릴 수 있다. 실제 raw를 매번 수동으로 찾아 돌리는 방식은 장기적으로 불안정하다.

### 권장 fixture 묶음

| 세트 | fixture 목적 | 기대 결과 |
|---|---|---|
| B세트 R2B | double decoded SQLi | double encoded SQLi candidate 유지 |
| B세트 R2B | educational SQL FP | educational SQL search는 likely_false_positive 또는 FP category 유지 |
| B세트 R2B | supporting_events | temporal chain 저신호 step이 context로 보존 |
| C세트 | HTML entity XSS | `encoding:html_entity_decoded_xss` 유지 |
| C세트 | XSS FP review | tutorial/onerror 검색은 false positive review context 유지 |
| D세트 R3 | directory probing sequence | `probing_sequence_summaries=1` 유지, candidate 과승격 없음 |
| E세트 R2/R2B | PHP wrapper | wrapper variant는 `suspicious_file_disclosure` candidate 유지 |
| E세트 R2/R2B | direct config path | `/config.php`, `/admin/config.php`는 context-only 또는 low-signal 유지 |
| E세트 R3/R3B | OpenCart search SQLi/XSS | SQLi 1, XSS 2 candidate 유지 |
| E세트 R3B | normal search baseline | normal search는 `benign_normal_search` / `reference_baseline` 유지 |

### 권장 구현 방식

- `tests/fixtures/` 또는 `lab/regression_fixtures/` 아래 최소 JSON fixture 저장
- raw 전체가 부담되면 필요한 row만 축약한 synthetic fixture 사용
- 공개 repo에 올릴 수 있는 수준으로 IP/host/path 노출을 검토
- `prepare_llm_input.py` 기준 smoke test부터 시작
- Stage1/Stage2 LLM 호출은 비용 때문에 기본 회귀에서는 제외하고 dry-run 또는 prompt input 구조만 확인

---

## 3. 완료 — `suspicious_file_disclosure` verdict 정식화

### 배경

E세트 R2/R2B에서 `php://filter`, `resource=config.php`, `convert.base64-encode` 계열 payload는 prepare 단계에서 `suspicious_file_disclosure` hint로 잘 보존된다. 그러나 Stage1 최종 verdict는 여전히 `suspicious_path_traversal`로 수렴하는 경향이 있다.

### 문제

`php://filter/convert.base64-encode/resource=config.php`는 단순 `../` path traversal과 다르다. PHP stream wrapper를 이용한 source/config disclosure 또는 LFI 계열 시도에 가깝다.

### 반영 내용

- Stage1 schema verdict enum에 `suspicious_file_disclosure`를 정식 추가
- label guidance 와 instructions 에 `php://filter`, `convert.base64-encode`, `resource=...` 는 단순 `../` traversal 과 구분하라고 명시
- `file_disclosure:php_filter_wrapper`, `file_disclosure:base64_source_intent`, `file_disclosure:resource_parameter` 힌트가 함께 있으면 `suspicious_file_disclosure`를 우선 고려하도록 보강
- LLM 이 `suspicious_path_traversal`을 반환해도 위 3종 hint 조합이 모두 있는 경우에만 `suspicious_file_disclosure`로 매우 좁게 정규화
- direct `/config.php`, `/admin/config.php` 단발 접근은 wrapper 구조가 없으면 기존처럼 candidate 과승격이나 high-confidence file disclosure로 해석하지 않음

### 해석 원칙

- `php://filter` 기반 payload는 path traversal 과 분리된 source/config disclosure 시도로 설명한다.
- Apache 로그만으로 실제 PHP source/config 파일 내용 노출 성공은 단정하지 않는다.
- `status_code=200`, `text/html`, `response_body_bytes`는 보조 근거일 뿐 file disclosure 성공의 확정 증거가 아니다.

### 검증 기준

- E세트 R2/R2B wrapper candidate가 Stage1에서 `suspicious_file_disclosure`로 분류되는지 확인
- D세트 path traversal은 여전히 `suspicious_path_traversal` 유지
- direct `/config.php` 단발 probe는 candidate로 과승격하지 않음

---

## 4. 완료 — benign normal search hint 정리

### 반영 내용

E세트 R3B에서 정상 `search=apple`은 `benign_normal_search`와 `reference_baseline`으로 잘 분리되었고, 이후 prepare 단계 보정으로 filtered out row의 `dir_probe:*` hint도 제거되었다.

### 원래 문제

`benign_normal_search`와 `dir_probe:burst`가 함께 있으면 데이터 구조상 어색하다. Stage2가 현재는 정상 baseline으로 잘 해석했지만, 후속 provider나 prompt 변경에서 불필요한 혼동을 만들 수 있다.

### 반영 방식

- `benign_normal_search`로 분류된 row 중 plain search baseline 조건을 만족하는 경우에만 `dir_probe:*` 계열 hint를 제거
- endpoint 이름 예외가 아니라 query-bearing baseline 판정 결과를 사용
- `supporting_events`의 `reference_baseline` 분류와 공격 candidate 판정은 유지

### 검증 결과

- E세트 R3B에서 정상 search는 candidate가 아님
- `filtered_out_breakdown={"benign_normal_search": 1}` 유지
- supporting event는 `reference_baseline` 유지
- SQLi/XSS candidate는 유지

---

## 5. P2 — SQLi xclose/quote termination hint 추가

### 배경

B세트 R2A/R2B와 E세트 R3/R3B에서 `x')) OR 1=1 --` 계열 payload가 사용되었다. 현재는 `sqli:or_true`, `sqli:sql_comment` 중심으로 탐지된다.

### 개선 방향

다음 hint를 추가 검토한다.

```text
sqli:xclose_pattern
sqli:quote_termination
sqli:parenthesis_termination
sqli:boolean_true_condition
```

### 주의

- 탐지 자체는 이미 성공하므로 필수 수정은 아니다.
- false positive를 늘리지 않도록 quote/parenthesis 단독이 아니라 boolean/comment/SQL keyword와 결합될 때만 사용한다.

---

## 6. P2 — Stage2 PHP wrapper 설명 보강

### 배경

E세트 R2/R2B에서 Stage2는 PHP wrapper 기반 파일 노출 시도를 대체로 잘 설명했다. 다만 `convert.base64-encode`의 의미를 보고서에서 더 안정적으로 설명할 수 있다.

### 권장 설명

```text
php://filter/convert.base64-encode/resource=... 는 PHP stream wrapper를 이용해 대상 파일을 base64 인코딩된 형태로 읽어 반환하도록 유도하는 기법으로, PHP source/config disclosure 시도에 해당한다. 다만 Apache 로그만으로 실제 반환 내용은 확인할 수 없다.
```

### 적용 위치

- `llm_stage2_reporter.py` prompt/policy
- E세트 R2/R2B 비교 문서
- 발표 자료

---

## 7. P3 — F세트 Auth/Login abuse 후보

### 목적

로그인 endpoint 반복 접근, 실패/성공 흐름, account enumeration-like pattern을 Apache 로그 표면에서 어느 정도 묶을 수 있는지 확인한다.

### 관찰 가능한 지표

- `POST /login` 또는 앱별 login endpoint 반복
- 동일 src_ip의 짧은 시간 내 반복
- status code 변화
- response_body_bytes 변화
- content_length 변화
- user_agent 반복

### 제한

- raw POST body가 없으므로 username/password 내용은 확인할 수 없다.
- password spraying 성공/실패를 단정하지 않는다.
- “brute-force-like pattern” 또는 “auth abuse suspicion” 정도로 제한한다.

---

## 8. P3 — G세트 HTTP method / protocol anomaly 후보

### 목적

특정 애플리케이션에 덜 의존하는 HTTP method anomaly를 검증한다.

후보 method:

```text
OPTIONS
TRACE
PUT
DELETE
HEAD
```

기대 해석:

- method probing 또는 reconnaissance
- misconfiguration 가능성
- 성공/침해보다는 노출된 method 확인 정도로 제한

---

## 9. 계속 유지할 제한

다음은 현재 구조에서 무리하게 확장하지 않는다.

- Time-based SQLi
  - B세트 R2A에서 실패로 기록
  - DB/앱별 payload 재설계 전까지 보류
- POST body payload 분석
  - raw POST body가 Apache 로그에 없으므로 성공/실패 판단 확장 금지
- response body 원문 기반 성공 판정
  - 현재 구조에서는 하지 않음
- 특정 실험환경 전용 규칙
  - `lab-*` UA, 특정 IP, 특정 response size hard-code 금지

---

## 10. 현재 결론

즉시 수정이 필요한 치명적 문제는 없다. 다음 개발 작업은 payload 추가보다 회귀 fixture 정리와 `suspicious_file_disclosure` verdict 정식화가 우선이다.
