"""harness/adapters/mock.py
Mock adapter for offline testing and dry runs.
"""
from typing import Any

from harness.adapters.base import ModelReply


class MockAdapter:
    name: str = "mock"

    def __init__(self, response_text: str = ""):
        self.response_text = response_text

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        return ModelReply(
            text=self.response_text or "### FILE: stub\n```python\npass\n```",
            input_tokens=len(prompt) // 4,
            output_tokens=len(self.response_text) // 4 if self.response_text else 10,
            latency_s=0.01,
            raw_meta={"model": "mock-v1", "finish_reason": "stop"},
        )
