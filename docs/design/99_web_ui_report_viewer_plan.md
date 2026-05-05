# Apache 웹 로그 분석 플랫폼 — Stage2 보고서 뷰어 구축 계획서 (수정)

> **작성일**: 2026-05-05  
> **문서 위치**: `docs/design/99_web_ui_report_viewer_plan_v2.md`  
> **대상**: 현재 LLM 서버 환경에서 로컬 웹 뷰어 구축  
> **범위**: Phase 1A (보고서 조회 + QA 표시) / Phase 1B (모델 비교)

---

## 0. 이 계획서의 변경사항

이전 계획서(web_console_build_plan.md / web_ui_plan.md)의 4가지 추정 오류를 수정:

| # | 문제점 | 원래 방식 | 수정된 방식 |
|---|--------|---------|-----------|
| 1 | 보고서 경로 고정 | `/opt/web_log_analysis/reports` 단일값 | `REPORT_GLOBS` (glob 기반 다중 경로) |
| 2 | URL 파일 경로 충돌 | `/report/{filename}` | `report_id` (hash 기반 안전 ID) |
| 3 | QA 스크립트 | `run_qa_check_production_v4.py` | `scripts/check_stage2_report_quality.py` |
| 4 | CSS 의존성 | Tailwind CDN | Plain CSS (오프라인 대응) |

**추가 설계**: Phase 1을 1A(조회+QA) / 1B(비교)로 쪼개 더 안전하고 점진적이게 진행

---

## 1. 현재 프로젝트 상태 진단

### 1.1 핵심 현황

```
/opt/web_log_analysis/
├── src/                        ← 파이프라인 (건드리지 않음)
├── data/raw/                   ← export JSON (외부 소스 X)
├── data/processed/             ← prepare/stage1 출력
├── reports/                    ← 메인 stage2 보고서
│   └── op-security_2026-04-25_..._stage2_report.json (8건 존재)
├── lab/*/reports/              ← 실험별 stage2 보고서 (10+ 건)
├── config/llm.env              ← API 키 (절대 노출 X)
├── docs/                       ← 문서 체계 (읽기 전용)
├── tests/fixtures/expected/    ← regression 기대값
└── web/                        ← ★ 새로 만들 폴더
```

### 1.2 현재 보고서 관리 상태

**보고서 파일의 현실:**

```bash
# reports/ 폴더
ls /opt/web_log_analysis/reports/*_stage2_report.json | wc -l
# → 8개 (main run)

# lab/ 하위 폴더들
find /opt/web_log_analysis/lab -name "*_stage2_report.json" | wc -l
# → 10+ 개 (실험 세트별)
```

**파일명 패턴들 (현재):**
- `op-security_2026-04-25_18-23-00_to_2026-04-25_18-29-00_kst_stage2_report.json`
- `cl-security_2026-04-25_18-23-00_to_2026-04-25_18-29-00_kst_v2_stage2_report.json`
- `lab/04-25_B세트_R2B_산출물/reports/b_r2b_stage1_sqli_2026-04-25_kst_stage2_report.json`
- `lab/LLM샘플검증/2026-05-04_BCE_sample_review.md` (문서)

**현황 분석:**
- ✅ 메인 보고서: `/reports` 1개 경로
- ⚠️ 실험 보고서: `lab/*/reports` 다중 경로 (구조 불규칙)
- ✅ 파일명 규칙: `{prefix}-{scenario}_{timeframe}_{stage}_report.json`
- ✅ Provider 구분: `op-` (OpenAI) / `cl-` (Claude/Anthropic)

---

## 2. 피드백 반영: 구체적 설계 변경

### 2.1 [개선 1] REPORT_GLOBS — 다중 경로 안전하게 처리

**이전 방식 (문제):**
```python
REPORTS_DIR = Path("/opt/web_log_analysis/reports")  # 단일값 → lab/ 놓침
```

**수정된 방식 (glob 기반):**
```python
# config.py
REPORT_GLOBS = [
    "reports/*_stage2_report.json",
    "lab/**/reports/*_stage2_report.json",
    "lab/LLM샘플검증/*_stage2_report.json",
]

# 사용 시
from pathlib import Path
import glob

def scan_all_reports():
    all_reports = []
    for glob_pattern in REPORT_GLOBS:
        matched = Path(".").glob(glob_pattern)
        all_reports.extend(matched)
    return sorted(all_reports)
```

