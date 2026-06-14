"""
ArchitectAgent — designs the system structure.
Sends a structured AgentMessage to CTO with the design plan.
Model: kimi-k2-instruct (best JSON schema compliance)
"""
import json
import re
from models.llm import call_llm, call_agent, AgentMessage

_KEYWORD_MAP = {
    ("website", "web app", "landing page", "html"): {
        "type": "web_app",
        "components": ["frontend html page", "css styling", "javascript interactions"],
    },
    ("rest api", "fastapi", "flask api", "django api"): {
        "type": "api",
        "components": ["fastapi server", "api endpoints", "request models"],
    },
    ("ml model", "train model", "machine learning", "neural network"): {
        "type": "ml_model",
        "components": ["data loading", "model training", "evaluation"],
    },
}


def _keyword_match(goal: str):
    goal_lower = goal.lower()
    for keywords, design in _KEYWORD_MAP.items():
        if any(k in goal_lower for k in keywords):
            return design
    return None


def _extract_json(text: str):
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


class ArchitectAgent:

    def design_system(self, goal: str) -> dict:
        """Design system and send plan to CTO via structured message."""
        # Fast-path for obvious goals
        fast = _keyword_match(goal)
        if fast:
            return fast

        prompt = f"""Analyze this goal and produce a software architecture plan.

Goal: {goal}

Respond ONLY with valid JSON:
{{
  "type": "web_app",
  "components": ["component1", "component2", "component3"]
}}

Types: web_app | api | cli_script | ml_model | desktop_app | game | other
Components: 2-5 concrete buildable items.
"""
        # Use call_agent so Architect→CTO handoff is a structured message
        msg = call_agent(
            from_role  = "architect",
            to_role    = "cto",
            msg_type   = "task",
            prompt     = prompt,
        )

        # Extract design from payload or parse from content
        payload = msg.payload
        if "steps" in payload:
            # kimi-k2 returned steps format — convert to design
            return {
                "type":       "script",
                "components": payload.get("steps", ["core logic", "output"]),
            }

        # Try to find type/components directly in payload
        if "type" in payload and "components" in payload:
            return {"type": payload["type"], "components": payload["components"]}

        # Try parsing raw content as JSON
        design = _extract_json(msg.content)
        if design and "type" in design:
            return design

        # Safe default
        return {
            "type":       "script",
            "components": ["core logic", "output display"],
        }
