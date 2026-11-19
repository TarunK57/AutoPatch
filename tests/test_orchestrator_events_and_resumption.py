"""Unit tests verifying event-sourced state reconstruction, worker crash/interruption resumption, and token telemetry."""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from autopatch.core.exceptions import CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.orchestrator.events import AuditEvent, EventStore, EventType
from autopatch.orchestrator.pipeline import BugPipelineOrchestrator
from autopatch.orchestrator.tokens import TokenUsageTracker


def test_audit_log_reconstructs_full_state_of_any_bug():
    """Acceptance criterion: The append-only audit log can reconstruct the full state of any bug."""
    event_store = EventStore()
    job_id = "job-eval-1"
    bug_id = f"{job_id}:src/core.py:42"

    # 1. Pipeline started
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.BUG_PIPELINE_STARTED,
            actor="ORCHESTRATOR",
            payload={"finding": {"file": "src/core.py", "line_start": 42, "category": "security"}},
        )
    )

    # 2. Locator completed
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.LOCATOR_COMPLETED,
            actor="LOCATOR",
            payload={"root_cause": {"summary": "SQL Injection vulnerability in user lookup"}},
        )
    )

    # 3. Reproducer completed
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.REPRODUCER_COMPLETED,
            actor="REPRODUCER",
            payload={"reproduction": {"is_confirmed": True, "test_file": "tests/test_brt_42.py"}},
        )
    )

    # 4. Patcher completed
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.PATCHER_COMPLETED,
            actor="PATCHER",
            payload={
                "candidate_patches": [
                    {
                        "id": "patch-100",
                        "file": "src/core.py",
                        "original_snippet": "query = f'SELECT * FROM users WHERE id = {uid}'",
                        "patched_snippet": "query = 'SELECT * FROM users WHERE id = ?', (uid,)",
                    }
                ]
            },
        )
    )

    # 5. Verifier completed
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.VERIFIER_COMPLETED,
            actor="VERIFIER",
            payload={"verification": {"status": "VERIFIED", "ensemble_pass_rate": 100.0}},
        )
    )

    # 6. Scoring completed
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.SCORING_COMPLETED,
            actor="SCORING",
            payload={"priority": {"priority_score": 92.5, "rank": 1}},
        )
    )

    # 7. Human Decision recorded
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.DECISION_RECORDED,
            actor="reviewer_admin",
            payload={"decision": {"status": "APPROVED", "reviewer": "reviewer_admin"}},
        )
    )

    # 8. Patch applied
    event_store.append(
        AuditEvent(
            job_id=job_id,
            bug_id=bug_id,
            event_type=EventType.PATCH_APPLIED,
            actor="SYSTEM",
            payload={"patch_id": "patch-100", "file": "src/core.py"},
        )
    )

    # REPLAY: Reconstruct full state purely from the audit events
    state = event_store.reconstruct_bug_state(bug_id)

    assert state["exists"] is True
    assert state["bug_id"] == bug_id
    assert state["status"] == "APPLIED"
    assert state["is_patch_applied"] is True
    assert state["root_cause"]["summary"] == "SQL Injection vulnerability in user lookup"
    assert state["reproduction"]["is_confirmed"] is True
    assert len(state["patches"]) == 1
    assert state["verification"]["status"] == "VERIFIED"
    assert state["priority"]["priority_score"] == 92.5
    assert state["decision"]["status"] == "APPROVED"
    assert state["event_count"] == 8
    assert "LOCATOR" in state["completed_stages"]
    assert "REPRODUCER" in state["completed_stages"]
    assert "VERIFIER" in state["completed_stages"]


@pytest.mark.anyio
async def test_killing_worker_mid_job_and_restarting_resumes_cleanly():
    """Acceptance criterion: Killing a worker mid-job and restarting resumes cleanly."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        (proj / "src").mkdir()
        (proj / "src" / "app.py").write_text("def work(): return 1\n")

        event_store = EventStore()
        token_tracker = TokenUsageTracker()
        orchestrator = BugPipelineOrchestrator(
            event_store=event_store,
            token_tracker=token_tracker,
            concurrency_limit=2,
        )

        job_id = "job-kill-resume-test"
        finding = Finding(
            file="src/app.py",
            line_start=1,
            line_end=1,
            category=FindingCategory.LOGIC_ERROR,
            evidence="def work(): return 1",
            detector="TEST_DETECTOR",
            raw_confidence=0.85,
            description="Simulated logic flaw",
        )

        # Phase 1: Simulate worker processing Locator stage, then being killed/interrupted
        bug_id = f"{job_id}:src/app.py:1"
        event_store.append(
            AuditEvent(
                job_id=job_id,
                bug_id=bug_id,
                event_type=EventType.BUG_PIPELINE_STARTED,
                payload={"finding": finding.model_dump()},
            )
        )
        event_store.append(
            AuditEvent(
                job_id=job_id,
                bug_id=bug_id,
                event_type=EventType.LOCATOR_COMPLETED,
                payload={"root_cause": {"summary": "Persisted checkpointed root cause"}},
            )
        )

        # State before restart: Locator completed, but Reproducer, Patcher, Verifier not yet done
        initial_state = event_store.reconstruct_bug_state(bug_id)
        assert "LOCATOR" in initial_state["completed_stages"]
        assert "REPRODUCER" not in initial_state["completed_stages"]

        # Phase 2: Worker restarts with resume=True
        # It must cleanly resume from the checkpoint, skipping Locator and completing remaining stages
        cancel_token = CancellationToken()
        resumed_state = await orchestrator.execute_single_bug(
            job_id=job_id,
            project_root=proj,
            finding=finding,
            cancel_token=cancel_token,
            resume=True,
        )

        assert resumed_state["status"] == "COMPLETED"
        assert resumed_state["root_cause"]["summary"] == "Persisted checkpointed root cause"
        assert "REPRODUCER" in resumed_state["completed_stages"]
        assert "PATCHER" in resumed_state["completed_stages"]
        assert "VERIFIER" in resumed_state["completed_stages"]
        assert "SCORING" in resumed_state["completed_stages"]


@pytest.mark.anyio
async def test_token_tracking_and_cost_aggregation():
    """Validates cumulative token and dollar cost tracking per job."""
    tracker = TokenUsageTracker()
    job_id = "job-telemetry-1"

    # Step 1: Locator calls model
    tracker.record(job_id, prompt_tokens=1000, completion_tokens=200, model="claude-3-5-sonnet")
    # Step 2: Reproducer calls model
    tracker.record(job_id, prompt_tokens=2500, completion_tokens=500, model="claude-3-5-sonnet")

    metrics = tracker.get_metrics(job_id)
    assert metrics.prompt_tokens == 3500
    assert metrics.completion_tokens == 700
    assert metrics.total_tokens == 4200
    assert metrics.llm_calls_count == 2
    # Estimated cost: 3500 * (3.0/1M) + 700 * (15.0/1M) = 0.0105 + 0.0105 = 0.021 USD
    assert metrics.estimated_cost_usd > 0.0
    assert round(metrics.estimated_cost_usd, 3) == 0.021
