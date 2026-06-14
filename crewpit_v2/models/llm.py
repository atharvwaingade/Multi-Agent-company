"""
Crewpit LLM Layer — Groq multi-model + Ollama fallback.

Each agent role is assigned the best model based on structured output compliance
and RPM/RPD budget:
  Orchestration / Critic / Architect → kimi-k2-instruct  (best structured output)
  Engineers                          → qwen/qwen3-32b     (strong code + format)
  Task Classifier / Tester / Router  → llama-3.1-8b-instant (fast, 14.4K RPD)
  Builder (final assembly)           → llama-3.3-70b-versatile
  Project Memory / large context     → meta-llama/llama-4-scout-17b-16e-instruct
  Fallback                           → gpt-oss-20b → Ollama (offline)

Agent-to-Agent Messaging:
  Every inter-agent call produces a structured AgentMessage envelope:
  {
    "from_agent": "architect",
    "to_agent":   "engineer",
    "type":       "task | review | result | fix_request | validation | context",
    "content":    "one-sentence summary",
    "payload":    { ...role-specific structured data... }
  }
  Use call_llm()   for direct prompts (returns raw text).
  Use call_agent() when agents talk to each other (returns AgentMessage).
"""

import os
import json
import re
import time
import random
import uuid
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional
from utils.logger import Logger

# ── API key — read ONLY from environment / .env (never hardcode) ──────────────
# Set it with:  export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Or add it to your .env file.  Never paste a real key in source code.
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Model assignments per agent role ─────────────────────────────────────────
MODEL_MAP = {
    # Orchestration: must produce reliable JSON for other agents to parse
    "architect":  "moonshotai/kimi-k2-instruct",
    "cto":        "moonshotai/kimi-k2-instruct",
    "critic":     "moonshotai/kimi-k2-instruct",

    # Engineers: strong code generation + consistent JSON handoff
    "engineer":   "qwen/qwen3-32b",
    "frontend":   "qwen/qwen3-32b",
    "backend":    "qwen/qwen3-32b",
    "ml":         "qwen/qwen3-32b",
    "db":         "qwen/qwen3-32b",
    "js":         "qwen/qwen3-32b",
    "security":   "qwen/qwen3-32b",
    "testing":    "qwen/qwen3-32b",
    "python":     "qwen/qwen3-32b",

    # High-frequency simple output — 14.4K RPD workhorse
    "tester":     "llama-3.1-8b-instant",
    "classifier": "llama-3.1-8b-instant",
    "router":     "llama-3.1-8b-instant",
    "validator":  "llama-3.1-8b-instant",

    # Final assembly — runs once per pipeline
    "builder":    "llama-3.3-70b-versatile",

    # Large context reads (500K TPD) — project memory ingestion
    "memory":     "meta-llama/llama-4-scout-17b-16e-instruct",

    # Fallback when primary hits rate limits
    "fallback":   "openai/gpt-oss-20b",
}

# Max chars we accept from any single LLM response (prevents memory exhaustion)
MAX_OUTPUT_CHARS = 8_000

# Offline Ollama fallback
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "180"))


# ─────────────────────────────────────────────────────────────────────────────
# Agent-to-Agent Message Schema
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    """
    Structured envelope for all inter-agent communication.
    Every agent reads and writes this schema — never raw strings.
    """
    from_agent: str    # e.g. "architect"
    to_agent:   str    # e.g. "engineer"
    type:       str    # task | review | result | fix_request | validation | context
    content:    str    # one-sentence human-readable summary
    payload:    dict   # role-specific structured data

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMessage":
        return cls(
            from_agent = d.get("from_agent", "unknown"),
            to_agent   = d.get("to_agent",   "unknown"),
            type       = d.get("type",       "task"),
            content    = d.get("content",    ""),
            payload    = d.get("payload",    {}),
        )

    def get_code(self) -> str:
        return self.payload.get("code", "")

    def get_issues(self) -> list:
        return self.payload.get("issues", [])

    def passed(self) -> bool:
        return self.payload.get("passed", False)


