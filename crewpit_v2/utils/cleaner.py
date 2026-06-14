import re


def clean_code(code: str) -> str:
    """
    Strip markdown fences, preamble lines, and trailing whitespace
    from LLM-generated code so it can be executed directly.
    """
    if not code:
        return ""

    # Remove markdown code fences (```python, ```html, ```, etc.)
    code = re.sub(r"^```[a-zA-Z]*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"```\s*$", "", code, flags=re.MULTILINE)

    lines = code.split("\n")
    cleaned = []

    # Common LLM preamble/postamble phrases to drop
    skip_phrases = [
        "here is",
        "here's",
        "below is",
        "complete runnable",
        "sure!",
        "sure,",
        "certainly",
        "of course",
        "this code",
        "the following",
        "output:",
        "result:",
    ]

    for line in lines:
        stripped = line.strip().lower()
        if any(stripped.startswith(p) for p in skip_phrases):
            continue
        cleaned.append(line.rstrip())

    # Remove leading/trailing blank lines
    result = "\n".join(cleaned).strip()
    return result
