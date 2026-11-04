"""The free-only guard: nothing that could cost money runs without allow_paid."""
import pytest

from harness.freeguard import PaidModelRefused, check_models


def _m(**kw):
    base = {"label": "x", "adapter": "openai_compat", "model_id": "m"}
    base.update(kw)
    return base


@pytest.mark.parametrize("url", [
    "https://generativelanguage.googleapis.com/v1beta/openai/",
    "https://api.groq.com/openai/v1",
    "https://api.mistral.ai/v1",
    "https://integrate.api.nvidia.com/v1",
])
def test_known_free_hosts_allowed(url):
    check_models([_m(base_url=url)])


def test_openrouter_only_free_models():
    url = "https://openrouter.ai/api/v1"
    check_models([_m(base_url=url, model_id="google/gemma-4-31b-it:free")])
    with pytest.raises(PaidModelRefused, match="not a ':free' model"):
        check_models([_m(base_url=url, model_id="anthropic/claude-x")])


@pytest.mark.parametrize("cfg", [
    {"adapter": "anthropic"},
    {"adapter": "openai"},
    {"base_url": "https://sumanyuchu--ep-yooo-server.us-west.modal.direct/v1"},
    {"base_url": "http://localhost:11434/v1"},
    {},
])
def test_paid_or_unknown_refused_unless_allowed(cfg):
    with pytest.raises(PaidModelRefused):
        check_models([_m(**cfg)])
    check_models([_m(**cfg, allow_paid=True)])


def test_mock_adapter_exempt():
    check_models([{"label": "t", "adapter": "mock", "model_id": "mock"}])
