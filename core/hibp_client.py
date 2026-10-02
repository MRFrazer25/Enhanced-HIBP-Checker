"""
File for interacting with the Have I Been Pwned (HIBP) APIs.

Provides:
- Breached account lookups (requires an HIBP API key).
- Pwned Passwords lookups using the k-anonymity range API (free, no key). Only the
  first 5 characters of the password's SHA-1 hash ever leave the machine.
- Helpers for turning breach records into readable text.
"""
import datetime
import hashlib
import html
import re
from urllib.parse import quote

import requests

HIBP_API_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{account}"
PWNED_PASSWORDS_URL = "https://api.pwnedpasswords.com/range/{prefix}"
USER_AGENT = "Enhanced-HIBP-Checker (Python)"
REQUEST_TIMEOUT = 30

# HIBP breach flags: (field, value that triggers it, short label for the UI, explanation for the AI advisor)
BREACH_FLAGS = [
    ("IsStealerLog", True, "stealer log",
     "This data came from info-stealing malware logs: a device used to log in was infected with malware "
     "that captured saved credentials. The first step must be scanning and cleaning that device; only then "
     "change passwords, otherwise the new passwords can be stolen too."),
    ("IsMalware", True, "malware",
     "This breach involved malware."),
    ("IsSpamList", True, "spam list",
     "This is a spam list: the email address is known to spammers, so expect more spam and phishing."),
    ("IsVerified", False, "unverified",
     "This breach is unverified: HIBP could not confirm it is genuine."),
    ("IsFabricated", True, "likely fabricated",
     "HIBP believes this breach data is likely fabricated."),
    ("IsSensitive", True, "sensitive",
     "HIBP marks this breach as sensitive (being in it may reveal something personal about the user)."),
]

class HibpError(Exception):
    """Custom exception for HIBP API errors."""
    pass

def check_hibp(account: str, api_key: str) -> list:
    """Checks the HIBP API for breaches associated with the given account.

    Args:
        account: The email address or username to check.
        api_key: The HIBP API key.

    Returns:
        A list of breach dictionaries (newest first) if found, an empty list if no breaches.

    Raises:
        HibpError: If there's an API or network error (such as rate limiting or an invalid key).
    """
    account = (account or "").strip()
    if not api_key:
        raise HibpError("HIBP API Key is missing. Please set it in Settings.")
    if not account:
        raise HibpError("Account cannot be empty.")

    headers = {
        "hibp-api-key": api_key,
        "User-Agent": USER_AGENT,
    }
    # The account must be URL encoded so characters like '/', '?' or '#' can't alter the request path.
    url = HIBP_API_URL.format(account=quote(account, safe=""))
    response = _get(url, headers=headers, params={"truncateResponse": "false"})

    if response.status_code == 200:
        try:
            breaches = response.json()
        except ValueError:
            raise HibpError("Failed to decode HIBP API response.")
        return sorted(breaches, key=lambda b: b.get("BreachDate") or "", reverse=True)
    if response.status_code == 404:
        return []
    if response.status_code == 400:
        raise HibpError("Bad Request: the account format is not valid.")
    if response.status_code == 401:
        raise HibpError("Unauthorized: the HIBP API key is invalid.")
    if response.status_code == 403:
        raise HibpError("Forbidden: HIBP rejected the request (check the User-Agent).")
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "a few")
        raise HibpError(f"Rate limited. Please wait {retry_after} seconds before trying again.")
    if response.status_code == 503:
        raise HibpError("Service Unavailable. HIBP might be down or undergoing maintenance.")
    raise HibpError(f"HIBP API Error: unexpected response (HTTP {response.status_code}).")

def check_pwned_password(password: str) -> int:
    """Returns how many times a password appears in the Pwned Passwords corpus (0 if never).

    Uses the k-anonymity model: only the first 5 hex characters of the SHA-1 hash are sent.
    Padding is requested so the response size doesn't reveal anything about the prefix.

    Raises:
        HibpError: If the password is empty or there's an API or network error.
    """
    if not password:
        raise HibpError("Password cannot be empty.")

    # SHA-1 is what the Pwned Passwords API uses for lookups; it isn't used to protect anything here.
    sha1 = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    response = _get(
        PWNED_PASSWORDS_URL.format(prefix=prefix),
        headers={"User-Agent": USER_AGENT, "Add-Padding": "true"},
    )
    if response.status_code != 200:
        raise HibpError(f"Pwned Passwords API Error: {response.status_code}")

    for line in response.text.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip() == suffix:
            # Padding entries have a count of 0, so they never produce a false positive.
            return int(count.strip() or 0)
    return 0

def html_to_text(text: str) -> str:
    """Strips tags from HIBP's HTML breach descriptions and decodes entities."""
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()

def breach_flags(breach: dict) -> list:
    """Returns (label, explanation) pairs for the HIBP flags that apply to a breach."""
    return [(label, note) for field, value, label, note in BREACH_FLAGS if breach.get(field) is value]

def format_breaches_for_ai(account: str, breaches: list, today: datetime.date = None) -> str:
    """Builds a plain text summary of breaches to give the AI advisor as context."""
    today = today or datetime.date.today()
    parts = [
        f"HIBP check results for account: {account}",
        f"Checked on: {today.isoformat()} (use this to judge how old each breach is)",
        f"Number of breaches: {len(breaches)}",
    ]
    for breach in breaches:
        parts.append("")
        parts.append(f"Breach: {breach.get('Title', 'Unknown')}")
        parts.append(f"Domain: {breach.get('Domain') or 'N/A'}")
        parts.append(f"Breach date: {breach.get('BreachDate', 'N/A')}")
        parts.append(f"Accounts affected: {breach.get('PwnCount') or 0:,}")
        parts.append(f"Compromised data: {', '.join(breach.get('DataClasses', [])) or 'N/A'}")
        for _, note in breach_flags(breach):
            parts.append(f"Note: {note}")
        parts.append(f"Description: {html_to_text(breach.get('Description', ''))}")
    return "\n".join(parts)

def _get(url: str, headers: dict, params: dict = None) -> requests.Response:
    """Performs a GET request, converting network failures into HibpError."""
    try:
        return requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise HibpError("The request to HIBP timed out.")
    except requests.exceptions.ConnectionError:
        raise HibpError("Could not connect to HIBP. Check your internet connection.")
    except requests.exceptions.RequestException as e:
        raise HibpError(f"An unexpected network error occurred: {e}")
