# 98B_E세트_OpenCart_비교실험

- 작성 기준일: 2026-04-30
- 문서 역할: E세트(OpenCart/PHP) 비교 실험 인덱스 및 공통 실행 원칙
- 상세 문서:
  - `98B_E세트_OpenCart_R2_R2B_php_wrapper.md`
  - `98B_E세트_OpenCart_R3_R3B_search.md`
- 기준 데이터: Apache `security` 로그 표면 지표
- 대상 서비스: OpenCart
- 기본 URL: `http://192.168.56.111`
- 기본 UA prefix: `lab-e-set`

> 주의: 이 문서는 승인된 로컬 실험 환경에서만 사용한다. Apache 로그만으로는 PHP wrapper 실행 성공, config 파일 내용 노출, SQLi 성공, XSS 브라우저 실행, 로그인/권한 상승 성공, POST body 내부 처리 결과를 확정하지 않는다.

---

## 1. 문서 구조

E세트 원문이 길어져, 메인 문서는 인덱스와 공통 기준만 남긴다. 각 round의 상세 payload와 평가 기준은 별도 문서에서 관리한다.

| 문서 | 역할 |
|---|---|
| `docs/experiments/E_set/98B_E세트_OpenCart_비교실험.md` | E세트 전체 인덱스, 공통 원칙, 실행 순서 |
| `docs/experiments/E_set/98B_E세트_OpenCart_R2_R2B_php_wrapper.md` | PHP wrapper / config exposure / file disclosure 실험 상세 |
| `docs/experiments/E_set/98B_E세트_OpenCart_R3_R3B_search.md` | product/search SQLi/XSS 및 정상 search baseline 상세 |
| `docs/99_비교실험_후속개선_TODO.md` | 회귀 fixture, verdict taxonomy, hint 품질 개선 등 후속 작업 |

---

## 2. 실험 목적

E세트는 Juice Shop 중심 A/B/C/D세트 이후, OpenCart/PHP 기반 환경에서 탐지 로직이 일반화되는지 확인하기 위한 실험이다.

주요 확인 항목:

1. OpenCart의 `index.php?route=...` 구조에서 route parameter probing을 식별하는가.
2. PHP 기반 환경에서 `php://filter` 같은 wrapper/file disclosure intent를 인식하는가.
3. `/admin`, `/admin/index.php`, `/config.php`, `/admin/config.php` 같은 PHP/OpenCart 경로 탐색을 context-only probing으로 보존하는가.
4. `product/search` 계열 query에서 SQLi/XSS payload가 Apache 로그에 남을 때 기존 B/C세트 탐지 로직이 일반화되는가.
5. 정상 search baseline과 공격성 search payload를 분리하는가.
6. POST body visibility 한계를 OpenCart에서도 보수적으로 유지하는가.

---

## 3. 기본 변수 및 환경

```bash
export OPENCART_URL="http://192.168.56.111"
export UA_PREFIX="lab-e-set"
```

사전 확인:

```bash
curl -i "$OPENCART_URL/"
curl -i "$OPENCART_URL/index.php"
curl -i "$OPENCART_URL/admin/"
sudo tail -n 10 /var/log/apache2/app_security.log
```

확인할 것:

- `host="192.168.56.111"` 또는 OpenCart vhost로 남는지
- `uri`, `query_string`, `raw_request`가 정상 기록되는지
- OpenCart와 Juice Shop이 같은 Apache/vhost 구성을 공유하는 경우 host/vhost 구분이 가능한지
- export 시 KST 입력, DB UTC 조회, KST JSON 출력 흐름이 맞는지

---

## 4. Round 구성

| Round | 주제 | 상태 | 상세 문서/산출물 |
|---|---|---|---|
| R1 | route traversal / admin path | 수행 완료, 별도 문서화 선택 | `lab/04-26_E세트R1_산출물` |
| R2 | PHP wrapper / config exposure | 수행 완료, 코드 개선 반영 | `docs/experiments/E_set/98B_E세트_OpenCart_R2_R2B_php_wrapper.md`, `lab/04-26_E세트R2_산출물/2026-04-26_E세트R2_비교.md` |
| R2B | PHP wrapper variant 일반화 | 수행 완료 | `docs/experiments/E_set/98B_E세트_OpenCart_R2_R2B_php_wrapper.md`, `lab/04-30_E세트R2B_산출물/2026-04-30_E세트R2B_비교.md` |
| R3 | product/search SQLi/XSS | 수행 완료 | `docs/experiments/E_set/98B_E세트_OpenCart_R3_R3B_search.md`, `lab/04-26_E세트R3_산출물/2026-04-26_E세트R3_비교.md` |
| R3B | 정상 search baseline / 공격 search 분리 | 수행 완료 | `docs/experiments/E_set/98B_E세트_OpenCart_R3_R3B_search.md`, `lab/04-29_E세트R3B_산출물/2026-04-29_E세트R3B_비교.md` |
| R4 | POST body visibility 재확인 | 후보 | 이 문서의 후속 후보로 유지 |
| R5 | OpenCart probing sequence 일반성 | 후보 | D세트 R3 개선의 OpenCart 확장 후보 |

