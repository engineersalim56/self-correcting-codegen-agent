"""Runs candidate code and its tests in an isolated process with a time limit and no inherited secrets.

Run the agent inside a container with networking disabled in production (`docker run --network none`).
"""
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

OUTPUT_LIMIT = 3000


@dataclass(frozen=True)
class TestOutcome:
    passed: bool
    timed_out: bool
    error_summary: str  # the last useful line of stderr, or a timeout note


def _text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def run_tests(code: str, tests: str, timeout_s: float = 5.0) -> TestOutcome:
    with tempfile.TemporaryDirectory() as workdir:
        script = Path(workdir) / "check.py"
        script.write_text(f"{code}\n\n{tests}\n", encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0"}
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return TestOutcome(False, True, f"timed out after {timeout_s}s (possible infinite loop)")
    if proc.returncode == 0:
        return TestOutcome(True, False, "")
    stderr = _text(proc.stderr)[-OUTPUT_LIMIT:]
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    summary = lines[-1] if lines else f"exit code {proc.returncode}"
    return TestOutcome(False, False, summary)
