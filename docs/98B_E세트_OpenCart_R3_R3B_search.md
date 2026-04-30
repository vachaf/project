# 98B_E세트_OpenCart_R3_R3B_search

- 작성 기준일: 2026-04-30
- 문서 역할: E세트 Round 3 / Round 3B 상세 실행 문서
- 범위: OpenCart product/search SQLi/XSS, HTML entity XSS, normal search baseline
- 기준 데이터: Apache `security` 로그 표면 지표
- 대상 서비스: OpenCart (`http://192.168.56.111`)
- 상위 문서: `docs/98B_E세트_OpenCart_비교실험.md`

> Apache 로그만으로 SQLi 성공, DB 결과 변경, XSS 브라우저 실행, DOM 반영 여부는 확정하지 않는다. 이 문서의 목적은 OpenCart `product/search` 구조에서도 기존 SQLi/XSS 탐지 로직이 일반화되는지 확인하는 것이다.

---

## 1. 목적

Round 3/Round 3B의 목적은 다음이다.

1. OpenCart의 `/index.php?route=product/search&search=...` 구조에서 SQLi/XSS payload가 candidate로 보존되는지 확인한다.
2. C세트에서 보강한 HTML entity decode 기반 XSS 탐지가 OpenCart에서도 작동하는지 확인한다.
3. 정상 검색 baseline이 공격성 low-signal으로 오해되지 않고 `reference_baseline`으로 보존되는지 확인한다.
4. Stage2가 정상/공격 비교를 하되, SQLi 성공 또는 XSS 실행을 단정하지 않는지 확인한다.

---

## 2. 기본 변수

```bash
export OPENCART_URL="http://192.168.56.111"
```

Round별 UA prefix:

```bash
export UA_PREFIX="lab-e-set"      # R3
export UA_PREFIX="lab-e-set-r3b"  # R3B
```

---

## 3. Round 3 — OpenCart SQLi / XSS query 재검증

Round 3은 B/C세트 탐지 로직이 OpenCart URL 구조에도 일반화되는지 확인한다.

### E-21 Product Search SQLi

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-sqli-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=x')) OR 1=1 --" \
  "$OPENCART_URL/index.php"
```

기대:

- `route=product/search`, `search=` parameter 보존
- SQLi payload가 B세트와 유사하게 탐지됨
- `sqli:or_true`, `sqli:sql_comment` 계열 hint 기대
- response size anomaly가 있어도 실제 SQLi 성공 단정 금지

### E-22 Product Search XSS

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-xss-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=<script>alert(1)</script>" \
  "$OPENCART_URL/index.php"
```

기대:

- XSS payload candidate 보존
- `<script>` 및 `alert()` 구조 인식
- 브라우저 실행 성공 단정 금지
- response body 반영 여부는 Apache 로그만으로 확정하지 않음

### E-23 Encoded XSS / Entity XSS

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-xss-entity-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;" \
  "$OPENCART_URL/index.php"
```

기대:

- HTML entity payload 식별
- `encoding:html_entity_payload`
- `encoding:html_entity_decoded`
- `encoding:html_entity_decoded_xss`
- `xss:html_entity_decoded_script`
- SQL comment `#` 오탐 재발 방지

---

## 4. Round 3B — 정상 search baseline 보강

Round 3B는 Round 3의 공격성 search 요청과 정상 search 요청을 같은 endpoint에서 비교하는 보강 실험이다.

```bash
export UA_PREFIX="lab-e-set-r3b"
```

### E-24 Normal Product Search Baseline

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-normal-apple-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=apple" \
  "$OPENCART_URL/index.php"
```

기대:

- 정상 검색 baseline
- candidate로 과승격하지 않음
- `benign_normal_search` 또는 정상 baseline 계열로 분리
- 공격 요청과 비교하는 보조 지표로만 사용

### E-25 Product Search SQLi Repeat

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-sqli-xclose-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=x')) OR 1=1 --" \
  "$OPENCART_URL/index.php"
```

기대:

- SQLi candidate 유지
- `sqli:or_true`, `sqli:sql_comment` 계열 hint 기대
- 향후 개선 시 `sqli:xclose_pattern` 또는 `sqli:quote_termination` hint 추가 검토

### E-26 Product Search XSS Repeat

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-xss-script-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=<script>alert(1)</script>" \
  "$OPENCART_URL/index.php"
