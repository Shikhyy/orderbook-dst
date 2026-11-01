# AI Use

## Tools used

| Step | Tool | Version | Use |
|---|---|---|---|
| Scaffold to M11 | Antigravity (Claude Sonnet 4.6 thinking) | 2026-11-01 | Code generation, test writing, document drafting |

## Review steps

1. The author reads each file the agent creates before the commit.
2. The author runs `make test` and `make validate` after each milestone.
3. The author reads the failure cards and checks each claim against result files.
4. The author checks `AI_USE.md` against the submission requirements before upload.

## What the agent did not do

- The agent did not run model API calls.
- The agent did not change a rule to lower or raise a model pass rate.
- The agent did not invent result files.
