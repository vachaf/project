#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실험용 Apache 로그 흔적 생성기 (Lab Traffic Generator, v2)
- 목적: authorized lab 환경에서 분석 파이프라인 검증용 원천 로그 생성
- 비목적: exploit 성공/계정 탈취/서버 상태 변경/파일 업로드·삭제 검증
- 원칙: Apache access log 관측 기반, GET/HEAD/OPTIONS 중심, fragment('#') 금지
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple
from urllib import error, parse, request

ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS"}

# UA/Referer/IP는 공격 성공 근거가 아니라 로그 다양성 목적이다.
USER_AGENTS = {
    "browser": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    ],
    "mobile": [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
        "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 Chrome/124.0 Mobile Safari/537.36",
    ],
    "crawler": [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "GenericCrawler/1.0",
    ],
    "script": [
        "curl/8.1.2",
        "Wget/1.21.4",
        "python-requests/2.31.0",
    ],
}

ACCEPT_LANGUAGES = ["en-US,en;q=0.9", "ko-KR,ko;q=0.9,en-US;q=0.7", "en-GB,en;q=0.8"]
REFERER_POOL = ["", "https://example.local/", "https://shop.local/category", "https://docs.local/search?q=guide"]

MUTATION_WORDS = ["phone", "shoes", "jacket", "juice", "guide", "manual", "status", "token", "select shoes", "union jacket"]
MUTATION_CATEGORY_PATHS = ["18", "20", "24", "57_62", "66_71"]
MUTATION_PRODUCT_IDS = ["1", "2", "8", "40", "77", "102"]

PROFILE_DELAYS = {
    "normal": (1.0, 4.0),
    "baseline": (1.0, 4.0),
    "scanner_burst": (0.05, 0.3),
    "low_and_slow": (10.0, 30.0),
    "mixed": (0.5, 3.0),
}

