"""harness/freeguard.py
Refuse to run models that could cost money, unless the config says so.

Rules (checked before any API call):
  - Only hosts with a known free tier are allowed by default.
  - OpenRouter is allowed only for model IDs ending in ":free".
  - Anything else (paid APIs, custom endpoints, GPU hosts that bill compute)
    needs `allow_paid = true` on that [[model]] entry.

This cannot see your account: a provider's free tier only stays free while no
billing is attached to the key's project or workspace. Check that in each
provider's dashboard.
"""
from typing import Any
from urllib.parse import urlparse

FREE_TIER_HOSTS = {
    "generativelanguage.googleapis.com",  # Google AI Studio (Gemini)
    "api.groq.com",
    "api.mistral.ai",  # "Experiment" tier
    "integrate.api.nvidia.com",  # NVIDIA NIM developer access
    "api.cerebras.ai",
    "openrouter.ai",  # only ":free" model IDs
}


class PaidModelRefused(Exception):
    pass


def check_model(m: dict[str, Any]) -> None:
    label = m.get("label", "model")
    if m.get("allow_paid") is True:
        return
    adapter = m.get("adapter", "")
    if adapter == "mock":
        return  # test adapter, no network calls
    if adapter in ("anthropic", "openai"):
        raise PaidModelRefused(
            f"{label}: adapter '{adapter}' is a paid API. Set allow_paid = true to use it."
        )
    host = urlparse(m.get("base_url", "")).hostname or ""
    if host not in FREE_TIER_HOSTS:
        raise PaidModelRefused(
            f"{label}: host '{host or '(none)'}' is not a known free-tier host "
            f"({', '.join(sorted(FREE_TIER_HOSTS))}). Set allow_paid = true if you accept "
            "that it may cost money."
        )
    if host == "openrouter.ai" and not str(m.get("model_id", "")).endswith(":free"):
        raise PaidModelRefused(
            f"{label}: OpenRouter model '{m.get('model_id')}' is not a ':free' model."
        )


def check_models(models_cfg: list[dict[str, Any]]) -> None:
    """Raise PaidModelRefused for the first model that could cost money."""
    for m in models_cfg:
        check_model(m)
