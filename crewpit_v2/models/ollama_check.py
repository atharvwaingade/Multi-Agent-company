"""
Ollama health check — called at server startup and before each run.
"""
import subprocess
import socket
from utils.logger import Logger


def is_ollama_running() -> tuple[bool, str]:
    """
    Returns (ok, message).
    Tries the Ollama HTTP API first (fastest), falls back to CLI.
    """
    # 1. Check HTTP API (Ollama listens on 11434 by default)
    try:
        s = socket.create_connection(("127.0.0.1", 11434), timeout=2)
        s.close()
        return True, "Ollama is running"
    except (ConnectionRefusedError, OSError):
        pass

    # 2. Fallback: try ollama list
    try:
        r = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return True, "Ollama is running"
        return False, "Ollama installed but not responding — run: ollama serve"
    except FileNotFoundError:
        return False, "Ollama not installed — download from https://ollama.com"
    except subprocess.TimeoutExpired:
        return False, "Ollama not responding (timeout) — run: ollama serve"


def get_local_models() -> list[str]:
    """Return list of model names already pulled locally."""
    try:
        r = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        models = []
        for line in r.stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                models.append(parts[0].split(":")[0])
        return models
    except Exception:
        return []


def check_model_available(model_name: str) -> tuple[bool, str]:
    """Check if a specific model is pulled and ready."""
    models = get_local_models()
    base   = model_name.split(":")[0]
    if base in models or model_name in models:
        return True, f"Model '{model_name}' is ready"
    return False, (
        f"Model '{model_name}' not found locally.\n"
        f"Pull it with:  ollama pull {model_name}\n"
        f"Available models: {models if models else 'none pulled yet'}"
    )


def full_startup_check(model_name: str) -> tuple[bool, str]:
    """
    Run all checks at server startup.
    Returns (ok, human-readable status message).
    """
    ok, msg = is_ollama_running()
    if not ok:
        return False, f"❌ Ollama not running: {msg}"

    ok, msg = check_model_available(model_name)
    if not ok:
        return False, f"❌ Model missing: {msg}"

    return True, f"✅ Ollama running | Model '{model_name}' ready"
