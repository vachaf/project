# 98B_E세트_OpenCart_R2_R2B_php_wrapper

- 작성 기준일: 2026-04-30
- 문서 역할: E세트 Round 2 / Round 2B 상세 실행 문서
- 범위: OpenCart/PHP wrapper, config exposure, file/source disclosure intent
- 기준 데이터: Apache `security` 로그 표면 지표
- 대상 서비스: OpenCart (`http://192.168.56.111`)
- 상위 문서: `docs/98B_E세트_OpenCart_비교실험.md`

> Apache 로그만으로 실제 PHP source/config 노출 성공은 확정하지 않는다. 이 문서의 목적은 wrapper/file disclosure intent가 로그 표면에서 candidate로 보존되는지 확인하는 것이다.

---

## 1. 목적

Round 2/Round 2B의 목적은 다음이다.

1. `php://filter`, `convert.base64-encode`, `resource=` 조합을 PHP/file disclosure intent로 인식하는지 확인한다.
2. `route=`, `path=`, `file=` 등 parameter name이 달라도 wrapper intent를 보존하는지 확인한다.
3. `/config.php`, `/admin/config.php` 직접 접근은 candidate로 과승격하지 않고 context-only 또는 `low_signal_dir_probe`로 유지하는지 확인한다.
4. Stage2가 200/text/html 또는 response size만으로 실제 source/config 노출 성공을 단정하지 않는지 확인한다.

---

## 2. 기본 변수

```bash
export OPENCART_URL="http://192.168.56.111"
```

Round별 UA prefix:

```bash
export UA_PREFIX="lab-e-set"      # R2
export UA_PREFIX="lab-e-set-r2b"  # R2B
```

---

## 3. Round 2 — PHP wrapper / config exposure intent

### E-11 PHP Wrapper via Route Parameter

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-route-1" \
  --data-urlencode "route=php://filter/convert.base64-encode/resource=index.php" \
  "$OPENCART_URL/index.php"
```

기대:

- `route=php://filter...index.php` 요청이 candidate로 올라감
- decoded view에서 PHP wrapper 의미 복원
- `file_disclosure:php_filter_wrapper`, `file_disclosure:base64_source_intent`, `file_disclosure:resource_parameter` 계열 hint 기대
- 404면 route 미인식 또는 실패 가능성까지만 서술
- 실제 base64 소스 노출 여부는 response body 원문 없이는 확정하지 않음

### E-12 PHP Wrapper via Path-like Parameter

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-path-1" \
  --data-urlencode "path=php://filter/convert.base64-encode/resource=config.php" \
  "$OPENCART_URL/index.php"
```

기대:

- `path=` parameter 내 PHP wrapper intent 식별
- `config.php` 접근 의도와 file disclosure intent를 함께 식별
- status 200이어도 실제 config 노출 성공은 단정하지 않음

### E-13 Direct Config Path Probe

```bash
curl -i --path-as-is \
  -A "${UA_PREFIX}-config-root-1" \
  "$OPENCART_URL/config.php"

curl -i --path-as-is \
  -A "${UA_PREFIX}-config-admin-1" \
  "$OPENCART_URL/admin/config.php"
```

기대:

- `/config.php`, `/admin/config.php` 접근 시도 식별
- direct sensitive config path probe로 context-only 보존
- 단발 요청이면 candidate 과승격보다 `low_signal_dir_probe` 또는 context-only 해석이 적절
- `response_body_bytes=0`이면 파일 노출 성공이 아니라 본문 노출 증거 없음으로 기록

---

## 4. Round 2B — PHP wrapper variant 일반화 보강

Round 2B는 Round 2에서 개선한 PHP wrapper/file disclosure 탐지가 `route=`와 `path=`에만 묶이지 않는지 확인하는 보강 실험이다.

```bash
export UA_PREFIX="lab-e-set-r2b"
```

### E-14 PHP Wrapper via File Parameter

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-file-config-1" \
  --data-urlencode "file=php://filter/convert.base64-encode/resource=config.php" \
  "$OPENCART_URL/index.php"
```

기대:

- `file=` parameter 안의 PHP wrapper intent가 candidate로 보존됨
- `file_disclosure:php_filter_wrapper`
- `file_disclosure:base64_source_intent`
- `file_disclosure:resource_parameter`
- `file_disclosure:sensitive_resource:config_php`

### E-15 PHP Wrapper Targeting admin/config.php

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-path-admin-config-1" \
  --data-urlencode "path=php://filter/convert.base64-encode/resource=admin/config.php" \
  "$OPENCART_URL/index.php"
