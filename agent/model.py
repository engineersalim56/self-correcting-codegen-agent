"""OpenAI-backed generate and repair functions. Each returns Python source code only."""
import json
import os
from dataclasses import dataclass

import httpx

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


@dataclass(frozen=True)
class ModelConfig:
    api_key: str
    model: str = "gpt-4o-mini"


def config_from_env() -> ModelConfig | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return ModelConfig(api_key=key, model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")) if key else None


def _ask(config: ModelConfig, prompt: str, transport: httpx.BaseTransport | None) -> str:
    body = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    with httpx.Client(timeout=45, transport=transport) as client:
        response = client.post(OPENAI_URL, headers={"Authorization": f"Bearer {config.api_key}"}, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"model API returned HTTP {response.status_code}")
    return json.loads(response.json()["choices"][0]["message"]["content"])["code"]


def make_generate(config: ModelConfig, transport=None):
    def generate(task_prompt: str) -> str:
        return _ask(config, f"Write Python 3 code for this task. Return JSON {{\"code\": \"...\"}} with source only.\n\nTask: {task_prompt}", transport)
    return generate


def make_repair(config: ModelConfig, transport=None):
    def repair(task_prompt: str, previous_code: str, error_summary: str) -> str:
        prompt = (
            "Fix this Python code so the tests pass. Return JSON {\"code\": \"...\"} with the full corrected source only.\n\n"
            f"Task: {task_prompt}\n\nCurrent code:\n{previous_code}\n\nTest failure:\n{error_summary}"
        )
        return _ask(config, prompt, transport)
    return repair
