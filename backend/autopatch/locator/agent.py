"""Locator Agent using Stratified Context Retrieval.

Orchestrates multi-stratum iterative AST search, SBFL Ochiai hint integration,
token-budget protection, and streamable evidence trail production.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional

from autopatch.core.exceptions import AutoPatchError
from autopatch.core.logging import get_logger
from autopatch.detection.models import Finding
from autopatch.intelligence.code_search import CodeSearchEngine
from autopatch.intelligence.models import FileASTIndex
from autopatch.locator.models import (
    BuggyLocation,
    EvidenceRecord,
    RootCause,
    ToolCallRequest,
)
from autopatch.locator.ochiai import OchiaiFaultLocalizer
from autopatch.locator.tools import CodeSearchToolDispatcher
from autopatch.security.redaction import assert_clean_prompt, redact_secrets
from autopatch.security.prompt_defense import (
    sanitize_untrusted_code,
    sanitize_untrusted_issue_text,
    build_hardened_system_prompt,
)
from autopatch.security.privacy_mode import PrivacyGuard

logger = get_logger(__name__)

MAX_STRATA = 10
HARD_TOKEN_BUDGET = 25000  # Hard token cap to prevent runaway token spend


class LocatorAgent:
    """Autonomous agent that locates buggy methods and deduces root causes via stratified search."""

    def __init__(
        self,
        search_engine: CodeSearchEngine,
        llm_client: Callable[[str], str],
        max_strata: int = MAX_STRATA,
        token_budget: int = HARD_TOKEN_BUDGET,
        file_indices: Optional[List[FileASTIndex]] = None,
    ):
        self.search_engine = search_engine
        self.dispatcher = CodeSearchToolDispatcher(search_engine)
        self.llm_client = llm_client
        self.max_strata = min(max_strata, MAX_STRATA)
        self.token_budget = token_budget
        self.fault_localizer = OchiaiFaultLocalizer(file_indices or [])

    def locate(
        self,
        finding: Finding,
        issue_text: Optional[str] = None,
        test_spectra: Optional[List[Dict[str, Any]]] = None,
        on_evidence_stream: Optional[Callable[[EvidenceRecord], None]] = None,
    ) -> RootCause:
        """Executes the stratified retrieval loop and produces the final RootCause object."""
        evidence_trail: List[EvidenceRecord] = []
        tokens_consumed = 0

        # 1. Compute Ochiai method-level hints if test spectra exist
        ochiai_hints = []
        if test_spectra:
            ochiai_hints = self.fault_localizer.compute_from_spectra(test_spectra, top_k=5)

        retrieved_context: List[Dict[str, Any]] = []
        strata_used = 0

        # 2. Stratified retrieval loop
        for stratum in range(1, self.max_strata + 1):
            strata_used = stratum

            # Check hard token budget cap
            if tokens_consumed >= self.token_budget:
                logger.warning(
                    f"Locator agent reached hard token cap ({self.token_budget}). Terminating search early."
                )
                break

            # Prompt 1: Request tool calls
            stratum_prompt = self._build_stratum_prompt(
                finding=finding,
                issue_text=issue_text,
                ochiai_hints=ochiai_hints,
                evidence_trail=evidence_trail,
                retrieved_context=retrieved_context,
                stratum=stratum,
            )

            # Redact prompt before sending to LLM (Rule 4)
            sanitized_prompt, _ = redact_secrets(stratum_prompt)
            assert_clean_prompt(sanitized_prompt)
            tokens_consumed += len(sanitized_prompt.split())

            raw_response = self.llm_client(sanitized_prompt)
            tokens_consumed += len(raw_response.split())

            # Parse requested tool calls
            tool_requests = self._parse_tool_requests(raw_response)
            if not tool_requests:
                # If LLM requested no tools, it may already have sufficient context
                break

            # Execute tool calls locally against AST index
            new_results = []
            for req in tool_requests:
                record = self.dispatcher.execute_call(req, stratum=stratum)
                evidence_trail.append(record)
                if on_evidence_stream:
                    on_evidence_stream(record)

                if record.success and record.raw_result:
                    if isinstance(record.raw_result, list):
                        new_results.extend(record.raw_result)
                    else:
                        new_results.append(record.raw_result)

            retrieved_context.extend(new_results)

            # Prompt 2: Context sufficiency evaluation
            eval_prompt = self._build_sufficiency_prompt(
                finding=finding,
                evidence_trail=evidence_trail,
                retrieved_context=retrieved_context,
            )
            sanitized_eval_prompt, _ = redact_secrets(eval_prompt)
            assert_clean_prompt(sanitized_eval_prompt)
            tokens_consumed += len(sanitized_eval_prompt.split())

            eval_response = self.llm_client(sanitized_eval_prompt)
            tokens_consumed += len(eval_response.split())

            sufficiency_decision = self._parse_sufficiency_decision(eval_response)
            if sufficiency_decision.get("sufficient", False):
                # Context is sufficient to localize the bug
                break

        # 3. Final Root Cause deduction
        root_cause = self._synthesize_root_cause(
            finding=finding,
            issue_text=issue_text,
            ochiai_hints=ochiai_hints,
            evidence_trail=evidence_trail,
            retrieved_context=retrieved_context,
            strata_used=strata_used,
            total_tokens=tokens_consumed,
        )

        return root_cause

    def _build_stratum_prompt(
        self,
        finding: Finding,
        issue_text: Optional[str],
        ochiai_hints: List[Dict[str, Any]],
        evidence_trail: List[EvidenceRecord],
        retrieved_context: List[Dict[str, Any]],
        stratum: int,
    ) -> str:
        tools_desc = json.dumps(self.dispatcher.get_tool_definitions(), indent=2)

        base_prompt = (
            f"You are the AutoPatch Locator Agent (Stratum {stratum} of {self.max_strata}).\n"
            "Your goal is to inspect source code to locate the root cause and faulty method(s).\n\n"
            f"--- INITIAL FINDING ---\n"
            f"File: {finding.file} (Lines {finding.line_start}-{finding.line_end})\n"
            f"Category: {finding.category.value} | CWE: {finding.cwe or 'None'}\n"
            f"Evidence:\n{sanitize_untrusted_code(finding.evidence, finding.file)}\n"
            f"Description: {finding.description}\n"
        )
        prompt = build_hardened_system_prompt(base_prompt)

        if issue_text:
            prompt += f"\n--- USER ISSUE REPORT ---\n{sanitize_untrusted_issue_text(issue_text)}\n"

        if ochiai_hints:
            prompt += "\n--- SBFL OCHIAI TOP SUSPICIOUS METHODS (HINTS) ---\n"
            for h in ochiai_hints:
                prompt += f"- {h['qualified_name']} (Ochiai score: {h['ochiai_score']:.3f})\n"

        if evidence_trail:
            prompt += "\n--- SEARCH HISTORY & RESULTS SO FAR ---\n"
            for rec in evidence_trail[-6:]:  # Keep recent history
                prompt += f"[Stratum {rec.stratum}] Tool: {rec.tool_name}({rec.arguments}) -> {rec.result_summary}\n"

        prompt += (
            f"\n--- AVAILABLE CODE-SEARCH TOOLS ---\n{tools_desc}\n\n"
            "Select ONLY the necessary API calls for this stratum (multiple allowed).\n"
            "Return JSON matching:\n"
            "{\n"
            '  "calls": [\n'
            '    {"tool": "search_method", "arguments": {"method_name": "foo"}, "reasoning": "..."}\n'
            "  ]\n"
            "}\n"
        )
        return prompt

    def _build_sufficiency_prompt(
        self,
        finding: Finding,
        evidence_trail: List[EvidenceRecord],
        retrieved_context: List[Dict[str, Any]],
    ) -> str:
        prompt = (
            "Evaluate whether the gathered code context is sufficient to explain the bug and pinpoint the faulty method.\n"
            f"Target finding: {finding.file}:{finding.line_start} ({finding.description})\n"
            f"Total tool executions: {len(evidence_trail)}\n"
            "Return JSON:\n"
            '{"sufficient": true or false, "reasoning": "..."}\n'
        )
        return prompt

    def _parse_tool_requests(self, response_text: str) -> List[ToolCallRequest]:
        requests: List[ToolCallRequest] = []
        try:
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(response_text[start : end + 1])
                calls = data.get("calls", [])
                for c in calls:
                    requests.append(
                        ToolCallRequest(
                            tool=c.get("tool", ""),
                            arguments=c.get("arguments", {}),
                            reasoning=c.get("reasoning", ""),
                        )
                    )
        except Exception:
            pass
        return requests

    def _parse_sufficiency_decision(self, response_text: str) -> Dict[str, Any]:
        try:
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(response_text[start : end + 1])
        except Exception:
            pass
        return {"sufficient": True}

    def _synthesize_root_cause(
        self,
        finding: Finding,
        issue_text: Optional[str],
        ochiai_hints: List[Dict[str, Any]],
        evidence_trail: List[EvidenceRecord],
        retrieved_context: List[Dict[str, Any]],
        strata_used: int,
        total_tokens: int,
    ) -> RootCause:
        """Synthesizes the RootCause analysis object."""
        # Query LLM for final structured RootCause JSON
        final_prompt = (
            "Based on the finding, evidence trail, and retrieved code, deduce the complete root cause.\n"
            f"Finding: {finding.file}:{finding.line_start} - {finding.description}\n"
            f"Evidence: {finding.evidence}\n"
            "Output JSON matching schema:\n"
            "{\n"
            '  "summary": string,\n'
            '  "trigger_input_or_state": string,\n'
            '  "causal_chain": [string, ...],\n'
            '  "buggy_locations": [\n'
            '    {"file": string, "class_name": string or null, "method_name": string, "line_start": int, "line_end": int, "score": float, "rationale": string}\n'
            "  ],\n"
            '  "confidence": float (0.0 to 1.0)\n'
            "}\n"
        )
        sanitized_final, _ = redact_secrets(final_prompt)
        assert_clean_prompt(sanitized_final)

        raw_final = self.llm_client(sanitized_final)

        # Parse JSON with fallback guarantees
        try:
            start = raw_final.find("{")
            end = raw_final.rfind("}")
            data = json.loads(raw_final[start : end + 1])
        except Exception:
            data = {}

        summary = data.get("summary") or finding.description
        trigger = data.get("trigger_input_or_state") or f"Execution reaching {finding.file}:{finding.line_start}"
        causal_chain = data.get("causal_chain") or [
            f"Execution enters {finding.file}",
            f"Fault triggered at line {finding.line_start}: {finding.evidence}",
        ]

        buggy_locations: List[BuggyLocation] = []
        raw_locs = data.get("buggy_locations", [])
        for loc in raw_locs:
            try:
                buggy_locations.append(
                    BuggyLocation(
                        file=loc.get("file", finding.file),
                        class_name=loc.get("class_name"),
                        method_name=loc.get("method_name", finding.symbol or "unknown"),
                        line_start=int(loc.get("line_start", finding.line_start)),
                        line_end=int(loc.get("line_end", finding.line_end)),
                        score=float(loc.get("score", 0.9)),
                        rationale=loc.get("rationale", ""),
                    )
                )
            except Exception:
                pass

        # Fallback if no locations were parsed: use finding symbol or ochiai hint
        if not buggy_locations:
            if ochiai_hints:
                top = ochiai_hints[0]
                buggy_locations.append(
                    BuggyLocation(
                        file=top["file"],
                        class_name=top.get("class_name"),
                        method_name=top["method_name"],
                        line_start=top["line_start"],
                        line_end=top["line_end"],
                        score=top["ochiai_score"],
                        rationale="Localized via spectrum-based fault localization (Ochiai).",
                    )
                )
            else:
                buggy_locations.append(
                    BuggyLocation(
                        file=finding.file,
                        class_name=None,
                        method_name=finding.symbol or "unknown",
                        line_start=finding.line_start,
                        line_end=finding.line_end,
                        score=finding.raw_confidence,
                        rationale=finding.description,
                    )
                )

        # Sort buggy locations by score descending
        buggy_locations.sort(key=lambda x: x.score, reverse=True)

        confidence = float(data.get("confidence", finding.raw_confidence))

        return RootCause(
            summary=summary,
            trigger_input_or_state=trigger,
            causal_chain=causal_chain,
            buggy_locations=buggy_locations,
            confidence=round(min(1.0, max(0.0, confidence)), 4),
            evidence_trail=evidence_trail,
            ochiai_hints=ochiai_hints,
            strata_used=strata_used,
            total_tokens_used=total_tokens,
        )
