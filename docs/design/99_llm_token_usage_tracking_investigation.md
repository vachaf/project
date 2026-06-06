# 99_llm_token_usage_tracking_investigation

- 작성일: 2026-06-06
- 문서 상태: investigation / implementation plan candidate
- 기준 커밋: 200e4114d2be9b0ec892b05326375c000e063fad
- 범위: Stage1/Stage2 LLM token usage 기록 가능성 조사
- 비범위: 코드 수정, DB schema 수정, provider call 변경, prompt/schema 변경, 비용 계산 구현

## 1. 결론

현재 코드도 provider 원본 응답 자체는 `LLMResponse.raw_response`로 받는다.

따라서 OpenAI/Anthropic 응답의 `usage`를 얻을 가능성은 있다. 다만 현재 정상 성공 경로에서는 `usage`를 추출하지 않고, Stage1/Stage2 artifact에도 저장하지 않는다.

가장 안전한 1차 구현 방향은 DB schema 변경 없이 artifact에만 token usage를 남기는 것이다.

권장 순서:

1. `llm_client.py`에서 provider별 `raw_response["usage"]`를 normalized usage로 추출한다.
2. Stage1 개별 candidate result에 `llm_usage`를 붙인다.
3. Stage1 `meta.llm_usage_totals`에 합산값을 둔다.
4. Stage2 `stage2_report.json.meta.llm_usage`에 report call usage를 둔다.
5. Anthropic Stage2 JSON repair가 발생하면 initial/repair usage를 분리 저장하고 total도 별도로 둔다.
6. `job_events.detail_json`에는 기본적으로 쓰지 않고, 필요하면 `JOB_SUCCEEDED` 또는 `PIPELINE_COMPLETED`에 aggregate totals만 후속으로 검토한다.

## 2. 현재 코드 조사

### 2.1 provider wrapper

대상 파일:

- `src/llm_client.py`

현재 구조:

- `LLMResponse` dataclass는 `output_text`, `response_id`, `raw_response`, `provider`, `model`, `stop_reason`을 가진다.
- `call_openai_responses()`는 `/responses` 응답 JSON 전체를 `raw_response`로 보존한다.
- `call_anthropic_messages()`는 `/messages` 응답 JSON 전체를 `raw_response`로 보존한다.
- 하지만 `LLMResponse`에 `usage` 전용 필드는 없다.
- `response_payload_stop_reason()`은 top-level `stop_reason`만 읽는다. OpenAI Responses의 상태/불완전 사유나 usage는 별도 추출하지 않는다.

판단:

- provider response가 `usage`를 포함하면 현재 wrapper 경계에서는 이미 접근 가능하다.
- 정상 산출물에 안정적으로 남기려면 raw response 전체를 저장하지 말고 usage만 normalized 형태로 추출해야 한다.

### 2.2 Stage1

대상 파일:

- `src/llm_stage1_classifier.py`

현재 구조:

- candidate별로 `classify_candidate()`가 `call_llm_json()`을 호출한다.
- 성공 시 `Stage1Result`에 `response_id`, `raw_output_text`는 저장한다.
- `llm_response.raw_response`는 성공 결과에 저장하지 않는다.
- empty output error에서는 `raw_response_excerpt`를 error artifact에 일부 저장한다.
- dry-run은 실제 provider call 없이 request plan만 `stage1_results.json`에 저장한다.

판단:

- candidate별 usage는 `classify_candidate()` 성공 시점에 붙일 수 있다.
- Stage1은 candidate별 API 호출 구조라 per-candidate usage 저장에 가장 적합하다.
- `stage1_results.json.results[*].llm_usage`와 `stage1_results.json.meta.llm_usage_totals` 조합이 가장 자연스럽다.

### 2.3 Stage2

대상 파일:

- `src/llm_stage2_reporter.py`

현재 구조:

- `build_report_input()`으로 `stage2_report_input.json`을 먼저 생성한다.
- 정상 경로에서는 `call_llm_json()` 응답을 parse하고 `stage2_report.json`에 다음 meta를 저장한다.
  - `provider`
  - `selected_model`
  - `response_id`
  - `stop_reason`
  - `json_parse_strategy`
- 정상 `stage2_report.json`에는 raw response나 usage가 저장되지 않는다.
- parse 실패/empty output 경로에서는 `stage2_report_raw_error.json`에 raw response를 저장한다.
- Anthropic JSON parse 실패 시 repair request를 한 번 더 호출한다. repair 성공 시 최종 report에는 repair response metadata만 남고, initial response usage는 현재 저장되지 않는다.
- dry-run은 실제 provider call 없이 `report: null`과 dry-run meta만 저장한다.

