"""
CriticAgent — reviews and fixes failing code.
Sends fix_request to engineer, receives fixed code back via AgentMessage.
Model: kimi-k2-instruct (best structured review output)
"""
from models.llm import call_agent, AgentMessage


def _detect_task_type(code: str) -> str:
    code_lower = code.lower()
    if "<html" in code_lower:
        return "html"
    if "{" in code_lower and "}" in code_lower and ";" in code_lower:
        return "css"
    if "function" in code_lower or "const " in code_lower or "let " in code_lower:
        return "js"
    return "python"


def _clean_code(code: str) -> str:
    if not code:
        return ""
    lines = [l for l in code.split("\n") if not l.strip().startswith("```")]
    skip = ["here is", "here's", "below is", "complete runnable", "sure!", "sure,"]
    lines = [l for l in lines if not any(l.strip().lower().startswith(p) for p in skip)]
    return "\n".join(lines).strip()


class CriticAgent:

    def fix_code(self, code: str, error: str, goal: str = None) -> str:
        """
        Send a fix_request from critic to the appropriate engineer.
        Returns the fixed code string.
        """
        task_type = _detect_task_type(code)
        language_map = {"html": "frontend", "css": "frontend", "js": "js", "python": "python"}
        target_engineer = language_map.get(task_type, "python")

        prompt = f"""The following {task_type} code failed and needs fixing.

ORIGINAL CODE:
{code}

ERROR:
{error}

ORIGINAL GOAL:
{goal or "Not specified"}

Fix the code so it:
- Runs without errors
- Preserves the original intent
- Has visible output (print statements if Python)

In your payload.code field, return ONLY the corrected {task_type} code.
No markdown. No explanation. Just fixed code.
"""
        # Critic sends fix_request → engineer
        msg = call_agent(
            from_role = "critic",
            to_role   = target_engineer,
            msg_type  = "fix_request",
            prompt    = prompt,
        )

        fixed = msg.get_code() or msg.payload.get("raw", "")
        return _clean_code(fixed)

    def review_code(self, code: str, goal: str) -> AgentMessage:
        """
        Perform a structured code review.
        Returns AgentMessage with issues, severity, suggestions.
        """
        prompt = f"""Review this code against the stated goal.

GOAL: {goal}

CODE:
{code}

Identify real issues (bugs, missing logic, bad practices).
In payload.issues list each problem. In payload.suggestions list fixes.
Set payload.severity to: low | medium | high
"""
        return call_agent(
            from_role = "critic",
            to_role   = "engineer",
            msg_type  = "review",
            prompt    = prompt,
        )
