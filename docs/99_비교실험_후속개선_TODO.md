# 99_비교실험_후속개선_TODO

- 작성일: 2026-04-26
- 문서 역할: A/B/C/D 비교실험 이후 남은 후속 개선 과제 정리
- 기준: Apache 로그 표면 기반 LLM 분석 파이프라인

---

## 1. 우선순위 요약

| 우선순위 | 과제 | 이유 |
|---|---|---|
| P1 | `low_signal_dir_probe` burst grouping 강화 | D세트 R3에서 가장 큰 한계로 확인됨 |
| P1 | Stage2 후보 밖 탐색성 요청 섹션 강화 | filtered-out 요청을 단순 분포가 아니라 sequence/context로 보여줄 필요 |
| P2 | fallback HTML 반복 응답 보조 지표 정리 | 200 text/html 대용량 응답을 성공으로 오해하지 않도록 보조 설명 필요 |
| P2 | Time-based SQLi 재설계 여부 결정 | B세트 R2A에서 실패로 기록됨 |
| P2 | POST body visibility 정책 유지/확장 판단 | B세트 R1, D세트 R2에서 반복적으로 한계 확인 |
| P3 | D세트 R1 D-04/D-05 재실험 여부 결정 | absolute path / PHP wrapper는 현재 핵심 평가에서 제외됨 |

---

## 2. P1 — Directory Probing burst grouping 강화

### 배경

D세트 R3에서는 10건의 directory probing 성격 요청이 수집되었다. 그러나 Stage1 candidate는 `/server-status` 403 요청 1건뿐이었고, 나머지 9건은 `low_signal_dir_probe` 또는 `low_signal_fuzzing`으로 filtered out 처리되었다.

이 판단 자체는 보수적이고 안전하지만, R3의 실험 목적이었던 “짧은 시간 내 여러 민감 경로 요청을 하나의 probing sequence로 묶는 능력”은 충분히 만족하지 못했다.

### 개선 방향

- 같은 `src_ip`
- 짧은 시간 window, 예: 60~120초
- 민감 경로 사전 기반 요청 3건 이상
- 동일 또는 유사 User-Agent
- `404`, `403`, 또는 반복적인 fallback HTML 응답

위 조건을 만족하면 개별 incident로 과승격하지 않고 다음 중 하나로 보존한다.

```json
{
  "probing_sequence_summary": [
    {
      "src_ip": "...",
      "start": "...",
      "end": "...",
      "request_count": 7,
      "paths": ["/.git/config", "/.env", "/admin", "/backup"],
      "category": "low_signal_dir_probe_burst",
      "policy": "context_only"
    }
  ]
}
```

또는 기존 구조와 맞추려면 `supporting_events`에 context-only로 보존한다.

### 주의

- 단발 `/admin` 요청을 high severity incident로 올리면 안 된다.
- public repo에 raw path list를 공개할 때는 내부 IP/민감 payload 노출 정책을 확인한다.

---

## 3. P1 — Stage2 후보 밖 탐색성 요청 섹션 강화

### 배경

현재 Stage2는 `filtered_out_breakdown`을 기반으로 `low_signal_dir_probe 7건`, `low_signal_fuzzing 2건` 정도를 요약한다. 그러나 실제 경로 목록, 시간 집중도, 동일 출발지 여부가 충분히 드러나지 않는다.

### 개선 방향

Stage2 report input에 다음 요약을 추가하는 방식을 검토한다.

- filtered-out directory probe 경로 목록 상위 N개
- 같은 IP의 연속 요청 수
- 첫 요청/마지막 요청 시각
- status 분포
- response_body_bytes 반복 패턴
- fallback HTML 가능성

예시 출력:

```text
후보 밖 탐색성 요청:
- 192.168.56.110에서 17초 동안 7건의 directory probe 성격 요청 발생
- 경로: /.git/config, /.env, /admin, /administrator, /backup, /phpmyadmin, /manager/html
- 다수 요청은 200 text/html 75002B로 동일 fallback HTML 가능성
- /server-status만 403으로 차단되어 candidate로 승격
```

---

## 4. P2 — fallback HTML 반복 응답 보조 지표 정리

### 배경

C/D세트에서 `200 text/html`, `response_body_bytes=75002` 같은 응답이 반복적으로 관찰되었다. Juice Shop SPA fallback HTML 가능성이 높지만, 현재 정책상 `resp_html_*` fingerprint는 핵심 근거로 쓰지 않고 있다.

### 개선 방향

- 핵심 판정 근거가 아니라 보조 설명으로만 사용한다.
- 반복되는 `status=200`, `resp_content_type=text/html`, 동일/유사 `response_body_bytes`를 fallback candidate로 표시한다.
- “파일 노출 성공” 또는 “관리 페이지 접근 성공”으로 단정하지 않도록 Stage2 문구를 보강한다.

