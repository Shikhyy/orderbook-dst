"""harness/adapters/openai_compat.py
OpenAI-compatible server adapter (<= 30 lines).
"""
import os
import time
from typing import Any

from harness.adapters.base import ModelReply


class OpenAICompatAdapter:
    name: str = "openai_compat"

    def __init__(self, base_url: str = "http://localhost:11434/v1") -> None:
        self.base_url = os.environ.get("OPENAI_BASE_URL", base_url)
        self.api_key = os.environ.get("OPENAI_API_KEY", "EMPTY")

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        import openai
        url = settings.get("base_url", self.base_url)
        client = openai.OpenAI(base_url=url, api_key=self.api_key)
        t0 = time.time()
        res = client.chat.completions.create(
            model=settings.get("model_id", "default"),
            temperature=settings.get("temperature", 1.0),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        choice = res.choices[0]
        usage = res.usage
        return ModelReply(
            text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_s=time.time() - t0,
            raw_meta={"model": res.model, "finish_reason": choice.finish_reason},
        )
