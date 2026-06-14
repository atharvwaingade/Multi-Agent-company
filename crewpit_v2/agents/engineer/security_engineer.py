from models.llm import call_llm
from utils.cleaner import clean_code


class SecurityEngineer:

    def generate_code(self, task: str) -> str:
        prompt = f"""You are a world-class security engineer.

Task:
{task}

REQUIREMENTS:
- Secure, production-ready code
- Use bcrypt for password hashing
- Use JWT for tokens where relevant
- Never store plaintext secrets
- Include input validation

STRICT:
- ONLY Python code
- NO explanation
- NO markdown
"""
        return clean_code(call_llm(prompt, agent_role="security"))
