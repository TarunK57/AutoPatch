"""Method-level Spectrum-Based Fault Localization (SBFL) using the Ochiai metric.

Ochiai Formula:
    Ochiai(m) = failed(m) / sqrt(total_failed * (failed(m) + passed(m)))

Computes suspiciousness rankings across methods based on test coverage spectra.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from autopatch.intelligence.models import FileASTIndex


class OchiaiMethodHint(Dict[str, Any]):
    """Top suspicious method hint produced by SBFL."""
    pass


class OchiaiFaultLocalizer:
    """Computes method-level fault localization scores from test execution spectra."""

    def __init__(self, file_indices: Optional[List[FileASTIndex]] = None):
        self.file_indices = file_indices or []
        self._known_methods: Set[str] = set()
        self._method_details: Dict[str, Dict[str, Any]] = {}
        self._populate_known_methods()

    def _populate_known_methods(self) -> None:
        for idx in self.file_indices:
            for fn in idx.functions:
                qual_name = f"{idx.file_path}:{fn.name}"
                self._known_methods.add(qual_name)
                self._method_details[qual_name] = {
                    "file": idx.file_path,
                    "method": fn.name,
                    "class": None,
                    "line_start": fn.range.start_line,
                    "line_end": fn.range.end_line,
                }
            for m in idx.methods:
                qual_name = f"{idx.file_path}:{m.class_name}.{m.name}"
                self._known_methods.add(qual_name)
                self._method_details[qual_name] = {
                    "file": idx.file_path,
                    "method": m.name,
                    "class": m.class_name,
                    "line_start": m.range.start_line,
                    "line_end": m.range.end_line,
                }

    def compute_from_spectra(
        self,
        test_spectra: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Calculates Ochiai scores given a list of test spectra records.

        Each test spectrum record:
        {
            "test_name": str,
            "passed": bool,
            "covered_methods": List[str]  # e.g. ["src/calc.py:Calculator.divide"]
        }
        """
        if not test_spectra:
            return []

        failing_tests = [t for t in test_spectra if not t.get("passed", True)]
        total_failed = len(failing_tests)

        if total_failed == 0:
            return []

        # Count method coverage
        failed_counts: Dict[str, int] = {}
        passed_counts: Dict[str, int] = {}

        for test in test_spectra:
            passed = test.get("passed", True)
            covered = set(test.get("covered_methods", []))

            for m in covered:
                if passed:
                    passed_counts[m] = passed_counts.get(m, 0) + 1
                else:
                    failed_counts[m] = failed_counts.get(m, 0) + 1

        # Calculate Ochiai score for each covered method
        all_methods = set(failed_counts.keys()).union(set(passed_counts.keys()))
        scores: List[Dict[str, Any]] = []

        for m in all_methods:
            nf = failed_counts.get(m, 0)
            np = passed_counts.get(m, 0)

            if nf == 0:
                score = 0.0
            else:
                denom = math.sqrt(total_failed * (nf + np))
                score = round(nf / denom, 4) if denom > 0 else 0.0

            details = self._method_details.get(m, {})
            scores.append(
                {
                    "qualified_name": m,
                    "file": details.get("file", m.split(":")[0] if ":" in m else "unknown"),
                    "method_name": details.get("method", m.split(":")[-1].split(".")[-1]),
                    "class_name": details.get("class"),
                    "line_start": details.get("line_start", 1),
                    "line_end": details.get("line_end", 1),
                    "ochiai_score": score,
                    "failed_test_count": nf,
                    "passed_test_count": np,
                }
            )

        # Sort descending by Ochiai score, break ties by failed_test_count
        scores.sort(key=lambda x: (x["ochiai_score"], x["failed_test_count"]), reverse=True)
        return scores[:top_k]