Endpoint = Dict[str, Any]

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "JuiceShop_Normal": {
        "desc": "Juice Shop 정상 API 탐색 패턴",
        "profile": "normal",
        "endpoints": [
            ("/", "GET"),
            ("/rest/products/search?q=apple", "GET"),
            ("/rest/products/search?q=juice", "GET"),
            ("/api/Products", "GET"),
            ("/rest/languages", "GET"),
            ("/rest/user/login", "OPTIONS"),
            ("/rest/products/1/reviews", "GET"),
        ],
    },
    "OpenCart_Normal": {
        "desc": "OpenCart 정상 커머스 이용 패턴",
        "profile": "baseline",
        "endpoints": [
            ("/index.php?route=common/home", "GET"),
            ("/index.php?route=product/category&path=20", "GET"),
            ("/index.php?route=product/product&product_id=40", "GET"),
            ("/index.php?route=product/search&search=phone", "GET"),
            ("/index.php?route=information/contact", "GET"),
        ],
    },
    "Static_Noise": {
        "desc": "정적 리소스 및 봇 노이즈 (오탐 억제 검증용)",
        "profile": "baseline",
        "endpoints": [
            {"path": "/robots.txt", "method": "GET", "ua_family": "crawler", "tag": "baseline"},
            {"path": "/favicon.ico", "method": "GET", "ua_family": "browser", "tag": "baseline"},
            {"path": "/sitemap.xml", "method": "GET", "ua_family": "crawler", "tag": "baseline"},
            {"path": "/assets/public/main.js", "method": "GET", "tag": "noise"},
            {"path": "/catalog/view/theme/default/stylesheet/stylesheet.css", "method": "GET", "tag": "noise"},
        ],
    },
    "ScannerBurst": {
        "desc": "취약점 스캐너 탐색 흔적 (민감 경로 위주)",
        "profile": "scanner_burst",
        "endpoints": [
            ("/.env", "GET"),
            ("/.git/config", "GET"),
            ("/wp-login.php", "GET"),
            ("/admin/config.php", "GET"),
            ("/phpmyadmin/", "HEAD"),
            ("/shell.php", "GET"),
            ("/backup.sql", "GET"),
        ],
    },
    "LowAndSlow": {
        "desc": "저속 의심 조사 흔적 (완화된 경로 사용)",
        "profile": "low_and_slow",
        "endpoints": [
            ("/view?file=..%2F..%2Fetc%2Fpasswd", "GET"),
            ("/config/backup", "GET"),
            ("/server-status", "GET"),
            ("/cgi-bin/test-cgi", "GET"),
            ("/admin/backup", "GET"),
        ],
    },
    "SuspiciousQueryMix": {
        "desc": "의심 문자열 혼합 요청 (SQLi/XSS/LFI 흔적)",
        "profile": "mixed",
        "endpoints": [
            ("/search?q=%3Cscript%3Ealert(1)%3C/script%3E", "GET"),
            ("/products?id=1%20OR%201=1", "GET"),
            ("/view?file=../../../../etc/passwd", "GET"),
            ("/search?q=' OR '1'='1", "GET"),
        ],
    },
    "SQLi_Markers": {
        "desc": "SQLi-like marker + 정상 검색어 혼합",
        "profile": "mixed",
        "endpoints": [
            {"path": "/search?q=%27%20OR%201%3D1--", "method": "GET", "tag": "sqli"},
            {"path": "/products?id=1%27%20AND%20%271%27%3D%271", "method": "GET", "tag": "sqli"},
            {"path": "/filter?name=%27%20UNION%20SELECT%201,2,3--", "method": "GET", "tag": "sqli"},
            {"path": "/search?q=%2527%2520or%25201%253d1", "method": "GET", "tag": "sqli"},
            {"path": "/search?q=select%20shoes", "method": "GET", "tag": "noise"},
            {"path": "/search?q=union%20jacket", "method": "GET", "tag": "noise"},
        ],
    },
    "XSS_Markers": {
        "desc": "XSS-like marker 생성 (브라우저 실행 검증 목적 아님)",
        "profile": "mixed",
        "endpoints": [
            {"path": "/search?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E", "method": "GET", "tag": "xss"},
            {"path": "/search?q=%22%20onerror%3Dalert%281%29%20x%3D%22", "method": "GET", "tag": "xss"},
            {"path": "/redirect?next=javascript%3Aalert%281%29", "method": "GET", "tag": "xss"},
            {"path": "/search?q=%26lt%3Bimg%20src%3Dx%20onload%3Dalert%281%29%26gt%3B", "method": "GET", "tag": "xss"},
        ],
    },
    "Traversal_FileDisclosure_Markers": {
        "desc": "Traversal/file-disclosure marker + 정상 파일명 노이즈",
        "profile": "mixed",
        "endpoints": [
            {"path": "/view?file=..%2F..%2F..%2Fetc%2Fpasswd", "method": "GET", "tag": "traversal"},
            {"path": "/download?path=%252e%252e%252f%252e%252e%252fetc%252fshadow", "method": "GET", "tag": "traversal"},
            {"path": "/view?file=php%3A%2F%2Ffilter%2Fconvert.base64-encode%2Fresource%3Dindex.php", "method": "GET", "tag": "file_disclosure"},
            {"path": "/docs/manual", "method": "GET", "tag": "noise"},
            {"path": "/backup/config", "method": "GET", "tag": "noise"},
        ],
    },
    "CMDI_Markers": {
        "desc": "CMDI-like marker 생성 (실행 목적 없음)",
        "profile": "mixed",
        "endpoints": [
            {"path": "/tools/ping?host=127.0.0.1%3Bcat%20%2Fetc%2Fpasswd", "method": "GET", "tag": "cmdi"},
            {"path": "/tools/ping?host=localhost%26%26id", "method": "GET", "tag": "cmdi"},
            {"path": "/run?cmd=whoami%7Cls", "method": "GET", "tag": "cmdi"},
            {"path": "/diagnose?target=8.8.8.8%24%28id%29", "method": "GET", "tag": "cmdi"},
        ],
    },
    "HPP_Markers": {
        "desc": "중복 파라미터(HPP) 흔적 생성",
        "profile": "mixed",
        "endpoints": [
            {"path": "/products?id=1&id=2", "method": "GET", "tag": "hpp"},
            {"path": "/search?q=normal&q=%2527%2520OR%25201%253D1", "method": "GET", "tag": "hpp"},
            {"path": "/filter?category=20&category=57_62", "method": "GET", "tag": "hpp"},
        ],
    },
    "Log4Shell_SSRF_Markers": {
        "desc": "Log4Shell/JNDI + SSRF-like internal target marker",
        "profile": "mixed",
        "endpoints": [
            {"path": "/search?q=%24%7Bjndi%3Aldap%3A%2F%2F127.0.0.1%3A1389%2Fa%7D", "method": "GET", "tag": "log4shell"},
            {"path": "/search?q=%24%7Bjndi%3Armi%3A%2F%2Finternal.local%3A1099%2Fx%7D", "method": "GET", "tag": "log4shell"},
            {"path": "/proxy?url=http%3A%2F%2F169.254.169.254%2Flatest%2Fmeta-data%2F", "method": "GET", "tag": "ssrf"},
            {"path": "/fetch?target=http%3A%2F%2Flocalhost%3A8080%2Fadmin", "method": "GET", "tag": "ssrf"},
        ],
    },
    "SSTI_XXE_Markers": {
        "desc": "SSTI/XXE-like marker를 query에 인코딩",
        "profile": "mixed",
        "endpoints": [
            {"path": "/search?q=%7B%7B7*7%7D%7D", "method": "GET", "tag": "ssti"},
            {"path": "/render?tpl=%24%7B7*7%7D", "method": "GET", "tag": "ssti"},
            {"path": "/api/xml?data=%3C!DOCTYPE%20a%20%5B%20%3C!ENTITY%20xxe%20SYSTEM%20%22file%3A%2F%2F%2Fetc%2Fpasswd%22%3E%20%5D%3E", "method": "GET", "tag": "xxe"},
            {"path": "/api/xml?entity=%26xxe%3B&probe=external", "method": "GET", "tag": "xxe"},
        ],
    },
    "Webshell_Path_Markers": {
        "desc": "webshell-like path 접근 흔적 생성",
        "profile": "scanner_burst",
        "endpoints": [
            {"path": "/shell.php", "method": "GET", "tag": "webshell", "ua_family": "script"},
            {"path": "/cmd.php?cmd=id", "method": "GET", "tag": "webshell", "ua_family": "script"},
            {"path": "/uploads/webshell.php", "method": "HEAD", "tag": "webshell"},
            {"path": "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", "method": "GET", "tag": "scanner"},
        ],
    },
    "Auth_Context_Markers": {
        "desc": "GET/OPTIONS auth endpoint 반복 접근 context",
        "profile": "mixed",
        "endpoints": [
            {"path": "/login", "method": "GET", "tag": "context"},
            {"path": "/auth/session", "method": "GET", "tag": "context"},
            {"path": "/account/reset?token=abc123", "method": "GET", "tag": "context"},
            {"path": "/api/token/refresh", "method": "OPTIONS", "tag": "context"},
            {"path": "/session/check", "method": "GET", "tag": "context"},
        ],
    },
    "Method_Protocol_Context": {
        "desc": "HEAD/OPTIONS 중심 method/protocol context",
        "profile": "normal",
        "endpoints": [
            {"path": "/", "method": "HEAD", "tag": "context"},
            {"path": "/robots.txt", "method": "HEAD", "tag": "context", "ua_family": "crawler"},
            {"path": "/api/status", "method": "OPTIONS", "tag": "context"},
            {"path": "/search?q=%2527%2520OR%25201%253D1", "method": "HEAD", "tag": "context"},
            {"path": "/very/long/path/" + "a" * 220, "method": "GET", "tag": "context"},
        ],
    },
    "Baseline_Crawler_Mixed": {
        "desc": "정상 browse + crawler baseline 혼합",
        "profile": "baseline",
        "endpoints": [
            {"path": "/robots.txt", "method": "GET", "ua_family": "crawler", "tag": "baseline"},
            {"path": "/sitemap.xml", "method": "GET", "ua_family": "crawler", "tag": "baseline"},
            {"path": "/health", "method": "GET", "ua_family": "script", "tag": "baseline"},
            {"path": "/status", "method": "GET", "tag": "baseline"},
            {"path": "/category/20", "method": "GET", "ua_family": "browser", "tag": "baseline"},
            {"path": "/product/40", "method": "GET", "ua_family": "browser", "tag": "baseline"},
            {"path": "/assets/app.js", "method": "GET", "tag": "noise"},
            {"path": "/assets/site.css", "method": "GET", "tag": "noise"},
        ],
    },
    "Mixed_Context_Heavy": {
        "desc": "정상/노이즈/의심/스캐너 소량 혼합 시나리오",
        "profile": "mixed",
        "endpoints": [
            # baseline 65%
            *[{"path": p, "method": "GET", "tag": "baseline"} for p in ["/", "/category/20", "/product/40", "/search?q=phone", "/assets/main.js", "/assets/site.css", "/health", "/status", "/robots.txt", "/sitemap.xml", "/api/products", "/rest/languages", "/catalog", ]],
            # noise 18%
            *[{"path": p, "method": "GET", "tag": "noise"} for p in ["/search?q=union%20jacket", "/search?q=select%20shoes", "/docs/manual", "/config/backup"]],
            # suspicious 14%
            *[{"path": p, "method": "GET", "tag": "suspicious"} for p in ["/search?q=%3Cscript%3E1%3C%2Fscript%3E", "/products?id=1%20OR%201=1", "/view?file=..%2F..%2Fetc%2Fpasswd"]],
            # scanner-like small
            {"path": "/.env", "method": "GET", "tag": "scanner", "ua_family": "script"},
            {"path": "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", "method": "HEAD", "tag": "scanner", "ua_family": "script"},
        ],
    },
}


