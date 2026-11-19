"""Unit tests for Reproducer Agent safety invariants and action constraints."""

from pathlib import Path
import pytest
from autopatch.core.exceptions import InvariantViolationError, TestModificationForbiddenError
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.service import CodeIntelligenceService
from autopatch.reproducer.agent import ReproducerAgent


@pytest.fixture
def agent_workspace(tmp_path: Path):
    root = tmp_path / "repro_invariants"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src/calculator.py").write_text("def divide(a, b): return a / b\n")
    (root / "tests").mkdir()
    (root / "tests/test_calculator.py").write_text("def test_div(): assert True\n")

    service = CodeIntelligenceService()
    project_id = "test_repro_inv"
    service.index_project(project_id, root)
    engine = service.get_search_engine(project_id, root)

    finding = Finding(
        file="src/calculator.py",
        line_start=1,
        line_end=1,
        symbol="divide",
        category=FindingCategory.LOGIC_ERROR,
        evidence="return a / b",
        detector="AST_RULE",
        raw_confidence=0.9,
        description="ZeroDivisionError on b=0",
    )

    return root, engine, finding


def test_edit_never_modifies_existing_files(agent_workspace):
    """Acceptance criterion: tests never modify existing files."""
    root, engine, finding = agent_workspace

    agent = ReproducerAgent(
        project_root=root,
        search_engine=engine,
        llm_client=lambda p: "dummy",
    )

    # 1. Attempting to edit an existing test file must be rejected
    with pytest.raises(InvariantViolationError) as exc_info:
        agent._action_edit(
            path="tests/test_calculator.py",
            change_desc="Rewrite existing tests",
            finding=finding,
            root_cause=None,
        )
    assert "was an existing file in the project" in str(exc_info.value)

    # 2. Attempting to edit existing application code must be rejected
    with pytest.raises(TestModificationForbiddenError):
        agent._action_edit(
            path="src/calculator.py",
            change_desc="Fix bug directly",
            finding=finding,
            root_cause=None,
        )


def test_finish_rejected_until_run_tests_executed(agent_workspace):
    """Acceptance criterion: finish is rejected until run_tests has executed at least once."""
    root, engine, finding = agent_workspace

    # Mock LLM that immediately attempts to finish without running tests
    step_calls = 0

    def eager_finish_llm(prompt: str) -> str:
        nonlocal step_calls
        step_calls += 1
        if step_calls == 1:
            return '{"action": "finish", "parameters": {}}'
        elif step_calls == 2:
            return '{"action": "edit", "parameters": {"path": "tests/repro_bug.py", "change_description": "Add repro test"}}'
        elif step_calls == 3:
            # Separate LLM call for edit code generation
            return "```python\ndef test_zero_div():\n    pass\n```"
        elif step_calls == 4:
            return '{"action": "run_tests", "parameters": {"path": "tests/repro_bug.py"}}'
        else:
            return '{"action": "finish", "parameters": {}}'

    agent = ReproducerAgent(
        project_root=root,
        search_engine=engine,
        llm_client=eager_finish_llm,
    )

    result = agent.run_reproduction_cycle(finding=finding)

    # First step attempting finish should have been rejected
    first_step = result.steps[0]
    assert first_step.action == "finish"
    assert "REJECTED" in first_step.output
    assert "must run the tests with run_tests" in first_step.output

    # Eventual finish succeeded after run_tests
    assert any(s.action == "run_tests" for s in result.steps)
