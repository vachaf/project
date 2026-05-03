# sensitive_path_probe_context category 도입 검토

- 작성 기준일: 2026-05-03
- 문서 역할: H세트 R3 이후 `sensitive_path_probe_context` noise/category 도입 여부 검토
- 관련 세트: H세트 R3 scanner-like low-signal path
- 관련 구조: `sensitive_path_probe_summaries`, `supporting_events`, `probing_sequence_summaries`, `filtered_out`

---

## 1. 배경

H세트 R3에서 다음 scanner-like / sensitive-looking path를 검증했다.

```text
/wp-login.php
/wp-admin/
/.env
/phpinfo.php
/server-status
/backup.zip
```

초기 결과에서는 `/server-status` 403 두 건이 개별 candidate로 남고, 나머지 path는 `dir_probe:*` 또는 `low_signal_dir_probe` 중심으로 정리되었다.

이후 개선으로 `sensitive_path_probe_summaries`를 추가했고, 결과는 다음처럼 안정화되었다.

```text
candidate_rows=1
supporting_events=1
filtered_out_rows=7
probing_sequence_summaries=1
ip_behavior_aggregates=1
sensitive_path_probe_summaries=1
```

`/server-status` 대표 1건은 `suspicious_scan / low` candidate로 유지하고, 나머지 `/server-status` 1건은 `sensitive_path_probe_support`로 내렸다. 나머지 scanner-like path는 `sensitive_path:*` 힌트와 함께 filtered/context로 보존했다.

---

## 2. 현재 남은 문제

현재 구조상 `filtered_out`의 category는 여전히 아래처럼 남는다.

```text
low_signal_dir_probe
low_signal_fuzzing
```

하지만 H R3의 의미상 일부 row는 더 구체적으로는 다음에 가깝다.

```text
sensitive_path_probe_context
```

예:

```text
/.env
/phpinfo.php
/server-status
/backup.zip
/wp-login.php
/wp-admin/
```

현재는 `reason_hints`와 `sensitive_path_probe_summaries`가 이 의미를 보완하고 있으므로 기능적으로 큰 문제는 없다. 다만 사람이 filtered_out summary만 볼 경우 `low_signal_dir_probe`보다 `sensitive_path_probe_context`가 더 직관적일 수 있다.

---

## 3. 도입 후보

### 3.1 새 noise_category 후보

```text
sensitive_path_probe_context
```

또는 더 세분화하면:

```text
sensitive_config_path_context
sensitive_admin_path_context
sensitive_diagnostic_path_context
sensitive_backup_path_context
```

하지만 초기에는 세분화하지 않는 편이 낫다.

권장 후보는 하나다.

```text
sensitive_path_probe_context
```

---

## 4. 도입 시 기대 효과

도입하면 다음 장점이 있다.

```text
- H R3 filtered_out 요약이 더 직관적이 됨
- low_signal_dir_probe와 sensitive path probing을 구분 가능
- Stage2의 후보 밖 문맥 요청 설명이 더 명확해짐
- summarize_prepare_output.py에서 H R3 결과를 더 쉽게 읽을 수 있음
```

예상 전후:

```text
현재:
filtered_out_breakdown:
- low_signal_dir_probe=6
- low_signal_fuzzing=1

도입 후 가능 형태:
filtered_out_breakdown:
- sensitive_path_probe_context=6
- low_signal_fuzzing=1
```

또는 일부는 다음처럼 남길 수 있다.

```text
- sensitive_path_probe_context=7
```

---

## 5. 도입 시 위험

반대로 위험도 있다.

```text
- 기존 D세트 directory probing fixture와 의미가 겹칠 수 있음
- E세트 direct config path expected와 충돌 가능
- PHP wrapper file_disclosure와 direct sensitive path context가 혼동될 수 있음
- Stage2가 새 category를 보고 더 강한 incident로 오해할 수 있음
- regression expected 수정 범위가 커질 수 있음
```

특히 아래 구분은 유지해야 한다.

```text
php://filter + convert.base64-encode + resource=...
→ file_disclosure / suspicious_file_disclosure 계열

/config.php, /admin/config.php, /.env, /backup.zip 단순 path 접근
→ sensitive_path_probe_context 또는 low-signal probing context
```

즉, `sensitive_path_probe_context`는 파일 노출 성공이나 file disclosure 성공을 뜻하면 안 된다.

---

## 6. 현재 구조로 충분한가?

현재는 다음 구조가 이미 존재한다.

```text
sensitive_path_probe_summaries
supporting_events.sensitive_path_probe_support
probing_sequence_summaries
ip_behavior_aggregates
filtered_out reason_hints = sensitive_path:*
```

그리고 H R3 결과에서는 다음이 충족됐다.

```text
- /server-status candidate는 대표 1건만 유지
- supporting_events는 row-specific hint로 정리됨
- sensitive_path_probe_summaries가 전체 문맥을 보존
- Stage2가 성공/노출/침해를 단정하지 않음
- regression 통과
```

따라서 현재 기능 요구에는 이미 충분하다.

---

## 7. 권장 판단

현재 시점에서는 **즉시 도입하지 않고 보류**하는 것이 적절하다.

이유:

```text
1. 기능적으로 이미 sensitive_path_probe_summaries가 문맥을 제공한다.
2. category 변경은 regression expected 수정 범위가 커질 수 있다.
3. D/E세트의 directory probing / direct config path와 의미 충돌 가능성이 있다.
4. 지금은 H세트 R4 또는 실제 LLM 샘플 검증 쪽 우선순위가 더 높다.
```

권장 결론:

```text
sensitive_path_probe_context category는 도입 후보로 남긴다.
단, 현재는 구현하지 않는다.
```

---

## 8. 도입 조건

다음 조건 중 하나 이상이 생기면 다시 검토한다.

```text
- H세트 R4 mixed benign + scanner-like 실험에서 filtered_out category가 너무 모호해지는 경우
- 실제 운영 로그에서 low_signal_dir_probe가 너무 넓어져 analyst가 구분하기 어려운 경우
- Stage2가 low_signal_dir_probe를 과도하게 directory probing으로만 설명하는 경우
- sensitive path 관련 false positive/false negative review가 반복되는 경우
- prepare summary helper에서 H세트 결과 가독성이 크게 떨어지는 경우
```

---

## 9. 도입 시 구현 원칙

나중에 구현한다면 원칙은 다음이다.

```text
- candidate 승격 기준은 변경하지 않는다.
- sensitive_path_probe_summaries는 유지한다.
- filtered_out noise_category만 제한적으로 세분화한다.
- file_disclosure:* 또는 suspicious_file_disclosure와 혼동하지 않는다.
- PHP wrapper 계열은 계속 file_disclosure로 둔다.
- direct sensitive path 접근은 context-only로 둔다.
- status_code=200/403/404만으로 노출/차단/성공 단정 금지.
```

예상 변경 범위:

```text
src/prepare_llm_input.py
scripts/check_prepare_regression.py
scripts/summarize_prepare_output.py
tests/expected/prepare_regression/h_r3_sensitive_path_probe_context.expected.json
필요 시 E/D세트 expected 일부
```

---

## 10. 최종 결론

```text
현재는 도입하지 않는다.
후속 H R4 또는 운영형 로그 검토에서 필요성이 커지면 다시 검토한다.
```

현재 우선순위는 다음이다.

```text
1. H R4 mixed benign + scanner-like 실험 여부 검토
2. 실제 LLM 샘플 검증 체계 검토
3. 발표/보고용 요약 정리
4. 필요 시 sensitive_path_probe_context category 재검토
```
