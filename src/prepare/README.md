# src/prepare/

## 목적

`src/prepare/`는 `src/prepare_llm_input.py`에서 분리한 prepare 단계의 helper, pattern, context summary builder를 topic별로 관리하는 폴더다.

`prepare_llm_input.py`는 여전히 coordinator 역할을 유지한다. 이 폴더의 모듈들은 기존 공개 함수명 wrapper를 통해 호출되며, output key, counts, policy_notes, candidate/scoring/filtering, supporting_events 의미를 바꾸지 않는 mechanical refactor를 원칙으로 한다.

## 출력 파일명

`prepare_llm_input.py`의 기본 출력명은 기존 호환성을 위해 `<base>_llm_input.json`, `<base>_analysis_candidates.json`, `<base>_noise_summary.json` 형식을 유지한다.

windowed/scheduler artifact처럼 표준 파일명이 필요한 경우 `--flat-output-names`를 사용한다. 이 옵션은 output key/count/scoring/filtering 의미를 바꾸지 않고 파일명만 `llm_input.json`, `analysis_candidates.json`, `noise_summary.json`으로 바꾼다. `--write-filtered-out`를 함께 쓰면 `filtered_out_rows.json`도 같은 방식으로 저장한다.

`--flat-output-names`와 `--base-name`은 함께 쓰지 않는다.

## 현재 모듈

```text
decoders.py
l3_hints.py
models.py
method_summaries.py
protocol_anomalies.py
auth_behavior.py
static_baseline.py
crawler_baseline.py
apache_observability_context.py
sensitive_path_probe.py
ip_behavior.py
probing_sequence.py
mixed_baseline_scanner.py
sqli_hints.py
xss_hints.py
file_disclosure_hints.py
traversal_cmdi_hints.py
```

## 모듈별 역할

- `decoders.py`
  - URL/HTML entity 등 decoded variant 생성에 필요한 decoder helper를 관리한다.
- `l3_hints.py`
  - L3/transport-level hint helper를 관리한다.
- `models.py`
  - prepare 단계에서 공유하는 경량 데이터 모델을 관리한다.
- `method_summaries.py`
  - HTTP method behavior summary와 관련 constants 일부를 관리한다.
- `protocol_anomalies.py`
  - protocol anomaly summary와 관련 constants를 관리한다.
- `auth_behavior.py`
  - auth/login behavior summary와 관련 constants/patterns를 관리한다.
- `static_baseline.py`
  - static/health-like baseline summary와 static baseline constants 일부를 관리한다.
- `crawler_baseline.py`
  - crawler-like baseline summary와 crawler baseline constants/patterns를 관리한다.
- `apache_observability_context.py`
  - Apache handler / route / proxy / fallback 관찰값에서 topology-aware context reason hints를 생성한다.
  - 성공 판정이나 scoring에는 사용하지 않는다.
- `sensitive_path_probe.py`
  - sensitive path probe summary helper를 관리한다.
- `ip_behavior.py`
  - source-IP-scoped aggregate context와 IP behavior constants를 관리한다.
- `probing_sequence.py`
  - probing sequence summary helper를 관리한다.
- `mixed_baseline_scanner.py`
  - baseline/static/crawler-like와 scanner-like 요청이 섞인 context summary를 관리한다.
- `sqli_hints.py`
  - SQLi 전용 pattern/constants와 educational SQL search helper를 관리한다.
- `xss_hints.py`
  - XSS 전용 pattern/constants를 관리한다.
- `file_disclosure_hints.py`
  - file disclosure/PHP wrapper pattern과 detector를 관리한다.
- `traversal_cmdi_hints.py`
  - traversal/CMDI 전용 pattern constants를 관리한다.

## 분리 원칙

- mechanical refactor 우선.
- `prepare_llm_input.py`의 기존 공개 함수명 wrapper 유지.
- 기존 import fallback 패턴 유지.

```python
try:
    from src.prepare.<module> import ...
except ImportError:
    from prepare.<module> import ...
```

- output key, counts, policy_notes 의미 변경 금지.
- candidate/scoring/filtering 변경 금지.
- supporting_events 생성/연결 의미 변경 금지.
- expected/test fixture와 Stage2 reporter는 prepare refactor 커밋에서 수정하지 않음.
- constants 이동은 owner가 명확한 소규모 mini-move로만 수행.
- shared policy constants, decoded shared logic, scoring/filtering, supporting_events는 별도 계획 없이 이동하지 않음.

## Apache logs-only guard

prepare 모듈은 Apache access/security/error log 표면 신호만 보존한다. 다음은 단정하지 않는다.

- raw POST body 원문
- response body 원문
- DB query 결과
- 브라우저 실행 여부
- 로그인 성공 / 계정 탈취 / credential stuffing 성공 / lockout 발동
- file/source disclosure 성공
- path traversal 파일 읽기 성공
- command execution 성공
- server compromise
- static file 존재
- real crawler identity
- site structure / product/category page existence
- WordPress 존재 / admin access / .env/phpinfo/server-status/backup 노출

`status_code`, `resp_content_type`, `response_body_bytes`, 특정 IP, 특정 UA, `lab-*` UA, 특정 route, 특정 product name은 성공/침해/유출의 단독 증거로 쓰지 않는다.

## context-only collection

아래 collection은 context 보존용이다. 단독으로 incident 승격이나 severity 상승 근거가 아니다.

```text
probing_sequence_summaries
static_baseline_summaries
crawler_baseline_summaries
sensitive_path_probe_summaries
mixed_baseline_scanner_summaries
ip_behavior_aggregates
auth_behavior_summaries
method_behavior_summaries
protocol_anomaly_summaries
```

각 collection의 request_count는 scope가 다를 수 있으므로 서로 합산하거나 같은 사건 수처럼 직접 비교하지 않는다.

## 검증 기준

prepare 관련 변경 후 최소 검증:

```bash
python3 -m py_compile src/prepare/*.py src/prepare_llm_input.py
python3 scripts/check_prepare_regression.py --strict
python3 scripts/check_stage_dryrun_regression.py --strict
```

필요 시 전체 compile도 함께 실행한다.

```bash
python3 -m py_compile src/llm_stage1_classifier.py src/llm_stage2_reporter.py src/run_analysis_pipeline.py
```

현재 안정 기준:

```text
prepare regression: pass=18 warn=0 fail=0
stage dry-run regression: pass=12 warn=0 fail=0
```

## 관련 문서

- prepare split 인덱스: `../../docs/design/README.md`
- prepare round1 summary: `../../docs/design/99_prepare_module_split_round1_summary.md`
- prepare round2 summary: `../../docs/design/99_prepare_module_split_round2_summary.md`
- constants mini-move summary: `../../docs/design/99_prepare_constants_mini_move_summary.md`
- hints split summary: `../../docs/design/99_prepare_hints_split_summary.md`
- 현재 상태: `../../docs/진행상황.md`
- 후속 TODO: `../../docs/planning/99_비교실험_후속개선_TODO.md`
