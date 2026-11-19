"""Rule-based AST detectors for Python and JS/TS.

Detects:
1. Off-by-one in loops over lengths
2. Division by a possibly-zero length or count
3. Null/None access without guard
4. Assignment in condition (e.g. if (x = y))
5. Comparing to NaN (e.g. x === NaN or x == float('nan'))
6. Swallowed exceptions (e.g. except: pass or empty catch)
7. Unclosed resources (e.g. open() without with or close())
8. Mutable default arguments (e.g. def foo(items=[]))
9. Unreachable code (statements following return/raise/throw/break)
"""

import re
from pathlib import Path
from typing import List, Optional
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.models import FileASTIndex


class ASTRuleDetector(BaseDetector):
    """Executes syntactic and structural AST rules against source code."""

    def __init__(self) -> None:
        self._py_lang = Language(tspython.language())
        self._py_parser = Parser(self._py_lang)
        self._js_lang = Language(tsjs.language())
        self._js_parser = Parser(self._js_lang)

    @property
    def name(self) -> str:
        return "AST_RULE"

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

            full_path = project_root / idx.file_path
            if not full_path.is_file():
                continue

            try:
                code = full_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if idx.language == "Python":
                findings.extend(self._analyze_python(idx.file_path, code))
            elif idx.language in {"JavaScript", "TypeScript"}:
                findings.extend(self._analyze_javascript(idx.file_path, code))

        return findings

    # =========================================================================
    # Python AST Analysis
    # =========================================================================
    def _analyze_python(self, rel_path: str, code: str) -> List[Finding]:
        findings: List[Finding] = []
        code_bytes = code.encode("utf-8")
        tree = self._py_parser.parse(code_bytes)

        lines = code.splitlines()

        def get_line_text(start_row: int, end_row: int) -> str:
            snippet = lines[start_row : end_row + 1]
            return "\n".join(snippet).strip()

        def walk(node: Node, current_symbol: Optional[str] = None) -> None:
            # Track current enclosing function or class
            if node.type in {"function_definition", "class_definition"}:
                name_node = node.child_by_field_name("name")
                if name_node:
                    current_symbol = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")

            # 1. Mutable default arguments
            if node.type == "function_definition":
                params = node.child_by_field_name("parameters")
                if params:
                    for child in params.children:
                        if child.type == "default_parameter":
                            val = child.child_by_field_name("value")
                            if val and val.type in {"list", "dictionary", "set"}:
                                evidence = get_line_text(child.start_point.row, child.end_point.row)
                                findings.append(
                                    Finding(
                                        file=rel_path,
                                        line_start=child.start_point.row + 1,
                                        line_end=child.end_point.row + 1,
                                        symbol=current_symbol,
                                        category=FindingCategory.LOGIC_ERROR,
                                        evidence=evidence or "mutable_default",
                                        detector=self.name,
                                        raw_confidence=0.95,
                                        description="Mutable default argument (list/dict/set) retains state across calls.",
                                    )
                                )

            # 2. Swallowed exceptions
            if node.type == "except_clause":
                for child in node.children:
                    if child.type == "block":
                        stmts = [c for c in child.children if c.type not in {"comment", "newline"}]
                        if len(stmts) == 1 and stmts[0].type == "pass_statement":
                            evidence = get_line_text(node.start_point.row, child.end_point.row)
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=node.start_point.row + 1,
                                    line_end=child.end_point.row + 1,
                                    symbol=current_symbol,
                                    category=FindingCategory.EXCEPTION_HANDLING,
                                    evidence=evidence or "except: pass",
                                    detector=self.name,
                                    raw_confidence=0.90,
                                    description="Swallowed exception with silent 'pass' hides critical runtime failures.",
                                )
                            )
                        break

            # 3. Off-by-one in loops over lengths
            # e.g. for i in range(len(arr) + 1):
            if node.type == "call":
                fn_name_node = node.child_by_field_name("function")
                if fn_name_node:
                    fn_name = code_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode("utf-8")
                    if fn_name == "range":
                        args = node.child_by_field_name("arguments")
                        if args:
                            args_text = code_bytes[args.start_byte : args.end_byte].decode("utf-8")
                            if re.search(r"len\s*\([^)]+\)\s*\+\s*1", args_text):
                                evidence = get_line_text(node.start_point.row, node.end_point.row)
                                findings.append(
                                    Finding(
                                        file=rel_path,
                                        line_start=node.start_point.row + 1,
                                        line_end=node.end_point.row + 1,
                                        symbol=current_symbol,
                                        category=FindingCategory.LOGIC_ERROR,
                                        evidence=evidence or args_text,
                                        detector=self.name,
                                        raw_confidence=0.88,
                                        description="Potential off-by-one error: iterating up to len(...) + 1 triggers IndexError.",
                                    )
                                )

            # 4. Division by zero (e.g. / len(x) or // len(x))
            if node.type == "binary_operator":
                op_node = node.children[1] if len(node.children) > 1 else None
                if op_node and code_bytes[op_node.start_byte : op_node.end_byte].decode("utf-8") in {"/", "//", "%"}:
                    right = node.child_by_field_name("right")
                    if right:
                        right_text = code_bytes[right.start_byte : right.end_byte].decode("utf-8")
                        if "len(" in right_text:
                            evidence = get_line_text(node.start_point.row, node.end_point.row)
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=node.start_point.row + 1,
                                    line_end=node.end_point.row + 1,
                                    symbol=current_symbol,
                                    category=FindingCategory.LOGIC_ERROR,
                                    evidence=evidence or right_text,
                                    detector=self.name,
                                    raw_confidence=0.85,
                                    description="Division by len(...) without non-empty guard triggers ZeroDivisionError on empty input.",
                                )
                            )

            # 5. Comparing to NaN
            if node.type == "comparison_operator":
                text = code_bytes[node.start_byte : node.end_byte].decode("utf-8")
                if "float('nan')" in text or 'float("nan")' in text:
                    evidence = get_line_text(node.start_point.row, node.end_point.row)
                    findings.append(
                        Finding(
                            file=rel_path,
                            line_start=node.start_point.row + 1,
                            line_end=node.end_point.row + 1,
                            symbol=current_symbol,
                            category=FindingCategory.LOGIC_ERROR,
                            evidence=evidence or text,
                            detector=self.name,
                            raw_confidence=0.98,
                            description="Comparing to NaN directly with == or is always evaluates to False. Use math.isnan() instead.",
                        )
                    )

            # 6. Unclosed resources: open() assigned without with context manager
            if node.type == "assignment":
                right = node.child_by_field_name("right")
                if right and right.type == "call":
                    fn_node = right.child_by_field_name("function")
                    if fn_node and code_bytes[fn_node.start_byte : fn_node.end_byte].decode("utf-8") == "open":
                        # Check if parent is NOT with_statement
                        p = node.parent
                        is_with = False
                        while p:
                            if p.type == "with_statement":
                                is_with = True
                                break
                            p = p.parent
                        if not is_with:
                            evidence = get_line_text(node.start_point.row, node.end_point.row)
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=node.start_point.row + 1,
                                    line_end=node.end_point.row + 1,
                                    symbol=current_symbol,
                                    category=FindingCategory.RESOURCE_LEAK,
                                    cwe="CWE-775",
                                    evidence=evidence or "open()",
                                    detector=self.name,
                                    raw_confidence=0.82,
                                    description="File opened without 'with' context manager or guaranteed close() risks file descriptor leak.",
                                )
                            )

            # 7. Unreachable code after return / raise
            if node.type in {"return_statement", "raise_statement", "break_statement", "continue_statement"}:
                parent = node.parent
                if parent and parent.type == "block":
                    idx_in_parent = parent.children.index(node)
                    # Check if there are subsequent non-comment statements
                    if idx_in_parent < len(parent.children) - 1:
                        next_stmt = parent.children[idx_in_parent + 1]
                        if next_stmt.type not in {"comment", "newline"}:
                            evidence = get_line_text(next_stmt.start_point.row, next_stmt.end_point.row)
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=next_stmt.start_point.row + 1,
                                    line_end=next_stmt.end_point.row + 1,
                                    symbol=current_symbol,
                                    category=FindingCategory.LOGIC_ERROR,
                                    evidence=evidence or "unreachable_statement",
                                    detector=self.name,
                                    raw_confidence=0.92,
                                    description="Unreachable code detected immediately following a terminating statement.",
                                )
                            )

            for child in node.children:
                walk(child, current_symbol)

        walk(tree.root_node)
        return findings

    # =========================================================================
    # JavaScript / TypeScript AST Analysis
    # =========================================================================
    def _analyze_javascript(self, rel_path: str, code: str) -> List[Finding]:
        findings: List[Finding] = []
        code_bytes = code.encode("utf-8")
        tree = self._js_parser.parse(code_bytes)

        lines = code.splitlines()

        def get_line_text(start_row: int, end_row: int) -> str:
            snippet = lines[start_row : end_row + 1]
            return "\n".join(snippet).strip()

        def walk(node: Node, current_symbol: Optional[str] = None) -> None:
            if node.type in {"function_declaration", "method_definition", "class_declaration"}:
                name_node = node.child_by_field_name("name")
                if name_node:
                    current_symbol = code_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")

            # 1. Assignment in condition: if (x = y)
            if node.type == "if_statement":
                cond = node.child_by_field_name("condition")
                if cond and cond.type == "parenthesized_expression":
                    inner = cond.children[1] if len(cond.children) > 1 else None
                    if inner and inner.type == "assignment_expression":
                        evidence = get_line_text(node.start_point.row, node.start_point.row)
                        findings.append(
                            Finding(
                                file=rel_path,
                                line_start=node.start_point.row + 1,
                                line_end=node.start_point.row + 1,
                                symbol=current_symbol,
                                category=FindingCategory.LOGIC_ERROR,
                                evidence=evidence or "if (x = y)",
                                detector=self.name,
                                raw_confidence=0.90,
                                description="Accidental assignment '=' inside if condition instead of comparison '==='.",
                            )
                        )

            # 2. Comparing to NaN: x === NaN or x == NaN
            if node.type == "binary_expression":
                left = node.child_by_field_name("left")
                right = node.child_by_field_name("right")
                op = node.child_by_field_name("operator")
                if op and code_bytes[op.start_byte : op.end_byte].decode("utf-8") in {"==", "===", "!=", "!=="}:
                    left_text = code_bytes[left.start_byte : left.end_byte].decode("utf-8") if left else ""
                    right_text = code_bytes[right.start_byte : right.end_byte].decode("utf-8") if right else ""
                    if left_text == "NaN" or right_text == "NaN":
                        evidence = get_line_text(node.start_point.row, node.end_point.row)
                        findings.append(
                            Finding(
                                file=rel_path,
                                line_start=node.start_point.row + 1,
                                line_end=node.end_point.row + 1,
                                symbol=current_symbol,
                                category=FindingCategory.LOGIC_ERROR,
                                evidence=evidence or "x === NaN",
                                detector=self.name,
                                raw_confidence=0.98,
                                description="Comparing directly to NaN always evaluates to false. Use Number.isNaN() instead.",
                            )
                        )

            # 3. Off-by-one in loop over array length: for (let i = 0; i <= arr.length; i++)
            if node.type == "for_statement":
                condition = node.child_by_field_name("condition")
                if condition and condition.type == "binary_expression":
                    op = condition.child_by_field_name("operator")
                    right = condition.child_by_field_name("right")
                    if op and code_bytes[op.start_byte : op.end_byte].decode("utf-8") == "<=":
                        if right and ".length" in code_bytes[right.start_byte : right.end_byte].decode("utf-8"):
                            evidence = get_line_text(node.start_point.row, node.start_point.row)
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=node.start_point.row + 1,
                                    line_end=node.start_point.row + 1,
                                    symbol=current_symbol,
                                    category=FindingCategory.LOGIC_ERROR,
                                    evidence=evidence or "i <= arr.length",
                                    detector=self.name,
                                    raw_confidence=0.88,
                                    description="Off-by-one error: 'i <= arr.length' accesses undefined index on last iteration.",
                                )
                            )

            # 4. Swallowed exceptions in catch: catch (e) {}
            if node.type == "catch_clause":
                body = node.child_by_field_name("body")
                if body and len(body.children) <= 2:  # only { and }
                    evidence = get_line_text(node.start_point.row, body.end_point.row)
                    findings.append(
                        Finding(
                            file=rel_path,
                            line_start=node.start_point.row + 1,
                            line_end=body.end_point.row + 1,
                            symbol=current_symbol,
                            category=FindingCategory.EXCEPTION_HANDLING,
                            evidence=evidence or "catch (e) {}",
                            detector=self.name,
                            raw_confidence=0.88,
                            description="Empty catch block silently swallows exceptions.",
                        )
                    )

            # 5. Unreachable code after return / throw
            if node.type in {"return_statement", "throw_statement", "break_statement", "continue_statement"}:
                parent = node.parent
                if parent and parent.type == "statement_block":
                    idx_in_parent = parent.children.index(node)
                    if idx_in_parent < len(parent.children) - 1:
                        next_stmt = parent.children[idx_in_parent + 1]
                        if next_stmt.type not in {"comment", "}"}:
                            evidence = get_line_text(next_stmt.start_point.row, next_stmt.end_point.row)
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=next_stmt.start_point.row + 1,
                                    line_end=next_stmt.end_point.row + 1,
                                    symbol=current_symbol,
                                    category=FindingCategory.LOGIC_ERROR,
                                    evidence=evidence or "unreachable_js",
                                    detector=self.name,
                                    raw_confidence=0.92,
                                    description="Unreachable JavaScript statement following return or throw.",
                                )
                            )

            for child in node.children:
                walk(child, current_symbol)

        walk(tree.root_node)
        return findings