권장 표현:

```text
200 text/html 대용량 응답이 반복되지만, response body 원문이 없고 동일 크기 fallback 패턴이 반복되므로 민감 리소스 노출 성공으로 단정하지 않는다.
```

---

## 5. P2 — Time-based SQLi 재설계 여부

### 배경

B세트 R2A에서 `randomblob` 기반 Time-based Track은 `duration_us` / `ttfb_us` 기준으로 충분한 지연 차이를 만들지 못했다.

### 현재 결론

- 실패 또는 미검증으로 유지한다.
- Time-based를 억지로 성공 처리하지 않는다.
- Boolean xclose처럼 물리 지표가 명확한 실험과 분리한다.

### 후속 검토

- DB/애플리케이션별로 실제 지연을 만드는 payload를 별도 조사한다.
- baseline median 3회 이상과 delay median 3회 이상을 비교한다.
- 네트워크 편차보다 충분히 큰 차이, 예: 30배 이상 또는 2초 이상을 기준으로 둔다.

---

## 6. P2 — POST body visibility 정책

### 배경

B세트 R1과 D세트 R2에서 POST body 내부 payload/HPP가 Apache 로그 baseline에서 직접 보이지 않는 문제가 반복 확인되었다.

### 현재 정책

- raw POST body를 baseline LLM input에 포함하지 않는다.
- POST body 공격은 method, URI, content-type, content-length, status 정도로만 보수적으로 해석한다.
- 실제 body payload나 서버 내부 처리 결과는 단정하지 않는다.

### 후속 선택지

1. 현재 정책 유지
   - privacy/security 관점에서 안전
   - POST body 분석 한계는 문서화

2. 제한적 body metadata만 추가
   - field name hash
   - length bucket
   - content-type
   - form field count

3. 실험 전용 body capture
   - public repo에는 절대 raw body 공개 금지
   - 보고서에는 요약만 포함

---

## 7. P3 — D세트 R1 D-04/D-05 재실험

### 배경

D세트 R1에서 D-01~D-03은 성공했지만, D-04 absolute path와 D-05 PHP wrapper는 핵심 평가에 포함되지 않았다.

### 재실험 조건

D-04:

```bash
curl -i --path-as-is \
  -A "lab-d-set-trav-absolute-passwd-2" \
  "$JUICE_URL/etc/passwd"
```

D-05:

- 실제 OpenCart/PHP target URL 확인 후 실행
- Juice Shop URL로는 PHP wrapper 검증으로 보지 않음

### 판단

현재 D세트 결론을 위해 필수는 아니다. 발표 또는 추가 검증 시간이 있으면 수행한다.

---

## 8. 유지해야 할 원칙

- raw_request_target 보존
- query_string 원본 보존
- URL decode/entity decode view는 분석용으로만 추가
- response body 원문 없는 성공 단정 금지
- raw POST body 없는 POST payload 단정 금지
- known asset IP는 내부 테스트 가능성으로 병기
- provider별 표현 차이는 Apache 로그 표면 지표로 보정
- public repo에는 상세 로그성 JSON 비공개

---

## 9. 구현 상태 (2026-04-26)

### 완료

- `src/prepare_llm_input.py`
- 일반화된 path pattern, 동일 `src_ip`, 120초 window 기준으로 `probing_sequence_summaries` 생성
- 기존 `analysis_candidates` 승격 규칙은 유지하고 sequence summary 는 `context_only` 정책으로만 추가
- 반복 `200 text/html` + 동일 `response_body_bytes`는 fallback-like HTML 보조 지표로만 요약

### 확인 결과

- D세트 R3 재처리에서 기존 candidate 1건, filtered-out 9건은 유지됨
- `probing_sequence_summaries` 1건 생성 확인
- sample path에 `/.git/config`, `/.env`, `/admin`, `/backup`, `/server-status`, `/phpmyadmin`, `/manager/html` 포함 확인
- Stage2 dry-run report input에 `probing_sequence_summary_count`, `probing_sequence_summaries`, context-only policy 반영 확인

### 남은 TODO

- Stage2 실제 LLM 호출 결과가 provider별로 probing sequence 문맥을 얼마나 안정적으로 서술하는지 추가 확인
- fallback-like HTML의 “유사 크기” 허용 범위를 더 일반화할지 여부는 후속 검토
- public repo용 비교 문서(`개선후_비교.md`)는 실제 재처리 결과를 정리할 때 별도 작성

---

## 10. 현재 결론

즉시 수정이 필요한 치명적 문제는 없다. 후속 개선은 D세트 R3에서 드러난 low-signal directory probing sequence 보존과 Stage2 설명력 개선에 집중하는 것이 적절하다.