PUBLIC_HOST_RE = re.compile(r"^[a-z0-9.-]+$", re.IGNORECASE)


def is_http_url(url: str) -> bool:
    parsed = parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_probably_public_target(base_url: str) -> bool:
    host = parse.urlparse(base_url).hostname or ""
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_loopback or ip.is_private or ip.is_link_local)
    except ValueError:
        return bool(PUBLIC_HOST_RE.match(host))


def normalize_endpoint(endpoint: Any) -> Endpoint:
    if isinstance(endpoint, tuple) and len(endpoint) == 2:
        path, method = endpoint
        normalized = {"path": str(path), "method": str(method).upper(), "ua_family": "random", "referer": None, "tag": "unlabeled"}
    elif isinstance(endpoint, dict):
        normalized = {
            "path": str(endpoint.get("path", "")),
            "method": str(endpoint.get("method", "GET")).upper(),
            "ua_family": str(endpoint.get("ua_family", "random")),
            "referer": endpoint.get("referer"),
            "tag": str(endpoint.get("tag", "unlabeled")),
        }
    else:
        raise ValueError(f"Unsupported endpoint type: {type(endpoint)}")

    if "#" in normalized["path"]:
        raise ValueError(f"Fragment not allowed in endpoint path: {normalized['path']}")
    if normalized["method"] not in ALLOWED_METHODS:
        raise ValueError(f"Method not allowed: {normalized['method']}")
    return normalized


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def mutate_path(path: str, rng: random.Random) -> str:
    parsed = parse.urlsplit(path)
    query_pairs = parse.parse_qsl(parsed.query, keep_blank_values=True)
    mutated: List[Tuple[str, str]] = []
    for key, value in query_pairs:
        new_value = value
        lk = key.lower()
        if lk in {"q", "search", "keyword", "query"}:
            new_value = rng.choice(MUTATION_WORDS)
        elif lk in {"product_id", "id"} and value.isdigit():
            new_value = rng.choice(MUTATION_PRODUCT_IDS)
        elif lk in {"path", "category"}:
            new_value = rng.choice(MUTATION_CATEGORY_PATHS)
        mutated.append((key, new_value))

    clean_path = parsed.path
    if "/category/" in clean_path:
        clean_path = re.sub(r"/category/[^/?]+", f"/category/{rng.choice(MUTATION_CATEGORY_PATHS)}", clean_path)
    if "/product/" in clean_path:
        clean_path = re.sub(r"/product/[^/?]+", f"/product/{rng.choice(MUTATION_PRODUCT_IDS)}", clean_path)

    new_query = parse.urlencode(mutated, doseq=True)
    rebuilt = parse.urlunsplit((parsed.scheme, parsed.netloc, clean_path, new_query, ""))
    if "#" in rebuilt:
        raise ValueError("Mutation generated forbidden fragment")
    return rebuilt


