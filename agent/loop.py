"""Plan-free repair loop: generate, test, repair from the failure, and stop on success, a repeated failure, or a budget limit.

Every step is recorded in a trace, so a reviewer can see what the agent tried and why it stopped.
"""
from dataclasses import asdict, dataclass, field
from typing import Callable

from .sandbox import run_tests

# generate(task_prompt) -> code
# repair(task_prompt, previous_code, error_summary) -> code
Generate = Callable[[str], str]
Repair = Callable[[str, str, str], str]


@dataclass
class Step:
    iteration: int
    passed: bool
    timed_out: bool
    error: str


@dataclass
class AgentResult:
    success: bool
    stop_reason: str  # "passed", "max_iterations", "repeated_error", "model_calls_exhausted"
    code: str
    steps: list[Step] = field(default_factory=list)
    model_calls: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stop_reason": self.stop_reason,
            "code": self.code,
            "model_calls": self.model_calls,
            "steps": [asdict(s) for s in self.steps],
        }


def solve(
    task_prompt: str,
    tests: str,
    generate: Generate,
    repair: Repair,
    max_iterations: int = 4,
    max_model_calls: int = 6,
    timeout_s: float = 5.0,
) -> AgentResult:
    calls = 0
    code = ""
    last_error: str | None = None
    result_steps: list[Step] = []

    def call(fn, *args) -> str:
        nonlocal calls
        calls += 1
        return fn(*args)

    for iteration in range(1, max_iterations + 1):
        if iteration == 1:
            if calls >= max_model_calls:
                return AgentResult(False, "model_calls_exhausted", code, result_steps, calls)
            code = call(generate, task_prompt)
        else:
            if calls >= max_model_calls:
                return AgentResult(False, "model_calls_exhausted", code, result_steps, calls)
            code = call(repair, task_prompt, code, last_error or "unknown failure")

        outcome = run_tests(code, tests, timeout_s=timeout_s)
        error = outcome.error_summary or ("passed" if outcome.passed else "failed")
        result_steps.append(Step(iteration, outcome.passed, outcome.timed_out, error))

        if outcome.passed:
            return AgentResult(True, "passed", code, result_steps, calls)
        if last_error is not None and error == last_error:
            # The same failure twice in a row means the repair is not making progress. Stop instead of spending more calls.
            return AgentResult(False, "repeated_error", code, result_steps, calls)
        last_error = error

    return AgentResult(False, "max_iterations", code, result_steps, calls)
