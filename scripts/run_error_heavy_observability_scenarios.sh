#!/usr/bin/env bash
set -uo pipefail

# Apache observability error-heavy lab runner.
#
# Purpose:
#   Reproduce the EH01~EH12 request set against the lab PHP sample target so an
#   operator can generate Apache observability logs from a local or external
#   client in a consistent way.
#
# Scope boundary:
#   - Lab-only request generator
#   - Does not collect logs
#   - Does not run export/dry-run/explain
#   - Does not verify exploit success
#   - Does not change prepare/scoring/filtering
#
# Reconstruction note:
#   This runner is based on the existing
#   lab/observability/runs/obs_php_sample_v2_error_heavy_001 artifact and keeps
#   the observed `?scenario=EHxx&run=$RUN_ID` query shape. EH04/EH06 POST bodies
#   are synthetic best-effort lab inputs, not recovered originals. Raw POST
#   bodies are not collected by the Apache logs-only pipeline and are not
#   success evidence.

SCRIPT_NAME="$(basename "$0")"

RUN_ID=""
BASE_URL=""
HOST_HEADER=""
PAUSE_SEC="0.2"
CURL_BIN="curl"
DRY_RUN=0
FAIL_FAST=0
SCENARIO_FILTER="all"

ATTEMPTED=0
SUCCESSFUL_CALLS=0
FAILED_CALLS=0
TMP_DIR=""

usage() {
  cat <<'EOF'
Usage:
  scripts/run_error_heavy_observability_scenarios.sh \
    --run-id ID \
    --base-url URL \
    [options]

Required:
  --run-id ID
      Run identifier inserted into the query string as `run=$RUN_ID`.

  --base-url URL
      Base URL of the lab Apache/PHP target.
      Example: http://192.168.56.115
      Example: http://apache-log-test-v2.local

Options:
  --host-header HOST
      Optional Host header for IP-based access to a named vhost.

  --pause-sec SEC
      Sleep interval between scenario requests. Default: 0.2

  --curl-bin PATH
      curl binary to use. Default: curl

  --scenario ID[,ID...]
      Run only specific EH scenarios.
      Example: EH01
      Example: EH01,EH10,EH12
      Default: all

  --dry-run
      Print planned requests and curl commands without executing them.

  --fail-fast
      Stop immediately on curl transport failure.

  -h, --help
      Show this help.

Notes:
  - Uses `?scenario=EHxx&run=$RUN_ID` by default.
  - Sends no Referer, X-Forwarded-For, X-Real-IP, or Forwarded headers by default.
  - Non-2xx/3xx HTTP statuses are not treated as failures.
  - Only curl transport failures are counted as failed calls.
EOF
}

