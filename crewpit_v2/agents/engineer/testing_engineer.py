from models.llm import call_llm
from utils.cleaner import clean_code


class TestingEngineer:

    def generate_code(self, task: str) -> str:
        prompt = f"""You are a world-class QA/testing engineer.

Task:
{task}

REQUIREMENTS:
- Write pytest tests
- Cover happy path and edge cases
- Use mocks where needed
- Tests must be runnable with: pytest <file>

STRICT:
- ONLY Python test code
- NO explanation
- NO markdown
"""
        return clean_code(call_llm(prompt, agent_role="testing"))
