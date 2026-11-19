"""Append-only audit event store and event-sourced state reconstruction engine.

Enforces:
- Every pipeline transition is recorded as an immutable append-only event.
- Complete state of any bug or job can be deterministically reconstructed from events.
- Audit log persists event payloads, token usage, actors, and cryptographic decision signatures.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from autopatch.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Categorical types of append-only pipeline audit events."""

    JOB_STARTED = "JOB_STARTED"
    SCAN_STARTED = "SCAN_STARTED"
    FINDINGS_DETECTED = "FINDINGS_DETECTED"
    BUG_PIPELINE_STARTED = "BUG_PIPELINE_STARTED"
    LOCATOR_STARTED = "LOCATOR_STARTED"
    LOCATOR_COMPLETED = "LOCATOR_COMPLETED"
    REPRODUCER_STARTED = "REPRODUCER_STARTED"
    REPRODUCER_STEP = "REPRODUCER_STEP"
    REPRODUCER_COMPLETED = "REPRODUCER_COMPLETED"
    PATCHER_STARTED = "PATCHER_STARTED"
    PATCHER_COMPLETED = "PATCHER_COMPLETED"
    VERIFIER_STARTED = "VERIFIER_STARTED"
    VERIFIER_COMPLETED = "VERIFIER_COMPLETED"
    SCORING_COMPLETED = "SCORING_COMPLETED"
    BUG_COMPLETED = "BUG_COMPLETED"
    DECISION_RECORDED = "DECISION_RECORDED"
    PATCH_APPLIED = "PATCH_APPLIED"
    PATCH_REVERTED = "PATCH_REVERTED"
    BRANCH_CREATED = "BRANCH_CREATED"
    PULL_REQUEST_OPENED = "PULL_REQUEST_OPENED"
    JOB_CANCELLED = "JOB_CANCELLED"
    JOB_FAILED = "JOB_FAILED"
    JOB_COMPLETED = "JOB_COMPLETED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"


