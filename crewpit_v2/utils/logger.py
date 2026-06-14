"""
Logger — colored console output with AGENT_MSG support for inter-agent messages.

Thread-safety: per-thread log overrides are stored in threading.local() so
concurrent pipeline runs cannot overwrite each other's scoped logger.
"""
import datetime
import threading

_local = threading.local()


class Logger:

    COLORS = {
        "SYSTEM":    "\033[96m",    # cyan
        "CEO":       "\033[91m",    # bright red
        "CTO":       "\033[94m",    # blue
        "ARCHITECT": "\033[35m",    # magenta
        "ENGINEER":  "\033[92m",    # green
        "CRITIC":    "\033[33m",    # yellow
        "EXECUTOR":  "\033[93m",    # bright yellow
        "TESTER":    "\033[95m",    # bright magenta
        "BUILDER":   "\033[36m",    # dark cyan
        "MEMORY":    "\033[90m",    # dark grey
        "LLM":       "\033[37m",    # light grey
        "WORKFLOW":  "\033[34m",    # dark blue
        "AGENT_MSG": "\033[38;5;208m",  # orange — inter-agent messages
        "SANDBOX":   "\033[38;5;160m",  # red-orange
        "RESET":     "\033[0m",
    }

    @staticmethod
    def log(agent: str, message: str) -> None:
        # If the current thread has a scoped override, use it.
        override = getattr(_local, "log_override", None)
        if override is not None:
            override(agent, message)
            return
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        color = Logger.COLORS.get(agent, Logger.COLORS.get("RESET", ""))
        reset = Logger.COLORS["RESET"]
        print(f"{color}[{ts}] [{agent}] {message}{reset}")

    @staticmethod
    def set_thread_override(fn):
        """Install a per-thread log handler (used by the SSE server for run scoping)."""
        _local.log_override = fn

    @staticmethod
    def clear_thread_override():
        """Remove the per-thread log handler, restoring default behaviour."""
        _local.log_override = None
