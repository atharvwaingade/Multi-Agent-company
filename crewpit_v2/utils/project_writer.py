"""
ProjectWriter — writes generated code to an organised output folder.

Each run gets its own timestamped folder under output/runs/<timestamp>/.
Files are named by agent type so engineers can read each other's work.

    output/
    └── runs/
        └── 20260403_142301_my_goal/
            ├── frontend.html
            ├── backend.py
            ├── db.py
            ├── ml.py
            ├── script.py
            ├── tests.py
            └── run_summary.md
"""

import os
import re
import datetime
from pathlib import Path
from utils.logger import Logger

# Project root = two levels up from this file (utils/ → project root)
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_BASE_DIR = str(_PROJECT_ROOT / "output" / "runs")


# Maps agent_type → file extension + filename
_FILE_MAP = {
    "frontend": ("index.html",   "html"),
    "js":       ("script.js",    "js"),
    "backend":  ("backend.py",   "python"),
    "db":       ("database.py",  "python"),
    "ml":       ("model.py",     "python"),
    "security": ("auth.py",      "python"),
    "testing":  ("tests.py",     "python"),
    "python":   ("script.py",    "python"),
}


def _slugify(text: str, max_len: int = 40) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text[:max_len].strip("_")


class ProjectWriter:

    def __init__(self, goal: str, base_dir: str = _DEFAULT_BASE_DIR):
        timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        slug       = _slugify(goal)
        self.run_dir = os.path.join(base_dir, f"{timestamp}_{slug}")
        os.makedirs(self.run_dir, exist_ok=True)
        Logger.log("WRITER", f"Project folder: {self.run_dir}")

        self._manifest: list[dict] = []   # tracks what was written

    def write(self, agent_type: str, code: str) -> str:
        """
        Write code to the appropriate file. Returns the file path.
        Appends if the file already exists (multiple agents of same type).
        """
        if not code.strip():
            return ""

        filename, _ = _FILE_MAP.get(agent_type, ("output.py", "python"))
        file_path   = os.path.join(self.run_dir, filename)

        mode = "a" if os.path.exists(file_path) else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            if mode == "a":
                f.write("\n\n# ── next section ──\n\n")
            f.write(code)

        Logger.log("WRITER", f"📄 Wrote {agent_type} → {filename}")
        self._manifest.append({"agent": agent_type, "file": filename})
        return file_path

    def read(self, agent_type: str) -> str:
        """
        Read back what was written for a given agent type.
        Lets later agents see what earlier agents produced.
        """
        filename, _ = _FILE_MAP.get(agent_type, ("output.py", "python"))
        file_path   = os.path.join(self.run_dir, filename)
        if not os.path.exists(file_path):
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_all(self) -> str:
        """Concatenate everything written so far (for the Builder agent)."""
        parts = []
        seen  = set()
        for entry in self._manifest:
            fp = os.path.join(self.run_dir, entry["file"])
            if fp in seen or not os.path.exists(fp):
                continue
            seen.add(fp)
            with open(fp, "r", encoding="utf-8") as f:
                parts.append(f.read())
        return "\n\n".join(parts)

    def write_summary(self, goal: str, design: dict, session_summary: str) -> str:
        """Write a human-readable run_summary.md."""
        path = os.path.join(self.run_dir, "run_summary.md")
        files_written = list({e["file"] for e in self._manifest})

        content = f"""# Crewpit Run Summary

## Goal
{goal}

## Project Type
{design.get("type", "unknown")}

## Components
{chr(10).join(f"- {c}" for c in design.get("components", []))}

## Files Generated
{chr(10).join(f"- {f}" for f in files_written)}

## Agent Log
{session_summary}
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        Logger.log("WRITER", f"📋 Summary → run_summary.md")
        return path

    @property
    def output_dir(self) -> str:
        return self.run_dir
