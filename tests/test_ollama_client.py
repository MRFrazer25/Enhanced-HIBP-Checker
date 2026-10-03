import json
import threading

import pytest
import requests

from core import ollama_client
from core.ollama_client import CancellableRequest, OllamaError, list_models, normalize_base_url, stream_chat

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

def test_stream_chat_ssl_error_is_not_generic_connection_message(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.SSLError("bad cert")
    monkeypatch.setattr(ollama_client.requests, "post", boom)
    with pytest.raises(OllamaError, match="certificate") as excinfo:
        list(stream_chat("", "m", []))
    assert isinstance(excinfo.value.__cause__, requests.exceptions.SSLError)
    assert "Is Ollama running" not in str(excinfo.value)

def test_stream_chat_errors_chain_cause(monkeypatch):
    monkeypatch.setattr(
        ollama_client.requests, "post",
        lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.ConnectionError("boom")),
    )
    with pytest.raises(OllamaError, match="connect") as excinfo:
        list(stream_chat("", "m", []))
    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)

def test_list_models_ssl_error(monkeypatch):
    monkeypatch.setattr(
        ollama_client.requests, "get",
        lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.SSLError("bad cert")),
    )
    with pytest.raises(OllamaError, match="certificate") as excinfo:
        list_models("https://ollama.example")
    assert isinstance(excinfo.value.__cause__, requests.exceptions.SSLError)

def test_cancellable_request_close_unblocks_before_first_token(monkeypatch):
    started = threading.Event()
    released = threading.Event()

    class BlockingStream:
        def __init__(self):
            self.status_code = 200
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def close(self):
            self.closed = True
            released.set()

        def iter_lines(self):
            started.set()
            if not released.wait(2):
                raise AssertionError("close() was not called")
            raise requests.exceptions.ConnectionError("read aborted")

    stream = BlockingStream()
    cancel = CancellableRequest()

    class FakeSession:
        def mount(self, *a, **k):
            pass

        def post(self, *a, **k):
            cancel.attach_response(stream)
            return stream

        def close(self):
            stream.close()

    monkeypatch.setattr(ollama_client.requests, "Session", FakeSession)

    def closer():
        started.wait(2)
        cancel.close()

    threading.Thread(target=closer, daemon=True).start()
    assert list(stream_chat("", "m", [], cancel=cancel)) == []
    assert cancel.aborted()
    assert stream.closed
