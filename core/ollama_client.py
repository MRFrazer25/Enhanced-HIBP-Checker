"""
Minimal client for a local Ollama server.

Uses the /api/chat endpoint so the AI advisor keeps conversation history,
and /api/tags to list the models that have been pulled locally.
"""
import json
import socket
import threading
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter

DEFAULT_OLLAMA_URL = "http://localhost:11434"
# (connect, read) timeouts. Large models can take a while to load before the first token.
CHAT_TIMEOUT = (10, 300)
TAGS_TIMEOUT = 5
CHAT_TEMPERATURE = 0.3

class OllamaError(Exception):
    """Raised when Ollama can't be reached or returns an error."""
    pass

class CancellableRequest:
    """An in-flight Ollama HTTP request that the UI thread can abort.

    Stop and New Chat call close() so a blocked read ends immediately, including
    while the model is still loading and no tokens have arrived yet.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._aborted = False
        self._session = None
        self._response = None
        self._sockets = []

    def aborted(self) -> bool:
        return self._aborted

    def attach_session(self, session: requests.Session):
        with self._lock:
            self._session = session
            if self._aborted:
                self._close_locked()

    def attach_response(self, response: requests.Response):
        with self._lock:
            self._response = response
            raw = getattr(response, "raw", None)
            conn = getattr(raw, "_connection", None) or getattr(raw, "connection", None)
            sock = getattr(conn, "sock", None) if conn is not None else None
            if sock is not None:
                self._sockets.append(sock)
            if self._aborted:
                self._close_locked()

    def watch_connection(self, conn):
        with self._lock:
            sock = getattr(conn, "sock", None)
            if sock is not None:
                self._sockets.append(sock)
            orig_connect = getattr(conn, "connect", None)
            if orig_connect is not None and not getattr(conn, "_hibp_connect_wrapped", False):
                def connect_and_track():
                    orig_connect()
                    self._track_socket(getattr(conn, "sock", None))
                conn.connect = connect_and_track
                conn._hibp_connect_wrapped = True
            if self._aborted:
                self._close_locked()

    def _track_socket(self, sock):
        with self._lock:
            if sock is not None:
                self._sockets.append(sock)
            if self._aborted:
                self._close_locked()

    def close(self):
        with self._lock:
            self._aborted = True
            self._close_locked()

    def _close_locked(self):
        for sock in self._sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        self._sockets.clear()
        if self._response is not None:
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

class _AbortableAdapter(HTTPAdapter):
    """Captures the live connection so CancellableRequest can shut its socket down."""

    def __init__(self, tracker: CancellableRequest, **kwargs):
        self._tracker = tracker
        super().__init__(**kwargs)

    def get_connection(self, url, proxies=None):
        conn = super().get_connection(url, proxies)
        self._tracker.watch_connection(conn)
        return conn

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        conn = super().get_connection_with_tls_context(request, verify, proxies, cert)
        self._tracker.watch_connection(conn)
        return conn

def normalize_base_url(url: str) -> str:
    """Turns whatever the user entered into the Ollama server's base URL.

    Older versions of this app stored the full /api/generate endpoint, so any
    trailing /api/... path is stripped.
    """
    url = (url or "").strip()
    if not url:
        return DEFAULT_OLLAMA_URL
    if "://" not in url:
        url = "http://" + url
    parts = urlsplit(url)
    path = parts.path
    api_index = path.find("/api/")
    if api_index != -1 or path.endswith("/api"):
        path = path[:api_index] if api_index != -1 else path[:-len("/api")]
    return urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))

def list_models(base_url: str) -> list:
    """Returns the names of the models available on the Ollama server."""
    try:
        response = requests.get(f"{normalize_base_url(base_url)}/api/tags", timeout=TAGS_TIMEOUT)
        response.raise_for_status()
        return sorted(m["name"] for m in response.json().get("models", []))
    except requests.exceptions.SSLError as e:
        raise OllamaError(
            f"Secure connection to Ollama at {normalize_base_url(base_url)} failed (certificate problem)."
        ) from e
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(f"Could not connect to Ollama at {normalize_base_url(base_url)}. Is Ollama running?") from e
    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        raise OllamaError(f"Error fetching models: {e}") from e

def stream_chat(base_url: str, model: str, messages: list, should_stop=lambda: False, cancel=None):
    """Streams a chat completion from Ollama, yielding text chunks as they arrive.

    Args:
        base_url: The Ollama server URL.
        model: The model name.
        messages: The conversation as a list of {"role": ..., "content": ...} dicts.
        should_stop: Called between chunks; returning True ends the stream early.
        cancel: Optional CancellableRequest. close() from another thread aborts
            the HTTP connection immediately, including before the first token.

    Raises:
        OllamaError: If Ollama can't be reached or reports an error.
    """
    url = f"{normalize_base_url(base_url)}/api/chat"
    # Thinking is turned off: on typical laptops (CPU only) a reasoning phase can add minutes
    # before the first word appears, and it isn't needed for this kind of advice.
    # A low temperature keeps advice consistent and makes the model follow its instructions more reliably.
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": {"temperature": CHAT_TEMPERATURE},
    }
    session = None
    try:
        if cancel is not None and cancel.aborted():
            return
        if cancel is None:
            context = requests.post(url, json=payload, timeout=CHAT_TIMEOUT, stream=True)
        else:
            session = requests.Session()
            adapter = _AbortableAdapter(cancel)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            cancel.attach_session(session)
            if cancel.aborted():
                return
            context = session.post(url, json=payload, timeout=CHAT_TIMEOUT, stream=True)
        with context as response:
            if cancel is not None:
                cancel.attach_response(response)
                if cancel.aborted():
                    return
            if response.status_code != 200:
                raise OllamaError(_error_from_response(response))
            for line in response.iter_lines():
                if _cancelled(should_stop, cancel):
                    return
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("error"):
                    raise OllamaError(data["error"])
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    return
    except requests.exceptions.SSLError as e:
        if _cancelled(should_stop, cancel):
            return
        raise OllamaError(
            f"Secure connection to Ollama at {normalize_base_url(base_url)} failed (certificate problem)."
        ) from e
    except requests.exceptions.ConnectionError as e:
        if _cancelled(should_stop, cancel):
            return
        raise OllamaError(f"Could not connect to Ollama at {normalize_base_url(base_url)}. Is Ollama running?") from e
    except requests.exceptions.Timeout as e:
        if _cancelled(should_stop, cancel):
            return
        raise OllamaError("The request to Ollama timed out.") from e
    except requests.exceptions.RequestException as e:
        if _cancelled(should_stop, cancel):
            return
        raise OllamaError(f"An error occurred talking to Ollama: {e}") from e
    finally:
        if session is not None:
            session.close()

def _cancelled(should_stop, cancel: CancellableRequest | None) -> bool:
    return bool(should_stop() or (cancel is not None and cancel.aborted()))

def _error_from_response(response: requests.Response) -> str:
    """Extracts Ollama's error message (such as 'model not found') from a failed response."""
    try:
        message = response.json().get("error")
    except ValueError:
        message = None
    return f"Ollama error ({response.status_code}): {message or response.text[:200] or response.reason}"
