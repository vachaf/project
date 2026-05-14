#!/usr/bin/env bash
set -euo pipefail

# Apache app observability scenario runner.
#
# Purpose:
#   Execute the S01~S15 scenario catalog against an authorized Apache-fronted
#   application target and save client-side request/response artifacts.
#
# Safety default:
#   Only localhost, private IPv4 ranges, and *.local / *.test / *.internal
#   hostnames are allowed unless --allow-non-local-target is explicitly set.
#
# Related docs:
#   - lab/observability/scenario_catalog.md
#   - lab/observability/observation_matrix_template.md
#   - docs/design/99_apache_app_observability_comparison_plan.md

SCRIPT_NAME="$(basename "$0")"

TARGET_BASE_URL=""
RUN_ID=""
OUTPUT_ROOT="lab/observability/runs"
SCENARIOS="all"
ALLOW_NON_LOCAL_TARGET=0
DRY_RUN=0
VERBOSE=0
INSECURE_TLS=0
SLEEP_BETWEEN_SEC="0.2"
CONNECT_TIMEOUT_SEC="5"
MAX_TIME_SEC="20"
UA_PREFIX="obs-test"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_observability_scenarios.sh --target-base-url URL [options]

Required:
  --target-base-url URL
      Base URL of the authorized Apache-fronted test target.
      Example: http://apache-log-test.local

Options:
  --run-id ID
      Run identifier. Defaults to obs_YYYY_MM_DD_HHMMSS_<host>.

  --output-root DIR
      Root directory for client-side artifacts.
      Default: lab/observability/runs

  --scenarios LIST
      Comma-separated scenario IDs or "all".
      Example: S01,S04,S11
      Default: all

  --allow-non-local-target
      Permit targets outside localhost/private/lab-style hostnames.
      Use only for authorized systems.

  --dry-run
      Print planned curl commands without executing them.

  --verbose
      Print progress and curl command summaries.

  --insecure-tls
      Pass -k to curl for test HTTPS endpoints with self-signed certs.

  --sleep-between-sec SEC
      Sleep interval between requests. Default: 0.2

  --connect-timeout-sec SEC
      curl --connect-timeout value. Default: 5

  --max-time-sec SEC
      curl --max-time value. Default: 20

Examples:
  scripts/run_observability_scenarios.sh \
    --target-base-url http://apache-log-test.local

  scripts/run_observability_scenarios.sh \
    --target-base-url http://127.0.0.1 \
    --run-id obs_php_sample_001 \
    --scenarios S01,S04,S11

Output:
  <output-root>/<run-id>/client/
    commands.log
    summary.tsv
    responses/*.headers
    responses/*.body
    responses/*.meta
EOF
}

log() {
  printf '[%s] %s\n' "${SCRIPT_NAME}" "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

urlencode_component() {
  local raw="${1}"
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "${raw}"
}

normalize_base_url() {
  local url="$1"
  # Remove trailing slashes for stable path joining.
  while [[ "${url}" == */ ]]; do
    url="${url%/}"
  done
  printf '%s' "${url}"
}

extract_url_host() {
  local url="$1"
  python3 -c 'import sys, urllib.parse; print(urllib.parse.urlparse(sys.argv[1]).hostname or "")' "${url}"
}

extract_url_scheme() {
  local url="$1"
  python3 -c 'import sys, urllib.parse; print(urllib.parse.urlparse(sys.argv[1]).scheme or "")' "${url}"
}

is_allowed_default_target_host() {
  local host="$1"

  [[ -n "${host}" ]] || return 1

  case "${host}" in
    localhost|*.localhost|*.local|*.test|*.internal)
      return 0
      ;;
  esac

  if [[ "${host}" =~ ^127\. ]]; then return 0; fi
  if [[ "${host}" =~ ^10\. ]]; then return 0; fi
  if [[ "${host}" =~ ^192\.168\. ]]; then return 0; fi
  if [[ "${host}" =~ ^172\.([1][6-9]|2[0-9]|3[0-1])\. ]]; then return 0; fi

  # IPv6 localhost.
  if [[ "${host}" == "::1" ]]; then return 0; fi

  return 1
}

