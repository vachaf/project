#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실험용 Apache 로그 흔적 생성기 (Lab Traffic Generator)
- 위치: scripts/generate_lab_traffic.py
- 목적: 분석 파이프라인 검증용 원천 로그 생성 (Exploit 성공 목적 없음)
- 특징: GET/HEAD/OPTIONS 중심, Fragment 금지, Seed 기반 재현성, 에러 집계 이원화
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime
from urllib import request, error

# --- 시나리오 정의 (Fragment '#' 사용 금지, 의심 경로는 완화된 버전 사용) ---
SCENARIOS = {
    "JuiceShop_Normal": {
        "desc": "Juice Shop 정상 API 탐색 패턴",
        "endpoints": [
            ("/", "GET"), 
            ("/rest/products/search?q=apple", "GET"),
            ("/rest/products/search?q=juice", "GET"),
            ("/api/Products", "GET"), 
            ("/rest/languages", "GET"),
            ("/rest/user/login", "OPTIONS"), 
            ("/rest/products/1/reviews", "GET")
        ]
    },
    "OpenCart_Normal": {
        "desc": "OpenCart 정상 커머스 이용 패턴",
        "endpoints": [
            ("/index.php?route=common/home", "GET"),
            ("/index.php?route=product/category&path=20", "GET"),
            ("/index.php?route=product/product&product_id=40", "GET"),
            ("/index.php?route=product/search&search=phone", "GET"),
            ("/index.php?route=information/contact", "GET")
        ]
    },
    "Static_Noise": {
        "desc": "정적 리소스 및 봇 노이즈 (오탐 억제 검증용)",
        "endpoints": [
            ("/robots.txt", "GET"), 
            ("/favicon.ico", "GET"),
            ("/sitemap.xml", "GET"), 
            ("/assets/public/main.js", "GET"),
            ("/catalog/view/theme/default/stylesheet/stylesheet.css", "GET")
        ]
    },
    "ScannerBurst": {
        "desc": "취약점 스캐너 탐색 흔적 (민감 경로 위주)",
        "endpoints": [
            ("/.env", "GET"), 
            ("/.git/config", "GET"), 
            ("/wp-login.php", "GET"),
            ("/admin/config.php", "GET"), 
            ("/phpmyadmin/", "HEAD"), 
            ("/shell.php", "GET"),
            ("/backup.sql", "GET")
        ]
    },
    "LowAndSlow": {
        "desc": "저속 의심 조사 흔적 (완화된 경로 사용)",
        "endpoints": [
            ("/view?file=..%2F..%2Fetc%2Fpasswd", "GET"),
            ("/config/backup", "GET"),
            ("/server-status", "GET"),
            ("/cgi-bin/test-cgi", "GET"),
            ("/admin/backup", "GET")
        ]
    },
    "SuspiciousQueryMix": {
        "desc": "의심 문자열 혼합 요청 (SQLi/XSS/LFI 흔적)",
        "endpoints": [
            ("/search?q=%3Cscript%3Ealert(1)%3C/script%3E", "GET"),
            ("/products?id=1%20OR%201=1", "GET"),
            ("/view?file=../../../../etc/passwd", "GET"),
            ("/search?q=' OR '1'='1", "GET")
        ]
    }
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "LabTrafficGenerator/1.0 (Experimental Tool)",
    "curl/8.1.2"
]

def run_traffic(args):
    # 무한 실행 방지 로직
    if args.count <= 0 and args.duration_minutes <= 0:
        print("[Error] --count 또는 --duration-minutes 중 하나는 양수여야 합니다.")
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)

    scenario = SCENARIOS[args.scenario_id]
    start_time = datetime.now()
    request_count = 0
    http_error_count = 0
    transport_error_count = 0
    
    end_at = time.time() + (args.duration_minutes * 60) if args.duration_minutes > 0 else None

    print(f"[*] Started: {args.scenario_id} ({scenario['desc']})")
    print(f"[*] Target : {args.target_name} ({args.base_url})")
    if args.seed is not None:
        print(f"[*] Seed   : {args.seed} (Reproduction Enabled)")
    
    try:
        while True:
            if args.count > 0 and request_count >= args.count: break
            if end_at and time.time() > end_at: break

            path, method = random.choice(scenario['endpoints'])
            url = f"{args.base_url.rstrip('/')}/{path.lstrip('/')}"
            
            if args.dry_run:
                print(f"[DRY-RUN] {method:7} {url}")
            else:
                try:
                    req = request.Request(url, method=method)
                    req.add_header("User-Agent", random.choice(USER_AGENTS))
                    with request.urlopen(req, timeout=5) as resp:
                        _ = resp.read()
                except error.HTTPError as e:
                    http_error_count += 1 # 403, 404 등 서버가 보낸 에러
                except Exception:
                    transport_error_count += 1 # 타임아웃, 연결 실패 등
                
                # Dry-run이 아닐 때만 실제 지연 적용
                time.sleep(random.uniform(args.min_delay, args.max_delay))

            request_count += 1
            
    except KeyboardInterrupt:
        print("\n[!] Stopped by user.")

    finish_time = datetime.now()
    
    summary = {
        "status": "COMPLETED",
        "scenario_id": args.scenario_id,
        "target_name": args.target_name,
        "base_url": args.base_url,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": finish_time.strftime("%Y-%m-%d %H:%M:%S"),
        "request_count": request_count,
        "http_error_count": http_error_count,
        "transport_error_count": transport_error_count
    }
    
    print("\n" + "="*60)
    print("Execution Summary (Copy for export reference)")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lab Traffic Generator for Apache Access Logs")
    parser.add_argument("--base-url", required=True, help="Target Base URL")
    parser.add_argument("--scenario-id", choices=sorted(SCENARIOS.keys()), required=True)
    parser.add_argument("--target-name", default="LabServer", help="Target Label")
    parser.add_argument("--count", type=int, default=10, help="Total request count")
    parser.add_argument("--duration-minutes", type=int, default=0, help="Run time in minutes")
    parser.add_argument("--min-delay", type=float, default=0.1)
    parser.add_argument("--max-delay", type=float, default=0.5)
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--dry-run", action="store_true", help="Print plans without sending traffic")
    
    args = parser.parse_args()
    run_traffic(args)