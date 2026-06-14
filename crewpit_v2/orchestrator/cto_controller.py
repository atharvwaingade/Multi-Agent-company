import re
from models.llm import call_llm, call_agent


class CTOController:

    def create_plan(self, goal: str) -> list[str]:
        prompt = f"""You are an expert CTO and project manager.

Break the following goal into 2-4 concrete, minimal coding steps.

Rules:
- Each step must be a single sentence starting with a verb (e.g. "Build...", "Create...", "Write...")
- Steps must be directly relevant to the goal
- No explanations, no markdown, no numbering
- One step per line

Goal: {goal}
"""
        response = call_llm(prompt, agent_role="cto")

        steps = []
        for line in response.splitlines():
            # Strip leading bullets / numbers like "1.", "- ", "* "
            line = re.sub(r"^[\s\-\*\d\.]+", "", line).strip()
            if line and len(line) > 5:
                steps.append(line)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for s in steps:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique.append(s)

        return unique if unique else [f"Build the complete solution for: {goal}"]

    def evaluate(self, result: dict) -> str:
        if result.get("error"):
            return "retry"
        if not result.get("output", "").strip():
            return "retry"
        return "success"
