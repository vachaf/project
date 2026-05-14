#!/usr/bin/env bash
set -euo pipefail

# Initialize note/matrix directories for an Apache app observability run.
#
# Purpose:
#   Create the standard run artifact skeleton after or before executing
#   scripts/run_observability_scenarios.sh.
#
# Related docs:
#   - docs/design/99_apache_app_observability_comparison_plan.md
#   - lab/observability/scenario_catalog.md
#   - lab/observability/observation_matrix_template.md

SCRIPT_NAME="$(basename "$0")"

RUN_ID=""
RUN_DIR=""
OUTPUT_ROOT="lab/observability/runs"
TARGET_BASE_URL=""
TARGET_APP=""
TOPOLOGY=""
APP_STACK=""
LOG_FORMAT_VERSION="security_db_aligned_v1"
SCENARIO_CATALOG_VERSION="apache_observability_s01_s15_v1"
FORCE=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  scripts/init_observability_run_notes.sh [--run-id ID | --run-dir DIR] [options]

Required, one of:
  --run-id ID
      Run identifier. The run directory becomes <output-root>/<run-id>.

  --run-dir DIR
      Explicit run directory to initialize.

Options:
  --output-root DIR
      Root directory for runs when --run-id is used.
      Default: lab/observability/runs

  --target-base-url URL
      Target base URL to record in notes/metadata.

  --target-app NAME
      App name to record. Example: php_sample, opencart, juiceshop.

  --topology VALUE
      Topology label. Example: apache_php, apache_php_fpm, apache_reverse_proxy_node.

  --app-stack VALUE
      App/runtime stack. Example: Apache+PHP, Apache+PHP-FPM+OpenCart.

  --log-format-version VALUE
      Log format version label. Default: security_db_aligned_v1

  --scenario-catalog-version VALUE
      Scenario catalog version. Default: apache_observability_s01_s15_v1

  --force
      Overwrite existing generated note/template files. Raw/exported directories are preserved.

  --dry-run
      Print planned operations without writing files.

Examples:
  scripts/init_observability_run_notes.sh \
    --run-id obs_php_sample_001 \
    --target-base-url http://apache-log-test.local \
    --target-app php_sample \
    --topology apache_php \
    --app-stack 'Apache+PHP'

  scripts/init_observability_run_notes.sh \
    --run-dir lab/observability/runs/obs_php_sample_001
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
      --target-base-url)
        TARGET_BASE_URL="${2:-}"
        shift 2
        ;;
      --target-app)
        TARGET_APP="${2:-}"
        shift 2
        ;;
      --topology)
        TOPOLOGY="${2:-}"
        shift 2
        ;;
      --app-stack)
        APP_STACK="${2:-}"
        shift 2
        ;;
      --log-format-version)
        LOG_FORMAT_VERSION="${2:-}"
        shift 2
        ;;
      --scenario-catalog-version)
        SCENARIO_CATALOG_VERSION="${2:-}"
        shift 2
        ;;
      --force)
        FORCE=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
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

require_repo_root_files() {
  [[ -f "lab/observability/observation_matrix_template.md" ]] || \
    fail "missing template: lab/observability/observation_matrix_template.md"
  [[ -f "lab/observability/scenario_catalog.md" ]] || \
    fail "missing scenario catalog: lab/observability/scenario_catalog.md"
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
}

write_file() {
  local path="$1"
  local content="$2"

  if [[ -e "${path}" && "${FORCE}" -ne 1 ]]; then
    log "skip existing file: ${path}"
    return 0
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "would write: ${path}"
    return 0
  fi

  mkdir -p "$(dirname "${path}")"
  printf '%s\n' "${content}" > "${path}"
  log "wrote: ${path}"
}

copy_template() {
  local src="$1"
  local dst="$2"

  if [[ -e "${dst}" && "${FORCE}" -ne 1 ]]; then
    log "skip existing file: ${dst}"
    return 0
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "would copy: ${src} -> ${dst}"
    return 0
  fi

  mkdir -p "$(dirname "${dst}")"
  cp "${src}" "${dst}"
  log "copied: ${dst}"
}

ensure_dir() {
  local path="$1"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "would mkdir: ${path}"
    return 0
  fi
  mkdir -p "${path}"
}

now_utc() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

metadata_content() {
  cat <<EOF
RUN_ID=${RUN_ID}
TARGET_BASE_URL=${TARGET_BASE_URL}
TARGET_APP=${TARGET_APP}
TOPOLOGY=${TOPOLOGY}
APP_STACK=${APP_STACK}
LOG_FORMAT_VERSION=${LOG_FORMAT_VERSION}
SCENARIO_CATALOG_VERSION=${SCENARIO_CATALOG_VERSION}
INITIALIZED_AT_UTC=$(now_utc)
EOF
}

