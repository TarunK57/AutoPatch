"""FastAPI route handlers implementing the full AutoPatch REST and SSE API."""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse

from autopatch.api.auth import User, assert_project_ownership, get_current_user
from autopatch.api.export import ProjectExporter
from autopatch.api.models import (
    BugDetailResponse,
    BugListResponse,
    BugSummaryItem,
    CreateProjectRequest,
    CreateRemediationBranchRequest,
    CreateRemediationBranchResponse,
    DecisionRequest,
    DecisionResponse,
    HistoryResponse,
    OpenPullRequestRequest,
    OpenPullRequestResponse,
    PatchGenerationRequest,
    ProjectResponse,
    PurgeResponse,
    RevertCommitRequest,
    RevertCommitResponse,
    RevertResponse,
    ScanJobResponse,
    StartScanRequest,
    ValidationRequest,
)
from autopatch.git.git_service import GitService, GitIntegrationError
from autopatch.git.pr_formatter import generate_pr_markdown_description
from autopatch.git.github_client import GitHubClient, GitHubTokenMissingError, GitHubApiError
from autopatch.security.retention import DataRetentionManager
from autopatch.security.dependency_scanner import DependencyScanner
from autopatch.security.privacy_mode import PrivacyGuard
from autopatch.storage.db import get_default_db_path, get_storage
from autopatch.api.rate_limit import rate_limit_dependency
from autopatch.api.upload_scanner import UploadScanner
from autopatch.core.exceptions import CancellationToken, UnauthorizedPatchApplicationError
from autopatch.core.logging import get_logger
from autopatch.core.models import ApprovalDecision, ApprovalStatus
from autopatch.detection.pipeline import DetectionPipeline
from autopatch.ingestion.extractor import SafeExtractor
from autopatch.ingestion.project_map import ProjectMapper
from autopatch.intelligence.service import CodeIntelligenceService
from autopatch.orchestrator.events import AuditEvent, EventStore, EventType
from autopatch.orchestrator.pipeline import BugPipelineOrchestrator
from autopatch.orchestrator.tokens import TokenUsageTracker
from autopatch.observability import (
    CostDashboardService,
    ProjectCostSummary,
    ReplayEngine,
    ReplayResult,
    global_dashboard_service,
    global_replay_engine,
    global_tracer,
    global_budget_manager,
    global_llm_cache,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["AutoPatch API"])

storage = get_storage()
event_store = EventStore(db_path=get_default_db_path().parent / "audit_events.db")
token_tracker = TokenUsageTracker()
orchestrator = BugPipelineOrchestrator(event_store=event_store, token_tracker=token_tracker)
upload_scanner = UploadScanner()
safe_extractor = SafeExtractor()
intel_service = CodeIntelligenceService()


class PersistentProjectDict(dict):
    def __init__(self, db_storage):
        super().__init__()
        self.db_storage = db_storage

    def __getitem__(self, key: str) -> Dict[str, Any]:
        if key not in self:
            val = self.db_storage.get_project(key)
            if val is not None:
                super().__setitem__(key, val)
                return val
            raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        if not super().__contains__(key):
            val = self.db_storage.get_project(key)
            if val is not None:
                super().__setitem__(key, val)
                return val
            return default
        return super().get(key, default)

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        super().__setitem__(key, value)
        self.db_storage.save_project(value)

    def __delitem__(self, key: str) -> None:
        if super().__contains__(key):
            super().__delitem__(key)
        self.db_storage.delete_project(key)

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        return self.db_storage.get_project(str(key)) is not None

    def pop(self, key: str, default: Any = None) -> Any:
        val = self.get(key, default)
        try:
            del self[key]
        except KeyError:
            pass
        return val


class PersistentJobDict(dict):
    def __init__(self, db_storage):
        super().__init__()
        self.db_storage = db_storage

    def __getitem__(self, key: str) -> Dict[str, Any]:
        if key not in self:
            val = self.db_storage.get_job(key)
            if val is not None:
                super().__setitem__(key, val)
                return val
            raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        if not super().__contains__(key):
            val = self.db_storage.get_job(key)
            if val is not None:
                super().__setitem__(key, val)
                return val
            return default
        return super().get(key, default)

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        super().__setitem__(key, value)
        self.db_storage.save_job(value)

    def __delitem__(self, key: str) -> None:
        if super().__contains__(key):
            super().__delitem__(key)
        self.db_storage.delete_job(key)

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        return self.db_storage.get_job(str(key)) is not None

    def pop(self, key: str, default: Any = None) -> Any:
        val = self.get(key, default)
        try:
            del self[key]
        except KeyError:
            pass
        return val


