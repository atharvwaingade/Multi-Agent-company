"""
EngineerRouter — determines which specialist engineer(s) to use for a task.

Returns a list so a single task can involve multiple specialists
(e.g. a "database-backed API with a frontend" needs backend + db + frontend).
"""


class EngineerRouter:

    # Ordered keyword rules — most specific first
    _RULES = [
        ("frontend",  ["html", "css", "ui", "frontend", "webpage", "website", "landing page", "component"]),
        ("backend",   ["api", "backend", "server", "fastapi", "flask", "django", "endpoint", "rest", "route"]),
        ("ml",        ["ml", "machine learning", "train", "model", "neural", "dataset", "sklearn", "pytorch", "tensorflow"]),
        ("db",        ["database", "sql", "sqlite", "postgres", "mysql", "mongodb", "db", "schema", "migration", "orm"]),
        ("js",        ["javascript", "typescript", "node", "npm", "react", "vue", "angular", "express"]),
        ("security",  ["auth", "authentication", "jwt", "oauth", "password", "encrypt", "security"]),
        ("testing",   ["test", "pytest", "unittest", "spec", "coverage", "mock"]),
    ]

    def route(self, task: str) -> list[str]:
        """Return ordered list of engineer types needed for this task."""
        task_lower = task.lower()
        matched = []

        for agent_type, keywords in self._RULES:
            if any(k in task_lower for k in keywords):
                matched.append(agent_type)

        # Always have at least a Python engineer as default
        if not matched:
            matched = ["python"]

        return matched

    def route_primary(self, task: str) -> str:
        """Backward-compatible single-engineer routing."""
        return self.route(task)[0]
