#!/usr/bin/env bash
set -euo pipefail

# Generate an observation matrix draft from collected Apache observability logs.
#
# Inputs expected under a run directory:
#   raw/app_security.filtered.log
#   raw/app_error.by_request_id.log
#   raw/scenario_counts.tsv
#   client/summary.tsv                 # optional
#
# Output:
#   observation_matrix.autofill.md      # default, safe non-destructive draft
#
# The matrix distinguishes app/PHP notice-style error-log context from real
# warning/error context. This prevents benign PHP error_log() notice events from
# making every scenario look like an Apache/PHP error.

SCRIPT_NAME="$(basename "$0")"

RUN_ID=""
RUN_DIR=""
OUTPUT_ROOT="lab/observability/runs"
OUTPUT_FILE=""
FORCE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/summarize_observability_run.sh --run-id ID [options]
  scripts/summarize_observability_run.sh --run-dir DIR [options]

Required, one of:
  --run-id ID
      Run identifier. Uses <output-root>/<run-id> as run directory.

  --run-dir DIR
      Explicit run directory.

Options:
  --output-root DIR
      Root directory for runs when --run-id is used.
      Default: lab/observability/runs

  --output FILE
      Output markdown path. Default: <run-dir>/observation_matrix.autofill.md

  --force
      Overwrite existing output file.

Examples:
  scripts/summarize_observability_run.sh --run-id obs_php_sample_002 --force
EOF
}

log() {
  printf '[%s] %s\n' "${SCRIPT_NAME}" "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

sanitize_for_path() {
  local value="$1"
  value="${value//[^A-Za-z0-9._-]/_}"
  printf '%s' "${value}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --run-id)
        RUN_ID="${2:-}"
        shift 2
        ;;
      --run-dir)
        RUN_DIR="${2:-}"
        shift 2
        ;;
      --output-root)
        OUTPUT_ROOT="${2:-}"
        shift 2
        ;;
      --output)
        OUTPUT_FILE="${2:-}"
        shift 2
        ;;
      --force)
        FORCE=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "unknown argument: $1"
        ;;
    esac
  done
}

resolve_run_dir() {
  if [[ -n "${RUN_ID}" && -n "${RUN_DIR}" ]]; then
    fail "use either --run-id or --run-dir, not both"
  fi
  if [[ -z "${RUN_ID}" && -z "${RUN_DIR}" ]]; then
    fail "one of --run-id or --run-dir is required"
  fi

  if [[ -n "${RUN_ID}" ]]; then
    RUN_ID="$(sanitize_for_path "${RUN_ID}")"
    RUN_DIR="${OUTPUT_ROOT}/${RUN_ID}"
  else
    RUN_DIR="${RUN_DIR%/}"
    RUN_ID="$(basename "${RUN_DIR}")"
  fi

  if [[ -z "${OUTPUT_FILE}" ]]; then
    OUTPUT_FILE="${RUN_DIR}/observation_matrix.autofill.md"
  fi
}

