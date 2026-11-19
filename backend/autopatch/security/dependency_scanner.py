from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from autopatch.detection.models import Finding, FindingCategory


# Known vulnerable package versions database (package_name -> list of (max_vulnerable_version, cve, desc))
KNOWN_VULNERABLE_PACKAGES: Dict[str, List[Tuple[str, str, str]]] = {
    "requests": [("2.31.0", "CVE-2023-32681", "Leaking Proxy-Authorization header on redirect")],
    "urllib3": [("1.26.18", "CVE-2023-45803", "Cookie request header leak on redirect")],
    "jinja2": [("3.1.3", "CVE-2024-22195", "Cross-site scripting (XSS) via xmlattr filter")],
    "flask": [("2.2.5", "CVE-2023-30861", "Session cookie leak with shared secret")],
    "pyyaml": [("5.4.0", "CVE-2020-14343", "Arbitrary code execution via full_load parser")],
    "cryptography": [("41.0.6", "CVE-2023-49083", "NULL-pointer dereference in PKCS7 parsing")],
    "lodash": [("4.17.21", "CVE-2021-23337", "Command injection via template function")],
    "axios": [("0.21.1", "CVE-2020-28168", "SSRF bypass via server-relative URLs")],
    "json-schema": [("0.4.0", "CVE-2021-3918", "Prototype pollution vulnerability")],
}

KNOWN_MALICIOUS_PACKAGES = {
    "colorama-fake",
    "python-dateutil-v2",
    "reqeusts",
    "lodahs",
    "express-security",
    "discord-selfbot",
}


class DependencyScanner:
    """Scans project dependency manifests (requirements.txt, package.json) for CVEs and malicious packages."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        findings.extend(self._scan_requirements_txt())
        findings.extend(self._scan_package_json())
        return findings

    def _scan_requirements_txt(self) -> List[Finding]:
        findings: List[Finding] = []
        for req_file in self.project_root.rglob("*requirements*.txt"):
            if any(x in req_file.parts for x in [".git", ".venv", "node_modules"]):
                continue
            try:
                rel_path = str(req_file.relative_to(self.project_root))
                lines = req_file.read_text(encoding="utf-8", errors="replace").splitlines()
                for idx, line in enumerate(lines, start=1):
                    line_clean = line.strip()
                    if not line_clean or line_clean.startswith("#"):
                        continue

                    # Match package name and version
                    m = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:([=<>!~]+)(.+))?", line_clean)
                    if not m:
                        continue
                    pkg_name = m.group(1).lower()
                    op = m.group(2)
                    version_str = m.group(3).strip() if m.group(3) else None

                    # 1. Malicious package check
                    if pkg_name in KNOWN_MALICIOUS_PACKAGES:
                        findings.append(
                            Finding(
                                file=rel_path,
                                line_start=idx,
                                line_end=idx,
                                symbol=pkg_name,
                                category=FindingCategory.SECURITY,
                                cwe="CWE-506",
                                evidence=line_clean,
                                detector="DEPENDENCY_SCANNER",
                                raw_confidence=0.99,
                                description=f"Known malicious package detected in dependencies: '{pkg_name}'",
                            )
                        )
                        continue

                    # 2. Known vulnerable package check
                    if pkg_name in KNOWN_VULNERABLE_PACKAGES:
                        for max_vuln_ver, cve, desc in KNOWN_VULNERABLE_PACKAGES[pkg_name]:
                            # If version is pinned lower or unpinned
                            if not version_str or op in ("<", "<=", "=="):
                                findings.append(
                                    Finding(
                                        file=rel_path,
                                        line_start=idx,
                                        line_end=idx,
                                        symbol=pkg_name,
                                        category=FindingCategory.SECURITY,
                                        cwe="CWE-1395",
                                        evidence=line_clean,
                                        detector="DEPENDENCY_SCANNER",
                                        raw_confidence=0.92,
                                        description=f"Dependency '{pkg_name}' matches vulnerable threshold ({cve}: {desc})",
                                    )
                                )
                                break

                    # 3. Wildcard unpinned check
                    if version_str in ("*", "0.0.1", "0.1") or op == "*":
                        findings.append(
                            Finding(
                                file=rel_path,
                                line_start=idx,
                                line_end=idx,
                                symbol=pkg_name,
                                category=FindingCategory.SECURITY,
                                cwe="CWE-1104",
                                evidence=line_clean,
                                detector="DEPENDENCY_SCANNER",
                                raw_confidence=0.75,
                                description=f"Unpinned or wildcard dependency '{pkg_name}' introduces supply-chain risk",
                            )
                        )
            except Exception:
                pass

        return findings

    def _scan_package_json(self) -> List[Finding]:
        findings: List[Finding] = []
        for pkg_file in self.project_root.rglob("package.json"):
            if any(x in pkg_file.parts for x in [".git", ".venv", "node_modules"]):
                continue
            try:
                rel_path = str(pkg_file.relative_to(self.project_root))
                data = json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                for pkg_name_raw, ver_raw in deps.items():
                    pkg_name = pkg_name_raw.lower()
                    ver_clean = re.sub(r"[^0-9\.]", "", ver_raw)

                    # 1. Malicious package
                    if pkg_name in KNOWN_MALICIOUS_PACKAGES:
                        findings.append(
                            Finding(
                                file=rel_path,
                                line_start=1,
                                line_end=1,
                                symbol=pkg_name,
                                category=FindingCategory.SECURITY,
                                cwe="CWE-506",
                                evidence=f'"{pkg_name_raw}": "{ver_raw}"',
                                detector="DEPENDENCY_SCANNER",
                                raw_confidence=0.99,
                                description=f"Known malicious npm package detected: '{pkg_name}'",
                            )
                        )
                        continue

                    # 2. Known vulnerable package
                    if pkg_name in KNOWN_VULNERABLE_PACKAGES:
                        for max_vuln_ver, cve, desc in KNOWN_VULNERABLE_PACKAGES[pkg_name]:
                            findings.append(
                                Finding(
                                    file=rel_path,
                                    line_start=1,
                                    line_end=1,
                                    symbol=pkg_name,
                                    category=FindingCategory.SECURITY,
                                    cwe="CWE-1395",
                                    evidence=f'"{pkg_name_raw}": "{ver_raw}"',
                                    detector="DEPENDENCY_SCANNER",
                                    raw_confidence=0.90,
                                    description=f"NPM dependency '{pkg_name}' vulnerable to {cve}: {desc}",
                                )
                            )
                            break
            except Exception:
                pass

        return findings
