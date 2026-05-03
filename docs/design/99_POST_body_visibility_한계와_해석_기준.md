# 99_POST_body_visibility_한계와_해석_기준

- 문서 상태: 보류 결정 메모
- 버전: v1.0
- 작성일: 2026-04-25

## 1. 결론

POST body 내부에만 공격 신호가 있는 요청은 현재 baseline 평가의 직접 입력이 아니다. 이 경우의 누락 가능성은 현재 파이프라인의 blind spot으로 기록하는 것이 맞다.

## 2. 현재 운영 기준

현재 시스템의 본래 목적은 Apache 공통/security 로그를 기반으로 LLM이 어디까지 공격 분류·요약을 할 수 있는지 평가하는 것이다.

따라서 baseline에서는 아래 원칙을 유지한다.

- Apache 공통/security 로그 표면에 직접 남는 신호를 우선 사용한다.
- query string, raw request target, status code, response body size, response content type, 500 오류처럼 로그 표면에서 확인 가능한 근거를 중심으로 해석한다.
- `POST` body 원문을 새로 저장하거나, 상류에서 body-derived signal을 추가해 baseline 입력을 확장하지 않는다.

## 3. 왜 raw POST body를 바로 로그에 저장하지 않는가

현재 baseline 평가 질문은 Apache 공통/security 로그만으로 어디까지 가능한지를 보는 것이다. 이 단계에서 raw POST body를 직접 저장하거나 상류에서 payload 의미를 추출해 넣으면, 더 이상 같은 질문을 평가하는 것이 아니다.

또한 POST body에는 계정 정보, 개인정보, 토큰, 민감 입력이 포함될 수 있으므로 원문 저장은 별도 보안·보관 기준이 필요하다. 따라서 현재 문서 기준에서는 raw body 저장을 baseline 운영 기준으로 채택하지 않는다.

## 4. 왜 blind spot을 결과로 인정하는가

auth bypass 성공형 요청이라도 공격 신호가 POST JSON body 내부에만 있고, Apache 공통/security 로그 표면에는 `POST /rest/user/login`, `200`, `application/json`, 일반적인 응답 크기 정도만 남는 경우가 있다. 이 경우 prepare 단계는 로그 표면 신호만으로 후보화를 수행하므로 해당 요청이 candidate 구성 단계에서 누락될 수 있다.

이 현상은 모델 성능 부족으로만 설명하기 어렵다. 더 직접적으로는 LLM에 전달되기 전에 확보 가능한 데이터 가시성 범위가 제한되어 있기 때문이다. 따라서 현재 baseline에서는 이러한 누락 가능성을 숨기지 않고 결과로 기록하는 것이 타당하다.

## 5. 현재 보류 항목

아래 보강은 production-hardening 또는 visibility 개선 관점에서는 검토 가치가 있지만, 현재 baseline 평가 범위에는 넣지 않는다.

- sanitized signal 형태의 상류 보강
- body-derived security hint 추가
- baseline과 다른 별도 보강 모드 도입

## 6. 향후 검토 기준

향후에는 baseline mode와 augmented mode를 분리해 비교하는 방식은 검토할 수 있다. 다만 그 경우 augmented mode는 "Apache 공통/security 로그만으로 가능한 범위"를 평가하는 실험이 아니라, 상류 가공 신호까지 포함한 별도 실험으로 문서와 결과를 분리해야 한다.

즉 현재는 blind spot을 결과로 인정하고 baseline 평가의 순도를 유지한다. visibility 보강은 별도 개선안으로만 짧게 관리한다.
