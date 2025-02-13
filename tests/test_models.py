"""
Example test.
"""
import pytest

from pack218.entities.models import InvalidPasswordException, InvalidNewPasswordException, User


@pytest.fixture
def user() -> User:
    return User(id="jsjeannotte",
                first_name="John",
                last_name="Doe",
                email="test@google.com",
                hashed_password=User.hash_password("test"))

def test_user(user: User):
    print(user)

    assert user.validate_password("test")
    assert user.id == "jsjeannotte"
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.email == "test@google.com"
    assert user.validate_password("test")


def test_user_validate(user: User):
    assert user.validate_password("test")


def test_user_update_password(user: User):
    user.update_password("test", "test2", "test2")
    assert user.validate_password("test2")

def test_user_update_password_wrong_current(user: User):
    # Validate that we raise the correct exception when the current password is wrong
    with pytest.raises(InvalidPasswordException):
        user.update_password("test2", "test3", "test3")

def test_user_update_password_new_no_match(user: User):
    # Validate that we raise the correct exception when the current password is wrong
    with pytest.raises(InvalidNewPasswordException):
        user.update_password("test2", "test3", "test4")
