"""Input validation detector for bounded numeric parameters.

Detects parameters with domain-specific numeric semantics (marks, score, age, price,
quantity, percent) that are consumed in calculations without range or NaN bounds checks.
"""

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.models import FileASTIndex


class DomainRange(NamedTuple):
    range_str: str
    min_val: Optional[float]
    max_val: Optional[float]
    reasoning: str


# Semantic parameter name mappings
NUMERIC_PARAMETER_DOMAINS: Dict[str, DomainRange] = {
    "marks": DomainRange(
        "[0, 100]",
        0.0,
        100.0,
        "Academic marks typically range from 0 to 100.",
    ),
    "score": DomainRange(
        "[0, 100]",
        0.0,
        100.0,
        "Percentage or test scores are bounded between 0 and 100.",
    ),
    "age": DomainRange(
        "[0, 150]",
        0.0,
        150.0,
        "Human age must be non-negative and under reasonable biological limits.",
    ),
    "price": DomainRange(
        ">= 0.0",
        0.0,
        None,
        "Monetary prices cannot be negative.",
    ),
    "cost": DomainRange(
        ">= 0.0",
        0.0,
        None,
        "Item cost cannot be negative.",
    ),
    "fee": DomainRange(
        ">= 0.0",
        0.0,
        None,
        "Transaction fee cannot be negative.",
    ),
    "quantity": DomainRange(
        ">= 0",
        0.0,
        None,
        "Quantity counts cannot be negative.",
    ),
    "qty": DomainRange(
        ">= 0",
        0.0,
        None,
        "Quantity counts cannot be negative.",
    ),
    "count": DomainRange(
        ">= 0",
        0.0,
        None,
        "Item count must be a non-negative number.",
    ),
    "percent": DomainRange(
        "[0, 100] or [0.0, 1.0]",
        0.0,
        100.0,
        "Percentage must be bounded between 0 and 100 (or 0.0 to 1.0).",
    ),
    "percentage": DomainRange(
        "[0, 100] or [0.0, 1.0]",
        0.0,
        100.0,
        "Percentage must be bounded between 0 and 100 (or 0.0 to 1.0).",
    ),
}


class InputValidationDetector(BaseDetector):
    """Detects numeric parameters used without bounds or NaN validation."""

    @property
    def name(self) -> str:
        return "INPUT_VALIDATION"

    def detect(
        self,
        project_root: Path,
        file_indices: List[FileASTIndex],
        cancel_token: Optional[CancellationToken] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []

        for idx in file_indices:
            if cancel_token:
                cancel_token.check_cancelled()

            # Analyze functions
            for fn in idx.functions:
                findings.extend(
                    self._check_callable(
                        file_path=idx.file_path,
                        symbol=fn.name,
                        signature=fn.signature,
                        implementation=fn.implementation,
                        start_line=fn.range.start_line,
                    )
                )

            # Analyze methods
            for m in idx.methods:
                findings.extend(
                    self._check_callable(
                        file_path=idx.file_path,
                        symbol=f"{m.class_name}.{m.name}",
                        signature=m.signature,
                        implementation=m.implementation,
                        start_line=m.range.start_line,
                    )
                )

        return findings

    def _check_callable(
        self,
        file_path: str,
        symbol: str,
        signature: str,
        implementation: str,
        start_line: int,
    ) -> List[Finding]:
        findings: List[Finding] = []

        # Extract parameter names from signature
        # e.g. def calculate_grade(marks: float, score: int):
        if "(" in signature and ")" in signature:
            params_str = signature[signature.find("(") + 1 : signature.rfind(")")]
        else:
            params_str = signature

        raw_parts = [p.strip() for p in params_str.split(",") if p.strip()]
        found_params = []
        for part in raw_parts:
            # Strip type annotation and default value
            param_name = part.split(":")[0].split("=")[0].strip()
            # Remove any leading * or **
            param_name = param_name.lstrip("*")
            if param_name and param_name not in {"self", "cls"}:
                found_params.append(param_name)

        for param in found_params:
            param_lower = param.lower().strip()
            # Match directly or as suffix (e.g. final_score, item_price, total_quantity)
            matched_key = None
            if param_lower in NUMERIC_PARAMETER_DOMAINS:
                matched_key = param_lower
            else:
                for key in NUMERIC_PARAMETER_DOMAINS:
                    if param_lower.endswith(f"_{key}") or param_lower.startswith(f"{key}_"):
                        matched_key = key
                        break

            if not matched_key:
                continue

            domain = NUMERIC_PARAMETER_DOMAINS[matched_key]

            # Check if parameter has guard checks in implementation
            # Look for checks like: if param < 0, if param > 100, isnan(param), etc.
            guard_patterns = [
                rf"\b{param}\s*<\s*0",
                rf"\b{param}\s*<=\s*0",
                rf"\b{param}\s*>\s*0",
                rf"\b{param}\s*>\s*100",
                rf"\b{param}\s*>=\s*100",
                rf"isnan\s*\(\s*{param}\s*\)",
                rf"isinstance\s*\(\s*{param}\s*,",
                rf"typeof\s+{param}",
                rf"isNaN\s*\(\s*{param}\s*\)",
            ]

            has_guard = any(re.search(pat, implementation) for pat in guard_patterns)

            if not has_guard:
                # Find line of parameter definition or first use
                lines = implementation.splitlines()
                evidence = signature
                rel_line = 0
                for i, l in enumerate(lines):
                    if param in l and i > 0:
                        evidence = l.strip()
                        rel_line = i
                        break

                findings.append(
                    Finding(
                        file=file_path,
                        line_start=start_line + rel_line,
                        line_end=start_line + rel_line,
                        symbol=symbol,
                        category=FindingCategory.INPUT_VALIDATION,
                        cwe="CWE-20",
                        evidence=evidence,
                        detector=self.name,
                        raw_confidence=0.86,
                        description=(
                            f"Numeric parameter '{param}' is used without range or NaN validation. "
                            f"Probable valid range: {domain.range_str}. Reasoning: {domain.reasoning}"
                        ),
                        metadata={
                            "parameter": param,
                            "probable_valid_range": domain.range_str,
                            "reasoning": domain.reasoning,
                        },
                    )
                )

        return findings
