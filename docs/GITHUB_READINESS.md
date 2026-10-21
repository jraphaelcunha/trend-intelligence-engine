# GitHub readiness review — 2026-10-20

## Reviewed remote baseline

- `main`: `b726e5f089ea37ea3f5619de790f7c768f9063f3`.
- PR #2: open, mergeable, head `c64e8bc6a08c68186541c6790da7de01ef4d636b`;
  eight commits, 27 changed files, +1667/-84 relative to main.
- Main CI [39220417775](https://github.com/jraphaelcunha/trend-intelligence-engine/actions/runs/39220417775)
  failed importing nonexistent `AnalysisResult` in conftest. Main lint was nonblocking.
- PR #2 CI [39281116693](https://github.com/jraphaelcunha/trend-intelligence-engine/actions/runs/39281116693)
  succeeded on its exact head. The proposed branch includes PR #2 and minimal follow-ups.
- Main was reported unprotected. No protection, visibility or deployment setting was changed.

## Independently reproduced evidence

Local environment: clean virtualenv, Python 3.12.14, no service credentials or live calls.
The CI workflow uses Python 3.11; its result for the new PR must be checked separately.

| Check | Result |
|---|---|
| PR #2 baseline `pytest tests/ --cov=src --cov-report=term-missing` | 80 passed, 75% rounded coverage |
| Follow-up suite, same command | 80 passed, 75% coverage (710/948 statements) |
| `ruff check src/ tests/` | Passed |
| `pip check` | Passed |
| `pip-audit -r requirements.txt` | No known vulnerabilities in resolved dependencies |
| `bandit -r src scripts` | Six medium B113 findings: HTTP requests without timeouts |
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
- Correct bilingual counts (82 → 80), synthetic Recall@1 (75% threshold → 100% measured),
  overbroad lint/adversarial guarantees and setup limitations.

## Reviewer limitations and pending decisions

No Docker build, deployment, live API, database migration, rotation or merge was run.
No SQL bootstrap/schema/RPC definition is supplied; full end-to-end provisioning is
not reproducible from this repository alone. SDK deprecation, embedding-dimension
compatibility, Telegram access control and inherited TLS/n8n configuration remain
explicitly documented limitations. HTTP timeouts require a separate small follow-up.

Antigravity: browser inventory contained no available session/tab, so task submission
and response retrieval could not be demonstrated. Work used GitHub and local tools.

The new draft PR is an **alternative to merging PR #2 separately**, not a second
independent feature. Both remain open pending owner review. Check the new PR's exact
head and CI before approval; a local green run alone is insufficient.
