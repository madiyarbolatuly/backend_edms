"""
Password hashing has to work, or nobody can sign up or log in.

`requirements.txt` pinned `passlib~=1.7.4` but left `bcrypt` unpinned. passlib
1.7.4 reads bcrypt's version through `bcrypt.__about__`, which bcrypt removed in
4.1 — so a fresh `pip install -r requirements.txt` picked up bcrypt 5.x and
every hash raised `ValueError: password cannot be longer than 72 bytes`, for a
nine-character password. Signup and login were both dead on a clean install.

These run against whatever bcrypt is actually installed, so the pin cannot drift
back without the suite going red.
"""
import pytest

from app.api.dependencies.auth_utils import get_hashed_password, verify_password


def test_a_password_can_be_hashed():
    assert get_hashed_password(password="Test1234!")


def test_a_hash_is_not_the_password():
    assert get_hashed_password(password="Test1234!") != "Test1234!"


def test_the_correct_password_verifies():
    hashed = get_hashed_password(password="Test1234!")

    assert verify_password(password="Test1234!", hashed_password=hashed) is True


def test_a_wrong_password_does_not_verify():
    hashed = get_hashed_password(password="Test1234!")

    assert verify_password(password="Test1235!", hashed_password=hashed) is False


def test_two_hashes_of_one_password_differ():
    """Salted — otherwise the hashes leak which users share a password."""
    assert get_hashed_password(password="Test1234!") != get_hashed_password(
        password="Test1234!"
    )


@pytest.mark.parametrize(
    "password",
    [
        "aaaaa",                       # the schema's 5-character minimum
        "Пароль1234",                  # non-ASCII
        "with spaces and $ymbol$!",
        "a" * 64,                      # the schema's 64-character maximum
    ],
)
def test_passwords_the_signup_schema_accepts_all_hash(password):
    assert verify_password(
        password=password, hashed_password=get_hashed_password(password=password)
    )


def test_the_installed_bcrypt_is_compatible_with_passlib():
    """
    The specific incompatibility, named. bcrypt >= 4.1 dropped `__about__`,
    which passlib 1.7.4 requires.
    """
    import bcrypt

    major, minor = (int(p) for p in bcrypt.__version__.split(".")[:2])
    assert (major, minor) < (4, 1), (
        f"bcrypt {bcrypt.__version__} is incompatible with passlib 1.7.4; "
        "requirements.txt pins bcrypt<4.1"
    )