sanitize_for_path() {
  local value="$1"
  value="${value//[^A-Za-z0-9._-]/_}"
  printf '%s' "${value}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --target-base-url)
        TARGET_BASE_URL="${2:-}"
        shift 2
        ;;
      --run-id)
        RUN_ID="${2:-}"
        shift 2
        ;;
      --output-root)
        OUTPUT_ROOT="${2:-}"
        shift 2
        ;;
      --scenarios)
        SCENARIOS="${2:-}"
        shift 2
        ;;
      --allow-non-local-target)
        ALLOW_NON_LOCAL_TARGET=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --insecure-tls)
        INSECURE_TLS=1
        shift
        ;;
      --sleep-between-sec)
        SLEEP_BETWEEN_SEC="${2:-}"
        shift 2
        ;;
      --connect-timeout-sec)
        CONNECT_TIMEOUT_SEC="${2:-}"
        shift 2
        ;;
      --max-time-sec)
        MAX_TIME_SEC="${2:-}"
        shift 2
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

ALL_SCENARIOS=(
  S01
  S02
  S03
  S04
  S05
  S06
  S07
  S08
  S09
  S10
  S11
  S12
  S13
  S14
  S15
)

scenario_enabled() {
  local scenario="$1"

  if [[ "${SCENARIOS}" == "all" ]]; then
    return 0
  fi

  local list=",${SCENARIOS},"
  [[ "${list}" == *",${scenario},"* ]]
}