```

기대:

- XSS candidate 유지
- 브라우저 실행 성공 단정 금지

### E-27 Product Search HTML Entity XSS Repeat

```bash
curl -i -G \
  -A "${UA_PREFIX}-search-xss-entity-1" \
  --data-urlencode "route=product/search" \
  --data-urlencode "search=&#x3C;script&#x3E;alert(1)&#x3C;/script&#x3E;" \
  "$OPENCART_URL/index.php"
```

기대:

- HTML entity decode 기반 XSS candidate 유지
- `xss:html_entity_decoded_script` 계열 hint 유지

---

## 5. 실행 후 확인 명령

prepare 결과 확인:

```bash
python3 src/prepare_llm_input.py \
  --input "$R3B_RAW" \
  --out-dir lab/04-29_E세트R3B_산출물/data/processed \
  --base-name opencart_e_r3b \
  --pretty \
  --write-filtered-out
```

요약 확인:

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("lab/04-29_E세트R3B_산출물/data/processed/opencart_e_r3b_llm_input.json")
data = json.loads(p.read_text(encoding="utf-8"))

print(data.get("meta", {}).get("counts", {}))
print("candidates:")
for c in data.get("analysis_candidates", []):
    print(c.get("user_agent"), c.get("verdict_hint"), c.get("score"), c.get("reason_hints"))
print("supporting_events:")
for s in data.get("supporting_events", []):
    print(s.get("user_agent"), s.get("supporting_role"), s.get("supporting_reason"), s.get("reason_hints"))
PY
```

R3B 기대:

```text
total_exported_rows=4
candidate_rows=3
filtered_out_rows=1
supporting_events=1
filtered_out_breakdown={"benign_normal_search": 1}
```

핵심 기대:

- 정상 search는 candidate가 아님
- 정상 search는 `reference_baseline` supporting event로 보존
- SQLi/XSS 3건은 candidate 유지
- `supporting:encoded_payload_trace`는 정상 search에 붙지 않음

---

## 6. 실제 확인 결과 요약

### R3

- `search=x')) OR 1=1 --` → SQLi candidate / `suspicious_sqli`
- `search=<script>alert(1)</script>` → XSS candidate / `suspicious_xss`
- `search=&#x3C;script&#x3E;alert(1)...` → HTML entity XSS candidate / `suspicious_xss`

비교 문서:

- `lab/04-26_E세트R3_산출물/2026-04-26_E세트R3_비교.md`

### R3B

- 정상 `search=apple`은 candidate로 과승격되지 않음
- 정상 search는 `benign_normal_search` 및 `reference_baseline`으로 보존
- SQLi 1건과 XSS 2건은 모두 candidate로 유지
- OpenAI Stage2는 정상 baseline을 후보 밖 탐색성 요청이 아니라 정상 비교군으로 설명
- Anthropic은 크레딧 문제로 미실행

비교 문서:

- `lab/04-29_E세트R3B_산출물/2026-04-29_E세트R3B_비교.md`

---

## 7. 남은 개선점

1. benign normal search hint 정리
   - `benign_normal_search` row에 `dir_probe:burst` hint가 남는 경우가 있음
   - 정상 baseline row에서는 `dir_probe:*` 계열 hint를 제거하거나 `normal_search_baseline` 계열 hint로 교체하는 것이 적절

2. SQLi xclose 세부 hint
   - 현재 `x')) OR 1=1 --`는 `or_true`, `sql_comment` 중심으로 잡힘
   - `sqli:xclose_pattern`, `sqli:quote_termination`, `sqli:parenthesis_termination` 추가 검토 가능

3. provider 비교
   - R3B는 OpenAI만 실행됨
   - Anthropic은 크레딧 여유가 있을 때 선택적으로 비교 가능

---

## 8. 최종 해석 원칙

- 정상 search는 공격 의도를 낮추는 근거가 아니라 reference baseline이다.
- SQLi/XSS payload는 정상 baseline과 분리해 candidate로 보존한다.
- 200/text/html, response size만으로 SQLi 성공/XSS 실행을 확정하지 않는다.
- HTML entity decode는 XSS 의미 복원을 위한 분석 view이지 실행 성공 증거가 아니다.
- 코드 개선은 일반 search parameter와 일반 공격 신호 기반으로 해야 하며, OpenCart/IP/UA 전용 조건을 사용하지 않는다.
