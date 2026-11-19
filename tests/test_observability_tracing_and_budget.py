"""Unit tests verifying structured tracing, token budgets, graceful degradation, LLM caching, replay, and project cost dashboard.

Acceptance criteria:
1. A job exceeding budget stops cleanly and reports partial results.
2. Replaying a trace reproduces the same decisions with cached responses.
"""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from autopatch.api.main import app
from autopatch.api.routes import JOBS_DB, PROJECTS_DB
from autopatch.detection.models import Finding, FindingCategory
from autopatch.observability.budget import TokenBudgetManager
from autopatch.observability.cache import LLMCache, compute_cache_key
from autopatch.observability.dashboard import CostDashboardService
from autopatch.observability.models import TraceOutcome
from autopatch.observability.replay import ReplayEngine
from autopatch.observability.tracing import StructuredTracer, compute_prompt_hash
from autopatch.orchestrator.events import EventStore, EventType
from autopatch.orchestrator.pipeline import BugPipelineOrchestrator
from autopatch.orchestrator.tokens import TokenUsageTracker

client = TestClient(app)


def test_structured_tracing_records_all_fields_for_every_step():
    """Verifies that StructuredTracer records prompt hash, tools called, tokens, latency, and outcome."""
    tracer = StructuredTracer(db_path=":memory:")
    job_id = f"job-{uuid4()}"
    bug_id = f"{job_id}:src/auth.py:45"
    prompt = "Locate SQL injection flaw in login method"

    trace = tracer.record_step(
        job_id=job_id,
        bug_id=bug_id,
        agent_name="Locator",
        stage="ROOT_CAUSE_LOCALIZATION",
        prompt=prompt,
        tools_called=[{"tool": "code_search", "query": "auth"}],
        prompt_tokens=350,
        completion_tokens=150,
        latency_ms=14.2,
        outcome=TraceOutcome.SUCCESS,
        cached=False,
        model_used="claude-3-5-sonnet",
        details={"evidence": "raw sql string concatenation"},
    )

    assert trace.job_id == job_id
    assert trace.bug_id == bug_id
    assert trace.prompt_hash == compute_prompt_hash(prompt)
    assert trace.prompt_length == len(prompt)
    assert len(trace.tools_called) == 1
    assert trace.tools_called[0]["tool"] == "code_search"
    assert trace.prompt_tokens == 350
    assert trace.completion_tokens == 150
    assert trace.total_tokens == 500
    assert trace.latency_ms == 14.2
    assert trace.outcome == TraceOutcome.SUCCESS
    assert trace.model_used == "claude-3-5-sonnet"
    assert trace.estimated_cost_usd > 0.0

    # Query back by job_id and bug_id
    traces = tracer.get_traces(job_id=job_id)
    assert len(traces) == 1
    assert traces[0].step_id == trace.step_id

    bug_traces = tracer.get_traces(bug_id=bug_id)
    assert len(bug_traces) == 1
    assert bug_traces[0].agent_name == "Locator"


def test_llm_cache_returns_cached_response_and_computes_stats():
    """Verifies caching of LLM calls by input hash and zero incremental cost on cache hits."""
    cache = LLMCache()
    model = "claude-3-5-sonnet"
    prompt = "Synthesize minimal patch for off-by-one error"
    response = "def is_valid(i, n): return i < n"

    # 1. First lookup: Miss
    cached = cache.get(model=model, prompt=prompt)
    assert cached is None

    # 2. Put into cache
    entry = cache.put(
        model=model,
        prompt=prompt,
        response_text=response,
        prompt_tokens=400,
        completion_tokens=80,
    )
    assert entry.cache_key == compute_cache_key(model, prompt)
    assert entry.response_text == response
    assert entry.cost_saved_usd > 0.0

    # 3. Second lookup: Hit
    cached_hit = cache.get(model=model, prompt=prompt)
    assert cached_hit is not None
    assert cached_hit.response_text == response
    assert cached_hit.hit_count == 2

    # Verify telemetry stats
    stats = cache.get_stats()
    assert stats["total_requests"] == 2
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate_pct"] == 50.0
    assert stats["tokens_saved"] == 480
    assert stats["cost_saved_usd"] > 0.0


