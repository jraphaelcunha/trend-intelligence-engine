"""Regression checks for secret patterns missed by default scanners in Docker files.

Only synthetic dummy strings are used. These tests do not inspect real credentials.
The Gitleaks action still scans new commits separately; historic incidents need rotation.
"""

import re
from pathlib import Path

import tomllib

CONFIG = Path(__file__).resolve().parents[2] / "gitleaks.toml"


def _rules():
    with CONFIG.open("rb") as f:
        data = tomllib.load(f)
    assert data["extend"]["useDefault"] is True
    return {rule["id"]: re.compile(rule["regex"]) for rule in data["rules"]}


def test_custom_rules_detect_inline_runtime_secrets():
    rules = _rules()
    assert rules["trend-inline-n8n-encryption-key"].search(
        "ENV N8N_ENCRYPTION_KEY=syntheticExampleKey1234567890123"
    )
    assert rules["trend-inline-postgres-password"].search(
        'ENV DB_POSTGRESDB_PASSWORD="sampleTestPassword123"'
    )


def test_custom_rules_ignore_runtime_references_and_empty_examples():
    rules = _rules()
    assert not rules["trend-inline-n8n-encryption-key"].search(
        "ENV N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}"
    )
    assert not rules["trend-inline-postgres-password"].search(
        "DB_POSTGRESDB_PASSWORD=${DB_POSTGRESDB_PASSWORD}"
    )
    assert not rules["trend-inline-n8n-encryption-key"].search(
        "N8N_ENCRYPTION_KEY="
    )
    assert not rules["trend-inline-postgres-password"].search(
        "# ENV DB_POSTGRESDB_PASSWORD=sampleTestPassword123"
    )
