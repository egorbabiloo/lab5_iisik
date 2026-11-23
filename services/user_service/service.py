"""
User Service Domain Business Logic.
Returns decoupled Pydantic v2 DTOs.
"""
from typing import Optional, List, Union
from uuid import UUID
from sqlalchemy.orm import Session
from services.common.database import session_scope
from services.common.exceptions import EntityNotFoundError, ValidationError
from services.user_service.models import User
from services.user_service.repository import UserRepository
from services.user_service.schemas import UserDTO, RoleDTO, UserCreateDTO


class UserService:
    def __init__(
        self,
        repository_or_session: Optional[Union[UserRepository, Session]] = None,
        session: Optional[Session] = None,
        repository: Optional[UserRepository] = None,
    ):
        if isinstance(repository_or_session, UserRepository):
            self.repository = repository_or_session
            self._session = repository_or_session._session
        elif isinstance(repository_or_session, Session):
            self._session = repository_or_session
            self.repository = UserRepository(session=self._session)
        elif repository is not None:
            self.repository = repository
            self._session = repository._session
        elif session is not None:
            self._session = session
            self.repository = UserRepository(session=self._session)
        else:
            self._session = None
            self.repository = None

    def _get_repo(self, session: Optional[Session] = None) -> UserRepository:
        if session is not None:
            return UserRepository(session)
        if self.repository is not None:
            return self.repository
        if self._session is not None:
            return UserRepository(self._session)
        return UserRepository()

    def get_by_id(self, user_id: UUID | str) -> Optional[UserDTO]:
        if self.repository is not None or self._session is not None:
            user = self._get_repo().get_by_id(user_id)
            return UserDTO.model_validate(user) if user else None
        with session_scope("user_db") as session:
            user = self._get_repo(session).get_by_id(user_id)
            return UserDTO.model_validate(user) if user else None

    def get_user_by_id(self, user_id: UUID | str) -> Optional[UserDTO]:
        return self.get_by_id(user_id)

    def get_by_email(self, email: str) -> Optional[UserDTO]:
        if self.repository is not None or self._session is not None:
            user = self._get_repo().get_by_email(email)
            return UserDTO.model_validate(user) if user else None
        with session_scope("user_db") as session:
            user = self._get_repo(session).get_by_email(email)
            return UserDTO.model_validate(user) if user else None

    def get_user_by_email(self, email: str) -> Optional[UserDTO]:
        return self.get_by_email(email)

    def list_all(self, skip: int = 0, limit: int = 100) -> List[UserDTO]:
        if self.repository is not None or self._session is not None:
            users = self._get_repo().list_all(skip=skip, limit=limit)
            return [UserDTO.model_validate(u) for u in users]
        with session_scope("user_db") as session:
            users = self._get_repo(session).list_all(skip=skip, limit=limit)
            return [UserDTO.model_validate(u) for u in users]

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserDTO]:
        return self.list_all(skip=skip, limit=limit)

    def get_current_user(self, email: str = "client@logistics.by") -> Optional[UserDTO]:
        """Provides default profile for GraphQL `me` query."""
        return self.get_by_email(email)

    def list_roles(self) -> List[RoleDTO]:
        if self.repository is not None or self._session is not None:
            roles = self._get_repo().list_roles()
            return [RoleDTO.model_validate(r) for r in roles]
        with session_scope("user_db") as session:
            roles = self._get_repo(session).list_roles()
            return [RoleDTO.model_validate(r) for r in roles]

    def get_role_by_code(self, code: str) -> Optional[RoleDTO]:
        if self.repository is not None or self._session is not None:
            role = self._get_repo().get_role_by_code(code)
            return RoleDTO.model_validate(role) if role else None
        with session_scope("user_db") as session:
            role = self._get_repo(session).get_role_by_code(code)
            return RoleDTO.model_validate(role) if role else None

    def create_user(self, data: UserCreateDTO) -> UserDTO:
        def _execute(repo: UserRepository) -> UserDTO:
            role = repo.get_role_by_code(data.role)
            if not role:
                raise ValidationError(f"Invalid role code '{data.role}'")
            import bcrypt
            pw_hash = (
                data.password
                if data.password.startswith("$2b$") or data.password.startswith("$2a$")
                else bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
            )
            user = User(
                email=data.email,
                phone=data.phone,
                password_hash=pw_hash,
                first_name=data.first_name,
                last_name=data.last_name,
                role_id=role.id,
                account_status="ACTIVE",
            )
            saved = repo.create(user)
            # Fetch with role joined
            loaded = repo.get_by_id(saved.id)
            return UserDTO.model_validate(loaded)

        if self.repository is not None or self._session is not None:
            return _execute(self._get_repo())
        with session_scope("user_db") as session:
            return _execute(self._get_repo(session))
