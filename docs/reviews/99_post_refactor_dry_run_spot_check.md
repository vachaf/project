# 99_post_refactor_dry_run_spot_check

- 문서 상태: post-refactor dry-run spot check
- 기준 시점: 2026-05-05
- 목적: prepare module split, constants mini-move, hint pattern split 이후 대표 B/C/E/H dry-run 산출물이 Apache logs-only 해석 경계와 Stage1/Stage2 구조를 유지하는지 짧게 점검한다.

관련 문서:

- [../design/99_prepare_module_split_round1_summary.md](../design/99_prepare_module_split_round1_summary.md)
- [../design/99_prepare_module_split_round2_summary.md](../design/99_prepare_module_split_round2_summary.md)
- [../design/99_prepare_constants_mini_move_summary.md](../design/99_prepare_constants_mini_move_summary.md)
- [../design/99_prepare_hints_split_summary.md](../design/99_prepare_hints_split_summary.md)
- [../design/99_prepare_shared_attack_policy_boundary_review.md](../design/99_prepare_shared_attack_policy_boundary_review.md)
- [../planning/99_비교실험_후속개선_TODO.md](../planning/99_비교실험_후속개선_TODO.md)

## 1. 결론

대표 dry-run spot check는 통과로 본다.

점검 대상:

```text
B R2B SQLi dry-run
C XSS dry-run
E R2B PHP wrapper / file disclosure dry-run
H R4 mixed baseline scanner dry-run
```

공통 결과:

```text
- prepare 실행 성공
- stage1 dry-run 실행 성공
- stage2 dry-run 실행 성공
- stage2_report_input / stage2_report_md / stage2_report_json 생성 성공
- context-only summary 정책 유지
- Apache logs-only 위반 단정 문구는 dry-run 초안 기준 발견하지 않음
```

주의:

```text
- dry-run은 실제 LLM API 호출이 아니다.
- dry-run은 Stage1 placeholder와 Stage2 report 입력/초안 구조를 확인하는 용도다.
- 실제 LLM wording 품질은 별도 실제 LLM spot check에서 확인해야 한다.
```

## 2. 점검 기준

공통 점검 항목:

```text
- pipeline dry-run이 prepare -> stage1 -> stage2까지 완료되는지
- candidate / filtered / context-only summary counts가 생성되는지
- 주요 hint가 Stage1/Stage2 입력까지 보존되는지
- context-only summary가 incident/severity 상승 근거로 과승격되지 않는지
- status_code, response_body_bytes, content-type만으로 성공/침해/유출을 단정하지 않는지
- lab-* UA 또는 특정 IP를 공격 근거로 일반화하지 않는지
```

Apache logs-only 유지 항목:

```text
- SQLi 성공 / DB 결과 / 인증 우회 / 데이터 탈취 단정 금지
- XSS 실행 / 쿠키 탈취 / 브라우저 실행 / exfiltration 성공 단정 금지
- file disclosure 성공 / 파일 내용 노출 / source/config disclosure 성공 단정 금지
- sensitive path probe의 WordPress 존재 / admin access / .env/phpinfo/server-status/backup 노출 단정 금지
- static/crawler/mixed scanner context의 file existence / crawler authenticity / site structure / attack success 단정 금지
```

## 3. B R2B SQLi dry-run

실행 대상:

```text
lab/04-25_B세트R2A_산출물/data/raw/security_2026-04-25_17-50-00_to_2026-04-25_17-55-00_kst.json
```

산출물 prefix:

```text
openai-b_r2b_dry-run
```

결과 요약:

```text
prepare:
- total=17
- candidates_before_dedup=13
- distinct_candidates=13
- filtered=4
- noise_groups=0

stage1:
- processed_candidate_count=13
- success_count=13
- error_count=0

stage2:
- stage2_report_input 생성
- stage2_report_md 생성
- stage2_report_json 생성
```

확인한 사항:

```text
- SQLi-like reason_hints 보존
- xclose / quote termination / boolean / comment 구조 hint 보존
- benign_normal_search 4건은 filtered baseline으로 유지
- ip_behavior_aggregates는 context-only로 유지
- dry-run report에서 context-only summary 단독 severity 상승 방지 문구 유지
```

보수적 해석:

```text
- DB 결과 단정 없음
- SQL injection 성공 단정 없음
- schema exposure / row 반환 / data exfiltration 단정 없음
- decoded payload는 reconstruction/context 신호로만 다룸
```

## 4. C XSS dry-run

실행 대상:

```text
lab/04-25_C세트_산출물/data/raw/security_2026-04-25_21-30-00_to_2026-04-25_21-33-00_kst.json
```

산출물 prefix:

```text
openai-c_set_dry-run
```

결과 요약:

```text
prepare:
- total=10
- candidates_before_dedup=9
- distinct_candidates=9
- filtered=1
- noise_groups=0

stage1:
- processed_candidate_count=9
- success_count=9
- error_count=0

stage2:
- stage2_report_input 생성
- stage2_report_md 생성
- stage2_report_json 생성
```

확인한 주요 hint:

```text
- xss:script_tag
- xss:alert_call
- xss:document_cookie
- xss:browser_data_access
- xss:external_navigation
- xss:external_exfil_intent
- encoding:double_decoded_payload
- encoding:decoded_depth_2
- encoding:html_entity_decoded_xss
```

