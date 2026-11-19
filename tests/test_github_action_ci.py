from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
import pytest

from autopatch.ci.action_runner import ActionRunner
from autopatch.git.github_client import GitHubTokenMissingError


@pytest.mark.anyio
async def test_action_fails_safely_when_tokens_missing(monkeypatch, capsys):
    """
    Test that when GITHUB_TOKEN is missing or empty, ActionRunner fails safely
    with clear, actionable diagnostic messages and does not crash unpredictably.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("INPUT_GITHUB_TOKEN", raising=False)

    runner = ActionRunner(token="")

    with pytest.raises(GitHubTokenMissingError) as exc_info:
        await runner.run(dry_run=True)

    assert "Missing GITHUB_TOKEN" in str(exc_info.value)

    captured = capsys.readouterr()
    assert "::error title=AutoPatch Missing Token::" in captured.err
    assert "secrets.GITHUB_TOKEN" in captured.err
    assert "pull-requests: write" in captured.err


@pytest.mark.anyio
async def test_action_runs_and_never_pushes_changes_without_approval():
    """
    Test that the ActionRunner scans code, formats findings, and strictly adheres to
    Rule 1 (Trust): never pushes changes, never modifies remote branch without explicit human approval.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)

        # Create sample file with potential bug
        calc_py = workspace / "calculator.py"
        calc_py.write_text(
            "def avg(items):\n"
            "    return sum(items) / len(items)\n",
            encoding="utf-8",
        )

        runner = ActionRunner(
            token="ghp_mock_token_for_ci",
            repo_slug="acme/ecommerce",
            pr_number=10,
            head_sha="abcdef1234567890",
            workspace_dir=workspace,
        )

        result = await runner.run(dry_run=True)

        assert result["status"] == "SUCCESS"
        assert result["findings_count"] >= 1
        assert result["inline_comments_count"] >= 1

        # Check comment contents
        summary = result["summary"]
        assert "AutoPatch Automated Analysis Summary" in summary
        assert "CWE-369" in summary
        assert "AST_RULE_ZERO_DIVISION" in summary

        # INVARIANT: Must strictly NEVER push changes on PR analysis
        assert result["rule_1_pushed_changes"] is False
        assert "AutoPatch will **never** automatically push commits" in summary


def test_github_action_workflow_file_validity():
    """
    Verify that .github/workflows/autopatch.yml exists and contains
    all required triggers, permissions, and safe execution steps.
    """
    workflow_path = Path(".github/workflows/autopatch.yml")
    assert workflow_path.exists(), "Workflow file .github/workflows/autopatch.yml must exist"

    content = workflow_path.read_text(encoding="utf-8")

    # Verify triggers
    assert "pull_request:" in content
    assert "types: [opened, synchronize, reopened]" in content

    # Verify permissions
    assert "contents: read" in content
    assert "pull-requests: write" in content

    # Verify step execution
    assert "actions/checkout@v4" in content
    assert "actions/setup-python@v5" in content
    assert "python -m autopatch.ci.action_runner" in content
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in content
