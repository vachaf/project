# standards

## 목적

- `standards/`는 실험 문서 작성 표준과 공통 템플릿을 둔다.
- 세트별 문서에 공통으로 적용되는 절차, 명명 규칙, 기록 형식을 먼저 안내한다.
- 분석 결과와 보고서 품질을 평가하기 위한 공통 기준도 함께 관리한다.

## 문서 목록

- [98_비교_실험_요청_세트_표준.md](./98_비교_실험_요청_세트_표준.md): 비교 실험 절차, 시간 구간, provider 비교, 산출물 보관 기준
- [99_비교_실험_결과_기록_템플릿.md](./99_비교_실험_결과_기록_템플릿.md): 실험 후 결과 기록 양식
- [99_analysis_quality_criteria.md](./99_analysis_quality_criteria.md): Apache logs-only 분석 신뢰성 평가 기준과 좋은 분석의 정의
- [99_LLM분석_품질평가_체크리스트.md](./99_LLM분석_품질평가_체크리스트.md): LLM 분석 결과 수동 평가용 10점 체크리스트

## 읽는 순서

1. [98_비교_실험_요청_세트_표준.md](./98_비교_실험_요청_세트_표준.md)
2. [99_비교_실험_결과_기록_템플릿.md](./99_비교_실험_결과_기록_템플릿.md)
3. [99_analysis_quality_criteria.md](./99_analysis_quality_criteria.md)
4. [99_LLM분석_품질평가_체크리스트.md](./99_LLM분석_품질평가_체크리스트.md)
5. [../experiments/README.md](../experiments/README.md)와 세트별 문서

## 관리 원칙

- 공통 표준과 템플릿만 `standards/`에 둔다.
- 세트별 실험 설계와 실행 문서는 `experiments/`에 둔다.
- 완료 평가나 리뷰 문서는 `reviews/`에 둔다.
- 설계 판단, 구현 보류 결정, taxonomy 검토는 `design/`에 둔다.