보수적 해석:

```text
- 브라우저 실행 단정 없음
- 쿠키 탈취 / 세션 탈취 / exfiltration 성공 단정 없음
- HTML entity / URL decode는 reconstruction으로만 유지
- false_positive_review_candidates 1건 보존
```

## 5. E R2B PHP wrapper / file disclosure dry-run

실행 대상:

```text
lab/04-30_E세트R2B_산출물/data/raw/security_2026-04-30_13-55-00_to_2026-04-30_13-56-00_kst.json
```

산출물 prefix:

```text
openai-e_r2b_dry-run
```

결과 요약:

```text
prepare:
- total=6
- candidates_before_dedup=4
- distinct_candidates=4
- filtered=2
- noise_groups=0

stage1:
- processed_candidate_count=4
- success_count=4
- error_count=0

stage2:
- stage2_report_input 생성
- stage2_report_md 생성
- stage2_report_json 생성
```

확인한 주요 hint/verdict:

```text
- suspicious_file_disclosure
- file_disclosure:php_filter_wrapper
- file_disclosure:base64_source_intent
- file_disclosure:resource_parameter
- file_disclosure:sensitive_resource:config_php
- file_disclosure:sensitive_resource:admin_config_php
```

확인한 context-only 구조:

```text
- probing_sequence_summaries: 1
- sensitive_path_probe_summaries: 1
- ip_behavior_aggregates: 1
```

보수적 해석:

```text
- file disclosure 성공 단정 없음
- 파일 내용 반환 단정 없음
- source/config disclosure 성공 단정 없음
- sensitive path probe는 file/app exposure inference 금지 상태 유지
- Stage2 dry-run Markdown에서 PHP wrapper 문맥을 source/config disclosure attempt로만 설명
```

## 6. H R4 mixed baseline scanner dry-run

실행 대상:

```text
lab/05-03_H세트R4_산출물/data/raw/all_2026-05-03_H_R4_kst.json
```

산출물 prefix:

```text
openai-HR4_dry-run
```

참고:

```text
실행 로그에서는 `--base-name openai-e_r2b_dry-run` 형태가 보였으나, 업로드된 산출물 파일명은 `openai-HR4_dry-run_*` 기준으로 확인했다.
```

결과 요약:

```text
prepare:
- total=45
- candidates_before_dedup=1
- distinct_candidates=1
- filtered=21
- noise_groups=3

stage1:
- processed_candidate_count=1
- success_count=1
- error_count=0

stage2:
- stage2_report_input 생성
- stage2_report_md 생성
- stage2_report_json 생성
```

확인한 context-only 구조:

```text
- probing_sequence_summaries: 1
- static_baseline_summaries: 1
- crawler_baseline_summaries: 1
- sensitive_path_probe_summaries: 1
- mixed_baseline_scanner_summaries: 1
- ip_behavior_aggregates: 1
```

상위 incident:

```text
- /server-status 403 1건
- verdict=suspicious_scan
- severity=low
- sensitive_path:no_server_status_exposure_inference 유지
```

보수적 해석:

```text
- context-only summary 단독으로 severity를 올리지 않음
- static file 존재 / robots/sitemap 내용 / JS 실행 / health 정상 여부 단정 없음
- crawler authenticity / site structure / product/category page existence 단정 없음
- WordPress 존재 / admin access / .env/phpinfo/server-status/backup 노출 단정 없음
- mixed scanner context를 attack success로 병합하지 않음
```

## 7. 종합 판단

B/C/E/H 대표 dry-run은 모두 통과로 본다.

```text
B R2B SQLi dry-run: 통과
C XSS dry-run: 통과
E R2B file disclosure dry-run: 통과
H R4 mixed baseline scanner dry-run: 통과
```

확인된 공통 안정성:

```text
- prepare/stage1/stage2 dry-run 완료
- 주요 hint 보존
- context-only summary 보존
- filtered_out_breakdown 보존
- Stage2 report input 생성 정상
- Markdown dry-run 초안 생성 정상
- Apache logs-only 해석 제한 유지
```

## 8. 남은 확인 범위

아직 확인하지 않은 것:

```text
- 실제 LLM API 호출 결과의 자연어 wording
- 실제 LLM이 SQLi 성공 / XSS 실행 / file disclosure 성공 / scanner success를 과승격하는지 여부
- 실제 LLM이 lab-* UA, 특정 IP, 특정 route를 공격 근거처럼 재해석하는지 여부
```

다음 단계 후보:

```text
1. 대표 1~2개만 실제 LLM spot check 실행
2. 실제 LLM 출력에서 반복 wording 문제가 있으면 report lint 또는 Stage2 wording 보강 검토
3. 문제가 없으면 refactor 작업을 일단 안정화 완료로 고정
```

## 9. 권장 다음 작업

추천 순서:

```text
1. B 또는 E 중 1개 실제 LLM spot check
2. C 또는 H 중 1개 실제 LLM spot check
3. 결과를 `docs/reviews/99_post_refactor_LLM_output_spot_check.md`로 기록
```

실제 LLM 호출 전에는 비용과 모델 선택을 확인한다.

## 10. 커밋 메모

문서 전용 커밋 후보:

```text
docs: add post-refactor dry-run spot check
```
