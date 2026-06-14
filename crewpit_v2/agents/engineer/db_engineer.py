from models.llm import call_llm
from utils.cleaner import clean_code


class DatabaseEngineer:

    def generate_code(self, task):
        prompt = f"""
You are a database expert.

Task:
{task}

REQUIREMENTS:
- Proper schema design
- Use SQL or SQLAlchemy
- Handle constraints

STRICT:
- ONLY code
- NO explanation
"""

        return clean_code(call_llm(prompt, agent_role="db"))