raw_readme_content() {
  cat <<'EOF'
# Raw Server Logs

Copy server-side logs for this run here.

Recommended files:

- app_security.log
- app_access.log
- app_error.log
- apache_log_shipper.log
- app_runtime.log
- php_fpm.log
- modsec_audit.log
- auth.log
- ufw.log
- fail2ban.log

Guidelines:

- Preserve original lines where possible.
- Do not edit raw logs in place.
- If logs include secrets or personal data, store a sanitized copy separately and document the sanitization in notes.md.
EOF
}

exported_readme_content() {
  cat <<'EOF'
# Exported/Normalized Data

Place exported DB rows or normalized JSON/CSV artifacts here.

Recommended files:

- security.json
- access.json
- error.json
- app_runtime.json
- modsec.json
- system_context.json

Guidelines:

- Keep exports scoped to this run marker where possible.
- Preserve timestamps and request IDs.
- Do not infer relationships in exported data; relationship building belongs in analysis/prepare steps.
EOF
}

client_readme_content() {
  cat <<EOF
# Client Artifacts

This directory is used by scripts/run_observability_scenarios.sh.

Expected files after scenario execution:

- commands.log
- summary.tsv
- responses/*.headers
- responses/*.body
- responses/*.meta
- responses/*.stderr

Run ID: ${RUN_ID}
EOF
}

notes_content() {
  cat <<EOF
# Observability Run Notes

## 1. Run Summary

| 항목 | 값 |
|---|---|
| run_id | ${RUN_ID} |
| target_base_url | ${TARGET_BASE_URL} |
| target_app | ${TARGET_APP} |
| topology | ${TOPOLOGY} |
| app_stack | ${APP_STACK} |
| log_format_version | ${LOG_FORMAT_VERSION} |
| scenario_catalog_version | ${SCENARIO_CATALOG_VERSION} |
| initialized_at_utc | $(now_utc) |
| start_time_kst |  |
| end_time_kst |  |

## 2. Environment

| 항목 | 값 |
|---|---|
| OS |  |
| Apache version |  |
| Apache modules |  |
| PHP/runtime version |  |
| WAF enabled |  |
| app log available |  |
| DB/audit log available |  |

## 3. Apache Log Configuration

- app_security.log:
- app_access.log:
- app_error.log:

## 4. Scenario Execution

Command used:

    scripts/run_observability_scenarios.sh \\
      --target-base-url '${TARGET_BASE_URL}' \\
      --run-id '${RUN_ID}'

Notes:

- 
- 
- 

## 5. Server-Side Log Collection

Example only. Adjust paths and time windows per server.

    sudo cp /var/log/apache2/app_security.log '${RUN_DIR}/raw/app_security.log'
    sudo cp /var/log/apache2/app_access.log '${RUN_DIR}/raw/app_access.log'
    sudo cp /var/log/apache2/app_error.log '${RUN_DIR}/raw/app_error.log'

## 6. Observed Differences

### Apache-only evidence

- 

### app_error.log additions

- 

### app/WAF additions

- 

### Still unknowable without app/DB audit

- 

## 7. Follow-up Items

- 
- 
- 
EOF
}

summary_content() {
  cat <<EOF
# Observability Run Summary

- run_id: ${RUN_ID}
- target_app: ${TARGET_APP}
- topology: ${TOPOLOGY}
- scenario_catalog_version: ${SCENARIO_CATALOG_VERSION}

## 1. High-Level Result

TBD

## 2. Evidence Level Summary

| evidence level | count | notes |
|---|---:|---|
| O0 |  |  |
| O1 |  |  |
| O2 |  |  |
| O3 |  |  |
| O4 |  |  |

## 3. Key Findings for Pipeline Design

- 
- 
- 

## 4. Guardrail Checks

| guardrail | result | notes |
|---|---|---|
| No success inference from status_code=200 |  |  |
| No exposure inference from response size only |  |  |
| No login success inference from POST only |  |  |
| No upload success inference from POST only |  |  |
| No compromise inference from WAF match only |  |  |
| No attacker IP assertion from x_forwarded_for only |  |  |

## 5. Recommended Next Changes

- 
- 
- 
EOF
}

main() {
  parse_args "$@"
  require_repo_root_files
  resolve_run_dir

  log "run_id=${RUN_ID}"
  log "run_dir=${RUN_DIR}"

  ensure_dir "${RUN_DIR}/raw"
  ensure_dir "${RUN_DIR}/exported"
  ensure_dir "${RUN_DIR}/client"

  write_file "${RUN_DIR}/metadata.env" "$(metadata_content)"
  write_file "${RUN_DIR}/raw/README.md" "$(raw_readme_content)"
  write_file "${RUN_DIR}/exported/README.md" "$(exported_readme_content)"
  write_file "${RUN_DIR}/client/README.md" "$(client_readme_content)"
  write_file "${RUN_DIR}/notes.md" "$(notes_content)"
  write_file "${RUN_DIR}/summary.md" "$(summary_content)"
  copy_template "lab/observability/observation_matrix_template.md" "${RUN_DIR}/observation_matrix.md"

  log "initialized observability run skeleton"
}

main "$@"
