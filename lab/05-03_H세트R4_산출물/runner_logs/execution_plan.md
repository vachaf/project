# H Set R4 Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 22
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- safety: approved local lab only; public target execution is blocked by default
- note: request body content and response body content are not stored

## Requests

| # | scenario_id | runner label | request_label | method | path | user_agent | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|---|
| 1 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_root_request | GET | / | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 2 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_app_js_request | GET | /assets/app.js | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 3 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_favicon_request | GET | /favicon.ico | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 4 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_env_probe_request | GET | /.env | `GenericScanner/1.0` | any | 1.0 |
| 5 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_wp_login_probe_request | GET | /wp-login.php | `GenericScanner/1.0` | any | 1.0 |
| 6 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_backup_probe_request | GET | /backup.zip | `GenericScanner/1.0` | any | 1.0 |
| 7 | H-R4-01 | mixed_benign_scanner_basic | mixed_basic_robots_request | GET | /robots.txt | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 8 | H-R4-02 | benign_static_only | benign_static_root_request | GET | / | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 9 | H-R4-02 | benign_static_only | benign_static_app_js_request | GET | /assets/app.js | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 10 | H-R4-02 | benign_static_only | benign_static_style_css_request | GET | /assets/style.css | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 11 | H-R4-02 | benign_static_only | benign_static_favicon_request | GET | /favicon.ico | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 12 | H-R4-02 | benign_static_only | benign_static_robots_request | GET | /robots.txt | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 13 | H-R4-03 | scanner_sensitive_only | scanner_only_env_probe_request | GET | /.env | `GenericScanner/1.0` | any | 1.0 |
| 14 | H-R4-03 | scanner_sensitive_only | scanner_only_wp_login_probe_request | GET | /wp-login.php | `GenericScanner/1.0` | any | 1.0 |
| 15 | H-R4-03 | scanner_sensitive_only | scanner_only_backup_probe_request | GET | /backup.zip | `GenericScanner/1.0` | any | 1.0 |
| 16 | H-R4-03 | scanner_sensitive_only | scanner_only_server_status_probe_request | GET | /server-status | `GenericScanner/1.0` | any | 1.0 |
| 17 | H-R4-04 | mixed_static_crawler_scanner | mixed_crawler_root_request | GET | / | `Mozilla/5.0 regression-browser` | any | 1.0 |
| 18 | H-R4-04 | mixed_static_crawler_scanner | mixed_crawler_robots_googlebot_request | GET | /robots.txt | `Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)` | any | 1.0 |
| 19 | H-R4-04 | mixed_static_crawler_scanner | mixed_crawler_sitemap_googlebot_request | GET | /sitemap.xml | `Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)` | any | 1.0 |
| 20 | H-R4-04 | mixed_static_crawler_scanner | mixed_crawler_products_generic_request | GET | /products/ | `GenericCrawler/1.0` | any | 1.0 |
| 21 | H-R4-04 | mixed_static_crawler_scanner | mixed_crawler_env_probe_request | GET | /.env | `GenericScanner/1.0` | any | 1.0 |
| 22 | H-R4-04 | mixed_static_crawler_scanner | mixed_crawler_backup_probe_request | GET | /backup.zip | `GenericScanner/1.0` | any | 0.0 |

## Interpretation Guardrails

- This runner is mixed baseline/scanner context harness only and does not verify crawler authenticity, static file existence, file exposure, app presence, or attack success.
- Baseline/static/crawler-like requests and scanner-like sensitive-path requests should be separated when they appear in the same src_ip/time window.
- Status code, response body byte count, response header count, and User-Agent alone are not sufficient to infer crawler authenticity, file disclosure, WordPress presence, backup exposure, or compromise.
- Request body content and response body content are not written to disk.
