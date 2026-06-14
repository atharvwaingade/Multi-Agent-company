import json
import os
from pathlib import Path

# Always write next to this file (memory/), not relative to cwd.
_LOG_DIR  = Path(__file__).parent.parent / "data" / "logs"
_LOG_FILE = str(_LOG_DIR / "run_logs.json")


def save_log(data: dict) -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)

    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []

    logs.append(data)

    with open(_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)