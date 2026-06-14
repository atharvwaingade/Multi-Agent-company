from models.llm import call_llm
from utils.cleaner import clean_code


class JSEngineer:

    def generate_code(self, task):
        prompt = f"""
You are a senior JavaScript engineer.

Task:
{task}

REQUIREMENTS:
- Clean logic
- Event handling
- No HTML/CSS inside JS

STRICT:
- ONLY JavaScript
- NO explanation
"""

        return clean_code(call_llm(prompt, agent_role="js"))