# experiments

## 목적

- `experiments/`는 A~H 실험 세트별 설계 문서와 실행 요청 문서를 둔다.
- 라운드별 세부 문서와 runner 전환 문서도 이 폴더 아래 세트별로 관리한다.
- 이 폴더의 주 역할은 실험 설계, 실행 요청, runner 사용법, historical experiment planning이다.
- 완료 평가, 샘플 결론, lab 산출물 해석은 `../reviews/`의 docs-side summary를 우선 참조한다.
- `lab/` 산출물은 현재 legacy/generated artifact 성격으로 남아 있으며, 장기 보존/이관/정리 여부는 별도 PR에서 판단한다.

## 문서 목록

- `A_set`
  - [A_set/98A_A세트_비교실험.md](./A_set/98A_A세트_비교실험.md): A세트 초기 비교 실험 문서
- `B_set`
  - [B_set/98B_B세트_비교실험.md](./B_set/98B_B세트_비교실험.md): B세트 SQLi 비교 실험 문서
  - [B_set/98B_B세트_비교실험_라운드2.md](./B_set/98B_B세트_비교실험_라운드2.md): B세트 Round 2 재설계/비교 실험 문서
  - [B_set/98B_B세트_SQLi_runner_전환.md](./B_set/98B_B세트_SQLi_runner_전환.md): B세트 SQLi runner 전환 문서
- `C_set`
  - [C_set/98B_C세트_비교실험.md](./C_set/98B_C세트_비교실험.md): C세트 XSS 비교 실험 문서
  - [C_set/98B_C세트_XSS_runner_전환.md](./C_set/98B_C세트_XSS_runner_전환.md): C세트 XSS runner 전환 문서
- `D_set`
  - [D_set/98B_D세트_비교실험.md](./D_set/98B_D세트_비교실험.md): D세트 traversal/HPP/dir probe 계열 비교 실험 문서
  - [D_set/98B_D세트_runner_전환.md](./D_set/98B_D세트_runner_전환.md): D세트 runner 전환 문서
- `E_set`
  - [E_set/98B_E세트_OpenCart_비교실험.md](./E_set/98B_E세트_OpenCart_비교실험.md): E세트 OpenCart 비교 실험 문서
  - [E_set/98B_E세트_OpenCart_R2_R2B_php_wrapper.md](./E_set/98B_E세트_OpenCart_R2_R2B_php_wrapper.md): E세트 OpenCart R2/R2B PHP wrapper 관련 문서
  - [E_set/98B_E세트_OpenCart_R3_R3B_search.md](./E_set/98B_E세트_OpenCart_R3_R3B_search.md): E세트 OpenCart R3/R3B search 관련 문서
  - [E_set/98B_E세트_OpenCart_runner_전환.md](./E_set/98B_E세트_OpenCart_runner_전환.md): E세트 OpenCart runner 전환 문서
- `F_set`
  - [F_set/98B_F세트_Auth_Login_Abuse_비교실험.md](./F_set/98B_F세트_Auth_Login_Abuse_비교실험.md): F세트 Auth/Login abuse 비교 실험 문서
  - [F_set/98B_F세트_Auth_Login_Abuse_R2.md](./F_set/98B_F세트_Auth_Login_Abuse_R2.md): F세트 Auth/Login abuse R2 문서
- `G_set`
  - [G_set/98B_G세트_HTTP_Method_Protocol_Anomaly_비교실험.md](./G_set/98B_G세트_HTTP_Method_Protocol_Anomaly_비교실험.md): G세트 HTTP method/protocol anomaly 비교 실험 문서
- `H_set`
  - [H_set/98B_H세트_Static_Crawler_Noise_비교실험.md](./H_set/98B_H세트_Static_Crawler_Noise_비교실험.md): H세트 static/crawler/scanner/mixed noise 비교 실험 문서

## 읽는 순서

1. [../standards/98_비교_실험_요청_세트_표준.md](../standards/98_비교_실험_요청_세트_표준.md)
2. 해당 세트의 기본 비교실험 문서
3. 라운드 문서나 runner 전환 문서
4. 완료 평가와 lab 산출물 결론은 [../reviews/99_lab_experiment_set_summaries.md](../reviews/99_lab_experiment_set_summaries.md)를 우선 확인
5. 대표 샘플의 LLM 판단 품질은 [../reviews/99_llm_sample_validation_review.md](../reviews/99_llm_sample_validation_review.md)와 [../reviews/99_A-F세트_대표샘플_6선.md](../reviews/99_A-F세트_대표샘플_6선.md)를 확인
6. 필요한 경우에만 legacy lab source인 `lab/*_산출물` 원본 비교/종합 문서를 대조

## 관리 원칙

- 새 실험 요청 문서와 세트별 설계 문서는 해당 세트 폴더에 둔다.
- 완료 평가와 샘플 결론은 `reviews/`의 summary 문서를 우선한다.
- 공통 절차, 작성 표준, 템플릿은 `standards/`에 둔다.
- 기존 실행 재현 예시의 `lab/a_set`~`lab/h_set` runner 경로와 `lab/*_산출물` output 경로는 legacy path로 유지한다.
- lab runner 코드 이동과 산출물 위치 개편은 후속 PR에서 검토한다.
- `lab/` 원본은 이번 단계에서 삭제, 이동, archive하지 않는다.
