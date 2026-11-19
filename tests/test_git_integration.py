from __future__ import annotations

import tempfile
from pathlib import Path
from autopatch.git.git_service import GitService
from autopatch.git.models import RemediationBranchResult, RevertCommitResult


def test_create_remediation_branch_with_only_accepted_patches_and_one_commit_per_bug():
    """
    Test that create_remediation_branch creates a dedicated branch with ONLY accepted patches,
    generates exactly one commit per bug, and includes root cause and test evidence in the message.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir)
        git_service = GitService()
        git_service.init_or_open_repo(repo_dir, default_branch="main")

        # Create sample target file in repo
        src_file = repo_dir / "src" / "auth.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        initial_content = (
            "def authenticate(token):\n"
            "    # Vulnerable query\n"
            "    cursor.execute(f'SELECT * FROM users WHERE token = {token}')\n"
            "    return True\n"
        )
        src_file.write_text(initial_content, encoding="utf-8")

        calc_file = repo_dir / "src" / "calc.py"
        calc_content = (
            "def compute_average(nums):\n"
            "    return sum(nums) / len(nums)\n"
        )
        calc_file.write_text(calc_content, encoding="utf-8")

        # Commit baseline
        git_service._run_git(repo_dir, ["add", "."])
        git_service._run_git(repo_dir, ["commit", "-m", "feat: initial service code"])

        # Create bug states:
        # Bug 1: ACCEPTED / APPROVED
        bug_1 = {
            "bug_id": "bug-sec-01",
            "finding": {
                "file": "src/auth.py",
                "line_start": 3,
                "line_end": 3,
                "symbol": "authenticate",
                "category": "security",
                "cwe": "CWE-89",
                "description": "SQL injection via formatted query string",
                "severity_level": "CRITICAL",
                "confidence": 0.98,
            },
            "root_cause": {
                "summary": "Direct interpolation of authentication token allows unescaped query execution.",
                "trigger_input_or_state": "token = \"' OR 1=1 --\"",
                "causal_chain": [
                    "src/routes.py:10 (user input received)",
                    "src/auth.py:3 (unparameterized query executed)",
                ],
                "evidence_trail": ["Ochiai suspiciousness: 0.96", "AutoCodeRover search_method: confirmed sink"],
            },
            "reproduction": {
                "test_file_path": "tests/test_brt_auth.py",
                "test_code": "def test_sqli_fails():\n    assert False, 'Reproduction failed!'\n",
                "is_confirmed": True,
                "exit_code": 1,
            },
            "patches": [
                {
                    "id": "patch-1",
                    "file": "src/auth.py",
                    "original_snippet": "    cursor.execute(f'SELECT * FROM users WHERE token = {token}')",
                    "patched_snippet": "    cursor.execute('SELECT * FROM users WHERE token = ?', (token,))",
                    "rationale": "Uses parameterized query arguments",
                    "ensemble_pass_rate": 100.0,
                }
            ],
            "verification": {
                "status": "VERIFIED",
                "ensemble_pass_rate": 100.0,
                "regressions_count": 0,
                "flakiness_stability_score": 1.0,
                "overfitting_detected": False,
                "baseline_log": "FAILED test_sqli_fails - AssertionError",
                "patched_log": "1 passed in 0.12s (0 regressions)",
            },
            "priority": {
                "priority_score": 96.0,
                "rank": 1,
                "severity": {"severity_level": "CRITICAL"},
                "confidence": {"overall_confidence": 0.98},
            },
            "decision": {
                "status": "APPROVED",
                "reviewer_id": "lead_sec_engineer",
                "comment": "Verified against penetration test suite.",
                "signature_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
            "is_patch_applied": True,
        }

        # Bug 2: ACCEPTED / APPROVED
        bug_2 = {
            "bug_id": "bug-crash-02",
            "finding": {
                "file": "src/calc.py",
                "line_start": 2,
                "line_end": 2,
                "symbol": "compute_average",
                "category": "crash",
                "cwe": "CWE-369",
                "description": "Zero division when list is empty",
                "severity_level": "HIGH",
                "confidence": 0.91,
            },
            "root_cause": {
                "summary": "Calling len() on empty list returns 0 leading to ZeroDivisionError.",
                "trigger_input_or_state": "nums = []",
                "causal_chain": ["src/calc.py:2 (division by len(nums))"],
            },
            "reproduction": {
                "test_file_path": "tests/test_brt_calc.py",
                "test_code": "def test_empty_fails():\n    assert False, 'Zero division'\n",
                "is_confirmed": True,
                "exit_code": 1,
            },
            "patches": [
                {
                    "id": "patch-2",
                    "file": "src/calc.py",
                    "original_snippet": "    return sum(nums) / len(nums)",
                    "patched_snippet": "    return sum(nums) / len(nums) if nums else 0.0",
                    "rationale": "Guards against empty list with safe default 0.0",
                    "ensemble_pass_rate": 100.0,
                }
            ],
            "verification": {
                "status": "VERIFIED",
                "ensemble_pass_rate": 100.0,
                "regressions_count": 0,
                "flakiness_stability_score": 1.0,
                "overfitting_detected": False,
            },
            "priority": {
                "priority_score": 78.5,
                "rank": 2,
                "severity": {"severity_level": "HIGH"},
                "confidence": {"overall_confidence": 0.91},
            },
            "decision": {
                "status": "APPROVED",
                "reviewer_id": "dev_lead",
                "comment": "Safe guard approved.",
                "signature_hash": "c0ffee1234567890abcdef1234567890abcdef12",
            },
            "is_patch_applied": True,
        }

        # Bug 3: REJECTED (Must be excluded!)
        bug_3 = {
            "bug_id": "bug-rejected-03",
            "finding": {"file": "src/auth.py", "description": "False positive style issue"},
            "decision": {"status": "REJECTED", "reviewer_id": "dev_lead"},
            "is_patch_applied": False,
        }

        # Bug 4: PENDING_APPROVAL (Must be excluded!)
        bug_4 = {
            "bug_id": "bug-pending-04",
            "finding": {"file": "src/calc.py", "description": "Unreviewed potential issue"},
            "decision": {"status": "PENDING_APPROVAL"},
            "is_patch_applied": False,
        }

        # Create branch
        result: RemediationBranchResult = git_service.create_remediation_branch(
            repo_dir=repo_dir,
            branch_name="autopatch/accepted-fixes",
            base_branch="main",
            bug_states=[bug_1, bug_2, bug_3, bug_4],
            include_brt_tests=True,
        )

        # 1. Assert only accepted bugs were included
        assert result.bugs_included == ["bug-sec-01", "bug-crash-02"]
        assert "bug-rejected-03" in result.bugs_skipped
        assert "bug-pending-04" in result.bugs_skipped

        # 2. Assert exactly one commit per bug
        assert len(result.commits) == 2
        assert result.total_patches_applied == 2

        # 3. Check commit 1 message structure (Root Cause and Test Evidence)
        c1 = result.commits[0]
        assert c1.bug_id == "bug-sec-01"
        assert "fix(src): [AutoPatch]" in c1.subject
        assert "## Root Cause Analysis" in c1.message
        assert "Trigger Input / State: `token = \"' OR 1=1 --\"`" in c1.message
        assert "## Test Evidence (BRT Fail-to-Pass)" in c1.message
        assert "Buggy Snapshot: FAILED" in c1.message
        assert "Patched Snapshot: PASSED" in c1.message
        assert "Ensemble Pass Rate (EPR): 100.0%" in c1.message
        assert "AutoPatch-Bug-ID: bug-sec-01" in c1.message
        assert "SHA-256 Approval Signature" in c1.message

        # 4. Check commit 2 message structure
        c2 = result.commits[1]
        assert c2.bug_id == "bug-crash-02"
        assert "AutoPatch-Bug-ID: bug-crash-02" in c2.message
        assert "## Root Cause Analysis" in c2.message

        # 5. Check patched files on disk
        updated_auth = (repo_dir / "src" / "auth.py").read_text(encoding="utf-8")
        assert "cursor.execute('SELECT * FROM users WHERE token = ?', (token,))" in updated_auth

        updated_calc = (repo_dir / "src" / "calc.py").read_text(encoding="utf-8")
        assert "if nums else 0.0" in updated_calc

        # 6. Check BRT test files created
        assert (repo_dir / "tests" / "test_brt_auth.py").exists()
        assert (repo_dir / "tests" / "test_brt_calc.py").exists()


def test_revert_restores_exact_prior_state():
    """
    Test that revert_bug_commit cleanly reverts a specific commit-linked change
    and restores the target file to the exact prior byte-for-byte content.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir)
        git_service = GitService()
        git_service.init_or_open_repo(repo_dir, default_branch="main")

        target_file = repo_dir / "src" / "db.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        exact_prior_state = (
            "import os\n\n"
            "def open_connection():\n"
            "    f = open('config.json', 'r')\n"
            "    return f.read()\n"
        )
        target_file.write_text(exact_prior_state, encoding="utf-8")

        git_service._run_git(repo_dir, ["add", "."])
        git_service._run_git(repo_dir, ["commit", "-m", "feat: initial db logic"])

        # Apply and commit bug fix
        bug = {
            "bug_id": "bug-data-03",
            "finding": {
                "file": "src/db.py",
                "line_start": 4,
                "line_end": 5,
                "description": "Unclosed file handle",
            },
            "root_cause": {"summary": "Resource handle leak."},
            "reproduction": {"test_file_path": "tests/test_brt_db.py", "test_code": "# test"},
            "patches": [
                {
                    "file": "src/db.py",
                    "original_snippet": "    f = open('config.json', 'r')\n    return f.read()",
                    "patched_snippet": "    with open('config.json', 'r') as f:\n        return f.read()",
                }
            ],
            "decision": {"status": "APPROVED", "reviewer_id": "lead"},
            "is_patch_applied": True,
        }

        branch_res = git_service.create_remediation_branch(
            repo_dir=repo_dir,
            branch_name="autopatch/fix-db",
            bug_states=[bug],
        )

        assert len(branch_res.commits) == 1
        commit_sha = branch_res.commits[0].commit_sha

        # Verify content was patched
        patched_content = target_file.read_text(encoding="utf-8")
        assert "with open('config.json', 'r') as f:" in patched_content
        assert patched_content != exact_prior_state

        # Execute Revert
        revert_res: RevertCommitResult = git_service.revert_bug_commit(
            repo_dir=repo_dir,
            bug_id_or_commit_sha="bug-data-03",
        )

        assert revert_res.is_clean is True
        assert revert_res.target_commit_sha == commit_sha

        # Verify the file is restored to the EXACT prior state byte-for-byte!
        restored_content = target_file.read_text(encoding="utf-8")
        assert restored_content == exact_prior_state
        assert "with open" not in restored_content
