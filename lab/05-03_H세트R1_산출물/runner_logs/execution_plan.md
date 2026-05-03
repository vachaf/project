# H Set R1 Execution Plan

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- request_count: 8
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- safety: approved local lab only; public target execution is blocked by default
- note: request body content and response body content are not stored

## Requests

| # | scenario_id | runner label | request_label | method | path | expected_response | scaled_sleep_after_sec |
|---|---|---|---|---|---|---|---|
| 1 | H-R1-01 | favicon_baseline | favicon_request | GET | /favicon.ico | any | 1.0 |
| 2 | H-R1-02 | robots_txt_baseline | robots_txt_request | GET | /robots.txt | any | 1.0 |
| 3 | H-R1-03 | sitemap_xml_baseline | sitemap_xml_request | GET | /sitemap.xml | any | 1.0 |
| 4 | H-R1-04 | js_asset_baseline | js_asset_request | GET | /assets/app.js | any | 1.0 |
| 5 | H-R1-05 | css_asset_baseline | css_asset_request | GET | /assets/style.css | any | 1.0 |
| 6 | H-R1-06 | image_asset_baseline | image_asset_request | GET | /images/logo.png | any | 1.0 |
| 7 | H-R1-07 | health_check_baseline | health_check_request | GET | /api/health | any | 1.0 |
| 8 | H-R1-08 | normal_get_baseline | normal_get_request | GET | / | any | 0.0 |

## Interpretation Guardrails

- This runner is baseline/reference harness only and does not verify attack success.
- Static asset existence, robots/sitemap content, JS/CSS/image meaning, and health endpoint health must not be inferred.
- Status code, response body byte count, and User-Agent alone are not sufficient to label normality, attack, or exposure success.
- Request body content and response body content are not written to disk.
