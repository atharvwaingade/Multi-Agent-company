"""
BuilderAgent — assembles final output from all engineer code.
Model: llama-3.3-70b-versatile (broad reasoning, runs once per pipeline)
Sends result AgentMessage back to CTO when done.
"""
from models.llm import call_llm, call_agent


def _clean_code(code: str) -> str:
    if not code:
        return ""
    lines = code.split("\n")
    skip_phrases = ["here is", "here's", "below is", "complete runnable", "sure!", "sure,"]
    cleaned = []
    for line in lines:
        if line.strip().startswith("```"):
            continue
        if any(line.strip().lower().startswith(p) for p in skip_phrases):
            continue
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip()


class BuilderAgent:

    def build_python(self, code: str) -> str:
        """Assemble all Python snippets into one runnable program."""
        prompt = f"""You are a senior Python engineer.

Combine these code snippets into ONE complete runnable Python program:

{code}

RULES:
- Correct indentation throughout
- Add a main() function that calls everything
- Use sample/hardcoded values — never input()
- Print outputs clearly
- Remove duplicate imports
- No markdown, no explanation

Return ONLY valid Python code.
"""
        result = call_llm(prompt, agent_role="builder")
        return _clean_code(result)

    def build_web_project_content(self, code: str) -> str:
        """
        Assemble HTML/CSS/JS fragments into a single self-contained HTML file.
        Returns the HTML string — the CALLER is responsible for writing to disk.
        (Avoids hardcoding output path relative to cwd.)
        """
        prompt = f"""You are a senior frontend engineer.

Given these code fragments from multiple agents:

{code}

Produce a SINGLE complete self-contained HTML file that:
- Has proper <!DOCTYPE html> structure
- Includes all CSS in a <style> tag inside <head>
- Includes all JavaScript in a <script> tag before </body>
- Has real, useful content — not placeholder text
- Is responsive and modern

Return ONLY the HTML file content. No markdown. No explanation.
"""
        html = _clean_code(call_llm(prompt, agent_role="builder"))
        return html

    # Keep old name as a wrapper for backward-compat but route through the new one
    def build_web_project(self, code: str, output_path: str = "output/index.html") -> str:
        """
        Deprecated: prefer build_web_project_content() + writing in the caller.
        Kept for any direct callers outside main.py.
        """
        import os
        html = self.build_web_project_content(code)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        call_agent(
            from_role="builder",
            to_role="cto",
            msg_type="result",
            prompt=f"Web project assembled and saved to {output_path}. HTML length: {len(html)} chars.",
        )
        return f"🌐 Web project saved to {output_path}"

    def build_final_code(self, code: str, project_type: str = "script") -> str:
        if project_type == "web_app":
            return self.build_web_project_content(code)
        return self.build_python(code)
