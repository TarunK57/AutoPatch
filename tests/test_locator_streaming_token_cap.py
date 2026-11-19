"""Unit tests for evidence trail streaming and hard token budget caps."""

from pathlib import Path
import pytest
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.service import CodeIntelligenceService
from autopatch.locator.agent import LocatorAgent
from autopatch.locator.models import EvidenceRecord


def test_evidence_trail_streamable_and_persisted(tmp_path: Path):
    """Acceptance criterion: evidence trail is persisted and streamable to UI."""
    root = tmp_path / "stream_proj"
    root.mkdir()
    (root / "worker.py").write_text("def process_queue():\n    return []\n")

    service = CodeIntelligenceService()
    project_id = "test_stream"
    service.index_project(project_id, root)
    search_engine = service.get_search_engine(project_id, root)

    finding = Finding(
        file="worker.py",
        line_start=1,
        line_end=2,
        symbol="process_queue",
        category=FindingCategory.LOGIC_ERROR,
        evidence="def process_queue():",
        detector="AST_RULE",
        raw_confidence=0.9,
        description="Queue processing defect",
    )

    # Mock LLM that runs 2 strata with tool calls and then stops
    call_count = 0

    def mock_llm(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if "Select ONLY the necessary API calls" in prompt:
            return '{"calls": [{"tool": "search_method", "arguments": {"method_name": "process_queue"}, "reasoning": "Inspect implementation"}]}'
        elif "Evaluate whether the gathered code context is sufficient" in prompt:
            return '{"sufficient": true, "reasoning": "We found process_queue"}'
        else:
            # Final synthesis
            return """{
                "summary": "Queue fails to poll active jobs",
                "trigger_input_or_state": "Empty queue initial state",
                "causal_chain": ["worker.py:process_queue returns immediately"],
                "buggy_locations": [
                    {"file": "worker.py", "method_name": "process_queue", "line_start": 1, "line_end": 2, "score": 0.95, "rationale": "Premature return"}
                ],
                "confidence": 0.95
            }"""

    streamed_records = []

    def on_stream(rec: EvidenceRecord):
        streamed_records.append(rec)

    agent = LocatorAgent(search_engine=search_engine, llm_client=mock_llm, max_strata=5)
    root_cause = agent.locate(finding=finding, on_evidence_stream=on_stream)

    # 1. Verify streamable: listener received events
    assert len(streamed_records) == 1
    assert streamed_records[0].tool_name == "search_method"
    assert "process_queue" in streamed_records[0].arguments.values()

    # 2. Verify persisted in RootCause
    assert len(root_cause.evidence_trail) == 1
    assert root_cause.evidence_trail[0].tool_name == "search_method"
    assert root_cause.strata_used >= 1
    assert len(root_cause.buggy_locations) == 1
    assert root_cause.buggy_locations[0].method_name == "process_queue"


def test_hard_cap_prevents_runaway_token_spend(tmp_path: Path):
    """Acceptance criterion: a hard cap prevents runaway token use."""
    root = tmp_path / "cap_proj"
    root.mkdir()
    (root / "loop.py").write_text("def infinite(): pass\n")

    service = CodeIntelligenceService()
    project_id = "test_cap"
    service.index_project(project_id, root)
    search_engine = service.get_search_engine(project_id, root)

    finding = Finding(
        file="loop.py",
        line_start=1,
        line_end=1,
        symbol="infinite",
        category=FindingCategory.LOGIC_ERROR,
        evidence="def infinite():",
        detector="AST_RULE",
        raw_confidence=0.8,
        description="Infinite loop issue",
    )

    # Simulates an LLM that wants to keep searching forever (sufficient: false indefinitely)
    def runaway_llm(prompt: str) -> str:
        if "Select ONLY the necessary API calls" in prompt:
            return '{"calls": [{"tool": "search_method", "arguments": {"method_name": "infinite"}, "reasoning": "Need more context"}]}'
        elif "Evaluate whether the gathered code context is sufficient" in prompt:
            return '{"sufficient": false, "reasoning": "Never sufficient, need more"}'
        else:
            return '{"summary": "Capped root cause", "trigger_input_or_state": "state", "causal_chain": ["c"], "buggy_locations": [], "confidence": 0.5}'

    # Set very small token budget to trigger cap quickly
    small_budget = 300
    agent = LocatorAgent(
        search_engine=search_engine,
        llm_client=runaway_llm,
        max_strata=10,
        token_budget=small_budget,
    )

    root_cause = agent.locate(finding=finding)

    # Invariant: Must terminate before completing 10 strata due to hard cap
    assert root_cause.strata_used < 10
    assert root_cause.total_tokens_used >= small_budget
