# 99_비교실험_후속개선_TODO

- 작성일: 2026-04-30
- 문서 역할: A/B/C/D/E 비교실험 이후 남은 후속 개선 과제 정리
- 기준: Apache 로그 표면 기반 LLM 분석 파이프라인

---

## 1. 현재 우선순위 요약

| 우선순위 | 과제 | 이유 |
|---|---|---|
| P1 | 회귀 fixture 정리 | B/C/D/E 개선이 누적되어 다음 수정 때 기존 기능이 깨질 가능성이 커짐 |
| Done | `ip_behavior_aggregates` context-only 도입 | 동일 `src_ip`의 300초 window에서 다중 path, 높은 4xx 비율, 혼합 공격 category, 민감 경로 접근, 5xx cluster를 Stage2 문맥용으로 보존 |
| P2 | SQLi xclose/quote termination hint 추가 | B/E SQLi payload 설명력 강화 |
| Done | Stage2 PHP wrapper 설명 보강 | `php://filter/convert.base64-encode/resource=...` 를 PHP wrapper 기반 source/config disclosure attempt 로 설명하고 성공 단정 금지 반영 |
| Done | Stage2 `ip_behavior_aggregates` 설명 보강 | Stage2가 `ip_behavior_aggregates`를 context-only reconnaissance/scanning 문맥으로 읽고, candidate 승격 근거로 사용하지 않도록 반영 |
| P2 | L3 패턴 소량 확장 | Log4Shell, SSRF, SSTI, webshell 등 Apache 로그 표면에 남는 고신호 패턴만 제한적으로 추가 |
| P3 | F세트 Auth/Login abuse 설계 | 새 공격 유형 확장 후보. POST body visibility 한계 주의 필요 |
| P3 | G세트 HTTP method / protocol anomaly 설계 | 앱 의존도가 낮은 reconnaissance/anomaly 후보 |
| P3 | Threat intelligence 연동 검토 | 외부 의존성이 크므로 운영 적용 단계 후보 |
| Done | `suspicious_file_disclosure` verdict 정식화 | Stage1 enum/prompt에 verdict 추가, PHP wrapper 3종 hint 조합에서 좁은 정규화 반영 |
| Done | benign normal search hint 정리 | `benign_normal_search` baseline row의 `dir_probe:*` hint 제거 및 회귀 `MUST_NOT` 반영 완료 |

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
- `suspicious_file_disclosure` verdict 정식화

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

- `tests/fixtures/prepare_regression/` 아래 synthetic fixture 저장
- 실제 IP, 실제 UA, 실제 response size, OpenCart/Juice Shop 고유 endpoint hard-code 금지
- document IP(`198.51.100.x`, `203.0.113.x`)와 `example.test` 계열 host 사용
- `prepare_llm_input.py` 기준 smoke test부터 시작
- Stage1/Stage2 LLM 호출은 회귀 fixture 1차 범위에서 제외
- 전체 snapshot 비교가 아니라 MUST / SHOULD / MUST_NOT / WARN 조건 기반 assert 사용

---

## 3. 완료 — `ip_behavior_aggregates` context-only 도입

### 배경

현재 구조는 개별 request row 중심이다. 따라서 개별 요청 하나하나는 낮은 점수지만, 같은 IP가 짧은 시간 안에 다수의 경로를 탐색하거나 여러 공격 유형을 시도하는 경우 종합 행동을 충분히 반영하기 어렵다.

예:

```text
- 5분 동안 서로 다른 path 50개 요청
- 404 비율 70% 이상
- 같은 IP에서 traversal, XSS, SQLi, config probe가 혼합 발생
- 동일 IP가 여러 User-Agent를 바꿔가며 요청
```

이런 경우 개별 row를 candidate로 과승격하지 않더라도, Stage2에는 “IP 단위 행동 문맥”으로 전달하는 것이 적절하다.

### 반영 내용

`prepare_llm_input.py`의 top-level에 다음과 같은 context-only 구조를 반영했다.

```text
ip_behavior_aggregates
```

정책:

- 기본은 `context_only`
- 개별 요청 candidate 자동 승격 금지
- `analysis_candidates` 선정 로직과 분리
- Apache 로그 표면 지표만 사용
- 특정 IP, 실험 UA, response size hard-code 금지

### 후보 지표