```

기대:

- `admin/config.php` 대상 wrapper 요청을 file disclosure intent로 보존
- direct `/admin/config.php` 접근과 달리 wrapper 기반 source/config disclosure 시도로 해석
- 실제 admin config 노출 성공은 response body 원문 없이는 확정하지 않음

### E-16 Lightweight Wrapper without base64 filter

```bash
curl -i -G \
  -A "${UA_PREFIX}-php-wrapper-route-config-nob64-1" \
  --data-urlencode "route=php://filter/resource=config.php" \
  "$OPENCART_URL/index.php"
```

기대:

- `php://filter`와 `resource=config.php` 조합만으로도 file disclosure intent를 인식하는지 확인
- `convert.base64-encode`가 없으므로 E-14/E-15보다 confidence는 낮을 수 있음
- candidate로 보존되더라도 성공 단정은 금지

### E-17 Direct Config Probe Control

```bash
curl -i --path-as-is \
  -A "${UA_PREFIX}-config-root-control-1" \
  "$OPENCART_URL/config.php"

curl -i --path-as-is \
  -A "${UA_PREFIX}-config-admin-control-1" \
  "$OPENCART_URL/admin/config.php"
```

기대:

- direct config path 단발 요청은 candidate로 과승격하지 않음
- `probing_sequence_summaries` 또는 `low_signal_dir_probe` context로 보존
- `response_body_bytes=0`이면 “본문 노출 증거 없음”으로 해석

---

## 5. 실행 후 확인 명령

prepare 결과 확인:

```bash
python3 src/prepare_llm_input.py \
  --input "$R2B_RAW" \
  --out-dir lab/04-30_E세트R2B_산출물/data/processed \
  --base-name opencart_e_r2b \
  --pretty \
  --write-filtered-out
```

요약 확인:

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("lab/04-30_E세트R2B_산출물/data/processed/opencart_e_r2b_llm_input.json")
data = json.loads(p.read_text(encoding="utf-8"))

print(data.get("meta", {}).get("counts", {}))
for c in data.get("analysis_candidates", []):
    print(c.get("user_agent"), c.get("verdict_hint"), c.get("score"), c.get("reason_hints"))
PY
```

기대:

```text
candidate_rows >= 3
filtered_out_rows >= 2
probing_sequence_summaries >= 1
```

핵심 기대:

- wrapper 변형은 `suspicious_file_disclosure` candidate
- direct config path는 candidate가 아님
- Stage2는 실제 파일 내용 노출 성공을 단정하지 않음

---

## 6. 실제 확인 결과 요약

### R2

- `route=php://filter...index.php` candidate 유지
- `path=php://filter...config.php`가 수정 후 candidate로 승격
- `/config.php`, `/admin/config.php`는 candidate 과승격 없이 context-only 유지

비교 문서:

- `lab/04-26_E세트R2_산출물/2026-04-26_E세트R2_비교.md`

### R2B

- `file=php://filter/convert.base64-encode/resource=config.php` candidate 보존
- `path=php://filter/convert.base64-encode/resource=admin/config.php` candidate 보존
- `route=php://filter/resource=config.php`는 base64 없이도 candidate 보존
- direct `/config.php`, `/admin/config.php`는 `low_signal_dir_probe`
- OpenAI Stage2는 PHP wrapper 기반 파일 노출 시도 정황으로 설명하면서 실제 노출 성공은 단정하지 않음

비교 문서:

- `lab/04-30_E세트R2B_산출물/2026-04-30_E세트R2B_비교.md`

---

## 7. 남은 개선점

1. Stage1 verdict taxonomy
   - 현재 `php://filter` 계열이 `suspicious_path_traversal`로 흡수되는 경향이 있음
   - `suspicious_file_disclosure` 또는 `suspicious_source_disclosure` 정식화 필요

2. direct config path hint 세분화
   - `/config.php` 200/0B는 성공도 안전도 단정하지 않음
   - `file_probe:config_php_200_empty_body` 같은 context-only hint 검토 가능

3. provider 비교
   - R2B는 OpenAI만 실행됨
   - Anthropic은 크레딧 여유가 있을 때 선택적으로 비교 가능

---

## 8. 최종 해석 원칙

- wrapper 기반 요청은 file/source disclosure intent로 해석한다.
- direct config path는 단발이면 candidate로 과승격하지 않는다.
- 200/text/html, 404, response size만으로 성공/실패를 확정하지 않는다.
- Apache 로그 표면만으로 source/config 내용 반환 여부를 확인할 수 없다.
- 코드 개선은 `php://filter`, `resource=`, `config.php` 같은 일반 신호를 사용해야 하며, OpenCart/IP/UA 전용 조건을 사용하지 않는다.
