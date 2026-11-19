"""Evaluation of bug detection pipeline on a seeded repository with 15 known bugs.

Acceptance criteria:
- Report recall and precision on 15 known bugs
- Every finding has evidence
- Duplicates merged
"""

from pathlib import Path
import pytest

from autopatch.detection.models import Finding
from autopatch.detection.pipeline import DetectionPipeline
from autopatch.intelligence.service import CodeIntelligenceService


@pytest.fixture
def seeded_repo(tmp_path: Path):
    """Sets up a repository seeded with 15 distinct, verified bugs across Python and JS."""
    root = tmp_path / "seeded_repo"
    root.mkdir()

    # ---------------------------------------------------------
    # Bug 1-7: Python Logic & Resource Bugs (python_bugs.py)
    # ---------------------------------------------------------
    python_bugs_code = """import os
import math

# Bug 1: Mutable default argument
def append_item(val: int, registry=[]):
    registry.append(val)
    return registry

# Bug 2: Off-by-one in range over len
def iterate_items(items):
    total = 0
    for i in range(len(items) + 1):
        total += items[i]
    return total

# Bug 3: Division by zero on empty length
def compute_average(scores):
    total = sum(scores)
    return total / len(scores)

# Bug 4: Swallowed exception with pass
def load_data(source):
    try:
        data = source.read()
    except Exception:
        pass
    return None

# Bug 5: Comparing to NaN with ==
def check_nan(val):
    if val == float('nan'):
        return True
    return False

# Bug 6: Unclosed resource without with
def read_log_unclosed(log_path):
    f = open(log_path, 'r')
    return f.read()

# Bug 7: Unreachable code after return
def calculate_status(flag):
    if flag:
        return "ACTIVE"
        print("Flag was active") # Unreachable
    return "INACTIVE"
"""
    (root / "python_bugs.py").write_text(python_bugs_code)

    # ---------------------------------------------------------
    # Bug 8-10: JavaScript Logic Bugs (js_bugs.js)
    # ---------------------------------------------------------
    js_bugs_code = """// Bug 8: Accidental assignment in condition
function verifyActive(user) {
    if (user.status = 'active') {
        return true;
    }
    return false;
}

// Bug 9: Comparing directly to NaN
function isValueNaN(val) {
    if (val === NaN) {
        return true;
    }
    return false;
}

// Bug 10: Off-by-one with <= on array length
function printUsers(users) {
    for (let i = 0; i <= users.length; i++) {
        console.log(users[i]);
    }
}
"""
    (root / "js_bugs.js").write_text(js_bugs_code)

    # ---------------------------------------------------------
    # Bug 11-12: Input Validation Defects (validation_bugs.py)
    # ---------------------------------------------------------
    validation_code = """# Bug 11: Missing range validation on marks
def calculate_grade(marks: float) -> str:
    # Missing bounds validation
    if marks >= 90:
        return "A"
    return "F"

# Bug 12: Missing non-negative validation on price
def apply_discount(price: float, discount: float) -> float:
    # Missing non-negative validation
    return price * (1.0 - discount)
"""
    (root / "validation_bugs.py").write_text(validation_code)

    # ---------------------------------------------------------
    # Bug 13-15: Security Vulnerabilities (security_bugs.py)
    # ---------------------------------------------------------
    security_code = """import os
import subprocess
import sqlite3

# Bug 13: Hard-coded secret API key
api_key = "sk-proj-live-1234567890abcdef1234567890"

# Bug 14: SQL Injection via f-string
def get_user_by_id(db_conn, user_id: str):
    cursor = db_conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()

# Bug 15: Command Injection via shell=True
def backup_directory(target_dir: str):
    cmd = f"tar -czf backup.tar.gz {target_dir}"
    subprocess.run(cmd, shell=True)
"""
    (root / "security_bugs.py").write_text(security_code)

    # Known bugs ground truth mapping (15 bugs)
    known_bugs = [
        {"id": 1, "file": "python_bugs.py", "line": 6, "desc": "Mutable default"},
        {"id": 2, "file": "python_bugs.py", "line": 13, "desc": "Off-by-one range"},
        {"id": 3, "file": "python_bugs.py", "line": 20, "desc": "Division by zero len"},
        {"id": 4, "file": "python_bugs.py", "line": 27, "desc": "Swallowed exception"},
        {"id": 5, "file": "python_bugs.py", "line": 32, "desc": "Comparing to NaN"},
        {"id": 6, "file": "python_bugs.py", "line": 38, "desc": "Unclosed open()"},
        {"id": 7, "file": "python_bugs.py", "line": 45, "desc": "Unreachable code"},
        {"id": 8, "file": "js_bugs.js", "line": 3, "desc": "Assignment in if"},
        {"id": 9, "file": "js_bugs.js", "line": 11, "desc": "Comparing to NaN JS"},
        {"id": 10, "file": "js_bugs.js", "line": 19, "desc": "Off-by-one <= length"},
        {"id": 11, "file": "validation_bugs.py", "line": 2, "desc": "Marks range validation"},
        {"id": 12, "file": "validation_bugs.py", "line": 9, "desc": "Price range validation"},
        {"id": 13, "file": "security_bugs.py", "line": 6, "desc": "Hardcoded secret"},
        {"id": 14, "file": "security_bugs.py", "line": 11, "desc": "SQL injection"},
        {"id": 15, "file": "security_bugs.py", "line": 17, "desc": "Command injection"},
    ]

    return root, known_bugs


def test_seeded_repo_15_bugs_precision_and_recall(seeded_repo):
    """Acceptance criterion: on seeded repo with 15 known bugs, report recall and precision; every finding has evidence."""
    root, known_bugs = seeded_repo

    # Index project files
    service = CodeIntelligenceService()
    project_id = "eval_seeded_15"
    service.index_project(project_id, root)

    # Parse AST indices
    file_indices = []
    for p in root.glob("*.*"):
        adapter = service.get_adapter_for_path(p)
        if adapter:
            file_indices.append(adapter.parse_file(p.name, p.read_text(encoding="utf-8")))

    # Run detection pipeline
    pipeline = DetectionPipeline()
    report = pipeline.run(project_id, root, file_indices)

    assert not report.cancelled
    assert report.total_findings > 0

    # Acceptance criterion: every finding has evidence
    for f in report.findings:
        assert f.evidence is not None
        assert len(f.evidence.strip()) > 0, f"Finding in {f.file}:{f.line_start} has empty evidence!"

    # Compute recall and precision
    recall, precision = DetectionPipeline.evaluate_precision_recall(known_bugs, report.findings)

    print(f"\n[BENCHMARK] Total Findings: {report.total_findings}")
    for f in report.findings:
        print(f"FINDING: {f.file}:{f.line_start}-{f.line_end} | {f.category} | {f.description[:50]}")
    print("\nKNOWN BUGS:")
    for b in known_bugs:
        print(f"KNOWN BUG {b['id']}: {b['file']}:{b['line']} | {b['desc']}")
    print(f"[BENCHMARK] Known Bugs: {len(known_bugs)}")
    print(f"[BENCHMARK] Recall: {recall * 100:.2f}%")
    print(f"[BENCHMARK] Precision: {precision * 100:.2f}%")

    # Verify high detection coverage across the 15 known bugs
    assert recall >= 0.85, f"Recall was {recall}, expected >= 0.85"
    assert precision >= 0.70, f"Precision was {precision}, expected >= 0.70"
