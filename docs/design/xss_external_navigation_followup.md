# XSS External Navigation 탐지 후속 개선 기록

## 1. 문서 목적

Apache v2 로그의 `location` 필드가 XSS 외부 이동 패턴으로 잘못 해석되던 오탐을 수정한 뒤, 현재 수정에서 의도적으로 제외한 후속 개선 사항을 기록한다.

현재 수정은 발표 전 안정성을 우선하여 **Apache 로그 필드명 오탐 제거**에 집중했다.  
`location = ...` 형태의 bare JavaScript assignment 탐지 복구는 별도 후속 작업으로 분리한다.

---

## 2. 반영된 수정

- 커밋: `b4c1886bf1a747ebd3b38951a88938427c8ce653`
- 대상 문제: Apache v2 `raw_log`의 `location="-"` 필드가 `xss:external_navigation`으로 오탐되던 문제
- 수정 방식: external navigation 정규식을 JavaScript 문맥이 명확한 표현으로 제한
- 관련 변경:
  - `src/prepare/xss_hints.py`
  - `tests/test_prepare_xss_external_navigation.py`
  - `tests/test_viewer_payload_builder.py`

### 수정 전 문제 흐름

```text
raw_log의 location="-"
→ build_analysis_texts()가 raw_log 전체를 분석 텍스트에 포함
→ EXTERNAL_NAVIGATION_RE의 location\s*= 조건과 매칭
→ xss:external_navigation 생성
→ IP behavior의 attack_categories_attempted에 xss 포함
```

### 수정 후 확인된 결과

- Path Traversal 후보 4건 유지
- 전체 후보 5건 유지
- 후보 점수 유지: `13, 13, 13, 8, 5`
- `xss:external_navigation` 제거
- `attack_categories_attempted`에서 `xss` 제거
- 기존 Job 13 산출물은 덮어쓰지 않고 임시 디렉터리에서 재현 검증
- 관련 테스트 통과

수정 후 IP behavior에는 다음 범주만 남는다.

```text
path_traversal
dir_probe
```

`ip_behavior:multiple_attack_categories`는 위 두 범주가 정책상 남기 때문에 계속 생성될 수 있다. 이는 이번 XSS 오탐 수정과 별개의 정상 동작이다.

---

## 3. 현재 트레이드오프

정규식에서 일반적인 `location\s*=` 조건을 제거했기 때문에, 다음 bare assignment 형태는 현재 탐지되지 않는다.

```javascript
location = '/next';
location = 'https://example.test/';
```

반면 다음처럼 JavaScript 문맥이 명확한 표현은 계속 탐지된다.

```javascript
window.location = '/next';
document.location = '/next';
location.href = '/next';
location.assign('/next');
location.replace('/next');
```

현재 수정은 false positive 방지를 우선한 보수적 선택이다.

---

## 4. 후속 개선 목표

Apache 로그 메타데이터의 `location=` 필드와 실제 요청 payload의 bare JavaScript assignment를 구분한다.

목표 동작:

```text
Apache raw_log metadata:
location="-"
location="/login"
location="https://example.test/"
→ xss:external_navigation 미생성

요청 payload:
location='/next'
location='https://example.test/'
→ xss:external_navigation 생성
```

---

## 5. 권장 구현 방향

정규식만 다시 넓히지 말고 **분석 입력 출처를 분리**한다.

### 5.1 요청 payload 전용 텍스트

다음 필드를 이용해 요청 payload 분석용 텍스트를 구성한다.

```text
raw_request
raw_request_target
uri
query_string
필요한 요청 측 필드
```

이 영역에서는 bare assignment 탐지를 허용한다.

```regex
location\s*=\s*
```

단, 문자열 시작부나 값 형태 등 추가 문맥 제한을 적용해 과도한 매칭을 피한다.

### 5.2 Apache raw log 메타데이터

전체 `raw_log` key-value 문자열에서는 bare `location=` 탐지를 수행하지 않는다.

다만 아래처럼 명시적인 JavaScript 표현은 기존 엄격한 정규식으로 계속 탐지할 수 있다.

```text
window.location
document.location
location.href
location.assign(
location.replace(
```

### 5.3 권장 구조

```text
request_payload_target
→ bare location assignment 포함 XSS payload 탐지

combined_target 또는 raw_log metadata
→ 명시적 JavaScript navigation 표현만 탐지
```

Viewer 단계에서 관계를 추론하는 방식이 아니라 prepare 단계에서 분석 의미를 명확히 분리하는 것이 적절하다.

---

## 6. 완료 기준

후속 구현은 다음 조건을 모두 만족해야 한다.

### 오탐 방지

다음 문자열만 있을 때 `xss:external_navigation`이 생성되지 않아야 한다.

```text
location="-"
location="/login"
location="https://example.test/"
raw_log ... location="-" referer="-" ...
```

### 탐지 복구

다음 요청 payload에서는 `xss:external_navigation`이 생성되어야 한다.

```javascript
location='/next'
location = "https://example.test/"
location=`//example.test/path`
```

기존 명시적 표현도 계속 탐지되어야 한다.

```javascript
window.location='/next'
document.location='/next'
location.href='/next'
location.assign('/next')
location.replace('/next')
```

### 회귀 방지

- Path Traversal-only 요청에 XSS category가 추가되지 않을 것
- Path Traversal 후보 수와 점수가 불필요하게 변하지 않을 것
- Apache v2 원본 로그 보존 정책이 유지될 것
- 기존 Stage1, Stage2, Viewer 관련 테스트가 통과할 것

---

## 7. 필요한 테스트

### Prepare 회귀 테스트

- Apache `location="-"` 필드가 XSS hint를 생성하지 않는지 확인
- bare `location = ...` 요청 payload가 XSS hint를 생성하는지 확인
- 명시적 JavaScript navigation 표현 탐지가 유지되는지 확인

### IP behavior 테스트

Path Traversal-only 입력에서:

```text
attack_categories_attempted에 xss 없음
```

을 확인한다.

### Job 13 재현 테스트

`runs/jobs/13/export.json`을 임시 디렉터리에서 prepare 재실행하여 다음을 비교한다.

| 항목 | 기대값 |
|---|---:|
| Path Traversal 후보 | 4 |
| 전체 후보 | 5 |
| `xss:external_navigation` | 0 |
| attack category `xss` | 0 |
| 후보 점수 | `13,13,13,8,5` 유지 |

기존 `runs/jobs/13/` 산출물은 덮어쓰지 않는다.

---

## 8. 이번 후속 작업의 비범위

다음 항목은 별도 이슈로 유지한다.

- `low_signal_request`와 `low_signal_fuzzing` 분류 의미 분리
- Supporting event와 Finding의 명시적 관계 연결
- `raw_request` 원본/정규화 필드 명칭 정리
- 전체 `raw_log`가 다른 공격 정규식에 미치는 일반적인 오탐 가능성 조사

---

## 9. 우선순위

- 현재 발표 준비에는 커밋 `b4c1886bf1a747ebd3b38951a88938427c8ce653`의 수정으로 충분하다.
- bare `location = ...` 탐지 복구는 발표 이후 후속 개선으로 진행한다.
- 후속 구현 시에는 탐지 범위를 넓히는 과정에서 기존 Apache 로그 필드명 오탐이 재발하지 않는지를 우선 검증한다.
