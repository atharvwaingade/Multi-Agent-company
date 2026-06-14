from models.llm import call_llm
from utils.cleaner import clean_code


class MLEngineer:

    def generate_code(self, task):
        prompt = f"""
You are a machine learning engineer.

Task:
{task}

REQUIREMENTS:
- Load data
- Train model
- Evaluate
- Print results

STRICT:
- ONLY Python code
- NO explanation
"""

        return clean_code(call_llm(prompt, agent_role="ml"))