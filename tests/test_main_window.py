import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

# QtWebEngine must be imported before any QApplication is created.
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox

import pytest

from core.ollama_client import CancellableRequest


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(["enhanced-hibp-checker-tests"])
    return app


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("ui.main_window.get_api_key", lambda: None)
    monkeypatch.setattr("ui.main_window.list_models", lambda url: [])
    monkeypatch.setattr(
        "ui.main_window.QSettings",
        lambda *a, **k: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    monkeypatch.setattr(QMessageBox, "exec", lambda self: int(QMessageBox.StandardButton.Ok))

    from ui.main_window import MainWindow

    def run_inline(self, func, callback, *args):
        try:
            result = func(*args)
        except Exception as e:
            result = e
        callback(result)

    monkeypatch.setattr(MainWindow, "_run_in_background", run_inline)
    win = MainWindow()
    yield win
    win.close()


def test_task_finished_shows_callback_errors(window, monkeypatch):
    shown = []
    monkeypatch.setattr(window, "_show_error", lambda title, text: shown.append((title, text)))

    def boom(_result):
        raise TypeError("null title")

    window._on_task_finished(boom, {"Title": None})
    assert shown
    assert shown[0][0] == "Error"
    assert "null title" in shown[0][1]


def test_malformed_hibp_result_renders_instead_of_crashing(window):
    window._on_hibp_result("user@example.com", [{
        "Title": None,
        "Domain": None,
        "BreachDate": None,
        "PwnCount": "99",
        "DataClasses": None,
        "Description": None,
        "IsVerified": True,
    }])
    text = window.hibp_results_area.toPlainText()
    assert "Unknown" in text
    assert "99" in text
    assert window.hibp_ai_advice_button.isEnabled()
    assert window.hibp_context_for_ai
    assert "Breach: Unknown" in window.hibp_context_for_ai


def test_stop_and_new_chat_abort_in_flight_request(window):
    cancel = CancellableRequest()
    window.chat_stop_event = threading.Event()
    window.chat_request = cancel
    window.current_ai_message_id = "ai-message-1"
    window.current_ai_text = "partial"
    window.ai_send_button.setEnabled(True)
    window.ai_send_button.setText("Stop")

    window.ai_send_button.click()
    assert cancel.aborted()
    assert window.chat_stop_event is None
    assert window.ai_send_button.text() == "Send"

    window.ai_clear_button.click()
    assert window.chat_history == []


def test_picking_a_model_also_saves_the_server_url(window):
    window.ollama_endpoint_input.setText("http://10.0.0.5:11434/api/generate")
    window.ollama_model_combo.addItems(["aaa:latest", "gemma4:e4b"])
    window.ollama_model_combo.setCurrentIndex(-1)
    window.ollama_model_combo.textActivated.emit("gemma4:e4b")
    assert window.settings.value("ollama/model") == "gemma4:e4b"
    assert window.settings.value("ollama/endpoint") == "http://10.0.0.5:11434"


def test_chat_calls_are_dropped_after_the_page_fails_to_load(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    window.chat_view_ready = False
    window._on_chat_view_load_finished(False)
    window._call_chat_js("clearChat")
    window._call_chat_js("addUserMessage", "hi")
    assert window.pending_js_calls == []


def test_breach_context_strips_html_before_shortening(window):
    long_html = '<p>' + 'x' * 420 + ' <a href="http://www.example.com/very/long/path">read more</a></p>'
    context = window._build_ai_breach_context("user@example.com", [{"Title": "Adobe", "Description": long_html}])
    assert "<a" not in context and "href" not in context
    assert "..." in context


def test_saved_api_key_is_loaded_into_settings(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("ui.main_window.get_api_key", lambda: "stored-key")
    monkeypatch.setattr("ui.main_window.list_models", lambda url: [])
    monkeypatch.setattr(
        "ui.main_window.QSettings",
        lambda *a, **k: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    from ui.main_window import MainWindow

    def run_inline(self, func, callback, *args):
        callback(func(*args))

    monkeypatch.setattr(MainWindow, "_run_in_background", run_inline)
    win = MainWindow()
    try:
        assert win.api_key_input.text() == "stored-key"
    finally:
        win.close()


def test_desktop_app_exercise(window, capsys):
    """Headless walk through the window the way a user would hit the fixed paths."""
    print("constructed MainWindow offscreen")
    print("send button:", window.ai_send_button.text(), "enabled=", window.ai_send_button.isEnabled())
    print("new chat button:", window.ai_clear_button.text(), "enabled=", window.ai_clear_button.isEnabled())
    print("tabs:", [window.tabs.tabText(i) for i in range(window.tabs.count())])
    print("chat view ready:", window.chat_view_ready)

    window._on_task_finished(lambda result: window._on_hibp_result("bad-fields@example.com", result), [{
        "Title": None,
        "PwnCount": "7",
        "DataClasses": None,
    }])
    rendered = window.hibp_results_area.toPlainText()
    print("hibp rendered:", rendered.replace("\n", " | "))
    assert "Unknown" in rendered
    assert "7" in rendered

    cancel = CancellableRequest()
    window.chat_stop_event = threading.Event()
    window.chat_request = cancel
    window.current_ai_message_id = "ai-message-exercise"
    window.current_ai_text = ""
    window.ai_send_button.setEnabled(True)
    window.ai_send_button.setText("Stop")
    window.ai_send_button.click()
    print("after Stop: aborted=", cancel.aborted(), "button=", window.ai_send_button.text())
    assert cancel.aborted()

    window.ai_clear_button.click()
    print("after New Chat: history=", window.chat_history)
    window.close()
    print("window closed")