def choose_delay(args: argparse.Namespace, scenario_profile: str, rng: random.Random) -> float:
    if args.min_delay is not None or args.max_delay is not None:
        min_delay = args.min_delay if args.min_delay is not None else 0.1
        max_delay = args.max_delay if args.max_delay is not None else 0.5
    elif args.profile_delay:
        min_delay, max_delay = PROFILE_DELAYS.get(scenario_profile, PROFILE_DELAYS["normal"])
    else:
        min_delay, max_delay = (0.1, 0.5)

    if max_delay < min_delay:
        min_delay, max_delay = max_delay, min_delay
    return rng.uniform(min_delay, max_delay)


def choose_ua(ua_family: str, rng: random.Random) -> Tuple[str, str]:
    if ua_family == "random":
        ua_family = rng.choice(list(USER_AGENTS.keys()))
    if ua_family not in USER_AGENTS:
        ua_family = "browser"
    return ua_family, rng.choice(USER_AGENTS[ua_family])


def build_request_headers(ep: Endpoint, rng: random.Random, xff_pool: List[str] | None = None) -> Dict[str, str]:
    ua_family, ua = choose_ua(ep.get("ua_family", "random"), rng)
    referer = ep.get("referer")
    if referer is None:
        referer = rng.choice(REFERER_POOL)
    headers = {
        "User-Agent": ua,
        "Accept-Language": rng.choice(ACCEPT_LANGUAGES),
    }
    if referer:
        headers["Referer"] = referer
    if xff_pool:
        headers["X-Forwarded-For"] = rng.choice(xff_pool)
    ep["_ua_family_selected"] = ua_family
    return headers


