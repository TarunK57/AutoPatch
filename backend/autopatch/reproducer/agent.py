"""Reproducer Agent that writes Bug Reproduction Tests (Fail-to-Pass).

Enforces non-negotiable rules:
- edit may ONLY modify files matching test-file patterns.
- Creates new tests and NEVER alters existing ones.
- finish is rejected until run_tests has executed at least once.
- Max 25 steps per run; run_tests outcome is Pass, Fail, or Error.
- Always generates boundary tests: normal, minimum, maximum, invalid.
- Candidate BRT (fails on buggy code) vs Plausible BRT (passes on reference fix).
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from autopatch.core.exceptions import InvariantViolationError, TestModificationForbiddenError
from autopatch.core.logging import get_logger
from autopatch.core.models import TEST_FILE_PATTERNS
from autopatch.detection.models import Finding
from autopatch.intelligence.code_search import CodeSearchEngine
from autopatch.locator.models import RootCause
from autopatch.reproducer.judge import BRTJudge
from autopatch.reproducer.models import (
    AgentStep,
    BRTClassification,
    ReproductionResult,
    TestRunResult,
    TestRunStatus,
)
from autopatch.reproducer.sandbox_runner import SandboxedBRTRunner
from autopatch.security.redaction import assert_clean_prompt, redact_secrets

logger = get_logger(__name__)

MAX_STEPS = 25


class ReproducerAgent:
    """Autonomous agent synthesizing Bug Reproduction Tests (BRTs)."""

    def __init__(
        self,
        project_root: Path,
        search_engine: CodeSearchEngine,
        llm_client: Callable[[str], str],
        sandbox_runner: Optional[SandboxedBRTRunner] = None,
        judge: Optional[BRTJudge] = None,
        max_steps: int = MAX_STEPS,
    ):
        self.project_root = project_root.resolve()
        self.search_engine = search_engine
        self.llm_client = llm_client
        self.runner = sandbox_runner or SandboxedBRTRunner()
        self.judge = judge or BRTJudge(llm_client)
        self.max_steps = min(max_steps, MAX_STEPS)

        # Snapshot existing project files before running to guarantee never modifying existing files
        self._existing_files: Set[str] = set()
        for p in self.project_root.rglob("*"):
            if p.is_file():
                self._existing_files.add(str(p.relative_to(self.project_root)))

        self._created_test_files: Set[str] = set()

    def run_reproduction_cycle(
        self,
        finding: Finding,
        root_cause: Optional[RootCause] = None,
        reference_fix_patch: Optional[str] = None,
        samples: int = 1,
    ) -> ReproductionResult:
        """Executes one or more reproduction test generation runs and classifies results."""
        all_runs_steps: List[List[AgentStep]] = []
        candidate_count = 0
        plausible_count = 0
        unique_traces: Set[str] = set()

        best_test_path: Optional[str] = None
        best_test_code: Optional[str] = None
        best_classification = BRTClassification()

        for sample_idx in range(1, samples + 1):
            steps: List[AgentStep] = []
            test_file_path: Optional[str] = None
            test_run_executed = False
            last_run_result: Optional[TestRunResult] = None

            # Agent step loop (Max 25 steps)
            for step_num in range(1, self.max_steps + 1):
                agent_prompt = self._build_agent_prompt(
                    finding=finding,
                    root_cause=root_cause,
                    steps=steps,
                    step_num=step_num,
                    test_run_executed=test_run_executed,
                    last_result=last_run_result,
                )

                sanitized_prompt, _ = redact_secrets(agent_prompt)
                assert_clean_prompt(sanitized_prompt)

                raw_action_resp = self.llm_client(sanitized_prompt)
                action_data = self._parse_action(raw_action_resp)
                action_name = action_data.get("action", "").lower().strip()
                params = action_data.get("parameters", {})

                # Dispatch Action
                step_output = ""

                if action_name == "cat":
                    path = params.get("path", "")
                    step_output = self._action_cat(path)

                elif action_name == "code_search":
                    text = params.get("text", "") or params.get("snippet", "")
                    step_output = self._action_code_search(text)

                elif action_name == "edit":
                    path = params.get("path", "")
                    change_desc = params.get("change_description", "Write bug reproduction test")
                    test_file_path = path
                    step_output = self._action_edit(
                        path=path,
                        change_desc=change_desc,
                        finding=finding,
                        root_cause=root_cause,
                    )

                elif action_name == "run_tests":
                    path = params.get("path", test_file_path or "")
                    last_run_result = self.runner.run_test_file(self.project_root, path)
                    test_run_executed = True
                    step_output = (
                        f"Status: {last_run_result.status.value}\n"
                        f"Exit Code: {last_run_result.exit_code}\n"
                        f"Failure Trace: {last_run_result.failure_trace or 'None'}\n"
                        f"Output: {last_run_result.stdout[:300]}"
                    )

                elif action_name == "finish":
                    # Rule: finish is rejected until run_tests has executed at least once
                    if not test_run_executed:
                        step_output = (
                            "Action 'finish' REJECTED: You must run the tests with run_tests(path) "
                            "at least once before finishing."
                        )
                    else:
                        steps.append(
                            AgentStep(
                                step_number=step_num,
                                action="finish",
                                parameters=params,
                                output="Reproduction test generation finished successfully.",
                            )
                        )
                        break
                else:
                    step_output = f"Unknown action '{action_name}'. Valid actions: cat, code_search, edit, run_tests, finish."

                steps.append(
                    AgentStep(
                        step_number=step_num,
                        action=action_name or "unknown",
                        parameters=params,
                        output=step_output,
                    )
                )

            all_runs_steps.append(steps)

            # Evaluate this sample's generated test
            if test_file_path and (self.project_root / test_file_path).is_file():
                test_code = (self.project_root / test_file_path).read_text(encoding="utf-8")
                classification = self._classify_test(
                    finding=finding,
                    root_cause=root_cause,
                    test_file_path=test_file_path,
                    test_code=test_code,
                    last_run_result=last_run_result,
                    reference_fix_patch=reference_fix_patch,
                )

                if classification.is_candidate:
                    candidate_count += 1
                    if classification.failure_trace:
                        unique_traces.add(classification.failure_trace.strip())

                if classification.is_plausible:
                    plausible_count += 1

                if not best_test_path or (classification.is_candidate and not best_classification.is_candidate):
                    best_test_path = test_file_path
                    best_test_code = test_code
                    best_classification = classification

        candidate_rate = round(candidate_count / max(1, samples), 4)
        plausible_rate = round(plausible_count / max(1, samples), 4)

        return ReproductionResult(
            bug_id=str(finding.metadata.get("bug_id", finding.file)),
            test_file_path=best_test_path,
            test_code=best_test_code,
            classification=best_classification,
            steps=all_runs_steps[0] if all_runs_steps else [],
            runs_sampled=samples,
            candidate_rate=candidate_rate,
            plausible_rate=plausible_rate,
            unique_failure_traces=sorted(list(unique_traces)),
        )

    # =========================================================================
    # Action Implementations
    # =========================================================================
    def _action_cat(self, rel_path: str) -> str:
        """Reads file contents safely."""
        full_path = (self.project_root / rel_path).resolve()
        if not str(full_path).startswith(str(self.project_root)):
            return f"Error: Access denied to path outside workspace: {rel_path}"
        if not full_path.is_file():
            return f"Error: File not found: {rel_path}"
        try:
            return full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading {rel_path}: {str(e)}"

    def _action_code_search(self, text: str) -> str:
        """Executes snippet code search."""
        if not text:
            return "Error: missing search snippet text."
        results = self.search_engine.search_code(text)
        if not results:
            return "No matches found."
        summaries = [f"{r.file_path}:{r.line_start}\n{r.content}" for r in results[:5]]
        return "\n---\n".join(summaries)

    def _action_edit(
        self,
        path: str,
        change_desc: str,
        finding: Finding,
        root_cause: Optional[RootCause],
    ) -> str:
        """Executes test creation via a dedicated LLM call with boundary tests.

        Enforces:
        - edit may only modify files matching test-file patterns.
        - Creates new tests and NEVER alters existing files.
        """
        # 1. Enforce test-file pattern
        is_test_pattern = any(pat.search(path) for pat in TEST_FILE_PATTERNS) or "tests/" in path or "test_" in path
        if not is_test_pattern:
            raise TestModificationForbiddenError(
                f"Action 'edit' rejected: target path '{path}' does not match test-file patterns. "
                "The Reproducer Agent is only permitted to create test files."
            )

        # 2. Enforce: Never modify existing files!
        if path in self._existing_files:
            raise InvariantViolationError(
                f"Action 'edit' rejected: '{path}' was an existing file in the project. "
                "Rule: The Reproducer Agent creates new tests and NEVER alters existing ones."
            )

        # 3. Dedicated LLM call for code editing
        test_code = self._generate_test_code_llm(
            path=path,
            change_desc=change_desc,
            finding=finding,
            root_cause=root_cause,
        )

        full_path = (self.project_root / path).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(test_code, encoding="utf-8")
        self._created_test_files.add(path)

        return f"Successfully created new reproduction test file at '{path}' ({len(test_code.splitlines())} lines)."

    def _generate_test_code_llm(
        self,
        path: str,
        change_desc: str,
        finding: Finding,
        root_cause: Optional[RootCause],
    ) -> str:
        """Separate LLM call generating boundary tests for the bug."""
        prompt = (
            "Write a bug reproduction test for the following bug.\n\n"
            f"--- BUG DETAILS ---\n"
            f"Target File: {finding.file}:{finding.line_start}\n"
            f"Category: {finding.category.value}\n"
            f"Description: {finding.description}\n"
            f"Evidence: {finding.evidence}\n"
        )

        if root_cause:
            prompt += (
                f"\n--- ROOT CAUSE & LOCATIONS ---\n"
                f"Summary: {root_cause.summary}\n"
                f"Trigger Input/State: {root_cause.trigger_input_or_state}\n"
                f"Locations: {', '.join(loc.qualified_name for loc in root_cause.buggy_locations)}\n"
            )

        prompt += (
            f"\n--- TEST SPECIFICATION ---\n"
            f"Target Test File: {path}\n"
            f"Change Description: {change_desc}\n\n"
            "REQUIREMENTS:\n"
            "1. Must be a standalone, executable pytest (Python) or Jest (JS) test file.\n"
            "2. Always generate boundary tests covering: normal, minimum, maximum, and invalid inputs.\n"
            "3. The test MUST fail on the buggy implementation (Candidate BRT), demonstrating the exact flaw.\n"
            "4. Return ONLY valid, executable source code inside a ```python or ```javascript block.\n"
        )

        sanitized_prompt, _ = redact_secrets(prompt)
        assert_clean_prompt(sanitized_prompt)

        raw_code_resp = self.llm_client(sanitized_prompt)

        # Extract code from markdown fences
        if "```" in raw_code_resp:
            start_fence = raw_code_resp.find("```")
            end_fence = raw_code_resp.rfind("```")
            block = raw_code_resp[start_fence:end_fence]
            lines = block.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            return "\n".join(lines).strip()

        return raw_code_resp.strip()

    def _classify_test(
        self,
        finding: Finding,
        root_cause: Optional[RootCause],
        test_file_path: str,
        test_code: str,
        last_run_result: Optional[TestRunResult],
        reference_fix_patch: Optional[str],
    ) -> BRTClassification:
        """Classifies reproduction test as Candidate and/or Plausible BRT."""
        if not last_run_result:
            return BRTClassification(is_candidate=False, failure_reason="Test was not executed.")

        # If test execution encountered syntax or environment setup error -> Not a Candidate
        if last_run_result.status == TestRunStatus.ERROR:
            return BRTClassification(
                is_candidate=False,
                failure_trace=last_run_result.failure_trace,
                failure_reason=f"Test failed with setup/environment error: {last_run_result.error_type}",
            )

        # If test passed on buggy code -> Failed to reproduce!
        if last_run_result.status == TestRunStatus.PASS:
            return BRTClassification(
                is_candidate=False,
                failure_reason="Test passed on buggy code; failed to reproduce the defect.",
            )

        # Test failed with runtime assertion/logic error -> Candidate BRT!
        failure_trace = last_run_result.failure_trace or "Assertion error"

        # LLM Judge verifies that the failure is genuinely caused by the reported bug
        judge_result = self.judge.evaluate_failure(
            finding=finding,
            root_cause=root_cause,
            test_code=test_code,
            failure_trace=failure_trace,
            error_type=last_run_result.error_type,
        )

        is_candidate = judge_result.get("confirmed", True)
        judge_reasoning = judge_result.get("reasoning", "")

        is_plausible = False
        # If a reference fix patch is supplied, verify if candidate passes on the fix
        if is_candidate and reference_fix_patch:
            is_plausible = self._test_against_reference_fix(test_file_path, reference_fix_patch)

        return BRTClassification(
            is_candidate=is_candidate,
            is_plausible=is_plausible,
            failure_trace=failure_trace,
            failure_reason="Failed as expected on buggy code." if is_candidate else "Failure did not match bug root cause.",
            llm_judge_verdict=is_candidate,
            llm_judge_reasoning=judge_reasoning,
        )

    def _test_against_reference_fix(self, test_file_path: str, patch_diff: str) -> bool:
        """Executes the test against the reference fix in an ephemeral sandbox to confirm Plausible BRT status."""
        try:
            import re
            import shutil
            import subprocess
            import tempfile
            from autopatch.reproducer.sandbox_runner import SandboxedBRTRunner
            with tempfile.TemporaryDirectory() as td:
                sandbox_dir = Path(td)
                shutil.copytree(str(self.project_root), str(sandbox_dir), dirs_exist_ok=True)
                
                # Try git apply first
                subprocess.run(["git", "init"], cwd=str(sandbox_dir), capture_output=True)
                apply_res = subprocess.run(
                    ["git", "apply", "--whitespace=nowarn"],
                    input=patch_diff,
                    cwd=str(sandbox_dir),
                    text=True,
                    capture_output=True,
                )
                if apply_res.returncode != 0:
                    # Fallback to direct hunk line replacement
                    file_match = re.search(r"\+\+\+ [ab]/(.+)", patch_diff)
                    if file_match:
                        target_file = sandbox_dir / file_match.group(1).strip()
                        if target_file.is_file():
                            removed = [line[1:].strip() for line in patch_diff.splitlines() if line.startswith("-") and not line.startswith("---")]
                            added = [line[1:].strip() for line in patch_diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
                            content = target_file.read_text(encoding="utf-8")
                            for r, a in zip(removed, added):
                                new_lines = []
                                replaced = False
                                for line in content.splitlines():
                                    if not replaced and r in line:
                                        indent = line[:line.find(line.strip())]
                                        new_lines.append(indent + a)
                                        replaced = True
                                    else:
                                        new_lines.append(line)
                                content = "\n".join(new_lines) + "\n"
                            target_file.write_text(content, encoding="utf-8")
                
                runner = SandboxedBRTRunner(timeout_seconds=10)
                res = runner.run_test_file(sandbox_dir, test_file_path)
                return res.status == TestRunStatus.PASS
        except Exception as e:
            logger.debug(f"Reference fix test execution failed: {e}")
            return False

    def _build_agent_prompt(
        self,
        finding: Finding,
        root_cause: Optional[RootCause],
        steps: List[AgentStep],
        step_num: int,
        test_run_executed: bool,
        last_result: Optional[TestRunResult],
    ) -> str:
        prompt = (
            f"You are the AutoPatch Reproducer Agent (Step {step_num} of {self.max_steps}).\n"
            "Your task is to write a Bug Reproduction Test (BRT) that fails on the current buggy code.\n\n"
            f"--- BUG FINDING ---\n"
            f"File: {finding.file}:{finding.line_start}\n"
            f"Category: {finding.category.value}\n"
            f"Description: {finding.description}\n"
            f"Evidence: {finding.evidence}\n"
        )

        if root_cause:
            prompt += f"Root Cause: {root_cause.summary}\nTrigger: {root_cause.trigger_input_or_state}\n"

        prompt += "\nACTIONS:\n"
        prompt += "- cat(path): Inspect file contents.\n"
        prompt += "- code_search(text): Search for code snippets.\n"
        prompt += "- edit(path, change_description): Create a new test file with boundary cases.\n"
        prompt += "- run_tests(path): Run the test file in the sandbox (outputs Pass, Fail, or Error).\n"
        prompt += f"- finish(): Complete reproduction cycle (REJECTED until run_tests runs at least once). run_tests_executed={test_run_executed}.\n\n"

        if steps:
            prompt += "--- PREVIOUS STEPS ---\n"
            for s in steps[-4:]:
                prompt += f"Step {s.step_number}: {s.action}({s.parameters}) -> {s.output[:150]}\n"

        prompt += (
            "\nReturn your next action as JSON:\n"
            '{"action": "cat" | "code_search" | "edit" | "run_tests" | "finish", "parameters": {...}}\n'
        )
        return prompt

    def _parse_action(self, response_text: str) -> Dict[str, Any]:
        try:
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(response_text[start : end + 1])
        except Exception:
            pass
        return {"action": "finish", "parameters": {}}
