# Web UI Report Viewer Phase 1A Plan

> 작성일: 2026-05-05
> 상위 문서: [99_web_ui_report_viewer_plan.md](./99_web_ui_report_viewer_plan.md)

## 목적

- report list/detail + Stage2 quality lint result display를 로컬 웹 UI에서 안전하게 제공한다.

## 범위

포함:
- report list
- report detail
- Stage2 quality lint result display
- defensive JSON parsing
- localhost-only
- read-only report access

제외:
- model compare
- pipeline run button
- regression run button
- upload
- search/filter
- DB/SQLite
- alert/dashboard
- external network exposure

## 사전 검증

- report glob 확인
- JSON 유효성 확인
- Stage2 JSON 필드 확인
- `scripts/check_stage2_report_quality.py --input ... --pretty` 확인
- `--output` 기반 UI 내부 파싱 경로 확인
- FastAPI/Jinja2 설치 확인

예시:

```bash
python3 scripts/check_stage2_report_quality.py \
  --input path/to/stage2_report.json \
  --pretty

python3 scripts/check_stage2_report_quality.py \
  --input path/to/stage2_report.json \
  --output /tmp/stage2_quality_lint/<report_id>.json
```

## 파일 구조

```text
web/app.py
web/config.py
web/services/report_loader.py
web/services/qa_runner.py
web/templates/base.html
web/templates/index.html
web/templates/detail.html
web/static/style.css
web/requirements.txt
```

## 코드 예시 / 설계 스니펫

### config 기준

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPORT_GLOBS = [
    "reports/*_stage2_report.json",
    "lab/**/reports/*_stage2_report.json",
]

HOST = "127.0.0.1"
PORT = 8000
DEBUG = False

QA_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_stage2_report_quality.py"
QA_OUTPUT_DIR = Path("/tmp/stage2_quality_lint")
QA_TIMEOUT_SEC = 30
```

### report_id 기준

```python
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def make_report_id(file_path: Path) -> str:
    try:
        relative_path = file_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        relative_path = file_path.resolve()
    return hashlib.sha256(str(relative_path).encode("utf-8")).hexdigest()[:16]
```

### Report / ReportLoader 개요

- `REPORT_GLOBS`를 `PROJECT_ROOT.glob()`로 순회해 대상 JSON을 수집한다.
- 파일명 파싱 실패 시에도 partial load를 허용한다.
- `report_id`를 key로 조회하고 URL에는 file path를 노출하지 않는다.

### QARunner 개요

- subprocess 기본 인자: `--input`, `--output`
- `--pretty`는 사람 확인용이며 UI 내부 파싱 기본값으로 쓰지 않는다.
- `--fail-on-blocker`는 기본으로 넣지 않는다.
- return code만으로 품질 판정하지 않고 output JSON을 읽어 판정한다.

스니펫:

```python
result = subprocess.run(
    [
        "python3",
        str(self.script_path),
        "--input", str(report_path),
        "--output", str(output_path),
    ],
    capture_output=True,
    text=True,
    timeout=self.timeout_sec,
)
```

### lint output schema 처리 기준

```json
{
  "verdict": "PASS",
  "blockers": [],
  "warnings": [],
  "info": [],
  "summary": {
    "checked_fields": 28,
    "blocker_count": 0,
    "warning_count": 0,
    "info_count": 6
  }
}
```

- 카운트는 `summary.blocker_count`, `summary.warning_count`, `summary.info_count`에서 읽는다.
- 세부 항목은 `blockers`, `warnings`, `info` 배열을 사용해 표시한다.

### import / template path 기준

```python
from web.config import HOST, PORT, REPORT_GLOBS, QA_SCRIPT_PATH, QA_OUTPUT_DIR, QA_TIMEOUT_SEC
from web.services.report_loader import ReportLoader
from web.services.qa_runner import QARunner

BASE_DIR = Path(__file__).resolve().parent
templates = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
```

## UI 표시 원칙

- report body text는 원문 유지
- metadata/source IP table/known asset/raw preview는 마스킹
- raw JSON full view는 Phase 1A에서 기본 제외 또는 debug-only 제한

## 테스트 방법

- `py_compile`로 `web/*.py`, `web/services/*.py` 문법 확인
- Jinja2 template syntax 확인
- `uvicorn web.app:app --host 127.0.0.1 --port 8000` 기동 확인
- `curl`로 list/detail route 확인
- detail에서 quality lint 결과(요약 카운트 + 배열) 표시 확인

## Phase 1A 완료 기준

- all report globs load
- malformed filename partial load
- detail page renders
- quality lint displayed
- localhost-only
- no src/scripts/tests changes

## Phase 1B로 넘길 항목

- compare screen
- severity/verdict delta
- model agreement/disagreement