판단:

- Stage2 usage는 `stage2_report.json.meta.llm_usage`에 붙일 수 있다.
- Anthropic repair path는 비용/usage 관점에서 두 번 호출하므로 initial/repair를 분리해야 한다.
- parse 실패 artifact에는 현재 raw response가 들어가므로 usage도 raw response 안에 있을 수 있지만, 정상화된 usage field는 없다.

### 2.4 run_analysis_pipeline / full_report runner / DB-backed worker

대상 파일:

- `src/run_analysis_pipeline.py`
- `src/full_report_job_runner.py`
- `src/analysis_job_worker.py`
- `web/services/analysis_job_repository.py`

현재 구조:

- `run_analysis_pipeline.py`는 Stage1/Stage2 CLI를 subprocess로 실행하고 artifact를 복사한다.
- `full_report_job_runner.py`는 run artifact path를 `FullReportRunResult`로 mapping한다.
- `analysis_reports`에는 `stage1_result_path`, `stage2_report_path`, `stage2_report_md_path`, `viewer_payload_path` 등 artifact path만 저장한다.
- `analysis_reports`에는 token usage 전용 컬럼이 없다.
- `job_events.detail_json`은 JSON 저장 가능하고 recursive redaction도 적용된다.
- worker는 `PIPELINE_COMPLETED`, `REPORT_SAVE_*`, `JOB_SUCCEEDED`, `JOB_FAILED` events를 기록하지만 usage를 읽거나 합산하지 않는다.

판단:

- DB schema 변경 없이 artifact에 usage를 저장하는 것은 가능하다.
- DB schema 변경 없이 `job_events.detail_json`에 aggregate usage를 저장하는 것도 기술적으로 가능하다.
- 하지만 per-candidate usage나 provider 세부 breakdown을 events에 넣으면 event payload가 커지고 event timeline이 비용/telemetry 저장소처럼 변할 수 있다.
- 1차 구현은 artifact-only가 안전하다.

## 3. provider별 usage field 차이

### 3.1 OpenAI Responses API

공식 API reference 기준 Response object에는 `usage`가 있고, 예시는 다음 필드를 포함한다.

```json
{
  "usage": {
    "input_tokens": 32,
    "input_tokens_details": {
      "cached_tokens": 0
    },
    "output_tokens": 18,
    "output_tokens_details": {
      "reasoning_tokens": 0
    },
    "total_tokens": 50
  }
}
```

OpenAI reasoning model 문서 기준 reasoning tokens는 API에서 보이지 않는 내부 reasoning token이지만 `usage.output_tokens_details.reasoning_tokens`로 수량을 볼 수 있고, output token으로 과금된다.

OpenAI normalized mapping 후보:

```json
{
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "response_id": "resp_...",
  "input_tokens": 32,
  "cached_input_tokens": 0,
  "output_tokens": 18,
  "reasoning_tokens": 0,
  "total_tokens": 50,
  "raw_usage": {
    "input_tokens": 32,
    "input_tokens_details": {"cached_tokens": 0},
    "output_tokens": 18,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 50
  },
  "estimated": false
}
```

### 3.2 Anthropic Messages API

Anthropic Messages response도 `usage`를 제공한다. prompt caching 문서 기준 cache 사용 시 input token field가 나뉜다.

주요 필드:

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `cache_creation`
- `service_tier`

Anthropic 문서 기준 total input tokens는 다음 합산으로 계산한다.

```text
total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
```

Anthropic normalized mapping 후보:

```json
{
  "provider": "anthropic",
  "model": "claude-...",
  "response_id": "msg_...",
  "input_tokens": 410,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 0,
  "total_input_tokens": 410,
  "output_tokens": 585,
  "total_tokens": 995,
  "service_tier": "standard",
  "raw_usage": {
    "input_tokens": 410,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 585,
    "service_tier": "standard"
  },
  "estimated": false
}
```

주의:

- Anthropic `input_tokens`는 cache field가 있을 때 전체 입력 token과 같지 않을 수 있다.
- OpenAI `total_tokens`는 provider가 제공하지만, Anthropic은 normalized layer에서 계산하는 편이 안전하다.
- provider별 cache/read/write token은 비용 단가가 다를 수 있으므로 단일 `total_tokens`만으로 비용을 계산하면 부정확할 수 있다.

## 4. 질문별 답변

### Q1. OpenAI/Anthropic 응답 usage를 현재 코드가 받는가?

