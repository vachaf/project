# H Set R2 Run Summary

- mode: execute
- base_url: http://192.168.56.105
- scenario: all
- started_at: 2026-05-03T14:48:12+09:00
- ended_at: 2026-05-03T14:48:21+09:00
- request_count: 8
- sleep_scale: 1.0
- timeout_sec: 10.0
- target_class: private-ip
- transport: urllib.request over http/https
- note: request body content and response body content are not stored

## Results

| scenario_id | request_label | method | path | status_code | response_headers_count | response_body_bytes_discarded | duration_ms | error |
|---|---|---|---|---|---|---|---|---|
| H-R2-01 | robots_googlebot_request | GET | /robots.txt | 200 | 12 | 28 | 25.52 |  |
| H-R2-02 | sitemap_googlebot_request | GET | /sitemap.xml | 200 | 15 | 75002 | 21.64 |  |
| H-R2-03 | products_generic_crawler_request | GET | /products/ | 200 | 15 | 75002 | 26.99 |  |
| H-R2-04 | category_generic_crawler_request | GET | /category/ | 200 | 15 | 75002 | 13.52 |  |
| H-R2-05 | normal_browser_get_request | GET | / | 200 | 15 | 75002 | 17.27 |  |
| H-R2-06 | repeated_crawler_robots_request | GET | /robots.txt | 200 | 12 | 28 | 4.36 |  |
| H-R2-06 | repeated_crawler_sitemap_request | GET | /sitemap.xml | 200 | 15 | 75002 | 15.64 |  |
| H-R2-06 | repeated_crawler_products_request | GET | /products/ | 200 | 15 | 75002 | 16.32 |  |

## Interpretation Guardrails

- Results are baseline/reference context only.
- No crawler authenticity inference, no robots/sitemap content inference, no site-structure inference, and no product/category existence inference are allowed.
- Status code, response body byte count, and User-Agent alone are not sufficient evidence of attack, disclosure, or exposure success.