class AuditEvent(BaseModel):
    """Immutable event record representing a discrete pipeline action or transition."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    bug_id: Optional[str] = None
    sequence_number: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType
    actor: str = "SYSTEM"  # "ORCHESTRATOR", "LOCATOR", "REPRODUCER", "USER", etc.
    payload: Dict[str, Any] = Field(default_factory=dict)

    def to_sse_dict(self) -> Dict[str, Any]:
        """Formats event for Server-Sent Events (SSE) streaming."""
        return {
            "id": self.event_id,
            "event": self.event_type.value,
            "job_id": self.job_id,
            "bug_id": self.bug_id,
            "seq": self.sequence_number,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "payload": self.payload,
        }


class EventStore:
    """Persistent append-only event store backed by SQLite for state reconstruction and SSE streams."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = ":memory:"
            self._conn: Optional[sqlite3.Connection] = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        else:
            self.db_path = str(db_path)
            self._conn = None
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    bug_id TEXT,
                    sequence_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_job_seq ON audit_events (job_id, sequence_number);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_bug ON audit_events (bug_id);
                """
            )
            conn.commit()

    def append(self, event: AuditEvent) -> AuditEvent:
        """Appends an event to the immutable store with monotonic sequence numbering."""
        with self._get_connection() as conn:
            # Determine next sequence number for this job
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM audit_events WHERE job_id = ?",
                (event.job_id,),
            )
            next_seq = cursor.fetchone()[0]
            event.sequence_number = next_seq

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, bug_id, sequence_number, timestamp, event_type, actor, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.event_id,
                    event.job_id,
                    event.bug_id,
                    event.sequence_number,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.actor,
                    json.dumps(event.payload, default=str),
                ),
            )
            conn.commit()

        logger.debug(
            f"Appended event {event.event_type.value} [seq={event.sequence_number}] for job {event.job_id}",
            extra={"data": {"event_id": event.event_id, "bug_id": event.bug_id}},
        )
        return event

    def get_events(
        self,
        job_id: str,
        bug_id: Optional[str] = None,
        after_sequence: int = 0,
    ) -> List[AuditEvent]:
        """Retrieves ordered events for a job or bug after a specific sequence number."""
        query = "SELECT * FROM audit_events WHERE job_id = ? AND sequence_number > ?"
        params: List[Any] = [job_id, after_sequence]

        if bug_id:
            query += " AND bug_id = ?"
            params.append(bug_id)

        query += " ORDER BY sequence_number ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        events: List[AuditEvent] = []
        for r in rows:
            events.append(
                AuditEvent(
                    event_id=r["event_id"],
                    job_id=r["job_id"],
                    bug_id=r["bug_id"],
                    sequence_number=r["sequence_number"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    event_type=EventType(r["event_type"]),
                    actor=r["actor"],
                    payload=json.loads(r["payload"]),
                )
            )
        return events

    def get_recent_events(
        self,
        limit: int = 50,
        job_id: Optional[str] = None,
        job_ids: Optional[List[str]] = None,
    ) -> List[AuditEvent]:
        """Retrieves most recent events across all jobs or for specified job IDs."""
        query = "SELECT * FROM audit_events"
        params: List[Any] = []
        if job_id:
            query += " WHERE job_id = ?"
            params.append(job_id)
        elif job_ids is not None and len(job_ids) > 0:
            placeholders = ",".join("?" for _ in job_ids)
            query += f" WHERE job_id IN ({placeholders})"
            params.extend(job_ids)

        query += " ORDER BY timestamp DESC, sequence_number DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        events: List[AuditEvent] = []
        for r in rows:
            events.append(
                AuditEvent(
                    event_id=r["event_id"],
                    job_id=r["job_id"],
                    bug_id=r["bug_id"],
                    sequence_number=r["sequence_number"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    event_type=EventType(r["event_type"]),
                    actor=r["actor"],
                    payload=json.loads(r["payload"]),
                )
            )
        return events

    def reconstruct_bug_state(self, bug_id: str) -> Dict[str, Any]:
        """Reconstructs the full lifecycle state of a bug by replaying its audit events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_events WHERE bug_id = ? ORDER BY sequence_number ASC",
                (bug_id,),
            )
            rows = cursor.fetchall()

        if not rows:
            return {"bug_id": bug_id, "status": "UNKNOWN", "exists": False}

        state: Dict[str, Any] = {
            "bug_id": bug_id,
            "exists": True,
            "status": "INITIALIZED",
            "finding": None,
            "root_cause": None,
            "reproduction": None,
            "patches": [],
            "verification": None,
            "priority": None,
            "decision": None,
            "is_patch_applied": False,
            "completed_stages": [],
            "event_count": len(rows),
            "history": [],
        }

        for r in rows:
            ev_type = EventType(r["event_type"])
            payload = json.loads(r["payload"])
            state["history"].append({"type": ev_type.value, "time": r["timestamp"]})

            if ev_type == EventType.BUG_PIPELINE_STARTED:
                state["status"] = "ANALYZING"
                state["finding"] = payload.get("finding")
                state["completed_stages"].append("STARTED")

            elif ev_type == EventType.LOCATOR_COMPLETED:
                state["root_cause"] = payload.get("root_cause")
                state["completed_stages"].append("LOCATOR")

            elif ev_type == EventType.REPRODUCER_COMPLETED:
                state["reproduction"] = payload.get("reproduction")
                state["completed_stages"].append("REPRODUCER")

            elif ev_type == EventType.PATCHER_COMPLETED:
                state["patches"] = payload.get("candidate_patches", [])
                state["completed_stages"].append("PATCHER")

            elif ev_type == EventType.VERIFIER_COMPLETED:
                state["verification"] = payload.get("verification")
                state["completed_stages"].append("VERIFIER")

            elif ev_type == EventType.SCORING_COMPLETED:
                state["priority"] = payload.get("priority")
                state["completed_stages"].append("SCORING")

            elif ev_type == EventType.BUG_COMPLETED:
                state["status"] = "COMPLETED"
                state["completed_stages"].append("COMPLETED")

            elif ev_type == EventType.DECISION_RECORDED:
                state["decision"] = payload.get("decision")
                state["status"] = f"DECIDED_{payload.get('decision', {}).get('status', 'RECORDED')}"

            elif ev_type == EventType.PATCH_APPLIED:
                state["is_patch_applied"] = True
                state["status"] = "APPLIED"

            elif ev_type == EventType.PATCH_REVERTED:
                state["is_patch_applied"] = False
                state["status"] = "REVERTED"

            elif ev_type == EventType.JOB_CANCELLED:
                state["status"] = "CANCELLED"

            elif ev_type == EventType.JOB_FAILED:
                state["status"] = "FAILED"
                state["error"] = payload.get("error")

        return state
