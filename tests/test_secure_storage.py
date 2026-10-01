import pytest
from keyring.errors import PasswordDeleteError

from core import secure_storage

class FakeKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, user, value):
        self.store[(service, user)] = value

    def get_password(self, service, user):
        return self.store.get((service, user))

    def delete_password(self, service, user):
        if (service, user) not in self.store:
            raise PasswordDeleteError("not found")
        del self.store[(service, user)]

@pytest.fixture
def fake_keyring(monkeypatch):
    fake = FakeKeyring()
    for name in ("set_password", "get_password", "delete_password"):
        monkeypatch.setattr(secure_storage.keyring, name, getattr(fake, name))
    return fake

def test_save_get_delete_round_trip(fake_keyring):
    secure_storage.set_api_key("abc123")
    assert secure_storage.get_api_key() == "abc123"
    secure_storage.delete_api_key()
    assert secure_storage.get_api_key() is None

def test_delete_when_nothing_stored_is_harmless(fake_keyring):
    secure_storage.delete_api_key()

def test_get_returns_none_when_keyring_fails(monkeypatch):
    def broken(*args):
        raise RuntimeError("no backend")
    monkeypatch.setattr(secure_storage.keyring, "get_password", broken)
    assert secure_storage.get_api_key() is None
