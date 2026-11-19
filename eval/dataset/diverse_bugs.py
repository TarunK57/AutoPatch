"""Diverse, unseeded real-world benchmark instances for AutoPatch evaluation.

Provides complex, multi-branch, and non-canonical defect patterns to evaluate
generalization beyond template-matching, honest reporting of regressions,
false positives, and false negatives.
"""

from __future__ import annotations

from typing import List
from eval.dataset.models import BugCategory, EvaluationInstance, Language

DIVERSE_BUGS: List[EvaluationInstance] = [
    EvaluationInstance(
        instance_id="DIV-PY-STATE-01",
        language=Language.PYTHON,
        category=BugCategory.BOUNDARY,
        description="Transaction state machine transitions to TERMINATED on retry without decrementing pending retries counter, leaving ledger unbalanced.",
        file_path="tx_processor.py",
        target_symbol="process_retry",
        line_start=14,
        line_end=20,
        buggy_code="""class TransactionProcessor:
    def __init__(self):
        self.state = "PENDING"
        self.retries_left = 3
        self.ledger_balanced = True

    def process_retry(self, tx_id, error_code):
        if self.retries_left <= 0:
            self.state = "TERMINATED"
            self.ledger_balanced = False
            return False
        # Bug: transition drops retry count directly to 0 on network error
        if error_code == "NET_TIMEOUT":
            self.state = "FAILED"
            self.retries_left = 0
            return False
        self.retries_left -= 1
        return True
""",
        ground_truth_patch="""--- a/tx_processor.py
+++ b/tx_processor.py
@@ -14,3 +14,3 @@
-        if error_code == "NET_TIMEOUT":
-            self.state = "FAILED"
-            self.retries_left = 0
+        if error_code == "NET_TIMEOUT":
+            self.retries_left -= 1
+            self.state = "RETRYING" if self.retries_left > 0 else "FAILED"
""",
        ground_truth_code="""class TransactionProcessor:
    def __init__(self):
        self.state = "PENDING"
        self.retries_left = 3
        self.ledger_balanced = True

    def process_retry(self, tx_id, error_code):
        if self.retries_left <= 0:
            self.state = "TERMINATED"
            self.ledger_balanced = False
            return False
        if error_code == "NET_TIMEOUT":
            self.retries_left -= 1
            self.state = "RETRYING" if self.retries_left > 0 else "FAILED"
            return False
        self.retries_left -= 1
        return True
""",
        hidden_oracle_test="""def test_oracle_net_timeout_allows_remaining_retries():
    proc = TransactionProcessor()
    proc.process_retry("tx_1", "NET_TIMEOUT")
    assert proc.retries_left == 2, f"Expected 2 retries left, got {proc.retries_left}"
    assert proc.state == "RETRYING"
""",
        existing_tests="""def test_existing_normal_retry():
    proc = TransactionProcessor()
    assert proc.process_retry("tx_1", "NORMAL") is True
    assert proc.retries_left == 2
""",
    ),
    EvaluationInstance(
        instance_id="DIV-PY-TRAP-02",
        language=Language.PYTHON,
        category=BugCategory.NULL_ACCESS,
        description="Deeply nested configuration dictionary lookup crashes on missing intermediate namespace key.",
        file_path="config_resolver.py",
        target_symbol="resolve_endpoint",
        line_start=3,
        line_end=6,
        buggy_code="""def resolve_endpoint(cfg, service_name):
    # Buggy: assumes 'services' and service_name always exist as non-null dicts
    host = cfg["services"][service_name]["host"]
    port = cfg["services"][service_name].get("port", 8080)
    return f"http://{host}:{port}"
""",
        ground_truth_patch="""--- a/config_resolver.py
+++ b/config_resolver.py
@@ -2,4 +2,6 @@
-    host = cfg["services"][service_name]["host"]
-    port = cfg["services"][service_name].get("port", 8080)
+    services = cfg.get("services") or {}
+    svc = services.get(service_name)
+    if not svc or "host" not in svc:
+        return None
+    host = svc["host"]
+    port = svc.get("port", 8080)
""",
        ground_truth_code="""def resolve_endpoint(cfg, service_name):
    services = cfg.get("services") or {}
    svc = services.get(service_name)
    if not svc or "host" not in svc:
        return None
    host = svc["host"]
    port = svc.get("port", 8080)
    return f"http://{host}:{port}"
""",
        hidden_oracle_test="""def test_oracle_missing_service():
    cfg = {"services": {}}
    res = resolve_endpoint(cfg, "payment")
    assert res is None, "Should safely return None for missing service"

def test_oracle_none_services():
    cfg = {"services": None}
    res = resolve_endpoint(cfg, "payment")
    assert res is None, "Should safely return None when services is None"
""",
        existing_tests="""def test_existing_valid_service():
    cfg = {"services": {"auth": {"host": "auth.internal", "port": 443}}}
    res = resolve_endpoint(cfg, "auth")
    assert res == "http://auth.internal:443"
""",
    ),
    EvaluationInstance(
        instance_id="DIV-PY-REGRESS-03",
        language=Language.PYTHON,
        category=BugCategory.VALIDATION,
        description="Rate limiter token replenishment calculation overflows on future timestamp and clamps incorrectly.",
        file_path="rate_limiter.py",
        target_symbol="consume_token",
        line_start=9,
        line_end=15,
        buggy_code="""class TokenBucket:
    def __init__(self, capacity=10, refill_rate=1.0):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = 0.0

    def consume(self, amount, now_ts):
        elapsed = now_ts - self.last_refill
        # Buggy: negative elapsed time from unsynced clocks causes negative tokens
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now_ts
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False
""",
        ground_truth_patch="""--- a/rate_limiter.py
+++ b/rate_limiter.py
@@ -9,2 +9,3 @@
         elapsed = now_ts - self.last_refill
+        if elapsed > 0:
+            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
+            self.last_refill = now_ts
-        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
-        self.last_refill = now_ts
""",
        ground_truth_code="""class TokenBucket:
    def __init__(self, capacity=10, refill_rate=1.0):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = 0.0

    def consume(self, amount, now_ts):
        elapsed = now_ts - self.last_refill
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now_ts
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False
""",
        hidden_oracle_test="""def test_oracle_clock_skew_backwards():
    bucket = TokenBucket(capacity=5, refill_rate=1.0)
    bucket.consume(1, 100.0)
    # Clock skew backwards: timestamp goes from 100.0 to 95.0
    res = bucket.consume(1, 95.0)
    assert res is True, "Clock skew backwards should not deplete existing tokens"
    assert bucket.tokens >= 0
""",
        existing_tests="""def test_existing_standard_consume():
    bucket = TokenBucket(capacity=10, refill_rate=2.0)
    assert bucket.consume(5, 0.0) is True
    assert bucket.tokens == 5
""",
    ),
    EvaluationInstance(
        instance_id="DIV-JS-PROMISE-04",
        language=Language.JAVASCRIPT,
        category=BugCategory.CONCURRENCY_LITE,
        description="Async cache memoizer returns shared in-flight promise without catching rejections, causing unhandled rejection cascades.",
        file_path="memoizer.js",
        target_symbol="fetchCached",
        line_start=5,
        line_end=12,
        buggy_code="""const cache = new Map();

function fetchCached(key, fetcher) {
    if (cache.has(key)) {
        return cache.get(key);
    }
    const promise = fetcher();
    cache.set(key, promise);
    return promise;
}

module.exports = { fetchCached, cache };
""",
        ground_truth_patch="""--- a/memoizer.js
+++ b/memoizer.js
@@ -7,2 +7,5 @@
     const promise = fetcher().catch(err => {
+        cache.delete(key);
+        return Promise.reject(err);
+    });
     cache.set(key, promise);
""",
        ground_truth_code="""const cache = new Map();

function fetchCached(key, fetcher) {
    if (cache.has(key)) {
        return cache.get(key);
    }
    const promise = fetcher().catch(err => {
        cache.delete(key);
        return Promise.reject(err);
    });
    cache.set(key, promise);
    return promise;
}

module.exports = { fetchCached, cache };
""",
        hidden_oracle_test="""const assert = require('assert');
const { fetchCached, cache } = require('./memoizer.js');

async function testOracle() {
    cache.clear();
    let calls = 0;
    const failingFetcher = () => {
        calls++;
        return Promise.reject(new Error("Network fail"));
    };

    try {
        await fetchCached("key1", failingFetcher);
    } catch (e) {}

    // On failure, cache entry must be purged so next call retries
    assert.strictEqual(cache.has("key1"), false, "Failed promise must be evicted from cache");
    console.log("ALL_ORACLE_PASSED");
}
testOracle();
""",
        existing_tests="""const assert = require('assert');
const { fetchCached, cache } = require('./memoizer.js');

async function testExisting() {
    cache.clear();
    let calls = 0;
    const fetcher = async () => { calls++; return "data"; };
    const res1 = await fetchCached("k1", fetcher);
    const res2 = await fetchCached("k1", fetcher);
    assert.strictEqual(res1, "data");
    assert.strictEqual(res2, "data");
    assert.strictEqual(calls, 1);
    console.log("ALL_EXISTING_PASSED");
}
testExisting();
""",
    ),
]


def get_diverse_dataset() -> List[EvaluationInstance]:
    """Returns the curated diverse non-seeded evaluation instances."""
    return [inst.model_copy(deep=True) for inst in DIVERSE_BUGS]
