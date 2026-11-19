"""Patcher Agent synthesizing minimal candidate patches with retry loop and template fast-path."""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from autopatch.core.exceptions import TestModificationForbiddenError
from autopatch.core.logging import get_logger
from autopatch.core.models import TEST_FILE_PATTERNS
from autopatch.locator.models import RootCause
from autopatch.patcher.diff_utils import (
    generate_unified_diff,
    validate_minimal_diff_rules,
    verify_patch_applies_cleanly,
)
from autopatch.patcher.models import CandidatePatch, PatchGenerationResult
from autopatch.patcher.templates import DeterministicTemplatePatcher
from autopatch.reproducer.models import ReproductionResult
from autopatch.security.redaction import assert_clean_prompt, redact_secrets
from autopatch.security.prompt_defense import (
    sanitize_untrusted_code,
    build_hardened_system_prompt,
)
from autopatch.security.privacy_mode import PrivacyGuard

logger = get_logger(__name__)

MAX_RETRIES = 3


class PatcherAgent:
    """Autonomous agent synthesizing minimal bug repair patches."""

    def __init__(
        self,
        project_root: Path,
        llm_client: Callable[[str], str],
        template_patcher: Optional[DeterministicTemplatePatcher] = None,
        max_retries: int = MAX_RETRIES,
    ):
        self.project_root = project_root.resolve()
        self.llm_client = llm_client
        self.template_patcher = template_patcher or DeterministicTemplatePatcher()
        self.max_retries = min(max_retries, MAX_RETRIES)

    def generate_candidate_patches(
        self,
        root_cause: RootCause,
        plausible_brt: Optional[ReproductionResult] = None,
        max_candidates: int = 3,
    ) -> PatchGenerationResult:
        """Generates up to N candidate patches, prioritizing deterministic templates and LLM retries."""
        candidates: List[CandidatePatch] = []
        bug_id = str(root_cause.buggy_locations[0].method_name if root_cause.buggy_locations else "unknown_bug")

        # 1. Template Fast-Path: check deterministic templates first
        for loc in root_cause.buggy_locations:
            full_path = (self.project_root / loc.file).resolve()
            if full_path.is_file():
                content = full_path.read_text(encoding="utf-8", errors="replace")
                template_patch = self.template_patcher.try_generate_patch(loc.file, content)
                if template_patch:
                    # Enforce minimal-diff and clean application
                    is_clean, err = verify_patch_applies_cleanly(
                        self.project_root,
                        template_patch.file,
                        template_patch.original_snippet,
                        template_patch.patched_snippet,
                    )
                    template_patch.applies_cleanly = is_clean
                    if err:
                        template_patch.validation_errors.append(err)

                    patched_content = content.replace(
                        template_patch.original_snippet, template_patch.patched_snippet, 1
                    )
                    template_patch.unified_diff = generate_unified_diff(
                        loc.file, content, patched_content
                    )
                    template_patch.lines_added = len(template_patch.patched_snippet.splitlines())
                    template_patch.lines_deleted = len(template_patch.original_snippet.splitlines())
                    candidates.append(template_patch)
                    if len(candidates) >= max_candidates:
                        break

        # 2. If templates already provided candidates, return if sufficient or if Privacy Mode is active
        if len(candidates) >= max_candidates or PrivacyGuard.is_privacy_mode_active():
            best_patch = candidates[0] if candidates else None
            return PatchGenerationResult(
                bug_id=bug_id,
                candidate_patches=candidates[:max_candidates],
                retry_count=0,
                best_attempt=best_patch,
                all_applied_cleanly=all(c.applies_cleanly for c in candidates) if candidates else False,
                summary=f"Synthesized {len(candidates)} candidate patches via deterministic templates (Privacy Mode / Fast-path).",
            )

        # 3. LLM Synthesis with Retry Loop (max 3 retries)
        retry_count = 0
        last_error = ""
        best_attempt: Optional[CandidatePatch] = None

        while len(candidates) < max_candidates and retry_count <= self.max_retries:
            prompt = self._build_patch_prompt(
                root_cause=root_cause,
                plausible_brt=plausible_brt,
                retry_error=last_error if retry_count > 0 else None,
            )

            sanitized_prompt, _ = redact_secrets(prompt)
            assert_clean_prompt(sanitized_prompt)

            raw_response = self.llm_client(sanitized_prompt)
            parsed_patch, parse_err = self._parse_strict_patch(raw_response)

            if parse_err:
                retry_count += 1
                last_error = f"Patch parsing error: {parse_err}. You must use strict tags: <file>path</file><original>exact lines</original><patched>replacement lines</patched>"
                continue

            # Validate patch rules
            val_ok, val_err = self._validate_candidate_patch(parsed_patch, root_cause)
            if not val_ok:
                best_attempt = parsed_patch
                retry_count += 1
                last_error = f"Validation failed: {val_err}. Please regenerate a minimal, syntactically clean patch."
                continue

            # Success: Candidate applies cleanly
            candidates.append(parsed_patch)
            best_attempt = parsed_patch
            break

        return PatchGenerationResult(
            bug_id=bug_id,
            candidate_patches=candidates,
            retry_count=retry_count,
            best_attempt=best_attempt or (candidates[0] if candidates else None),
            all_applied_cleanly=all(c.applies_cleanly for c in candidates) if candidates else False,
            summary=f"Generated {len(candidates)} candidate patch(es) across {retry_count} retries.",
        )

    def _validate_candidate_patch(
        self, patch: CandidatePatch, root_cause: RootCause
    ) -> Tuple[bool, Optional[str]]:
        """Verifies candidate patch against all minimal-diff, test-protection, and syntax invariants."""
        # Check 1: Rule 3 - Never modify test files
        for pattern in TEST_FILE_PATTERNS:
            if pattern.search(patch.file):
                raise TestModificationForbiddenError(
                    f"Candidate patch attempted to modify test file '{patch.file}'."
                )

        full_path = (self.project_root / patch.file).resolve()
        if not full_path.is_file():
            return False, f"Target file '{patch.file}' does not exist in workspace."

        content = full_path.read_text(encoding="utf-8", errors="replace")

        # Check 2: Original snippet must exist in target file
        if patch.original_snippet not in content:
            return False, f"Original snippet does not match exact content of '{patch.file}'."

        # Check 3: Minimal diff rules (no whitespace noise, no assertion deletion)
        min_ok, violations, flags_sig = validate_minimal_diff_rules(
            patch.original_snippet, patch.patched_snippet, patch.file
        )
        patch.flags_signature_change = flags_sig
        if not min_ok:
            return False, "; ".join(violations)

        # Check 4: Syntax and clean application check
        is_clean, err = verify_patch_applies_cleanly(
            self.project_root, patch.file, patch.original_snippet, patch.patched_snippet
        )
        patch.applies_cleanly = is_clean
        if not is_clean:
            return False, err

        # Generate unified diff
        patched_content = content.replace(patch.original_snippet, patch.patched_snippet, 1)
        patch.unified_diff = generate_unified_diff(patch.file, content, patched_content)
        patch.lines_added = len(patch.patched_snippet.splitlines())
        patch.lines_deleted = len(patch.original_snippet.splitlines())

        return True, None

    def _build_patch_prompt(
        self,
        root_cause: RootCause,
        plausible_brt: Optional[ReproductionResult],
        retry_error: Optional[str],
    ) -> str:
        base_instructions = (
            "You are the AutoPatch Patcher Agent.\n"
            "Generate a minimal, surgical source code patch in the exact required XML tag format.\n\n"
            f"--- ROOT CAUSE ---\n"
            f"Summary: {root_cause.summary}\n"
            f"Trigger: {root_cause.trigger_input_or_state}\n"
            f"Causal Chain: {' -> '.join(root_cause.causal_chain)}\n"
        )
        prompt = build_hardened_system_prompt(base_instructions)

        prompt += "\n--- BUGGY METHOD LOCATIONS ---\n"
        for loc in root_cause.buggy_locations:
            full_path = (self.project_root / loc.file).resolve()
            method_source = ""
            if full_path.is_file():
                try:
                    lines = full_path.read_text(encoding="utf-8").splitlines()
                    start = max(0, loc.line_start - 1)
                    end = min(len(lines), loc.line_end)
                    method_source = "\n".join(lines[start:end])
                except Exception:
                    pass

            quarantined_source = sanitize_untrusted_code(method_source, loc.file)
            prompt += (
                f"File: {loc.file} | Method: {loc.method_name} (Lines {loc.line_start}-{loc.line_end})\n"
                f"{quarantined_source}\n\n"
            )

        if plausible_brt and plausible_brt.test_code:
            quarantined_test = sanitize_untrusted_code(plausible_brt.test_code, plausible_brt.test_file_path)
            prompt += (
                f"--- PLAUSIBLE REPRODUCTION TEST (BRT) ---\n"
                f"File: {plausible_brt.test_file_path}\n"
                f"{quarantined_test}\n\n"
            )

        if retry_error:
            prompt += (
                f"\n--- PREVIOUS ATTEMPT FAILED WITH ERROR ---\n"
                f"{retry_error}\n"
                "Fix the error and regenerate the patch with exact line matching.\n\n"
            )

        prompt += (
            "CRITICAL RULES:\n"
            "1. Output format MUST be strictly:\n"
            "<file>path</file>\n"
            "<original>\nexact lines to be replaced\n</original>\n"
            "<patched>\nreplacement lines\n</patched>\n"
            "Rationale: plain-language explanation tied to root cause\n"
            "Risk Notes: potential side effects or None\n\n"
            "2. Minimal diff: change only what the root cause requires. Never reformat unrelated code.\n"
            "3. NEVER modify existing test files.\n"
        )
        return prompt

    def _parse_strict_patch(self, raw_text: str) -> Tuple[Optional[CandidatePatch], Optional[str]]:
        """Parses output matching <file>...</file><original>...</original><patched>...</patched>."""
        file_match = re.search(r"<file>(.*?)</file>", raw_text, re.DOTALL)
        orig_match = re.search(r"<original>(.*?)</original>", raw_text, re.DOTALL)
        patch_match = re.search(r"<patched>(.*?)</patched>", raw_text, re.DOTALL)

        if not file_match:
            return None, "Missing <file>...</file> tags"
        if not orig_match:
            return None, "Missing <original>...</original> tags"
        if not patch_match:
            return None, "Missing <patched>...</patched> tags"

        target_file = file_match.group(1).strip()
        original = orig_match.group(1)
        patched = patch_match.group(1)

        # Strip only leading/trailing blank line if present from tags
        if original.startswith("\n"):
            original = original[1:]
        if original.endswith("\n"):
            original = original[:-1]
        if patched.startswith("\n"):
            patched = patched[1:]
        if patched.endswith("\n"):
            patched = patched[:-1]

        # Extract rationale & risk notes if provided
        rationale_match = re.search(r"Rationale:\s*([^\n]+)", raw_text, re.IGNORECASE)
        risk_match = re.search(r"Risk Notes:\s*([^\n]+)", raw_text, re.IGNORECASE)

        rationale = rationale_match.group(1).strip() if rationale_match else "Surgical bug fix addressing root cause."
        risk_notes = risk_match.group(1).strip() if risk_match else "Low risk: localized fix."

        try:
            candidate = CandidatePatch(
                file=target_file,
                original_snippet=original,
                patched_snippet=patched,
                rationale=rationale,
                risk_notes=risk_notes,
                source="LLM",
            )
            return candidate, None
        except Exception as e:
            return None, str(e)
