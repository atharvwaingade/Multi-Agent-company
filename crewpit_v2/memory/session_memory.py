"""
SessionMemory — in-process shared context for a single Crewpit run.

Agents can read what prior agents generated, so the backend engineer
knows what the frontend already produced, etc.

Usage:
    from memory.session_memory import SessionMemory
    mem = SessionMemory()

    mem.set_design(design)
    mem.add_step_result("Build the API", "python", code, result)
    mem.get_all_code()          # concatenated code so far
    mem.get_code_by_type("frontend")
    mem.get_context_summary()   # compact string agents can read in prompts
"""

from dataclasses import dataclass, field
from typing import Optional
import datetime


@dataclass
class StepRecord:
    step:       str
    agent_type: str
    code:       str
    output:     str
    success:    bool
    timestamp:  str = field(default_factory=lambda: datetime.datetime.now().strftime("%H:%M:%S"))


class SessionMemory:

    def __init__(self):
        self._design:  dict        = {}
        self._goal:    str         = ""
        self._records: list[StepRecord] = []

    # ── Write ──────────────────────────────────────────────────────────────────

    def set_goal(self, goal: str) -> None:
        self._goal = goal

    def set_design(self, design: dict) -> None:
        self._design = design

    def add_step_result(
        self,
        step:       str,
        agent_type: str,
        code:       str,
        result:     dict,
    ) -> None:
        record = StepRecord(
            step       = step,
            agent_type = agent_type,
            code       = code,
            output     = result.get("output", ""),
            success    = not bool(result.get("error")),
        )
        self._records.append(record)

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_goal(self) -> str:
        return self._goal

    def get_design(self) -> dict:
        return self._design

    def get_all_code(self) -> str:
        """All successfully generated code concatenated."""
        return "\n\n".join(r.code for r in self._records if r.success)

    def get_code_by_type(self, agent_type: str) -> str:
        """Code produced by a specific engineer type."""
        return "\n\n".join(
            r.code for r in self._records
            if r.agent_type == agent_type and r.success
        )

    def get_successful_steps(self) -> list[str]:
        return [r.step for r in self._records if r.success]

    def get_failed_steps(self) -> list[str]:
        return [r.step for r in self._records if not r.success]

    def get_context_summary(self, max_chars: int = 800) -> str:
        """
        Compact string injected into agent prompts so they know
        what has already been built.
        """
        if not self._records:
            return "No prior work yet."

        lines = [f"Goal: {self._goal}", f"Project type: {self._design.get('type', 'unknown')}", ""]
        for r in self._records:
            status = "✅" if r.success else "❌"
            preview = r.code[:120].replace("\n", " ") + "..."
            lines.append(f"{status} [{r.agent_type}] {r.step}")
            lines.append(f"   Code: {preview}")

        summary = "\n".join(lines)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "\n...(truncated)"
        return summary

    def has_code_of_type(self, agent_type: str) -> bool:
        return any(r.agent_type == agent_type and r.success for r in self._records)

    def step_count(self) -> int:
        return len(self._records)

    def success_count(self) -> int:
        return sum(1 for r in self._records if r.success)
