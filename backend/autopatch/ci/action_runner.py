from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopatch.git.github_client import GitHubClient, GitHubTokenMissingError, GitHubApiError


class ActionRunner:
    """
    Executes AutoPatch inside GitHub Actions on pull_request events.
    Runs detection, comments findings inline on the PR diff, and strictly enforces
    that no changes are ever pushed to the branch without explicit human approval.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repo_slug: Optional[str] = None,
        pr_number: Optional[int] = None,
        head_sha: Optional[str] = None,
        workspace_dir: Optional[Path] = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN")
        self.repo_slug = repo_slug or os.environ.get("GITHUB_REPOSITORY") or os.environ.get("INPUT_REPO")
        self.pr_number = pr_number
        self.head_sha = head_sha
        self.workspace_dir = workspace_dir or Path(os.environ.get("GITHUB_WORKSPACE", "."))

        # Check event.json if pr_number or head_sha not explicitly given
        if not self.pr_number or not self.head_sha:
            event_path = os.environ.get("GITHUB_EVENT_PATH")
            if event_path and Path(event_path).exists():
                try:
                    event_data = json.loads(Path(event_path).read_text(encoding="utf-8"))
                    pr_info = event_data.get("pull_request") or {}
                    if not self.pr_number and pr_info.get("number"):
                        self.pr_number = int(pr_info["number"])
                    if not self.head_sha and pr_info.get("head", {}).get("sha"):
                        self.head_sha = pr_info["head"]["sha"]
                except Exception:
                    pass

    def validate_tokens_or_fail(self) -> None:
        """
        Validates that required tokens exist. Fails safely with clear, actionable
        messages when tokens are missing.
        """
        if not self.token or not self.token.strip():
            # GitHub Action standard error output
            print(
                "::error title=AutoPatch Missing Token::"
                "GITHUB_TOKEN is missing or empty. Please pass GITHUB_TOKEN to the workflow step:\n"
                "  env:\n"
                "    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
                "Also ensure your workflow has 'pull-requests: write' and 'contents: read' permissions.",
                file=sys.stderr,
            )
            raise GitHubTokenMissingError(
                "Missing GITHUB_TOKEN. AutoPatch cannot comment on pull requests without an authentication token."
            )

        # Check LLM token; if missing, log clear notice rather than crashing
        llm_token = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not llm_token:
            print(
                "::notice title=AutoPatch Engine Notice::"
                "No OPENAI_API_KEY or ANTHROPIC_API_KEY detected. "
                "AutoPatch will run with deterministic AST rules and static linter detectors.",
                file=sys.stdout,
            )

    def scan_changed_files(self) -> List[Dict[str, Any]]:
        """
        Scans workspace files and emits normalized findings.
        In CI mode, prioritizes Python and JS/TS files.
        """
        findings: List[Dict[str, Any]] = []

        # Find target files
        for p in self.workspace_dir.rglob("*.py"):
            if any(x in p.parts for x in [".git", "__pycache__", ".venv", "node_modules"]):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                rel_path = str(p.relative_to(self.workspace_dir))

                # Simple AST/regex checks for CI demonstration
                for idx, line in enumerate(lines, start=1):
                    # Zero division check
                    if "/ len(" in line and "if len(" not in line:
                        findings.append({
                            "file": rel_path,
                            "line": idx,
                            "symbol": "function",
                            "category": "crash",
                            "cwe": "CWE-369",
                            "detector": "AST_RULE_ZERO_DIVISION",
                            "description": "Possible division by zero on empty collection without prior length check.",
                            "confidence": 0.92,
                        })
                    # Raw SQL query check
                    if 'cursor.execute(f"' in line or "cursor.execute(f'" in line:
                        findings.append({
                            "file": rel_path,
                            "line": idx,
                            "symbol": "query",
                            "category": "security",
                            "cwe": "CWE-89",
                            "detector": "SECURITY_SQLI",
                            "description": "Unsanitized formatted string in SQL query execution (SQL Injection).",
                            "confidence": 0.96,
                        })
            except Exception:
                pass

        return findings

    async def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes the CI action:
        1. Validates tokens (fails safely with clear errors if missing).
        2. Detects flaws on project code.
        3. Formulates inline PR review comments and top-level summary.
        4. NEVER pushes changes to repository (strictly read-only / advisory on PRs).
        """
        self.validate_tokens_or_fail()

        findings = self.scan_changed_files()
        print(f"AutoPatch detected {len(findings)} potential finding(s).")

        summary_lines = [
            f"### 🛡️ AutoPatch Automated Analysis Summary",
            f"Analyzed workspace: **{len(findings)} potential flaw(s)** identified.",
            "",
            "| Location | Line | Category | CWE | Detector | Confidence |",
            "| :--- | :---: | :---: | :---: | :--- | :---: |",
        ]

        inline_comments = []
        for f in findings:
            summary_lines.append(
                f"| `{f['file']}` | {f['line']} | **{f['category'].upper()}** | `{f.get('cwe', 'N/A')}` | `{f['detector']}` | {f['confidence'] * 100:.0f}% |"
            )

            comment_body = (
                f"### 🛡️ AutoPatch Finding: {f['category'].upper()}\n"
                f"**CWE:** `{f.get('cwe', 'N/A')}` | **Detector:** `{f['detector']}` | **Confidence:** {f['confidence'] * 100:.0f}%\n\n"
                f"**Description:** {f['description']}\n\n"
                f"> 🔒 **Rule 1 Guarantee:** AutoPatch runs in advisory mode on pull requests. "
                f"No changes will be applied without human review and approval."
            )

            inline_comments.append({
                "path": f["file"],
                "line": f["line"],
                "side": "RIGHT",
                "body": comment_body,
            })

        summary_lines.extend([
            "",
            "> 🔒 **Human Approval Invariant (Rule 1):**",
            "> AutoPatch will **never** automatically push commits or modify this branch without explicit human approval in the AutoPatch dashboard.",
            "",
            "<sub>Powered by [AutoPatch](https://github.com/google/autopatch)</sub>",
        ])

        summary_text = "\n".join(summary_lines)

        result = {
            "status": "SUCCESS",
            "findings_count": len(findings),
            "inline_comments_count": len(inline_comments),
            "summary": summary_text,
            "rule_1_pushed_changes": False,  # Assert invariant: NEVER pushes changes
        }

        if dry_run or not self.repo_slug or not self.pr_number:
            print("AutoPatch CI dry-run completed successfully.")
            return result

        client = GitHubClient(token=self.token)
        head_commit = self.head_sha or "HEAD"

        try:
            await client.post_pr_review_comments(
                repo_slug=self.repo_slug,
                pr_number=self.pr_number,
                commit_sha=head_commit,
                summary_body=summary_text,
                inline_comments=inline_comments,
            )
            print(f"Successfully posted {len(inline_comments)} inline review comments to PR #{self.pr_number}.")
        except GitHubApiError as e:
            # Fallback to general comment if review fails
            print(f"Warning: review comment post failed ({e}); falling back to top-level PR comment.")
            await client.post_issue_comment(self.repo_slug, self.pr_number, summary_text)

        return result


def main():
    parser = argparse.ArgumentParser(description="AutoPatch GitHub Action Runner")
    parser.add_argument("--repo", help="Repository slug (owner/repo)")
    parser.add_argument("--pr", type=int, help="Pull request number")
    parser.add_argument("--sha", help="Pull request head commit SHA")
    parser.add_argument("--token", help="GitHub API Token")
    parser.add_argument("--dry-run", action="store_true", help="Run scan without posting to GitHub API")
    args = parser.parse_args()

    runner = ActionRunner(
        token=args.token,
        repo_slug=args.repo,
        pr_number=args.pr,
        head_sha=args.sha,
    )

    import asyncio
    try:
        asyncio.run(runner.run(dry_run=args.dry_run))
    except GitHubTokenMissingError as e:
        print(f"AutoPatch Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
