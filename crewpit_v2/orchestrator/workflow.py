"""
Workflow — parallel step execution engine.

Groups independent steps and runs them concurrently via ThreadPoolExecutor.
Steps that share keywords (e.g. both touch "database") are kept sequential
to avoid agents overwriting each other's context.

Usage:
    from orchestrator.workflow import WorkflowEngine
    engine = WorkflowEngine(max_workers=3)
    results = engine.run_parallel(steps, run_single_step_fn)
"""

import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout
from utils.logger import Logger

# Per-step timeout in seconds (0 = disabled).
# Override with STEP_TIMEOUT_SECONDS env var.
STEP_TIMEOUT = int(os.environ.get("STEP_TIMEOUT_SECONDS", "120"))

# Keywords that indicate a step MUST be sequential (shared resource risk)
_SEQUENTIAL_KEYWORDS = [
    "database", "db", "schema", "migration",
    "config", "settings", "environment",
    "main", "entry", "app",
]


def _is_sequential(step: str) -> bool:
    step_lower = step.lower()
    return any(k in step_lower for k in _SEQUENTIAL_KEYWORDS)


def group_steps(steps: list[str]) -> list[list[str]]:
    """
    Partition steps into batches.
    - Steps with shared-resource keywords → own sequential batch (size 1)
    - All other steps → grouped into one parallel batch

    Returns a list of batches. Each batch is run fully before the next.
    """
    parallel   = []
    sequential = []

    for step in steps:
        if _is_sequential(step):
            sequential.append(step)
        else:
            parallel.append(step)

    batches = []
    if parallel:
        batches.append(parallel)
    for s in sequential:
        batches.append([s])  # each sequential step is its own batch

    return batches


class WorkflowEngine:

    def __init__(self, max_workers: int = 3):
        self.max_workers  = max_workers
        self.step_timeout = STEP_TIMEOUT  # seconds; 0 = no timeout

    def run_parallel(
        self,
        steps: list[str],
        run_step_fn,                  # callable(step: str) -> dict
    ) -> list[dict]:
        """
        Execute steps, using parallel threads where safe.

        Each future is given at most `self.step_timeout` seconds.
        If it exceeds that, it is cancelled and a timeout error dict is
        returned so the pipeline continues with the remaining steps.

        Thread exceptions are caught, logged with a full traceback, and
        converted to error dicts — they are never silently swallowed.

        Args:
            steps:       list of task step strings
            run_step_fn: function that processes one step and returns a result dict

        Returns:
            List of result dicts in original step order.
        """
        batches = group_steps(steps)
        Logger.log("WORKFLOW", f"{len(steps)} steps → {len(batches)} batch(es) "
                               f"(timeout={self.step_timeout}s)")

        all_results: list[dict] = []

        for batch_idx, batch in enumerate(batches):
            if len(batch) == 1:
                Logger.log("WORKFLOW", f"Batch {batch_idx+1}: sequential — '{batch[0]}'")
                result = self._run_one(run_step_fn, batch[0])
                all_results.append({"step": batch[0], **result})
            else:
                Logger.log("WORKFLOW", f"Batch {batch_idx+1}: parallel × {len(batch)}")
                batch_results: dict[str, dict] = {}

                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch))) as pool:
                    futures = {pool.submit(run_step_fn, step): step for step in batch}

                    # Pass timeout to as_completed so the iterator itself stops
                    # waiting after the deadline — this is what actually cancels
                    # hung steps. The old pattern of as_completed(timeout=None) +
                    # future.result(timeout=N) only timed out result *retrieval*,
                    # not execution.
                    outer_timeout = self.step_timeout if self.step_timeout > 0 else None

                    try:
                        completed_iter = as_completed(futures, timeout=outer_timeout)
                        for future in completed_iter:
                            step = futures[future]
                            try:
                                res = future.result()  # already done; no extra timeout needed
                                batch_results[step] = {"step": step, **res}
                                Logger.log("WORKFLOW", f"  ✅ Done: {step[:60]}")
                            except Exception as e:
                                tb = traceback.format_exc()
                                Logger.log("WORKFLOW",
                                           f"  ❌ Exception in step '{step[:60]}':\n{tb}")
                                batch_results[step] = {
                                    "step":   step,
                                    "code":   "",
                                    "output": "",
                                    "error":  f"{type(e).__name__}: {e}",
                                }
                    except FutureTimeout:
                        # One or more futures did not complete within outer_timeout.
                        # Cancel all remaining futures and record timeout errors.
                        for future, step in futures.items():
                            if step not in batch_results:
                                future.cancel()
                                Logger.log("WORKFLOW",
                                           f"  ⏱  Timeout ({self.step_timeout}s): {step[:60]}")
                                batch_results[step] = {
                                    "step":   step,
                                    "code":   "",
                                    "output": "",
                                    "error":  f"Step timed out after {self.step_timeout}s",
                                }

                # Preserve original batch order in results
                for step in batch:
                    all_results.append(batch_results[step])

        return all_results

    @staticmethod
    def _run_one(fn, step: str) -> dict:
        """Run a single step, catching and returning any exception as an error dict."""
        try:
            return fn(step)
        except Exception as e:
            tb = traceback.format_exc()
            Logger.log("WORKFLOW", f"  ❌ Exception in sequential step '{step[:60]}':\n{tb}")
            return {
                "code":   "",
                "output": "",
                "error":  f"{type(e).__name__}: {e}",
            }
