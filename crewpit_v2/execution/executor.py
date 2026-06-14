"""
Executor — legacy wrapper kept for backward compatibility.

All actual execution is delegated to execution.sandbox.safe_run which
applies static safety checks, resource limits, and output truncation.
Do NOT add direct subprocess calls here — use safe_run instead.
"""
from execution.sandbox import safe_run


class Executor:

    def run(self, code: str) -> dict:
        """Execute code safely via the sandbox. Returns {output, error}."""
        return safe_run(code)
