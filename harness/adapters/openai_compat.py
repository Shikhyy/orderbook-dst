"""harness/adapters/openai_compat.py
OpenAI-compatible server adapter (Ollama, vLLM, LM Studio, OpenRouter, ...).
"""
import os
import time
from typing import Any

from harness.adapters.base import ModelReply


class OpenAICompatAdapter:
    name: str = "openai_compat"

    def __init__(self, base_url: str = "http://localhost:11434/v1") -> None:
        self.base_url = os.environ.get("OPENAI_BASE_URL", base_url)
        self.api_key = os.environ.get("OPENAI_COMPAT_API_KEY", "EMPTY")

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        import openai
        url = settings.get("base_url", self.base_url)
        client = openai.OpenAI(base_url=url, api_key=self.api_key)
        kwargs: dict[str, Any] = {
            "model": settings["model_id"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if "temperature" in settings:
            kwargs["temperature"] = settings["temperature"]
        if "max_tokens" in settings:
            kwargs["max_tokens"] = settings["max_tokens"]
        t0 = time.time()
        res = client.chat.completions.create(**kwargs)
        choice = res.choices[0]
        usage = res.usage
        return ModelReply(
            text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_s=time.time() - t0,
            raw_meta={"model": res.model, "finish_reason": choice.finish_reason},
        )