**효과:**
- ✅ 메인 보고서 + 실험 보고서 모두 포함
- ✅ 새 폴더 구조 추가해도 glob 수정만으로 대응
- ✅ 보고서 누락 위험 제거

---

### 2.2 [개선 2] report_id — URL 안전성 강화

**이전 방식 (문제):**
```python
@app.get("/report/{filename}")
# → 같은 파일명이 여러 폴더에 있으면 충돌
# → 예: /report/op-security_2026-04-25_..._stage2_report.json
#      경로가 없으면 404 (ambiguous)
```

**수정된 방식 (해시 기반 report_id):**
```python
# services/report_loader.py
import hashlib

class Report:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.filename = file_path.name
        self.full_path = str(file_path.resolve())
        
        # 풀 경로를 안전한 ID로 변환
        self.report_id = hashlib.sha256(
            str(file_path.resolve()).encode()
        ).hexdigest()[:16]  # 16자 축약
        
        # 파일명에서 provider/timeframe 추출
        self.provider = "openai" if filename.startswith("op-") else "anthropic"
        self.timeframe = self._extract_timeframe(filename)
        # ...

# app.py
@app.get("/report/{report_id}")
async def get_report(report_id: str):
    """report_id로 안전하게 조회"""
    report = find_report_by_id(report_id)
    if not report:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return render_template("detail.html", report=report)
```

**URL 예시:**
- Before: `/report/op-security_2026-04-25_..._stage2_report.json` (경로 노출)
- After: `/report/a3f7e2d9c1b4f0a5` (안전한 ID)

**효과:**
- ✅ 중복 파일명 충돌 방지
- ✅ 실제 파일시스템 경로 노출 안 함
- ✅ 파일 이동해도 ID 일관성 유지

---

### 2.3 [개선 3] QA 점수 스크립트 — 실제 존재하는 것 사용

**이전 방식 (오류):**
```python
# Phase 3에서 run_qa_check_production_v4.py 실행
# → 이 파일이 현재 repo에 없음 (가상의 파일명)
```

**수정된 방식 (실제 파일 기준):**
```python
# Phase 1A에서 QA 표시를 위해
from pathlib import Path
import subprocess

QA_CHECK_SCRIPT = Path("scripts/check_stage2_report_quality.py")

def run_qa_check(report_path: Path) -> dict:
    """현재 repo의 실제 check 스크립트 실행"""
    result = subprocess.run(
        [
            "python3",
            str(QA_CHECK_SCRIPT),
            "--report", str(report_path),
            "--json",  # JSON 출력
        ],
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        qa_data = json.loads(result.stdout)
        return {
            "verdict": qa_data.get("verdict"),
            "blocker_count": qa_data.get("blocker_count", 0),
            "warning_count": qa_data.get("warning_count", 0),
            "info_count": qa_data.get("info_count", 0),
            "details": qa_data.get("details", []),
        }
    else:
        return {
            "verdict": "error",
            "blocker_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "details": [{"msg": result.stderr}],
        }

# UI 표시 (report detail page)
# ▸ QA Check Results
#   Verdict: ✅ PASS (또는 ⚠️ WARNING / 🔴 BLOCKER)
#   Blockers: 0 | Warnings: 2 | Info: 1
#   Details: [...list of issues...]
```

**효과:**
- ✅ 현재 repo의 실제 스크립트와 연동
- ✅ Stage2 report 품질을 UI에서 즉시 피드백
- ✅ 분석 결과 신뢰도 한눈에 파악

---

### 2.4 [개선 4] CSS — Plain CSS만 사용 (CDN 제외)

**이전 방식 (문제):**
```html
<!-- Tailwind CDN -->
<script src="https://cdn.tailwindcss.com"></script>
<!-- → 외부 네트워크 의존 -->
```

