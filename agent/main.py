"""HTTP API: POST a task with tests, get back the final code and a full trace."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .loop import solve
from .model import config_from_env, make_generate, make_repair

app = FastAPI(title="Self-Correcting Codegen Agent", version="0.1.0")


class SolveRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=4000)
    tests: str = Field(min_length=5, max_length=8000)
    max_iterations: int = Field(default=4, ge=1, le=6)
    max_model_calls: int = Field(default=6, ge=1, le=10)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/solve")
def solve_task(request: SolveRequest) -> dict:
    config = config_from_env()
    if config is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set")
    result = solve(
        request.prompt,
        request.tests,
        make_generate(config),
        make_repair(config),
        max_iterations=request.max_iterations,
        max_model_calls=request.max_model_calls,
    )
    return result.to_dict()
