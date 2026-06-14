"""
Utility helpers for code post-processing.
"""

import ast
import re


def remove_duplicate_functions(code: str) -> str:
    """
    Remove duplicate top-level function definitions from Python source code.

    Uses the AST for accurate parsing so class methods and multi-line
    signatures are handled correctly.  Falls back to a regex-based approach
    if the code is not valid Python (e.g. template/pseudo-code).

    The FIRST occurrence of each function name is kept; later duplicates are
    removed along with their entire body.
    """
    # ── AST path (preferred) ──────────────────────────────────────────────────
    try:
        tree  = ast.parse(code)
        lines = code.splitlines(keepends=True)
        seen:   set[str]        = set()
        # Build a set of (start_line, end_line) ranges to drop (1-indexed)
        drop:   set[tuple[int, int]] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only deduplicate top-level functions (col_offset == 0)
                if node.col_offset == 0:
                    name = node.name
                    if name in seen:
                        # end_lineno is inclusive in Python 3.8+
                        drop.add((node.lineno, node.end_lineno))
                    else:
                        seen.add(name)

        if not drop:
            return code

        # Filter out lines that belong to a dropped function
        result = []
        for lineno, line in enumerate(lines, start=1):
            in_dropped = any(start <= lineno <= end for start, end in drop)
            if not in_dropped:
                result.append(line)

        return "".join(result)

    except SyntaxError:
        pass  # fall through to regex fallback

    # ── Regex fallback (handles non-parseable / template code) ───────────────
    seen_names: set[str] = set()
    output_lines = []
    skip_until_indent: int | None = None

    for line in code.splitlines():
        # Check if we are currently skipping a duplicate function body
        if skip_until_indent is not None:
            indent = len(line) - len(line.lstrip())
            if line.strip() == "" or indent > skip_until_indent:
                continue  # still inside the duplicate function body
            else:
                skip_until_indent = None  # body ended

        # Match 'def func_name(' at any indentation
        m = re.match(r"^(\s*)def\s+(\w+)\s*\(", line)
        if m:
            indent_width = len(m.group(1))
            func_name    = m.group(2)
            if func_name in seen_names and indent_width == 0:
                # Skip this definition and its body
                skip_until_indent = indent_width
                continue
            seen_names.add(func_name)

        output_lines.append(line)

    return "\n".join(output_lines)
