import pathlib

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    import config.settings as settings
    import modules.db as db

    test_path = tmp_path / "test_veridexa.db"
    monkeypatch.setattr(settings, "DB_PATH", test_path)
    monkeypatch.setattr(db, "DB_PATH", test_path)
    db.init_db()
    return test_path


def test_signup_and_login(temp_db):
    from modules.auth import signup, login

    user = signup("carol", "carol@example.com", "Passw0rd", "Passw0rd", "Carol C")
    assert user.username == "carol"

    logged_in = login("carol", "Passw0rd")
    assert logged_in.id == user.id

    logged_in_by_email = login("carol@example.com", "Passw0rd")
    assert logged_in_by_email.id == user.id


def test_signup_rejects_duplicate_username(temp_db):
    from modules.auth import signup, AuthError

    signup("dave", "dave@example.com", "Passw0rd", "Passw0rd")
    with pytest.raises(AuthError):
        signup("dave", "someone@example.com", "Passw0rd", "Passw0rd")


def test_login_rejects_wrong_password(temp_db):
    from modules.auth import signup, login, AuthError

    signup("erin", "erin@example.com", "Passw0rd", "Passw0rd")
    with pytest.raises(AuthError):
        login("erin", "WrongPassword1")


def test_signup_rejects_weak_password(temp_db):
    from modules.auth import signup, AuthError

    with pytest.raises(AuthError):
        signup("frank", "frank@example.com", "weak", "weak")
