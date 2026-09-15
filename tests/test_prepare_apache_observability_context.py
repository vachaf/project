from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prepare.apache_observability_context import build_apache_observability_reason_hints_for_row


def test_opencart_front_controller_fallback_hints() -> None:
    row = {
        "uri": "/download.php",
        "query_string": "?_route_=download.php&file=..%2F..%2Fetc%2Fpasswd",
        "status_code": 200,
        "handler": "redirect-handler",
    }
    hints = build_apache_observability_reason_hints_for_row(row)
    assert "observability:front_controller_candidate" in hints
    assert "observability:route_param_present" in hints
    assert "observability:route_param=download.php" in hints
    assert "observability:fallback_200_candidate" in hints


def test_juiceshop_reverse_proxy_fallback_hints() -> None:
    row = {
        "uri": "/private/secret.txt",
        "query_string": "?scenario=S06",
        "status_code": 200,
        "handler": "proxy-server",
    }
    hints = build_apache_observability_reason_hints_for_row(row)
    assert "observability:reverse_proxy_candidate" in hints
    assert "observability:backend_response_candidate" in hints
    assert "observability:backend_fallback_200_candidate" in hints
    assert "observability:fallback_200_candidate" in hints


def test_normal_php_request_has_no_observability_hint() -> None:
    row = {
        "uri": "/index.php",
        "query_string": "?obs_run=test",
        "status_code": 200,
        "handler": "application/x-httpd-php",
    }
    hints = build_apache_observability_reason_hints_for_row(row)
    assert hints == []


def test_server_status_handler_hint() -> None:
    row = {
        "uri": "/server-status",
        "status_code": 200,
        "handler": "server-status",
    }
    hints = build_apache_observability_reason_hints_for_row(row)
    assert "observability:server_status_handler_observed" in hints


def test_directory_redirect_candidate_hint() -> None:
    row = {
        "uri": "/admin",
        "status_code": 301,
        "handler": "httpd/unix-directory",
        "location": "/admin/",
    }
    hints = build_apache_observability_reason_hints_for_row(row)
    assert "observability:directory_redirect_candidate" in hints
    assert "observability:redirect_candidate" in hints
