import json

import pytest

from core import ollama_client
from core.ollama_client import OllamaError, normalize_base_url, stream_chat

@pytest.mark.parametrize("value, expected", [
    ("", "http://localhost:11434"),
    ("http://localhost:11434/api/generate", "http://localhost:11434"),
    ("http://localhost:11434/api/generate/", "http://localhost:11434"),
    ("http://10.0.0.5:11434/", "http://10.0.0.5:11434"),
    ("localhost:11434", "http://localhost:11434"),
    ("http://apihost:11434", "http://apihost:11434"),
    ("https://example.com/ollama/api/chat", "https://example.com/ollama"),
    ("http://localhost:11434/api", "http://localhost:11434"),
])
def test_normalize_base_url(value, expected):
    assert normalize_base_url(value) == expected

class FakeStream:
    def __init__(self, lines, status_code=200, json_data=None):
        self.lines = lines
        self.status_code = status_code
        self._json = json_data
        self.text = ""
        self.reason = "Error"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        yield from self.lines

    def json(self):
        return self._json

def chunk(content, done=False):
    return json.dumps({"message": {"role": "assistant", "content": content}, "done": done}).encode()

def test_stream_chat_yields_content(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None, stream=None):
        captured.update(url=url, payload=json)
        return FakeStream([chunk("Hel"), b"", chunk("lo"), chunk("", done=True), chunk("ignored")])

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)
    messages = [{"role": "user", "content": "hi"}]
    assert "".join(stream_chat("http://localhost:11434/api/generate", "gemma4:e4b", messages)) == "Hello"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["messages"] == messages
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"]["temperature"] == ollama_client.CHAT_TEMPERATURE

def test_stream_chat_stops_early(monkeypatch):
    monkeypatch.setattr(ollama_client.requests, "post", lambda *a, **k: FakeStream([chunk("a"), chunk("b")]))
    stop = iter([False, True])
    assert list(stream_chat("", "m", [], should_stop=lambda: next(stop))) == ["a"]

def test_stream_chat_reports_ollama_error(monkeypatch):
    monkeypatch.setattr(
        ollama_client.requests, "post",
        lambda *a, **k: FakeStream([], status_code=404, json_data={"error": "model 'nope' not found"}),
    )
    with pytest.raises(OllamaError, match="not found"):
        list(stream_chat("", "nope", []))