| 지표 | 의미 |
|---|---|
| `request_count` | window 내 총 요청 수 |
| `distinct_paths` | 서로 다른 path 수 |
| `distinct_methods` | method 다양성 |
| `status_4xx_ratio` | 4xx 비율. fuzzing/probing 정황 |
| `status_5xx_count` | 서버 오류 유발 정황 |
| `distinct_user_agents` | UA 변경/자동화 정황. 단독 판단 금지 |
| `attack_categories_attempted` | SQLi/XSS/traversal/file probe/HPP 등 혼합 시도 |
| `sensitive_path_hits` | config/admin/backup/.git/.env 등 민감 경로 접근 수 |
| `burst_window_sec` | 집계 window 크기 |

### 반영 조건

다음 중 하나 이상을 만족할 때만 aggregate 를 생성한다.

- `request_count >= 5 and distinct_paths >= 4`
- `status_4xx_ratio >= 0.5 and request_count >= 4`
- `attack_categories_attempted` 개수 `>= 2`
- `sensitive_path_hits` 개수 `>= 2`
- `status_5xx_count >= 2`

### 반영 hint

```text
ip_behavior:high_4xx_ratio
ip_behavior:multi_path_burst
ip_behavior:multiple_attack_categories
ip_behavior:sensitive_path_focus
ip_behavior:server_error_cluster
```

### 출력 예시

```json
{
  "context_role": "ip_behavior_context",
  "aggregate_scope": "same_src_ip_time_window",
  "should_promote_to_candidate": false,
  "src_ip": "198.51.100.10",
  "window_start": "2026-04-30T10:20:05.000+09:00",
  "window_end": "2026-04-30T10:21:29.000+09:00",
  "burst_window_sec": 300,
  "request_count": 5,
  "distinct_paths": 4,
  "distinct_methods": 1,
  "status_4xx_count": 3,
  "status_4xx_ratio": 0.6,
  "status_5xx_count": 0,
  "distinct_user_agents": 1,
  "attack_categories_attempted": ["dir_probe", "sqli", "xss"],
  "sensitive_path_hits": ["/admin/", "/backup/", "/config.php"],
  "sample_request_ids": ["ip-behavior-admin-1", "ip-behavior-backup-1"],
  "reason_hints": [
    "ip_behavior:multi_path_burst",
    "ip_behavior:high_4xx_ratio",
    "ip_behavior:multiple_attack_categories",
    "ip_behavior:sensitive_path_focus"
  ],
  "interpretation_limit": "context_only_no_success_inference"
}
```

### 해석 원칙

- “IP 단위 scanning/reconnaissance 정황”으로만 설명
- 개별 요청 성공이나 침해를 단정하지 않음
- request count, 4xx ratio, distinct path 수는 우선순위 조정 보조 지표
- known asset이면 내부 점검/스캐너 가능성 병기

### 회귀 검증

- synthetic fixture `ip_behavior_multi_signal_context` 추가
- `scripts/check_prepare_regression.py`가 `ip_behavior_aggregates` collection 검증 지원
- low-signal `/admin/`, `/backup/`, `/config.php`는 개별 candidate 로 승격되지 않음
- 같은 fixture 안의 SQLi/XSS payload 는 기존 규칙대로 candidate 유지

### 후속 TODO

1. known asset IP 와 결합된 IP aggregate 해석 문구 보강
2. 실데이터 D/E 세트 raw에서 aggregate 과다 생성 여부 점검
3. 필요 시 report_input 기반 Stage2 smoke fixture 추가 검토

### Stage2 반영 상태

- `llm_stage2_reporter.py`가 `llm_input.json` top-level의 `ip_behavior_aggregates`를 읽어 `stage2_report_input.json`에 포함한다.
- Stage2 prompt/system/user guidance 에 `ip_behavior_aggregates` 해석 원칙을 추가했다.
- `ip_behavior_aggregates`는 context-only 이며 `analysis_candidates`와 섞지 않는다.
- `should_promote_to_candidate=false` 인 aggregate 는 어떤 개별 row도 candidate 로 승격시키는 근거로 사용하지 않는다.
- `attack_categories_attempted`는 attempted category 요약일 뿐 성공한 공격 목록이 아니다.
- `sensitive_path_hits`는 민감 경로 접근 시도 문맥일 뿐 실제 노출 또는 침해 성공 근거가 아니다.

---

## 4. 완료 — `suspicious_file_disclosure` verdict 정식화

