# LLM 기반 Apache 침입 로그 분석 시스템

Apache 웹 로그를 MariaDB에 적재한 뒤 `export -> prepare -> stage1 -> stage2` 순서로 분석하고 LLM 기반 보안 보고서를 생성하는 파이프라인입니다.

이 저장소는 OWASP Juice Shop / OpenCart 같은 통제된 취약 애플리케이션 실험 환경에서 생성한 Apache 로그를 바탕으로, **Apache 로그 표면에 남는 정보만으로 어디까지 공격 정황을 해석할 수 있는지**를 검증합니다.

---

## 1. 핵심 방향

- Apache `access`, `security`, `error` 로그를 MariaDB에 적재합니다.
- raw export 전체를 LLM에 그대로 보내지 않고, 전처리 단계에서 후보 요청과 요약 정보를 선별합니다.
- Stage1은 개별 후보 요청을 분류합니다.
- Stage2는 Stage1 결과, 후보 밖 탐색성 요청, supporting context, probing sequence context를 종합해 보고서를 생성합니다.
- 결론은 **Apache 로그에서 직접 관찰 가능한 지표**를 기준으로 보수적으로 작성합니다.

직접 관찰 가능한 대표 필드:

- `method`, `uri`, `query_string`, `raw_request_target`
- `status_code`, `response_body_bytes`, `duration_us`, `ttfb_us`
- `resp_content_type`, `req_content_type`, `req_content_length`
- `src_ip`, `user_agent`, `request_id`, `error_link_id`

직접 단정하지 않는 것:

- raw POST body 원문
- response body 원문
- application 내부 result count
- DB query 실행 결과
- 실제 데이터 유출 확정

---

## 2. 파이프라인 개요

```text
Apache logs
  -> MariaDB 적재
  -> export_db_logs_cli.py
  -> prepare_llm_input.py
  -> llm_stage1_classifier.py
  -> llm_stage2_reporter.py
  -> Markdown / JSON reports
```

| 단계 | 스크립트 | 역할 |
|---|---|---|
| Export | `src/export_db_logs_cli.py` | MariaDB 로그를 JSON으로 export |
| Prepare | `src/prepare_llm_input.py` | 후보 선별, noise 요약, supporting events, probing sequence summary 구성 |
| Stage1 | `src/llm_stage1_classifier.py` | 후보 요청 LLM 분류 |
| Stage2 | `src/llm_stage2_reporter.py` | 종합 보고서 생성 |
| 통합 실행 | `src/run_analysis_pipeline.py` | prepare/stage1/stage2 통합 실행 |
| Shipper | `src/apache_log_shipper.py` | Apache 로그를 MariaDB에 적재 |

---

## 3. 빠른 시작

실제 운영/실행 기준은 아래 문서를 우선합니다.

- [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)

일반적인 실행 흐름:

```bash
# 1. LLM 입력 전처리
python ./src/prepare_llm_input.py \
  --input ./data/raw/security_YYYY-MM-DD_kst.json \
  --out-dir ./data/processed \
  --pretty \
  --write-filtered-out

# 2. Stage1 분류
python ./src/llm_stage1_classifier.py \
  --input ./data/processed/security_YYYY-MM-DD_kst_llm_input.json \
  --out-dir ./data/processed \
  --mode routine \
  --pretty

# 3. Stage2 보고서 생성
python ./src/llm_stage2_reporter.py \
  --stage1-results ./data/processed/security_YYYY-MM-DD_kst_stage1_results.json \
  --llm-input ./data/processed/security_YYYY-MM-DD_kst_llm_input.json \
  --out-dir ./reports \
  --pretty
```

DB export와 통합 실행 명령은 운영 가이드와 스크립트 설명 문서를 기준으로 확인합니다.

---

## 4. 문서 읽는 순서

1. [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)
2. [docs/00_전체_흐름_요약_가이드.md](docs/00_전체_흐름_요약_가이드.md)
3. [docs/02_LLM_환경_구축_및_설치.md](docs/02_LLM_환경_구축_및_설치.md)
4. [docs/04_로그_적재_및_운영.md](docs/04_로그_적재_및_운영.md)
5. [docs/05_Export_LLM_분석_전략.md](docs/05_Export_LLM_분석_전략.md)
6. [docs/06_통합_스크립트_설명_정리본.md](docs/06_통합_스크립트_설명_정리본.md)

실험 설계와 한계 문서:

- [docs/98B_B세트_비교실험.md](docs/98B_B세트_비교실험.md)
- [docs/98B_B세트_비교실험_라운드2.md](docs/98B_B세트_비교실험_라운드2.md)
- [docs/98B_C세트_비교실험.md](docs/98B_C세트_비교실험.md)
- [docs/98B_D세트_비교실험.md](docs/98B_D세트_비교실험.md)
- [docs/99_POST_body_visibility_한계와_해석_기준.md](docs/99_POST_body_visibility_한계와_해석_기준.md)
- [docs/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md](docs/99_HTML_fallback_fingerprint_구현_검토와_보류_결정.md)
- [docs/99_비교실험_후속개선_TODO.md](docs/99_비교실험_후속개선_TODO.md)

---

## 5. 최근 실험 산출물

최근 실험 산출물은 `lab/` 아래에 공개 가능한 요약 문서 중심으로 정리합니다.

