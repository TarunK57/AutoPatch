"""Unit tests for deterministic template fixes.

Acceptance criterion: Template fixes pass their own unit tests.
"""

import pytest
from autopatch.patcher.templates import DeterministicTemplatePatcher


@pytest.fixture
def template_patcher():
    return DeterministicTemplatePatcher()


def test_template_off_by_one_python(template_patcher):
    """Verify deterministic template fix for Python off-by-one."""
    code = """def get_all(items):
    for i in range(len(items) + 1):
        process(items[i])
"""
    patch = template_patcher.try_generate_patch("src/utils.py", code)
    assert patch is not None
    assert patch.template_name == "OFF_BY_ONE"
    assert "range(len(items))" in patch.patched_snippet
    assert "off-by-one" in patch.rationale.lower()


def test_template_off_by_one_js(template_patcher):
    """Verify deterministic template fix for JS off-by-one."""
    code = """function loop(arr) {
    for (let i = 0; i <= arr.length; i++) {
        console.log(arr[i]);
    }
}"""
    patch = template_patcher.try_generate_patch("src/utils.js", code)
    assert patch is not None
    assert patch.template_name == "OFF_BY_ONE"
    assert "i < arr.length" in patch.patched_snippet


def test_template_nan_check_python_and_js(template_patcher):
    """Verify deterministic template fix for direct NaN comparison."""
    # Python
    py_code = "if val == float('nan'): return True"
    py_patch = template_patcher.try_generate_patch("src/calc.py", py_code)
    assert py_patch is not None
    assert py_patch.template_name == "NAN_CHECK"
    assert "math.isnan(val)" in py_patch.patched_snippet

    # JS
    js_code = "if (val === NaN) { return true; }"
    js_patch = template_patcher.try_generate_patch("src/calc.js", js_code)
    assert js_patch is not None
    assert js_patch.template_name == "NAN_CHECK"
    assert "Number.isNaN(val)" in js_patch.patched_snippet


def test_template_zero_division_guard(template_patcher):
    """Verify deterministic template fix for division by len(...)."""
    code = """def calc_avg(scores):
    return sum(scores) / len(scores)
"""
    patch = template_patcher.try_generate_patch("src/stats.py", code)
    assert patch is not None
    assert patch.template_name == "VALIDATION_GUARD"
    assert "if len(scores) > 0 else 0.0" in patch.patched_snippet


def test_template_assignment_in_condition_js(template_patcher):
    """Verify deterministic template fix for accidental assignment in if condition."""
    code = "if (status = 'active') { doWork(); }"
    patch = template_patcher.try_generate_patch("src/auth.js", code)
    assert patch is not None
    assert patch.template_name == "STRICT_EQUALITY"
    assert "if (status === 'active')" in patch.patched_snippet


def test_template_missing_radix_js(template_patcher):
    """Verify deterministic template fix for parseInt missing radix."""
    code = "const val = parseInt(input);"
    patch = template_patcher.try_generate_patch("src/parser.js", code)
    assert patch is not None
    assert patch.template_name == "RADIX"
    assert "parseInt(input, 10)" in patch.patched_snippet


def test_template_swallowed_exception(template_patcher):
    """Verify deterministic template fix for swallowed exceptions."""
    code = """def load_file(p):
    try:
        read_data(p)
    except Exception:
        pass
"""
    patch = template_patcher.try_generate_patch("src/io.py", code)
    assert patch is not None
    assert patch.template_name == "EMPTY_CATCH_LOGGING"
    assert "logging.exception" in patch.patched_snippet


def test_template_parameterized_query_sql(template_patcher):
    """Verify deterministic template fix for SQL injection."""
    code = """def get_user(db, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
    patch = template_patcher.try_generate_patch("src/db.py", code)
    assert patch is not None
    assert patch.template_name == "PARAMETERIZED_QUERY"
    assert 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))' in patch.patched_snippet
