import json
import os
from pathlib import Path

# Always resolve relative to this file's directory, not the cwd.
# This matches the pattern used by vector_memory.py.
MEMORY_DIR = str(Path(__file__).parent)


def get_memory_file(task_type: str) -> str:
    return os.path.join(MEMORY_DIR, f"{task_type}_memory.json")


def load_memory(task_type: str) -> list:
    file_path = get_memory_file(task_type)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_memory(task_type: str, memory: list) -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    file_path = get_memory_file(task_type)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def add_memory(task_type: str, entry: dict) -> None:
    """
    Store a learned error->fix pair.
    entry = {"error_type": "NameError", "fix": "<corrected code>"}
    """
    if not entry or "error_type" not in entry or "fix" not in entry:
        return
    memory = load_memory(task_type)
    for m in memory:
        if m["error_type"] == entry["error_type"]:
            m["fix"] = entry["fix"]
            save_memory(task_type, memory)
            return
    memory.append(entry)
    save_memory(task_type, memory)


def find_similar_error(error_msg: str, task_type: str = "python"):
    """
    Look up a previously learned fix for a similar error.

    Args:
        error_msg:  The stderr / error string from the executor.
        task_type:  Which memory shard to search (default 'python').

    Returns:
        A fixed code string if found, else None.
    """
    if not error_msg:
        return None
    memory = load_memory(task_type)
    for m in reversed(memory):
        if m.get("error_type", "") in error_msg:
            return m["fix"]
    return None
