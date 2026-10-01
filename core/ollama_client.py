"""
Minimal client for a local Ollama server.

Uses the /api/chat endpoint so the AI advisor keeps conversation history,
and /api/tags to list the models that have been pulled locally.
"""
import json
from urllib.parse import urlsplit, urlunsplit

import requests

DEFAULT_OLLAMA_URL = "http://localhost:11434"
# (connect, read) timeouts. Large models can take a while to load before the first token.
CHAT_TIMEOUT = (10, 300)
TAGS_TIMEOUT = 5

class OllamaError(Exception):
    """Raised when Ollama can't be reached or returns an error."""
    pass

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
    except requests.exceptions.ConnectionError:
        raise OllamaError(f"Could not connect to Ollama at {normalize_base_url(base_url)}. Is Ollama running?")
    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        raise OllamaError(f"Error fetching models: {e}")

def stream_chat(base_url: str, model: str, messages: list, should_stop=lambda: False):
    """Streams a chat completion from Ollama, yielding text chunks as they arrive.

    Args:
        base_url: The Ollama server URL.
        model: The model name.
        messages: The conversation as a list of {"role": ..., "content": ...} dicts.
        should_stop: Called between chunks; returning True ends the stream early.

    Raises:
        OllamaError: If Ollama can't be reached or reports an error.
    """
    url = f"{normalize_base_url(base_url)}/api/chat"
    payload = {"model": model, "messages": messages, "stream": True}
    try:
        with requests.post(url, json=payload, timeout=CHAT_TIMEOUT, stream=True) as response:
            if response.status_code != 200:
                raise OllamaError(_error_from_response(response))
            for line in response.iter_lines():
                if should_stop():
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
    except requests.exceptions.ConnectionError:
        raise OllamaError(f"Could not connect to Ollama at {normalize_base_url(base_url)}. Is Ollama running?")
    except requests.exceptions.Timeout:
        raise OllamaError("The request to Ollama timed out.")
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"An error occurred talking to Ollama: {e}")

def _error_from_response(response: requests.Response) -> str:
    """Extracts Ollama's error message (such as 'model not found') from a failed response."""
    try:
        message = response.json().get("error")
    except ValueError:
        message = None
    return f"Ollama error ({response.status_code}): {message or response.text[:200] or response.reason}"