**수정된 방식 (plain CSS):**
```
web/
├── static/
│   └── style.css  (150줄 정도, 핵심 스타일만)
└── templates/
    ├── base.html
    ├── detail.html
    └── compare.html
```

**style.css 구성:**
```css
/* web/static/style.css */

:root {
  --color-high: #dc2626;    /* Red: severity high */
  --color-medium: #f59e0b;  /* Amber: severity medium */
  --color-low: #10b981;     /* Green: severity low */
  --color-border: #e5e7eb;  /* Gray: borders */
  --color-bg: #f9fafb;      /* Gray: background */
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
  color: #333;
  background: var(--color-bg);
}

.report-list { /* 목록 화면 */ }
.report-detail { /* 상세 화면 */ }
.severity-high { background: var(--color-high); color: white; }
.severity-medium { background: var(--color-medium); color: white; }
.severity-low { background: var(--color-low); color: white; }

/* 비교 화면 */
.compare-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.qa-badge { /* QA 점수 배지 */ }
```

**효과:**
- ✅ 외부 네트워크 의존 제거
- ✅ 오프라인/내부망 환경에서도 정상 동작
- ✅ 로딩 속도 향상
- ✅ 유지보수 단순화

---

## 3. Phase 설계 변경 — Phase 1을 1A/1B로 분할

원래 계획의 "Phase 1: 보고서 뷰어"를 두 개로 쪼개면 더 안전:

```
Phase 1A: 보고서 조회 + QA 검증 (1주)
  ├─ 기능: 목록 조회 + 상세 보기 + QA 점수 표시
  ├─ URL: GET / (목록)
  │      GET /report/{report_id} (상세)
  └─ 완료 기준: JSON 보고서를 웹으로 읽고 QA 결과 표시 가능
  
Phase 1B: 모델 비교 (1주)
  ├─ 기능: OpenAI vs Anthropic 동일 시간대 비교
  ├─ URL: GET /compare/{timeframe}
  └─ 완료 기준: 두 모델의 severity/verdict 차이를 한눈에 비교 가능
  
Phase 2: 파이프라인 실행 연동 (Phase 1B 안정 후)
  ├─ 기능: 웹에서 분석 실행 + 상태 모니터링
  └─ 완료 기준: 웹 버튼으로 파이프라인 실행 + 결과 자동 반영
```

**이유:**
- ✅ Phase 1A만으로도 현재 병목(JSON 파일을 터미널로 읽기) 해결
- ✅ Phase 1B 비교는 Phase 1A가 안정된 후 추가
- ✅ 각 단계별 명확한 완료 기준

---

## 4. Phase 1A 상세 설계 (Week 1)

### 4.1 파일 구조

```
/opt/web_log_analysis/web/
├── app.py                    ← FastAPI 진입점
├── config.py                 ← 설정 (glob, host/port)
├── services/
│   ├── __init__.py
│   ├── report_loader.py      ← JSON 파일 스캔 + 파싱
│   └── qa_runner.py          ← QA 스크립트 호출
├── templates/
│   ├── base.html             ← 공통 레이아웃
│   ├── index.html            ← 보고서 목록
│   └── detail.html           ← 보고서 상세 + QA 결과
├── static/
│   └── style.css             ← Plain CSS
└── requirements.txt          ← 의존성 (fastapi, uvicorn, jinja2)
```

**총 파일: 10개 / 총 코드: ~400줄**

### 4.2 config.py (20줄)

```python
from pathlib import Path

# 보고서 경로 — 글로브 패턴으로 다중 경로 지원
REPORT_GLOBS = [
    "reports/*_stage2_report.json",
    "lab/**/reports/*_stage2_report.json",
]

# 웹 서버
HOST = "127.0.0.1"
PORT = 8000
DEBUG = False

# QA 검증 스크립트
QA_SCRIPT_PATH = Path("scripts/check_stage2_report_quality.py")
QA_TIMEOUT_SEC = 30
```

### 4.3 report_loader.py (140줄)

