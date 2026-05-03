# H Set R4 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T19:59:16+09:00
- ended_at: 2026-05-03T19:59:37+09:00
- request_count: 22
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- note: request body content and response body content are not stored

## Results

| scenario_id | request_label | method | path | status_code | response_headers_count | response_body_bytes_discarded | duration_ms | error |
|---|---|---|---|---|---|---|---|---|
| H-R4-01 | mixed_basic_root_request | GET | / | 200 | 15 | 75002 | 63.98 |  |
| H-R4-01 | mixed_basic_app_js_request | GET | /assets/app.js | 200 | 15 | 75002 | 49.09 |  |
| H-R4-01 | mixed_basic_favicon_request | GET | /favicon.ico | 200 | 15 | 75002 | 29.53 |  |
| H-R4-01 | mixed_basic_env_probe_request | GET | /.env | 200 | 15 | 75002 | 17.12 |  |
| H-R4-01 | mixed_basic_wp_login_probe_request | GET | /wp-login.php | 200 | 15 | 75002 | 17.18 |  |
| H-R4-01 | mixed_basic_backup_probe_request | GET | /backup.zip | 200 | 15 | 75002 | 19.86 |  |
| H-R4-01 | mixed_basic_robots_request | GET | /robots.txt | 200 | 12 | 28 | 17.75 |  |
| H-R4-02 | benign_static_root_request | GET | / | 200 | 15 | 75002 | 13.39 |  |
| H-R4-02 | benign_static_app_js_request | GET | /assets/app.js | 200 | 15 | 75002 | 19.67 |  |
| H-R4-02 | benign_static_style_css_request | GET | /assets/style.css | 200 | 15 | 75002 | 18.23 |  |
| H-R4-02 | benign_static_favicon_request | GET | /favicon.ico | 200 | 15 | 75002 | 15.92 |  |
| H-R4-02 | benign_static_robots_request | GET | /robots.txt | 200 | 12 | 28 | 8.95 |  |
| H-R4-03 | scanner_only_env_probe_request | GET | /.env | 200 | 15 | 75002 | 18.59 |  |
| H-R4-03 | scanner_only_wp_login_probe_request | GET | /wp-login.php | 200 | 15 | 75002 | 19.0 |  |
| H-R4-03 | scanner_only_backup_probe_request | GET | /backup.zip | 200 | 15 | 75002 | 12.21 |  |
| H-R4-03 | scanner_only_server_status_probe_request | GET | /server-status | 403 | 5 | 279 | 9.7 |  |
| H-R4-04 | mixed_crawler_root_request | GET | / | 200 | 15 | 75002 | 6.87 |  |
| H-R4-04 | mixed_crawler_robots_googlebot_request | GET | /robots.txt | 200 | 12 | 28 | 9.17 |  |
| H-R4-04 | mixed_crawler_sitemap_googlebot_request | GET | /sitemap.xml | 200 | 15 | 75002 | 20.83 |  |
| H-R4-04 | mixed_crawler_products_generic_request | GET | /products/ | 200 | 15 | 75002 | 26.42 |  |
| H-R4-04 | mixed_crawler_env_probe_request | GET | /.env | 200 | 15 | 75002 | 14.86 |  |
| H-R4-04 | mixed_crawler_backup_probe_request | GET | /backup.zip | 200 | 15 | 75002 | 17.37 |  |

## Interpretation Guardrails

- Results are mixed baseline/crawler/scanner context only.
- No crawler authenticity inference, no static file existence inference, no WordPress presence inference, no file exposure inference, and no attack-success inference are allowed.
- Mixed same-window requests should not be over-collapsed into one successful attack narrative.
