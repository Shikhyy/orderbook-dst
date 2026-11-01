"""harness/adapters/anthropic.py
Anthropic Claude API adapter (<= 30 lines).
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

        client: Any = anthropic.Anthropic(api_key=self.api_key)
        t0 = time.time()
        res = client.messages.create(
            model=settings.get("model_id", "claude-3-7-sonnet-20250219"),
            max_tokens=settings.get("max_tokens", 8000),
            temperature=settings.get("temperature", 1.0),
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return ModelReply(
            text=res.content[0].text if res.content else "",
            input_tokens=res.usage.input_tokens,
            output_tokens=res.usage.output_tokens,
            latency_s=time.time() - t0,
            raw_meta={"model": res.model, "stop_reason": res.stop_reason},
        )