```python
from pathlib import Path
from typing import List, Dict, Optional
import json
import re
import hashlib
from datetime import datetime

class Report:
    """Stage2 JSON 보고서를 메모리에 로드"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.filename = file_path.name
        
        # 안전한 ID 생성 (풀 경로 기반)
        self.report_id = hashlib.sha256(
            str(file_path.resolve()).encode()
        ).hexdigest()[:16]
        
        # 파일명에서 정보 추출
        self.provider = "openai" if self.filename.startswith("op-") else "anthropic"
        self._parse_filename()
        
        # JSON 로드 + 기본값 처리
        self._load_json()
    
    def _parse_filename(self):
        """파일명 패턴: op-security_2026-04-25_18-23-00_to_18-29-00_kst_stage2_report.json"""
        # 예외 처리: 파일명 규칙이 맞지 않아도 부분 추출
        match = re.search(r'(op|cl)-(\w+?)_(\d{4}-\d{2}-\d{2}_.+?)(?:_v\d+)?_stage2_report', self.filename)
        if match:
            _, scenario, timeframe = match.groups()
            self.scenario = scenario
            self.timeframe = timeframe.replace("_to_", " to ")  # UI용 포맷
        else:
            self.scenario = "unknown"
            self.timeframe = "unknown"
    
    def _load_json(self):
        """JSON 파일 로드 + 필드 기본값"""
        try:
            data = json.loads(self.file_path.read_text())
            self.meta = data.get("meta", {})
            self.report = data.get("report", {})
            self.is_valid = True
        except Exception as e:
            self.is_valid = False
            self.error = str(e)
            self.meta = {}
            self.report = {}
    
    def get_incidents(self) -> List[Dict]:
        """notable_incidents 안전 추출"""
        return self.report.get("notable_incidents", [])
    
    def get_actions(self) -> List[Dict]:
        """recommended_actions 안전 추출"""
        return self.report.get("recommended_actions", [])
    
    def mask_sensitive_info(self) -> dict:
        """UI 표시용 마스킹"""
        return {
            "provider": self.meta.get("provider", "unknown"),
            "model": self.meta.get("selected_model", "unknown"),
            "scenario": self.scenario,
            "timeframe": self.timeframe,
            # raw_log, response_id 등은 제외
        }


class ReportLoader:
    """모든 보고서를 스캔하고 관리"""
    
    def __init__(self, glob_patterns: List[str]):
        self.glob_patterns = glob_patterns
        self.reports: Dict[str, Report] = {}
        self.scan()
    
    def scan(self):
        """glob 패턴으로 모든 보고서 스캔"""
        from pathlib import Path
        
        found_files = set()
        for pattern in self.glob_patterns:
            matched = Path(".").glob(pattern)
            found_files.update(matched)
        
        for file_path in sorted(found_files):
            try:
                report = Report(file_path)
                self.reports[report.report_id] = report
            except Exception as e:
                # 파일 로드 실패해도 계속
                print(f"Warning: Failed to load {file_path}: {e}")
    
    def get_report_by_id(self, report_id: str) -> Optional[Report]:
        """report_id로 조회"""
        return self.reports.get(report_id)
    
    def group_by_timeframe(self) -> Dict[str, Dict]:
        """시간대별 그룹핑 (OpenAI/Anthropic 쌍)"""
        groups = {}
        for report in self.reports.values():
            tf = report.timeframe
            if tf not in groups:
                groups[tf] = {"openai": None, "anthropic": None, "timeframe": tf}
            
            if report.provider == "openai":
                groups[tf]["openai"] = report
            elif report.provider == "anthropic":
                groups[tf]["anthropic"] = report
        
        return dict(sorted(groups.items(), reverse=True))
    
    def get_list_summary(self) -> Dict:
        """목록 화면용 요약"""
        grouped = self.group_by_timeframe()
        return {
            "total_count": len(self.reports),
            "timeframe_count": len(grouped),
            "groups": grouped,
        }
```

### 4.4 qa_runner.py (80줄)

