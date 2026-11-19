"""Unit tests for AutoCodeRover code search API, including not-found cases."""

from pathlib import Path
import pytest

from autopatch.intelligence.service import CodeIntelligenceService


@pytest.fixture
def indexed_project(tmp_path: Path):
    """Sets up and indexes a sample project with classes, methods, and functions."""
    root = tmp_path / "sample_project"
    root.mkdir()

    # File 1: payment.py
    payment_code = """import os

class PaymentGateway(BaseGateway):
    '''Payment processing class.'''
    def __init__(self, api_key: str):
        self.api_key = api_key

    def charge(self, amount: float) -> bool:
        if amount <= 0:
            raise ValueError("Invalid amount")
        return True

    def refund(self, tx_id: str) -> bool:
        return True

def audit_transaction(tx_id: str) -> None:
    print(f"Auditing {tx_id}")
"""
    (root / "payment.py").write_text(payment_code)

    # File 2: auth.py
    auth_code = """class Authenticator:
    def verify_token(self, token: str) -> bool:
        return len(token) > 10
"""
    (root / "auth.py").write_text(auth_code)

    # File 3: multiline context file for +/- 3 lines search
    context_code = """line 1: header
line 2: setup
line 3: config
line 4: before
line 5: TARGET_SNIPPET_HERE
line 6: after
line 7: teardown
line 8: cleanup
line 9: footer
"""
    (root / "context.txt").write_text(context_code)

    service = CodeIntelligenceService()
    project_id = "test_proj_1"
    service.index_project(project_id, root)
    search_engine = service.get_search_engine(project_id, root)

    return search_engine, root


# 1. search_class
def test_search_class_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_class("PaymentGateway")
    assert len(results) == 1
    res = results[0]
    assert res.symbol_name == "PaymentGateway"
    assert res.symbol_type == "class"
    # AutoCodeRover specification: signature only!
    assert "class PaymentGateway(BaseGateway):" in res.content
    assert "def charge" not in res.content  # Body must be omitted


def test_search_class_not_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_class("NonExistentClass")
    assert results == []


# 2. search_class_in_file
def test_search_class_in_file_found(indexed_project):
    engine, _ = indexed_project
    res = engine.search_class_in_file("Authenticator", "auth.py")
    assert res is not None
    assert res.symbol_name == "Authenticator"
    assert "class Authenticator:" in res.content


def test_search_class_in_file_not_found(indexed_project):
    engine, _ = indexed_project
    # Wrong file
    res1 = engine.search_class_in_file("Authenticator", "payment.py")
    assert res1 is None

    # Non-existent class
    res2 = engine.search_class_in_file("GhostClass", "auth.py")
    assert res2 is None


# 3. search_method
def test_search_method_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_method("charge")
    assert len(results) == 1
    res = results[0]
    assert res.symbol_name == "PaymentGateway.charge"
    assert res.symbol_type == "method"
    # AutoCodeRover specification: full implementation!
    assert "def charge(self, amount: float)" in res.content
    assert "return True" in res.content


def test_search_method_not_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_method("missing_method")
    assert results == []


# 4. search_method_in_class
def test_search_method_in_class_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_method_in_class("charge", "PaymentGateway")
    assert len(results) == 1
    assert "def charge" in results[0].content


def test_search_method_in_class_not_found(indexed_project):
    engine, _ = indexed_project
    # Method not in Authenticator class
    res1 = engine.search_method_in_class("charge", "Authenticator")
    assert res1 == []

    # Non-existent method
    res2 = engine.search_method_in_class("fake_method", "PaymentGateway")
    assert res2 == []


# 5. search_method_in_file
def test_search_method_in_file_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_method_in_file("refund", "payment.py")
    assert len(results) == 1
    assert "def refund" in results[0].content


def test_search_method_in_file_not_found(indexed_project):
    engine, _ = indexed_project
    # Method not in auth.py
    res1 = engine.search_method_in_file("refund", "auth.py")
    assert res1 == []

    # Non-existent method
    res2 = engine.search_method_in_file("nonexistent", "payment.py")
    assert res2 == []


# 6. search_code
def test_search_code_returns_plus_minus_3_lines(indexed_project):
    engine, _ = indexed_project
    results = engine.search_code("TARGET_SNIPPET_HERE")
    assert len(results) == 1
    content = results[0].content

    # Target is on line 5
    # Must include lines 2, 3, 4 (3 before) and lines 6, 7, 8 (3 after)
    assert "line 5: TARGET_SNIPPET_HERE" in content
    assert "line 2: setup" in content
    assert "line 4: before" in content
    assert "line 6: after" in content
    assert "line 8: cleanup" in content
    # Should not include line 1 or line 9
    assert "line 1: header" not in content
    assert "line 9: footer" not in content


def test_search_code_not_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_code("COMPLETELY_ABSENT_TOKEN_12345")
    assert results == []


# 7. search_code_in_file
def test_search_code_in_file_found(indexed_project):
    engine, _ = indexed_project
    results = engine.search_code_in_file("TARGET_SNIPPET_HERE", "context.txt")
    assert len(results) == 1
    assert "TARGET_SNIPPET_HERE" in results[0].content


def test_search_code_in_file_not_found(indexed_project):
    engine, _ = indexed_project
    # Wrong file
    res1 = engine.search_code_in_file("TARGET_SNIPPET_HERE", "payment.py")
    assert res1 == []

    # Absent snippet
    res2 = engine.search_code_in_file("GHOST_STRING", "context.txt")
    assert res2 == []
