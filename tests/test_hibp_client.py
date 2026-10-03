import hashlib

import pytest
import requests

from core import hibp_client
from core.hibp_client import HibpError, check_hibp, check_pwned_password, format_breaches_for_ai, html_to_text, normalize_breach

class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

@pytest.fixture
def fake_get(monkeypatch):
    calls = []

    def install(response=None, exception=None):
        def fake(url, headers=None, params=None, timeout=None):
            calls.append({"url": url, "headers": headers, "params": params})
            if exception:
                raise exception
            return response
        monkeypatch.setattr(hibp_client.requests, "get", fake)
        return calls
    return install

def test_check_hibp_url_encodes_account(fake_get):
    calls = fake_get(FakeResponse(404))
    assert check_hibp("a/b?c#d@example.com", "key") == []
    assert calls[0]["url"].endswith("/breachedaccount/a%2Fb%3Fc%23d%40example.com")
    assert calls[0]["headers"]["hibp-api-key"] == "key"

def test_check_hibp_sorts_newest_first(fake_get):
    fake_get(FakeResponse(200, [{"Title": "Old", "BreachDate": "2012-01-01"}, {"Title": "New", "BreachDate": "2020-05-01"}]))
    assert [b["Title"] for b in check_hibp("x@example.com", "key")] == ["New", "Old"]

@pytest.mark.parametrize("status, fragment", [(401, "invalid"), (429, "Rate limited"), (503, "Unavailable"), (500, "500")])
def test_check_hibp_error_statuses(fake_get, status, fragment):
    fake_get(FakeResponse(status, headers={"Retry-After": "2"}))
    with pytest.raises(HibpError, match=fragment):
        check_hibp("x@example.com", "key")

def test_check_hibp_requires_key_and_account():
    with pytest.raises(HibpError):
        check_hibp("x@example.com", "")
    with pytest.raises(HibpError):
        check_hibp("   ", "key")

def test_network_errors_become_hibp_errors(fake_get):
    fake_get(exception=requests.exceptions.ConnectionError("boom"))
    with pytest.raises(HibpError, match="connect") as excinfo:
        check_hibp("x@example.com", "key")
    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
    assert "internet connection" in str(excinfo.value)

def test_ssl_error_is_not_generic_connection_message(fake_get):
    fake_get(exception=requests.exceptions.SSLError("bad cert"))
    with pytest.raises(HibpError, match="certificate") as excinfo:
        check_hibp("x@example.com", "key")
    assert isinstance(excinfo.value.__cause__, requests.exceptions.SSLError)
    assert "internet connection" not in str(excinfo.value)

def test_timeout_and_generic_errors_chain_cause(fake_get):
    fake_get(exception=requests.exceptions.Timeout("slow"))
    with pytest.raises(HibpError, match="timed out") as excinfo:
        check_hibp("x@example.com", "key")
    assert isinstance(excinfo.value.__cause__, requests.exceptions.Timeout)

    fake_get(exception=requests.exceptions.RequestException("other"))
    with pytest.raises(HibpError) as excinfo:
        check_hibp("x@example.com", "key")
    assert isinstance(excinfo.value.__cause__, requests.exceptions.RequestException)

def test_bad_json_chains_value_error(fake_get):
    fake_get(FakeResponse(200))
    with pytest.raises(HibpError, match="decode") as excinfo:
        check_hibp("x@example.com", "key")
    assert isinstance(excinfo.value.__cause__, ValueError)

def test_check_hibp_rejects_non_list_payload(fake_get):
    fake_get(FakeResponse(200, {"Title": "nope"}))
    with pytest.raises(HibpError, match="decode"):
        check_hibp("x@example.com", "key")

def test_check_hibp_normalizes_malformed_records(fake_get):
    fake_get(FakeResponse(200, [{
        "Title": None, "PwnCount": "5", "DataClasses": None, "BreachDate": "2020-01-01",
    }]))
    [breach] = check_hibp("x@example.com", "key")
    assert breach["Title"] == "Unknown"
    assert breach["PwnCount"] == 5
    assert breach["DataClasses"] == []

def test_pwned_password_only_sends_hash_prefix(fake_get):
    sha1 = hashlib.sha1(b"password123", usedforsecurity=False).hexdigest().upper()
    calls = fake_get(FakeResponse(200, text=f"0000000000000000000000000000000000A:0\r\n{sha1[5:]}:42\r\n"))
    assert check_pwned_password("password123") == 42
    assert calls[0]["url"].endswith("/range/" + sha1[:5])
    assert "password123" not in calls[0]["url"]
    assert calls[0]["headers"]["Add-Padding"] == "true"

def test_pwned_password_not_found(fake_get):
    fake_get(FakeResponse(200, text="0000000000000000000000000000000000A:3\r\n"))
    assert check_pwned_password("something-unique") == 0

def test_html_to_text():
    assert html_to_text('In 2013, <a href="x">Adobe</a> &amp; co.') == "In 2013, Adobe & co."

def test_format_breaches_for_ai():
    text = format_breaches_for_ai("x@example.com", [{
        "Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04", "PwnCount": 152445165,
        "DataClasses": ["Email addresses", "Passwords"], "Description": "<p>Big breach</p>", "IsVerified": True,
    }])
    assert "Breach: Adobe" in text
    assert "152,445,165" in text
    assert "Email addresses, Passwords" in text
    assert "<p>" not in text

def test_unexpected_status_does_not_echo_server_body(fake_get):
    fake_get(FakeResponse(500, text="<b>server internals</b>"))
    with pytest.raises(HibpError) as excinfo:
        check_hibp("x@example.com", "key")
    assert "server internals" not in str(excinfo.value)

def test_format_breaches_handles_missing_fields():
    text = format_breaches_for_ai("x@example.com", [{"Title": "Mystery", "PwnCount": None}])
    assert "Accounts affected: 0" in text

def test_format_breaches_handles_null_and_wrong_types():
    text = format_breaches_for_ai("x@example.com", [{
        "Title": None,
        "Domain": None,
        "BreachDate": None,
        "PwnCount": "12",
        "DataClasses": None,
        "Description": None,
    }])
    assert "Breach: Unknown" in text
    assert "Accounts affected: 12" in text
    assert "Compromised data: N/A" in text

def test_normalize_breach_coerces_fields():
    breach = normalize_breach({
        "Title": None,
        "PwnCount": "not-a-number",
        "DataClasses": ["Email", None, 3],
    })
    assert breach["Title"] == "Unknown"
    assert breach["PwnCount"] == 0
    assert breach["DataClasses"] == ["Email", "3"]
    assert normalize_breach("not-a-dict")["Title"] == "Unknown"

def test_format_breaches_explains_flags_and_date():
    import datetime
    text = format_breaches_for_ai("x@example.com", [
        {"Title": "Logs", "IsStealerLog": True, "IsVerified": True},
        {"Title": "Spam", "IsSpamList": True, "IsVerified": False},
    ], today=datetime.date(2026, 10, 2))
    assert "Checked on: 2026-10-02" in text
    assert "malware" in text and "cleaning that device; only then" in text
    assert "spam list" in text and "unverified" in text

def test_breach_flags_labels():
    assert [label for label, _ in hibp_client.breach_flags({"IsStealerLog": True, "IsVerified": True})] == ["stealer log"]
    assert hibp_client.breach_flags({"IsVerified": True}) == []
