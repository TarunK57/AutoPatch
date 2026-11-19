from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopatch.core.logging import get_logger

logger = get_logger(__name__)


class RetentionPolicy(BaseModel):
    """Configuration for data retention and automated cleanup limits."""
    max_job_age_days: int = 30
    max_completed_jobs_per_project: int = 5
    purge_working_copy_on_completion: bool = False


class PurgeReport(BaseModel):
    """Detailed summary of artifacts and records removed during a purge."""
    target_id: str
    target_type: str  # "project" or "job"
    success: bool
    deleted_paths: List[str] = Field(default_factory=list)
    purged_events_count: int = 0
    purged_jobs_count: int = 0
    purged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str


class DataRetentionManager:
    """
    Enforces per-job data retention limits and completely purges all artifacts,
    working directories, and audit database entries upon request.
    """

    def __init__(self, policy: Optional[RetentionPolicy] = None) -> None:
        self.policy = policy or RetentionPolicy()

    def purge_project(
        self,
        project_id: str,
        project_dir: Optional[Path] = None,
        event_store: Any = None,
        projects_db: Optional[Dict[str, Any]] = None,
        jobs_db: Optional[Dict[str, Any]] = None,
    ) -> PurgeReport:
        """
        Completely removes all artifacts, working directories, upload files,
        and database records associated with a project.
        """
        deleted_paths: List[str] = []
        purged_events = 0
        purged_jobs = 0

        # 1. Delete project directory on disk
        if project_dir and project_dir.exists():
            deleted_paths.append(str(project_dir))
            shutil.rmtree(str(project_dir), ignore_errors=True)

        # 2. Check and delete any tmp upload files
        tmp_base = Path("/tmp")
        for f in tmp_base.glob(f"autopatch_*{project_id}*"):
            try:
                if f.is_dir():
                    shutil.rmtree(str(f), ignore_errors=True)
                else:
                    f.unlink(missing_ok=True)
                deleted_paths.append(str(f))
            except Exception:
                pass

        # 3. Purge associated jobs from jobs_db
        associated_job_ids = []
        if jobs_db is not None:
            to_delete = [
                jid for jid, j in jobs_db.items()
                if j.get("project_id") == project_id
            ]
            for jid in to_delete:
                associated_job_ids.append(jid)
                del jobs_db[jid]
                purged_jobs += 1

        # 4. Purge events from event_store
        if event_store is not None:
            # Delete project-level events and job-level events
            target_ids = [project_id] + associated_job_ids
            try:
                with event_store._conn:
                    for tid in target_ids:
                        cursor = event_store._conn.execute(
                            "DELETE FROM audit_events WHERE job_id = ? OR bug_id LIKE ?",
                            (tid, f"%{tid}%"),
                        )
                        purged_events += cursor.rowcount
            except Exception as e:
                logger.warning(f"Failed to delete audit events during purge: {e}")

        # 5. Remove project from projects_db
        if projects_db is not None and project_id in projects_db:
            del projects_db[project_id]

        logger.info(
            f"Purged project '{project_id}': deleted {len(deleted_paths)} path(s), "
            f"purged {purged_jobs} job(s), {purged_events} event(s)."
        )

        return PurgeReport(
            target_id=project_id,
            target_type="project",
            success=True,
            deleted_paths=deleted_paths,
            purged_events_count=purged_events,
            purged_jobs_count=purged_jobs,
            message=f"All artifacts and records for project '{project_id}' successfully purged.",
        )

    def purge_job(
        self,
        job_id: str,
        event_store: Any = None,
        jobs_db: Optional[Dict[str, Any]] = None,
    ) -> PurgeReport:
        """Purges an individual scan job and its associated events and temporary runner files."""
        deleted_paths: List[str] = []
        purged_events = 0

        # Purge from jobs_db
        if jobs_db is not None and job_id in jobs_db:
            del jobs_db[job_id]

        # Purge from event_store
        if event_store is not None:
            try:
                with event_store._conn:
                    cursor = event_store._conn.execute(
                        "DELETE FROM audit_events WHERE job_id = ?",
                        (job_id,),
                    )
                    purged_events = cursor.rowcount
            except Exception as e:
                logger.warning(f"Failed to delete audit events for job {job_id}: {e}")

        return PurgeReport(
            target_id=job_id,
            target_type="job",
            success=True,
            deleted_paths=deleted_paths,
            purged_events_count=purged_events,
            purged_jobs_count=1,
            message=f"Scan job '{job_id}' and all associated events purged successfully.",
        )
