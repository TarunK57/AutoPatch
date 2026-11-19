from __future__ import annotations

import tempfile
from pathlib import Path
from autopatch.verifier.sandbox import EphemeralSandbox


def test_sandbox_outbound_network_attempt_strictly_fails():
    """
    Acceptance criterion: A test attempting outbound network from the sandbox fails.
    Verifies that socket.connect or socket creation fails with PermissionError / network blocked.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)

        # Write test that attempts outbound network connection to external IP/port
        test_file = proj_dir / "test_malicious_network.py"
        test_file.write_text(
            "import socket\n"
            "import pytest\n\n"
            "def test_exfiltrate_network():\n"
            "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "    s.connect(('8.8.8.8', 53))\n"
            "    assert True\n",
            encoding="utf-8",
        )

        sandbox = EphemeralSandbox(timeout_seconds=10)
        result = sandbox.run_tests(proj_dir, "python3 -m pytest test_malicious_network.py")

        # Invariant: Must fail due to forbidden network access
        assert result.exit_code != 0
        assert result.failed >= 1 or result.errors >= 1 or "PermissionError" in (result.stdout + result.stderr)
        assert "Network access is strictly forbidden" in (result.stdout + result.stderr) or "PermissionError" in (result.stdout + result.stderr)
        assert result.sandbox_network_disabled is True


def test_sandbox_host_filesystem_escape_attempt_fails():
    """Verify that an attempt to access host sensitive files from inside sandbox is blocked."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = Path(tmp_dir)

        test_file = proj_dir / "test_host_escape.py"
        test_file.write_text(
            "import pytest\n\n"
            "def test_read_etc_passwd():\n"
            "    with open('/etc/passwd', 'r') as f:\n"
            "        data = f.read()\n"
            "    assert False, 'Should not reach here'\n",
            encoding="utf-8",
        )

        sandbox = EphemeralSandbox(timeout_seconds=10)
        result = sandbox.run_tests(proj_dir, "python3 -m pytest test_host_escape.py")

        assert result.exit_code != 0
        assert "PermissionError" in (result.stdout + result.stderr) or "forbidden inside sandbox" in (result.stdout + result.stderr)


def test_sandbox_docker_command_hardening_flags():
    """Verify that the Docker command includes all STRIDE hardening flags."""
    sandbox = EphemeralSandbox(
        memory_limit="512m",
        cpu_limit="0.5",
        pids_limit=64,
        user="1000:1000",
    )
    cmd = sandbox.build_docker_run_command(Path("/tmp/snapshot"), "pytest")

    assert "--network" in cmd
    idx_net = cmd.index("--network")
    assert cmd[idx_net + 1] == "none"

    assert "--read-only" in cmd
    assert "--tmpfs" in cmd
    assert "--user" in cmd
    assert "1000:1000" in cmd
    assert "--memory" in cmd
    assert "512m" in cmd
    assert "--pids-limit" in cmd
    assert "64" in cmd