main() {
  parse_args "$@"
  resolve_run_dir

  [[ -d "${RUN_DIR}" ]] || fail "run directory does not exist: ${RUN_DIR}"

  local security_log="${RUN_DIR}/raw/app_security.filtered.log"
  local error_log="${RUN_DIR}/raw/app_error.by_request_id.log"
  local scenario_counts="${RUN_DIR}/raw/scenario_counts.tsv"
  local client_summary="${RUN_DIR}/client/summary.tsv"

  [[ -f "${security_log}" ]] || fail "missing ${security_log}; run collect_observability_server_logs.sh first"

  if [[ -e "${OUTPUT_FILE}" && "${FORCE}" -ne 1 ]]; then
    fail "output already exists: ${OUTPUT_FILE}; use --force to overwrite"
  fi

  mkdir -p "$(dirname "${OUTPUT_FILE}")"

  python3 - "$RUN_ID" "$RUN_DIR" "$security_log" "$error_log" "$scenario_counts" "$client_summary" "$OUTPUT_FILE" <<'PY'
import collections
import datetime as dt
import os
import re
import sys
from pathlib import Path

run_id, run_dir, security_log, error_log, scenario_counts, client_summary, output_file = sys.argv[1:]

SCENARIOS = [f"S{i:02d}" for i in range(1, 16)]
SCENARIO_NAMES = {
    "S01": "normal_main",
    "S02": "static_css",
    "S03": "static_js",
    "S04": "query_search",
    "S05": "not_found",
    "S06": "forbidden_or_sensitive_path",
    "S07": "login_get",
    "S08": "login_post",
    "S09": "upload_like_post",
    "S10": "slow_or_large_request",
    "S11": "server_error",
    "S12": "scanner_burst",
    "S13": "sqli_like",
    "S14": "xss_like",
    "S15": "traversal_like",
}

KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
SCENARIO_RE = re.compile(r'obs-test/(S\d{2})\s+run=([^"\s]+)')
ERROR_RID_RE = re.compile(r'\[request_id:([^\]]+)\]')
ERROR_LEVEL_RE = re.compile(r'\[log_level:([^\]]+)\]')
ERROR_MODULE_RE = re.compile(r'\[module_name:([^\]]+)\]')

NOTICE_LEVELS = {"trace1", "trace2", "trace3", "trace4", "trace5", "trace6", "trace7", "trace8", "debug", "info", "notice"}
WARN_LEVELS = {"warn", "warning"}
ERROR_LEVELS = {"error", "crit", "critical", "alert", "emerg", "emergency"}
WARN_OR_ABOVE = WARN_LEVELS | ERROR_LEVELS


def strip_quotes(value: str) -> str:
    if value is None:
        return ""
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def parse_kv_line(line: str) -> dict:
    result = {}
    for m in KV_RE.finditer(line):
        result[m.group(1)] = strip_quotes(m.group(2))
    return result


def md_escape(value) -> str:
    if value is None:
        return ""
    s = str(value)
    s = s.replace("|", "\\|")
    s = s.replace("\n", " ")
    return s


def compact_counts(values):
    c = collections.Counter(str(v) for v in values if str(v) != "")
    if not c:
        return ""
    return ", ".join(f"{k}x{v}" if v > 1 else k for k, v in sorted(c.items()))


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def classify_levels(counter: collections.Counter) -> dict:
    notice = sum(counter.get(level, 0) for level in NOTICE_LEVELS)
    warn = sum(counter.get(level, 0) for level in WARN_LEVELS)
    error = sum(counter.get(level, 0) for level in ERROR_LEVELS)
    total = sum(counter.values())
    return {
        "total": total,
        "notice": notice,
        "warn": warn,
        "error": error,
        "warn_or_above": warn + error,
        "summary": compact_counts([level for level, count in counter.items() for _ in range(count)]),
    }

security_rows = []
with open(security_log, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        row = parse_kv_line(line)
        ua = row.get("user_agent", "")
        m = SCENARIO_RE.search(ua)
        if m:
            row["scenario"] = m.group(1)
            row["run_marker"] = m.group(2)
        else:
            row["scenario"] = "UNKNOWN"
            row["run_marker"] = ""
        row["raw_log"] = line
        security_rows.append(row)

error_lines_by_request = collections.defaultdict(list)
error_levels_by_request = collections.defaultdict(collections.Counter)
error_modules_by_request = collections.defaultdict(collections.Counter)
if os.path.exists(error_log):
    with open(error_log, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            rid_m = ERROR_RID_RE.search(line)
            if not rid_m:
                continue
            rid = rid_m.group(1)
            if not rid or rid == "-":
                continue
            level_m = ERROR_LEVEL_RE.search(line)
            module_m = ERROR_MODULE_RE.search(line)
            level = (level_m.group(1) if level_m else "unknown").strip().lower()
            module = (module_m.group(1) if module_m else "unknown").strip().lower()
            error_lines_by_request[rid].append(line)
            error_levels_by_request[rid][level] += 1
            error_modules_by_request[rid][module] += 1

client_by_scenario = collections.defaultdict(list)
if os.path.exists(client_summary):
    with open(client_summary, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < len(header):
                parts += [""] * (len(header) - len(parts))
            d = dict(zip(header, parts))
            scenario = d.get("scenario", "")
            if scenario:
                client_by_scenario[scenario].append(d)

rows_by_scenario = collections.defaultdict(list)
for row in security_rows:
    rows_by_scenario[row.get("scenario", "UNKNOWN")].append(row)


def scenario_error_stats(request_ids):
    levels = collections.Counter()
    modules = collections.Counter()
    line_count = 0
    for rid in request_ids:
        line_count += len(error_lines_by_request.get(rid, []))
        levels.update(error_levels_by_request.get(rid, {}))
        modules.update(error_modules_by_request.get(rid, {}))
    classified = classify_levels(levels)
    classified["line_count"] = line_count
    classified["modules"] = compact_counts([module for module, count in modules.items() for _ in range(count)])
    return classified


def infer_evidence_level(scenario: str, rows: list, err_stats: dict) -> str:
    if not rows:
        return "O0"
    if scenario == "S11":
        return "O2" if err_stats["warn_or_above"] > 0 else "O1"
    if scenario in {"S08", "S09"}:
        return "O1/O4"
    return "O1"


def notes_for(scenario: str, rows: list, err_stats: dict) -> str:
    if not rows:
        return "not observed"
    if scenario == "S08":
        return "POST observed; success/failure requires app or DB audit"
    if scenario == "S09":
        return "multipart/upload-like POST observed; stored result requires app or DB audit"
    if scenario == "S11":
        if err_stats["warn_or_above"] > 0:
            return "500 observed; warn/error-level Apache/PHP context linked"
        if err_stats["notice"] > 0:
            return "500 observed; only notice-level context linked"
        return "500 observed; no related error context found"
    if scenario == "S12":
        return "burst pattern observed via repeated User-Agent marker"
    if scenario == "S13":
        return "SQLi-like query observed; no success inference"
    if scenario == "S14":
        return "XSS-like query observed; no browser execution inference"
    if scenario == "S15":
        return "traversal-like query observed; no file-read success inference"
    if err_stats["notice"] > 0 and err_stats["warn_or_above"] == 0:
        return "observed in Apache request metadata; notice-level app/PHP context only"
    return "observed in Apache request metadata"

matrix_lines = []
for scenario in SCENARIOS:
    rows = rows_by_scenario.get(scenario, [])
    request_ids = [r.get("request_id", "") for r in rows]
    err_stats = scenario_error_stats([rid for rid in request_ids if rid])
    client_rows = client_by_scenario.get(scenario, [])

    methods = compact_counts(r.get("method", "") for r in rows)
    uris = compact_counts(r.get("uri", "") for r in rows)
    statuses = compact_counts(r.get("status_code", "") for r in rows)
    handlers = compact_counts(r.get("handler", "") for r in rows)
    req_ct = compact_counts(r.get("req_content_type", "") for r in rows if r.get("req_content_type") not in {"", "-"})
    resp_ct = compact_counts(r.get("resp_content_type", "") for r in rows if r.get("resp_content_type") not in {"", "-"})

    request_summary = "; ".join(x for x in [methods, uris] if x) or "-"
    actual_status = statuses or compact_counts(c.get("http_code", "") for c in client_rows)

    line = {
        "scenario": f"{scenario} {SCENARIO_NAMES[scenario]}",
        "request_summary": request_summary,
        "actual_status": actual_status,
        "observed_in_security": yes_no(bool(rows)),
        "observed_in_error": yes_no(err_stats["warn_or_above"] > 0),
        "error_level_summary": err_stats["summary"],
        "notice_count": str(err_stats["notice"]),
        "warn_or_error_count": str(err_stats["warn_or_above"]),
        "observed_in_app": "n/a",
        "observed_in_waf": "n/a",
        "evidence_level": infer_evidence_level(scenario, rows, err_stats),
        "notes": notes_for(scenario, rows, err_stats),
        "handler": handlers,
        "req_content_type": req_ct,
        "resp_content_type": resp_ct,
        "error_count": str(err_stats["line_count"]),
        "count": str(len(rows)),
        "error_modules": err_stats["modules"],
    }
    matrix_lines.append(line)

field_names = [
    "log_schema", "log_time", "request_id", "error_link_id", "vhost", "server_name",
    "server_port", "local_ip", "src_ip", "peer_ip", "method", "raw_request", "uri",
    "query_string", "protocol", "status_code", "original_status_code", "response_body_bytes",
    "in_bytes", "out_bytes", "total_bytes", "duration_us", "ttfb_us", "keepalive_count",
    "connection_status", "handler", "req_content_type", "req_content_length", "resp_content_type",
    "location", "referer", "origin", "user_agent", "host", "x_forwarded_for", "x_real_ip",
    "forwarded",
]
field_present = {name: any(name in row and row.get(name, "") != "" for row in security_rows) for name in field_names}
level_counts = collections.Counter(item["evidence_level"] for item in matrix_lines)

out = []
out.append("# Observation Matrix Autofill Draft")
out.append("")
out.append(f"- run_id: `{run_id}`")
out.append(f"- run_dir: `{run_dir}`")
out.append(f"- generated_at_utc: `{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z`")
out.append(f"- source_security_log: `{security_log}`")
out.append(f"- source_error_log: `{error_log}`")
out.append("")
out.append("> Review this draft before copying sections into `observation_matrix.md`.")
out.append("")

out.append("## 1. Scenario Result Matrix")
out.append("")
out.append("| scenario | count | request summary | actual status | observed in security | observed in warn/error | error levels | evidence level | notes |")
out.append("|---|---:|---|---|---|---|---|---|---|")
for item in matrix_lines:
    safe = {k: md_escape(v) for k, v in item.items()}
    out.append(
        "| {scenario} | {count} | {request_summary} | {actual_status} | {observed_in_security} | {observed_in_error} | {error_level_summary} | {evidence_level} | {notes} |".format(**safe)
    )
out.append("")

out.append("## 2. Evidence Level Summary")
out.append("")
out.append("| evidence level | count | notes |")
out.append("|---|---:|---|")
for level in ["O0", "O1", "O1/O4", "O2", "O3", "O4"]:
    out.append(f"| {level} | {level_counts.get(level, 0)} |  |")
out.append("")

out.append("## 3. Related Error-Level Summary")
out.append("")
out.append("| scenario | notice count | warn/error count | modules | interpretation |")
out.append("|---|---:|---:|---|---|")
for item in matrix_lines:
    interpretation = "warn/error context" if int(item["warn_or_error_count"]) > 0 else ("notice-only context" if int(item["notice_count"]) > 0 else "none")
    out.append(f"| {md_escape(item['scenario'])} | {item['notice_count']} | {item['warn_or_error_count']} | {md_escape(item['error_modules'])} | {interpretation} |")
out.append("")

out.append("## 4. Field Observation Checklist")
out.append("")
out.append("| field | observed | notes |")
out.append("|---|---:|---|")
for name in field_names:
    out.append(f"| `{name}` | {yes_no(field_present[name])} |  |")
out.append("")

out.append("## 5. Per-Scenario Details")
out.append("")
for scenario in SCENARIOS:
    rows = rows_by_scenario.get(scenario, [])
    out.append(f"### {scenario} {SCENARIO_NAMES[scenario]}")
    out.append("")
    if not rows:
        out.append("- observed: no")
        out.append("")
        continue
    for idx, row in enumerate(rows, 1):
        rid = row.get("request_id", "")
        row_levels = classify_levels(error_levels_by_request.get(rid, collections.Counter()))
        out.append(f"- event {idx}")
        out.append(f"  - request_id: `{md_escape(rid)}`")
        out.append(f"  - method: `{md_escape(row.get('method', ''))}`")
        out.append(f"  - uri: `{md_escape(row.get('uri', ''))}`")
        out.append(f"  - query_string: `{md_escape(row.get('query_string', ''))}`")
        out.append(f"  - status_code: `{md_escape(row.get('status_code', ''))}`")
        out.append(f"  - handler: `{md_escape(row.get('handler', ''))}`")
        out.append(f"  - req_content_type: `{md_escape(row.get('req_content_type', ''))}`")
        out.append(f"  - resp_content_type: `{md_escape(row.get('resp_content_type', ''))}`")
        out.append(f"  - related_error_count: `{row_levels['total']}`")
        out.append(f"  - related_notice_count: `{row_levels['notice']}`")
        out.append(f"  - related_warn_or_error_count: `{row_levels['warn_or_above']}`")
        out.append(f"  - related_error_levels: `{md_escape(row_levels['summary'])}`")
    out.append("")

out.append("## 6. Prohibited Inferences Check")
out.append("")
out.append("| guardrail | status | notes |")
out.append("|---|---|---|")
out.append("| No success inference from status_code=200 | pass | Needs manual review in final report |")
out.append("| No exposure inference from response size only | pass | Needs manual review in final report |")
out.append("| No login success inference from POST only | pass | S08 remains O1/O4 |")
out.append("| No upload success inference from POST only | pass | S09 remains O1/O4 |")
out.append("| No compromise inference from WAF match only | n/a | No WAF context in this run |")
out.append("| No attacker IP assertion from x_forwarded_for only | pass | x_forwarded_for is logged as observed header only |")
out.append("")

Path(output_file).write_text("\n".join(out) + "\n", encoding="utf-8")
PY

  log "wrote: ${OUTPUT_FILE}"
}

main "$@"
