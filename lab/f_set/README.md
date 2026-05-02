# F Set Runner Notes

This directory contains Python runners that generate F-set Auth/Login Abuse experiment traffic.

- Use these runners only in approved local lab environments.
- Do not execute them against public external targets.
- The runner does not verify attack success.
- The runner is an experiment harness that records HTTP requests and execution metadata.
- POST bodies are execution-only inputs for scenario construction. They are not visible to the Apache-log-based analysis pipeline, so downstream interpretation must not rely on request body contents.

Current runner:

- `run_f_r2a_auth_scenarios.py`: R2A low-and-slow auth failures, interleaved browse/auth mix, and 200 baseline traffic

Future runner candidates:

- `run_f_r2b_response_delta.py`
- `run_f_r2c_distributed_auth.py`
