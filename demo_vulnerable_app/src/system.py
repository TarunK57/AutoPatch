"""System utilities."""
import subprocess

def ping_remote_host(host_ip: str):
    # Command Injection via shell=True (CWE-78)
    return subprocess.call(f"ping -c 1 {host_ip}", shell=True)
