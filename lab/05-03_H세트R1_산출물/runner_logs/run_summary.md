# H Set R1 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T13:52:31+09:00
- ended_at: 2026-05-03T13:52:38+09:00
- request_count: 8
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- note: request body content and response body content are not stored

## Results

| scenario_id | request_label | method | path | status_code | response_headers_count | response_body_bytes_discarded | duration_ms | error |
|---|---|---|---|---|---|---|---|---|
| H-R1-01 | favicon_request | GET | /favicon.ico | 200 | 15 | 75002 | 52.79 |  |
| H-R1-02 | robots_txt_request | GET | /robots.txt | 200 | 12 | 28 | 5.3 |  |
| H-R1-03 | sitemap_xml_request | GET | /sitemap.xml | 200 | 15 | 75002 | 14.35 |  |
| H-R1-04 | js_asset_request | GET | /assets/app.js | 200 | 15 | 75002 | 41.13 |  |
| H-R1-05 | css_asset_request | GET | /assets/style.css | 200 | 15 | 75002 | 18.17 |  |
| H-R1-06 | image_asset_request | GET | /images/logo.png | 200 | 15 | 75002 | 20.03 |  |
| H-R1-07 | health_check_request | GET | /api/health | 500 | 11 | 3025 | 8.94 |  |
| H-R1-08 | normal_get_request | GET | / | 200 | 15 | 75002 | 9.0 |  |

## Interpretation Guardrails

- Results are baseline/reference context only.
- No static file existence inference, no robots/sitemap content inference, no health endpoint health inference, and no attack-success inference are allowed.
- Status code, response body byte count, and User-Agent alone are not sufficient evidence of attack or exposure success.
