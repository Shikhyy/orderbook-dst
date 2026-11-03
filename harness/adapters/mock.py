"""harness/adapters/mock.py
Mock adapter for offline testing and dry runs.
"""

from typing import Any, Optional

from harness.adapters.base import ModelReply


class MockAdapter:
    name: str = "mock"

    def __init__(
        self,
        response_text: str = "",
        responses: Optional[list[str]] = None,
    ):
        self.response_text = response_text
        self.responses = list(responses) if responses else []
        self._call_count = 0

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        if self.responses and self._call_count < len(self.responses):
            resp = self.responses[self._call_count]
        else:
            resp = self.response_text or "### FILE: stub\n```python\npass\n```"
        self._call_count += 1
        return ModelReply(
            text=resp,
            input_tokens=len(prompt) // 4,
            output_tokens=len(resp) // 4 if resp else 10,
            latency_s=0.01,
            raw_meta={"model": "mock-v1", "finish_reason": "stop"},
        )
