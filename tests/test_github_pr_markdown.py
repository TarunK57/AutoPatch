from __future__ import annotations

from autopatch.git.pr_formatter import generate_pr_markdown_description


def test_pr_markdown_description_renders_correctly():
    """
    Test that generate_pr_markdown_description generates a well-formed Markdown
    document containing the executive summary, evidence table, BRT before/after logs,
    regression summary, and confidence.
    """
    bugs = [
        {
            "bug_id": "bug-sec-01",
            "finding": {
                "file": "src/auth/service.py",
                "line_start": 34,
                "line_end": 38,
                "symbol": "get_user_by_token",
                "category": "security",
                "cwe": "CWE-89",
                "description": "SQL Injection vulnerability via formatted token string",
                "severity_level": "CRITICAL",
                "confidence": 0.96,
            },
            "root_cause": {
                "summary": "Direct interpolation of user-supplied token into raw SQL statement.",
                "trigger_input_or_state": "token = \"' OR '1'='1\"",
                "causal_chain": [
                    "src/api/routes.py:12 (auth_header received)",
                    "src/auth/service.py:34 (token forwarded without sanitization)",
                    "src/auth/service.py:36 (unparameterized query executed)",
                ],
            },
            "reproduction": {
                "test_file_path": "tests/test_brt_auth_sqli.py",
                "test_code": "def test_sqli_fails():\n    assert False, 'SQL Injection!'\n",
                "is_confirmed": True,
                "exit_code": 1,
                "execution_log": "FAILED tests/test_brt_auth_sqli.py::test_sqli_fails - AssertionError",
            },
            "patches": [
                {
                    "file": "src/auth/service.py",
                    "unified_diff": "--- a/src/auth/service.py\n+++ b/src/auth/service.py\n@@ -34,2 +34,2 @@\n- query = f'SELECT * FROM users WHERE token = {token}'\n+ query = 'SELECT * FROM users WHERE token = ?'\n+ cursor.execute(query, (token,))",
                    "rationale": "Parameterized SQL arguments",
                }
            ],
            "verification": {
                "status": "VERIFIED",
                "ensemble_pass_rate": 100.0,
                "regressions_count": 0,
                "flakiness_stability_score": 1.0,
                "baseline_log": "1 failed in 0.32s (Reproduction test confirmed)",
                "patched_log": "15 passed, 0 failed in 0.45s (0 regressions)",
            },
            "priority": {
                "priority_score": 94.2,
                "rank": 1,
                "severity": {"severity_level": "CRITICAL"},
                "confidence": {"overall_confidence": 0.96},
            },
            "decision": {
                "status": "APPROVED",
                "reviewer_id": "security_lead",
                "comment": "Verified by security audit.",
                "signature_hash": "a9f8b4c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
            },
        }
    ]

    md = generate_pr_markdown_description(
        project_name="Core Commerce Service",
        base_branch="main",
        remediation_branch="autopatch/fix-sec-01",
        approved_bug_states=bugs,
    )

    # 1. Verify Headers & Badges
    assert "# [AutoPatch] Remediation Report: 1 Verified Bug Fixes" in md
    assert "**Target Branch** | `main`" in md
    assert "**Remediation Branch** | `autopatch/fix-sec-01`" in md
    assert "**Test Suite Regressions** | **0 Regressions**" in md
    assert "**Sandbox Isolation** | **Network Disabled**" in md
    assert "**Rule 1 Compliance** | **Human Approved**" in md

    # 2. Verify Table Columns
    table_header = "| Rank | Bug ID | Location | Category / CWE | Priority | BRT Reproduction (Before $\\to$ After) | Regressions | Conf. (EPR) | Signature |"
    assert table_header in md
    assert "| **#1** | `bug-sec-01` |" in md
    assert "src/auth/service.py" in md
    assert "**SECURITY**<br/><sub>CWE-89</sub>" in md
    assert "**94.2**<br/><sub>CRITICAL</sub>" in md
    assert "❌ Exit 1 $\\to$ ✅ Exit 0" in md
    assert "✅ 0" in md
    assert "96%<br/><sub>EPR: 100%</sub>" in md
    assert "security_lead" in md

    # 3. Verify Collapsible Dossier & Evidence
    assert "<details>" in md
    assert "<summary><b>🔍 Bug bug-sec-01:" in md
    assert "#### Root Cause Analysis" in md
    assert "Trigger Input / State:** `token = \"' OR '1'='1\"`" in md
    assert "1. src/api/routes.py:12 (auth_header received)" in md
    assert "#### Bug Reproduction Test (Fail-to-Pass Proof)" in md
    assert "tests/test_brt_auth_sqli.py" in md
    assert "1 failed in 0.32s (Reproduction test confirmed)" in md
    assert "15 passed, 0 failed in 0.45s (0 regressions)" in md
    assert "#### Minimal Diff Applied" in md
    assert "+ query = 'SELECT * FROM users WHERE token = ?'" in md
    assert "#### Human Approval Record (Rule 1)" in md
    assert "a9f8b4c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0" in md

    # 4. Invariants
    assert "Rule 1 (Trust):" in md
    assert "Rule 2 (Reproduce Before Repair):" in md
    assert "Rule 3 (Minimal Diffs):" in md