---

## 5. 공통 실행 순서

각 round는 한 export window에 섞지 않고 분리한다.

권장 흐름:

```text
1. round별 curl 실행
2. app_security.log tail 또는 DB row 확인
3. export_db_logs_cli.py로 security 로그 export
4. prepare_llm_input.py 실행
5. candidate / filtered_out / supporting_events / probing_sequence_summaries 확인
6. Stage1 실행
7. Stage2 실행
8. 비교 문서 작성
```

OpenCart는 route, PHP wrapper, probing, POST body visibility의 평가 축이 다르므로 한 구간에 모든 round를 섞지 않는다.

---

## 6. 평가 기준

| 평가 축 | 성공 기준 | 보수적 해석 |
|---|---|---|
| Route parameter visibility | `route=`가 query_string에 보존됨 | route 처리 성공은 단정하지 않음 |
| PHP wrapper intent | `php://filter`, `resource=`, `convert.base64-encode` 의미 복원 | source/config disclosure 성공은 body 없이는 미확정 |
| Config path probe | `/config.php`, `/admin/config.php` 접근 확인 | 파일 내용 노출 단정 금지 |
| SQLi query | `search=` 등에 SQLi payload 보존 | DB 결과 변경/유출 단정 금지 |
| XSS query | query parameter에 XSS payload 보존 | 브라우저 실행/DOM 반영 단정 금지 |
| Normal baseline | 정상 search/route가 candidate로 과승격되지 않음 | 정상/공격 비교는 보조 지표로만 사용 |
| POST body | content-type/length 확인 | body payload는 직접 보이지 않음 |
| Probing sequence | `probing_sequence_summaries` 생성 | context-only, incident 과승격 금지 |

---

## 7. 산출물 관리

public repo 공개 권장:

- 비교 Markdown
- 최종 Stage2 Markdown
- 통합 요약 문서

public repo 공개 비권장:

- raw export
- LLM input JSON
- Stage2 report input JSON
- analysis_candidates JSON
- noise_summary JSON
- stage1_errors JSON

OpenCart에서는 admin path, config path, route query, host/vhost 정보가 포함될 수 있으므로 raw/LLM input 공개에 더 주의한다.

---

## 8. 코드 개선 원칙

E세트는 OpenCart/PHP라는 특정 앱을 대상으로 하지만, 코드 개선은 실험환경 특화가 되면 안 된다.

금지:

- `lab-e-set-*` UA를 탐지 조건으로 사용
- `192.168.56.111`을 탐지 조건으로 사용
- 특정 OpenCart 응답 크기를 hard-code
- `/admin/config.php` 등 특정 경로 하나만 보고 high severity 자동 승격
- 200 응답을 source/config 노출 성공으로 단정

허용:

- 일반적인 PHP wrapper 패턴 인식
- 일반적인 config/admin/backup path probing 인식
- route/query parameter에 남은 공격 payload 인식
- same src_ip/time window 기반 probing sequence context 보존
- 정상 검색을 `reference_baseline`으로 보존

---

## 9. 후속 후보

E세트 기준 후속 후보는 다음이다.

1. R4 — POST body visibility 재확인
   - OpenCart admin login POST에서 method/content-type/content-length만 보이는 한계 확인
   - raw POST body 없이 로그인 성공/SQLi 성공 단정 금지

2. R5 — Directory probing sequence 일반성 확인
   - `/admin/`, `/config.php`, `/backup.sql`, `/phpmyadmin`, `/vendor/` 등
   - 개별 candidate 과승격 없이 `probing_sequence_summaries`로 보존하는지 확인

3. 코드 후속 개선
   - `suspicious_file_disclosure` verdict 정식화
   - benign normal search row의 `dir_probe:*` hint 정리
   - 회귀 fixture 정리

---

## 10. 발표용 한 줄 정리

E세트는 OpenCart/PHP 환경에서 route parameter, PHP wrapper, config/admin path probing, SQLi/XSS query, 정상 search baseline을 검증하는 실험이다. 핵심은 PHP/OpenCart 특성을 활용하되, 실제 파일 노출·SQLi 성공·XSS 실행은 Apache 로그만으로 단정하지 않는 것이다.
