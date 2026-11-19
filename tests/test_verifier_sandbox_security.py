"""Unit tests verifying sandbox security isolation and containment (Rule 4).

Acceptance Criteria:
- A deliberately malicious test cannot reach the network (PermissionError on socket).
- A deliberately malicious test cannot read sensitive host files (/etc/passwd, ~/.ssh).
- Output exceeding 500KB is capped.
- Timed-out execution is halted safely.
"""

import tempfile
from pathlib import Path
import pytest

from autopatch.verifier.sandbox import EphemeralSandbox, MAX_OUTPUT_BYTES
from autopatch.verifier.models import SingleTestStatus


def test_malicious_test_cannot_reach_network():
    """Rule 4: All untrusted code runs in a network-disabled sandbox."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        test_file = proj / "test_malicious_network.py"
        test_file.write_text(
            """import socket
def test_outbound_connection():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("8.8.8.8", 53))
"""
        )

        sandbox = EphemeralSandbox(timeout_seconds=5)
        res = sandbox.run_tests(proj, f"pytest {test_file.name}")

        assert not res.is_success
        assert res.failed > 0 or res.errors > 0
        assert "Network access is strictly forbidden" in (res.stdout + res.stderr)
        assert res.sandbox_network_disabled is True


def test_malicious_test_cannot_access_host_sensitive_files():
    """Security: Host file reads outside the sandbox are rejected."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        test_file = proj / "test_malicious_fs.py"
        test_file.write_text(
            """def test_read_host_passwd():
    with open("/etc/passwd", "r") as f:
        _ = f.read()
"""
        )

        sandbox = EphemeralSandbox(timeout_seconds=5)
        res = sandbox.run_tests(proj, f"pytest {test_file.name}")

        assert not res.is_success
        assert res.failed > 0 or res.errors > 0
        assert "forbidden" in (res.stdout + res.stderr).lower()


def test_sandbox_output_size_capping():
    """Output ceiling: prevents memory exhaustion from runaway spam output."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        test_file = proj / "test_spam.py"
        test_file.write_text(
            """def test_huge_stdout():
    print("A" * (600 * 1024))
    assert True
"""
        )

        sandbox = EphemeralSandbox(timeout_seconds=5)
        res = sandbox.run_tests(proj, f"pytest -s {test_file.name}")

        assert res.output_truncated is True
        assert "[TRUNCATED BY OUTPUT SIZE CAP]" in res.stdout
        assert len(res.stdout.encode("utf-8")) <= MAX_OUTPUT_BYTES + 1024


def test_sandbox_timeout_enforcement():
    """Timeout ceiling: halts infinite loops within specified timeout."""
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        test_file = proj / "test_hang.py"
        test_file.write_text(
            """import time
def test_infinite_loop():
    while True:
        time.sleep(0.1)
"""
        )

        sandbox = EphemeralSandbox(timeout_seconds=1)
        res = sandbox.run_tests(proj, f"pytest {test_file.name}")

        assert not res.is_success
        assert res.exit_code == 124
        assert "timed out after 1s limit" in res.stderr


def test_docker_command_security_flags():
    """Validates that Docker execution flags enforce all non-negotiable security controls."""
    sandbox = EphemeralSandbox(
        memory_limit="512m",
        cpu_limit="0.5",
        pids_limit=50,
        user="1001:1001",
        docker_image="custom-test-image:v1",
    )
    fake_path = Path("/tmp/fake_project")
    cmd = sandbox.build_docker_run_command(fake_path, "pytest tests/")

    # Assert Docker security invariants
    assert "docker" in cmd[0]
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd and "/tmp:rw,noexec,nosuid" in cmd[cmd.index("--tmpfs") + 1]
    assert "--memory" in cmd and cmd[cmd.index("--memory") + 1] == "512m"
    assert "--cpus" in cmd and cmd[cmd.index("--cpus") + 1] == "0.5"
    assert "--pids-limit" in cmd and cmd[cmd.index("--pids-limit") + 1] == "50"
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "1001:1001"
    assert "-v" in cmd and f"{fake_path.resolve()}:/workspace:ro" in cmd
    assert "-w" in cmd and cmd[cmd.index("-w") + 1] == "/workspace"
    assert "custom-test-image:v1" in cmd

