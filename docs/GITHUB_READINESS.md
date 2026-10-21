# GitHub readiness review — 2026-10-21

## Reviewed remote baseline

- `main`: `23ed9e21ebfc58d7b0d7756e187a5369bb9c6123` (incorporates PR #2 and PR #3).
- PR #2: MERGED (`refactor/restore-professional-narrative-ci`, head `c64e8bc`, merged 2026-10-19).
  CI [39281116693](https://github.com/jraphaelcunha/trend-intelligence-engine/actions/runs/39281116693) succeeded.
- PR #3: MERGED (`fix/github-readiness`, head `d391f9c`, merged 2026-10-21).
  CI [39533332824](https://github.com/jraphaelcunha/trend-intelligence-engine/actions/runs/39533332824) succeeded.
- Main CI: [39533622191](https://github.com/jraphaelcunha/trend-intelligence-engine/actions/runs/39533622191)
  succeeded 100% GREEN on `main` following merge of PR #3.
- Main was reported unprotected. No protection, visibility or deployment setting was changed.

## Independently reproduced evidence

Local environment: clean virtualenv, Python 3.12.14, no service credentials or live calls.
The CI workflow uses Python 3.11; its result for the new PR must be checked separately.

| Check | Result |
|---|---|
| PR #2 baseline `pytest tests/ --cov=src --cov-report=term-missing` | 80 passed, 75% rounded coverage |
| Reliability hardening suite, same command | 85 passed, 76% coverage (722/948 statements) |
| `ruff check src/ tests/` | Passed |
| `pip check` | Passed |
| `pip-audit -r requirements.txt` | No known vulnerabilities in resolved dependencies |
| `bandit -r src/ -t B113` | 0 findings: HTTP timeouts remediated with tailored connect/read tuples |
| Gitleaks 8.30.0 full history, `git --redact --log-opts=--all` | Five JWT findings in removed scripts |
| Manual historical Dockerfile review | Two secret assignments present in all 21 fetched commits |
| Gitleaks current directory + known-secret literal check | No findings; known values absent from current tracked files |
| Offline evals `pytest tests/evals/ -s` | 12 passed; synthetic Recall@1/3/5=1, MRR=1; normalization accuracy/F1=1 |
| Relative README links / `git diff --check` | Passed |

The scanner's default rules missed the Dockerfile secrets. The full-history scan is
**not clean**. Neither token validity nor incident impact was tested. See
[security operations](SECURITY_OPERATIONS.md) for the required owner actions.

## Corrections beyond PR #2

- Remove database password and n8n encryption key from the image definition; require
  runtime values in Compose. No active installation was touched.
- Restore effective `.env` ignore rule by removing its leading BOM; exclude `.env.*`
  except the example. Add safe blank examples for optional/runtime settings.
- Declare the Telegram package and remove module-wide fake package injection from tests.
  A clean install previously failed collection without that fake module.
- Use `YouTubeTranscriptApi().fetch()` with snippet attributes and declare the supported
  major version. The old method did not exist in the resolved dependency. The revised
  success regression failed before the fix and passed afterward; no network was used.
- Correct bilingual counts (82 → 80 → 85), synthetic Recall@1 (75% threshold → 100% measured),
  overbroad lint/adversarial guarantees and setup limitations.

## Reviewer limitations and pending decisions

No Docker build, deployment, live API, database migration, rotation or merge was run.
No SQL bootstrap/schema/RPC definition is supplied; full end-to-end provisioning is
not reproducible from this repository alone. SDK deprecation, embedding-dimension
compatibility, Telegram access control and inherited TLS/n8n configuration remain
explicitly documented limitations. HTTP timeouts remediated with tailored connect/read
limits across fetcher, exporters, and ops scripts (Bandit B113 resolved).

Antigravity: browser inventory contained no available session/tab, so task submission
and response retrieval could not be demonstrated. Work used GitHub and local tools.

PR #2 and PR #3 have both been reviewed and merged into `main`. The remote baseline is
now 100% GREEN on GitHub Actions (Run ID `39533622191`). Reliability hardening with tailored
HTTP timeouts is tracked on dedicated branch `fix/final-readiness-audit` with PR verification.