join_url() {
  local path="$1"
  if [[ "${path}" == /* ]]; then
    printf '%s%s' "${TARGET_BASE_URL}" "${path}"
  else
    printf '%s/%s' "${TARGET_BASE_URL}" "${path}"
  fi
}

curl_common_args=()

build_curl_common_args() {
  curl_common_args=(
    --silent
    --show-error
    --location
    --connect-timeout "${CONNECT_TIMEOUT_SEC}"
    --max-time "${MAX_TIME_SEC}"
  )

  if [[ "${INSECURE_TLS}" -eq 1 ]]; then
    curl_common_args+=(--insecure)
  fi
}

COMMANDS_LOG=""
SUMMARY_TSV=""
RESPONSES_DIR=""
TMP_DIR=""

write_metadata() {
  local run_dir="$1"
  local target_host="$2"
  local metadata_path="${run_dir}/metadata.env"

  cat > "${metadata_path}" <<EOF
RUN_ID=${RUN_ID}
TARGET_BASE_URL=${TARGET_BASE_URL}
TARGET_HOST=${target_host}
SCENARIOS=${SCENARIOS}
START_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SCENARIO_CATALOG_VERSION=apache_observability_s01_s15_v1
EOF
}

record_command() {
  printf '%s\n' "$*" >> "${COMMANDS_LOG}"
}

record_summary_header() {
  printf 'scenario\tname\tmethod\turl\thttp_code\ttime_total\tsize_download\terror\n' > "${SUMMARY_TSV}"
}

record_summary() {
  local scenario="$1"
  local name="$2"
  local method="$3"
  local url="$4"
  local http_code="$5"
  local time_total="$6"
  local size_download="$7"
  local error_msg="$8"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${scenario}" "${name}" "${method}" "${url}" "${http_code}" "${time_total}" "${size_download}" "${error_msg}" \
    >> "${SUMMARY_TSV}"
}

run_curl() {
  local scenario="$1"
  local name="$2"
  local method="$3"
  local url="$4"
  shift 4

  local safe_name
  safe_name="$(sanitize_for_path "${scenario}_${name}")"
  local headers_path="${RESPONSES_DIR}/${safe_name}.headers"
  local body_path="${RESPONSES_DIR}/${safe_name}.body"
  local meta_path="${RESPONSES_DIR}/${safe_name}.meta"
  local err_path="${RESPONSES_DIR}/${safe_name}.stderr"

  local ua="${UA_PREFIX}/${scenario} run=${RUN_ID}"
  local -a cmd=(
    curl
    "${curl_common_args[@]}"
    --request "${method}"
    --user-agent "${ua}"
    --dump-header "${headers_path}"
    --output "${body_path}"
    --write-out 'http_code=%{http_code}\ntime_total=%{time_total}\nsize_download=%{size_download}\nurl_effective=%{url_effective}\n'
  )

  cmd+=("$@")
  cmd+=("${url}")

  record_command "# ${scenario} ${name}"
  printf '%q ' "${cmd[@]}" >> "${COMMANDS_LOG}"
  printf '\n\n' >> "${COMMANDS_LOG}"

  if [[ "${VERBOSE}" -eq 1 || "${DRY_RUN}" -eq 1 ]]; then
    log "${scenario} ${name}: ${method} ${url}"
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    record_summary "${scenario}" "${name}" "${method}" "${url}" "DRY_RUN" "" "" ""
    return 0
  fi

  local curl_status=0
  "${cmd[@]}" > "${meta_path}" 2> "${err_path}" || curl_status=$?

  local http_code=""
  local time_total=""
  local size_download=""
  if [[ -s "${meta_path}" ]]; then
    http_code="$(awk -F= '$1 == "http_code" {print $2}' "${meta_path}" | tail -n 1)"
    time_total="$(awk -F= '$1 == "time_total" {print $2}' "${meta_path}" | tail -n 1)"
    size_download="$(awk -F= '$1 == "size_download" {print $2}' "${meta_path}" | tail -n 1)"
  fi

  local error_msg=""
  if [[ "${curl_status}" -ne 0 ]]; then
    error_msg="curl_exit_${curl_status}"
    log "WARN: ${scenario} ${name} curl exited with ${curl_status}; see ${err_path}"
  fi

  record_summary "${scenario}" "${name}" "${method}" "${url}" "${http_code}" "${time_total}" "${size_download}" "${error_msg}"
}

scenario_s01() {
  run_curl S01 normal_main GET \
    "$(join_url "/?obs_run=${RUN_ID}&scenario=S01")"
}

scenario_s02() {
  run_curl S02 static_css GET \
    "$(join_url "/static/style.css?obs_run=${RUN_ID}&scenario=S02")"
}

scenario_s03() {
  run_curl S03 static_js GET \
    "$(join_url "/static/app.js?obs_run=${RUN_ID}&scenario=S03")"
}

scenario_s04() {
  run_curl S04 query_search GET \
    "$(join_url "/search.php?q=normal-search&obs_run=${RUN_ID}&scenario=S04")"
}

scenario_s05() {
  run_curl S05 not_found GET \
    "$(join_url "/does-not-exist-${RUN_ID}?scenario=S05&obs_run=${RUN_ID}")"
}

scenario_s06() {
  run_curl S06 forbidden_or_sensitive_path GET \
    "$(join_url "/private/secret.txt?scenario=S06&obs_run=${RUN_ID}")"
}

scenario_s07() {
  run_curl S07 login_get GET \
    "$(join_url "/login.php?obs_run=${RUN_ID}&scenario=S07")"
}

scenario_s08() {
  run_curl S08 login_post POST \
    "$(join_url "/login.php")" \
    --header "Content-Type: application/x-www-form-urlencoded" \
    --data "username=alice&password=wrong-password&obs_run=${RUN_ID}&scenario=S08"
}

scenario_s09() {
  local upload_file="${TMP_DIR}/obs-upload-${RUN_ID}.txt"
  printf 'observability upload sample %s\n' "${RUN_ID}" > "${upload_file}"

  run_curl S09 upload_like_post POST \
    "$(join_url "/upload.php")" \
    --form "file=@${upload_file}" \
    --form "obs_run=${RUN_ID}" \
    --form "scenario=S09"
}

scenario_s10() {
  run_curl S10 slow_or_large_request GET \
    "$(join_url "/search.php?q=slow-check&sleep_ms=300&obs_run=${RUN_ID}&scenario=S10")"
}

scenario_s11() {
  run_curl S11 server_error GET \
    "$(join_url "/error.php?obs_run=${RUN_ID}&scenario=S11")"
}

scenario_s12() {
  local paths=(
    "/"
    "/search.php"
    "/admin"
    "/wp-login.php"
    "/.env"
    "/server-status"
    "/does-not-exist"
  )

  local idx=0
  local path
  for path in "${paths[@]}"; do
    idx=$((idx + 1))
    run_curl S12 "scanner_burst_${idx}" GET \
      "$(join_url "${path}?obs_run=${RUN_ID}&scenario=S12&burst_index=${idx}")"
  done
}

scenario_s13() {
  local payload
  payload="$(urlencode_component "1' OR '1'='1")"
  run_curl S13 sqli_like GET \
    "$(join_url "/search.php?q=${payload}&obs_run=${RUN_ID}&scenario=S13")"
}

scenario_s14() {
  local payload
  payload="$(urlencode_component "<script>alert(1)</script>")"
  run_curl S14 xss_like GET \
    "$(join_url "/search.php?q=${payload}&obs_run=${RUN_ID}&scenario=S14")"
}

scenario_s15() {
  local payload
  payload="$(urlencode_component "../../../etc/passwd")"
  run_curl S15 traversal_like GET \
    "$(join_url "/download.php?file=${payload}&obs_run=${RUN_ID}&scenario=S15")"
}

run_scenario() {
  local scenario="$1"
  case "${scenario}" in
    S01) scenario_s01 ;;
    S02) scenario_s02 ;;
    S03) scenario_s03 ;;
    S04) scenario_s04 ;;
    S05) scenario_s05 ;;
    S06) scenario_s06 ;;
    S07) scenario_s07 ;;
    S08) scenario_s08 ;;
    S09) scenario_s09 ;;
    S10) scenario_s10 ;;
    S11) scenario_s11 ;;
    S12) scenario_s12 ;;
    S13) scenario_s13 ;;
    S14) scenario_s14 ;;
    S15) scenario_s15 ;;
    *) fail "unknown scenario: ${scenario}" ;;
  esac
}

validate_selected_scenarios() {
  if [[ "${SCENARIOS}" == "all" ]]; then
    return 0
  fi

  local IFS=','
  local selected=(${SCENARIOS})
  local s
  for s in "${selected[@]}"; do
    [[ " ${ALL_SCENARIOS[*]} " == *" ${s} "* ]] || fail "unknown scenario in --scenarios: ${s}"
  done
}

main() {
  parse_args "$@"

  require_command curl
  require_command python3
  require_command awk
  require_command date

  [[ -n "${TARGET_BASE_URL}" ]] || fail "--target-base-url is required"
  TARGET_BASE_URL="$(normalize_base_url "${TARGET_BASE_URL}")"

  local scheme
  scheme="$(extract_url_scheme "${TARGET_BASE_URL}")"
  [[ "${scheme}" == "http" || "${scheme}" == "https" ]] || fail "target URL must start with http:// or https://"

  local target_host
  target_host="$(extract_url_host "${TARGET_BASE_URL}")"
  [[ -n "${target_host}" ]] || fail "failed to parse target host from URL: ${TARGET_BASE_URL}"

  if [[ "${ALLOW_NON_LOCAL_TARGET}" -ne 1 ]]; then
    if ! is_allowed_default_target_host "${target_host}"; then
      fail "target host '${target_host}' is not localhost/private/lab-style. Re-run with --allow-non-local-target only for authorized systems."
    fi
  fi

  validate_selected_scenarios

  if [[ -z "${RUN_ID}" ]]; then
    RUN_ID="obs_$(date +%Y_%m_%d_%H%M%S)_$(sanitize_for_path "${target_host}")"
  fi

  local run_dir="${OUTPUT_ROOT}/${RUN_ID}"
  RESPONSES_DIR="${run_dir}/client/responses"
  TMP_DIR="${run_dir}/client/tmp"
  COMMANDS_LOG="${run_dir}/client/commands.log"
  SUMMARY_TSV="${run_dir}/client/summary.tsv"

  mkdir -p "${RESPONSES_DIR}" "${TMP_DIR}"
  : > "${COMMANDS_LOG}"
  record_summary_header
  write_metadata "${run_dir}" "${target_host}"
  build_curl_common_args

  log "run_id=${RUN_ID}"
  log "target=${TARGET_BASE_URL}"
  log "output=${run_dir}"

  local scenario
  for scenario in "${ALL_SCENARIOS[@]}"; do
    if scenario_enabled "${scenario}"; then
      run_scenario "${scenario}"
      if [[ "${scenario}" != "S12" ]]; then
        sleep "${SLEEP_BETWEEN_SEC}"
      fi
    fi
  done

  cat > "${run_dir}/client/README.md" <<EOF
# Observability Client Artifacts

- run_id: ${RUN_ID}
- target: ${TARGET_BASE_URL}
- scenarios: ${SCENARIOS}
- generated_at_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Files:

- \`commands.log\`: exact curl commands executed or planned
- \`summary.tsv\`: response status/timing summary
- \`responses/*.headers\`: response headers
- \`responses/*.body\`: response bodies
- \`responses/*.meta\`: curl write-out metadata
- \`responses/*.stderr\`: curl stderr

Next steps:

1. Copy relevant server-side logs into \`${run_dir}/raw/\`.
2. Export DB rows for the run marker \`${RUN_ID}\`.
3. Copy \`lab/observability/observation_matrix_template.md\` to \`${run_dir}/observation_matrix.md\`.
4. Fill the scenario result matrix.
EOF

  log "completed"
  log "summary=${SUMMARY_TSV}"
}

main "$@"
