# Crewpit — Multi-Agent AI Dev Team (Groq Edition)

Builds software from a plain English goal using a team of specialized AI agents
that **talk to each other** via structured JSON messages.

```
Goal → Architect → CTO plans steps → Engineers build in parallel
     ↓                               ↓ (AgentMessage envelopes)
  Tester validates ← Executor runs ← Engineer produces code
     ↓
  Critic fixes errors → Builder assembles final output
```

---

## Agent → Model assignments

| Agent | Model | Why |
|---|---|---|
| **Architect** | `kimi-k2-instruct` | Best JSON schema compliance for handoffs |
| **CTO** | `kimi-k2-instruct` | Structured plan output |
| **Critic** | `kimi-k2-instruct` | Writes structured review messages |
| **All Engineers** | `qwen/qwen3-32b` | Strong code + 60 RPM budget |
| **Tester/Validator** | `llama-3.1-8b-instant` | 14.4K RPD, fast pass/fail JSON |
| **Builder** | `llama-3.3-70b-versatile` | Final assembly, runs once |
| **Memory** | `llama-4-scout-17b` | 500K TPD for large context reads |
| **Fallback** | `gpt-oss-20b` | When primary hits rate limits |
| **Offline** | Ollama (local) | No internet / all limits exhausted |

---

## Agent-to-Agent Messaging

Every inter-agent call uses a structured `AgentMessage` envelope:

```json
{
  "from_agent": "architect",
  "to_agent":   "engineer",
  "type":       "task",
  "content":    "Build a login form with JWT auth",
  "payload": {
    "steps":   ["Create HTML form", "Add JS validation", "Wire to API"],
    "context": "Web app project, FastAPI backend already planned"
  }
}
```

Types: `task | result | review | fix_request | validation | context`

---

## Quick Start

### 1. Get a Groq API key (free)
Go to **https://console.groq.com/keys** and create a key.

### 2. Set your API key

**Option A — edit the file:**
Open `models/llm.py` and replace the highlighted placeholder:
```python
GROQ_API_KEY = "████████  PASTE_YOUR_GROQ_API_KEY_HERE  ████████"
```

**Option B — environment variable:**
```bash
export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Option C — .env file:**
```bash
cp .env.example .env
# Edit .env and paste your key
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify setup
```bash
python setup.py
```

### 5. Run
```bash
# Web UI
python app/server.py
# Open http://localhost:8000

# Command line
python app/main.py "build me a calculator web app"
python app/main.py "create a todo list API with FastAPI"
```

---

## Offline fallback (no API key)

If you don't set a Groq key, or Groq is unavailable, all agents fall back to
a local Ollama model automatically.

```bash
ollama pull mistral      # ~4GB
python app/server.py     # runs fully offline
```

---

## Output

Every run creates a timestamped folder:
```
output/runs/20260403_142301_calculator_web_app/
├── index.html      ← frontend
├── backend.py      ← API
├── database.py     ← DB layer
├── final.py        ← assembled program
└── run_summary.md  ← what was built + agent message log
```
