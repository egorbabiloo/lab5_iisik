# -*- coding: utf-8 -*-
"""
AuthRepository: Isolated data-access layer for Auth Service against user_db.
Uses parameterized SQL queries without importing ORM models from user_service.
"""

import uuid
from typing import Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.auth_service.schemas import AuthUserDTO
from services.common.database import get_session_for_db


class AuthRepository:
    def __init__(self, session: Optional[Session] = None) -> None:
        self._session = session

    def _get_session(self) -> Session:
        return self._session if self._session is not None else get_session_for_db("user_db")

    @staticmethod
    def _row_to_dto(row: dict) -> AuthUserDTO:
        return AuthUserDTO(
            id=row["id"],
            email=row["email"],
            phone=row["phone"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=row["role_code"],
            account_status=row["account_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_user_with_hash_by_email(
        self, email: str
    ) -> Tuple[Optional[str], Optional[AuthUserDTO]]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            row = (
                sess.execute(
                    text(
                        """
                        SELECT u.id, u.email, u.phone, u.password_hash, u.first_name, u.last_name,
                               u.account_status, u.created_at, u.updated_at, r.code AS role_code
                        FROM users u
                        JOIN roles r ON r.id = u.role_id
                        WHERE LOWER(u.email) = LOWER(:email)
                        LIMIT 1;
                        """
                    ),
                    {"email": email.strip()},
                )
                .mappings()
                .one_or_none()
            )
            if not row:
                return None, None
            return row["password_hash"], self._row_to_dto(dict(row))
        finally:
            if should_close:
                sess.close()

    def get_user_by_id(self, user_id: str) -> Optional[AuthUserDTO]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            row = (
                sess.execute(
                    text(
                        """
                        SELECT u.id, u.email, u.phone, u.first_name, u.last_name,
                               u.account_status, u.created_at, u.updated_at, r.code AS role_code
                        FROM users u
                        JOIN roles r ON r.id = u.role_id
                        WHERE u.id = :uid
                        LIMIT 1;
                        """
                    ),
                    {"uid": str(user_id)},
                )
                .mappings()
                .one_or_none()
            )
            return self._row_to_dto(dict(row)) if row else None
        finally:
            if should_close:
                sess.close()

    def exists_by_phone(self, phone: str) -> bool:
        sess = self._get_session()
        should_close = self._session is None
        try:
            row = sess.execute(
                text("SELECT 1 FROM users WHERE phone = :phone LIMIT 1;"),
                {"phone": phone.strip()},
            ).first()
            return row is not None
        finally:
            if should_close:
                sess.close()

    def get_role_id_by_code(self, code: str) -> Optional[int]:
        sess = self._get_session()
        should_close = self._session is None
        try:
            val = sess.execute(
                text("SELECT id FROM roles WHERE code = :code LIMIT 1;"),
                {"code": code.strip()},
            ).scalar()
            return int(val) if val is not None else None
        finally:
            if should_close:
                sess.close()

    def create_user(
        self,
        email: str,
        phone: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        role_id: int,
    ) -> AuthUserDTO:
        sess = self._get_session()
        should_close = self._session is None
        new_id = str(uuid.uuid4())
        try:
            sess.execute(
                text(
                    """
                    INSERT INTO users (id, email, phone, password_hash, first_name, last_name, role_id, account_status)
                    VALUES (:id, :email, :phone, :password_hash, :first_name, :last_name, :role_id, 'ACTIVE');
                    """
                ),
                {
                    "id": new_id,
                    "email": email,
                    "phone": phone,
                    "password_hash": password_hash,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role_id": role_id,
                },
            )
            if should_close:
                sess.commit()
            loaded = self.get_user_by_id(new_id)
            assert loaded is not None
            return loaded
        except Exception:
            if should_close:
                sess.rollback()
            raise
        finally:
            if should_close:
                sess.close()
