"""Unit tests for Spectrum-Based Fault Localization (Ochiai metric)."""

import pytest
from autopatch.intelligence.models import FileASTIndex, FunctionDefinition, MethodDefinition, SourceRange
from autopatch.locator.ochiai import OchiaiFaultLocalizer


def test_ochiai_fault_localization_calculation():
    """Verify exact Ochiai formula calculation and suspiciousness ranking.

    Ochiai Formula:
        Ochiai(m) = failed(m) / sqrt(total_failed * (failed(m) + passed(m)))
    """
    file_idx = FileASTIndex(
        file_path="src/calc.py",
        language="Python",
        methods=[
            MethodDefinition(
                name="divide",
                class_name="Calculator",
                file_path="src/calc.py",
                signature="def divide(self, a, b):",
                implementation="return a / b",
                range=SourceRange(start_line=10, end_line=12),
            ),
            MethodDefinition(
                name="add",
                class_name="Calculator",
                file_path="src/calc.py",
                signature="def add(self, a, b):",
                implementation="return a + b",
                range=SourceRange(start_line=5, end_line=7),
            ),
        ],
    )

    localizer = OchiaiFaultLocalizer([file_idx])

    # 3 test cases:
    # Test 1 (FAIL): covers divide
    # Test 2 (PASS): covers divide & add
    # Test 3 (PASS): covers add
    # total_failed = 1
    # For 'divide': failed=1, passed=1 -> Ochiai = 1 / sqrt(1 * (1 + 1)) = 1 / sqrt(2) ~= 0.7071
    # For 'add': failed=0, passed=2 -> Ochiai = 0 / ... = 0.0
    test_spectra = [
        {"test_name": "test_div_zero", "passed": False, "covered_methods": ["src/calc.py:Calculator.divide"]},
        {"test_name": "test_div_normal", "passed": True, "covered_methods": ["src/calc.py:Calculator.divide", "src/calc.py:Calculator.add"]},
        {"test_name": "test_add_normal", "passed": True, "covered_methods": ["src/calc.py:Calculator.add"]},
    ]

    hints = localizer.compute_from_spectra(test_spectra, top_k=5)

    assert len(hints) == 2
    top = hints[0]
    assert top["qualified_name"] == "src/calc.py:Calculator.divide"
    assert top["method_name"] == "divide"
    assert top["class_name"] == "Calculator"
    assert top["failed_test_count"] == 1
    assert top["passed_test_count"] == 1
    assert abs(top["ochiai_score"] - 0.7071) < 0.001

    second = hints[1]
    assert second["qualified_name"] == "src/calc.py:Calculator.add"
    assert second["ochiai_score"] == 0.0


def test_ochiai_empty_when_no_failures():
    """Verify that 0 failing tests return empty hints gracefully."""
    localizer = OchiaiFaultLocalizer([])
    all_passing = [
        {"test_name": "test_1", "passed": True, "covered_methods": ["m1"]},
        {"test_name": "test_2", "passed": True, "covered_methods": ["m2"]},
    ]
    assert localizer.compute_from_spectra(all_passing) == []
    assert localizer.compute_from_spectra([]) == []
