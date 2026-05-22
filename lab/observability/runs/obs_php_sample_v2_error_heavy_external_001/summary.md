# obs_php_sample_v2_error_heavy_external_001 Summary

## Run Metadata

- `run_id`: `obs_php_sample_v2_error_heavy_external_001`
- `topology`: direct PHP app, controlled external client
- `log_format_version`: `apache_security_io_v2`
- `client`: `192.168.56.114`
- `Apache/PHP v2 server local_ip`: `192.168.56.115`
- `source`: `observability_raw_log`
- `total_count`: `12`

## Purpose

This run checks whether the PHP sample v2 error-heavy distribution remains stable when the requests come from a controlled external client instead of localhost/internal execution.

It is not an attacker attribution test, exploit success test, upload success test, login success test, file exposure test, or remoteIP test.

## Identity / Header Observations

- `client_ip_source=direct`
- `src_ip=192.168.56.114`
- `peer_ip=192.168.56.114`
- `remoteip_proxy_chain`: not present
- `x_forwarded_for`: not present
- `x_real_ip`: not present
- `forwarded`: not present
- `req_host=apache-log-test-v2.local`

Interpretation:

- The controlled external client path `192.168.56.114 -> 192.168.56.115` is confirmed.
- Without `mod_remoteip`, the direct peer identity fields are preserved as observed metadata.
- These fields are not attacker identity proof.

## Candidate Policy Distribution

| policy_class | count |
|---|---:|
| `context_candidate_auth_failure` | 1 |
| `context_candidate_probe` | 4 |
| `context_candidate_upload_failure` | 1 |
| `demotion_candidate_status_error_only` | 3 |
| `keep_candidate_payload` | 3 |

Observed shape:

- `candidate_count=12`
- The distribution matches the local/internal `obs_php_sample_v2_error_heavy_001_current_dryrun` shape.
- External client identity did not change the conservative bucket split.

## Candidate Interpretation

- EH10 traversal-like request remains `keep_candidate_payload`.
- EH11 SQLi-like request remains `keep_candidate_payload`.
- EH12 XSS-like request remains `keep_candidate_payload`.
- EH01 500 and EH02 403 remain status/error-only diagnostic candidates.
- EH04 login POST 401 remains auth failure context.
- EH06 upload POST 400 remains upload failure context.
- EH03/EH07/EH08/EH09 probe-like paths remain probe context.

These are request-pattern and context observations only. They are not exploit success, compromise, DB impact, file exposure, login success, or upload persistence evidence.

## Scenario Label Note

The generated `candidate_policy_explanation.md` for this external run displayed `scenario=-` for all candidates, even though the security export preserved `scenario=EHxx` in the query string and `obs-error-heavy/EHxx` in the User-Agent.

This is recorded as a diagnostic UX follow-up candidate. It does not affect prepare/scoring/filtering, candidate counts, or policy classification.

## Guardrail Notes

- `status_code=200` is not attack success or compromise evidence.
- `status_code=403/404/500` is not vulnerability, exploit success, file exposure, or compromise evidence.
- `response_body_bytes`, `resp_content_type`, and `text/html` do not prove file exposure or internal result disclosure.
- POST metadata alone does not prove login success or upload persistence.
- Raw POST body, response body, DB results, and browser execution are not available from Apache logs-only input and must not be inferred.
- `src_ip`/`peer_ip` and client headers are observations, not attribution proof.
- prepare/scoring/filtering changed: no.
- broad demotion changed: no.
