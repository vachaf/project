# H Set R2 Execution Plan

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
| 1 | H-R2-01 | robots_googlebot_like | robots_googlebot_request | GET | /robots.txt | any | 1.0 |
| 2 | H-R2-02 | sitemap_googlebot_like | sitemap_googlebot_request | GET | /sitemap.xml | any | 1.0 |
| 3 | H-R2-03 | products_generic_crawler | products_generic_crawler_request | GET | /products/ | any | 1.0 |
| 4 | H-R2-04 | category_generic_crawler | category_generic_crawler_request | GET | /category/ | any | 1.0 |
| 5 | H-R2-05 | normal_browser_get | normal_browser_get_request | GET | / | any | 1.0 |
| 6 | H-R2-06 | repeated_crawler_browse_x3 | repeated_crawler_robots_request | GET | /robots.txt | any | 2.0 |
| 7 | H-R2-06 | repeated_crawler_browse_x3 | repeated_crawler_sitemap_request | GET | /sitemap.xml | any | 2.0 |
| 8 | H-R2-06 | repeated_crawler_browse_x3 | repeated_crawler_products_request | GET | /products/ | any | 0.0 |

## Interpretation Guardrails

- This runner is baseline/reference harness only and does not verify actual crawler authenticity or attack success.
- Googlebot-like/Bingbot-like User-Agent strings are spoofable and must not be treated as authenticated search-engine crawlers.
- Robots/sitemap content, site structure, and product/category page existence must not be inferred.
- Status code, response body byte count, and User-Agent alone are not sufficient to label normality, attack, disclosure, or success.
- Request body content and response body content are not written to disk.