부분적으로 받는다.

- wrapper는 원본 응답 전체를 `LLMResponse.raw_response`로 보존한다.
- provider가 `usage`를 내려주면 `raw_response["usage"]`로 접근 가능하다.
- 그러나 현재 정상 성공 artifact에는 usage를 추출/저장하지 않는다.

### Q2. Stage1 개별 candidate 결과에 usage를 붙일 수 있는가?

가능하다.

권장 위치:

```json
{
  "results": [
    {
      "candidate_index": 0,
      "request_id": "...",
      "response_id": "resp_...",
      "llm_usage": {
        "provider": "openai",
        "model": "gpt-5.4-mini",
        "input_tokens": 123,
        "output_tokens": 45,
        "total_tokens": 168,
        "estimated": false
      }
    }
  ],
  "meta": {
    "llm_usage_totals": {
      "provider": "openai",
      "selected_model": "gpt-5.4-mini",
      "call_count": 1,
      "input_tokens": 123,
      "output_tokens": 45,
      "total_tokens": 168,
      "estimated": false
    }
  }
}
```

주의:

- Stage1은 candidate별 call이므로 per-candidate usage가 자연스럽다.
- 실패한 candidate는 provider 응답을 못 받았을 수 있으므로 `llm_usage`를 생략하거나 `unavailable_reason`을 둔다.
- raw response 전체 저장은 피한다.

### Q3. Stage2 report에 usage를 붙일 수 있는가?

가능하다.

권장 위치:

```json
{
  "meta": {
    "provider": "openai",
    "selected_model": "gpt-5.4",
    "response_id": "resp_...",
    "llm_usage": {
      "stage": "stage2",
      "provider": "openai",
      "model": "gpt-5.4",
      "input_tokens": 1000,
      "output_tokens": 600,
      "total_tokens": 1600,
      "estimated": false
    }
  },
  "report": {}
}
```

Anthropic repair path 권장:

```json
{
  "meta": {
    "llm_usage": {
      "stage": "stage2",
      "calls": [
        {"call_role": "initial", "provider": "anthropic", "total_tokens": 1200},
        {"call_role": "repair", "provider": "anthropic", "total_tokens": 300}
      ],
      "totals": {
        "call_count": 2,
        "total_tokens": 1500
      },
      "estimated": false
    }
  }
}
```

### Q4. provider별 usage field 차이는 무엇인가?

요약:

| provider | current endpoint | provider usage fields | normalized 주의 |
|---|---|---|---|
| OpenAI | `/v1/responses` | `input_tokens`, `input_tokens_details.cached_tokens`, `output_tokens`, `output_tokens_details.reasoning_tokens`, `total_tokens` | reasoning tokens는 output usage에 포함되는 과금 대상이다. |
| Anthropic | `/v1/messages` | `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation`, `service_tier` | total input은 cache read/create/input 합산으로 계산한다. |

### Q5. mock/offline/dry-run provider에서는 어떻게 처리할 것인가?

현재 코드에는 별도 mock provider는 없고 `--dry-run`이 있다.

권장:

- dry-run은 실제 API call이 없으므로 usage를 기록하지 않는다.
- dry-run artifact에는 필요하면 다음처럼 명시한다.

```json
{
  "llm_usage": {
    "available": false,
    "estimated": false,
    "unavailable_reason": "dry_run_no_provider_call"
  }
}
```

토큰 추정은 1차 구현에서 하지 않는다.

이유:

- provider tokenizer 차이가 있다.
- system/schema wrapping 방식이 provider마다 다르다.
- Anthropic은 JSON schema instruction을 system에 문자열로 붙이고 있어 OpenAI 요청과 입력 token 구성이 다르다.
- 비용/usage 목적이면 실제 provider response usage가 더 신뢰 가능하다.

### Q6. token usage를 job_events에 합산 기록할지, artifact에만 둘지?

권장 1차 구현은 artifact-only다.

이유:

- DB schema 변경이 없다.
- per-candidate usage를 Stage1 artifact에 가장 정확히 보존할 수 있다.
- Stage2 repair call처럼 call-level breakdown이 필요한 경우 artifact가 더 적합하다.
- `job_events`는 lifecycle/timeline 용도이며 비용 telemetry 저장소로 확장하면 payload가 커질 수 있다.

후속으로 job_events에 남긴다면 aggregate만 권장한다.

후보:

- `PIPELINE_COMPLETED.detail_json.llm_usage_totals`
- 또는 `JOB_SUCCEEDED.detail_json.llm_usage_totals`

