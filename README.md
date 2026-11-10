# Self-Correcting Codegen Agent

A multi-step agent that writes code, runs the tests, and repairs its own code from the failure output. It stops when the tests pass, when the same failure repeats, or when its model-call budget runs out. Each step is recorded in a trace.

This covers the JD's "multi-step agents for code generation, self-correction and automated bug fixing."

## How it works

1. **Generate:** the model writes a first version from the task.
2. **Test:** the code and tests run in an isolated process with a time limit.
3. **Repair:** on failure, the model receives the previous code and the failure message.
4. **Stop when:**
   - the tests pass (success)
   - the same failure happens twice in a row (it is not making progress, so stop early to save cost)
   - the iteration limit is reached
   - the model-call budget is used up

The trace lists every step with pass or fail, the timeout flag, and the error summary.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q                       # uses scripted models; no API calls

export OPENAI_API_KEY="<your key>"
uvicorn agent.main:app --reload
```

`POST /api/solve` with:

```json
{
  "prompt": "Return the sum of two integers.",
  "tests": "assert add(2, 3) == 5\nassert add(-1, 1) == 0\n",
  "max_iterations": 4,
  "max_model_calls": 6
}
```

The response includes `success`, `stop_reason`, the final `code`, `model_calls`, and the `steps` trace.

## Safety and cost controls

- Candidate code runs in a separate process with `-I`, a time limit, and no inherited environment, so API keys are not passed to it.
- Model calls are capped per request, and the request limits are enforced server-side (max 6 iterations, max 10 calls).
- Production: run it in a container with networking limited to the model API. Process limits alone don't stop network access or file writes outside the temp folder.

## Limits

- Tests are the only success signal. Weak tests produce false passes, so pair this with the evaluation harness in `codegen-eval-harness`.
- The sandbox is process-level. Use containers for untrusted tasks.
- The agent does not plan across files yet. It repairs one function or module at a time.

## Structure

```
agent/
  sandbox.py  isolated test runs with timeout and error summary
  loop.py     generate, test, repair, and stop rules with trace
  model.py    OpenAI-backed generate and repair
  main.py     HTTP API
tests/        loop rules, timeouts, budgets, API
```
