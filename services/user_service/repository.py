"""
User Service Repository for user_db.
Strict database isolation: queries only roles and users tables.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from services.common.database import get_session_for_db
from services.user_service.models import User, Role


class UserRepository:
    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("user_db")

    def get_by_id(self, user_id: UUID | str) -> Optional[User]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(User)
                .options(joinedload(User.role))
                .where(User.id == user_id)
            )
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def get_by_email(self, email: str) -> Optional[User]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(User)
                .options(joinedload(User.role))
                .where(func.lower(User.email) == email.lower().strip())
            )
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def get_by_phone(self, phone: str) -> Optional[User]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(User)
                .options(joinedload(User.role))
                .where(User.phone == phone.strip())
            )
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = (
                select(User)
                .options(joinedload(User.role))
                .order_by(User.created_at.asc())
                .offset(skip)
                .limit(limit)
            )
            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def get_role_by_code(self, code: str) -> Optional[Role]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Role).where(Role.code == code.strip())
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Role).where(Role.id == role_id)
            return sess.execute(stmt).scalar_one_or_none()
        finally:
            if should_close:
                sess.close()

    def list_roles(self) -> List[Role]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            stmt = select(Role).order_by(Role.id.asc())
            return list(sess.execute(stmt).scalars().all())
        finally:
            if should_close:
                sess.close()

    def create(self, user: User) -> User:
        sess = self._get_session()
        should_close = self._session is None
        try:
            sess.add(user)
            sess.commit()
            sess.refresh(user)
            return user
        except Exception:
            sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
