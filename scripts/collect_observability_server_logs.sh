#!/usr/bin/env bash
set -euo pipefail

# Collect and filter Apache server-side logs for an observability run.
#
# This script intentionally treats User-Agent "obs-test/Sxx run=<run_id>" as the
# canonical scenario marker because POST scenarios may place scenario IDs in the
# request body, which Apache access/security logs do not record.
#
# Related:
#   - scripts/run_observability_scenarios.sh
#   - lab/observability/scenario_catalog.md
#   - lab/observability/observation_matrix_template.md

SCRIPT_NAME="$(basename "$0")"

RUN_ID=""
RUN_DIR=""
OUTPUT_ROOT="lab/observability/runs"
SECURITY_LOG="/var/log/apache2/apache-log-test_security.log"
ACCESS_LOG="/var/log/apache2/apache-log-test_access.log"
ERROR_LOG="/var/log/apache2/apache-log-test_error.log"
SUDO_CP=0
FORCE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/collect_observability_server_logs.sh --run-id ID [options]
  scripts/collect_observability_server_logs.sh --run-dir DIR [options]

Required, one of:
  --run-id ID
      Run identifier. Uses <output-root>/<run-id> as run directory.

  --run-dir DIR
      Explicit run directory.

Options:
  --output-root DIR
      Root directory for runs when --run-id is used.
      Default: lab/observability/runs

  --security-log PATH
      Apache security log path.
      Default: /var/log/apache2/apache-log-test_security.log

  --access-log PATH
      Apache access log path.
      Default: /var/log/apache2/apache-log-test_access.log

  --error-log PATH
      Apache error log path.
      Default: /var/log/apache2/apache-log-test_error.log

  --sudo-cp
      Use sudo for existence checks and copying logs from protected directories.

  --force
      Overwrite copied raw log files and generated filtered files.

Examples:
  scripts/collect_observability_server_logs.sh \
    --run-id obs_php_sample_002 \
    --sudo-cp

Generated files:
  raw/apache-log-test_security.log
  raw/apache-log-test_access.log
  raw/apache-log-test_error.log
  raw/app_security.filtered.log
  raw/app_access.filtered.log
  raw/request_ids.txt
  raw/app_error.by_request_id.log
  raw/scenario_counts.tsv
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
      --security-log)
        SECURITY_LOG="${2:-}"
        shift 2
        ;;
      --access-log)
        ACCESS_LOG="${2:-}"
        shift 2
        ;;
      --error-log)
        ERROR_LOG="${2:-}"
        shift 2
        ;;
      --sudo-cp)
        SUDO_CP=1
        shift
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
}

source_log_exists() {
  local path="$1"
  if [[ "${SUDO_CP}" -eq 1 ]]; then
    sudo test -f "${path}"
  else
    test -f "${path}"
  fi
}

copy_log() {
  local src="$1"
  local dst="$2"

  if ! source_log_exists "${src}"; then
    log "WARN: source log does not exist or is not readable: ${src}"
    : > "${dst}"
    return 0
  fi

  if [[ -e "${dst}" && "${FORCE}" -ne 1 ]]; then
    log "skip existing raw log: ${dst}"
    return 0
  fi

  if [[ "${SUDO_CP}" -eq 1 ]]; then
    sudo install -m 0644 -o "${USER}" -g "${USER}" "${src}" "${dst}"
  else
    cp "${src}" "${dst}"
  fi
  log "copied: ${src} -> ${dst}"
}

write_generated() {
  local path="$1"
  if [[ -e "${path}" && "${FORCE}" -ne 1 ]]; then
    log "skip existing generated file: ${path}"
    return 1
  fi
  return 0
}

main() {
  parse_args "$@"
  resolve_run_dir

  local raw_dir="${RUN_DIR}/raw"
  mkdir -p "${raw_dir}"

  local raw_security="${raw_dir}/$(basename "${SECURITY_LOG}")"
  local raw_access="${raw_dir}/$(basename "${ACCESS_LOG}")"
  local raw_error="${raw_dir}/$(basename "${ERROR_LOG}")"

  log "run_id=${RUN_ID}"
  log "run_dir=${RUN_DIR}"

  copy_log "${SECURITY_LOG}" "${raw_security}"
  copy_log "${ACCESS_LOG}" "${raw_access}"
  copy_log "${ERROR_LOG}" "${raw_error}"

  local security_filtered="${raw_dir}/app_security.filtered.log"
  local access_filtered="${raw_dir}/app_access.filtered.log"
  local request_ids="${raw_dir}/request_ids.txt"
  local error_by_request_id="${raw_dir}/app_error.by_request_id.log"
  local scenario_counts="${raw_dir}/scenario_counts.tsv"

  if write_generated "${security_filtered}"; then
    grep "obs-test/.*run=${RUN_ID}" "${raw_security}" > "${security_filtered}" || true
    log "wrote: ${security_filtered}"
  fi

  if write_generated "${access_filtered}"; then
    grep "obs-test/.*run=${RUN_ID}" "${raw_access}" > "${access_filtered}" || true
    log "wrote: ${access_filtered}"
  fi

  if write_generated "${request_ids}"; then
    grep -o 'request_id=[^ ]*' "${security_filtered}" \
      | cut -d= -f2 \
      | grep -v '^-$' \
      | sort -u \
      > "${request_ids}" || true
    log "wrote: ${request_ids}"
  fi

  if write_generated "${error_by_request_id}"; then
    if [[ -s "${request_ids}" ]]; then
      grep -Ff "${request_ids}" "${raw_error}" > "${error_by_request_id}" || true
    else
      : > "${error_by_request_id}"
    fi
    log "wrote: ${error_by_request_id}"
  fi

  if write_generated "${scenario_counts}"; then
    {
      printf 'scenario\tcount\n'
      grep -o 'obs-test/S[0-9][0-9]' "${security_filtered}" \
        | sed 's/obs-test\///' \
        | sort \
        | uniq -c \
        | awk '{print $2 "\t" $1}'
    } > "${scenario_counts}" || true
    log "wrote: ${scenario_counts}"
  fi

  log "line counts:"
  wc -l "${security_filtered}" "${access_filtered}" "${error_by_request_id}" "${scenario_counts}" >&2 || true

  log "scenario counts:"
  column -t -s $'\t' "${scenario_counts}" >&2 || cat "${scenario_counts}" >&2
}

main "$@"
