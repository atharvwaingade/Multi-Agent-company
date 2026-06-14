from models.llm import call_llm
from utils.cleaner import clean_code


class PythonEngineer:

    def generate_code(self, task):
        prompt = f"""
You are a world-class Python engineer.

Task:
{task}

REQUIREMENTS:
- Clean, production-ready code
- Handle edge cases
- Fully runnable
- Print outputs clearly

STRICT:
- ONLY Python code
- NO explanation
"""

        return clean_code(call_llm(prompt, agent_role="python"))