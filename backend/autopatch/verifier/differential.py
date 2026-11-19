"""Differential probe execution checking behavioral invariance on unrelated functions.

Calls unrelated public functions with deterministic probe inputs on both baseline
and patched snapshots to prove no collateral behavior drift occurred.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from autopatch.verifier.models import DifferentialCheckResult


class DifferentialChecker:
    """Executes differential probing across untouched public functions."""

    def run_differential_check(
        self,
        baseline_snapshot: Path,
        patched_snapshot: Path,
        affected_files: List[str],
        max_probes: int = 5,
    ) -> DifferentialCheckResult:
        """Compares return values of untouched public functions between baseline and patched snapshots."""
        untouched_files = self._find_untouched_python_files(baseline_snapshot, affected_files)
        if not untouched_files:
            return DifferentialCheckResult(
                probed_functions=[],
                divergent=False,
                divergent_details=["No untouched public functions eligible for probing."],
            )

        probed_funcs: List[str] = []
        baseline_outputs: Dict[str, Any] = {}
        patched_outputs: Dict[str, Any] = {}
        divergences: List[str] = []

        for rel_file in untouched_files[:max_probes]:
            funcs = self._extract_public_top_level_functions(baseline_snapshot / rel_file)
            for fn_name in funcs[:2]:
                func_id = f"{rel_file}:{fn_name}"
                probed_funcs.append(func_id)

                # Execute on baseline
                base_val, base_err = self._probe_function(baseline_snapshot, rel_file, fn_name)
                # Execute on patched
                patch_val, patch_err = self._probe_function(patched_snapshot, rel_file, fn_name)

                baseline_outputs[func_id] = base_val if not base_err else f"ERROR: {base_err}"
                patched_outputs[func_id] = patch_val if not patch_err else f"ERROR: {patch_err}"

                # Compare results
                if base_val != patch_val or base_err != patch_err:
                    divergences.append(
                        f"Divergence in {func_id}: baseline={base_val!r} vs patched={patch_val!r}"
                    )

        return DifferentialCheckResult(
            probed_functions=probed_funcs,
            baseline_outputs=baseline_outputs,
            patched_outputs=patched_outputs,
            divergent=len(divergences) > 0,
            divergent_details=divergences,
        )

    def _find_untouched_python_files(self, root: Path, affected: List[str]) -> List[str]:
        affected_set = set(affected)
        untouched = []
        for p in root.rglob("*.py"):
            rel = str(p.relative_to(root))
            if (
                rel not in affected_set
                and not any(x in rel for x in ["test", "setup.py", "conftest.py"])
                and not p.name.startswith(".")
            ):
                untouched.append(rel)
        return sorted(untouched)

    def _extract_public_top_level_functions(self, file_path: Path) -> List[str]:
        if not file_path.is_file():
            return []
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
            return [
                node.name
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
            ]
        except Exception:
            return []

    def _probe_function(self, workspace: Path, rel_file: str, fn_name: str) -> tuple[Any, Optional[str]]:
        """Runs a probing harness in a subprocess to safely invoke the function."""
        module_path = rel_file.replace("/", ".").rstrip(".py")
        harness = f"""
import sys, json
try:
    from {module_path} import {fn_name}
    import inspect
    sig = inspect.signature({fn_name})
    # Supply dummy arguments based on parameter count
    args = [42 for _ in sig.parameters]
    res = {fn_name}(*args)
    print(json.dumps({{"res": str(res)}}))
except Exception as e:
    print(json.dumps({{"err": str(e)}}))
"""
        try:
            proc = subprocess.run(
                [sys.executable, "-c", harness],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            out = proc.stdout.strip()
            data = json.loads(out)
            return data.get("res"), data.get("err")
        except Exception as e:
            return None, str(e)
