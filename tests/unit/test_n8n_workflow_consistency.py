"""
Static consistency and contract tests for n8n workflow and container packaging.

Validates that:
1. n8n/workflow_trend_engine.json is valid JSON with expected structure.
2. All python scripts invoked in executeCommand nodes exist in the repository tree.
3. n8n parameter expressions follow valid n8n template syntax (leading '=', balanced '{{ ... }}').
4. Docker packaging contracts (Dockerfile COPY and Compose volumes) provide the referenced script directories.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW_PATH = REPO_ROOT / "n8n" / "workflow_trend_engine.json"
DOCKERFILE_PATH = REPO_ROOT / "docker" / "Dockerfile"
COMPOSE_PATH = REPO_ROOT / "docker" / "docker-compose.yml"


@pytest.fixture(scope="module")
def workflow_data():
    """Load and parse the n8n workflow JSON file."""
    assert WORKFLOW_PATH.is_file(), f"Workflow file not found at {WORKFLOW_PATH}"
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_workflow_json_structure(workflow_data):
    """Verify top-level keys and nodes structure in workflow JSON."""
    assert "nodes" in workflow_data, "Workflow JSON missing 'nodes' key"
    assert "connections" in workflow_data, "Workflow JSON missing 'connections' key"
    assert isinstance(workflow_data["nodes"], list)
    assert len(workflow_data["nodes"]) >= 7


def test_execute_command_nodes_script_existence(workflow_data):
    """
    Verify that every script referenced in executeCommand nodes exists in the repository.
    Maps container root /data/project/<dir>/<script> to local repo <dir>/<script>.
    """
    execute_nodes = [
        n for n in workflow_data["nodes"]
        if n.get("type") == "n8n-nodes-base.executeCommand"
    ]
    assert len(execute_nodes) >= 5, f"Expected at least 5 executeCommand nodes, found {len(execute_nodes)}"

    script_pattern = re.compile(r'/data/project/((?:src|scripts)/[^\s"\']+?\.py)')

    checked_scripts = []
    for node in execute_nodes:
        command = node.get("parameters", {}).get("command", "")
        matches = script_pattern.findall(command)
        assert matches, f"Node '{node.get('name')}' executeCommand has no recognizable /data/project/ script path in command: {command}"

        for script_rel_path in matches:
            local_path = REPO_ROOT / script_rel_path
            assert local_path.is_file(), (
                f"Node '{node.get('name')}' references '{script_rel_path}' inside container, "
                f"but local file does not exist at {local_path}"
            )
            checked_scripts.append(script_rel_path)

    assert "src/collector.py" in checked_scripts
    assert "src/scraper.py" in checked_scripts
    assert "src/analyzer.py" in checked_scripts
    assert "src/fetcher.py" in checked_scripts
    assert "scripts/ops/mark_as_exported.py" in checked_scripts


def test_n8n_expression_syntax(workflow_data):
    """
    Verify expression syntax in workflow parameters:
    - Parameters with dynamic expressions must start with '='
    - Expression interpolations must use double braces '{{ ... }}'
    - Disallows invalid single brace template interpolation '{ $('...')... }'
    """
    for node in workflow_data["nodes"]:
        node_name = node.get("name", "Unknown")
        params = node.get("parameters", {})

        for param_key, param_val in params.items():
            if isinstance(param_val, str):
                # Disallow single curly leak e.g. { $('node').item... }
                single_curly_leak = re.search(r'(?<!\{)\{\s*\$\([^\}]+\)[^\}]*\}(?!\})', param_val)
                assert not single_curly_leak, (
                    f"Node '{node_name}' parameter '{param_key}' has invalid single-brace expression: {single_curly_leak.group(0)}. "
                    f"n8n expressions require double braces '{{{{ ... }}}}' and a leading '=' prefix."
                )

                # Check dynamic references
                has_dyn_ref = bool(re.search(r'(\$\(|(?<!\w)\$json|(?<!\w)\$env|\{\{)', param_val))
                if has_dyn_ref and param_key != "jsCode":
                    assert param_val.startswith("="), (
                        f"Node '{node_name}' parameter '{param_key}' contains dynamic expressions but is missing "
                        f"the required leading '=' prefix for n8n expression mode."
                    )

                if "{{" in param_val:
                    open_count = param_val.count("{{")
                    close_count = param_val.count("}}")
                    assert open_count == close_count, (
                        f"Node '{node_name}' parameter '{param_key}' has mismatched braces: {open_count} open vs {close_count} close."
                    )


def test_dockerfile_and_compose_mount_contracts():
    """
    Verify that docker/Dockerfile and docker/docker-compose.yml package both
    'src' and 'scripts' directories to satisfy workflow execution paths.
    """
    assert DOCKERFILE_PATH.is_file(), f"Dockerfile not found at {DOCKERFILE_PATH}"
    assert COMPOSE_PATH.is_file(), f"docker-compose.yml not found at {COMPOSE_PATH}"

    dockerfile_content = DOCKERFILE_PATH.read_text(encoding="utf-8")
    compose_content = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "COPY src /data/project/src" in dockerfile_content
    assert "COPY scripts /data/project/scripts" in dockerfile_content
    assert "../src:/data/project/src" in compose_content
    assert "../scripts:/data/project/scripts" in compose_content
