"""harness/adapters/anthropic.py
Anthropic Claude API adapter.
"""
import os
import time
from typing import Any

from harness.adapters.base import ModelReply


class AnthropicAdapter:
    name: str = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        import anthropic

        client: Any = anthropic.Anthropic(api_key=self.api_key, max_retries=0)
        kwargs: dict[str, Any] = {
            "model": settings["model_id"],
            "max_tokens": settings.get("max_tokens", 8000),
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        # Only send sampling settings that models.toml sets explicitly, so the
        # recorded settings are exactly what the provider received.
        if "temperature" in settings:
            kwargs["temperature"] = settings["temperature"]
        # [model.settings.extra] is passed to the provider unchanged, for options
        # such as extended thinking. Copy the exact parameter names from the
        # provider's API reference.
        kwargs.update(settings.get("extra", {}))
        t0 = time.time()
        res = client.messages.create(**kwargs)
        # Join every text block; skip thinking or other non-text blocks.
        text = "".join(getattr(b, "text", "") for b in res.content if b.type == "text")
        return ModelReply(
            text=text,
            input_tokens=res.usage.input_tokens,
            output_tokens=res.usage.output_tokens,
            latency_s=time.time() - t0,
            raw_meta={"model": res.model, "stop_reason": res.stop_reason},
        )
