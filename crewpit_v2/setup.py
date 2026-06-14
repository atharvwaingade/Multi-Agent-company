"""
Crewpit setup checker — verifies Groq API key and Ollama fallback.
Run: python setup.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  Crewpit Setup Check")
print("=" * 60)

# 1. Groq API key
from models.llm import check_groq, _is_api_key_set, GROQ_API_KEY, MODEL_MAP

print("\n[1] Groq API Key")
if _is_api_key_set():
    print("    ✅ Key found: set in environment")
    print("    Testing connection...")
    ok, msg = check_groq()
    print(f"    {'✅' if ok else '❌'} {msg}")
else:
    print("    ⚠️  GROQ_API_KEY not set!")
    print("    → Edit models/llm.py and paste your key")
    print("    → OR: export GROQ_API_KEY=gsk_xxxx")
    print("    → Get a free key at: https://console.groq.com/keys")

# 2. Model assignments
print("\n[2] Agent → Model assignments")
for role, model in MODEL_MAP.items():
    print(f"    {role:12s} → {model}")

# 3. Ollama fallback
print("\n[3] Ollama offline fallback")
try:
    import subprocess
    r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
    if r.returncode == 0:
        models = [l.split()[0] for l in r.stdout.splitlines()[1:] if l.strip()]
        print(f"    ✅ Ollama running — {len(models)} model(s): {', '.join(models[:3])}")
    else:
        print("    ⚠️  Ollama not responding")
except FileNotFoundError:
    print("    ⚠️  Ollama not installed (optional — needed if Groq key is missing)")

# 4. Python deps
print("\n[4] Python dependencies")
for pkg in ["fastapi", "uvicorn", "dotenv"]:
    try:
        __import__(pkg.replace("-", "_"))
        print(f"    ✅ {pkg}")
    except ImportError:
        print(f"    ❌ {pkg} — run: pip install {pkg}")

print("\n" + "=" * 60)
print("  Run the app:")
print("    python app/server.py           # Web UI at http://localhost:8000")
print("    python app/main.py 'your goal' # Command line")
print("=" * 60)
