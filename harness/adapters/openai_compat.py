"""harness/adapters/openai_compat.py
OpenAI-compatible server adapter (Ollama, vLLM, LM Studio, OpenRouter, ...).
"""
import os
import time
from typing import Any

from harness.adapters.base import ModelReply, content_to_text


class OpenAICompatAdapter:
    name: str = "openai_compat"

    def __init__(self, base_url: str = "http://localhost:11434/v1") -> None:
        self.base_url = os.environ.get("OPENAI_BASE_URL", base_url)
        self.api_key = os.environ.get("OPENAI_COMPAT_API_KEY", "EMPTY")

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        import openai
        url = settings.get("base_url", self.base_url)
        # Each provider has its own key; models.toml names the environment
        # variable that holds it (api_key_env), never the key itself.
        key_env = settings.get("api_key_env")
        api_key = os.environ.get(key_env, "") if key_env else self.api_key
        if key_env and not api_key:
            raise RuntimeError(f"environment variable {key_env} is not set")
        # Some hosts (for example Modal proxy auth) want "<id>.<secret>" as the bearer
        # token; api_key_secret_env names the variable holding the second part.
        secret_env = settings.get("api_key_secret_env")
        if secret_env:
            secret = os.environ.get(secret_env, "")
            if not secret:
                raise RuntimeError(f"environment variable {secret_env} is not set")
            api_key = f"{api_key}.{secret}"
        client = openai.OpenAI(base_url=url, api_key=api_key, max_retries=0)
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
