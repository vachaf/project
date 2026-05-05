# 99_post_refactor_LLM_output_spot_check

- 문서 상태: post-refactor 실제 LLM output spot check
- 기준 시점: 2026-05-05
- 목적: prepare module split, constants mini-move, hint split 이후 실제 LLM 출력이 Apache logs-only 해석 경계를 유지하는지 대표 샘플로 확인한다.

관련 문서:

- [99_post_refactor_dry_run_spot_check.md](./99_post_refactor_dry_run_spot_check.md)
- [../design/99_prepare_module_split_round1_summary.md](../design/99_prepare_module_split_round1_summary.md)
- [../design/99_prepare_module_split_round2_summary.md](../design/99_prepare_module_split_round2_summary.md)
- [../design/99_prepare_constants_mini_move_summary.md](../design/99_prepare_constants_mini_move_summary.md)
- [../design/99_prepare_hints_split_summary.md](../design/99_prepare_hints_split_summary.md)
- [../design/99_prepare_shared_attack_policy_boundary_review.md](../design/99_prepare_shared_attack_policy_boundary_review.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

실제 LLM spot check 2건은 통과로 본다.

점검 대상:

```text
H R4 mixed baseline scanner actual LLM
E R2B PHP wrapper / file disclosure actual LLM
```

공통 결론:

```text
- prepare -> stage1 -> stage2 실제 LLM 실행 완료
- Stage2 JSON direct parse 성공
- Apache logs-only 위반 단정은 주요 보고서 문맥에서 발견하지 않음
- context-only summary를 단독으로 성공/침해/유출 근거로 과승격하지 않음
- known asset IP는 내부 테스트/자체 호출/운영 점검 가능성을 병기함
```

주의:

```text
- spot check 대상은 2개뿐이다.
- 전체 실제 LLM 품질을 보증하는 회귀 테스트는 아니다.
- 반복 wording 문제는 향후 실제 LLM 출력 관찰에서 계속 확인한다.
```

## 2. 공통 점검 기준

점검 항목:

```text
- 실제 LLM 호출이 stage1/stage2까지 완료되는지
- Stage2 report JSON parse가 성공하는지
- SQLi/XSS/file disclosure/context-only 경계가 과승격되지 않는지
- status_code, response_body_bytes, content-type만으로 성공/침해/유출을 단정하지 않는지
- lab-* UA 또는 특정 IP를 공격 근거로 일반화하지 않는지
- known asset IP 해석이 보수적으로 유지되는지
```

Apache logs-only 유지 항목:

```text
- response body 원문 없음
- DB 결과 없음
- 브라우저 실행 검증 없음
- 파일 내용 노출 확인 없음
- static file 존재 확인 없음
- crawler identity 확인 없음
- site structure 확인 없음
- WordPress/admin access/server-status exposure 확인 없음
```

## 3. H R4 mixed baseline scanner 실제 LLM spot check

실행 대상:

```text
lab/05-03_H세트R4_산출물/data/raw/all_2026-05-03_H_R4_kst.json
```

산출물 prefix:

```text
openai-h_r4-check
```

실행 결과 요약:

```text
prepare:
- total=45
- candidates_before_dedup=1
- distinct_candidates=1
- filtered=21
- noise_groups=3

stage1:
- request_id=afcqk19TYrFq3zXDH9-VqQAAAM4
- verdict=suspicious_scan
- severity=low
- confidence=high

stage2:
- 실제 OpenAI 응답 수신
- JSON direct parse 성공
- stage2_report_input 생성
- stage2_report_json 생성
- stage2_report_md 생성
```

Stage2 주요 판단:

```text
- 전체 평가는 내부 자산 IP의 경량 정찰 및 민감 경로 탐색 정황으로 정리됨
- 침해 성공이나 민감 정보 유출을 단정할 수 없다고 명시
- known asset IP에서 발생했으므로 내부 테스트/운영 점검 가능성을 함께 열어둠
- /server-status 403은 저위험 정찰성 incident로 유지됨
- 같은 IP의 민감 경로 탐색은 시도 수준으로 해석됨
- 정상 baseline 요청과 scanner-like 요청을 단일 공격 체인으로 병합하지 않음
```

확인한 context-only 구조:

```text
- probing_sequence_summary_count = 1
- static_baseline_summary_count = 1
- crawler_baseline_summary_count = 1
- sensitive_path_probe_summary_count = 1
- mixed_baseline_scanner_summary_count = 1
- ip_behavior_aggregate_count = 1
```

보수적 해석 유지:

```text
- server-status 노출 성공 단정 없음
- .env / backup.zip / wp-login.php 노출 또는 앱 존재 단정 없음
- static file 존재, JS 실행, robots/sitemap 내용 단정 없음
- 실제 crawler identity, site structure, product/category page existence 단정 없음
- mixed baseline/scanner context를 attack success로 병합하지 않음
```

약한 wording 후보:

```text
- 보고서에 “외부에서 접근을 시도한 정황”이라는 표현이 있음
- 같은 보고서에서 known asset IP와 내부 테스트/운영 점검 가능성을 명확히 병기하므로 수정 필요 수준은 아님
- 더 엄격히 하려면 “외부에서” 대신 “출발지 IP에서” 또는 “클라이언트가”로 바꾸는 Stage2 wording 후보로 둘 수 있음
```

판정:

```text
H R4 actual LLM spot check: 통과
```

## 4. E R2B PHP wrapper / file disclosure 실제 LLM spot check

실행 대상:

```text
lab/04-30_E세트R2B_산출물/data/raw/security_2026-04-30_13-55-00_to_2026-04-30_13-56-00_kst.json
```

산출물 prefix:

```text
openai-e_r2b-check
```

실행 결과 요약:

```text
prepare:
- total=6
- candidates_before_dedup=4
- distinct_candidates=4
- filtered=2
- noise_groups=0

stage1:
- 4개 후보 모두 suspicious_file_disclosure
- severity=medium
- confidence=high

stage2:
- 실제 OpenAI 응답 수신
- JSON direct parse 성공
- stage2_report_input 생성
- stage2_report_json 생성
- stage2_report_md 생성
```

확인한 주요 hints:

```text
- file_disclosure:php_filter_wrapper
- file_disclosure:base64_source_intent
- file_disclosure:resource_parameter
- file_disclosure:sensitive_resource:config_php
- file_disclosure:sensitive_resource:admin_config_php
```

Stage2 주요 판단:

```text
- PHP wrapper 기반 source/config disclosure 시도로 정리됨
- 실제 파일 내용 노출이나 침해 성공은 확인되지 않았다고 명시
- 200 또는 404 응답만으로 유출 성공을 단정할 수 없다고 명시
- response body 원문이 없으므로 실제 노출 성공을 단정하지 않음
- known asset IP이므로 내부 테스트/자체 호출/운영 점검 가능성을 병기함
```

Stage1 주요 판단:

```text
- suspicious_file_disclosure로 분류됨
- severity=medium / confidence=high
- reasoning은 파일/소스 공개 시도 수준으로 제한됨
- 실제 파일 내용 노출 성공은 확인되지 않는다고 설명함
```

보수적 해석 유지:

```text
- file disclosure 성공 단정 없음
- source/config disclosure 성공 단정 없음
- PHP source code 노출 단정 없음
- .env/phpinfo/server-status/backup 노출 단정 없음
- status_code=200 또는 text/html/response_body_bytes만으로 유출 성공 단정 없음
```

약한 wording 후보:

```text
- “파일/소스 공개 시도” 표현은 대체로 허용 가능
- 더 엄격히 하려면 “파일/소스 공개를 노린 것으로 보이는 요청 패턴”으로 완화 가능
- 현재 보고서는 대부분 “시도”, “성공 확인 안 됨”, “단정할 수 없음”을 함께 사용하므로 수정 필요 수준은 아님
```

판정:

```text
E R2B actual LLM spot check: 통과
```

## 5. 종합 판단

실제 LLM spot check 결과:

```text
H R4 mixed baseline scanner: 통과
E R2B file disclosure: 통과
```

공통 안정성:

```text
- 실제 LLM 응답 수신 성공
- Stage2 JSON direct parse 성공
- conservative wording 유지
- known asset IP caution 유지
- context-only summary 과승격 없음
- file disclosure / sensitive path / crawler / mixed scanner 성공 단정 없음
```

## 6. 남은 확인 범위

아직 실제 LLM으로 직접 확인하지 않은 대표 영역:

```text
B R2B SQLi
C HTML entity XSS
```

다만 dry-run spot check에서 B/C는 구조와 hint 보존이 확인되었고, 실제 LLM spot check에서 H/E의 context-only 및 file disclosure wording이 안정적으로 나왔으므로, 현재 시점에서 추가 실제 LLM 호출은 필수는 아니다.

추가 확인이 필요해지는 조건:

```text
- SQLi 성공 / DB 결과 / 인증 우회 단정이 실제 LLM에서 다시 보이는 경우
- XSS 실행 / 쿠키 탈취 / 브라우저 실행 단정이 실제 LLM에서 다시 보이는 경우
- file disclosure 성공 / 파일 내용 노출 단정이 재발하는 경우
- context-only summary가 severity를 올리는 근거처럼 반복 표현되는 경우
- lab-* UA 또는 특정 IP를 공격 근거로 일반화하는 경우
```

## 7. 권장 다음 작업

현재는 추가 코드 분리를 멈추고 안정화 상태로 두는 것이 적절하다.

권장:

```text
1. docs/planning/99_비교실험_후속개선_TODO.md에 실제 LLM spot check 완료 반영
2. 필요 시 docs/진행상황.md에 H/E actual spot check 통과 요약 반영
3. 실제 운영/보고 단계에서 반복 wording 문제가 확인될 때만 report lint 또는 Stage2 wording 보강 검토
```

보류 유지:

```text
- AUTOMATION_UA_PATTERNS 이동
- detect_decoded_attack_hints 이동
- shared attack/search policy constants 이동
- scoring/filtering 이동
- supporting_events 생성/연결 로직 이동
- Stage2 reporter 변경
```

## 8. 커밋 메모

문서 전용 커밋 후보:

```text
docs: add post-refactor LLM output spot check
```
