import ast


def _is_python(code: str) -> bool:
    """Heuristic: HTML/CSS/JS won't have Python-style indentation and keywords."""
    if not code:
        return True
    code_lower = code.lower().lstrip()
    if code_lower.startswith("<!doctype") or code_lower.startswith("<html"):
        return False
    non_python_markers = ["function ", "const ", "let ", "var ", "=>", "console.log"]
    if any(m in code for m in non_python_markers) and "def " not in code:
        return False
    return True


class TesterAgent:

    # Phrases that almost always mean the code failed silently
    _ERROR_SIGNALS = [
        "traceback",
        "error:",
        "exception:",
        "failed",
        "could not",
        "no module named",
    ]

    def validate(self, result: dict, code: str = None, goal: str = None) -> bool:
        # 1. Hard fail — runtime error
        if result.get("error"):
            return False

        output = result.get("output", "")

        # 2. Syntax check on Python source only
        if code and _is_python(code):
            try:
                ast.parse(code)
            except SyntaxError:
                return False

        # 3. Detect silent errors in output
        output_lower = output.lower()
        for signal in self._ERROR_SIGNALS:
            if signal in output_lower:
                return False

        # 4. Empty output check — only meaningful for Python.
        #    Frontend/JS produces no stdout; non-empty code is sufficient.
        if not output.strip():
            if code and not _is_python(code):
                return bool(code.strip())  # pass if code was generated
            return False  # Python must print something

        return True