def _build_agent_system_prompt(from_role: str, to_role: str, msg_type: str) -> str:
    payload_examples = {
        "task":        '{ "steps": ["step1", "step2"], "context": "prior work summary" }',
        "result":      '{ "code": "...", "language": "python", "notes": "what was built" }',
        "review":      '{ "issues": ["issue1"], "severity": "low|medium|high", "suggestions": ["fix1"] }',
        "fix_request": '{ "code": "...", "error": "traceback or error msg", "goal": "original task" }',
        "validation":  '{ "passed": true, "reason": "explanation", "score": 85 }',
        "context":     '{ "summary": "...", "prior_code": "...", "project_type": "web_app" }',
    }
    example_payload = payload_examples.get(msg_type, '{ "data": "..." }')

    return f"""You are the {from_role.upper()} agent in a multi-agent software team.
You are sending a message of type "{msg_type}" to the {to_role.upper()} agent.

RULE: Respond with ONLY a valid JSON object. No markdown. No explanation. No backticks.

Required schema:
{{
  "from_agent": "{from_role}",
  "to_agent": "{to_role}",
  "type": "{msg_type}",
  "content": "<one sentence: what you are communicating>",
  "payload": {example_payload}
}}

Fill "payload" with real data based on the task given below.
The {to_role} agent will parse this JSON directly — malformed output breaks the pipeline.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Groq HTTP call (no external deps — uses stdlib urllib)
# ─────────────────────────────────────────────────────────────────────────────

def _is_api_key_set() -> bool:
    return bool(GROQ_API_KEY) and len(GROQ_API_KEY) > 20


def _groq_call(
    prompt:     str,
    model:      str,
    system:     str = "",
    max_tokens: int = 2048,
    retries:    int = 2,
) -> str:
    if not _is_api_key_set():
        Logger.log("LLM", "⚠️  GROQ_API_KEY not set — using Ollama offline fallback")
        return _ollama_call(prompt)

    import urllib.request
    import urllib.error

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    request_id = str(uuid.uuid4())[:8]

    body = json.dumps({
        "model":      model,
        "messages":   messages,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                GROQ_BASE_URL,
                data=body,
                headers={
                    "Content-Type":      "application/json",
                    "Authorization":     f"Bearer {GROQ_API_KEY}",
                    "X-Request-ID":      request_id,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                # Cap output to prevent memory exhaustion from runaway models
                if len(text) > MAX_OUTPUT_CHARS:
                    Logger.log("LLM", f"⚠️  Response truncated {len(text)}→{MAX_OUTPUT_CHARS} chars [req={request_id}]")
                    text = text[:MAX_OUTPUT_CHARS]
                Logger.log("LLM", f"✅ {model} → {len(text)} chars [req={request_id}]")
                return text

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code == 429:
                Logger.log("LLM", f"⚠️  Rate limit on {model} — trying fallback model [req={request_id}]")
                fallback = MODEL_MAP["fallback"]
                if model != fallback:
                    return _groq_call(prompt, fallback, system, max_tokens, retries=0)
                # Exponential backoff WITH jitter to avoid thundering herd
                wait = (2 ** attempt) + random.uniform(0, 1)
                Logger.log("LLM", f"⏳ Waiting {wait:.1f}s before retry... [req={request_id}]")
                time.sleep(wait)
            elif e.code in (401, 403):
                Logger.log("LLM", f"❌ Auth error — is GROQ_API_KEY correct? {err_body[:150]} [req={request_id}]")
                return _ollama_call(prompt)
            else:
                Logger.log("LLM", f"❌ HTTP {e.code}: {err_body[:150]} [req={request_id}]")
                if attempt < retries:
                    time.sleep(1 + random.uniform(0, 0.5))

        except Exception as ex:
            Logger.log("LLM", f"❌ Request failed: {ex} [req={request_id}]")
            if attempt < retries:
                time.sleep(1 + random.uniform(0, 0.5))

    Logger.log("LLM", f"⚠️  All Groq attempts exhausted — falling back to Ollama [req={request_id}]")
    return _ollama_call(prompt)


def _ollama_call(prompt: str) -> str:
    """Local Ollama fallback — works fully offline."""
    Logger.log("LLM", f"🔌 Ollama [{OLLAMA_MODEL}] fallback")
    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=OLLAMA_TIMEOUT,
            encoding="utf-8",
            errors="ignore",
        )
        output = result.stdout.strip()
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS]
        if output:
            Logger.log("LLM", f"✅ Ollama → {len(output)} chars")
        else:
            Logger.log("LLM", "⚠️  Ollama returned empty — check: ollama list")
        return output
    except FileNotFoundError:
        Logger.log("LLM", "❌ Ollama not installed — https://ollama.com")
        return ""
    except subprocess.TimeoutExpired:
        Logger.log("LLM", f"⏱️  Ollama timeout ({OLLAMA_TIMEOUT}s) — try a smaller model")
        return ""
    except Exception as ex:
        Logger.log("LLM", f"❌ Ollama error: {ex}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def call_llm(
    prompt:     str,
    model:      str = None,
    agent_role: str = None,
    max_tokens: int = 2048,
) -> str:
    """
    Standard single-agent LLM call — returns raw text.

    Args:
        prompt:     Full prompt string.
        model:      Explicit model name. Takes priority over agent_role.
        agent_role: Role key from MODEL_MAP (e.g. "architect", "engineer").
                    Defaults to "engineer" if neither model nor role given.
        max_tokens: Max response tokens.
    """
    resolved_model = model or MODEL_MAP.get(agent_role or "engineer", MODEL_MAP["fallback"])
    Logger.log("LLM", f"→ {resolved_model} | role={agent_role or 'direct'} | {len(prompt)}c prompt")
    return _groq_call(prompt, resolved_model, max_tokens=max_tokens)


def call_agent(
    from_role:  str,
    to_role:    str,
    msg_type:   str,
    prompt:     str,
    max_tokens: int = 1500,
) -> AgentMessage:
    """
    Inter-agent structured call.
    Forces the sending agent's model to return a valid AgentMessage JSON.

    Args:
        from_role:  Sending agent (e.g. "architect") — determines which model is used.
        to_role:    Receiving agent (e.g. "engineer").
        msg_type:   "task" | "review" | "result" | "fix_request" | "validation" | "context"
        prompt:     Task-specific content for the agent to act on.
        max_tokens: Response token budget.

    Returns:
        AgentMessage — always valid (falls back gracefully on parse error).
    """
    model  = MODEL_MAP.get(from_role, MODEL_MAP["fallback"])
    system = _build_agent_system_prompt(from_role, to_role, msg_type)

    Logger.log("LLM", f"📨 {from_role} → {to_role} [{msg_type}] via {model}")

    raw = _groq_call(prompt, model, system=system, max_tokens=max_tokens)

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            msg  = AgentMessage.from_dict(data)
            Logger.log("LLM", f"✅ AgentMessage OK — payload keys: {list(msg.payload.keys())}")
            return msg
        except (json.JSONDecodeError, KeyError) as e:
            Logger.log("LLM", f"⚠️  JSON parse failed ({e}) — wrapping as raw content")

    return AgentMessage(
        from_agent = from_role,
        to_agent   = to_role,
        type       = msg_type,
        content    = (raw[:300] if raw else "Empty response from model"),
        payload    = {"raw": raw, "parse_error": True},
    )


def get_model_for_role(role: str) -> str:
    """Return the assigned Groq model for a given agent role."""
    return MODEL_MAP.get(role, MODEL_MAP["fallback"])


def check_groq() -> tuple[bool, str]:
    """Quick connectivity + auth check. Call this from setup.py."""
    if not _is_api_key_set():
        return False, "GROQ_API_KEY not configured (empty or missing from environment)"
    result = _groq_call("Reply with the single word: OK", MODEL_MAP["tester"], max_tokens=5, retries=0)
    if result and "ok" in result.lower():
        return True, f"Groq ✅  (test via {MODEL_MAP['tester']})"
    if result:
        return True, f"Groq ✅  responded (got: {result[:30]})"
    return False, "Groq unreachable — check key and internet"
