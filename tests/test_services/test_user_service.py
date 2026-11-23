"""
Unit tests for UserService and UserRepository in user_service.
Isolation: strictly user_db.
"""
from uuid import UUID
import pytest
from services.user_service.repository import UserRepository
from services.user_service.service import UserService
from services.user_service.schemas import UserDTO, RoleDTO
from tests.test_services.conftest import KNOWN_CLIENT_ID, NON_EXISTENT_UUID


def test_get_user_by_id_found(user_session):
    repo = UserRepository(user_session)
    service = UserService(repo)
    user = service.get_user_by_id(KNOWN_CLIENT_ID)

    assert user is not None
    assert isinstance(user, UserDTO)
    assert user.id == KNOWN_CLIENT_ID
    assert user.first_name == "Иван"
    assert user.last_name == "Иванов"
    assert user.email == "client@logistics.by"
    assert user.account_status == "ACTIVE"
    assert user.role == "ROLE_CLIENT"
    assert user.role.code == "ROLE_CLIENT"


def test_get_user_by_id_not_found(user_session):
    service = UserService(UserRepository(user_session))
    assert service.get_user_by_id(NON_EXISTENT_UUID) is None


def test_get_user_by_email_found(user_session):
    service = UserService(UserRepository(user_session))
    user = service.get_user_by_email("client@logistics.by")
    assert user is not None
    assert user.id == KNOWN_CLIENT_ID


def test_get_user_by_email_not_found(user_session):
    service = UserService(UserRepository(user_session))
    assert service.get_user_by_email("nonexistent@example.com") is None


def test_list_users(user_session):
    service = UserService(UserRepository(user_session))
    users = service.list_users()
    assert isinstance(users, list)
    assert len(users) >= 5


def test_get_current_user(user_session):
    service = UserService(user_session)
    user = service.get_current_user()
    assert user is not None
    assert user.email == "client@logistics.by"


def test_dual_lifecycle_auto_session():
    service = UserService()
    user = service.get_by_id(KNOWN_CLIENT_ID)
    assert user is not None
    assert user.id == KNOWN_CLIENT_ID


def test_user_db_isolation(user_session):
    """Assert session is bound exclusively to user_db."""
    url = str(user_session.bind.url)
    assert "user_db" in url
