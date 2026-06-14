from models.llm import call_llm
from utils.cleaner import clean_code


class FrontendEngineer:

    def generate_code(self, task):
        prompt = f"""
You are a world-class frontend engineer and UI/UX designer.

Task:
{task}

REQUIREMENTS:
- Modern UI (hero, sections, footer)
- Responsive design
- Clean HTML + CSS
- Use real content from task

STRICT:
- ONLY HTML/CSS/JS
- NO explanation
"""

        return clean_code(call_llm(prompt, agent_role="frontend"))