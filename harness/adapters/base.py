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


def content_to_text(content: Any) -> str:
    """Final answer text from a chat-completions message content.

    Most providers return a string. Some (for example Mistral's reasoning
    models) return a list of blocks such as {"type": "thinking", ...} followed
    by {"type": "text", "text": "..."}. Only the text blocks are the answer.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type", "text") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        else:
            if getattr(block, "type", "text") == "text" and isinstance(
                getattr(block, "text", None), str
            ):
                parts.append(block.text)
    return "".join(parts)