### 배경

E세트 R2/R2B에서 `php://filter`, `resource=config.php`, `convert.base64-encode` 계열 payload는 prepare 단계에서 `suspicious_file_disclosure` hint로 잘 보존된다. 그러나 Stage1 최종 verdict는 기존에 `suspicious_path_traversal`로 수렴하는 경향이 있었다.

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

---

## 5. 완료 — benign normal search hint 정리

### 반영 내용

E세트 R3B에서 정상 `search=apple`은 `benign_normal_search`와 `reference_baseline`으로 잘 분리되었고, 이후 prepare 단계 보정으로 filtered out row의 `dir_probe:*` hint도 제거되었다.

### 반영 방식

- `benign_normal_search`로 분류된 row 중 plain search baseline 조건을 만족하는 경우에만 `dir_probe:*` 계열 hint를 제거
- endpoint 이름 예외가 아니라 query-bearing baseline 판정 결과를 사용
- `supporting_events`의 `reference_baseline` 분류와 공격 candidate 판정은 유지

---

## 6. P2 — SQLi xclose/quote termination hint 추가

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

## 7. 완료 — Stage2 PHP wrapper 설명 보강

### 반영 설명

```text
php://filter/convert.base64-encode/resource=... 는 PHP stream wrapper를 이용해 대상 파일을 base64 인코딩된 형태로 읽어 반환하도록 유도하는 기법으로, PHP source/config disclosure 시도에 해당한다. 다만 Apache 로그만으로 실제 반환 내용은 확인할 수 없다.
```

### 반영 원칙

- Stage2 prompt/system/user guidance 에 위 설명을 반영했다.
- `suspicious_file_disclosure` verdict 또는 `file_disclosure:*` hint 는 의도/시도 근거이지 성공/유출 근거가 아님을 명시했다.
- `status_code=200`, `text/html`, `response_body_bytes`만으로 성공 단정 금지 문구를 강화했다.
- direct `/config.php`, `/admin/config.php` 단발 접근은 wrapper payload 와 동일한 강한 file disclosure 시도로 과장하지 않도록 분리했다.

---

## 8. P2 — L3 패턴 소량 확장 후보

### 배경

추가 공격 패턴 확장은 커버리지를 늘릴 수 있지만, 정규식만 대량 추가하면 false positive가 늘 수 있다. 따라서 회귀 fixture와 IP 행동 집계 이후 소량으로 시작한다.

### 1차 후보

| 유형 | 예시 패턴 | 해석 제한 |
|---|---|---|
| Log4Shell/JNDI | `${jndi:ldap://`, `${jndi:rmi://`, `${jndi:dns://` | exploit 성공 단정 금지 |
| SSRF | `127.0.0.1`, `localhost`, `169.254.169.254`, `file://`, `gopher://` | 내부 접근 성공 단정 금지 |
| SSTI | `{{7*7}}`, `${7*7}`, `<%=`, `#{}` | template 실행 성공 단정 금지 |
| Webshell upload/probe | `.php`, `.jsp`, `.aspx` + upload/probe 흐름 | 업로드 성공 단정 금지 |

### 원칙

- 초기에는 candidate 자동 승격보다 hint/context 우선
- Stage2 정책에 “성공 단정 금지” 문구를 함께 추가
- fixture 추가 후 반영

---

## 9. P3 — F세트 Auth/Login abuse 후보

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

## 10. P3 — G세트 HTTP method / protocol anomaly 후보

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

## 11. P3 — Threat intelligence 연동 검토

### 후보

- AbuseIPDB
- Tor exit node list
- Spamhaus DROP/EDROP
- GreyNoise Community

### 현재 판단

실전성은 있지만 지금은 후순위다.

이유:

- 외부 의존성 증가
- API key/쿼터/네트워크 실패 처리 필요
- 결과 재현성 저하
- 연구 실험 결과가 외부 DB 상태에 좌우됨

운영 적용 확장 단계에서 검토한다.

---

## 12. 계속 유지할 제한

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
- 공격 패턴 대량 확장
  - 회귀 fixture 없이 한 번에 많이 추가하지 않음

---

## 13. 현재 결론

즉시 수정이 필요한 치명적 문제는 없다. 다음 개발 작업은 payload 추가보다 **회귀 fixture 유지**와 **Stage2 smoke 검증 정리**가 우선이다.
