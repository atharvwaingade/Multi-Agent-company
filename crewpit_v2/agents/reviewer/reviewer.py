"""
ReviewerAgent — performs a final review pass on assembled code.

Uses the Critic model to check for correctness, completeness, and style,
then returns structured feedback as an AgentMessage.
"""

from models.llm import call_llm, call_agent, AgentMessage


class ReviewerAgent:
    """
    Lightweight post-build reviewer.

    Call review_code() after the BuilderAgent has assembled the final output.
    Returns an AgentMessage of type "review" with issues and suggestions.
    """

    def review_code(self, code: str, goal: str, language: str = "python") -> AgentMessage:
        """
        Review *code* against *goal* and return structured feedback.

        Args:
            code:     The assembled code to review.
            goal:     The original user goal (used as acceptance criteria).
            language: Programming language hint for the reviewer prompt.

        Returns:
            AgentMessage with type="review" and payload keys:
              issues      — list of problems found
              severity    — "low" | "medium" | "high"
              suggestions — list of actionable fix suggestions
              approved    — bool (True if no blocking issues)
        """
        return call_agent(
            from_role="critic",
            to_role="cto",
            msg_type="review",
            prompt=(
                f"Review the following {language} code for the goal: {goal}\n\n"
                f"```{language}\n{code[:3000]}\n```\n\n"
                "Identify any bugs, missing edge-case handling, or style issues. "
                "Be concise and actionable."
            ),
        )

    def quick_review(self, code: str, goal: str) -> str:
        """
        Lightweight single-turn review — returns a plain-text summary.
        Useful when you need human-readable feedback fast without parsing JSON.
        """
        prompt = f"""You are a senior code reviewer.

Review this code for the goal: {goal}

```
{code[:3000]}
```

Provide a short review (3–5 bullet points) covering:
- Correctness: does it implement the goal?
- Bugs or edge cases missed
- Code quality / readability issues
- One concrete improvement suggestion

Be direct and specific.
"""
        return call_llm(prompt, agent_role="critic")
