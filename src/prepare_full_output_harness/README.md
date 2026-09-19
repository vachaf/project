# Prepare Full-output Harness

## 1. 역할

`src/prepare_full_output_harness/`는 Prepare 변경 전후의 **전체 반환값 compatibility**를 비교하기 위한 offline verification package다.

이 harness는 production runtime이 아니다.

~~~text
Prepare full-output harness
  = compatibility / regression verification

!= Analysis Job runtime
!= Stage1 / Stage2 runtime
!= Live Monitoring runtime
~~~

주요 비교 대상은 `prepare_llm_input.build_outputs()`의 전체 반환값이다.

~~~text
1. llm_input
2. candidate payload
3. noise payload
4. filtered_reasons payload
5. filtered_out payload
~~~

## 2. 검증 계열

검증 의미는 서로 분리한다.

~~~text
compatibility
  -> 같은 승인 입력/parameter에서 기존 의미와 차이가 없는지

corrected
  -> 별도로 승인된 의미 변경만 발생했는지

live_adoption
  -> Live가 승인된 shared-signal observation 계약만 채택하는지
~~~

한 계열의 PASS는 다른 계열의 PASS를 의미하지 않는다.

## 3. Typed capture

`capture.py`는 Prepare 반환값을 lossless typed representation으로 기록한다.

구분하는 대표 타입:

- null
- bool
- int
- float
- str
- list
- tuple
- dict

~~~text
True != 1
1 != 1.0
list != tuple
missing != null
null != empty string
~~~

지원하지 않는 객체나 non-finite float는 임의 문자열로 변환하지 않고 capture error로 처리한다.

dict는 key/value를 typed entry로 저장해 key type과 insertion order 차이를 관찰할 수 있게 한다.

## 4. Strict comparison

`compare.py`는 capture를 정렬·set 변환·whitespace normalization 등으로 숨기지 않고 재귀 비교한다.

대표 차이:

- type changed
- value changed
- missing / added
- length changed
- sequence changed
- dict order changed
- input mutation
- exception changed

dict insertion-order 차이는 별도 차이로 기록하며, 값/타입 compatibility와 구분한다.

## 5. Input mutation

각 Prepare 호출에는 fresh deep copy를 사용한다.

~~~text
input before call
  -> typed capture

Prepare call

input after call
  -> typed capture
  -> mutation comparison
~~~

Prepare가 입력 객체를 변경한 경우 output equality와 별개로 `input_mutation` 차이로 기록한다.

## 6. Exception comparison

명시적 error case는 exception의 존재 여부뿐 아니라 다음을 비교한다.

- qualified exception type
- exact message

~~~text
same failure presence
!= same exception contract
~~~

예상하지 않은 일반 case의 exception은 compatibility 성공으로 간주하지 않는다.

## 7. Source / input identity

`identity.py`는 경로 이름만으로 비교 대상을 동일하다고 보지 않는다.

Source identity는 source/harness/adapter의 content-backed identity를 사용하고, input identity는 corpus/case/source/projection/parameter provenance를 유지한다.

같은 bytes라도 source identity가 다르면 자동으로 하나의 case로 합치지 않는다.

before/after identity가 일치하지 않으면 unrelated capture를 비교하지 않고 중단한다.

## 8. Determinism과 isolation

Harness execution은 production DB/LLM/Worker 실행과 분리한다.

검증 시 확인할 대표 경계:

- fixed/controlled clock이 필요한 값
- 독립 process/source root
- 실제 import origin
- source checksum
- network / DB / LLM 호출 금지
- source tree 변경 금지
- 기존 baseline 덮어쓰기 금지

같은 before source를 반복 실행했을 때 전체 capture가 동일한지도 compatibility의 전제다.

## 9. Artifact integrity

Harness artifact는 source/input identity와 capture/comparison 결과를 함께 보존한다.

완료된 baseline 또는 comparison을 사용할 때는 manifest/checksum/completion 상태를 확인해야 한다.

불완전 run이나 identity가 맞지 않는 artifact를 current baseline으로 승격하지 않는다.

## 10. Shared Signal 변경과의 관계

Shared Security Signal Extractor를 Prepare에 공용화하거나 rule/profile을 수정할 때 harness는 **Prepare의 전체 output contract가 의도치 않게 바뀌지 않았는지** 확인하는 보조 수단이다.

Shared extractor 자체의 관찰 사실과 Prepare policy ownership은 분리한다.

~~~text
Extractor
  -> observation/provenance

Prepare
  -> score / reason / candidate / filtering / aggregation
~~~

따라서 extractor test가 PASS했다고 해서 Prepare full-output compatibility까지 자동 PASS가 되는 것은 아니다.

## 11. 주요 모듈

| 파일 | 책임 |
| --- | --- |
| `capture.py` | lossless typed capture / validation |
| `compare.py` | strict comparison / mutation / exception comparison |
| `identity.py` | source/input identity |
| `inventory.py` | case inventory |
| `isolation.py` | isolated execution support |
| `artifacts.py` | harness artifact handling |
| `stage_e_*.py` | approved comparison stage adapter/contract |

## 12. 검증 원칙

Harness package나 test가 repository에 존재한다는 사실만으로 특정 revision의 compatibility PASS를 의미하지 않는다.

실제 판정은 해당 revision에서:

~~~text
source identity 확인
-> input inventory 확인
-> before repeatability
-> after capture
-> strict comparison
-> mutation / exception 확인
-> artifact integrity 확인
~~~

을 수행한 결과를 기준으로 한다.

고정 fixture 개수나 과거 benchmark 수치는 이 README의 current contract에 포함하지 않는다.
