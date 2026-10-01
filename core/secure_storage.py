"""
Manages secure storage of the HIBP API key using the system keyring.

This file provides functions to set, retrieve, and delete the API key, abstracting
the interaction with the `keyring` library.
"""
import sys

import keyring
from keyring.errors import PasswordDeleteError

# Kept unchanged so keys saved by earlier versions are still found.
SERVICE_NAME = "HIBP APP AI"
API_KEY_USERNAME = "hibp_api_key"

def set_api_key(api_key):
    """Securely store the HIBP API key. Raises if the keyring is unavailable."""
    try:
        keyring.set_password(SERVICE_NAME, API_KEY_USERNAME, api_key)
    except Exception as e:
        # Handle potential keyring errors (such as no backend available).
        # The exception is re-raised for the UI to handle.
        print(f"Error storing API key in keyring: {e}", file=sys.stderr)
        raise

def get_api_key():
    """Retrieve the stored HIBP API key, or None if unavailable."""
    try:
        return keyring.get_password(SERVICE_NAME, API_KEY_USERNAME)
    except Exception as e:
        print(f"Error retrieving API key from keyring: {e}", file=sys.stderr)
        return None

def delete_api_key():
    """Remove the stored HIBP API key. Does nothing if no key is stored."""
    try:
        keyring.delete_password(SERVICE_NAME, API_KEY_USERNAME)
    except PasswordDeleteError:
        pass
