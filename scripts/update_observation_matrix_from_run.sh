#!/usr/bin/env bash
set -euo pipefail

# Generate and apply an observation matrix draft for an observability run.
#
# This is a convenience wrapper around summarize_observability_run.sh.
# It regenerates observation_matrix.autofill.md and then applies it to
# observation_matrix.md, creating a timestamped backup by default.

SCRIPT_NAME="$(basename "$0")"

RUN_ID=""
RUN_DIR=""
OUTPUT_ROOT="lab/observability/runs"
NO_BACKUP=0
FORCE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/update_observation_matrix_from_run.sh --run-id ID [options]
  scripts/update_observation_matrix_from_run.sh --run-dir DIR [options]

Required, one of:
  --run-id ID
      Run identifier. Uses <output-root>/<run-id> as run directory.

  --run-dir DIR
      Explicit run directory.

Options:
  --output-root DIR
      Root directory for runs when --run-id is used.
      Default: lab/observability/runs

  --force
      Overwrite existing observation_matrix.autofill.md and observation_matrix.md.
      A backup of observation_matrix.md is still created unless --no-backup is set.

  --no-backup
      Do not create a timestamped backup of observation_matrix.md.

Examples:
  scripts/update_observation_matrix_from_run.sh \
    --run-id obs_php_sample_002 \
    --force

Generated/updated files:
  <run-dir>/observation_matrix.autofill.md
  <run-dir>/observation_matrix.md
  <run-dir>/observation_matrix.md.bak.<UTC timestamp>  # unless --no-backup
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
      --force)
        FORCE=1
        shift
        ;;
      --no-backup)
        NO_BACKUP=1
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

utc_stamp() {
  date -u +%Y%m%dT%H%M%SZ
}

main() {
  parse_args "$@"
  resolve_run_dir

  [[ -d "${RUN_DIR}" ]] || fail "run directory does not exist: ${RUN_DIR}"
  [[ -x "scripts/summarize_observability_run.sh" ]] || fail "missing or non-executable: scripts/summarize_observability_run.sh"

  local autofill_path="${RUN_DIR}/observation_matrix.autofill.md"
  local matrix_path="${RUN_DIR}/observation_matrix.md"

  local summarize_args=(
    --run-dir "${RUN_DIR}"
    --output "${autofill_path}"
  )

  if [[ "${FORCE}" -eq 1 ]]; then
    summarize_args+=(--force)
  fi

  log "generating autofill draft: ${autofill_path}"
  scripts/summarize_observability_run.sh "${summarize_args[@]}"

  [[ -s "${autofill_path}" ]] || fail "autofill draft is missing or empty: ${autofill_path}"

  if [[ -e "${matrix_path}" && "${NO_BACKUP}" -ne 1 ]]; then
    local backup_path="${matrix_path}.bak.$(utc_stamp)"
    cp "${matrix_path}" "${backup_path}"
    log "backup created: ${backup_path}"
  fi

  if [[ -e "${matrix_path}" && "${FORCE}" -ne 1 ]]; then
    fail "matrix already exists: ${matrix_path}; use --force to apply"
  fi

  cp "${autofill_path}" "${matrix_path}"
  log "updated: ${matrix_path}"
}

main "$@"