| 구분 | 문서 | 요약 |
|---|---|---|
| A세트 | `lab/04-24_A세트_산출물/2026-04-24_A 세트 비교.md` | 인증 흐름과 provider별 보수성 비교 |
| B세트 R1 | `lab/04-25_B세트R1_산출물/2026-04-25_B세트R1_비교.md` | GET SQLi 가시성과 POST body visibility 한계 확인 |
| B세트 R2A | `lab/04-25_B세트R2A_산출물/2026-04-25_B세트R2A_비교.md` | xclose Boolean Blind는 byte delta 관찰, Time-based는 실패 |
| B세트 R2B | `lab/04-25_B세트R2B_산출물/2026-04-25_B세트R2B_비교.md` | double encoding 보존, temporal supporting context, educational SQL search FP 분리 |
| C세트 | `lab/04-25_C세트_산출물/04-25_C세트_비교.md` | XSS 탐지, HTML entity decode, FP review 개선 |
| D세트 R1 | `lab/04-26_D세트R1_산출물/2026-04-26_D세트R1_비교.md` | Traversal D-01~D-03 탐지 성공, D-04/D-05는 보조/미평가 |
| D세트 R2 | `lab/04-26_D세트R2_산출물/2026-04-26_D세트R2_비교.md` | HPP+SQLi / HPP+XSS 탐지 성공, benign HPP는 context |
| D세트 R3 | `lab/04-26_D세트R3_산출물/2026-04-26_D세트R3_비교.md` | Directory probing 보수적 판단 성공, 초기 sequence grouping은 부분 성공 |
| D세트 R3 개선후 | `lab/04-26_D세트R3_산출물/2026-04-26_D세트R3_개선후_비교.md` | `probing_sequence_summaries`로 candidate 과승격 없이 probing burst context 전달 개선 |
| D세트 통합 | `lab/04-26_D세트_산출물/2026-04-26_D세트_통합비교.md` | R1/R2/R3 및 R3 개선 결과 통합 정리 |
| 전체 요약 | `lab/2026-04-24_to_04-26_전체_비교실험_요약.md` | A/B/C/D세트 전체 결과 요약 |

B세트 핵심:

- `xclose` Boolean pair는 Apache 로그 표면 기준 `response_body_bytes` 차이가 명확하게 관찰되었습니다.
- `randomblob` 기반 Time-based Track은 기준치에 도달하지 못해 실패/미검증으로 기록했습니다.
- double URL encoding payload가 candidate로 보존되었고, temporal chain 저신호 step은 `supporting_events`로 보존되었습니다.

C세트 핵심:

- XSS payload 탐지와 URL/entity encoding 복원이 성공했습니다.
- `document.cookie`, external navigation, event handler, `javascript:` protocol 등 XSS 세부 hint가 강화되었습니다.
- 교육용 event handler 검색은 false positive review context로 보존되었습니다.

D세트 핵심:

- R1 Traversal은 D-01~D-03 핵심 요청 기준 성공했습니다.
- R2 HPP는 HPP+SQLi / HPP+XSS 결합 공격 탐지에 성공했습니다.
- R3 Directory Probing은 초기에는 sequence grouping이 약했지만, `probing_sequence_summaries` 도입 후 candidate를 늘리지 않고 burst probing context를 Stage2에 전달할 수 있게 되었습니다.

---

## 6. public repo 산출물 정책

이 저장소는 public repo로 관리하므로 상세 로그성 산출물은 기본적으로 제외합니다.

현재 `.gitignore` 정책:

```gitignore
raw/
*noise_summary.json
*stage1_errors.json
*analysis_candidates.json
*llm_input.json
*stage2_report_input.json
```

공개 권장:

- 비교 요약 Markdown 문서
- 최종 Stage2 Markdown 보고서
- 코드와 일반 문서

공개 비권장:

- raw export
- LLM input JSON
- Stage2 report input JSON
- analysis candidates JSON
- noise summary JSON
- stage1 error/debug JSON

이유:

- 내부 IP, request_id, raw_request_target, query_string, User-Agent, known asset 정보가 포함될 수 있습니다.
- raw full export가 아니더라도 LLM input/report input은 축약된 로그 데이터셋으로 볼 수 있습니다.

---

## 7. 운영 기준 디렉터리

로컬 운영 기준 경로:

- raw 입력: `/opt/web_log_analysis/data/raw`
- 전처리 결과: `/opt/web_log_analysis/data/processed`
- 보고서 결과: `/opt/web_log_analysis/reports`
- 실행 로그: `/opt/web_log_analysis/logs`

저장소 내 실험 산출물은 `lab/` 아래에 공개 가능한 요약 문서 중심으로 정리합니다.

---

## 8. 모델 비교 관점

동일한 system prompt와 동일한 로그 입력을 사용해도 provider별 해석 성향은 달라질 수 있습니다.

- OpenAI 계열은 known asset, 내부 테스트 가능성, 성공/유출 미확정 표현을 더 강하게 유지하는 경향이 있습니다.
- Anthropic 계열은 evasion, chain, campaign 구조를 더 적극적으로 묶어 설명하는 경향이 있습니다.
- 최종 평가는 모델 표현을 그대로 확정 결론으로 쓰지 않고, Apache 로그 표면에서 확인 가능한 지표와 함께 검토합니다.

---

## 9. 주의

- 본 저장소의 실험은 허가된 로컬/실험 환경을 전제로 합니다.
- 외부 시스템을 대상으로 한 공격 실행이나 검증 용도로 사용하지 않습니다.
- Apache 로그만으로 실제 DB 결과, response body 내용, 데이터 유출 여부를 확정하지 않습니다.
- POST body 내부 payload는 현재 baseline 입력에서 직접 보이지 않습니다.
- `resp_html_*` fingerprint 계열은 구현 검토 및 보류 항목이며 핵심 근거로 사용하지 않습니다.
- 실제 운영 명령, 경로, OpenAI/Claude 차이는 [docs/01_운영_기준_실행_가이드.md](docs/01_운영_기준_실행_가이드.md)를 우선합니다.
