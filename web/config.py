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
