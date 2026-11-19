"""Durable SQLite storage engine for project metadata, jobs, findings, and decisions.

Guarantees persistence and recovery across server restarts with complete audit trails.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopatch.core.logging import get_logger

logger = get_logger(__name__)


def get_default_db_path() -> Path:
    env_path = os.getenv("AUTOPATCH_DB_PATH")
    if env_path:
        p = Path(env_path)
    else:
        # Default to user home or fallback to /tmp
        try:
            home = Path.home() / ".autopatch"
            home.mkdir(parents=True, exist_ok=True)
            p = home / "autopatch.db"
        except Exception:
            tmp = Path("/tmp/autopatch")
            tmp.mkdir(parents=True, exist_ok=True)
            p = tmp / "autopatch.db"

    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class DatabaseManager:
    """Provides ACID-compliant persistent storage backed by SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or get_default_db_path())
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    project_dir TEXT NOT NULL,
                    github_url TEXT,
                    created_at TEXT NOT NULL,
                    applied_patches TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS scan_jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0.0,
                    total_bugs INTEGER NOT NULL DEFAULT 0,
                    completed_bugs INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    token_metrics TEXT NOT NULL DEFAULT '{}',
                    bug_ids TEXT NOT NULL DEFAULT '[]',
                    error TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    bug_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    comment TEXT,
                    signature_hash TEXT,
                    patch_id TEXT,
                    patch_hash TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    file TEXT NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    cwe TEXT,
                    raw_confidence REAL,
                    description TEXT,
                    evidence TEXT,
                    raw_data TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_project ON scan_jobs(project_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);
                CREATE INDEX IF NOT EXISTS idx_findings_project ON findings(project_id);
                CREATE INDEX IF NOT EXISTS idx_findings_job ON findings(job_id);
                """
            )
            conn.commit()

    # --- Project Operations ---
    def save_project(self, project: Dict[str, Any]) -> None:
        created_at = project.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        elif not created_at:
            created_at = datetime.now(timezone.utc).isoformat()

        applied = project.get("applied_patches", {})
        if not isinstance(applied, str):
            applied = json.dumps(applied)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (project_id, name, owner_id, project_dir, github_url, created_at, applied_patches)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    name=excluded.name,
                    project_dir=excluded.project_dir,
                    github_url=excluded.github_url,
                    applied_patches=excluded.applied_patches;
                """,
                (
                    project["project_id"],
                    project["name"],
                    project["owner_id"],
                    str(project["project_dir"]),
                    project.get("github_url"),
                    created_at,
                    applied,
                ),
            )
            conn.commit()

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["applied_patches"] = json.loads(res.get("applied_patches") or "{}")
            except Exception:
                res["applied_patches"] = {}
            return res

    def list_projects_for_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                p = dict(r)
                try:
                    p["applied_patches"] = json.loads(p.get("applied_patches") or "{}")
                except Exception:
                    p["applied_patches"] = {}
                results.append(p)
            return results

    def delete_project(self, project_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM scan_jobs WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM findings WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM decisions WHERE project_id = ?", (project_id,))
            conn.commit()

    # --- Scan Job Operations ---
    def save_job(self, job: Dict[str, Any]) -> None:
        created_at = job.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        elif not created_at:
            created_at = datetime.now(timezone.utc).isoformat()

        token_metrics = job.get("token_metrics", {})
        if not isinstance(token_metrics, str):
            if hasattr(token_metrics, "model_dump"):
                token_metrics = json.dumps(token_metrics.model_dump())
            else:
                token_metrics = json.dumps(token_metrics)

        bug_ids = job.get("bug_ids", [])
        if not isinstance(bug_ids, str):
            bug_ids = json.dumps(bug_ids)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scan_jobs (job_id, project_id, owner_id, status, progress, total_bugs, completed_bugs, created_at, token_metrics, bug_ids, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    progress=excluded.progress,
                    total_bugs=excluded.total_bugs,
                    completed_bugs=excluded.completed_bugs,
                    token_metrics=excluded.token_metrics,
                    bug_ids=excluded.bug_ids,
                    error=excluded.error;
                """,
                (
                    job["job_id"],
                    job["project_id"],
                    job["owner_id"],
                    job["status"],
                    float(job.get("progress", 0.0)),
                    int(job.get("total_bugs", 0)),
                    int(job.get("completed_bugs", 0)),
                    created_at,
                    token_metrics,
                    bug_ids,
                    job.get("error"),
                ),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["token_metrics"] = json.loads(res.get("token_metrics") or "{}")
            except Exception:
                res["token_metrics"] = {}
            try:
                res["bug_ids"] = json.loads(res.get("bug_ids") or "[]")
            except Exception:
                res["bug_ids"] = []
            return res

    def list_jobs_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_jobs WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                j = dict(r)
                try:
                    j["token_metrics"] = json.loads(j.get("token_metrics") or "{}")
                except Exception:
                    j["token_metrics"] = {}
                try:
                    j["bug_ids"] = json.loads(j.get("bug_ids") or "[]")
                except Exception:
                    j["bug_ids"] = []
                results.append(j)
            return results

    def delete_job(self, job_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM scan_jobs WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM findings WHERE job_id = ?", (job_id,))
            conn.commit()

    # --- Findings Operations ---
    def save_finding(self, finding: Dict[str, Any]) -> None:
        finding_id = finding.get("finding_id") or f"{finding['job_id']}:{finding['file']}:{finding['line_start']}"
        raw_data = finding.get("raw_data") or finding
        if not isinstance(raw_data, str):
            raw_data = json.dumps(raw_data)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO findings (finding_id, project_id, job_id, file, line_start, line_end, category, cwe, raw_confidence, description, evidence, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(finding_id) DO UPDATE SET
                    description=excluded.description,
                    evidence=excluded.evidence,
                    raw_data=excluded.raw_data;
                """,
                (
                    finding_id,
                    finding["project_id"],
                    finding["job_id"],
                    finding["file"],
                    finding["line_start"],
                    finding["line_end"],
                    finding["category"],
                    finding.get("cwe"),
                    float(finding.get("raw_confidence", 0.7)),
                    finding.get("description"),
                    finding.get("evidence"),
                    raw_data,
                ),
            )
            conn.commit()

    def list_findings_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE project_id = ?", (project_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Decisions Operations ---
    def save_decision(self, decision: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO decisions (bug_id, project_id, reviewer_id, status, comment, signature_hash, patch_id, patch_hash, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bug_id) DO UPDATE SET
                    status=excluded.status,
                    comment=excluded.comment,
                    signature_hash=excluded.signature_hash,
                    patch_id=excluded.patch_id,
                    patch_hash=excluded.patch_hash,
                    timestamp=excluded.timestamp;
                """,
                (
                    decision["bug_id"],
                    decision["project_id"],
                    decision["reviewer_id"],
                    decision["status"],
                    decision.get("comment"),
                    decision.get("signature_hash"),
                    decision.get("patch_id"),
                    decision.get("patch_hash"),
                    decision.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_decision(self, bug_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM decisions WHERE bug_id = ?", (bug_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


_global_storage: Optional[DatabaseManager] = None


def get_storage(db_path: Optional[Path] = None) -> DatabaseManager:
    global _global_storage
    if _global_storage is None or db_path is not None:
        _global_storage = DatabaseManager(db_path=db_path)
    return _global_storage
