from models.llm import call_llm
from utils.cleaner import clean_code


class BackendEngineer:

    def generate_code(self, task):
        prompt = f"""
You are a senior backend engineer.

Task:
{task}

REQUIREMENTS:
- Use FastAPI
- Clean API structure
- JSON responses
- Error handling

STRICT:
- ONLY Python code
- NO explanation
"""

        return clean_code(call_llm(prompt, agent_role="backend"))