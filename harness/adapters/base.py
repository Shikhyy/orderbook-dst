"""harness/adapters/base.py
Model adapter interface and response dataclass.
See docs/08_HARNESS_AND_STATS.md section 5.
"""
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ModelReply:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    raw_meta: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(Protocol):
    name: str

    def generate(
        self,
        system: str,
        prompt: str,
        settings: dict[str, Any],
    ) -> ModelReply: ...
