# Multi-Agent-company

This repository now contains the extracted **Crewpit v2** project under:

- `/home/runner/work/Multi-Agent-company/Multi-Agent-company/atharvwaingade/Multi-Agent-company/crewpit_v2`

## What this project is

Crewpit v2 is a Python-based multi-agent software builder. It coordinates specialized agents (architect, engineers, tester, reviewer, critic, and builder) to turn a plain-English goal into generated project output.

## Repository structure

- `crewpit_v2/` — main application source code
- `crewpit_v2/app/` — CLI and web entrypoints
- `crewpit_v2/agents/` — agent role implementations
- `crewpit_v2/orchestrator/` — workflow and task coordination
- `crewpit_v2/models/` — LLM integration and routing

## Quick start

1. Move into the project directory:
   ```bash
   cd crewpit_v2
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run setup checks:
   ```bash
   python setup.py
   ```
4. Start the web interface:
   ```bash
   python app/server.py
   ```
5. Or run from CLI:
   ```bash
   python app/main.py "build me a calculator web app"
   ```

## Notes

- Set `GROQ_API_KEY` in your environment (or use `.env`) to enable Groq models.
- If Groq is unavailable, the project can fall back to Ollama when configured.

For more details, see `crewpit_v2/README.md`.
