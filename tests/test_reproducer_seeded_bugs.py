"""Evaluation of Reproducer Agent on seeded bugs reporting candidate and plausible rates."""

from pathlib import Path
import pytest
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.service import CodeIntelligenceService
from autopatch.locator.models import RootCause
from autopatch.reproducer.agent import ReproducerAgent
from autopatch.reproducer.judge import BRTJudge


@pytest.fixture
def seeded_bug_workspace(tmp_path: Path):
    root = tmp_path / "seeded_repro_workspace"
    root.mkdir()
    (root / "src").mkdir()
    (root / "tests").mkdir()

    # Seeded Bug: ZeroDivisionError in calculate_discount on total_items == 0
    (root / "src/discount.py").write_text("""def calculate_discount(price: float, total_items: int) -> float:
    # Bug: when total_items == 0, raises ZeroDivisionError
    rate = 10.0 / total_items
    return price * (1.0 - rate / 100.0)
""")

    service = CodeIntelligenceService()
    project_id = "test_repro_seeded"
    service.index_project(project_id, root)
    engine = service.get_search_engine(project_id, root)

    finding = Finding(
        file="src/discount.py",
        line_start=3,
        line_end=4,
        symbol="calculate_discount",
        category=FindingCategory.LOGIC_ERROR,
        evidence="rate = 10.0 / total_items",
        detector="AST_RULE",
        raw_confidence=0.92,
        description="ZeroDivisionError when total_items is zero.",
        metadata={"bug_id": "BUG-DIV-ZERO-01"},
    )

    root_cause = RootCause(
        summary="calculate_discount performs division by total_items without checking if total_items > 0",
        trigger_input_or_state="total_items=0",
        causal_chain=["calculate_discount(100.0, 0) called", "rate = 10.0 / 0 triggers ZeroDivisionError"],
        confidence=0.95,
        strata_used=2,
        total_tokens_used=400,
    )

    # Reference fix diff (for Plausible BRT check)
    reference_fix = """--- a/src/discount.py\n+++ b/src/discount.py\n@@ -3,1 +3,1 @@\n- rate = 10.0 / total_items\n+ rate = 10.0 / total_items if total_items > 0 else 0.0"""

    return root, engine, finding, root_cause, reference_fix


def test_reproducer_reports_candidate_and_plausible_rates(seeded_bug_workspace):
    """Acceptance criteria:
    - Report candidate and plausible rates across sampled runs
    - Agent step trace is stored
    - Tests never modify existing files
    - LLM judge confirms failure is caused by bug
    - Boundary tests generated (normal, min, max, invalid)
    """
    root, engine, finding, root_cause, reference_fix = seeded_bug_workspace

    # Track actions taken
    def intelligent_reproducer_llm(prompt: str) -> str:
        # Code generation call for edit
        if "Write a bug reproduction test for the following bug" in prompt:
            # Generates boundary tests: normal, minimum, maximum, invalid (boundary test requirement)
            return """```python
import pytest
from src.discount import calculate_discount

def test_discount_normal():
    # Normal case: valid quantity
    assert calculate_discount(100.0, 5) is not None

def test_discount_boundary_min():
    # Minimum valid boundary
    assert calculate_discount(100.0, 1) is not None

def test_discount_boundary_max():
    # Maximum high volume
    assert calculate_discount(100.0, 10000) is not None

def test_discount_invalid_zero():
    # Invalid boundary: trigger bug (ZeroDivisionError)
    # On buggy code this will raise ZeroDivisionError and fail the test!
    result = calculate_discount(100.0, 0)
    assert result == 100.0
```"""

        # Judge evaluation
        elif "Determine if the test failure trace below is GENUINELY CAUSED BY" in prompt:
            return '{"confirmed": true, "reasoning": "ZeroDivisionError in calculate_discount directly matches the reported bug."}'

        # Agent step loop decisions
        elif "You are the AutoPatch Reproducer Agent" in prompt:
            prev_steps_section = prompt.split("PREVIOUS STEPS")[-1] if "PREVIOUS STEPS" in prompt else ""
            if "edit(" not in prev_steps_section:
                # Step 1: Create test file
                return '{"action": "edit", "parameters": {"path": "tests/repro_discount_bug.py", "change_description": "Create reproduction test with boundary conditions (normal, min, max, zero)"}}'
            elif "run_tests(" not in prev_steps_section:
                # Step 2: Run tests
                return '{"action": "run_tests", "parameters": {"path": "tests/repro_discount_bug.py"}}'
            else:
                # Step 3: Finish after running tests
                return '{"action": "finish", "parameters": {}}'

        return '{"action": "finish", "parameters": {}}'

    judge = BRTJudge(llm_client=intelligent_reproducer_llm)
    agent = ReproducerAgent(
        project_root=root,
        search_engine=engine,
        llm_client=intelligent_reproducer_llm,
        judge=judge,
        max_steps=10,
    )

    # Sample 3 runs at low temperature
    result = agent.run_reproduction_cycle(
        finding=finding,
        root_cause=root_cause,
        reference_fix_patch=reference_fix,
        samples=3,
    )

    # 1. Step trace is stored
    print("\nRESULT STEPS:", [(s.step_number, s.action, s.output[:40]) for s in result.steps])
    assert len(result.steps) >= 3
    assert result.steps[0].action == "edit"
    assert any(s.action == "run_tests" for s in result.steps)
    assert any(s.action == "finish" for s in result.steps)

    # 2. Existing files were never modified
    original_code = (root / "src/discount.py").read_text()
    assert "rate = 10.0 / total_items" in original_code  # Unmodified baseline

    # 3. Candidate & Plausible rates reported
    print(f"\n[BRT EVALUATION] Candidate Rate: {result.candidate_rate * 100:.1f}%")
    print(f"[BRT EVALUATION] Plausible Rate: {result.plausible_rate * 100:.1f}%")
    print(f"[BRT EVALUATION] Unique Failure Traces: {len(result.unique_failure_traces)}")

    assert result.candidate_rate > 0.0
    assert result.plausible_rate > 0.0
    assert result.runs_sampled == 3

    # 4. LLM judge verdict confirms failure
    assert result.classification.is_candidate is True
    assert result.classification.llm_judge_verdict is True
    assert "ZeroDivisionError" in result.classification.llm_judge_reasoning

    # 5. Boundary tests verified in generated code
    test_content = (root / "tests/repro_discount_bug.py").read_text()
    assert "test_discount_normal" in test_content
    assert "test_discount_boundary_min" in test_content
    assert "test_discount_boundary_max" in test_content
    assert "test_discount_invalid_zero" in test_content
