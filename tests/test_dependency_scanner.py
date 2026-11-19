from __future__ import annotations

import json
import tempfile
from pathlib import Path
from autopatch.detection.models import FindingCategory
from autopatch.security.dependency_scanner import DependencyScanner


def test_dependency_scanner_detects_vulnerable_and_malicious_packages():
    """Verify that DependencyScanner flags vulnerable versions, typosquats, and unpinned packages."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # 1. Create requirements.txt
        req_file = root / "requirements.txt"
        req_file.write_text(
            "# App dependencies\n"
            "requests==2.28.0\n"  # Vulnerable to CVE-2023-32681
            "urllib3<1.26.0\n"   # Vulnerable to CVE-2023-45803
            "colorama-fake==1.0.0\n"  # Malicious package
            "flask=*\n"          # Wildcard unpinned
            "safe-pkg==1.2.3\n",
            encoding="utf-8",
        )

        # 2. Create package.json
        pkg_file = root / "package.json"
        pkg_file.write_text(
            json.dumps({
                "name": "sample-ui",
                "dependencies": {
                    "lodash": "4.17.15",  # Vulnerable to CVE-2021-23337
                    "express-security": "1.0.0",  # Malicious package
                }
            }),
            encoding="utf-8",
        )

        scanner = DependencyScanner(project_root=root)
        findings = scanner.scan()

        assert len(findings) >= 5

        # Check Python findings
        symbols = [f.symbol for f in findings]
        assert "requests" in symbols
        assert "urllib3" in symbols
        assert "colorama-fake" in symbols
        assert "flask" in symbols

        # Check JS findings
        assert "lodash" in symbols
        assert "express-security" in symbols

        # Check finding categories and CWEs
        for f in findings:
            assert f.category == FindingCategory.SECURITY
            assert f.cwe in ("CWE-1395", "CWE-506", "CWE-1104")

        # Malicious finding has high confidence and CWE-506
        malicious_f = next(f for f in findings if f.symbol == "colorama-fake")
        assert malicious_f.cwe == "CWE-506"
        assert malicious_f.raw_confidence >= 0.95