def validate_scenarios(scenarios: Dict[str, Dict[str, Any]]) -> None:
    for scenario_id, scenario in scenarios.items():
        if not scenario.get("desc"):
            raise ValueError(f"Scenario missing desc: {scenario_id}")
        endpoints = scenario.get("endpoints")
        if not endpoints:
            raise ValueError(f"Scenario missing endpoints: {scenario_id}")
        for endpoint in endpoints:
            normalize_endpoint(endpoint)


def load_xff_pool(path: str | None) -> List[str] | None:
    if not path:
        return None
    pool: List[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            ip = line.strip()
            if ip and not ip.startswith("#"):
                pool.append(ip)
    return pool or None


def run_traffic(args: argparse.Namespace) -> Dict[str, Any]:
    if args.count <= 0 and args.duration_minutes <= 0:
        print("[Error] --count 또는 --duration-minutes 중 하나는 양수여야 합니다.")
        sys.exit(1)
    if not is_http_url(args.base_url):
        print("[Error] --base-url must start with http:// or https://")
        sys.exit(1)

    validate_scenarios(SCENARIOS)
    if is_probably_public_target(args.base_url) and not args.allow_public_target:
        print("[Warning] Public target detected. Authorized lab only. Use --allow-public-target to suppress this warning.")

    rng = random.Random(args.seed)
    scenario = SCENARIOS[args.scenario_id]
    endpoints = [normalize_endpoint(ep) for ep in scenario["endpoints"]]
    xff_pool = load_xff_pool(args.xff_pool_file)

    start_time = datetime.now()
    request_count = 0
    http_error_count = 0
    transport_error_count = 0

    method_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    ua_family_counts: Counter[str] = Counter()
    endpoint_unique = set()

    end_at = time.time() + (args.duration_minutes * 60) if args.duration_minutes > 0 else None

    print(f"[*] Started: {args.scenario_id} ({scenario['desc']})")
    print(f"[*] Target : {args.target_name} ({args.base_url})")
    print("[*] Policy : authorized lab only / Apache logs-only interpretation")
    if args.seed is not None:
        print(f"[*] Seed   : {args.seed} (Reproduction Enabled)")
    if args.xff_pool_file:
        print("[*] Note   : X-Forwarded-For는 Apache log format/mod_remoteip 설정 없으면 source_ip를 바꾸지 않습니다.")
        print("[*] Note   : 실제 source IP 다양성은 다중 VM/컨테이너/호스트에서 실행해야 합니다.")

    try:
        while True:
            if args.count > 0 and request_count >= args.count:
                break
            if end_at and time.time() > end_at:
                break

            ep = dict(rng.choice(endpoints))
            path = ep["path"]
            if args.mutate_params:
                path = mutate_path(path, rng)

            method = ep["method"]
            url = build_url(args.base_url, path)
            headers = build_request_headers(ep, rng, xff_pool=xff_pool)
            ua_family = ep.get("_ua_family_selected", "unknown")

            method_counts[method] += 1
            tag_counts[ep.get("tag", "unlabeled")] += 1
            ua_family_counts[str(ua_family)] += 1
            endpoint_unique.add(f"{method} {path}")

            if args.dry_run:
                print(f"[DRY-RUN] {method:7} {url}")
                if args.print_curl:
                    header_flags = " ".join([f"-H {json.dumps(f'{k}: {v}') }" for k, v in headers.items()])
                    print(f"           curl -X {method} {header_flags} {json.dumps(url)}")
            else:
                try:
                    req = request.Request(url, method=method)
                    for k, v in headers.items():
                        req.add_header(k, v)
                    with request.urlopen(req, timeout=5) as resp:
                        _ = resp.read()
                except error.HTTPError:
                    http_error_count += 1
                except Exception:
                    transport_error_count += 1

                time.sleep(choose_delay(args, scenario.get("profile", "normal"), rng))

            request_count += 1
    except KeyboardInterrupt:
        print("\n[!] Stopped by user.")

    finish_time = datetime.now()

    summary = {
        "status": "COMPLETED",
        "scenario_id": args.scenario_id,
        "scenario_desc": scenario["desc"],
        "target_name": args.target_name,
        "base_url": args.base_url,
        "dry_run": bool(args.dry_run),
        "seed": args.seed,
        "mutate_params": bool(args.mutate_params),
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": finish_time.strftime("%Y-%m-%d %H:%M:%S"),
        "request_count": request_count,
        "http_error_count": http_error_count,
        "transport_error_count": transport_error_count,
        "method_counts": dict(method_counts),
        "tag_counts": dict(tag_counts),
        "ua_family_counts": dict(ua_family_counts),
        "endpoint_unique_count": len(endpoint_unique),
    }

    print("\n" + "=" * 60)
    print("Execution Summary (Copy for export reference)")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("=" * 60)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lab Traffic Generator v2 for Apache Access Logs (authorized lab only)",
    )
    parser.add_argument("--base-url", required=True, help="Target Base URL (http/https)")
    parser.add_argument("--scenario-id", choices=sorted(SCENARIOS.keys()), required=True)
    parser.add_argument("--target-name", default="LabServer", help="Target Label")
    parser.add_argument("--count", type=int, default=10, help="Total request count")
    parser.add_argument("--duration-minutes", type=int, default=0, help="Run time in minutes")
    parser.add_argument("--min-delay", type=float, default=None, help="Min delay between requests")
    parser.add_argument("--max-delay", type=float, default=None, help="Max delay between requests")
    parser.add_argument("--profile-delay", action="store_true", help="Use scenario delay profile (normal/scanner/low-and-slow/mixed)")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--dry-run", action="store_true", help="Print plans without sending traffic")
    parser.add_argument("--print-curl", action="store_true", help="Print curl examples in dry-run mode")
    parser.add_argument("--mutate-params", action="store_true", help="Mutate query/path params with seed-reproducible randomness")
    parser.add_argument("--allow-public-target", action="store_true", help="Allow public target warning suppression (authorized lab only)")
    parser.add_argument(
        "--xff-pool-file",
        default=None,
        help="Optional X-Forwarded-For pool file (disabled by default). Without Apache log format/mod_remoteip, source_ip may not change.",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    run_traffic(args)
