"""API Security Testing suite auditing REST endpoints against OWASP API Security Top 10."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autopatch.core.logging import get_logger

logger = get_logger(__name__)


class ApiEndpointSecurityFinding(BaseModel):
    finding_id: str
    file_path: str
    line_number: int
    http_method: str
    route_path: str
    owasp_category: str  # e.g. "API1:2023 - Broken Object Level Authorization"
    cwe: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    description: str
    evidence: str
    suggested_fix: str


class ApiSecurityAuditReport(BaseModel):
    project_id: str
    total_endpoints_discovered: int
    vulnerable_endpoints_count: int
    security_posture_grade: str  # "A+", "B", "C", "D", "F"
    owasp_coverage: List[str] = Field(default_factory=list)
    findings: List[ApiEndpointSecurityFinding] = Field(default_factory=list)


class ApiRouteVisitor(ast.NodeVisitor):
    """AST visitor discovering API endpoint definitions and inspecting security controls."""

    def __init__(self, rel_path: str, source_lines: List[str]):
        self.rel_path = rel_path
        self.source_lines = source_lines
        self.endpoints_count = 0
        self.findings: List[ApiEndpointSecurityFinding] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._inspect_function(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def _inspect_function(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            route_info = self._extract_route_info(decorator)
            if not route_info:
                continue

            self.endpoints_count += 1
            http_method, path_str = route_info
            fn_code = self._get_node_text(node)
            decorator_text = self._get_line_text(decorator.lineno)

            # Check 1: API2:2023 - Broken Authentication on state-changing operations
            has_auth = any(
                keyword in fn_code for keyword in (
                    "get_current_user", "auth", "token", "login_required",
                    "jwt_required", "Depends(", "Security("
                )
            )
            is_mutation = http_method.upper() in ("POST", "PUT", "DELETE", "PATCH")

            if is_mutation and not has_auth and not any(wh in path_str for wh in ("login", "register", "token", "signup", "webhook", "health")):
                f_id = f"api-auth-{node.lineno}"
                self.findings.append(
                    ApiEndpointSecurityFinding(
                        finding_id=f_id,
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        http_method=http_method,
                        route_path=path_str,
                        owasp_category="API2:2023 - Broken Authentication",
                        cwe="CWE-306",
                        severity="CRITICAL",
                        description=(
                            f"Endpoint '{http_method} {path_str}' modifies system state but contains "
                            "no authentication guard or user credential check."
                        ),
                        evidence=decorator_text,
                        suggested_fix="Add authentication dependency: 'current_user: User = Depends(get_current_user)'",
                    )
                )

            # Check 2: API1:2023 - Broken Object Level Authorization (BOLA / IDOR)
            has_id_param = any(p in path_str for p in ("{id}", "{user_id}", "{account_id}", "{project_id}", "{job_id}"))
            has_tenant_check = any(ch in fn_code for ch in ("assert_project_ownership", "owner_id", "tenant_id", "user_id == current_user.user_id"))

            if has_id_param and has_auth and not has_tenant_check:
                f_id = f"api-bola-{node.lineno}"
                self.findings.append(
                    ApiEndpointSecurityFinding(
                        finding_id=f_id,
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        http_method=http_method,
                        route_path=path_str,
                        owasp_category="API1:2023 - Broken Object Level Authorization (BOLA)",
                        cwe="CWE-639",
                        severity="HIGH",
                        description=(
                            f"Endpoint '{http_method} {path_str}' accepts resource identifier from path "
                            "without verifying authenticated user owns or is authorized to access target entity."
                        ),
                        evidence=decorator_text,
                        suggested_fix="Enforce authorization check: 'assert_ownership(entity.owner_id, current_user)'",
                    )
                )

            # Check 3: API4:2023 - Unrestricted Resource Consumption (Missing Pagination)
            is_listing = http_method.upper() == "GET" and not has_id_param and not any(wh in path_str for wh in ("health", "status", "metrics", "me"))
            has_limit = any(lim in fn_code for lim in ("limit", "paginate", "page", "slice", "[:", "OFFSET"))

            if is_listing and not has_limit and ("all" in node.name or "list" in node.name):
                f_id = f"api-dos-{node.lineno}"
                self.findings.append(
                    ApiEndpointSecurityFinding(
                        finding_id=f_id,
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        http_method=http_method,
                        route_path=path_str,
                        owasp_category="API4:2023 - Unrestricted Resource Consumption",
                        cwe="CWE-770",
                        severity="MEDIUM",
                        description=(
                            f"Endpoint '{http_method} {path_str}' queries collection without enforcing "
                            "pagination limits (offset/limit), risking memory exhaustion under large tables."
                        ),
                        evidence=decorator_text,
                        suggested_fix="Enforce default pagination: 'limit: int = Query(50, le=100), offset: int = 0'",
                    )
                )

    def _extract_route_info(self, decorator: ast.AST) -> Optional[tuple[str, str]]:
        """Extracts (HTTP_METHOD, ROUTE_PATH) from decorator AST node."""
        if isinstance(decorator, ast.Call):
            func = decorator.func
            method = ""
            if isinstance(func, ast.Attribute):
                method = func.attr.upper()  # e.g. get, post, put, delete, route
            elif isinstance(func, ast.Name):
                method = func.id.upper()

            if method in ("GET", "POST", "PUT", "DELETE", "PATCH", "ROUTE"):
                # Extract first argument (route path)
                if decorator.args:
                    first_arg = decorator.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        path_str = first_arg.value
                        if method == "ROUTE":
                            method = "GET"
                        return (method, path_str)
        return None

    def _get_line_text(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip() or f"# line {lineno}"
        return f"# line {lineno}"

    def _get_node_text(self, node: ast.AST) -> str:
        start = getattr(node, "lineno", 1) - 1
        end = getattr(node, "end_lineno", start + 25)
        return "\n".join(self.source_lines[start:end])


class ApiSecurityScanner:
    """Scans and validates API contracts and endpoints for OWASP API Security vulnerabilities."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()

    def audit_project(self, project_id: str) -> ApiSecurityAuditReport:
        findings: List[ApiEndpointSecurityFinding] = []
        total_endpoints = 0

        # Scan python files
        for py_path in self.project_root.rglob("*.py"):
            rel_str = str(py_path.relative_to(self.project_root))
            if any(part.startswith(".") or part in ("venv", ".venv", "tests") for part in py_path.parts):
                continue

            try:
                content = py_path.read_text(encoding="utf-8", errors="replace")
                if "@app." not in content and "@router." not in content and ".route(" not in content:
                    continue

                tree = ast.parse(content, filename=str(py_path))
                visitor = ApiRouteVisitor(rel_str, content.splitlines())
                visitor.visit(tree)

                total_endpoints += visitor.endpoints_count
                findings.extend(visitor.findings)
            except Exception:
                continue

        # Check CORS configuration
        self._check_cors_misconfiguration(findings)

        # Compute grade
        vulnerable_count = len(findings)
        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in findings if f.severity == "HIGH")

        if critical_count > 0:
            grade = "D" if critical_count <= 2 else "F"
        elif high_count > 0:
            grade = "C"
        elif vulnerable_count > 0:
            grade = "B"
        else:
            grade = "A+"

        return ApiSecurityAuditReport(
            project_id=project_id,
            total_endpoints_discovered=total_endpoints,
            vulnerable_endpoints_count=vulnerable_count,
            security_posture_grade=grade,
            owasp_coverage=[
                "API1:2023 - Broken Object Level Authorization (BOLA)",
                "API2:2023 - Broken Authentication",
                "API4:2023 - Unrestricted Resource Consumption",
                "API8:2023 - Security Misconfiguration",
            ],
            findings=findings,
        )

    def _check_cors_misconfiguration(self, findings: List[ApiEndpointSecurityFinding]) -> None:
        """Inspects for wildcards in CORS configuration."""
        for py_path in self.project_root.rglob("*.py"):
            rel_str = str(py_path.relative_to(self.project_root))
            if any(part.startswith(".") or part in ("venv", ".venv", "tests") for part in py_path.parts):
                continue
            try:
                txt = py_path.read_text(encoding="utf-8", errors="replace")
                if 'allow_origins=["*"]' in txt and "allow_credentials=True" in txt:
                    findings.append(
                        ApiEndpointSecurityFinding(
                            finding_id=f"cors-wildcard-{rel_str}",
                            file_path=rel_str,
                            line_number=1,
                            http_method="ALL",
                            route_path="/*",
                            owasp_category="API8:2023 - Security Misconfiguration",
                            cwe="CWE-942",
                            severity="HIGH",
                            description="Permissive CORS policy: 'allow_origins=[\"*\"]' combined with 'allow_credentials=True' allows unauthorized cross-origin credential leakage.",
                            evidence="CORSMiddleware(allow_origins=['*'], allow_credentials=True)",
                            suggested_fix="Explicitly declare trusted origins whitelist instead of wildcard '*'",
                        )
                    )
            except Exception:
                continue
