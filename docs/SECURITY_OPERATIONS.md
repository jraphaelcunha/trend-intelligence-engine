# Security operations and deployment hold

## Confirmed exposure

The repository is public. A database password and n8n encryption key were embedded
in `docker/Dockerfile`, including commit `bbeeb24`. They have been removed from the
tracked image definition on `main` (PR #3 merged), but remain in Git history and possibly previously built
images. Full-history Gitleaks also detected JWT-shaped credentials in five removed
scripts at that commit. No credential was tested against a live service; current
validity and privileges are unknown. Treat the exposed values as compromised until
an owner verifies revocation. A clean scan of only a PR diff is not a clean history.

## Before any deployment (owner approval required)

1. Inventory current services, database users, n8n credential storage and image consumers.
2. Back up the database and securely preserve the **existing** n8n encryption key.
   Verify the recovery procedure. Do not generate or substitute a key on an existing
   n8n database: stored credentials may become unreadable.
3. Supply `N8N_ENCRYPTION_KEY` and `DB_POSTGRESDB_PASSWORD` via the deployment's
   secret configuration. Initially preserve the existing key to maintain compatibility.
   Removing literals from the Dockerfile does not configure Cloud Run secrets.
4. Plan and approve database-password/token rotation with coordinated consumer
   updates. Handle n8n re-encryption separately with a tested backup/restore plan.
5. Complete and verify the approved password/token revocations and consumer updates
   before lifting the deployment hold. An owner must explicitly accept any temporary
   continued use of the exposed encryption key while a safe re-encryption migration
   is prepared. Only then approve deployment and verify health and credential decryption.
   PR #3 has been merged into `main`. Deployment hold, credential rotation, and historical secret remediation remain required owner actions before production deployment.

## Remaining operational limitations

- The image still contains environment-specific host/URL defaults. Review these before
   any use outside the original installation. Docker Compose uses the configured remote
   PostgreSQL service; it is **not** a self-contained offline database environment.
- PostgreSQL certificate verification is disabled in the inherited image configuration.
   Correct trust/certificate configuration needs validation before enabling verification.
- Cloud Run deployment permits unauthenticated access at the platform layer. Verify
   application authentication and network exposure separately; no live access was tested.
- n8n command execution and environment access remain enabled for existing workflows.
   Restrict editor access and do not run untrusted workflows.
- Telegram has no user/chat allowlist in the current implementation. Do not expose the
   bot to untrusted users with sensitive dossiers or unrestricted billable API access.
- HTTP calls previously flagged by Bandit (B113) have been remediated with tailored connect/read timeouts across fetcher, exporters, and ops scripts, validated by explicit timeout tests.
- No database bootstrap migrations/RPC definition are included. A working existing
  schema is required; tests mock the database and do not prove production readiness.
- `google.generativeai` emits an upstream end-of-support warning. SDK migration is
  deferred to a separate tested change. Embedding dimension/model compatibility needs
  a controlled live check; neither code path requests a fixed output dimensionality.

## Safe verification without service credentials

Use a clean virtual environment and no populated `.env` file. Run:

```bash
pip install -r requirements.txt
ruff check src/ tests/
pytest tests/ --cov=src --cov-report=term-missing
pytest tests/evals/ -s
```

For a full-history secret scan (Gitleaks 8.30.0 was used), keep reports private and
redacted; never commit a report containing credential values:

```bash
gitleaks git --redact --log-opts=--all .
```

Gitleaks did not detect the two Dockerfile assignments with its default rules;
manual configuration review identified them. Scanner success alone is insufficient.