권장 event payload shape:

```json
{
  "llm_usage_totals": {
    "stage1_total_tokens": 10000,
    "stage2_total_tokens": 2000,
    "total_tokens": 12000,
    "estimated": false
  }
}
```

금지 권장:

- raw provider response 저장 금지
- prompt text 저장 금지
- per-candidate usage 전체를 job_events에 반복 저장 금지

### Q7. DB schema 변경 없이 가능한가?

가능하다.

가능한 범위:

- `stage1_results.json`에 per-candidate usage와 meta totals 추가
- `stage2_report.json.meta`에 usage 추가
- `stage2_report_error.json` / `stage2_report_raw_error.json`에 normalized usage 추가
- `job_events.detail_json`에 aggregate usage 추가

불가능하거나 비권장인 범위:

- `analysis_reports`에 usage 전용 컬럼 추가 없이 DB query/filter/sort를 직접 지원하는 것
- model/provider별 비용 집계를 SQL로 안정적으로 조회하는 것

DB 조회가 필요한 운영 지표가 되면 후속 schema 설계가 필요하다.

### Q8. 비용 추정까지 할 것인가, 아니면 token counts만 기록할 것인가?

1차 구현은 token counts만 권장한다.

이유:

- provider/model pricing은 시점별로 바뀐다.
- cache read/cache creation/reasoning/output/service tier는 단가가 다를 수 있다.
- 비용 계산에는 가격표 버전, currency, billing policy, provider account tier가 필요하다.
- 잘못된 비용 추정은 운영 판단을 흐릴 수 있다.

후속 비용 추정이 필요하면 별도 artifact 또는 별도 문서로 다음 metadata를 함께 고정해야 한다.

```json
{
  "cost_estimate": {
    "enabled": true,
    "currency": "USD",
    "pricing_source": "manual_snapshot",
    "pricing_snapshot_date": "YYYY-MM-DD",
    "estimated_cost": 0.0
  }
}
```

## 5. 안전한 normalized usage helper 후보

코드 변경 시 helper는 provider wrapper 계층이 가장 적절하다.

후보 API:

```python
def normalize_llm_usage(response: LLMResponse, *, call_role: str) -> dict:
    ...
```

공통 필드 후보:

```json
{
  "schema_version": "llm_usage.v1",
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "response_id": "resp_...",
  "call_role": "stage1_candidate",
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "estimated": false,
  "provider_usage": {}
}
```

Provider-specific field는 `provider_usage` 또는 `breakdown` 아래에 둔다.

```json
{
  "breakdown": {
    "cached_input_tokens": 0,
    "reasoning_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "service_tier": "standard"
  }
}
```

## 6. 테스트 후보

코드 구현 시 추가할 테스트:

- OpenAI raw response fixture에서 `usage` normalized 추출
- Anthropic raw response fixture에서 `usage` normalized 추출
- Anthropic cache usage total input 계산
- Stage1 success result에 `llm_usage` 포함
- Stage1 meta totals 합산
- Stage2 report meta에 `llm_usage` 포함
- Stage2 Anthropic repair path에서 initial/repair usage 분리
- dry-run에서 `available=false` 또는 usage 생략
- error path에서 raw response 전체가 정상 artifact로 새지 않는지 확인
- DB schema 변경 없이 기존 `analysis_reports` upsert 테스트 유지

## 7. Open questions

- Stage1 result schema를 외부에서 strict하게 소비하는 도구가 있는가?
- `raw_output_text`를 계속 저장하는 현재 정책과 token usage 저장 정책을 함께 재검토할 필요가 있는가?
- `job_events.detail_json`에 aggregate를 남길 경우, Web UI timeline에 표시할 것인가?
- provider별 `total_tokens` 합산을 같은 의미로 비교할지, provider별 breakdown을 우선할지 결정이 필요하다.
- 비용 추정은 가격 snapshot을 어디에 둘지 결정한 뒤 별도 작업으로 진행한다.

## 8. 참고 공식 문서

- OpenAI Responses API Response object: `usage.input_tokens`, `usage.output_tokens`, `usage.total_tokens`, details fields를 제공한다.
- OpenAI reasoning guide: reasoning tokens는 `usage.output_tokens_details.reasoning_tokens`에서 확인 가능하며 output token으로 과금된다.
- Anthropic prompt caching docs: `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`를 제공하며 total input은 세 input field 합산이다.
- Anthropic service tiers docs: response `usage`에 `service_tier`가 포함될 수 있다.
