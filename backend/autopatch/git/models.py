from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GitCommitInfo(BaseModel):
    """Metadata for a single bug remediation commit."""
    commit_sha: str
    bug_id: str
    subject: str
    message: str
    files_changed: List[str]
    author_name: str = "AutoPatch Agent"
    author_email: str = "autopatch@system.local"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RemediationBranchResult(BaseModel):
    """Result of creating a remediation branch with accepted patches."""
    branch_name: str
    base_branch: str
    repo_path: str
    commits: List[GitCommitInfo] = Field(default_factory=list)
    bugs_included: List[str] = Field(default_factory=list)
    bugs_skipped: List[str] = Field(default_factory=list)
    total_patches_applied: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PullRequestResult(BaseModel):
    """Result of opening a pull request on GitHub."""
    pr_number: int
    html_url: str
    head_branch: str
    base_branch: str
    title: str
    body_markdown: str
    commits_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevertCommitResult(BaseModel):
    """Result of reverting a commit-linked bug remediation."""
    bug_id: str
    target_commit_sha: str
    revert_commit_sha: str
    restored_files: List[str]
    is_clean: bool
    reverted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