@pytest.mark.anyio
async def test_job_exceeding_budget_stops_cleanly_and_reports_partial_results():
    """Acceptance criterion: A job exceeding budget stops cleanly and reports partial results."""
    with tempfile.TemporaryDirectory() as td:
        proj_dir = Path(td)
        (proj_dir / "src").mkdir()
        (proj_dir / "src" / "math.py").write_text("def calc(a, b): return a / b\n")

        tracer = StructuredTracer(db_path=":memory:")
        cache = LLMCache()
        event_store = EventStore()
        token_tracker = TokenUsageTracker()
        budget_manager = TokenBudgetManager(
            default_job_budget=1_500,  # Hard ceiling: 1,500 tokens
            default_bug_budget=10_000,
        )

        orchestrator = BugPipelineOrchestrator(
            event_store=event_store,
            token_tracker=token_tracker,
            concurrency_limit=1,
            budget_manager=budget_manager,
            tracer=tracer,
            cache=cache,
        )

        job_id = f"job-budget-test-{uuid4()}"
        findings = [
            Finding(
                file="src/math.py",
                line_start=1,
                line_end=1,
                category=FindingCategory.LOGIC_ERROR,
                evidence="def calc(a, b): return a / b",
                detector="TEST",
                raw_confidence=0.9,
                description="Zero division risk 1",
            ),
            Finding(
                file="src/math.py",
                line_start=2,
                line_end=2,
                category=FindingCategory.LOGIC_ERROR,
                evidence="def calc(a, b): return a / b",
                detector="TEST",
                raw_confidence=0.9,
                description="Zero division risk 2",
            ),
            Finding(
                file="src/math.py",
                line_start=3,
                line_end=3,
                category=FindingCategory.LOGIC_ERROR,
                evidence="def calc(a, b): return a / b",
                detector="TEST",
                raw_confidence=0.9,
                description="Zero division risk 3",
            ),
        ]

        # Execute scan job
        results = await orchestrator.execute_job(
            job_id=job_id,
            project_root=proj_dir,
            findings=findings,
        )

        # 1. Job completes cleanly without exception
        assert len(results) == 3

        # 2. First bug processed successfully (spent ~2,000+ tokens, exceeding 1,500 budget cap)
        assert results[0].get("status") == "COMPLETED"

        # 3. Subsequent bugs were skipped cleanly due to job budget ceiling
        assert results[1].get("status") == "SKIPPED_BUDGET_EXCEEDED"
        assert results[2].get("status") == "SKIPPED_BUDGET_EXCEEDED"

        # 4. Partial results recorded in audit log
        job_events = event_store.get_events(job_id=job_id)
        completion_events = [e for e in job_events if e.event_type == EventType.JOB_COMPLETED]
        assert len(completion_events) == 1
        assert completion_events[0].payload.get("is_partial") is True
        assert completion_events[0].payload.get("status") == "COMPLETED_PARTIAL"

        # 5. Budget exceeded traces recorded
        traces = tracer.get_traces(job_id=job_id)
        budget_traces = [t for t in traces if t.outcome == TraceOutcome.BUDGET_EXCEEDED]
        assert len(budget_traces) >= 1


