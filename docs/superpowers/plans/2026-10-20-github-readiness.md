# GitHub readiness: minimal remediation plan

Base: PR #2 at c64e8bc; main at b726e5f. No merge, deployment, credential rotation,
or history rewrite is authorized.

1. Audit the complete fetched history and current tree without printing secret values.
2. Remove image-baked credentials from docker/Dockerfile. Document runtime injection,
   backup of the existing n8n key/database, and approval-dependent incident response.
3. Reproduce clean-install defects: missing Telegram package and obsolete transcript
   method hidden by mocks. Repair only those dependency contracts and their tests.
4. Reproduce tests/lint/security scans; reconcile both READMEs with measured counts,
   synthetic evaluation scope, missing schema provisioning and operational limitations.
5. Commit on fix/github-readiness, open a draft PR against main containing PR #2,
   and verify remote commit, diff and CI. Keep PR #2 open; do not merge either PR.
