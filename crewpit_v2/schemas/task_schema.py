"""
Task schema — Pydantic models for all structured data that flows between
agents and the HTTP layer.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

class ProjectType(str, Enum):
    web_app  = "web_app"
    script   = "script"
    api      = "api"
    ml_model = "ml_model"
    cli      = "cli"


class AgentRole(str, Enum):
    architect = "architect"
    cto       = "cto"
    engineer  = "engineer"
    frontend  = "frontend"
    backend   = "backend"
    ml        = "ml"
    db        = "db"
    js        = "js"
    security  = "security"
    testing   = "testing"
    python    = "python"
    critic    = "critic"
    tester    = "tester"
    builder   = "builder"
    reviewer  = "reviewer"
    router    = "router"
    memory    = "memory"


class MessageType(str, Enum):
    task        = "task"
    review      = "review"
    result      = "result"
    fix_request = "fix_request"
    validation  = "validation"
    context     = "context"


# ─── HTTP request / response models ──────────────────────────────────────────

class RunRequest(BaseModel):
    """POST /run body."""
    goal: str = Field(..., min_length=3, max_length=2000,
                      description="The natural-language goal for the pipeline.")


class RunStatus(BaseModel):
    run_id:     str
    status:     str   # "running" | "done" | "error"
    output_dir: str = ""
    error:      str = ""


class HealthResponse(BaseModel):
    status: str = "ok"


# ─── Agent message schema (mirrors models/llm.AgentMessage as Pydantic) ───────

class AgentMessageSchema(BaseModel):
    from_agent: AgentRole
    to_agent:   AgentRole
    type:       MessageType
    content:    str
    payload:    dict[str, Any] = Field(default_factory=dict)


# ─── Step result schema ────────────────────────────────────────────────────────

class StepResult(BaseModel):
    step:   str
    code:   str  = ""
    output: str  = ""
    error:  str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and bool(self.code)


# ─── Design schema (from ArchitectAgent) ──────────────────────────────────────

class SystemDesign(BaseModel):
    type:       ProjectType = ProjectType.script
    components: list[str]  = Field(default_factory=list)
    language:   str        = "python"
    notes:      str        = ""
