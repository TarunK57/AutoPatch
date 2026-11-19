from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from autopatch.core.logging import get_logger
from autopatch.observability.models import AgentStepTrace, TraceOutcome
from autopatch.orchestrator.tokens import PRICING_PER_MILLION

logger = get_logger(__name__)


def compute_prompt_hash(prompt: str) -> str:
    """Computes a canonical SHA-256 hex digest of a prompt text."""
    return hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()


class StructuredTracer:
    """
    Records and queries structured execution traces for every agent step.
    Maintains prompt hashes, tool invocations, token spend, latency, and outcomes.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_step_traces (
                    step_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    bug_id TEXT,
                    agent_name TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    prompt_length INTEGER NOT NULL,
                    tools_called TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    outcome TEXT NOT NULL,
                    cached INTEGER NOT NULL,
                    model_used TEXT NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_job ON agent_step_traces (job_id);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_bug ON agent_step_traces (bug_id);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_hash ON agent_step_traces (prompt_hash);")

    def record_step(
        self,
        job_id: str,
        agent_name: str,
        stage: str,
        prompt: str,
        tools_called: Optional[List[Dict[str, Any]]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0.0,
        outcome: TraceOutcome = TraceOutcome.SUCCESS,
        cached: bool = False,
        model_used: str = "claude-3-5-sonnet",
        bug_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AgentStepTrace:
        """Records an agent step trace into the persistent store."""
        prompt_hash = compute_prompt_hash(prompt)
        prompt_len = len(prompt)
        tools = tools_called or []
        tot_tokens = prompt_tokens + completion_tokens

        # Calculate cost
        pricing = PRICING_PER_MILLION.get(model_used, PRICING_PER_MILLION["default"])
        cost = (prompt_tokens / 1_000_000.0) * pricing["input"] + (completion_tokens / 1_000_000.0) * pricing["output"]
        if cached:
            cost = 0.0  # Zero incremental cost on cache hit

        trace = AgentStepTrace(
            job_id=job_id,
            bug_id=bug_id,
            agent_name=agent_name,
            stage=stage,
            prompt_hash=prompt_hash,
            prompt_length=prompt_len,
            tools_called=tools,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=tot_tokens,
            latency_ms=round(latency_ms, 2),
            outcome=outcome,
            cached=cached,
            model_used=model_used,
            estimated_cost_usd=round(cost, 6),
            details=details or {},
            timestamp=datetime.now(timezone.utc),
        )

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO agent_step_traces (
                    step_id, job_id, bug_id, agent_name, stage, prompt_hash,
                    prompt_length, tools_called, prompt_tokens, completion_tokens,
                    total_tokens, latency_ms, outcome, cached, model_used,
                    estimated_cost_usd, details, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.step_id,
                    trace.job_id,
                    trace.bug_id,
                    trace.agent_name,
                    trace.stage,
                    trace.prompt_hash,
                    trace.prompt_length,
                    json.dumps(trace.tools_called),
                    trace.prompt_tokens,
                    trace.completion_tokens,
                    trace.total_tokens,
                    trace.latency_ms,
                    trace.outcome.value,
                    1 if trace.cached else 0,
                    trace.model_used,
                    trace.estimated_cost_usd,
                    json.dumps(trace.details),
                    trace.timestamp.isoformat(),
                ),
            )

        return trace

    def get_traces(
        self,
        job_id: Optional[str] = None,
        bug_id: Optional[str] = None,
    ) -> List[AgentStepTrace]:
        """Queries step traces matching job_id or bug_id in chronological order."""
        query = "SELECT * FROM agent_step_traces WHERE 1=1"
        params: List[Any] = []
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        if bug_id:
            query += " AND bug_id = ?"
            params.append(bug_id)
        query += " ORDER BY timestamp ASC"

        with self._conn:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()

        traces: List[AgentStepTrace] = []
        for r in rows:
            traces.append(
                AgentStepTrace(
                    step_id=r[0],
                    job_id=r[1],
                    bug_id=r[2],
                    agent_name=r[3],
                    stage=r[4],
                    prompt_hash=r[5],
                    prompt_length=r[6],
                    tools_called=json.loads(r[7]),
                    prompt_tokens=r[8],
                    completion_tokens=r[9],
                    total_tokens=r[10],
                    latency_ms=r[11],
                    outcome=TraceOutcome(r[12]),
                    cached=bool(r[13]),
                    model_used=r[14],
                    estimated_cost_usd=r[15],
                    details=json.loads(r[16]),
                    timestamp=datetime.fromisoformat(r[17]),
                )
            )
        return traces


# Global shared tracer instance
global_tracer = StructuredTracer()
