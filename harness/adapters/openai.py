"""harness/adapters/openai.py
OpenAI API adapter.
"""
import os
import time
from typing import Any

from harness.adapters.base import ModelReply, content_to_text


class OpenAIAdapter:
    name: str = "openai"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        import openai
        client = openai.OpenAI(api_key=self.api_key, max_retries=0)
        kwargs: dict[str, Any] = {
            "model": settings["model_id"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        # Only send settings that models.toml sets explicitly. Reasoning models
        # reject a non-default temperature, so it is never sent by default.
        if "temperature" in settings:
            kwargs["temperature"] = settings["temperature"]
        if "max_tokens" in settings:
            kwargs["max_completion_tokens"] = settings["max_tokens"]
        if "reasoning_effort" in settings:
            kwargs["reasoning_effort"] = settings["reasoning_effort"]
        # [model.settings.extra] is passed to the provider unchanged, for options
        # such as extended thinking. Copy the exact parameter names from the
        # provider's API reference.
        kwargs.update(settings.get("extra", {}))
        t0 = time.time()
        res = client.chat.completions.create(**kwargs)
        choice = res.choices[0]
        usage = res.usage
        return ModelReply(
            text=content_to_text(choice.message.content),
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_s=time.time() - t0,
            raw_meta={"model": res.model, "finish_reason": choice.finish_reason},
        )
