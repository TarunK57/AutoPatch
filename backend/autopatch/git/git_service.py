from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from autopatch.core.exceptions import AutoPatchException
from autopatch.git.commit_formatter import format_commit_message
from autopatch.git.models import (
    GitCommitInfo,
    RemediationBranchResult,
    RevertCommitResult,
)


class GitIntegrationError(AutoPatchException):
    """Raised when a Git command or repository operation fails."""
    pass


class GitService:
    """
    Handles Git branch creation, per-bug commits with root cause and test evidence,
    and commit-linked reverts.
    """

    def __init__(self, author_name: str = "AutoPatch Agent", author_email: str = "autopatch@system.local") -> None:
        self.author_name = author_name
        self.author_email = author_email

    def _run_git(self, repo_dir: Path, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Runs a git command in repo_dir with safe author/committer environment variables."""
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = self.author_name
        env["GIT_AUTHOR_EMAIL"] = self.author_email
        env["GIT_COMMITTER_NAME"] = self.author_name
        env["GIT_COMMITTER_EMAIL"] = self.author_email
        env["GIT_TERMINAL_PROMPT"] = "0"

        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if check and res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip() or f"Git exited with code {res.returncode}"
                raise GitIntegrationError(f"git {' '.join(args)} failed: {err_msg}")
            return res
        except FileNotFoundError:
            raise GitIntegrationError("Git executable not found on host system.")

    def init_or_open_repo(self, repo_dir: Path, default_branch: str = "main") -> None:
        """Initializes a git repository if one doesn't exist."""
        repo_dir.mkdir(parents=True, exist_ok=True)
        git_dir = repo_dir / ".git"
        if not git_dir.exists():
            self._run_git(repo_dir, ["init", "-b", default_branch])
            self._run_git(repo_dir, ["config", "user.name", self.author_name])
            self._run_git(repo_dir, ["config", "user.email", self.author_email])
            # Initial dummy commit if completely empty
            readme = repo_dir / "README.md"
            if not readme.exists():
                readme.write_text(f"# Project\nInitialized by AutoPatch\n", encoding="utf-8")
            self._run_git(repo_dir, ["add", "."])
            self._run_git(repo_dir, ["commit", "-m", "chore: initial repository commit", "--allow-empty"])

    def create_remediation_branch(
        self,
        repo_dir: Path,
        branch_name: str,
        base_branch: str = "main",
        bug_states: Optional[List[Dict[str, Any]]] = None,
        include_brt_tests: bool = True,
    ) -> RemediationBranchResult:
        """
        Creates a dedicated branch containing ONLY accepted patches,
        committing each approved bug as a separate commit with complete root cause
        and test evidence metadata.
        """
        bug_states = bug_states or []
        self.init_or_open_repo(repo_dir, default_branch=base_branch)

        # Check out or create base branch
        self._run_git(repo_dir, ["checkout", base_branch], check=False)

        # Create and switch to new remediation branch
        # If branch already exists, delete or switch
        check_branch = self._run_git(repo_dir, ["branch", "--list", branch_name])
        if branch_name in check_branch.stdout:
            self._run_git(repo_dir, ["checkout", branch_name])
        else:
            self._run_git(repo_dir, ["checkout", "-b", branch_name])

        commits: List[GitCommitInfo] = []
        bugs_included: List[str] = []
        bugs_skipped: List[str] = []

        for b in bug_states:
            bid = b.get("bug_id", "unknown")
            decision = b.get("decision") or {}
            is_applied = b.get("is_patch_applied", False)
            status = decision.get("status")

            # Enforce Rule 1: ONLY accepted patches are included
            is_accepted = (status == "APPROVED") or is_applied
            if not is_accepted:
                bugs_skipped.append(bid)
                continue

            patches = b.get("patches", [])
            if not patches:
                bugs_skipped.append(bid)
                continue

            best_patch = patches[0]
            target_rel = best_patch.get("file")
            orig = best_patch.get("original_snippet", "")
            patched = best_patch.get("patched_snippet", "")

            if not target_rel:
                bugs_skipped.append(bid)
                continue

            target_file = repo_dir / target_rel
            if not target_file.exists():
                # Create file if missing
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(patched or orig or "# source\n", encoding="utf-8")
            else:
                content = target_file.read_text(encoding="utf-8", errors="replace")
                if orig in content:
                    target_file.write_text(content.replace(orig, patched, 1), encoding="utf-8")
                elif patched not in content:
                    # Append or overwrite if exact snippet not cleanly matched
                    target_file.write_text(content + "\n" + patched, encoding="utf-8")

            staged_files = [str(target_file.relative_to(repo_dir))]

            # Also commit BRT reproduction test file if present
            reproduction = b.get("reproduction") or {}
            test_path_str = reproduction.get("test_file_path")
            test_code = reproduction.get("test_code")
            if include_brt_tests and test_path_str and test_code:
                test_file = repo_dir / test_path_str
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text(test_code, encoding="utf-8")
                staged_files.append(str(test_file.relative_to(repo_dir)))

            # Stage files
            self._run_git(repo_dir, ["add"] + staged_files)

            # Generate structured commit message
            commit_msg = format_commit_message(b)
            self._run_git(repo_dir, ["commit", "-m", commit_msg])

            # Get commit sha
            rev = self._run_git(repo_dir, ["rev-parse", "HEAD"])
            commit_sha = rev.stdout.strip()

            commits.append(
                GitCommitInfo(
                    commit_sha=commit_sha,
                    bug_id=bid,
                    subject=commit_msg.splitlines()[0],
                    message=commit_msg,
                    files_changed=staged_files,
                    author_name=self.author_name,
                    author_email=self.author_email,
                )
            )
            bugs_included.append(bid)

        return RemediationBranchResult(
            branch_name=branch_name,
            base_branch=base_branch,
            repo_path=str(repo_dir),
            commits=commits,
            bugs_included=bugs_included,
            bugs_skipped=bugs_skipped,
            total_patches_applied=len(commits),
        )

    def find_commit_for_bug(self, repo_dir: Path, bug_id: str) -> Optional[str]:
        """Finds the commit hash associated with a bug ID via Git log trailers."""
        res = self._run_git(
            repo_dir,
            ["log", f"--grep=AutoPatch-Bug-ID: {bug_id}", "-n", "1", "--format=%H"],
            check=False,
        )
        sha = res.stdout.strip()
        return sha if sha else None

    def revert_bug_commit(self, repo_dir: Path, bug_id_or_commit_sha: str) -> RevertCommitResult:
        """
        Reverts a commit-linked bug remediation and verifies the exact prior state is restored.
        """
        target_commit_sha = bug_id_or_commit_sha

        # If argument is bug_id, find commit sha
        if len(bug_id_or_commit_sha) < 40 or "-" in bug_id_or_commit_sha:
            found_sha = self.find_commit_for_bug(repo_dir, bug_id_or_commit_sha)
            if not found_sha:
                # Fallback: check if bug_id_or_commit_sha is a short commit hash
                test_rev = self._run_git(repo_dir, ["rev-parse", "--verify", bug_id_or_commit_sha], check=False)
                if test_rev.returncode == 0:
                    found_sha = test_rev.stdout.strip()
                else:
                    raise GitIntegrationError(f"No commit found linked to bug '{bug_id_or_commit_sha}'.")
            target_commit_sha = found_sha
            bug_id = bug_id_or_commit_sha
        else:
            bug_id = "unknown"

        # List files touched by target commit
        show_files = self._run_git(
            repo_dir,
            ["show", "--name-only", "--format=", target_commit_sha],
        )
        touched_files = [f.strip() for f in show_files.stdout.splitlines() if f.strip()]

        # Execute git revert --no-edit
        revert_proc = self._run_git(repo_dir, ["revert", "--no-edit", target_commit_sha], check=False)

        if revert_proc.returncode != 0:
            # Handle conflict by restoring touched files from target_commit_sha~1
            self._run_git(repo_dir, ["revert", "--abort"], check=False)
            for file_path in touched_files:
                restore_proc = self._run_git(
                    repo_dir,
                    ["checkout", f"{target_commit_sha}~1", "--", file_path],
                    check=False,
                )
                if restore_proc.returncode != 0:
                    # File was newly created in that commit; remove it
                    p = repo_dir / file_path
                    if p.exists():
                        p.unlink()

            self._run_git(repo_dir, ["add", "."])
            rev_msg = f"revert: [AutoPatch] Clean revert of commit {target_commit_sha[:8]} for bug {bug_id}\n\nAutoPatch-Reverted-Commit: {target_commit_sha}\nAutoPatch-Bug-ID: {bug_id}"
            self._run_git(repo_dir, ["commit", "-m", rev_msg])

        # Get new revert commit SHA
        rev_head = self._run_git(repo_dir, ["rev-parse", "HEAD"])
        new_commit_sha = rev_head.stdout.strip()

        # Check working tree is clean
        status_proc = self._run_git(repo_dir, ["status", "--porcelain"])
        is_clean = len(status_proc.stdout.strip()) == 0

        return RevertCommitResult(
            bug_id=bug_id,
            target_commit_sha=target_commit_sha,
            revert_commit_sha=new_commit_sha,
            restored_files=touched_files,
            is_clean=is_clean,
            message=f"Successfully reverted commit {target_commit_sha[:8]} for bug '{bug_id}'.",
        )

    def push_branch(
        self,
        repo_dir: Path,
        branch_name: str,
        remote_name: str = "origin",
        remote_url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pushes a local branch to the remote git repository."""
        check_remotes = self._run_git(repo_dir, ["remote"], check=False)
        remotes = [r.strip() for r in check_remotes.stdout.splitlines() if r.strip()]

        cur_url = ""
        if remote_name in remotes:
            cur_url_res = self._run_git(repo_dir, ["remote", "get-url", remote_name], check=False)
            cur_url = cur_url_res.stdout.strip()

        target_url = remote_url or cur_url
        tok = (token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()

        is_remote_http = bool(
            target_url
            and (
                target_url.startswith(("http://", "https://"))
                or "github.com" in target_url
            )
        )

        if is_remote_http and not tok:
            raise GitIntegrationError(
                f"GitHub Personal Access Token (PAT) required to push branch '{branch_name}' to '{target_url}'. "
                "GitHub requires authentication for remote git push. "
                "Please provide a GitHub Personal Access Token with 'repo' or 'contents: write' scope in the modal, "
                "or click 'Download Patched ZIP' to download the complete remediated project."
            )

        if remote_url:
            push_url = remote_url
            if tok and "github.com" in push_url and "@" not in push_url:
                push_url = push_url.replace("https://", f"https://x-access-token:{tok}@")
            if remote_name in remotes:
                self._run_git(repo_dir, ["remote", "set-url", remote_name, push_url])
            else:
                self._run_git(repo_dir, ["remote", "add", remote_name, push_url])
        elif tok and remote_name in remotes and cur_url:
            if cur_url.startswith("https://") and "@" not in cur_url:
                auth_url = cur_url.replace("https://", f"https://x-access-token:{tok}@")
                self._run_git(repo_dir, ["remote", "set-url", remote_name, auth_url])

        push_cmd = ["push", "-u", remote_name, branch_name]
        if tok:
            push_cmd = ["-c", f"http.extraheader=Authorization: Bearer {tok}"] + push_cmd

        res = self._run_git(repo_dir, push_cmd)
        return {
            "branch_name": branch_name,
            "remote_name": remote_name,
            "success": True,
            "output": res.stdout.strip(),
        }
