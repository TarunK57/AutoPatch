"""Unit test verifying that LLM findings without verbatim code evidence are dropped."""

from pathlib import Path
import pytest
from autopatch.detection.llm_reviewer import LLMSemanticReviewer
from autopatch.intelligence.models import FileASTIndex, FunctionDefinition, SourceRange


def test_llm_hallucination_without_code_evidence_dropped(tmp_path: Path):
    """Acceptance criterion: LLM findings with no matching code evidence are dropped."""
    project_root = tmp_path / "llm_eval_proj"
    project_root.mkdir()

    source_code = """def compute_discount(price: float) -> float:
    # Actual code in file
    return price * 0.15
"""
    (project_root / "pricing.py").write_text(source_code)

    file_index = FileASTIndex(
        file_path="pricing.py",
        language="Python",
        functions=[
            FunctionDefinition(
                name="compute_discount",
                file_path="pricing.py",
                signature="def compute_discount(price: float) -> float:",
                implementation=source_code,
                range=SourceRange(start_line=1, end_line=3),
            )
        ],
    )

    # Mock LLM returning 1 authentic finding and 1 hallucinated finding
    def mock_llm_response(prompt: str) -> str:
        return """[
            {
                "file": "pricing.py",
                "line_start": 3,
                "line_end": 3,
                "symbol": "compute_discount",
                "category": "LOGIC_ERROR",
                "cwe": null,
                "evidence": "return price * 0.15",
                "description": "Hardcoded discount rate may not match dynamic store policies.",
                "raw_confidence": 0.85
            },
            {
                "file": "pricing.py",
                "line_start": 99,
                "line_end": 100,
                "symbol": "phantom_func",
                "category": "SECURITY",
                "cwe": "CWE-89",
                "evidence": "cursor.execute('DROP TABLE users WHERE ' + hallucinated_var)",
                "description": "Critical SQL injection in non-existent database call.",
                "raw_confidence": 0.99
            }
        ]"""

    reviewer = LLMSemanticReviewer(llm_client=mock_llm_response)
    findings = reviewer.detect(project_root, [file_index])

    # Invariant check: only 1 finding must survive
    assert len(findings) == 1

    surviving = findings[0]
    assert surviving.evidence == "return price * 0.15"
    assert surviving.symbol == "compute_discount"

    # Verify hallucinated finding was dropped completely
    assert not any("DROP TABLE" in f.evidence for f in findings)
    assert not any("phantom_func" == f.symbol for f in findings)
