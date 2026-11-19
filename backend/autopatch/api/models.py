"""Pydantic schemas for the AutoPatch REST API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopatch.orchestrator.tokens import TokenMetrics


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    github_url: Optional[str] = Field(default=None, description="Optional GitHub URL for shallow clone")


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    owner_id: str
    total_files: int
    languages: List[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StartScanRequest(BaseModel):
    entry_points: Optional[List[str]] = Field(default=None, description="Explicit application entry points")
    concurrency_limit: int = Field(ge=1, le=10, default=3)
    privacy_mode: bool = Field(default=False, description="Disables external LLM calls and runs local AST rules & templates only")



class ScanJobResponse(BaseModel):
    job_id: str
    project_id: str
    status: str
    progress: float = Field(ge=0.0, le=100.0, default=0.0)
    total_bugs: int = 0
    completed_bugs: int = 0
    token_metrics: TokenMetrics = Field(default_factory=TokenMetrics)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BugSummaryItem(BaseModel):
    bug_id: str
    file_path: str
    line_start: int
    category: str
    description: str
    severity_level: str
    confidence: float
    priority_score: float
    status: str
    rank: int = 1
    rank_explanation: Optional[str] = None
    cwe: Optional[str] = None
    symbol: Optional[str] = None


class BugListResponse(BaseModel):
    project_id: str
    total_bugs: int
    bugs: List[BugSummaryItem]


class BugDetailResponse(BaseModel):
    bug_id: str
    status: str
    finding: Optional[Dict[str, Any]] = None
    root_cause: Optional[Dict[str, Any]] = None
    reproduction: Optional[Dict[str, Any]] = None
    patches: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    priority: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    is_patch_applied: bool = False
    completed_stages: List[str] = Field(default_factory=list)


class PatchGenerationRequest(BaseModel):
    rationale_hint: Optional[str] = None


class ValidationRequest(BaseModel):
    patch_id: Optional[str] = None


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED|NEEDS_REVIEW)$")
    comment: str = ""
    patch_id: Optional[str] = Field(default=None, description="Exact patch ID approved by reviewer")


class DecisionResponse(BaseModel):
    bug_id: str
    reviewer_id: str
    status: str
    comment: str
    signature_hash: str
    applied: bool = False
    patch_id: Optional[str] = None
    patch_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevertResponse(BaseModel):
    bug_id: str
    reverted: bool
    message: str


class HistoryResponse(BaseModel):
    project_id: str
    total_events: int
    events: List[Dict[str, Any]] = Field(default_factory=list)


class CreateRemediationBranchRequest(BaseModel):
    branch_name: str = Field(min_length=1, max_length=150, default="autopatch/remediation-patches")
    base_branch: str = Field(min_length=1, max_length=150, default="main")
    include_brt_tests: bool = True


class CreateRemediationBranchResponse(BaseModel):
    branch_name: str
    base_branch: str
    total_commits: int
    bugs_included: List[str]
    bugs_skipped: List[str]
    commits: List[Dict[str, Any]] = Field(default_factory=list)


class OpenPullRequestRequest(BaseModel):
    repo_slug: str = Field(description="e.g. owner/repo")
    head_branch: str
    base_branch: str = "main"
    title: Optional[str] = None
    github_token: Optional[str] = None


class OpenPullRequestResponse(BaseModel):
    pr_number: int
    html_url: str
    head_branch: str
    base_branch: str
    title: str
    body_markdown: str


class RevertCommitRequest(BaseModel):
    bug_id_or_commit_sha: str


class RevertCommitResponse(BaseModel):
    bug_id: str
    target_commit_sha: str
    revert_commit_sha: str
    is_clean: bool
    restored_files: List[str]
    message: str


class PurgeResponse(BaseModel):
    target_id: str
    target_type: str
    success: bool
    deleted_paths: List[str] = Field(default_factory=list)
    purged_events_count: int
    purged_jobs_count: int
    message: str


