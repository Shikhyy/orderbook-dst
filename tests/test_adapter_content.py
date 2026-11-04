from harness.adapters.base import content_to_text


def test_plain_string_and_none():
    assert content_to_text("hello") == "hello"
    assert content_to_text(None) == ""


def test_mistral_style_thinking_then_text_blocks():
    content = [
        {"type": "thinking", "thinking": [{"type": "text", "text": "hmm"}], "closed": True},
        {"type": "text", "text": "```python\nx = 1\n```"},
    ]
    assert content_to_text(content) == "```python\nx = 1\n```"


def test_multiple_text_blocks_are_joined_and_objects_supported():
    class B:
        def __init__(self, type, text=None):
            self.type, self.text = type, text

    assert content_to_text([B("text", "a"), B("thinking", "no"), B("text", "b")]) == "ab"
    assert content_to_text([{"text": "x"}, "y"]) == "xy"


def test_two_part_api_key_is_joined(monkeypatch):
    import openai

    from harness.adapters.openai_compat import OpenAICompatAdapter

    seen = {}

    class FakeClient:
        def __init__(self, base_url=None, api_key=None, max_retries=None):
            seen["key"] = api_key
            raise RuntimeError("stop")

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("T_ID", "wk-id")
    monkeypatch.setenv("T_SECRET", "ws-secret")
    settings = {"model_id": "m", "base_url": "http://x/v1",
                "api_key_env": "T_ID", "api_key_secret_env": "T_SECRET"}
    try:
        OpenAICompatAdapter().generate("s", "p", settings)
    except RuntimeError:
        pass
    assert seen["key"] == "wk-id.ws-secret"
    monkeypatch.delenv("T_SECRET")
    try:
        OpenAICompatAdapter().generate("s", "p", settings)
    except RuntimeError as e:
        assert "T_SECRET" in str(e)
