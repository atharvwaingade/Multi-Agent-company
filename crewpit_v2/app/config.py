"""
Config — reads from .env
"""
import os
from pathlib import Path

_root = Path(__file__).parent.parent
_env  = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass

# ── Groq API ───────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Ollama fallback ────────────────────────────────────────────────────────────
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",   "mistral")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

# ── Execution ──────────────────────────────────────────────────────────────────
SANDBOX_MODE = os.getenv("SANDBOX_MODE", "subprocess")
MAX_MEM_MB   = int(os.getenv("MAX_MEM_MB",   "256"))
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "10"))

# ── Server ─────────────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "8000"))
