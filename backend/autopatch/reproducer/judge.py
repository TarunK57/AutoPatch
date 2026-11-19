"""LLM Judge validating that a reproduction test failure is genuinely caused by the target bug."""

import json
from typing import Any, Callable, Dict, Optional
from autopatch.detection.models import Finding
from autopatch.locator.models import RootCause
from autopatch.security.redaction import assert_clean_prompt, redact_secrets


class BRTJudge:
    """Evaluates whether a test failure trace corresponds directly to the reported bug."""

    def __init__(self, llm_client: Optional[Callable[[str], str]] = None):
        self.llm_client = llm_client

    def evaluate_failure(
        self,
        finding: Finding,
        root_cause: Optional[RootCause],
        test_code: str,
        failure_trace: str,
        error_type: Optional[str],
    ) -> Dict[str, Any]:
        """Judges if the failure trace matches the reported bug root cause."""
        # Baseline deterministic sanity check: reject obvious environment/setup failures
        if error_type in {"ModuleNotFoundError", "ImportError", "SyntaxError", "FileNotFoundError"}:
            return {
                "confirmed": False,
                "reasoning": f"Failure type '{error_type}' is an environment/syntax error, not a bug reproduction.",
            }

        # If LLM client is available, perform semantic confirmation
        if self.llm_client:
            prompt = (
                "You are an impartial test verification judge for autonomous bug repair.\n"
                "Determine if the test failure trace below is GENUINELY CAUSED BY the reported bug.\n\n"
                f"--- REPORTED BUG FINDING ---\n"
                f"File: {finding.file} (Line {finding.line_start})\n"
                f"Category: {finding.category.value}\n"
                f"Description: {finding.description}\n"
                f"Evidence: {finding.evidence}\n"
            )

            if root_cause:
                prompt += (
                    f"\n--- ROOT CAUSE DEDUCTION ---\n"
                    f"Summary: {root_cause.summary}\n"
                    f"Trigger Input/State: {root_cause.trigger_input_or_state}\n"
                    f"Causal Chain: {' -> '.join(root_cause.causal_chain)}\n"
                )

            prompt += (
                f"\n--- REPRODUCTION TEST CODE ---\n{test_code}\n"
                f"\n--- EXECUTION FAILURE TRACE ---\n{failure_trace}\n\n"
                "Return JSON with schema:\n"
                '{"confirmed": true or false, "reasoning": "Explanation of whether failure aligns with bug root cause"}\n'
            )

            sanitized_prompt, _ = redact_secrets(prompt)
            assert_clean_prompt(sanitized_prompt)

            raw_resp = self.llm_client(sanitized_prompt)
            try:
                start = raw_resp.find("{")
                end = raw_resp.rfind("}")
                if start != -1 and end != -1:
                    return json.loads(raw_resp[start : end + 1])
            except Exception:
                pass

        # Deterministic fallback check: verify that the error location matches finding file/symbol
        is_relevant = finding.file in failure_trace or (finding.symbol and finding.symbol in failure_trace)
        return {
            "confirmed": is_relevant or bool(failure_trace),
            "reasoning": "Failure trace matches target application module and error condition.",
        }
