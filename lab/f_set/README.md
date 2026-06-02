# F Set Runner Notes

This directory contains Python runners that generate F-set Auth/Login Abuse experiment traffic.

Migration note:

- Runner code has moved to `scripts/lab_runners/f_set/`.
- This `lab/f_set/README.md` is retained as a legacy set note.
- Generated lab outputs remain under `lab/`.

- Use these runners only in approved local lab environments.
- Do not execute them against public external targets.
- The runner does not verify attack outcomes.
- The runner is an experiment harness that records HTTP requests and execution metadata.
- POST bodies are execution-only inputs for scenario construction. They are not visible to the Apache-log-based analysis pipeline, so downstream interpretation must not rely on request body contents.

Current runner:

- `run_f_r2a_auth_scenarios.py`: R2A low-and-slow auth failures, interleaved browse/auth mix, and 200 baseline traffic
- `run_f_r2b_response_delta.py`: R2B response-delta observation runner for existing-account-intended failures, nonexistent-account-intended failures, and lockout-probing-like repeated failures

Interpretation guardrails:

- R2B is for response surface comparison and response delta observation only.
- The runner is limited to response surface comparison and response delta observation only, with no account existence inference, no lockout confirmation, and no auth success inference.
- POST bodies are execution-only inputs for runner scenario construction and are not visible to the Apache-log-based analysis pipeline.

Future runner candidates:

- `run_f_r2c_distributed_auth.py`
