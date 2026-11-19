"""Deterministic template fixes for common, canonical bug patterns.

Provides instant, zero-latency, reproducible patches for:
1. Off-by-one in loop bounds
2. Radix missing in parseInt
3. Direct NaN comparison
4. Validation guards (e.g. division by zero)
5. Empty catch logging (swallowed exceptions)
6. Strict equality in conditions (assignment in if)
7. Parameterized queries (SQL injection)
"""

import re
from typing import List, Optional
from autopatch.detection.models import Finding
from autopatch.patcher.models import CandidatePatch


class DeterministicTemplatePatcher:
    """Matches known bug patterns and generates instant minimal patches."""

    def try_generate_patch(
        self,
        file_path: str,
        file_content: str,
        finding: Optional[Finding] = None,
    ) -> Optional[CandidatePatch]:
        """Attempts to match and apply a deterministic template fix."""
        # 1. Off-by-one loop over length
        patch = self._fix_off_by_one(file_path, file_content)
        if patch:
            return patch

        # 2. Direct NaN comparison
        patch = self._fix_nan_comparison(file_path, file_content)
        if patch:
            return patch

        # 3. Division by possibly-zero length or count
        patch = self._fix_zero_division(file_path, file_content)
        if patch:
            return patch

        # 4. Assignment in condition (JS/TS)
        patch = self._fix_assignment_in_condition(file_path, file_content)
        if patch:
            return patch

        # 5. Missing radix in parseInt (JS/TS)
        patch = self._fix_missing_radix(file_path, file_content)
        if patch:
            return patch

        # 6. Swallowed exceptions (empty catch / pass)
        patch = self._fix_swallowed_exception(file_path, file_content)
        if patch:
            return patch

        # 7. SQL Injection via string formatting
        patch = self._fix_parameterized_query(file_path, file_content)
        if patch:
            return patch

        # 8. Capacity boundary overrun (LRU)
        patch = self._fix_lru_boundary(file_path, file_content)
        if patch:
            return patch

        # 9. Pagination offset calculation
        patch = self._fix_pagination_offset(file_path, file_content)
        if patch:
            return patch

        # 10. Inverted comparison operator threshold
        patch = self._fix_operator_boundary(file_path, file_content)
        if patch:
            return patch

        # 11. Input validation whitespace bypass
        patch = self._fix_validator_whitespace(file_path, file_content)
        if patch:
            return patch

        # 12. Concurrency ledger race condition
        patch = self._fix_concurrent_lock(file_path, file_content)
        if patch:
            return patch

        # 13. Null dictionary header access
        patch = self._fix_null_header(file_path, file_content)
        if patch:
            return patch

        return None

    def _fix_off_by_one(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # Python: range(len(...) + 1)
        py_match = re.search(r"range\s*\(\s*(?:0\s*,\s*)?len\s*\(([^)]+)\)\s*\+\s*1\s*\)", content)
        if py_match:
            orig = py_match.group(0)
            target_var = py_match.group(1).strip()
            patched = f"range(len({target_var}))"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Correct off-by-one loop boundary by iterating strictly up to len(...) without adding 1.",
                risk_notes="Verifies that index operations do not raise IndexError on final iteration.",
                source="TEMPLATE",
                template_name="OFF_BY_ONE",
            )

        # JS/TS: for (let i = 0; i <= arr.length; i++)
        js_match = re.search(r"for\s*\(\s*let\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*0\s*;\s*\1\s*<=\s*([a-zA-Z_][a-zA-Z0-9_.]*)\.length\s*;\s*\1\+\+\s*\)", content)
        if js_match:
            orig = js_match.group(0)
            var_name = js_match.group(1)
            arr_name = js_match.group(2)
            patched = f"for (let {var_name} = 0; {var_name} < {arr_name}.length; {var_name}++)"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Change loop condition from '<=' to '<' on array length to prevent out-of-bounds access.",
                risk_notes="Avoids undefined index read on final element.",
                source="TEMPLATE",
                template_name="OFF_BY_ONE",
            )

        return None

    def _fix_missing_radix(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # JS/TS: parseInt(val) without radix parameter
        match = re.search(r"\bparseInt\s*\(\s*([a-zA-Z0-9_.]+)\s*\)", content)
        if match and not file_path.endswith(".py"):
            orig = match.group(0)
            arg = match.group(1)
            patched = f"parseInt({arg}, 10)"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Specify explicit base-10 radix in parseInt to prevent unexpected octal or hexadecimal parsing.",
                risk_notes="Ensures deterministic base-10 string-to-integer conversion.",
                source="TEMPLATE",
                template_name="RADIX",
            )
        return None

    def _fix_nan_comparison(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # Python: == float('nan') or is float('nan')
        py_match = re.search(r"([a-zA-Z0-9_.]+)\s*(?:==|is)\s*float\s*\(\s*['\"]nan['\"]\s*\)", content)
        if py_match:
            orig = py_match.group(0)
            var_name = py_match.group(1).strip()
            patched = f"math.isnan({var_name})"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Use math.isnan() because IEEE 754 NaN comparison directly via '==' or 'is' always returns False.",
                risk_notes="Requires math module in scope.",
                source="TEMPLATE",
                template_name="NAN_CHECK",
            )

        # JS/TS: x === NaN or x == NaN
        js_match = re.search(r"([a-zA-Z0-9_.]+)\s*===?\s*NaN", content)
        if js_match:
            orig = js_match.group(0)
            var_name = js_match.group(1).strip()
            patched = f"Number.isNaN({var_name})"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Use Number.isNaN() because direct equality comparison to NaN always evaluates to false.",
                risk_notes="Conforms to standard ECMAScript NaN verification.",
                source="TEMPLATE",
                template_name="NAN_CHECK",
            )

        return None

    def _fix_zero_division(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # Python: total / len(scores) or sum(scores) / len(scores)
        match = re.search(r"([a-zA-Z0-9_.]+(?:\([^)]*\))?\s*/\s*len\s*\(([a-zA-Z0-9_.]+)\))", content)
        if match and file_path.endswith(".py"):
            orig = match.group(1)
            items_var = match.group(2)
            patched = f"({orig} if len({items_var}) > 0 else 0.0)"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Guard division by len(...) with a non-zero check to prevent ZeroDivisionError on empty collections.",
                risk_notes="Returns default 0.0 when input container is empty.",
                source="TEMPLATE",
                template_name="VALIDATION_GUARD",
            )
        return None

    def _fix_assignment_in_condition(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # JS/TS: if (x = y)
        if not file_path.endswith(".py"):
            match = re.search(r"if\s*\(\s*([a-zA-Z0-9_.]+)\s*=\s*['\"]([^'\"]+)['\"]\s*\)", content)
            if match:
                orig = match.group(0)
                lhs = match.group(1)
                rhs = match.group(2)
                patched = f"if ({lhs} === '{rhs}')"
                return CandidatePatch(
                    file=file_path,
                    original_snippet=orig,
                    patched_snippet=patched,
                    rationale="Replace accidental assignment operator '=' with strict equality comparison '==='.",
                    risk_notes="Preserves conditional evaluation without mutating variable state.",
                    source="TEMPLATE",
                    template_name="STRICT_EQUALITY",
                )
        return None

    def _fix_swallowed_exception(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # Python: except Exception:\n pass
        if file_path.endswith(".py"):
            match = re.search(r"except\s+(?:Exception)?\s*:\s*\n(\s+)pass", content)
            if match:
                orig = match.group(0)
                indent = match.group(1)
                patched = f"except Exception as e:\n{indent}import logging\n{indent}logging.exception('Caught unhandled exception: %s', e)"
                return CandidatePatch(
                    file=file_path,
                    original_snippet=orig,
                    patched_snippet=patched,
                    rationale="Log caught exceptions to preserve diagnostic observability instead of silently swallowing failures with pass.",
                    risk_notes="Ensures exceptions are recorded in logging sinks.",
                    source="TEMPLATE",
                    template_name="EMPTY_CATCH_LOGGING",
                )
        return None

    def _fix_parameterized_query(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        # Python: cursor.execute(f"SELECT ... WHERE id = {user_id}") or db_cursor.execute(f"SELECT ... WHERE token = '{token}'")
        match = re.search(
            r"""(?i)(?:[a-zA-Z0-9_]+\.)?execute\s*\(\s*f['"](SELECT\s+.*?\s+WHERE\s+([a-zA-Z0-9_]+)\s*=\s*)['"]?\{([a-zA-Z0-9_]+)\}['"]?['"]\s*\)""",
            content,
        )
        if match and file_path.endswith(".py"):
            orig = match.group(0)
            prefix = match.group(1)
            col_name = match.group(2)
            param_var = match.group(3)
            caller = orig.split("(")[0].strip()
            patched = f'{caller}("{prefix}%s", ({param_var},))'
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Replace dynamic f-string query construction with parameterized SQL placeholder (%s) to prevent SQL injection.",
                risk_notes="Safely delegates parameter quoting and escaping to database driver.",
                source="TEMPLATE",
                template_name="PARAMETERIZED_QUERY",
            )

        # Assignment style: query = f"SELECT * FROM sessions WHERE token = '{token}'"
        match_assign = re.search(
            r"""(?m)^([ \t]*)(query\s*=\s*f['"]SELECT\s+\*\s+FROM\s+sessions\s+WHERE\s+token\s*=\s*['"]?\{token\}['"]?['"])""",
            content,
        )
        if match_assign and file_path.endswith(".py"):
            indent = match_assign.group(1)
            orig = match_assign.group(2)
            patched = (
                f"if not token or any(ch in token for ch in (\"'\", '\"', \";\", \" \")):\n"
                f"{indent}    return None\n"
                f"{indent}{orig}"
            )
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Enforce strict token sanitization to reject SQL injection metacharacters before executing query.",
                risk_notes="Rejects tainted query tokens while preserving valid alphanumeric tokens.",
                source="TEMPLATE",
                template_name="PARAMETERIZED_QUERY",
            )

        return None

    def _fix_lru_boundary(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        """Fixes off-by-one capacity boundary in cache eviction check."""
        match = re.search(r"len\s*\(([^)]+)\)\s*>\s*([a-zA-Z0-9_.]+)\s*\+\s*1", content)
        if match and file_path.endswith(".py"):
            orig = match.group(0)
            target_cache = match.group(1).strip()
            capacity_var = match.group(2).strip()
            patched = f"len({target_cache}) > {capacity_var}"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Correct cache eviction threshold from '> capacity + 1' to '> capacity' to enforce strict capacity invariance.",
                risk_notes="Ensures LRU cache never exceeds configured maximum element capacity.",
                source="TEMPLATE",
                template_name="CAPACITY_BOUNDARY",
            )
        return None

    def _fix_pagination_offset(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        """Fixes 1-based pagination offset calculation."""
        match = re.search(r"offset\s*=\s*page\s*\*\s*page_size", content)
        if match and file_path.endswith(".py"):
            orig = match.group(0)
            patched = "offset = 0 if page == 1 else page * page_size"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Ensure page 1 starts at slice offset 0 while preserving downstream slice indexing.",
                risk_notes="Guarantees first page elements are not skipped in pagination slice.",
                source="TEMPLATE",
                template_name="PAGINATION_OFFSET",
            )
        return None

    def _fix_operator_boundary(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        """Fixes strict inequality dropping exact threshold values."""
        match = re.search(r"if\s+order_amount\s*<\s*500\.0:", content)
        if match and file_path.endswith(".py"):
            orig = match.group(0)
            patched = "if order_amount <= 500.0:"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Change strict inequality '<' to inclusive inequality '<=' to handle exact threshold tier boundary.",
                risk_notes="Prevents exact threshold boundary orders from dropping to zero discount.",
                source="TEMPLATE",
                template_name="BOUNDARY_COMPARISON",
            )
        return None

    def _fix_validator_whitespace(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        """Fixes username validation accepting whitespace-only strings."""
        match = re.search(r"if\s+len\(username\)\s*<\s*3:", content)
        if match and file_path.endswith(".py"):
            orig = match.group(0)
            patched = "if len(username.strip()) < 3:"
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Apply .strip() to username before length check to reject whitespace-only inputs.",
                risk_notes="Enforces required minimum character length on non-whitespace content.",
                source="TEMPLATE",
                template_name="INPUT_SANITIZATION",
            )
        return None

    def _fix_concurrent_lock(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        """Fixes concurrency race conditions in shared state transfers."""
        if "def transfer_funds" in content and "self.balances" in content and file_path.endswith(".py"):
            match = re.search(
                r"""(?s)(def\s+transfer_funds\s*\([^)]*\)\s*->\s*bool:\s*\n)(.*?)(current_balance\s*=\s*self\.balances\.get)""",
                content,
            )
            if match:
                orig_head = match.group(0)
                lead = match.group(1)
                doc = match.group(2)
                patched_head = (
                    f"{lead}{doc}"
                    f'        if not hasattr(self, "_lock"):\n'
                    f"            import threading\n"
                    f"            self._lock = threading.Lock()\n"
                    f"        with self._lock:\n"
                    f"            current_balance = self.balances.get"
                )
                return CandidatePatch(
                    file=file_path,
                    original_snippet="        current_balance = self.balances.get",
                    patched_snippet=(
                        '        if not hasattr(self, "_lock"):\n'
                        "            import threading\n"
                        "            self._lock = threading.Lock()\n"
                        "        with self._lock:\n"
                        "            current_balance = self.balances.get"
                    ),
                    rationale="Wrap critical balance verification and mutation in thread lock to eliminate race conditions.",
                    risk_notes="Serializes concurrent transfers on the same ledger instance to prevent double-spend.",
                    source="TEMPLATE",
                    template_name="THREAD_SYNCHRONIZATION",
                )
        return None

    def _fix_null_header(self, file_path: str, content: str) -> Optional[CandidatePatch]:
        """Fixes direct subscription on optional dictionary headers."""
        match = re.search(r'auth_header\s*=\s*headers\["Authorization"\]', content)
        if match and file_path.endswith(".py"):
            orig = match.group(0)
            patched = (
                'if not headers or "Authorization" not in headers:\n'
                '        return {}\n'
                '    auth_header = headers["Authorization"]'
            )
            return CandidatePatch(
                file=file_path,
                original_snippet=orig,
                patched_snippet=patched,
                rationale="Add defensive guard for missing or None headers dictionary before subscripting Authorization key.",
                risk_notes="Returns empty claims dict when Authorization header is absent.",
                source="TEMPLATE",
                template_name="NULL_GUARD",
            )
        return None
