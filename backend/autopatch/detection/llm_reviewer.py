"""LLM semantic reviewer analyzing function logic and edge-case vulnerabilities.

Feeds AST context, signatures, callers, and callees.
Enforces strict hallucination elimination: any finding whose quoted evidence
does not verbatim exist in the target file is discarded immediately.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from autopatch.core.logging import get_logger
from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.graph import DependencyGraphs
from autopatch.intelligence.models import FileASTIndex
from autopatch.security.redaction import assert_clean_prompt, redact_secrets
from autopatch.security.prompt_defense import (
    sanitize_untrusted_code,
    build_hardened_system_prompt,
)
from autopatch.security.privacy_mode import PrivacyGuard

logger = get_logger(__name__)


class LLMSemanticReviewer(BaseDetector):
    """Batched LLM semantic reviewer with strict evidence validation."""

    def __init__(
        self,
        llm_client: Optional[Callable[[str], str]] = None,
        graphs: Optional[DependencyGraphs] = None,
        batch_size: int = 5,
    ):
        self.llm_client = llm_client
        self.graphs = graphs
        self.batch_size = batch_size

    @property
    def name(self) -> str:
        return "LLM_SEMANTIC"

    def detect(
        self,
        project_root: Path,
        file_indices: List[FileASTIndex],
        cancel_token: Optional[CancellationToken] = None,
    ) -> List[Finding]:
        findings: List[Finding] = []
        if PrivacyGuard.is_privacy_mode_active():
            logger.info("Privacy Mode active: Bypassing external LLM semantic review.")
            return findings

        if not self.llm_client:
            return findings

        # Collect all functions and methods across indices
        callables_to_review: List[Dict[str, Any]] = []
        for idx in file_indices:
            for fn in idx.functions:
                callables_to_review.append(
                    {
                        "file": idx.file_path,
                        "symbol": fn.name,
                        "signature": fn.signature,
                        "implementation": fn.implementation,
                        "start_line": fn.range.start_line,
                        "end_line": fn.range.end_line,
                    }
                )
            for m in idx.methods:
                callables_to_review.append(
                    {
                        "file": idx.file_path,
                        "symbol": f"{m.class_name}.{m.name}",
                        "signature": m.signature,
                        "implementation": m.implementation,
                        "start_line": m.range.start_line,
                        "end_line": m.range.end_line,
                    }
                )

        # Batch callables
        for i in range(0, len(callables_to_review), self.batch_size):
            if cancel_token:
                cancel_token.check_cancelled()

            batch = callables_to_review[i : i + self.batch_size]
            batch_prompt = self._build_prompt(batch, project_root)

            # Rule 4: Redact secrets before sending prompt to LLM
            sanitized_prompt, _ = redact_secrets(batch_prompt)
            assert_clean_prompt(sanitized_prompt)

            try:
                response_text = self.llm_client(sanitized_prompt)
                parsed_findings = self._parse_and_validate_response(response_text, project_root)
                findings.extend(parsed_findings)
            except Exception as e:
                logger.warning("LLM review batch failed", extra={"data": {"error": str(e)}})

        return findings

    def _build_prompt(self, batch: List[Dict[str, Any]], project_root: Path) -> str:
        base_instruction = (
            "You are an expert static analysis security and logic reviewer.\n"
            "Analyze the following functions for logic bugs, boundary edge cases, and runtime defects.\n"
            "Return a JSON array of findings with schema:\n"
            "[{\n"
            '  "file": string,\n'
            '  "line_start": int,\n'
            '  "line_end": int,\n'
            '  "symbol": string,\n'
            '  "category": "LOGIC_ERROR" | "INPUT_VALIDATION" | "SECURITY" | "RESOURCE_LEAK",\n'
            '  "cwe": string or null,\n'
            '  "evidence": string (MUST BE A VERBATIM QUOTE FROM THE CODE),\n'
            '  "description": string,\n'
            '  "raw_confidence": float (0.0 to 1.0)\n'
            "}]\n\n"
        )
        prompt = build_hardened_system_prompt(base_instruction)

        for item in batch:
            callers = self.graphs.callers(item["symbol"]) if self.graphs else []
            callees = self.graphs.callees(item["symbol"]) if self.graphs else []
            quarantined_code = sanitize_untrusted_code(item["implementation"], item["file"])

            prompt += (
                f"\n--- FUNCTION: {item['symbol']} in {item['file']} ---\n"
                f"Signature: {item['signature']}\n"
                f"Callers: {', '.join(callers) or 'None'}\n"
                f"Callees: {', '.join(callees) or 'None'}\n"
                f"{quarantined_code}\n"
            )

        return prompt

    def _parse_and_validate_response(self, response_text: str, project_root: Path) -> List[Finding]:
        """Parses LLM JSON and discards any finding without exact verbatim code evidence."""
        findings: List[Finding] = []

        # Extract JSON array
        start_idx = response_text.find("[")
        end_idx = response_text.rfind("]")
        if start_idx == -1 or end_idx == -1:
            return findings

        json_str = response_text[start_idx : end_idx + 1]
        try:
            raw_list = json.loads(json_str)
        except Exception:
            return findings

        if not isinstance(raw_list, list):
            return findings

        for item in raw_list:
            if not isinstance(item, dict):
                continue

            file_path = item.get("file", "")
            evidence = item.get("evidence", "").strip()

            if not file_path or not evidence:
                logger.debug("Discarding LLM finding: missing file or evidence.")
                continue

            full_path = (project_root / file_path).resolve()
            if not full_path.is_file():
                logger.debug(f"Discarding LLM finding: target file does not exist: {file_path}")
                continue

            # Invariant: Code evidence MUST exist verbatim in the target file
            file_code = full_path.read_text(encoding="utf-8", errors="replace")
            if evidence not in file_code:
                logger.warning(
                    f"Discarding hallucinated LLM finding: evidence '{evidence}' not found in {file_path}"
                )
                continue

            # Calculate accurate line range from the evidence occurrence
            lines = file_code.splitlines()
            start_line = item.get("line_start", 1)
            end_line = item.get("line_end", start_line)

            for line_no, line in enumerate(lines, start=1):
                if evidence in line:
                    start_line = line_no
                    end_line = line_no
                    break

            try:
                category_val = item.get("category", "LOGIC_ERROR")
                category = FindingCategory(category_val)
            except Exception:
                category = FindingCategory.LOGIC_ERROR

            try:
                finding = Finding(
                    file=file_path,
                    line_start=start_line,
                    line_end=end_line,
                    symbol=item.get("symbol"),
                    category=category,
                    cwe=item.get("cwe"),
                    evidence=evidence,
                    detector=self.name,
                    raw_confidence=float(item.get("raw_confidence", 0.85)),
                    description=item.get("description", "LLM identified defect"),
                    metadata={"reviewer": "llm"},
                )
                findings.append(finding)
            except Exception as e:
                logger.debug(f"Discarding malformed LLM finding: {e}")

        return findings