# Persistent repositories for state persistence across server restarts
PROJECTS_DB = PersistentProjectDict(storage)
JOBS_DB = PersistentJobDict(storage)
CANCELLATION_TOKENS: Dict[str, CancellationToken] = {}


# ============================================================================
# 1. Project Creation & Management
# ============================================================================

@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Project",
    description="Upload a ZIP archive or specify a GitHub repository for autonomous scanning and repair.",
    dependencies=[Depends(rate_limit_dependency)],
)
async def create_project(
    name: Optional[str] = Form(None),
    github_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    json_body: Optional[CreateProjectRequest] = None,
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project_id = str(uuid4())
    proj_name = name or (json_body.name if json_body else f"project_{project_id[:8]}")
    url = github_url or (json_body.github_url if json_body else None)

    project_dir = Path(tempfile.mkdtemp(prefix=f"autopatch_proj_{project_id}_"))

    if file:
        file_bytes = await file.read()
        # Security scan upload
        scan_res = upload_scanner.scan_archive_bytes(file_bytes)
        if not scan_res.is_safe:
            shutil.rmtree(project_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded archive rejected: {'; '.join(scan_res.errors)}",
            )
        # Safe extraction
        safe_extractor.extract_zip_bytes(file_bytes, project_dir)
    elif url:
        try:
            safe_extractor.clone_git_repo(url, project_dir)
        except Exception as clone_err:
            shutil.rmtree(project_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to ingest git repository: {str(clone_err)}",
            )
    else:
        # Default empty initialized project workspace
        (project_dir / "src").mkdir(parents=True, exist_ok=True)
        (project_dir / "src" / "main.py").write_text("def hello(): return 'world'\n")

    # Map project topology
    mapper = ProjectMapper()
    proj_map = mapper.build_project_map(project_dir)

    record = {
        "project_id": project_id,
        "name": proj_name,
        "owner_id": current_user.user_id,
        "project_dir": str(project_dir),
        "total_files": proj_map.total_files,
        "languages": proj_map.languages,
        "entry_points": proj_map.entry_points,
        "created_at": datetime.now(timezone.utc),
        "applied_patches": {},  # bug_id -> patch_dict
    }
    PROJECTS_DB[project_id] = record

    return ProjectResponse(
        project_id=project_id,
        name=proj_name,
        owner_id=current_user.user_id,
        total_files=proj_map.total_files,
        languages=proj_map.languages,
        created_at=record["created_at"],
    )


@router.get(
    "/projects",
    response_model=List[ProjectResponse],
    summary="List User Projects",
    description="Lists all projects owned by the authenticated user.",
)
async def list_projects(current_user: User = Depends(get_current_user)) -> List[ProjectResponse]:
    user_projects = [
        ProjectResponse(
            project_id=p["project_id"],
            name=p["name"],
            owner_id=p["owner_id"],
            total_files=p["total_files"],
            languages=p["languages"],
            created_at=p["created_at"],
        )
        for p in PROJECTS_DB.values()
        if p["owner_id"] == current_user.user_id
    ]
    return user_projects


# ============================================================================
# 2. Scanning & Pipeline Execution
# ============================================================================

@router.post(
    "/projects/{project_id}/scan",
    response_model=ScanJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Scan Job",
    description="Runs detection pipeline and queues parallel autonomous bug repair pipelines.",
)
async def start_scan(
    project_id: str,
    request: StartScanRequest = StartScanRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
) -> ScanJobResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    assert_project_ownership(project["owner_id"], current_user)

    job_id = str(uuid4())
    proj_dir = Path(project["project_dir"])
    cancel_token = CancellationToken()
    CANCELLATION_TOKENS[job_id] = cancel_token

    job_record = {
        "job_id": job_id,
        "project_id": project_id,
        "owner_id": current_user.user_id,
        "status": "RUNNING",
        "progress": 0.0,
        "total_bugs": 0,
        "completed_bugs": 0,
        "created_at": datetime.now(timezone.utc),
        "bug_ids": [],
    }
    JOBS_DB[job_id] = job_record

    # Asynchronous worker execution in background
    async def _async_scan_worker():
        try:
            intel_service.index_project(project_id, proj_dir)

            # Build file indices across all supported languages (Python, JS, TS)
            file_indices = []
            for p in proj_dir.rglob("*"):
                if not p.is_file():
                    continue
                if any(x in p.parts for x in [".git", "__pycache__", ".venv", "node_modules", "dist", "build"]):
                    continue
                adapter = intel_service.get_adapter_for_path(p)
                if adapter:
                    rel = str(p.relative_to(proj_dir))
                    try:
                        file_indices.append(adapter.parse_file(rel, p.read_text(encoding="utf-8", errors="replace")))
                    except Exception as pe:
                        logger.warning(f"Error indexing {rel}: {pe}")

            pipeline = DetectionPipeline()
            report = pipeline.run(project_id, proj_dir, file_indices, cancel_token=cancel_token)

            findings = report.findings
            job_record["total_bugs"] = len(findings)

            event_store.append(
                AuditEvent(
                    job_id=job_id,
                    event_type=EventType.FINDINGS_DETECTED,
                    actor="DETECTOR",
                    payload={"findings_count": len(findings)},
                )
            )

            # Execute parallel bug pipelines
            results = await orchestrator.execute_job(
                job_id=job_id,
                project_root=proj_dir,
                findings=findings,
                cancel_token=cancel_token,
            )

            job_record["bug_ids"] = [r.get("bug_id") for r in results if r.get("bug_id")]
            job_record["completed_bugs"] = sum(1 for r in results if r.get("status") == "COMPLETED")
            has_partial = any(r.get("status") == "SKIPPED_BUDGET_EXCEEDED" for r in results)
            if cancel_token.is_cancelled:
                job_record["status"] = "CANCELLED"
            elif has_partial or orchestrator.budget_manager.is_job_exceeded(job_id):
                job_record["status"] = "COMPLETED_PARTIAL"
            else:
                job_record["status"] = "COMPLETED"
            job_record["progress"] = 100.0 if not cancel_token.is_cancelled else job_record["progress"]

        except Exception as e:
            logger.error(f"Scan job {job_id} failed: {str(e)}")
            job_record["status"] = "FAILED"
            job_record["error"] = str(e)
            event_store.append(
                AuditEvent(
                    job_id=job_id,
                    event_type=EventType.JOB_FAILED,
                    actor="ORCHESTRATOR",
                    payload={"error": str(e)},
                )
            )

    background_tasks.add_task(_async_scan_worker)

    return ScanJobResponse(
        job_id=job_id,
        project_id=project_id,
        status="RUNNING",
        progress=0.0,
        total_bugs=0,
        completed_bugs=0,
        token_metrics=token_tracker.get_metrics(job_id),
        created_at=job_record["created_at"],
    )


class StartJobDirectRequest(BaseModel):
    project_id: str
    concurrency_limit: int = 3
    token_budget: int = 25000
    fast_path_templates: bool = True


@router.post(
    "/jobs",
    response_model=ScanJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Scan Job (Direct)",
    description="Alias to launch a scan job by passing project_id in JSON body.",
)
async def start_scan_job_direct(
    body: StartJobDirectRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
) -> ScanJobResponse:
    return await start_scan(
        project_id=body.project_id,
        request=StartScanRequest(
            concurrency_limit=body.concurrency_limit,
            token_budget=body.token_budget,
            fast_path_templates=body.fast_path_templates,
        ),
        background_tasks=background_tasks,
        current_user=current_user,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ScanJobResponse,
    summary="Get Job Status",
    description="Retrieves scan progress, status, token usage, and cost.",
)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> ScanJobResponse:
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    assert_project_ownership(job["owner_id"], current_user)

    metrics = token_tracker.get_metrics(job_id)
    total = max(1, job["total_bugs"])
    progress = round((job["completed_bugs"] / total) * 100.0, 1) if job["status"] != "COMPLETED" else 100.0

    return ScanJobResponse(
        job_id=job_id,
        project_id=job["project_id"],
        status=job["status"],
        progress=progress,
        total_bugs=job["total_bugs"],
        completed_bugs=job["completed_bugs"],
        token_metrics=metrics,
        created_at=job["created_at"],
    )


@router.get(
    "/jobs/{job_id}/events",
    summary="Stream Job Events (SSE)",
    description="Real-time Server-Sent Events (SSE) stream of agent traces, transitions, and token usage.",
)
async def stream_job_events(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    assert_project_ownership(job["owner_id"], current_user)

    async def _event_generator():
        last_seq = 0
        while True:
            if await request.is_disconnected():
                break

            events = event_store.get_events(job_id=job_id, after_sequence=last_seq)
            for ev in events:
                last_seq = ev.sequence_number
                sse_data = f"data: {json.dumps(ev.to_sse_dict())}\n\n"
                yield sse_data

            if job.get("status") in {"COMPLETED", "FAILED", "CANCELLED"} and not events:
                yield "data: {\"event\": \"DONE\", \"status\": \"STREAM_CLOSED\"}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@router.post(
    "/jobs/{job_id}/cancel",
    summary="Cancel Job",
    description="Interrupts running bug pipelines cleanly.",
)
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    assert_project_ownership(job["owner_id"], current_user)

    token = CANCELLATION_TOKENS.get(job_id)
    if token:
        token.cancel()

    job["status"] = "CANCELLED"
    event_store.append(
        AuditEvent(
            job_id=job_id,
            event_type=EventType.JOB_CANCELLED,
            actor=current_user.user_id,
            payload={"reason": "User requested cancellation"},
        )
    )
    return {"job_id": job_id, "status": "CANCELLED"}


@router.post(
    "/jobs/{job_id}/resume",
    response_model=ScanJobResponse,
    summary="Resume Job",
    description="Resumes an interrupted or cancelled job cleanly from the last committed stage.",
)
async def resume_job(
    job_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
):
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    assert_project_ownership(job["owner_id"], current_user)

    project = PROJECTS_DB.get(job["project_id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    cancel_token = CancellationToken()
    CANCELLATION_TOKENS[job_id] = cancel_token
    job["status"] = "RUNNING"

    async def _async_resume_worker():
        proj_dir = Path(project["project_dir"])
        events = event_store.get_events(job_id=job_id)
        # Find detected findings from initial event
        findings_ev = next((e for e in events if e.event_type == EventType.FINDINGS_DETECTED), None)
        findings_list = []
        if findings_ev:
            raw_findings = findings_ev.payload.get("findings", [])
            for rf in raw_findings:
                findings_list.append(Finding(**rf))

        await orchestrator.execute_job(
            job_id=job_id,
            project_root=proj_dir,
            findings=findings_list,
            cancel_token=cancel_token,
            resume=True,
        )
        job["status"] = "COMPLETED"

    background_tasks.add_task(_async_resume_worker)
    return ScanJobResponse(
        job_id=job_id,
        project_id=job["project_id"],
        status="RUNNING",
        progress=job.get("progress", 0.0),
        total_bugs=job.get("total_bugs", 0),
        completed_bugs=job.get("completed_bugs", 0),
        token_metrics=token_tracker.get_metrics(job_id),
        created_at=job["created_at"],
    )


# ============================================================================
# 3. Bug Details, Patching, and Human Decision
# ============================================================================

@router.get(
    "/projects/{project_id}/bugs",
    response_model=BugListResponse,
    summary="List Ranked Bugs",
    description="Returns prioritized bugs ordered deterministically by Priority score with optional filtering.",
)
async def list_bugs(
    project_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity level (CRITICAL, HIGH, MEDIUM, LOW)"),
    status: Optional[str] = Query(None, description="Filter by status (VERIFIED, NEEDS_REVIEW, FAILED, etc.)"),
    current_user: User = Depends(get_current_user),
) -> BugListResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    assert_project_ownership(project["owner_id"], current_user)

    # Find jobs for project
    project_jobs = [j["job_id"] for j in JOBS_DB.values() if j["project_id"] == project_id]
    bug_ids = set()
    for jid in project_jobs:
        events = event_store.get_events(job_id=jid)
        for ev in events:
            if ev.bug_id:
                bug_ids.add(ev.bug_id)

    bug_items: List[BugSummaryItem] = []
    for bid in bug_ids:
        state = event_store.reconstruct_bug_state(bid)
        finding = state.get("finding") or {}
        p_data = state.get("priority") or {}
        sev = p_data.get("severity") or {}
        conf = p_data.get("confidence") or {}

        bug_items.append(
            BugSummaryItem(
                bug_id=bid,
                file_path=finding.get("file", "unknown"),
                line_start=finding.get("line_start", 1),
                category=finding.get("category", "wrong_output"),
                description=finding.get("description", "Identified bug"),
                severity_level=sev.get("severity_level", "MEDIUM"),
                confidence=conf.get("overall_confidence", 0.70),
                priority_score=p_data.get("priority_score", 50.0),
                status=state.get("status", "INITIALIZED"),
                rank=p_data.get("rank", 1),
                rank_explanation=p_data.get("rank_explanation"),
                cwe=finding.get("cwe"),
                symbol=finding.get("symbol"),
            )
        )

    # Apply optional filtering
    if severity:
        bug_items = [b for b in bug_items if b.severity_level.upper() == severity.upper()]
    if status:
        bug_items = [b for b in bug_items if b.status.upper() == status.upper()]

    # Deterministic sort
    bug_items.sort(key=lambda b: (-b.priority_score, b.file_path, b.line_start))
    for idx, b in enumerate(bug_items, start=1):
        b.rank = idx

    return BugListResponse(
        project_id=project_id,
        total_bugs=len(bug_items),
        bugs=bug_items,
    )


@router.get(
    "/projects/{project_id}/bugs/{bug_id:path}",
    response_model=BugDetailResponse,
    summary="Get Bug Detail",
    description="Returns complete dossier: root cause, BRT evidence, candidate patches, and verification metrics.",
)
async def get_bug_detail(
    project_id: str,
    bug_id: str,
    current_user: User = Depends(get_current_user),
) -> BugDetailResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    state = event_store.reconstruct_bug_state(bug_id)
    if not state.get("exists"):
        raise HTTPException(status_code=404, detail=f"Bug '{bug_id}' not found in audit log.")

    return BugDetailResponse(
        bug_id=bug_id,
        status=state.get("status", "UNKNOWN"),
        finding=state.get("finding"),
        root_cause=state.get("root_cause"),
        reproduction=state.get("reproduction"),
        patches=state.get("patches", []),
        verification=state.get("verification"),
        priority=state.get("priority"),
        decision=state.get("decision"),
        is_patch_applied=state.get("is_patch_applied", False),
        completed_stages=state.get("completed_stages", []),
    )


@router.post(
    "/projects/{project_id}/bugs/{bug_id:path}/decision",
    response_model=DecisionResponse,
    summary="Record Human Decision",
    description="Enforces Rule 1 (Trust): explicit human approval required. Applies patch when approved.",
)
async def record_decision(
    project_id: str,
    bug_id: str,
    request: DecisionRequest,
    current_user: User = Depends(get_current_user),
) -> DecisionResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    state = event_store.reconstruct_bug_state(bug_id)
    if not state.get("exists"):
        raise HTTPException(status_code=404, detail="Bug not found.")

    decision_status = ApprovalStatus(request.decision)
    bundle_id = uuid4()

    approval = ApprovalDecision(
        bundle_id=bundle_id,
        reviewer_id=current_user.user_id,
        status=decision_status,
        comment=request.comment,
    )

    # Persist decision to immutable event log
    event_store.append(
        AuditEvent(
            job_id=bug_id.split(":")[0],
            bug_id=bug_id,
            event_type=EventType.DECISION_RECORDED,
            actor=current_user.user_id,
            payload={"decision": approval.model_dump(mode="json")},
        )
    )

    applied = False
    chosen_patch_id = None
    chosen_patch_hash = None

    if decision_status == ApprovalStatus.APPROVED:
        patches = state.get("patches", [])
        best_patch = None

        # P1 — 6: Apply the exact reviewed/selected patch, never regenerate
        if request.patch_id:
            best_patch = next((p for p in patches if str(p.get("id")) == str(request.patch_id)), None)
        if not best_patch and patches:
            ver = state.get("verification") or {}
            sel_id = ver.get("selected_patch_id")
            if sel_id:
                best_patch = next((p for p in patches if str(p.get("id")) == str(sel_id)), None)
            if not best_patch:
                best_patch = patches[0]

        if best_patch:
            chosen_patch_id = best_patch.get("id")
            chosen_patch_hash = best_patch.get("patch_hash")
            proj_dir = Path(project["project_dir"])
            target_file = proj_dir / best_patch["file"]
            if target_file.is_file():
                content = target_file.read_text(encoding="utf-8", errors="replace")
                orig = best_patch.get("original_snippet", "")
                patched = best_patch.get("patched_snippet", "")
                if orig in content:
                    target_file.write_text(content.replace(orig, patched, 1), encoding="utf-8")
                    applied = True
                    project["applied_patches"][bug_id] = best_patch
                    storage.save_project(project)
                    event_store.append(
                        AuditEvent(
                            job_id=bug_id.split(":")[0],
                            bug_id=bug_id,
                            event_type=EventType.PATCH_APPLIED,
                            actor=current_user.user_id,
                            payload={
                                "patch_id": best_patch.get("id"),
                                "patch_hash": chosen_patch_hash,
                                "file": best_patch["file"],
                            },
                        )
                    )

    # Persist decision to SQLite database
    storage.save_decision({
        "bug_id": bug_id,
        "project_id": project_id,
        "reviewer_id": current_user.user_id,
        "status": decision_status.value,
        "comment": request.comment,
        "signature_hash": approval.signature_hash,
        "patch_id": str(chosen_patch_id) if chosen_patch_id else None,
        "patch_hash": chosen_patch_hash,
        "timestamp": approval.timestamp.isoformat(),
    })

    return DecisionResponse(
        bug_id=bug_id,
        reviewer_id=current_user.user_id,
        status=decision_status.value,
        comment=request.comment,
        signature_hash=approval.signature_hash,
        applied=applied,
        patch_id=str(chosen_patch_id) if chosen_patch_id else None,
        patch_hash=chosen_patch_hash,
        timestamp=approval.timestamp,
    )


@router.post(
    "/projects/{project_id}/bugs/{bug_id:path}/revert",
    response_model=RevertResponse,
    summary="Revert Applied Patch",
    description="Cleanly rolls back an applied patch in the working project tree.",
)
async def revert_patch(
    project_id: str,
    bug_id: str,
    current_user: User = Depends(get_current_user),
) -> RevertResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    applied_patch = project["applied_patches"].get(bug_id)
    if not applied_patch:
        raise HTTPException(status_code=400, detail="No applied patch found for this bug.")

    proj_dir = Path(project["project_dir"])
    target_file = proj_dir / applied_patch["file"]
    if target_file.is_file():
        content = target_file.read_text(encoding="utf-8", errors="replace")
        orig = applied_patch.get("original_snippet", "")
        patched = applied_patch.get("patched_snippet", "")
        if patched in content:
            target_file.write_text(content.replace(patched, orig, 1), encoding="utf-8")

    del project["applied_patches"][bug_id]
    storage.save_project(project)
    event_store.append(
        AuditEvent(
            job_id=bug_id.split(":")[0],
            bug_id=bug_id,
            event_type=EventType.PATCH_REVERTED,
            actor=current_user.user_id,
            payload={"file": applied_patch["file"]},
        )
    )

    return RevertResponse(
        bug_id=bug_id,
        reverted=True,
        message=f"Patch reverted cleanly for '{applied_patch['file']}'.",
    )


# ============================================================================
# 4. Export & Audit History
# ============================================================================

@router.get(
    "/projects/{project_id}/export",
    summary="Export Artifacts",
    description="Exports project results in diff, markdown, sarif, html, json, or zip format.",
)
async def export_artifacts(
    project_id: str,
    format: str = Query("markdown", pattern="^(diff|markdown|sarif|zip|html|json)$"),
    current_user: User = Depends(get_current_user),
):
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    # Gather all bug states
    project_jobs = [j["job_id"] for j in JOBS_DB.values() if j["project_id"] == project_id]
    bug_ids = set()
    for jid in project_jobs:
        events = event_store.get_events(job_id=jid)
        for ev in events:
            if ev.bug_id:
                bug_ids.add(ev.bug_id)

    bug_states = [event_store.reconstruct_bug_state(bid) for bid in bug_ids]

    if format == "diff":
        all_patches = []
        for bs in bug_states:
            all_patches.extend(bs.get("patches", []))
        diff_text = ProjectExporter.export_unified_diff(all_patches)
        return PlainTextResponse(diff_text, media_type="text/x-diff")

    elif format == "markdown":
        md_text = ProjectExporter.export_markdown_report(project["name"], bug_states)
        return PlainTextResponse(md_text, media_type="text/markdown")

    elif format == "sarif":
        sarif_json = ProjectExporter.export_sarif_json(project["name"], bug_states)
        return JSONResponse(sarif_json, media_type="application/sarif+json")

    elif format == "html":
        html_text = ProjectExporter.export_interactive_html_report(project["name"], bug_states)
        return HTMLResponse(content=html_text, media_type="text/html")

    elif format == "json":
        return JSONResponse(
            {
                "project_id": project_id,
                "project_name": project["name"],
                "total_bugs": len(bug_states),
                "bugs": bug_states,
            }
        )

    elif format == "zip":
        proj_dir = Path(project["project_dir"])
        zip_bytes = ProjectExporter.export_patched_project_zip(proj_dir)
        return Response(
            zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={project['name']}_patched.zip"},
        )


@router.get(
    "/projects/{project_id}/report",
    summary="Get Full Inspection Report",
    description="Returns the full interactive HTML report or downloadable report for a project.",
)
async def get_project_report(
    project_id: str,
    format: str = Query("html", pattern="^(html|markdown|sarif|json|diff)$"),
    current_user: User = Depends(get_current_user),
):
    return await export_artifacts(project_id=project_id, format=format, current_user=current_user)


@router.get(
    "/projects/{project_id}/history",
    response_model=HistoryResponse,
    summary="Get Project Audit History",
    description="Returns immutable append-only event log across all scan jobs and human decisions.",
)
async def get_project_history(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> HistoryResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    project_jobs = [j["job_id"] for j in JOBS_DB.values() if j["project_id"] == project_id]
    all_events: List[Dict[str, Any]] = []
    for jid in project_jobs:
        evs = event_store.get_events(job_id=jid)
        all_events.extend([e.model_dump(mode="json") for e in evs])

    all_events.sort(key=lambda e: e.get("sequence_number", 0))

    return HistoryResponse(
        project_id=project_id,
        total_events=len(all_events),
        events=all_events,
    )


# ============================================================================
# 5. Git & GitHub Integration
# ============================================================================

git_service = GitService()

@router.post(
    "/projects/{project_id}/git/branch",
    response_model=CreateRemediationBranchResponse,
    summary="Create Remediation Branch",
    description="Creates a branch containing ONLY accepted patches, one commit per bug with root cause and test evidence.",
)
async def create_git_remediation_branch(
    project_id: str,
    request: CreateRemediationBranchRequest,
    current_user: User = Depends(get_current_user),
) -> CreateRemediationBranchResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    # Gather all bug states for project
    project_jobs = [j["job_id"] for j in JOBS_DB.values() if j["project_id"] == project_id]
    bug_ids = set()
    for jid in project_jobs:
        for ev in event_store.get_events(job_id=jid):
            if ev.bug_id:
                bug_ids.add(ev.bug_id)

    bug_states = [event_store.reconstruct_bug_state(bid) for bid in bug_ids]
    proj_dir = Path(project["project_dir"])

    try:
        result = git_service.create_remediation_branch(
            repo_dir=proj_dir,
            branch_name=request.branch_name,
            base_branch=request.base_branch,
            bug_states=bug_states,
            include_brt_tests=request.include_brt_tests,
        )
    except GitIntegrationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_store.append(
        AuditEvent(
            job_id=project_id,
            event_type=EventType.BRANCH_CREATED if hasattr(EventType, "BRANCH_CREATED") else EventType.PATCH_APPLIED,
            actor=current_user.user_id,
            payload={
                "branch_name": result.branch_name,
                "commits_count": len(result.commits),
                "bugs_included": result.bugs_included,
            },
        )
    )

    return CreateRemediationBranchResponse(
        branch_name=result.branch_name,
        base_branch=result.base_branch,
        total_commits=len(result.commits),
        bugs_included=result.bugs_included,
        bugs_skipped=result.bugs_skipped,
        commits=[c.model_dump(mode="json") for c in result.commits],
    )


@router.post(
    "/projects/{project_id}/git/pull-request",
    response_model=OpenPullRequestResponse,
    summary="Open GitHub Pull Request",
    description="Opens a pull request on GitHub via REST API with a Markdown evidence table (BRT before/after, regressions, confidence).",
)
async def open_github_pull_request(
    project_id: str,
    request: OpenPullRequestRequest,
    current_user: User = Depends(get_current_user),
) -> OpenPullRequestResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    project_jobs = [j["job_id"] for j in JOBS_DB.values() if j["project_id"] == project_id]
    bug_ids = set()
    for jid in project_jobs:
        for ev in event_store.get_events(job_id=jid):
            if ev.bug_id:
                bug_ids.add(ev.bug_id)

    bug_states = [event_store.reconstruct_bug_state(bid) for bid in bug_ids]
    approved_bugs = [
        b for b in bug_states
        if (b.get("decision", {}).get("status") == "APPROVED") or b.get("is_patch_applied", False)
    ]

    title = request.title or f"[AutoPatch] Fix {len(approved_bugs)} verified defects in {project['name']}"
    body_markdown = generate_pr_markdown_description(
        project_name=project["name"],
        base_branch=request.base_branch,
        remediation_branch=request.head_branch,
        approved_bug_states=approved_bugs,
    )

    client = GitHubClient(token=request.github_token)
    try:
        pr_result = await client.open_pull_request(
            repo_slug=request.repo_slug,
            head_branch=request.head_branch,
            base_branch=request.base_branch,
            title=title,
            body_markdown=body_markdown,
        )
    except GitHubTokenMissingError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except GitHubApiError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    return OpenPullRequestResponse(
        pr_number=pr_result.pr_number,
        html_url=pr_result.html_url,
        head_branch=pr_result.head_branch,
        base_branch=pr_result.base_branch,
        title=pr_result.title,
        body_markdown=body_markdown,
    )


@router.post(
    "/projects/{project_id}/git/revert",
    response_model=RevertCommitResponse,
    summary="Revert Commit-Linked Change",
    description="Reverts a commit-linked bug remediation and verifies the exact prior state is restored.",
)
async def revert_git_commit(
    project_id: str,
    request: RevertCommitRequest,
    current_user: User = Depends(get_current_user),
) -> RevertCommitResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    proj_dir = Path(project["project_dir"])
    try:
        result = git_service.revert_bug_commit(
            repo_dir=proj_dir,
            bug_id_or_commit_sha=request.bug_id_or_commit_sha,
        )
    except GitIntegrationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RevertCommitResponse(
        bug_id=result.bug_id,
        target_commit_sha=result.target_commit_sha,
        revert_commit_sha=result.revert_commit_sha,
        is_clean=result.is_clean,
        restored_files=result.restored_files,
        message=result.message,
    )


# ============================================================================
# 6. Data Retention & Artifact Purge
# ============================================================================

retention_manager = DataRetentionManager()


@router.delete(
    "/projects/{project_id}/purge",
    response_model=PurgeResponse,
    summary="Purge Project Artifacts & Records",
    description="Completely removes all extracted source files, temporary working copies, audit logs, and DB records.",
)
async def purge_project_artifacts(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> PurgeResponse:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    proj_dir = Path(project["project_dir"])
    report = retention_manager.purge_project(
        project_id=project_id,
        project_dir=proj_dir,
        event_store=event_store,
        projects_db=PROJECTS_DB,
        jobs_db=JOBS_DB,
    )

    return PurgeResponse(
        target_id=report.target_id,
        target_type=report.target_type,
        success=report.success,
        deleted_paths=report.deleted_paths,
        purged_events_count=report.purged_events_count,
        purged_jobs_count=report.purged_jobs_count,
        message=report.message,
    )


@router.delete(
    "/jobs/{job_id}/purge",
    response_model=PurgeResponse,
    summary="Purge Scan Job Data",
    description="Purges an individual scan job and its associated events and temporary runner files.",
)
async def purge_job_artifacts(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> PurgeResponse:
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("owner_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="Cross-user access forbidden.")

    report = retention_manager.purge_job(
        job_id=job_id,
        event_store=event_store,
        jobs_db=JOBS_DB,
    )

    return PurgeResponse(
        target_id=report.target_id,
        target_type=report.target_type,
        success=report.success,
        deleted_paths=report.deleted_paths,
        purged_events_count=report.purged_events_count,
        purged_jobs_count=report.purged_jobs_count,
        message=report.message,
    )


# ============================================================================
# 11. Cost Dashboard & Deterministic Replay
# ============================================================================

@router.get(
    "/projects/{project_id}/costs",
    response_model=ProjectCostSummary,
    summary="Get Project Cost & Token Dashboard",
    description="Returns aggregate token metrics, USD costs by agent and model, and cache savings for a project.",
)
async def get_project_costs(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> ProjectCostSummary:
    project = PROJECTS_DB.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    assert_project_ownership(project["owner_id"], current_user)

    summary = global_dashboard_service.get_project_cost_summary(
        project_id=project_id,
        jobs_db=JOBS_DB,
    )
    return summary


@router.post(
    "/jobs/{job_id}/replay",
    response_model=ReplayResult,
    summary="Replay Job Traces Deterministically",
    description="Re-runs stored execution traces for a scan job using cached responses without making new LLM calls.",
)
async def replay_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> ReplayResult:
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("owner_id") != current_user.user_id:
        raise HTTPException(status_code=403, detail="Cross-user access forbidden.")

    result = global_replay_engine.replay_trace(target_id=job_id, target_type="job")
    return result