@pytest.mark.anyio
async def test_per_bug_budget_exceeded_triggers_graceful_degradation():
    """Verifies that exceeding per-bug budget falls back gracefully to template fixes and cheaper model."""
    with tempfile.TemporaryDirectory() as td:
        proj_dir = Path(td)
        (proj_dir / "src").mkdir()
        # Seed an off-by-one loop that DeterministicTemplatePatcher can resolve
        code = (
            "def iterate_items(items):\n"
            "    for i in range(len(items) + 1):\n"
            "        print(items[i])\n"
        )
        (proj_dir / "src" / "loop.py").write_text(code)

        tracer = StructuredTracer(db_path=":memory:")
        cache = LLMCache()
        event_store = EventStore()
        token_tracker = TokenUsageTracker()

        # Set a low per-bug token budget (500 tokens) so locator pushes it into degradation
        budget_manager = TokenBudgetManager(
            default_job_budget=50_000,
            default_bug_budget=500,
            fallback_model="claude-3-haiku",
        )

        orchestrator = BugPipelineOrchestrator(
            event_store=event_store,
            token_tracker=token_tracker,
            budget_manager=budget_manager,
            tracer=tracer,
            cache=cache,
        )

        job_id = f"job-degrade-test-{uuid4()}"
        finding = Finding(
            file="src/loop.py",
            line_start=2,
            line_end=2,
            category=FindingCategory.LOGIC_ERROR,
            evidence="for i in range(len(items) + 1):",
            detector="TEST",
            raw_confidence=0.88,
            description="Off-by-one bound in loop",
        )

        res = await orchestrator.execute_single_bug(
            job_id=job_id,
            project_root=proj_dir,
            finding=finding,
            cancel_token=None,
        )

        bug_id = f"{job_id}:src/loop.py:2"
        # 1. Bug must be marked as degraded
        assert budget_manager.is_bug_degraded(bug_id) is True

        # 2. Subsequent model selection returns fallback cheaper model
        assert budget_manager.get_model_for_bug(bug_id) == "claude-3-haiku"

        # 3. Patcher used deterministic template fix
        patches = res.get("patches", [])
        assert len(patches) >= 1
        assert patches[0].get("is_template") is True
        assert "Deterministic Template" in patches[0].get("rationale", "")

        # 4. Traces contain DEGRADED outcome steps
        traces = tracer.get_traces(bug_id=bug_id)
        degraded_traces = [t for t in traces if t.outcome == TraceOutcome.DEGRADED]
        assert len(degraded_traces) >= 1
        assert any(t.model_used == "claude-3-haiku" for t in degraded_traces)


@pytest.mark.anyio
async def test_replay_tool_reproduces_same_decisions_with_cached_responses():
    """Acceptance criterion: Replaying a trace reproduces the same decisions with cached responses."""
    with tempfile.TemporaryDirectory() as td:
        proj_dir = Path(td)
        (proj_dir / "src").mkdir()
        (proj_dir / "src" / "sample.py").write_text("def run(): pass\n")

        tracer = StructuredTracer(db_path=":memory:")
        cache = LLMCache()
        budget_manager = TokenBudgetManager()
        orchestrator = BugPipelineOrchestrator(
            tracer=tracer,
            cache=cache,
            budget_manager=budget_manager,
        )

        job_id = f"job-replay-eval-{uuid4()}"
        finding = Finding(
            file="src/sample.py",
            line_start=1,
            line_end=1,
            category=FindingCategory.INPUT_VALIDATION,
            evidence="def run(): pass",
            detector="TEST",
            raw_confidence=0.95,
            description="Missing input parameter validation",
        )

        # 1. Run pipeline first time (populates traces and cache)
        initial_result = await orchestrator.execute_single_bug(
            job_id=job_id,
            project_root=proj_dir,
            finding=finding,
            cancel_token=None,
        )
        assert initial_result.get("status") == "COMPLETED"

        recorded_traces = tracer.get_traces(job_id=job_id)
        assert len(recorded_traces) >= 4  # Locator, Reproducer, Patcher, Verifier, Scoring

        # 2. Deterministic Replay using ReplayEngine
        replay_engine = ReplayEngine(tracer=tracer, cache=cache)
        replay_result = replay_engine.replay_trace(target_id=job_id, target_type="job")

        # 3. Verify exact match invariants
        assert replay_result.is_exact_match is True
        assert replay_result.discrepancies == []
        assert replay_result.total_steps_replayed == len(recorded_traces)
        assert replay_result.reproduced_decisions == len(recorded_traces)
        assert replay_result.cache_hits > 0
        assert "Successfully replayed" in replay_result.summary


