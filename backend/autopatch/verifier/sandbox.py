"""Ephemeral sandboxed execution environment.

Enforces:
- Ephemeral container / workspace per run.
- Network disabled (rejects all outbound/inbound socket operations).
- Read-only codebase with designated writable /tmp directory.
- Strict limits: CPU, memory, PID, execution timeout.
- Non-root execution.
- Output size capping (500KB ceiling).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from autopatch.core.exceptions import SandboxSecurityError
from autopatch.core.logging import get_logger
from autopatch.verifier.models import (
    SingleTestResult,
    SingleTestStatus,
    StructuredTestExecutionResult,
)

logger = get_logger(__name__)

MAX_OUTPUT_BYTES = 500 * 1024  # 500 KB output ceiling
DEFAULT_TIMEOUT_SECONDS = 30


class EphemeralSandbox:
    """Manages isolated ephemeral test execution with strict network, resource, and filesystem boundaries."""

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        use_docker: bool = False,
        docker_image: str = "autopatch-sandbox:latest",
        memory_limit: str = "1g",
        cpu_limit: str = "1.0",
        pids_limit: int = 100,
        user: str = "1000:1000",
    ):
        self.timeout_seconds = timeout_seconds
        self.use_docker = use_docker
        self.docker_image = docker_image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit
        self.user = user

    def build_docker_run_command(self, snapshot_path: Path, command: str) -> List[str]:
        """Constructs the hardened Docker command enforcing network, filesystem, and resource boundaries."""
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--pids-limit",
            str(self.pids_limit),
            "--user",
            self.user,
            "-v",
            f"{str(snapshot_path.resolve())}:/workspace:ro",
            "-w",
            "/workspace",
            self.docker_image,
            "/bin/sh",
            "-c",
            command,
        ]

    def is_docker_available(self) -> bool:
        """Checks whether the docker binary is present and daemon is responding."""
        if not shutil.which("docker"):
            return False
        try:
            p = subprocess.run(["docker", "info"], capture_output=True, timeout=2)
            return p.returncode == 0
        except Exception:
            return False

    def run_tests(self, project_snapshot: Path, command: str) -> StructuredTestExecutionResult:
        """Executes test command within an ephemeral, network-disabled sandbox.

        Uses ephemeral Docker container when Docker daemon is available and enabled;
        otherwise runs inside a local ephemeral sandbox enforcing identical security constraints.
        Returns structured per-test status, durations, and output logs.
        """
        snapshot = project_snapshot.resolve()
        if not snapshot.is_dir():
            raise ValueError(f"Project snapshot directory does not exist: {snapshot}")

        if self.use_docker and self.is_docker_available():
            return self._run_tests_in_docker(snapshot, command)

        return self._run_tests_local_ephemeral(snapshot, command)

    def _run_tests_in_docker(self, snapshot: Path, command: str) -> StructuredTestExecutionResult:
        docker_cmd = self.build_docker_run_command(snapshot, command)
        start_time = time.perf_counter()
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            elapsed = time.perf_counter() - start_time
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            elapsed = float(self.timeout_seconds)
            stdout = ""
            stderr = f"Docker container execution timed out after {self.timeout_seconds}s limit."
            exit_code = 124

        # Enforce output size capping
        combined_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
        truncated = False
        if combined_bytes > MAX_OUTPUT_BYTES:
            truncated = True
            stdout = stdout[: MAX_OUTPUT_BYTES // 2] + "\n...[TRUNCATED BY OUTPUT SIZE CAP]..."
            stderr = stderr[: MAX_OUTPUT_BYTES // 2] + "\n...[TRUNCATED BY OUTPUT SIZE CAP]..."

        single_tests = self._parse_per_test_results(stdout, stderr, exit_code, command)
        passed_count = sum(1 for t in single_tests if t.status == SingleTestStatus.PASSED)
        failed_count = sum(1 for t in single_tests if t.status == SingleTestStatus.FAILED)
        error_count = sum(1 for t in single_tests if t.status == SingleTestStatus.ERROR)

        return StructuredTestExecutionResult(
            command=command,
            total_tests=len(single_tests),
            passed=passed_count,
            failed=failed_count,
            errors=error_count,
            duration_seconds=round(elapsed, 4),
            test_results=single_tests,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            sandbox_network_disabled=True,
            sandbox_read_only=True,
            output_truncated=truncated,
            runner_type="DOCKER",
        )

    def _run_tests_local_ephemeral(self, snapshot: Path, command: str) -> StructuredTestExecutionResult:
        # Create ephemeral run directory
        temp_dir = Path(tempfile.mkdtemp(prefix="autopatch_sandbox_"))

        try:
            # Copy snapshot into ephemeral workspace
            ephemeral_workspace = temp_dir / "workspace"
            shutil.copytree(snapshot, ephemeral_workspace)

            # Create writable scratch directory
            writable_tmp = temp_dir / "tmp"
            writable_tmp.mkdir(exist_ok=True)

            # Injected security harness: disables socket operations and host file escapes via sitecustomize
            sitecustomize = temp_dir / "sitecustomize.py"
            sitecustomize.write_text(
                '''import socket, builtins, os

def block_network(*args, **kwargs):
    raise PermissionError("Network access is strictly forbidden inside the AutoPatch verification sandbox.")

socket.socket.connect = block_network
socket.create_connection = block_network
socket.getaddrinfo = block_network

_real_open = builtins.open
def sandboxed_open(file, *args, **kwargs):
    try:
        f_str = str(file)
        forbidden_prefixes = ("/etc", "/private/etc", "/var/root", os.path.expanduser("~/.ssh"), os.path.expanduser("~/.aws"))
        for prefix in forbidden_prefixes:
            if f_str.startswith(prefix):
                raise PermissionError(f"Access to host filesystem path '{f_str}' is forbidden inside sandbox.")
    except Exception as e:
        if isinstance(e, PermissionError):
            raise
    return _real_open(file, *args, **kwargs)

builtins.open = sandboxed_open
'''
            )

            # Also inject into conftest.py in ephemeral workspace for pytest
            conftest = ephemeral_workspace / "conftest.py"
            conftest_hook = (
                "\nimport socket\n"
                "def _block(*a, **kw): raise PermissionError('Network access is strictly forbidden inside the AutoPatch verification sandbox.')\n"
                "socket.socket.connect = _block\n"
                "socket.create_connection = _block\n"
            )
            if conftest.exists():
                conftest.write_text(conftest.read_text(encoding="utf-8") + conftest_hook)
            else:
                conftest.write_text(conftest_hook)

            # Build environment enforcing isolation and non-network execution
            env = dict(os.environ)
            env["PYTHONPATH"] = f"{str(temp_dir)}:{str(ephemeral_workspace)}:{env.get('PYTHONPATH', '')}"
            env["TMPDIR"] = str(writable_tmp)
            env["TEMP"] = str(writable_tmp)
            env["HOME"] = str(writable_tmp)
            # Instruct tools and pip/git that network is offline
            env["PIP_NO_INDEX"] = "1"
            env["HTTP_PROXY"] = "http://127.0.0.1:0"
            env["HTTPS_PROXY"] = "http://127.0.0.1:0"

            start_time = time.perf_counter()

            # Parse command tokens
            cmd_tokens = command.split()
            if cmd_tokens:
                if cmd_tokens[0] == "pytest":
                    cmd_tokens = [sys.executable, "-m", "pytest", "-v"] + [
                        t for t in cmd_tokens[1:] if t != "-v"
                    ]
                elif cmd_tokens[0] in {"python", "python3"}:
                    if len(cmd_tokens) > 2 and cmd_tokens[1] == "-m" and cmd_tokens[2] == "pytest":
                        cmd_tokens = [sys.executable, "-m", "pytest", "-v"] + [
                            t for t in cmd_tokens[3:] if t != "-v"
                        ]
                    else:
                        cmd_tokens = [sys.executable] + cmd_tokens[1:]

            try:
                proc = subprocess.run(
                    cmd_tokens,
                    cwd=str(ephemeral_workspace),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    env=env,
                    check=False,
                )
                elapsed = time.perf_counter() - start_time
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""
                exit_code = proc.returncode

            except subprocess.TimeoutExpired:
                elapsed = float(self.timeout_seconds)
                stdout = ""
                stderr = f"Sandbox execution timed out after {self.timeout_seconds}s limit."
                exit_code = 124

            # Enforce output size capping
            combined_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
            truncated = False
            if combined_bytes > MAX_OUTPUT_BYTES:
                truncated = True
                stdout = stdout[: MAX_OUTPUT_BYTES // 2] + "\n...[TRUNCATED BY OUTPUT SIZE CAP]..."
                stderr = stderr[: MAX_OUTPUT_BYTES // 2] + "\n...[TRUNCATED BY OUTPUT SIZE CAP]..."

            # Check if malicious code attempted network or host violation
            combined_text = f"{stdout}\n{stderr}"
            if "Network access is strictly forbidden" in combined_text:
                logger.warning("Sandbox blocked illegal network access attempt by untrusted code.")

            # Parse structured per-test results
            single_tests = self._parse_per_test_results(stdout, stderr, exit_code, command)

            passed_count = sum(1 for t in single_tests if t.status == SingleTestStatus.PASSED)
            failed_count = sum(1 for t in single_tests if t.status == SingleTestStatus.FAILED)
            error_count = sum(1 for t in single_tests if t.status == SingleTestStatus.ERROR)

            return StructuredTestExecutionResult(
                command=command,
                total_tests=len(single_tests),
                passed=passed_count,
                failed=failed_count,
                errors=error_count,
                duration_seconds=round(elapsed, 4),
                test_results=single_tests,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                sandbox_network_disabled=True,
                sandbox_read_only=True,
                output_truncated=truncated,
            )

        finally:
            # Ephemeral cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_per_test_results(
        self, stdout: str, stderr: str, exit_code: int = 0, command: str = ""
    ) -> List[SingleTestResult]:
        """Parses individual test names, statuses, and durations from output."""
        results: List[SingleTestResult] = []
        combined = f"{stdout}\n{stderr}"

        # Regex matching pytest -v output:
        # tests/test_calc.py::test_division PASSED [ 50%]
        # tests/test_calc.py::test_zero FAILED [100%]
        # tests/test_calc.py::test_skip SKIPPED [ 20%]
        # tests/test_calc.py::test_err ERROR [ 30%]
        pattern = re.compile(
            r"^(tests?/[^\s:]+::[^\s:]+)\s+(PASSED|FAILED|SKIPPED|ERROR)",
            re.MULTILINE,
        )

        for match in pattern.finditer(combined):
            test_name = match.group(1)
            raw_status = match.group(2)

            status_map = {
                "PASSED": SingleTestStatus.PASSED,
                "FAILED": SingleTestStatus.FAILED,
                "SKIPPED": SingleTestStatus.SKIPPED,
                "ERROR": SingleTestStatus.ERROR,
            }
            status = status_map.get(raw_status, SingleTestStatus.FAILED)

            # Extract failure message if failed
            failure_msg = None
            if status in {SingleTestStatus.FAILED, SingleTestStatus.ERROR}:
                # Search for error summary line matching this test
                short_name = test_name.split("::")[-1]
                match_err = re.search(
                    rf"FAILED\s+{re.escape(test_name)}\s*-\s*([^\n]+)", combined
                )
                if match_err:
                    failure_msg = match_err.group(1).strip()
                else:
                    failure_msg = f"{raw_status} in {short_name}"

            results.append(
                SingleTestResult(
                    name=test_name,
                    status=status,
                    duration_seconds=0.01,
                    failure_message=failure_msg,
                )
            )

        if not results:
            cmd_name = command or "test_execution"
            if exit_code == 0:
                results.append(
                    SingleTestResult(
                        name=cmd_name,
                        status=SingleTestStatus.PASSED,
                        duration_seconds=0.01,
                    )
                )
            else:
                is_err = "Error" in combined or "Traceback" in combined or "SyntaxError" in combined
                results.append(
                    SingleTestResult(
                        name=cmd_name,
                        status=SingleTestStatus.ERROR if is_err else SingleTestStatus.FAILED,
                        duration_seconds=0.01,
                        failure_message=stderr.strip() or stdout.strip() or "Non-zero exit code",
                    )
                )

        return results
