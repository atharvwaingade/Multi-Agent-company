"""
Sandbox — safe code execution with resource limits and static safety checks.

Two modes (set SANDBOX_MODE env var):
  - subprocess (default) — child process with timeout + Unix resource limits
  - docker               — runs inside a throwaway container (requires Docker)

Static checks run BEFORE execution and block dangerous patterns.
"""

import os
import re
import subprocess
import tempfile
import platform
from utils.logger import Logger

SANDBOX_MODE  = os.environ.get("SANDBOX_MODE", "subprocess")
EXEC_TIMEOUT  = int(os.environ.get("EXEC_TIMEOUT", "10"))
MAX_MEM_MB    = int(os.environ.get("MAX_MEM_MB", "256"))
DOCKER_IMAGE  = os.environ.get("SANDBOX_DOCKER_IMAGE", "python:3.11-slim")
# Truncate output to this many chars to prevent memory exhaustion
MAX_OUTPUT_BYTES = int(os.environ.get("MAX_OUTPUT_BYTES", str(512 * 1024)))  # 512 KB

# Patterns blocked before execution (order matters — most dangerous first)
_BLOCKED = [
    (r"os\.system\s*\(",            "os.system() call"),
    (r"shutil\.rmtree\s*\(",        "shutil.rmtree() call"),
    (r"subprocess\.Popen\s*\(",     "subprocess.Popen() call"),
    (r"subprocess\.call\s*\(",      "subprocess.call() call"),
    (r"subprocess\.run\s*\(",       "subprocess.run() call"),
    (r"\beval\s*\(",                "eval() call"),
    (r"\bexec\s*\(",                "exec() call"),
    (r"__import__\s*\(",            "__import__() call"),
    # Block file writes and appends only — reads are permitted.
    (r'open\s*\(.*?,\s*["\'\"][wa]', "file write/append open()"),
    # Block outbound network access in generated code
    (r"urllib\.request\.",          "urllib.request network call"),
    (r"requests\.(get|post|put|delete|patch|head)\s*\(", "requests HTTP call"),
    (r"socket\.connect\s*\(",       "socket.connect() call"),
    (r"http\.client\.",             "http.client network call"),
]


def static_check(code: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).
    Runs before any execution attempt.
    """
    for pattern, description in _BLOCKED:
        if re.search(pattern, code):
            return False, f"Blocked: {description}"
    return True, "ok"


def _set_limits():
    """Called in child process (Unix only) to cap memory + CPU time."""
    try:
        import resource
        mem_bytes = MAX_MEM_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS,  (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (EXEC_TIMEOUT, EXEC_TIMEOUT))
    except Exception as exc:
        # Log the failure instead of swallowing it silently
        # (can't use Logger here — we're in the forked child)
        print(f"[SANDBOX] _set_limits warning: {exc}", flush=True)


def _truncate(text: str, label: str) -> str:
    if len(text.encode("utf-8", errors="replace")) > MAX_OUTPUT_BYTES:
        Logger.log("SANDBOX", f"⚠️  {label} truncated to {MAX_OUTPUT_BYTES // 1024} KB")
        return text[:MAX_OUTPUT_BYTES] + "\n...[truncated]"
    return text


def _run_subprocess(code: str) -> dict:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        is_unix = platform.system() != "Windows"
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT,
            encoding="utf-8",
            errors="ignore",
            preexec_fn=_set_limits if is_unix else None,
        )
        stdout = _truncate(result.stdout, "stdout")
        stderr = _truncate(result.stderr, "stderr")
        return {
            "output": stdout,
            "error":  stderr if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"output": "", "error": f"Execution timed out after {EXEC_TIMEOUT}s."}
    except Exception as e:
        return {"output": "", "error": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _run_docker(code: str) -> dict:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", f"{MAX_MEM_MB}m",
                "--cpus",   "0.5",
                "--read-only",
                "-v", f"{tmp_path}:/code.py:ro",
                DOCKER_IMAGE,
                "python3", "/code.py",
            ],
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT + 10,
            encoding="utf-8",
            errors="ignore",
        )
        stdout = _truncate(result.stdout, "stdout")
        stderr = _truncate(result.stderr, "stderr")
        return {
            "output": stdout,
            "error":  stderr if result.returncode != 0 else None,
        }
    except FileNotFoundError:
        Logger.log("SANDBOX", "❌ Docker not found — falling back to subprocess")
        return _run_subprocess(code)
    except subprocess.TimeoutExpired:
        return {"output": "", "error": "Docker execution timed out."}
    except Exception as e:
        return {"output": "", "error": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def safe_run(code: str) -> dict:
    """
    Main entry point. Runs static checks then executes in sandbox.
    Returns {"output": str, "error": str | None}.
    """
    is_safe, reason = static_check(code)
    if not is_safe:
        Logger.log("SANDBOX", f"🚫 Code blocked by static check: {reason}")
        return {"output": "", "error": f"Safety check failed: {reason}"}

    Logger.log("SANDBOX", f"Mode: {SANDBOX_MODE}")
    if SANDBOX_MODE == "docker":
        return _run_docker(code)
    return _run_subprocess(code)