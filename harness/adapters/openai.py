"""harness/adapters/openai.py
OpenAI API adapter (<= 30 lines).
"""
import os
import time
from typing import Any

from harness.adapters.base import ModelReply


class OpenAIAdapter:
    name: str = "openai"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        import openai
        client = openai.OpenAI(api_key=self.api_key)
        t0 = time.time()
        res = client.chat.completions.create(
            model=settings.get("model_id", "gpt-4o"),
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
