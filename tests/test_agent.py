from fastapi.testclient import TestClient

from agent import main
from agent.loop import solve
from agent.sandbox import run_tests

ADD_TESTS = "assert add(2, 3) == 5\nassert add(-1, 1) == 0\n"
GOOD_ADD = "def add(a, b):\n    return a + b\n"
WRONG_ADD = "def add(a, b):\n    return a - b\n"


def scripted_repair(answers):
    queue = list(answers)

    def repair(prompt, previous, error):
        return queue.pop(0)

    return repair


def test_passes_on_first_try_with_one_model_call():
    result = solve("add two numbers", ADD_TESTS, lambda p: GOOD_ADD, scripted_repair([]))
    assert result.success is True
    assert result.stop_reason == "passed"
    assert result.model_calls == 1
    assert len(result.steps) == 1


def test_repairs_from_test_failure_and_succeeds():
    result = solve("add two numbers", ADD_TESTS, lambda p: WRONG_ADD, scripted_repair([GOOD_ADD]))
    assert result.success is True
    assert [s.passed for s in result.steps] == [False, True]
    assert result.steps[0].error  # the failure was recorded for the trace


def test_repair_receives_the_failing_code_and_error():
    seen = {}

    def repair(prompt, previous, error):
        seen["previous"] = previous
        seen["error"] = error
        return GOOD_ADD

    solve("add two numbers", ADD_TESTS, lambda p: WRONG_ADD, repair)
    assert seen["previous"] == WRONG_ADD
    assert "AssertionError" in seen["error"]


def test_stops_on_repeated_identical_failure():
    calls = []

    def repair(prompt, previous, error):
        calls.append(1)
        return WRONG_ADD  # never improves

    result = solve("add two numbers", ADD_TESTS, lambda p: WRONG_ADD, repair, max_iterations=6)
    assert result.success is False
    assert result.stop_reason == "repeated_error"
    assert len(calls) == 1  # stopped after the second identical failure, not after six


def test_model_call_budget_is_enforced():
    # Each attempt fails with a different message, so the repeated-error rule does not fire first.
    attempts = iter(range(100))

    def different_failure(_=None, *args):
        return f"def add(a, b):\n    raise ValueError('attempt {next(attempts)}')\n"

    result = solve("add two numbers", ADD_TESTS, different_failure, lambda p, c, e: different_failure(),
                   max_iterations=10, max_model_calls=2)
    assert result.stop_reason == "model_calls_exhausted"
    assert result.model_calls == 2


def test_identical_failures_stop_before_budget():
    result = solve("add two numbers", ADD_TESTS, lambda p: WRONG_ADD, lambda p, c, e: WRONG_ADD,
                   max_iterations=10, max_model_calls=10)
    assert result.stop_reason == "repeated_error"
    assert result.model_calls == 2


def test_timeout_is_reported_as_a_failed_step():
    looping = "def add(a, b):\n    while True:\n        pass\n"
    outcome = run_tests(looping, ADD_TESTS, timeout_s=1)
    assert outcome.timed_out is True and outcome.passed is False


def test_api_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(main.app).post("/api/solve", json={"prompt": "add two numbers please", "tests": ADD_TESTS})
    assert response.status_code == 503


def test_health():
    assert TestClient(main.app).get("/health").json() == {"status": "ok"}