log() {
  printf '[%s] %s\n' "${SCRIPT_NAME}" "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

cleanup() {
  if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

normalize_base_url() {
  local url="$1"
  while [[ "${url}" == */ ]]; do
    url="${url%/}"
  done
  printf '%s' "${url}"
}

scenario_enabled() {
  local scenario="$1"
  if [[ "${SCENARIO_FILTER}" == "all" ]]; then
    return 0
  fi
  local list=",${SCENARIO_FILTER},"
  [[ "${list}" == *",${scenario},"* ]]
}

join_url() {
  local path="$1"
  if [[ "${path}" == /* ]]; then
    printf '%s%s' "${BASE_URL}" "${path}"
  else
    printf '%s/%s' "${BASE_URL}" "${path}"
  fi
}

build_query() {
  local scenario="$1"
  case "${scenario}" in
    EH10)
      printf 'file=..%%2F..%%2F..%%2Fetc%%2Fpasswd&scenario=%s&run=%s' "${scenario}" "${RUN_ID}"
      ;;
    EH11)
      printf 'q=%%27%%20OR%%20%%271%%27%%3D%%271--&scenario=%s&run=%s' "${scenario}" "${RUN_ID}"
      ;;
    EH12)
      printf 'q=%%3Cscript%%3Ealert(1)%%3C%%2Fscript%%3E&scenario=%s&run=%s' "${scenario}" "${RUN_ID}"
      ;;
    *)
      printf 'scenario=%s&run=%s' "${scenario}" "${RUN_ID}"
      ;;
  esac
}

build_path() {
  local scenario="$1"
  case "${scenario}" in
    EH01) printf '/error.php' ;;
    EH02) printf '/private/secret.txt' ;;
    EH03) printf '/does-not-exist-error-heavy-%s' "${RUN_ID}" ;;
    EH04) printf '/login.php' ;;
    EH05) printf '/login.php' ;;
    EH06) printf '/upload.php' ;;
    EH07) printf '/.env' ;;
    EH08) printf '/wp-login.php' ;;
    EH09) printf '/admin' ;;
    EH10) printf '/download.php' ;;
    EH11) printf '/search.php' ;;
    EH12) printf '/search.php' ;;
    *)
      fail "unsupported scenario: ${scenario}"
      ;;
  esac
}

build_method() {
  local scenario="$1"
  case "${scenario}" in
    EH04|EH06) printf 'POST' ;;
    *) printf 'GET' ;;
  esac
}

build_expected_note() {
  local scenario="$1"
  case "${scenario}" in
    EH01) printf 'expected 500 / status-error-only candidate' ;;
    EH02) printf 'expected 403 / status-error-only candidate' ;;
    EH03) printf 'expected 404 / probe context' ;;
    EH04) printf 'expected 401 / auth-failure context' ;;
    EH05) printf 'expected 200 with error-linked metadata / status-error-only review' ;;
    EH06) printf 'expected 400 / upload-failure context' ;;
    EH07) printf 'expected 404 / probe context' ;;
    EH08) printf 'expected 404 / probe context' ;;
    EH09) printf 'expected 404 / probe context' ;;
    EH10) printf 'expected traversal-like payload candidate' ;;
    EH11) printf 'expected SQLi-like payload candidate' ;;
    EH12) printf 'expected XSS-like payload candidate' ;;
    *)
      printf 'best-effort lab scenario'
      ;;
  esac
}

write_eh04_body() {
  local file_path="$1"
  printf 'username=obs&password=invalid' >"${file_path}"
}

write_eh06_body() {
  local file_path="$1"
  cat >"${file_path}" <<'EOF'
------ObsBoundary
Content-Disposition: form-data; name="upload"; filename="obs-error-heavy.txt"
Content-Type: text/plain

synthetic upload body for observability only
------ObsBoundary--
EOF
}

scenario_body_file() {
  local scenario="$1"
  local body_file=""
  case "${scenario}" in
    EH04)
      body_file="${TMP_DIR}/${scenario}.body"
      write_eh04_body "${body_file}"
      ;;
    EH06)
      body_file="${TMP_DIR}/${scenario}.body"
      write_eh06_body "${body_file}"
      ;;
  esac
  printf '%s' "${body_file}"
}

print_request_header() {
  local scenario="$1"
  local method="$2"
  local url="$3"
  printf '=== %s ===\n' "${scenario}"
  printf 'method: %s\n' "${method}"
  printf 'url: %s\n' "${url}"
  if [[ -n "${HOST_HEADER}" ]]; then
    printf 'host_header: %s\n' "${HOST_HEADER}"
  else
    printf 'host_header: <none>\n'
  fi
  printf 'note: %s\n' "$(build_expected_note "${scenario}")"
}

run_scenario() {
  local scenario="$1"
  local method path query url ua body_file http_status curl_exit
  local -a curl_args

  path="$(build_path "${scenario}")"
  query="$(build_query "${scenario}")"
  method="$(build_method "${scenario}")"
  url="$(join_url "${path}")?${query}"
  ua="obs-error-heavy/${scenario} run=${RUN_ID}"
  body_file="$(scenario_body_file "${scenario}")"

  print_request_header "${scenario}" "${method}" "${url}"

  curl_args=(
    --silent
    --show-error
    --output /dev/null
    --write-out '%{http_code}'
    --request "${method}"
    --url "${url}"
    --user-agent "${ua}"
  )

  if [[ -n "${HOST_HEADER}" ]]; then
    curl_args+=(--header "Host: ${HOST_HEADER}")
  fi

  case "${scenario}" in
    EH04)
      curl_args+=(
        --header 'Content-Type: application/x-www-form-urlencoded'
        --data-binary "@${body_file}"
      )
      ;;
    EH06)
      curl_args+=(
        --header 'Content-Type: multipart/form-data; boundary=----ObsBoundary'
        --data-binary "@${body_file}"
      )
      ;;
  esac

  ATTEMPTED=$((ATTEMPTED + 1))

  if [[ ${DRY_RUN} -eq 1 ]]; then
    printf 'dry_run: %q' "${CURL_BIN}"
    local arg
    for arg in "${curl_args[@]}"; do
      printf ' %q' "${arg}"
    done
    printf '\n'
    printf 'http_status: <dry-run>\n'
    printf 'curl_exit_code: <dry-run>\n\n'
    SUCCESSFUL_CALLS=$((SUCCESSFUL_CALLS + 1))
    return 0
  fi

  http_status="$("${CURL_BIN}" "${curl_args[@]}")"
  curl_exit=$?

  if [[ ${curl_exit} -eq 0 ]]; then
    SUCCESSFUL_CALLS=$((SUCCESSFUL_CALLS + 1))
    printf 'http_status: %s\n' "${http_status}"
    printf 'curl_exit_code: %s\n\n' "${curl_exit}"
  else
    FAILED_CALLS=$((FAILED_CALLS + 1))
    printf 'http_status: %s\n' "${http_status:-000}"
    printf 'curl_exit_code: %s\n\n' "${curl_exit}"
    if [[ ${FAIL_FAST} -eq 1 ]]; then
      fail "curl transport failure on ${scenario}"
    fi
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --run-id)
        RUN_ID="${2:-}"
        shift 2
        ;;
      --base-url)
        BASE_URL="${2:-}"
        shift 2
        ;;
      --host-header)
        HOST_HEADER="${2:-}"
        shift 2
        ;;
      --pause-sec)
        PAUSE_SEC="${2:-}"
        shift 2
        ;;
      --curl-bin)
        CURL_BIN="${2:-}"
        shift 2
        ;;
      --scenario)
        SCENARIO_FILTER="${2:-}"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --fail-fast)
        FAIL_FAST=1
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

validate_args() {
  [[ -n "${RUN_ID}" ]] || fail "--run-id is required"
  [[ -n "${BASE_URL}" ]] || fail "--base-url is required"
  BASE_URL="$(normalize_base_url "${BASE_URL}")"
  require_command "${CURL_BIN}"
  require_command mktemp
  require_command sleep
}

main() {
  local scenarios scenario
  scenarios=(EH01 EH02 EH03 EH04 EH05 EH06 EH07 EH08 EH09 EH10 EH11 EH12)

  parse_args "$@"
  validate_args

  TMP_DIR="$(mktemp -d)"
  trap cleanup EXIT

  for scenario in "${scenarios[@]}"; do
    if ! scenario_enabled "${scenario}"; then
      continue
    fi
    run_scenario "${scenario}"
    if [[ ${DRY_RUN} -eq 0 && "${scenario}" != "EH12" && "${PAUSE_SEC}" != "0" && "${PAUSE_SEC}" != "0.0" ]]; then
      sleep "${PAUSE_SEC}"
    fi
  done

  printf '=== Summary ===\n'
  printf 'attempted: %d\n' "${ATTEMPTED}"
  printf 'succeeded_curl_calls: %d\n' "${SUCCESSFUL_CALLS}"
  printf 'failed_curl_calls: %d\n' "${FAILED_CALLS}"
  printf 'note: non-2xx/3xx HTTP statuses are expected in EH scenarios and are not treated as failures.\n'

  if [[ ${FAILED_CALLS} -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
