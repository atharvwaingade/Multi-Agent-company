"""
Crewpit — main pipeline (Groq multi-model edition).

Run:
    cd crewpit_groq
    python app/main.py "build me a calculator web app"

With Groq (recommended):
    export GROQ_API_KEY=gsk_xxxx
    python app/main.py "build me a calculator web app"

Offline fallback (no key needed):
    python app/main.py "build me a calculator web app"   # auto-falls back to Ollama
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.cto_controller import CTOController
from orchestrator.workflow import WorkflowEngine
from agents.critic.critic import CriticAgent
from agents.tester.tester import TesterAgent
from agents.architect.architect import ArchitectAgent
from agents.builder.builder import BuilderAgent
from agents.reviewer.reviewer import ReviewerAgent

from agents.engineer.router import EngineerRouter
from agents.engineer.python_engineer import PythonEngineer
from agents.engineer.frontend_engineer import FrontendEngineer
from agents.engineer.backend_engineer import BackendEngineer
from agents.engineer.ml_engineer import MLEngineer
from agents.engineer.db_engineer import DatabaseEngineer
from agents.engineer.js_engineer import JSEngineer
from agents.engineer.security_engineer import SecurityEngineer
from agents.engineer.testing_engineer import TestingEngineer

from models.llm import call_agent, get_model_for_role, AgentMessage
from utils.helpers import remove_duplicate_functions
from utils.logger import Logger
from utils.project_writer import ProjectWriter
from execution.sandbox import safe_run
from memory.logs import save_log
from memory.learning_memory import find_similar_error, add_memory
from memory.vector_memory import add_vector_memory
from memory.session_memory import SessionMemory


# ─── Engineer factory ──────────────────────────────────────────────────────────

_ENGINEER_MAP = {
    "frontend": FrontendEngineer,
    "backend":  BackendEngineer,
    "ml":       MLEngineer,
    "db":       DatabaseEngineer,
    "js":       JSEngineer,
    "security": SecurityEngineer,
    "testing":  TestingEngineer,
    "python":   PythonEngineer,
}


def get_engineer(agent_type: str):
    return _ENGINEER_MAP.get(agent_type, PythonEngineer)()


def is_executable(agent_types: list[str]) -> bool:
    """Only Python-producing agents can be executed in the sandbox."""
    non_python = {"frontend", "js"}
    return not all(a in non_python for a in agent_types)


# ─── Single step runner (used by WorkflowEngine) ──────────────────────────────

def make_step_runner(
    goal:     str,
    router:   EngineerRouter,
    critic:   CriticAgent,
    tester:   TesterAgent,
    session:  SessionMemory,
    writer:   ProjectWriter,
    cancel_flag=None,
):
    """
    Returns a closure that processes one step end-to-end.
    WorkflowEngine calls this — potentially in parallel threads.

    Agent message flow per step:
        CTO → Engineer  : task (AgentMessage)
        Engineer → CTO  : result (AgentMessage)
        Critic → Engineer: fix_request (AgentMessage)   [on failure]
        Tester → CTO    : validation (AgentMessage)
    """

    def run_step(step: str) -> dict:
        # Check cancellation before starting each step
        if cancel_flag and cancel_flag.is_set():
            Logger.log("CTO", f"🛑 Cancelled — skipping: {step}")
            return {"code": "", "output": "", "error": "cancelled"}

        Logger.log("CTO", f"▶ Step: {step}")

        # ── Route ─────────────────────────────────────────────────────────────
        agent_types  = router.route(step)
        primary_type = agent_types[0]
        engineer     = get_engineer(primary_type)
        model_used   = get_model_for_role(primary_type)

        Logger.log("CTO", f"→ {primary_type} engineer | model: {model_used}")

        # ── CTO sends task to Engineer via AgentMessage ───────────────────────
        context = session.get_context_summary()
        task_content = f"{step}\n\n--- Prior work context ---\n{context}" if context else step

        cto_msg = call_agent(
            from_role = "cto",
            to_role   = primary_type,
            msg_type  = "task",
            prompt    = task_content,
        )
        Logger.log("AGENT_MSG", f"CTO→{primary_type}: {cto_msg.content[:80]}")

        # ── Engineer generates code ───────────────────────────────────────────
        # Pass the structured task from CTO to the engineer's generate_code
        engineer_task = cto_msg.payload.get("context", step) or step
        if cto_msg.payload.get("steps"):
            engineer_task = step + "\n\nSteps to implement:\n" + "\n".join(
                f"- {s}" for s in cto_msg.payload["steps"]
            )

        code = engineer.generate_code(engineer_task)

        if not code.strip():
            Logger.log("ENGINEER", f"⚠️ Empty code for: {step}")
            return {"code": "", "output": "", "error": "Empty code generated"}

        Logger.log("ENGINEER", f"[{primary_type}] Code preview: {code[:120]}...")

        # ── Execute (Python only) ─────────────────────────────────────────────
        can_exec = is_executable(agent_types)
        if can_exec:
            result = safe_run(code)
        else:
            result = {"output": code, "error": None}

        # Log execution result
        if result.get("error"):
            Logger.log("EXECUTOR", f"❌ {result['error'][:200]}")
        else:
            Logger.log("EXECUTOR", f"✅ {str(result.get('output',''))[:200]}")

        # ── Tester validates and sends AgentMessage back to CTO ───────────────
        is_valid = tester.validate(result, code, goal) if can_exec else True

        validation_msg = call_agent(
            from_role = "tester",
            to_role   = "cto",
            msg_type  = "validation",
            prompt    = (
                f"Validate this result for step: {step}\n"
                f"Code length: {len(code)} chars\n"
                f"Output: {str(result.get('output',''))[:300]}\n"
                f"Error: {result.get('error') or 'None'}\n"
                f"Syntax valid: {is_valid}"
            ),
        )
        Logger.log("AGENT_MSG", f"Tester→CTO: passed={validation_msg.passed()} | {validation_msg.content[:60]}")

        save_log({"step": step, "agent": primary_type, "code": code, "result": result})

        # ── Success path ──────────────────────────────────────────────────────
        if is_valid and not result.get("error"):
            Logger.log("CTO", f"✅ Step passed")
            writer.write(primary_type, code)
            add_vector_memory(text=f"{goal} | {step}", code=code)
            session.add_step_result(step, primary_type, code, result)

            # Engineer sends result back to CTO
            call_agent(
                from_role = primary_type,
                to_role   = "cto",
                msg_type  = "result",
                prompt    = f"Step completed: {step}\nCode was {len(code)} chars of {primary_type} code.",
            )
            return {"code": code, "output": result.get("output", ""), "error": None}

        # ── Failure → Critic ──────────────────────────────────────────────────
        Logger.log("CRITIC", "Analyzing failure...")
        error_msg  = result.get("error") or ""
        task_type  = primary_type if primary_type != "frontend" else "html"
        memory_fix = find_similar_error(error_msg, task_type) if error_msg else None

        if memory_fix:
            Logger.log("MEMORY", "⚡ Applying learned fix from memory")
            fixed_code = memory_fix
        else:
            # Critic sends fix_request → Engineer, gets fixed code back
            fixed_code = critic.fix_code(code, error_msg, goal)

        Logger.log("CRITIC", f"Fixed preview: {fixed_code[:120]}...")

        fixed_result = safe_run(fixed_code) if can_exec else {"output": fixed_code, "error": None}

        if fixed_result.get("error"):
            Logger.log("CRITIC", f"❌ Fix still failing")
            add_memory(task_type, {
                "error_type": error_msg.split("\n")[-1][:80],
                "fix": fixed_code,
            })
            session.add_step_result(step, primary_type, "", {"output": "", "error": error_msg})
            return {"code": "", "output": "", "error": error_msg}

        Logger.log("CRITIC", "✅ Fix successful")
        writer.write(primary_type, fixed_code)
        add_vector_memory(text=f"{goal} | {step}", code=fixed_code)
        add_memory(task_type, {
            "error_type": error_msg.split("\n")[-1][:80],
            "fix": fixed_code,
        })
        session.add_step_result(step, primary_type, fixed_code, fixed_result)
        return {"code": fixed_code, "output": fixed_result.get("output", ""), "error": None}

    return run_step


# ─── Main pipeline ─────────────────────────────────────────────────────────────

def run_crewpit(goal: str, cancel_flag=None) -> str:
    """
    Run the full multi-agent pipeline for a goal.
    Returns the path to the output folder.
    """
    Logger.log("SYSTEM", "🚀 Crewpit Groq Edition — Multi-Agent Pipeline")
    Logger.log("CEO",    f"🎯 Goal: {goal}")
    Logger.log("LLM",    f"Orchestration model: {get_model_for_role('architect')}")
    Logger.log("LLM",    f"Engineering model:   {get_model_for_role('engineer')}")
    Logger.log("LLM",    f"Tester model:        {get_model_for_role('tester')}")
    Logger.log("LLM",    f"Builder model:       {get_model_for_role('builder')}")

    # ── Init agents ───────────────────────────────────────────────────────────
    cto       = CTOController()
    architect = ArchitectAgent()
    critic    = CriticAgent()
    tester    = TesterAgent()
    router    = EngineerRouter()
    builder   = BuilderAgent()
    reviewer  = ReviewerAgent()
    workflow  = WorkflowEngine(max_workers=int(os.environ.get("MAX_WORKERS", "2")))

    # ── Init memory + writer ──────────────────────────────────────────────────
    session = SessionMemory()
    session.set_goal(goal)
    writer  = ProjectWriter(goal)

    # ── ARCHITECT → CTO: design handoff ──────────────────────────────────────
    Logger.log("ARCHITECT", f"Designing system... (model: {get_model_for_role('architect')})")
    design = architect.design_system(goal)
    Logger.log("ARCHITECT", f"type={design.get('type')}  components={design.get('components')}")
    session.set_design(design)

    # Architect sends design to CTO as AgentMessage
    call_agent(
        from_role = "architect",
        to_role   = "cto",
        msg_type  = "context",
        prompt    = f"Design complete for goal: {goal}\nType: {design.get('type')}\nComponents: {design.get('components')}",
    )

    # ── CTO plans steps ───────────────────────────────────────────────────────
    components = design.get("components", [])
    steps      = [f"Build component: {c}" for c in components] if components else cto.create_plan(goal)
    Logger.log("CTO", f"Plan ({len(steps)} steps): {steps}")

    # ── EXECUTE (parallel where safe) ─────────────────────────────────────────
    step_runner = make_step_runner(goal, router, critic, tester, session, writer, cancel_flag=cancel_flag)
    results     = workflow.run_parallel(steps, step_runner)

    if cancel_flag and cancel_flag.is_set():
        Logger.log("SYSTEM", "🛑 Run cancelled — skipping build phase")
        return writer.output_dir

    Logger.log("SYSTEM", f"🎉 Pipeline complete — {session.success_count()}/{session.step_count()} steps succeeded")

    # ── BUILD FINAL OUTPUT ────────────────────────────────────────────────────
    all_code     = writer.read_all()
    project_type = design.get("type", "script")

    if not all_code.strip():
        Logger.log("BUILDER", "⚠️ No code generated — check API key or Ollama connection")
        return writer.output_dir

    Logger.log("BUILDER", f"Assembling final {project_type}... (model: {get_model_for_role('builder')})")

    if project_type == "web_app":
        html = builder.build_web_project_content(all_code)
        if html.strip():
            dst = os.path.join(writer.output_dir, "index.html")
            with open(dst, "w", encoding="utf-8") as _f:
                _f.write(html)
            Logger.log("BUILDER", f"🌐 Web project → {dst}")
        else:
            Logger.log("BUILDER", "⚠️ Builder returned empty HTML — check API key or Ollama")
    else:
        final_code = builder.build_python(all_code)
        final_path = os.path.join(writer.output_dir, "final.py")
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(remove_duplicate_functions(final_code))

        Logger.log("EXECUTOR", "Running final assembled program...")
        final_result = safe_run(final_code)
        if final_result.get("error"):
            Logger.log("EXECUTOR", f"❌ {final_result['error']}")
        else:
            Logger.log("EXECUTOR", f"✅ {str(final_result.get('output',''))[:500]}")

    # ── REVIEW FINAL OUTPUT ───────────────────────────────────────────────────
    final_code_for_review = builder.build_python(writer.read_all()) if project_type != "web_app" else writer.read_all()
    if final_code_for_review.strip():
        Logger.log("REVIEWER", f"Reviewing final output... (model: {get_model_for_role('critic')})")
        language = "html" if project_type == "web_app" else "python"
        review_msg = reviewer.review_code(final_code_for_review, goal, language=language)
        approved   = review_msg.passed()
        severity   = review_msg.payload.get("severity", "unknown")
        Logger.log("REVIEWER", f"{'✅ Approved' if approved else '⚠️  Issues found'} "
                               f"(severity={severity}): {review_msg.content[:200]}")
    else:
        Logger.log("REVIEWER", "⚠️  Skipping review — no code to review")

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    writer.write_summary(goal, design, session.get_context_summary())
    Logger.log("SYSTEM", f"📁 Output: {writer.output_dir}")
    return writer.output_dir


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    else:
        goal = input("What do you want to build? ").strip()

    if not goal:
        print("No goal provided.")
        sys.exit(1)

    out = run_crewpit(goal)
    print(f"\n✅ Done. Output folder: {out}")
