def fix_indentation(code):
    lines = code.split("\n")
    fixed = []
    indent_level = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            fixed.append("")
            continue

        # decrease indent for return / else / elif
        if stripped.startswith(("return", "elif", "else", "except", "finally")):
            indent_level = max(indent_level - 1, 0)

        fixed.append("    " * indent_level + stripped)

        # increase indent after :
        if stripped.endswith(":"):
            indent_level += 1

    return "\n".join(fixed)