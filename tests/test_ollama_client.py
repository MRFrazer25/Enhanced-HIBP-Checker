import json
import threading

import pytest
import requests

from core import ollama_client
from core.ollama_client import (
    CancellableRequest,
    OllamaError,
    is_unencrypted_remote,
    list_models,
    normalize_base_url,
    stream_chat,
)

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

# Addresses typed without a scheme get http:// only on this machine; any other host gets https://
@pytest.mark.parametrize("value, expected", [
    ("localhost", "http://localhost"),
    ("LOCALHOST:11434", "http://LOCALHOST:11434"),
    ("127.0.0.1:11434", "http://127.0.0.1:11434"),
    ("127.1.2.3:11434", "http://127.1.2.3:11434"),
    ("::1", "http://[::1]"),
    ("[::1]:11434", "http://[::1]:11434"),
    ("host.docker.internal:11434", "http://host.docker.internal:11434"),
    ("ollama.example.com:11434", "https://ollama.example.com:11434"),
    ("10.0.0.5:11434/api/chat", "https://10.0.0.5:11434"),
    ("localhost.example.com", "https://localhost.example.com"),
    ("128.0.0.1:11434", "https://128.0.0.1:11434"),
    ("[2001:db8::1]:11434", "https://[2001:db8::1]:11434"),
    # An explicit scheme is always kept, so a LAN server over plain http still works
    ("http://192.168.1.20:11434", "http://192.168.1.20:11434"),
    ("https://localhost:11434", "https://localhost:11434"),
])
def test_default_scheme(value, expected):
    assert normalize_base_url(value) == expected

@pytest.mark.parametrize("value, expected", [
    ("", False),
    ("http://localhost:11434", False),
    ("http://127.0.0.1:11434", False),
    ("http://[::1]:11434", False),
    ("192.168.1.20:11434", False),  # becomes https://
    ("https://192.168.1.20:11434", False),
    ("http://192.168.1.20:11434", True),
    ("http://ollama.example.com", True),
])
def test_is_unencrypted_remote(value, expected):
    assert is_unencrypted_remote(value) is expected

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
    assert captured["payload"]["options"]["num_ctx"] == ollama_client.CHAT_CONTEXT_TOKENS

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


def test_stream_that_ends_without_done_is_an_error(monkeypatch):
    monkeypatch.setattr(ollama_client.requests, "post", lambda *a, **k: FakeStream([chunk("Half an ans")]))
    received = []
    with pytest.raises(OllamaError, match="before the reply was finished"):
        for part in stream_chat("", "m", []):
            received.append(part)
    assert received == ["Half an ans"]