def test_cost_dashboard_service_aggregates_project_costs_and_cache_savings():
    """Verifies that CostDashboardService computes accurate token spend, USD costs, and cache ROI."""
    tracer = StructuredTracer(db_path=":memory:")
    cache = LLMCache()
    dashboard = CostDashboardService(tracer=tracer, cache=cache)

    project_id = f"proj-cost-{uuid4()}"
    job_id = f"job-{uuid4()}"

    # Record Locator step (Sonnet)
    tracer.record_step(
        job_id=job_id,
        bug_id=f"{job_id}:app.py:10",
        agent_name="Locator",
        stage="LOCALIZATION",
        prompt="Find defect",
        prompt_tokens=1000,
        completion_tokens=200,
        model_used="claude-3-5-sonnet",
        cached=False,
    )

    # Record Patcher step in degraded mode (Haiku)
    tracer.record_step(
        job_id=job_id,
        bug_id=f"{job_id}:app.py:10",
        agent_name="Patcher",
        stage="PATCH",
        prompt="Fix defect",
        prompt_tokens=500,
        completion_tokens=100,
        model_used="claude-3-haiku",
        cached=False,
    )

    # Record Verifier step on cache hit
    tracer.record_step(
        job_id=job_id,
        bug_id=f"{job_id}:app.py:10",
        agent_name="Verifier",
        stage="VERIFY",
        prompt="Verify fix",
        prompt_tokens=0,
        completion_tokens=0,
        model_used="claude-3-5-sonnet",
        cached=True,
    )

    summary = dashboard.get_project_cost_summary(
        project_id=project_id,
        job_ids=[job_id],
    )

    assert summary.project_id == project_id
    assert summary.total_jobs == 1
    assert summary.total_prompt_tokens == 1500
    assert summary.total_completion_tokens == 300
    assert summary.total_tokens == 1800
    assert summary.total_llm_calls == 3
    assert summary.total_cache_hits == 1
    assert summary.total_cost_usd > 0.0

    # Agent breakdown
    assert "Locator" in summary.agent_costs
    assert "Patcher" in summary.agent_costs

    # Model breakdown
    assert "claude-3-5-sonnet" in summary.model_costs
    assert "claude-3-haiku" in summary.model_costs

    # Top expensive bugs
    assert len(summary.top_expensive_bugs) == 1
    assert summary.top_expensive_bugs[0]["bug_id"] == f"{job_id}:app.py:10"


def test_api_endpoints_cost_dashboard_and_replay():
    """Verifies REST API endpoints for project costs and trace replay with ownership checks."""
    headers = {"Authorization": "Bearer dev_token_user_alice"}
    headers_forbidden = {"Authorization": "Bearer dev_token_user_bob"}

    # Setup project and job in memory
    project_id = f"proj-{uuid4()}"
    job_id = f"job-{uuid4()}"

    PROJECTS_DB[project_id] = {
        "project_id": project_id,
        "name": "Cost Project",
        "owner_id": "user_alice",
        "project_dir": "/tmp/test",
        "languages": ["python"],
        "total_files": 5,
    }

    JOBS_DB[job_id] = {
        "job_id": job_id,
        "project_id": project_id,
        "owner_id": "user_alice",
        "status": "COMPLETED",
        "progress": 100.0,
    }

    # 1. Project costs endpoint
    resp = client.get(f"/api/v1/projects/{project_id}/costs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert "total_tokens" in data
    assert "total_cost_usd" in data
    assert "cache_hit_rate" in data

    # Cross-user forbidden check on costs
    resp_forbidden = client.get(f"/api/v1/projects/{project_id}/costs", headers=headers_forbidden)
    assert resp_forbidden.status_code == 403

    # 2. Replay endpoint
    resp_replay = client.post(f"/api/v1/jobs/{job_id}/replay", headers=headers)
    assert resp_replay.status_code == 200
    replay_data = resp_replay.json()
    assert replay_data["target_id"] == job_id
    assert "is_exact_match" in replay_data

    # Cross-user forbidden check on replay
    resp_replay_forbidden = client.post(f"/api/v1/jobs/{job_id}/replay", headers=headers_forbidden)
    assert resp_replay_forbidden.status_code == 403