```python
import subprocess
import json
from pathlib import Path
from typing import Dict, Optional

class QARunner:
    """QA 검증 스크립트 호출"""
    
    def __init__(self, script_path: Path, timeout_sec: int = 30):
        self.script_path = script_path
        self.timeout_sec = timeout_sec
    
    def run(self, report_path: Path) -> Dict:
        """
        QA 점수 실행
        
        반환:
        {
            "verdict": "PASS" | "WARNING" | "BLOCKER",
            "blocker_count": int,
            "warning_count": int,
            "info_count": int,
            "details": [...],
        }
        """
        try:
            result = subprocess.run(
                [
                    "python3",
                    str(self.script_path),
                    "--report", str(report_path),
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            
            if result.returncode == 0:
                qa_data = json.loads(result.stdout)
                return self._normalize_qa_output(qa_data)
            else:
                return self._error_response(f"QA script failed: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            return self._error_response(f"QA check timeout ({self.timeout_sec}s)")
        except FileNotFoundError:
            return self._error_response(f"QA script not found: {self.script_path}")
        except Exception as e:
            return self._error_response(str(e))
    
    def _normalize_qa_output(self, data: Dict) -> Dict:
        """QA 스크립트 출력을 UI 형식으로 정규화"""
        return {
            "verdict": data.get("verdict", "UNKNOWN"),
            "blocker_count": data.get("blocker_count", 0),
            "warning_count": data.get("warning_count", 0),
            "info_count": data.get("info_count", 0),
            "details": data.get("details", []),
            "is_error": False,
        }
    
    def _error_response(self, msg: str) -> Dict:
        return {
            "verdict": "ERROR",
            "blocker_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "details": [{"msg": msg}],
            "is_error": True,
        }
```

### 4.5 app.py (80줄)

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from config import HOST, PORT, REPORT_GLOBS, QA_SCRIPT_PATH, QA_TIMEOUT_SEC
from services.report_loader import ReportLoader
from services.qa_runner import QARunner

# 초기화
app = FastAPI(title="Security Intelligence — Report Viewer")
report_loader = ReportLoader(REPORT_GLOBS)
qa_runner = QARunner(QA_SCRIPT_PATH, QA_TIMEOUT_SEC)

