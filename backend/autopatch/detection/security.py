"""Security flaw detector with standardized CWE classification.

Detects:
- Hard-coded secrets (CWE-798)
- SQL injection (CWE-89)
- Command injection (CWE-78)
- Cross-Site Scripting (XSS) sinks (CWE-79)
- Dynamic code evaluation (eval/exec) (CWE-95)
- Unsafe deserialization (pickle, yaml.load) (CWE-502)
- Path traversal (CWE-22)
- Weak cryptographic hashing (MD5, SHA1) (CWE-328)
"""

import re
from pathlib import Path
from typing import List, Optional

from autopatch.detection.base import BaseDetector, CancellationToken
from autopatch.detection.models import Finding, FindingCategory
from autopatch.intelligence.models import FileASTIndex


class SecurityDetector(BaseDetector):
    """Identifies high-impact security vulnerabilities and maps them to CWE identifiers."""

    @property
    def name(self) -> str:
        return "SECURITY_CWE"

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

            lines = code.splitlines()

            # Analyze line by line and multi-line patterns
            for line_no, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                    continue

                # 1. Hard-coded secrets (CWE-798)
                secret_match = re.search(
                    r"""(?ix)
                    \b(api_key|apikey|secret_key|secret|password|access_token|auth_token)
                    \s*[:=]\s*
                    ['"]([^'"\s]{8,})['"]
                    """,
                    line,
                )
                if secret_match:
                    val = secret_match.group(2)
                    if val.lower() not in {"dummy", "test", "fake", "placeholder", "changeme", "password"}:
                        findings.append(
                            Finding(
                                file=idx.file_path,
                                line_start=line_no,
                                line_end=line_no,
                                category=FindingCategory.SECURITY,
                                cwe="CWE-798",
                                evidence=stripped,
                                detector=self.name,
                                raw_confidence=0.92,
                                description="Hard-coded credential detected in source code.",
                            )
                        )

                # 2. SQL Injection (CWE-89)
                # Formatted strings in execute, select, or query calls
                sql_inj_match = re.search(
                    r"""(?ix)
                    (?:execute|cursor\.execute|raw|query)\s*\(\s*
                    (?:f['"].*?(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE).*?\{.*?\}['"]|
                    ['"].*?(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE).*?['"]\s*\+|
                    ['"].*?(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE).*?%s.*?['"]\s*%)
                    """,
                    line,
                )
                if sql_inj_match:
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-89",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.95,
                            description="SQL query constructed via string interpolation risks SQL injection.",
                        )
                    )

                # 3. Command Injection (CWE-78)
                # os.system, subprocess with shell=True and dynamic variables
                cmd_inj_match = re.search(
                    r"""(?ix)
                    (?:os\.system\s*\(\s*f['"]|
                    subprocess\.(?:call|Popen|run|check_output)\s*\(.*shell\s*=\s*True|
                    child_process\.exec\s*\(.*?[\$\+])
                    """,
                    line,
                )
                if cmd_inj_match:
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-78",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.94,
                            description="OS command executed with dynamic string interpolation or shell=True risks command injection.",
                        )
                    )

                # 4. XSS Sinks (CWE-79)
                xss_match = re.search(
                    r"""(?ix)
                    (?:\.innerHTML\s*=|dangerouslySetInnerHTML\s*=|document\.write\s*\()
                    """,
                    line,
                )
                if xss_match:
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-79",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.90,
                            description="Direct assignment to DOM innerHTML or dangerouslySetInnerHTML invites Cross-Site Scripting (XSS).",
                        )
                    )

                # 5. Eval / Exec / Code Injection (CWE-95)
                eval_match = re.search(r"\b(eval|exec)\s*\([^)]+\)", line)
                if eval_match and not re.search(r"['\"][^'\"]*\b(eval|exec)\b[^'\"]*['\"]", line):
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-95",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.96,
                            description="Use of dynamic code evaluation (eval/exec) allows arbitrary code execution.",
                        )
                    )

                # 6. Unsafe Deserialization (CWE-502)
                deser_match = re.search(
                    r"""(?ix)
                    \b(?:pickle\.loads|pickle\.load|yaml\.load\s*\([^,)]+\))
                    """,
                    line,
                )
                if deser_match:
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-502",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.95,
                            description="Unsafe deserialization of untrusted data allows remote code execution.",
                        )
                    )

                # 7. Path Traversal (CWE-22)
                traversal_match = re.search(
                    r"""(?ix)
                    (?:open|os\.path\.join)\s*\([^,)]+,\s*(?:req|request|user_input|filename|path)[^)]*\)
                    """,
                    line,
                )
                if traversal_match and "commonpath" not in line and "resolve" not in line:
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-22",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.88,
                            description="Path joined with untrusted input without path sanitization risks directory traversal.",
                        )
                    )

                # 8. Weak Hashing (CWE-328)
                hash_match = re.search(
                    r"""(?ix)
                    \b(?:hashlib\.md5|hashlib\.sha1|crypto\.createHash\s*\(\s*['"](?:md5|sha1)['"]\))
                    """,
                    line,
                )
                if hash_match:
                    findings.append(
                        Finding(
                            file=idx.file_path,
                            line_start=line_no,
                            line_end=line_no,
                            category=FindingCategory.SECURITY,
                            cwe="CWE-328",
                            evidence=stripped,
                            detector=self.name,
                            raw_confidence=0.90,
                            description="Use of cryptographically weak hash algorithm (MD5 or SHA1).",
                        )
                    )

        return findings
