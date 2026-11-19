"""Curated benchmark dataset of 30 seeded defects across Python and JavaScript.

Covers 7 defect categories:
1. off-by-one (5 bugs: 3 Python, 2 JS)
2. validation (5 bugs: 3 Python, 2 JS)
3. null access (4 bugs: 2 Python, 2 JS)
4. security (4 bugs: 2 Python, 2 JS)
5. concurrency-lite (4 bugs: 2 Python, 2 JS)
6. wrong operator (4 bugs: 2 Python, 2 JS)
7. boundary (4 bugs: 2 Python, 2 JS)

Each instance includes the buggy file, ground-truth patch, baseline tests, and hidden oracle test.
"""

from __future__ import annotations

from typing import List
from eval.dataset.models import BugCategory, EvaluationInstance, Language

SEEDED_BUGS: List[EvaluationInstance] = [
    # =========================================================================
    # 1. OFF-BY-ONE (5 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-OBO-01",
        language=Language.PYTHON,
        category=BugCategory.OFF_BY_ONE,
        description="Loop over inventory stock uses len(items) + 1 causing IndexError on final iteration.",
        file_path="inventory.py",
        target_symbol="reserve_stock",
        line_start=3,
        line_end=5,
        buggy_code="""class InventoryManager:
    def reserve_stock(self, items, quantity):
        for i in range(len(items) + 1):
            if items[i]["stock"] >= quantity:
                items[i]["stock"] -= quantity
                return True
        return False
""",
        ground_truth_patch="""--- a/inventory.py
+++ b/inventory.py
@@ -3,1 +3,1 @@
-        for i in range(len(items) + 1):
+        for i in range(len(items)):
""",
        ground_truth_code="""class InventoryManager:
    def reserve_stock(self, items, quantity):
        for i in range(len(items)):
            if items[i]["stock"] >= quantity:
                items[i]["stock"] -= quantity
                return True
        return False
""",
        hidden_oracle_test="""def test_oracle_reserve_stock():
    mgr = InventoryManager()
    items = [{"stock": 2}, {"stock": 4}]
    # Should not raise IndexError when searching items
    res = mgr.reserve_stock(items, 10)
    assert res is False
""",
        existing_tests="""def test_existing_reserve_success():
    mgr = InventoryManager()
    items = [{"stock": 10}]
    assert mgr.reserve_stock(items, 5) is True
    assert items[0]["stock"] == 5
""",
    ),
    EvaluationInstance(
        instance_id="PY-OBO-02",
        language=Language.PYTHON,
        category=BugCategory.OFF_BY_ONE,
        description="1-based pagination offset calculation omits page - 1 shift, dropping the first page.",
        file_path="pagination.py",
        target_symbol="get_page_slice",
        line_start=2,
        line_end=4,
        buggy_code="""def get_page_slice(items, page, page_size):
    offset = page * page_size
    return items[offset:offset + page_size]
""",
        ground_truth_patch="""--- a/pagination.py
+++ b/pagination.py
@@ -2,1 +2,1 @@
-    offset = page * page_size
+    offset = (page - 1) * page_size
""",
        ground_truth_code="""def get_page_slice(items, page, page_size):
    offset = (page - 1) * page_size
    return items[offset:offset + page_size]
""",
        hidden_oracle_test="""def test_oracle_first_page():
    data = ["a", "b", "c", "d"]
    page1 = get_page_slice(data, page=1, page_size=2)
    assert page1 == ["a", "b"]
""",
        existing_tests="""def test_existing_empty_page():
    data = []
    assert get_page_slice(data, page=1, page_size=5) == []
""",
    ),
    EvaluationInstance(
        instance_id="PY-OBO-03",
        language=Language.PYTHON,
        category=BugCategory.OFF_BY_ONE,
        description="Delimiter strip slices len(s) - 1 blindly without checking if trailing character is comma.",
        file_path="formatter.py",
        target_symbol="strip_trailing_comma",
        line_start=2,
        line_end=4,
        buggy_code="""def strip_trailing_comma(text):
    if not text:
        return text
    return text[:len(text) - 1]
""",
        ground_truth_patch="""--- a/formatter.py
+++ b/formatter.py
@@ -3,1 +3,2 @@
-    return text[:len(text) - 1]
+    if text.endswith(","):
+        return text[:-1]
+    return text
""",
        ground_truth_code="""def strip_trailing_comma(text):
    if not text:
        return text
    if text.endswith(","):
        return text[:-1]
    return text
""",
        hidden_oracle_test="""def test_oracle_word_without_comma():
    assert strip_trailing_comma("hello") == "hello"
""",
        existing_tests="""def test_existing_empty():
    assert strip_trailing_comma("") == ""
""",
    ),
    EvaluationInstance(
        instance_id="JS-OBO-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.OFF_BY_ONE,
        description="Loop over array uses <= length causing undefined item addition and NaN result.",
        file_path="stats.js",
        target_symbol="calculateSum",
        line_start=3,
        line_end=5,
        buggy_code="""function calculateSum(numbers) {
    let sum = 0;
    for (let i = 0; i <= numbers.length; i++) {
        sum += numbers[i];
    }
    return sum;
}
module.exports = { calculateSum };
""",
        ground_truth_patch="""--- a/stats.js
+++ b/stats.js
@@ -3,1 +3,1 @@
-    for (let i = 0; i <= numbers.length; i++) {
+    for (let i = 0; i < numbers.length; i++) {
""",
        ground_truth_code="""function calculateSum(numbers) {
    let sum = 0;
    for (let i = 0; i < numbers.length; i++) {
        sum += numbers[i];
    }
    return sum;
}
module.exports = { calculateSum };
""",
        hidden_oracle_test="""const assert = require('assert');
const { calculateSum } = require('./stats.js');
assert.strictEqual(calculateSum([10, 20, 30]), 60);
""",
        existing_tests="""const assert = require('assert');
const { calculateSum } = require('./stats.js');
assert.strictEqual(calculateSum([]), 0);
""",
    ),
    EvaluationInstance(
        instance_id="JS-OBO-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.OFF_BY_ONE,
        description="Path trimmer substring truncates final character even if not a slash.",
        file_path="pathHelper.js",
        target_symbol="trimSlash",
        line_start=2,
        line_end=4,
        buggy_code="""function trimSlash(path) {
    if (!path) return "";
    return path.substring(0, path.length - 1);
}
module.exports = { trimSlash };
""",
        ground_truth_patch="""--- a/pathHelper.js
+++ b/pathHelper.js
@@ -3,1 +3,1 @@
-    return path.substring(0, path.length - 1);
+    return path.endsWith('/') ? path.substring(0, path.length - 1) : path;
""",
        ground_truth_code="""function trimSlash(path) {
    if (!path) return "";
    return path.endsWith('/') ? path.substring(0, path.length - 1) : path;
}
module.exports = { trimSlash };
""",
        hidden_oracle_test="""const assert = require('assert');
const { trimSlash } = require('./pathHelper.js');
assert.strictEqual(trimSlash("api/v1"), "api/v1");
assert.strictEqual(trimSlash("api/v1/"), "api/v1");
""",
        existing_tests="""const assert = require('assert');
const { trimSlash } = require('./pathHelper.js');
assert.strictEqual(trimSlash(""), "");
""",
    ),

    # =========================================================================
    # 2. VALIDATION (5 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-VAL-01",
        language=Language.PYTHON,
        category=BugCategory.VALIDATION,
        description="Average calculation divides by length of items without validating empty collection.",
        file_path="analytics.py",
        target_symbol="calculate_average",
        line_start=2,
        line_end=4,
        buggy_code="""def calculate_average(scores):
    total = sum(scores)
    return total / len(scores)
""",
        ground_truth_patch="""--- a/analytics.py
+++ b/analytics.py
@@ -2,1 +2,3 @@
+    if not scores:
+        return 0.0
     total = sum(scores)
""",
        ground_truth_code="""def calculate_average(scores):
    if not scores:
        return 0.0
    total = sum(scores)
    return total / len(scores)
""",
        hidden_oracle_test="""def test_oracle_empty_scores():
    assert calculate_average([]) == 0.0
""",
        existing_tests="""def test_existing_valid_average():
    assert calculate_average([10, 20]) == 15.0
""",
    ),
    EvaluationInstance(
        instance_id="PY-VAL-02",
        language=Language.PYTHON,
        category=BugCategory.VALIDATION,
        description="Order placement does not validate that quantity is positive.",
        file_path="orders.py",
        target_symbol="create_order",
        line_start=3,
        line_end=5,
        buggy_code="""class OrderService:
    def create_order(self, item_id, quantity, unit_price):
        total = quantity * unit_price
        return {"item_id": item_id, "quantity": quantity, "total": total}
""",
        ground_truth_patch="""--- a/orders.py
+++ b/orders.py
@@ -3,1 +3,3 @@
+        if quantity <= 0:
+            raise ValueError("Quantity must be positive")
         total = quantity * unit_price
""",
        ground_truth_code="""class OrderService:
    def create_order(self, item_id, quantity, unit_price):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        total = quantity * unit_price
        return {"item_id": item_id, "quantity": quantity, "total": total}
""",
        hidden_oracle_test="""import pytest
def test_oracle_negative_quantity_rejected():
    service = OrderService()
    with pytest.raises(ValueError, match="Quantity must be positive"):
        service.create_order("SKU-1", -5, 10.0)
""",
        existing_tests="""def test_existing_positive_order():
    service = OrderService()
    res = service.create_order("SKU-1", 2, 10.0)
    assert res["total"] == 20.0
""",
    ),
    EvaluationInstance(
        instance_id="PY-VAL-03",
        language=Language.PYTHON,
        category=BugCategory.VALIDATION,
        description="Missing at-sign and domain validation in email parser.",
        file_path="user_service.py",
        target_symbol="validate_email",
        line_start=2,
        line_end=4,
        buggy_code="""def validate_email(email):
    return len(email) > 3
""",
        ground_truth_patch="""--- a/user_service.py
+++ b/user_service.py
@@ -2,1 +2,1 @@
-    return len(email) > 3
+    return bool(email and "@" in email and "." in email.split("@")[-1])
""",
        ground_truth_code="""def validate_email(email):
    return bool(email and "@" in email and "." in email.split("@")[-1])
""",
        hidden_oracle_test="""def test_oracle_email_format():
    assert validate_email("plainaddress") is False
    assert validate_email("user@example.com") is True
""",
        existing_tests="""def test_existing_empty_email():
    assert validate_email("") is False
""",
    ),
    EvaluationInstance(
        instance_id="JS-VAL-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.VALIDATION,
        description="Missing explicit base 10 radix parameter in parseInt call.",
        file_path="converter.js",
        target_symbol="parseId",
        line_start=2,
        line_end=4,
        buggy_code="""function parseId(str) {
    return parseInt(str);
}
module.exports = { parseId };
""",
        ground_truth_patch="""--- a/converter.js
+++ b/converter.js
@@ -2,1 +2,1 @@
-    return parseInt(str);
+    return parseInt(str, 10);
""",
        ground_truth_code="""function parseId(str) {
    return parseInt(str, 10);
}
module.exports = { parseId };
""",
        hidden_oracle_test="""const assert = require('assert');
const { parseId } = require('./converter.js');
assert.strictEqual(parseId("08"), 8);
assert.strictEqual(parseId("09"), 9);
""",
        existing_tests="""const assert = require('assert');
const { parseId } = require('./converter.js');
assert.strictEqual(parseId("42"), 42);
""",
    ),
    EvaluationInstance(
        instance_id="JS-VAL-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.VALIDATION,
        description="Rate calculator divides requests by windowSeconds without checking for zero window.",
        file_path="rateLimiter.js",
        target_symbol="calculateRate",
        line_start=2,
        line_end=4,
        buggy_code="""function calculateRate(count, windowSeconds) {
    return count / windowSeconds;
}
module.exports = { calculateRate };
""",
        ground_truth_patch="""--- a/rateLimiter.js
+++ b/rateLimiter.js
@@ -2,1 +2,2 @@
+    if (!windowSeconds || windowSeconds <= 0) return 0;
     return count / windowSeconds;
""",
        ground_truth_code="""function calculateRate(count, windowSeconds) {
    if (!windowSeconds || windowSeconds <= 0) return 0;
    return count / windowSeconds;
}
module.exports = { calculateRate };
""",
        hidden_oracle_test="""const assert = require('assert');
const { calculateRate } = require('./rateLimiter.js');
assert.strictEqual(calculateRate(100, 0), 0);
""",
        existing_tests="""const assert = require('assert');
const { calculateRate } = require('./rateLimiter.js');
assert.strictEqual(calculateRate(60, 60), 1);
""",
    ),

    # =========================================================================
    # 3. NULL ACCESS (4 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-NULL-01",
        language=Language.PYTHON,
        category=BugCategory.NULL_ACCESS,
        description="Accessing city from address dictionary raises TypeError when address is None.",
        file_path="user_profile.py",
        target_symbol="get_user_city",
        line_start=2,
        line_end=4,
        buggy_code="""def get_user_city(user):
    return user["address"]["city"]
""",
        ground_truth_patch="""--- a/user_profile.py
+++ b/user_profile.py
@@ -2,1 +2,3 @@
+    if not user or not user.get("address"):
+        return "Unknown"
     return user["address"]["city"]
""",
        ground_truth_code="""def get_user_city(user):
    if not user or not user.get("address"):
        return "Unknown"
    return user["address"]["city"]
""",
        hidden_oracle_test="""def test_oracle_missing_address():
    assert get_user_city({"address": None}) == "Unknown"
    assert get_user_city({}) == "Unknown"
""",
        existing_tests="""def test_existing_valid_city():
    assert get_user_city({"address": {"city": "Zurich"}}) == "Zurich"
""",
    ),
    EvaluationInstance(
        instance_id="PY-NULL-02",
        language=Language.PYTHON,
        category=BugCategory.NULL_ACCESS,
        description="Calling strip() on optional token parameter raises AttributeError when token is None.",
        file_path="auth_tokens.py",
        target_symbol="sanitize_token",
        line_start=2,
        line_end=4,
        buggy_code="""def sanitize_token(token):
    return token.strip()
""",
        ground_truth_patch="""--- a/auth_tokens.py
+++ b/auth_tokens.py
@@ -2,1 +2,3 @@
+    if token is None:
+        return ""
     return token.strip()
""",
        ground_truth_code="""def sanitize_token(token):
    if token is None:
        return ""
    return token.strip()
""",
        hidden_oracle_test="""def test_oracle_none_token():
    assert sanitize_token(None) == ""
""",
        existing_tests="""def test_existing_token_strip():
    assert sanitize_token("  abc  ") == "abc"
""",
    ),
    EvaluationInstance(
        instance_id="JS-NULL-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.NULL_ACCESS,
        description="Deeply nested database host lookup throws TypeError when database config is undefined.",
        file_path="config.js",
        target_symbol="getDbHost",
        line_start=2,
        line_end=4,
        buggy_code="""function getDbHost(config) {
    return config.database.connection.host;
}
module.exports = { getDbHost };
""",
        ground_truth_patch="""--- a/config.js
+++ b/config.js
@@ -2,1 +2,1 @@
-    return config.database.connection.host;
+    return config?.database?.connection?.host || "localhost";
""",
        ground_truth_code="""function getDbHost(config) {
    return config?.database?.connection?.host || "localhost";
}
module.exports = { getDbHost };
""",
        hidden_oracle_test="""const assert = require('assert');
const { getDbHost } = require('./config.js');
assert.strictEqual(getDbHost({}), "localhost");
assert.strictEqual(getDbHost({ database: null }), "localhost");
""",
        existing_tests="""const assert = require('assert');
const { getDbHost } = require('./config.js');
assert.strictEqual(getDbHost({ database: { connection: { host: "db.internal" } } }), "db.internal");
""",
    ),
    EvaluationInstance(
        instance_id="JS-NULL-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.NULL_ACCESS,
        description="Index zero title access throws Cannot read property of undefined when items array is empty.",
        file_path="search.js",
        target_symbol="getFirstTitle",
        line_start=2,
        line_end=4,
        buggy_code="""function getFirstTitle(results) {
    return results[0].title;
}
module.exports = { getFirstTitle };
""",
        ground_truth_patch="""--- a/search.js
+++ b/search.js
@@ -2,1 +2,1 @@
-    return results[0].title;
+    return results && results.length > 0 ? results[0].title : null;
""",
        ground_truth_code="""function getFirstTitle(results) {
    return results && results.length > 0 ? results[0].title : null;
}
module.exports = { getFirstTitle };
""",
        hidden_oracle_test="""const assert = require('assert');
const { getFirstTitle } = require('./search.js');
assert.strictEqual(getFirstTitle([]), null);
assert.strictEqual(getFirstTitle(null), null);
""",
        existing_tests="""const assert = require('assert');
const { getFirstTitle } = require('./search.js');
assert.strictEqual(getFirstTitle([{ title: "Doc 1" }]), "Doc 1");
""",
    ),

    # =========================================================================
    # 4. SECURITY (4 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-SEC-01",
        language=Language.PYTHON,
        category=BugCategory.SECURITY,
        description="SQL query string interpolation enables SQL injection.",
        file_path="repository.py",
        target_symbol="find_user",
        line_start=2,
        line_end=4,
        buggy_code="""def find_user(username):
    query = f"SELECT id, username FROM users WHERE username = '{username}'"
    return query
""",
        ground_truth_patch="""--- a/repository.py
+++ b/repository.py
@@ -2,2 +2,2 @@
-    query = f"SELECT id, username FROM users WHERE username = '{username}'"
-    return query
+    query = "SELECT id, username FROM users WHERE username = ?"
+    return (query, (username,))
""",
        ground_truth_code="""def find_user(username):
    query = "SELECT id, username FROM users WHERE username = ?"
    return (query, (username,))
""",
        hidden_oracle_test="""def test_oracle_sql_injection_defense():
    attack = "admin' OR '1'='1"
    res = find_user(attack)
    # Should be parameterized tuple, never raw interpolated string
    assert isinstance(res, tuple)
    assert "?" in res[0]
    assert attack not in res[0]
    assert res[1] == (attack,)
""",
        existing_tests="""def test_existing_benign_query():
    res = find_user("alice")
    assert "?" in res[0] or "alice" in res
""",
    ),
    EvaluationInstance(
        instance_id="PY-SEC-02",
        language=Language.PYTHON,
        category=BugCategory.SECURITY,
        description="String concatenated system call allows command injection via shell metacharacters.",
        file_path="backup.py",
        target_symbol="create_archive",
        line_start=3,
        line_end=6,
        buggy_code="""import shlex

def create_archive(source_dir, output_file):
    cmd = "tar -czf " + output_file + " " + source_dir
    return cmd
""",
        ground_truth_patch="""--- a/backup.py
+++ b/backup.py
@@ -4,2 +4,2 @@
-    cmd = "tar -czf " + output_file + " " + source_dir
-    return cmd
+    args = ["tar", "-czf", output_file, source_dir]
+    return args
""",
        ground_truth_code="""import shlex

def create_archive(source_dir, output_file):
    args = ["tar", "-czf", output_file, source_dir]
    return args
""",
        hidden_oracle_test="""def test_oracle_command_injection_defense():
    bad_dir = "test; rm -rf /"
    cmd = create_archive(bad_dir, "out.tar.gz")
    assert isinstance(cmd, list)
    assert ";" not in cmd[2] and ";" not in cmd[1]
""",
        existing_tests="""def test_existing_valid_archive():
    res = create_archive("my_folder", "out.tar.gz")
    assert "tar" in res
""",
    ),
    EvaluationInstance(
        instance_id="JS-SEC-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.SECURITY,
        description="Unescaped HTML interpolation leads to Cross-Site Scripting (XSS).",
        file_path="renderer.js",
        target_symbol="renderUserCard",
        line_start=2,
        line_end=4,
        buggy_code="""function renderUserCard(userName) {
    return `<div class="user-card"><span>${userName}</span></div>`;
}
module.exports = { renderUserCard };
""",
        ground_truth_patch="""--- a/renderer.js
+++ b/renderer.js
@@ -2,1 +2,5 @@
-    return `<div class="user-card"><span>${userName}</span></div>`;
+    const safe = String(userName)
+        .replace(/&/g, "&amp;")
+        .replace(/</g, "&lt;")
+        .replace(/>/g, "&gt;");
+    return `<div class="user-card"><span>${safe}</span></div>`;
""",
        ground_truth_code="""function renderUserCard(userName) {
    const safe = String(userName)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    return `<div class="user-card"><span>${safe}</span></div>`;
}
module.exports = { renderUserCard };
""",
        hidden_oracle_test="""const assert = require('assert');
const { renderUserCard } = require('./renderer.js');
const xss = "<script>alert(1)</script>";
const output = renderUserCard(xss);
assert.ok(!output.includes("<script>"));
assert.ok(output.includes("&lt;script&gt;"));
""",
        existing_tests="""const assert = require('assert');
const { renderUserCard } = require('./renderer.js');
assert.ok(renderUserCard("Alice").includes("Alice"));
""",
    ),
    EvaluationInstance(
        instance_id="JS-SEC-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.SECURITY,
        description="Path joining without directory traversal guard allows arbitrary file reads.",
        file_path="server.js",
        target_symbol="resolveFilePath",
        line_start=4,
        line_end=7,
        buggy_code="""const path = require('path');

function resolveFilePath(baseDir, userInput) {
    return path.join(baseDir, userInput);
}
module.exports = { resolveFilePath };
""",
        ground_truth_patch="""--- a/server.js
+++ b/server.js
@@ -4,2 +4,5 @@
-    return path.join(baseDir, userInput);
+    const target = path.resolve(baseDir, userInput);
+    if (!target.startsWith(path.resolve(baseDir))) {
+        throw new Error("Directory traversal detected");
+    }
+    return target;
""",
        ground_truth_code="""const path = require('path');

function resolveFilePath(baseDir, userInput) {
    const target = path.resolve(baseDir, userInput);
    if (!target.startsWith(path.resolve(baseDir))) {
        throw new Error("Directory traversal detected");
    }
    return target;
}
module.exports = { resolveFilePath };
""",
        hidden_oracle_test="""const assert = require('assert');
const { resolveFilePath } = require('./server.js');
assert.throws(() => {
    resolveFilePath("/var/www/static", "../../../etc/passwd");
}, /Directory traversal/);
""",
        existing_tests="""const assert = require('assert');
const { resolveFilePath } = require('./server.js');
const p = resolveFilePath("/var/www/static", "css/app.css");
assert.ok(p.includes("css/app.css"));
""",
    ),

    # =========================================================================
    # 5. CONCURRENCY-LITE (4 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-CONC-01",
        language=Language.PYTHON,
        category=BugCategory.CONCURRENCY_LITE,
        description="Mutable default argument in task enqueuer leaks shared state across invocations.",
        file_path="task_queue.py",
        target_symbol="enqueue_task",
        line_start=2,
        line_end=5,
        buggy_code="""def enqueue_task(task_name, queue=[]):
    queue.append(task_name)
    return queue
""",
        ground_truth_patch="""--- a/task_queue.py
+++ b/task_queue.py
@@ -1,2 +1,4 @@
-def enqueue_task(task_name, queue=[]):
+def enqueue_task(task_name, queue=None):
+    if queue is None:
+        queue = []
     queue.append(task_name)
""",
        ground_truth_code="""def enqueue_task(task_name, queue=None):
    if queue is None:
        queue = []
    queue.append(task_name)
    return queue
""",
        hidden_oracle_test="""def test_oracle_independent_queues():
    q1 = enqueue_task("task1")
    q2 = enqueue_task("task2")
    assert q1 == ["task1"]
    assert q2 == ["task2"]
""",
        existing_tests="""def test_existing_custom_queue():
    custom = ["prior"]
    res = enqueue_task("new", custom)
    assert res == ["prior", "new"]
""",
    ),
    EvaluationInstance(
        instance_id="PY-CONC-02",
        language=Language.PYTHON,
        category=BugCategory.CONCURRENCY_LITE,
        description="File handle opened without context manager leaks unclosed descriptor in generator.",
        file_path="file_reader.py",
        target_symbol="read_first_line",
        line_start=2,
        line_end=4,
        buggy_code="""def read_first_line(filepath):
    f = open(filepath, "r")
    return f.readline()
""",
        ground_truth_patch="""--- a/file_reader.py
+++ b/file_reader.py
@@ -2,2 +2,3 @@
-    f = open(filepath, "r")
-    return f.readline()
+    with open(filepath, "r") as f:
+        return f.readline()
""",
        ground_truth_code="""def read_first_line(filepath):
    with open(filepath, "r") as f:
        return f.readline()
""",
        hidden_oracle_test=r"""import tempfile
def test_oracle_resource_closed():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("first line\nsecond line\n")
        tf.flush()
        line = read_first_line(tf.name)
        assert line == "first line\n"
""",
        existing_tests="""def test_existing_dummy():
    assert callable(read_first_line)
""",
    ),
    EvaluationInstance(
        instance_id="JS-CONC-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.CONCURRENCY_LITE,
        description="forEach ignores async promise returns, returning before batch operations finish.",
        file_path="batch.js",
        target_symbol="processBatch",
        line_start=3,
        line_end=8,
        buggy_code="""async function processBatch(items, asyncFn) {
    const results = [];
    items.forEach(async (item) => {
        const res = await asyncFn(item);
        results.push(res);
    });
    return results;
}
module.exports = { processBatch };
""",
        ground_truth_patch="""--- a/batch.js
+++ b/batch.js
@@ -3,4 +3,5 @@
-    items.forEach(async (item) => {
-        const res = await asyncFn(item);
-        results.push(res);
-    });
+    for (const item of items) {
+        const res = await asyncFn(item);
+        results.push(res);
+    }
""",
        ground_truth_code="""async function processBatch(items, asyncFn) {
    const results = [];
    for (const item of items) {
        const res = await asyncFn(item);
        results.push(res);
    }
    return results;
}
module.exports = { processBatch };
""",
        hidden_oracle_test="""const assert = require('assert');
const { processBatch } = require('./batch.js');

async function test() {
    const sleep = (n) => new Promise(resolve => setTimeout(() => resolve(n * 2), 10));
    const out = await processBatch([1, 2], sleep);
    assert.strictEqual(out.length, 2);
    assert.deepStrictEqual(out, [2, 4]);
}
test();
""",
        existing_tests="""const assert = require('assert');
const { processBatch } = require('./batch.js');
async function test() {
    const out = await processBatch([], async x => x);
    assert.deepStrictEqual(out, []);
}
test();
""",
    ),
    EvaluationInstance(
        instance_id="JS-CONC-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.CONCURRENCY_LITE,
        description="Async operation without catch block causes unhandled promise rejection.",
        file_path="fetcher.js",
        target_symbol="fetchDataWithFallback",
        line_start=2,
        line_end=5,
        buggy_code="""async function fetchDataWithFallback(fetchPromise, fallback) {
    const data = await fetchPromise;
    return data;
}
module.exports = { fetchDataWithFallback };
""",
        ground_truth_patch="""--- a/fetcher.js
+++ b/fetcher.js
@@ -2,2 +2,6 @@
-    const data = await fetchPromise;
-    return data;
+    try {
+        const data = await fetchPromise;
+        return data;
+    } catch (e) {
+        return fallback;
+    }
""",
        ground_truth_code="""async function fetchDataWithFallback(fetchPromise, fallback) {
    try {
        const data = await fetchPromise;
        return data;
    } catch (e) {
        return fallback;
    }
}
module.exports = { fetchDataWithFallback };
""",
        hidden_oracle_test="""const assert = require('assert');
const { fetchDataWithFallback } = require('./fetcher.js');

async function test() {
    const failing = Promise.reject(new Error("Network fail"));
    const res = await fetchDataWithFallback(failing, "cached_fallback");
    assert.strictEqual(res, "cached_fallback");
}
test();
""",
        existing_tests="""const assert = require('assert');
const { fetchDataWithFallback } = require('./fetcher.js');

async function test() {
    const success = Promise.resolve("live_data");
    const res = await fetchDataWithFallback(success, "cached_fallback");
    assert.strictEqual(res, "live_data");
}
test();
""",
    ),

    # =========================================================================
    # 6. WRONG OPERATOR (4 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-WRO-01",
        language=Language.PYTHON,
        category=BugCategory.WRONG_OPERATOR,
        description="Identity operator 'is' used for value comparison on integer threshold.",
        file_path="pricing.py",
        target_symbol="apply_tier_discount",
        line_start=2,
        line_end=5,
        buggy_code="""def apply_tier_discount(tier_code, price):
    if tier_code is 1000:
        return price * 0.9
    return price
""",
        ground_truth_patch="""--- a/pricing.py
+++ b/pricing.py
@@ -2,1 +2,1 @@
-    if tier_code is 1000:
+    if tier_code == 1000:
""",
        ground_truth_code="""def apply_tier_discount(tier_code, price):
    if tier_code == 1000:
        return price * 0.9
    return price
""",
        hidden_oracle_test="""def test_oracle_tier_discount():
    # Large int dynamically parsed won't share id in Python
    code = int("1000")
    assert apply_tier_discount(code, 100.0) == 90.0
""",
        existing_tests="""def test_existing_other_tier():
    assert apply_tier_discount(200, 100.0) == 100.0
""",
    ),
    EvaluationInstance(
        instance_id="PY-WRO-02",
        language=Language.PYTHON,
        category=BugCategory.WRONG_OPERATOR,
        description="Logical OR instead of AND in range boundary check accepts negative numbers.",
        file_path="validator.py",
        target_symbol="is_valid_age",
        line_start=2,
        line_end=4,
        buggy_code="""def is_valid_age(age):
    return age > 0 or age < 120
""",
        ground_truth_patch="""--- a/validator.py
+++ b/validator.py
@@ -2,1 +2,1 @@
-    return age > 0 or age < 120
+    return age >= 0 and age <= 120
""",
        ground_truth_code="""def is_valid_age(age):
    return age >= 0 and age <= 120
""",
        hidden_oracle_test="""def test_oracle_negative_age():
    assert is_valid_age(-5) is False
    assert is_valid_age(150) is False
    assert is_valid_age(25) is True
""",
        existing_tests="""def test_existing_normal_age():
    assert is_valid_age(30) is True
""",
    ),
    EvaluationInstance(
        instance_id="JS-WRO-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.WRONG_OPERATOR,
        description="Assignment operator '=' in if condition erroneously overwrites variable.",
        file_path="auth.js",
        target_symbol="isAdmin",
        line_start=2,
        line_end=5,
        buggy_code="""function isAdmin(userRole) {
    if (userRole = "admin") {
        return true;
    }
    return false;
}
module.exports = { isAdmin };
""",
        ground_truth_patch="""--- a/auth.js
+++ b/auth.js
@@ -2,1 +2,1 @@
-    if (userRole = "admin") {
+    if (userRole === "admin") {
""",
        ground_truth_code="""function isAdmin(userRole) {
    if (userRole === "admin") {
        return true;
    }
    return false;
}
module.exports = { isAdmin };
""",
        hidden_oracle_test="""const assert = require('assert');
const { isAdmin } = require('./auth.js');
assert.strictEqual(isAdmin("guest"), false);
assert.strictEqual(isAdmin("user"), false);
assert.strictEqual(isAdmin("admin"), true);
""",
        existing_tests="""const assert = require('assert');
const { isAdmin } = require('./auth.js');
assert.strictEqual(isAdmin("admin"), true);
""",
    ),
    EvaluationInstance(
        instance_id="JS-WRO-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.WRONG_OPERATOR,
        description="Direct equality check val === NaN always evaluates to false in JavaScript.",
        file_path="math_utils.js",
        target_symbol="checkNaN",
        line_start=2,
        line_end=5,
        buggy_code="""function checkNaN(val) {
    if (val === NaN) {
        return true;
    }
    return false;
}
module.exports = { checkNaN };
""",
        ground_truth_patch="""--- a/math_utils.js
+++ b/math_utils.js
@@ -2,1 +2,1 @@
-    if (val === NaN) {
+    if (Number.isNaN(val)) {
""",
        ground_truth_code="""function checkNaN(val) {
    if (Number.isNaN(val)) {
        return true;
    }
    return false;
}
module.exports = { checkNaN };
""",
        hidden_oracle_test="""const assert = require('assert');
const { checkNaN } = require('./math_utils.js');
assert.strictEqual(checkNaN(NaN), true);
assert.strictEqual(checkNaN(42), false);
""",
        existing_tests="""const assert = require('assert');
const { checkNaN } = require('./math_utils.js');
assert.strictEqual(checkNaN(100), false);
""",
    ),

    # =========================================================================
    # 7. BOUNDARY (4 bugs)
    # =========================================================================
    EvaluationInstance(
        instance_id="PY-BND-01",
        language=Language.PYTHON,
        category=BugCategory.BOUNDARY,
        description="Binary search loop condition low < high misses elements located at the upper bound.",
        file_path="search.py",
        target_symbol="binary_search",
        line_start=3,
        line_end=9,
        buggy_code="""def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
""",
        ground_truth_patch="""--- a/search.py
+++ b/search.py
@@ -4,1 +4,1 @@
-    while low < high:
+    while low <= high:
""",
        ground_truth_code="""def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
""",
        hidden_oracle_test="""def test_oracle_single_element_and_upper_bound():
    assert binary_search([5], 5) == 0
    assert binary_search([1, 3, 5], 5) == 2
""",
        existing_tests="""def test_existing_mid_find():
    assert binary_search([1, 3, 5], 3) == 1
    assert binary_search([1, 3, 5], 99) == -1
""",
    ),
    EvaluationInstance(
        instance_id="PY-BND-02",
        language=Language.PYTHON,
        category=BugCategory.BOUNDARY,
        description="Timestamp window check uses strict inequality, excluding the inclusive start second.",
        file_path="scheduler.py",
        target_symbol="is_in_window",
        line_start=2,
        line_end=4,
        buggy_code="""def is_in_window(current_ts, start_ts, end_ts):
    return start_ts < current_ts < end_ts
""",
        ground_truth_patch="""--- a/scheduler.py
+++ b/scheduler.py
@@ -2,1 +2,1 @@
-    return start_ts < current_ts < end_ts
+    return start_ts <= current_ts <= end_ts
""",
        ground_truth_code="""def is_in_window(current_ts, start_ts, end_ts):
    return start_ts <= current_ts <= end_ts
""",
        hidden_oracle_test="""def test_oracle_exact_boundary():
    assert is_in_window(100, 100, 200) is True
    assert is_in_window(200, 100, 200) is True
""",
        existing_tests="""def test_existing_middle():
    assert is_in_window(150, 100, 200) is True
    assert is_in_window(50, 100, 200) is False
""",
    ),
    EvaluationInstance(
        instance_id="JS-BND-01",
        language=Language.JAVASCRIPT,
        category=BugCategory.BOUNDARY,
        description="Math.min with empty array spreads to Math.min() returning Infinity.",
        file_path="summary.js",
        target_symbol="getMinScore",
        line_start=2,
        line_end=4,
        buggy_code="""function getMinScore(scores) {
    return Math.min(...scores);
}
module.exports = { getMinScore };
""",
        ground_truth_patch="""--- a/summary.js
+++ b/summary.js
@@ -2,1 +2,1 @@
-    return Math.min(...scores);
+    return !scores || scores.length === 0 ? 0 : Math.min(...scores);
""",
        ground_truth_code="""function getMinScore(scores) {
    return !scores || scores.length === 0 ? 0 : Math.min(...scores);
}
module.exports = { getMinScore };
""",
        hidden_oracle_test="""const assert = require('assert');
const { getMinScore } = require('./summary.js');
assert.strictEqual(getMinScore([]), 0);
""",
        existing_tests="""const assert = require('assert');
const { getMinScore } = require('./summary.js');
assert.strictEqual(getMinScore([5, 2, 9]), 2);
""",
    ),
    EvaluationInstance(
        instance_id="JS-BND-02",
        language=Language.JAVASCRIPT,
        category=BugCategory.BOUNDARY,
        description="Circular buffer head index increment does not wrap around with modulo capacity.",
        file_path="circularBuffer.js",
        target_symbol="push",
        line_start=6,
        line_end=11,
        buggy_code="""class CircularBuffer {
    constructor(capacity) {
        this.capacity = capacity;
        this.buffer = new Array(capacity);
        this.head = 0;
    }
    push(item) {
        this.buffer[this.head] = item;
        this.head = this.head + 1;
    }
}
module.exports = { CircularBuffer };
""",
        ground_truth_patch="""--- a/circularBuffer.js
+++ b/circularBuffer.js
@@ -8,1 +8,1 @@
-        this.head = this.head + 1;
+        this.head = (this.head + 1) % this.capacity;
""",
        ground_truth_code="""class CircularBuffer {
    constructor(capacity) {
        this.capacity = capacity;
        this.buffer = new Array(capacity);
        this.head = 0;
    }
    push(item) {
        this.buffer[this.head] = item;
        this.head = (this.head + 1) % this.capacity;
    }
}
module.exports = { CircularBuffer };
""",
        hidden_oracle_test="""const assert = require('assert');
const { CircularBuffer } = require('./circularBuffer.js');
const cb = new CircularBuffer(2);
cb.push("a");
cb.push("b");
cb.push("c"); // Should wrap around to head = 1 and buffer[0] = "c"
assert.strictEqual(cb.head, 1);
assert.strictEqual(cb.buffer[0], "c");
""",
        existing_tests="""const assert = require('assert');
const { CircularBuffer } = require('./circularBuffer.js');
const cb = new CircularBuffer(3);
cb.push("a");
assert.strictEqual(cb.head, 1);
assert.strictEqual(cb.buffer[0], "a");
""",
    ),
]


def get_seeded_dataset() -> List[EvaluationInstance]:
    """Returns the full benchmark dataset of 30 seeded bugs."""
    return list(SEEDED_BUGS)