# 템플릿 + 정적 파일
templates = Environment(loader=FileSystemLoader("templates"))
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """보고서 목록 화면"""
    summary = report_loader.get_list_summary()
    template = templates.get_template("index.html")
    return template.render(summary=summary)


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def get_report(report_id: str):
    """보고서 상세 + QA 결과"""
    report = report_loader.get_report_by_id(report_id)
    if not report:
        return "<h1>Report not found</h1>", 404
    
    # QA 실행
    qa_result = qa_runner.run(report.file_path)
    
    template = templates.get_template("detail.html")
    return template.render(
        report=report,
        qa_result=qa_result,
        incidents=report.get_incidents(),
        actions=report.get_actions(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=False,
    )
```

### 4.6 HTML 템플릿 구성

**base.html (50줄):**
```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Security Intelligence{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <header>
        <h1>Security Intelligence Console</h1>
        <nav>
            <a href="/">Reports</a>
        </nav>
    </header>
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <small>Phase 1A: Report Viewer | localhost only</small>
    </footer>
</body>
</html>
```

**index.html (60줄):**
```html
{% extends "base.html" %}

{% block title %}Report List{% endblock %}

{% block content %}
<section class="report-list">
    <h2>보고서 목록</h2>
    <p>Total: {{ summary.total_count }} reports | Timeframes: {{ summary.timeframe_count }}</p>
    
    {% for timeframe, group in summary.groups.items() %}
    <div class="timeframe-group">
        <h3>📅 {{ timeframe }}</h3>
        
        {% if group.openai %}
        <div class="report-card provider-openai">
            <h4>OpenAI</h4>
            <p>Model: {{ group.openai.get_meta().selected_model }}</p>
            <p>Incidents: {{ group.openai.get_incidents() | length }}</p>
            <a href="/report/{{ group.openai.report_id }}">상세보기</a>
        </div>
        {% endif %}
        
        {% if group.anthropic %}
        <div class="report-card provider-anthropic">
            <h4>Anthropic</h4>
            <p>Model: {{ group.anthropic.get_meta().selected_model }}</p>
            <p>Incidents: {{ group.anthropic.get_incidents() | length }}</p>
            <a href="/report/{{ group.anthropic.report_id }}">상세보기</a>
        </div>
        {% endif %}
    </div>
    {% endfor %}
</section>
{% endblock %}
```

**detail.html (100줄):**
```html
{% extends "base.html" %}

{% block title %}{{ report.filename }}{% endblock %}

{% block content %}
<section class="report-detail">
    <h2>{{ report.filename }}</h2>
    
    <!-- QA 점수 -->
    <div class="qa-section">
        <h3>QA Check Results</h3>
        <div class="qa-badge verdict-{{ qa_result.verdict | lower }}">
            {{ qa_result.verdict }}
        </div>
        <p>
            Blockers: {{ qa_result.blocker_count }} |
            Warnings: {{ qa_result.warning_count }} |
            Info: {{ qa_result.info_count }}
        </p>
        
        {% if qa_result.details %}
        <ul>
            {% for detail in qa_result.details %}
            <li class="severity-{{ detail.severity | default('info') }}">
                {{ detail.msg }}
            </li>
            {% endfor %}
        </ul>
        {% endif %}
    </div>
    
    <!-- 보고서 내용 -->
    <div class="report-content">
        <h3>Overall Assessment</h3>
        <p>{{ report.report.get('overall_assessment', 'N/A') }}</p>
        
        <h3>Notable Incidents ({{ incidents | length }}건)</h3>
        <table>
            <tr>
                <th>Severity</th>
                <th>Verdict</th>
                <th>Why It Matters</th>
            </tr>
            {% for incident in incidents %}
            <tr>
                <td>
                    <span class="severity-{{ incident.get('severity', 'low') | lower }}">
                        {{ incident.get('severity', 'unknown') | upper }}
                    </span>
                </td>
                <td>{{ incident.get('verdict', 'unknown') }}</td>
                <td>{{ incident.get('why_it_matters', '-') }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <h3>Recommended Actions</h3>
        <ul>
            {% for action in actions %}
            <li class="priority-{{ action.get('priority', 'p3') | lower }}">
                {{ action.get('action', '') }}
            </li>
            {% endfor %}
        </ul>
    </div>
</section>
{% endblock %}
```

### 4.7 style.css (120줄)

```css
:root {
  --color-high: #dc2626;
  --color-medium: #f59e0b;
  --color-low: #10b981;
  --color-border: #e5e7eb;
  --color-bg: #f9fafb;
  --color-text: #333;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
  margin: 0;
  padding: 0;
}

header {
  background: #fff;
  border-bottom: 1px solid var(--color-border);
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.report-list { }
.timeframe-group {
  margin: 20px 0;
  padding: 15px;
  background: #fff;
  border-left: 4px solid var(--color-border);
}

.report-card {
  padding: 15px;
  background: #f3f4f6;
  border-radius: 4px;
  margin: 10px 0;
}

.provider-openai { border-left: 4px solid #3b82f6; }
.provider-anthropic { border-left: 4px solid #a855f7; }

.severity-high { 
  color: white;
  background: var(--color-high);
  padding: 2px 6px;
  border-radius: 2px;
  font-weight: bold;
}

.severity-medium {
  color: white;
  background: var(--color-medium);
  padding: 2px 6px;
  border-radius: 2px;
}

.severity-low {
  color: white;
  background: var(--color-low);
  padding: 2px 6px;
  border-radius: 2px;
}

.qa-badge {
  display: inline-block;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: bold;
  margin: 10px 0;
}

.verdict-pass {
  background: var(--color-low);
  color: white;
}

.verdict-warning {
  background: var(--color-medium);
  color: white;
}

.verdict-blocker {
  background: var(--color-high);
  color: white;
}

.verdict-error {
  background: #6b7280;
  color: white;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 15px 0;
}

th, td {
  text-align: left;
  padding: 10px;
  border-bottom: 1px solid var(--color-border);
}

th {
  background: #f3f4f6;
  font-weight: bold;
}

a {
  color: #3b82f6;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}
```

---

## 5. Phase 1A 실행 방법

### 5.1 사전 준비

```bash
cd /opt/web_log_analysis

# 가상환경 활성화
source .venv/bin/activate

# 의존성 설치 (한 번만)
pip install fastapi uvicorn jinja2
```

### 5.2 폴더 및 파일 생성

```bash
# 폴더 생성
mkdir -p web/services web/templates web/static

# 위의 4.3~4.7 코드를 각 파일에 저장
# (별도 스크립트로 자동화 가능)
```

### 5.3 서버 실행

```bash
cd /opt/web_log_analysis

# 포그라운드에서 실행 (개발용)
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload

# 백그라운드에서 실행 (운영용)
nohup python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 > web/server.log 2>&1 &
```

### 5.4 브라우저 접속

```
http://127.0.0.1:8000          ← 보고서 목록
http://127.0.0.1:8000/report/a3f7e2d9c1b4f0a5  ← 보고서 상세 (ID는 실제값)
```

### 5.5 원격 접속 (Windows에서 LLM 서버 연결)

```powershell
# Windows PowerShell
ssh -L 8000:127.0.0.1:8000 user@192.168.56.110

# 그 후 Windows 브라우저
http://localhost:8000
```

---

## 6. Phase 1B 설계 (Week 2)

Phase 1A가 안정되면, 비교 기능 추가:

### 6.1 추가 라우트

```python
@app.get("/compare/{timeframe}", response_class=HTMLResponse)
async def compare_models(timeframe: str):
    """동일 시간대의 OpenAI vs Anthropic 비교"""
    group = report_loader.get_group_by_timeframe(timeframe)
    if not group or not (group.openai and group.anthropic):
        return "<h1>No comparison available</h1>", 404
    
    # 비교 분석
    comparison = analyze_comparison(group.openai, group.anthropic)
    
    template = templates.get_template("compare.html")
    return template.render(
        openai=group.openai,
        anthropic=group.anthropic,
        comparison=comparison,
    )
```

### 6.2 비교 분석 로직

```python
def analyze_comparison(op_report: Report, cl_report: Report) -> Dict:
    """두 보고서의 차이 분석"""
    op_incidents = op_report.get_incidents()
    cl_incidents = cl_report.get_incidents()
    
    # Severity delta 찾기
    severity_deltas = []
    for i, (op_inc, cl_inc) in enumerate(zip(op_incidents, cl_incidents)):
        if op_inc.get("severity") != cl_inc.get("severity"):
            severity_deltas.append({
                "index": i,
                "op_severity": op_inc.get("severity"),
                "cl_severity": cl_inc.get("severity"),
            })
    
    return {
        "severity_deltas": severity_deltas,
        "op_incident_count": len(op_incidents),
        "cl_incident_count": len(cl_incidents),
    }
```

### 6.3 compare.html (150줄)

좌우 분할 레이아웃으로 두 보고서를 나란히 표시:

```html
<div class="compare-layout">
    <div class="compare-panel openai">
        <h2>OpenAI</h2>
        <!-- 왼쪽: OpenAI 보고서 상세 -->
    </div>
    <div class="compare-panel anthropic">
        <h2>Anthropic</h2>
        <!-- 오른쪽: Anthropic 보고서 상세 -->
    </div>
</div>

<!-- Severity Delta 하이라이트-->
<section class="delta-section">
    <h3>Severity Differences</h3>
    {% for delta in comparison.severity_deltas %}
    <div class="delta-item">
        Incident #{{ delta.index }}:
        OpenAI <span class="severity-{{ delta.op_severity }}">{{ delta.op_severity }}</span>
        vs
        Anthropic <span class="severity-{{ delta.cl_severity }}">{{ delta.cl_severity }}</span>
    </div>
    {% endfor %}
</section>
```

---

## 7. 보안 및 운영 규칙

### 7.1 데이터 보호

| 규칙 | 실행 방식 |
|------|---------|
| IP 마스킹 | 192.168.56.*** 표시 (last octet 제외) |
| API 키 노출 방지 | config/llm.env 절대 읽지 않음 |
| localhost만 바인딩 | `HOST = "127.0.0.1"` (고정) |
| 읽기 전용 접근 | reports/ 폴더 쓰기 금지 |

### 7.2 보고서 해석 유지

Stage2 보고서의 표현을 UI에서 바꾸지 않음:
- "가능성이 있습니다" → "가능성이 있습니다" (그대로)
- "침해 성공은 확인되지 않음" → "침해 성공은 확인되지 않음" (그대로)
- severity "medium" → 배지로 "MEDIUM" (수정 금지)

---

## 8. 성공 기준

### Phase 1A 완료 기준

- ✅ 8개 보고서 모두 웹에서 조회 가능
- ✅ QA 점수 표시 (blocker/warning/info 카운트)
- ✅ 파일명 규칙이 안 맞는 보고서도 부분 로드
- ✅ 3초 이내 페이지 로드
- ✅ localhost 접속 정상, 외부 접근 불가

### Phase 1B 완료 기준

- ✅ OpenAI vs Anthropic 동일 시간대 비교 화면
- ✅ Severity 차이 하이라이트
- ✅ 좌우 분할 레이아웃 정상

### 전체 성공

**현재 (터미널 기반):**
```bash
cat reports/op-security_2026-04-25_..._stage2_report.json | python3 -m json.tool | less
# 터미널 1에서 OpenAI 읽기 → 터미널 2에서 Claude 읽기 → 눈으로 대조 (10분)
```

**Phase 1A 후:**
```
브라우저 `http://localhost:8000/report/{id}` 클릭 → 즉시 조회 (3초)
QA 결과 바로 확인
```

**Phase 1B 후:**
```
브라우저 `http://localhost:8000/compare/2026-04-25_18-23~18-29` 
→ OpenAI vs Claude 나란히 비교 (3초)
```

---

## 9. 주의사항 및 제약

### 9.1 Phase 1A/1B 범위

**포함하지 않는 것:**
- ❌ 파이프라인 실행 버튼 (Phase 2)
- ❌ 회귀 검증 버튼 (Phase 2)
- ❌ 모델 선택 드롭다운 (Phase 2)
- ❌ 보고서 업로드 (Phase 2)
- ❌ 검색/필터 (Phase 2)
- ❌ DB 또는 이력 저장 (Phase 3)
- ❌ 알림/대시보드 (Phase 3+)

### 9.2 파일 배치의 제약

- `lab/` 하위 보고서 경로가 불규칙할 수 있음
  - 해결: glob 패턴으로 유연하게 대응
- 파일명 규칙을 100% 따르지 않는 보고서 존재 가능
  - 해결: 파싱 실패해도 파일명 기반으로 부분 로드

---

## 10. 다음 행동

1. **현재 보고서 확인** (사전 검증)
   ```bash
   find /opt/web_log_analysis -name "*_stage2_report.json" | wc -l
   ls /opt/web_log_analysis/reports/*_stage2_report.json
   find /opt/web_log_analysis/lab -name "*_stage2_report.json"
   ```

2. **FastAPI 설치 가능 확인**
   ```bash
   cd /opt/web_log_analysis
   source .venv/bin/activate
   pip install fastapi uvicorn jinja2 --dry-run
   ```

3. **check_stage2_report_quality.py 확인**
   ```bash
   python scripts/check_stage2_report_quality.py --help
   ```

4. **Phase 1A 코드 작성** (4.3~4.7)

5. **로컬 테스트**
   ```bash
   python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
   ```

6. **브라우저 확인**
   ```
   http://127.0.0.1:8000
   ```

---

## 요약

```
목표: JSON 보고서를 웹에서 읽고 QA 결과 확인 (Phase 1A)
      + 모델 비교 (Phase 1B)

기술: FastAPI + Jinja2 + Plain CSS (CDN X)

파일 수: 10개 (Phase 1A) / +1 (compare.html for 1B)

코드량: ~400줄 (Phase 1A) / +150줄 (1B)

시간: 1주 (1A) + 1주 (1B) = 2주

핵심 개선사항:
  1. REPORT_GLOBS (다중 경로 안전)
  2. report_id (hash 기반 URL 안전)
  3. check_stage2_report_quality.py (실제 스크립트)
  4. Plain CSS (CDN 제거)

보안:
  - localhost only (127.0.0.1 바인드)
  - 읽기 전용 (쓰기 금지)
  - IP 마스킹
  - API 키 노출 금지
```

---

**작성 완료. Phase 1A 구현 준비 완료.**

