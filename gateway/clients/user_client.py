# -*- coding: utf-8 -*-
"""
UserClient: in-process client invoking UserService.
"""

from typing import Optional, List
from uuid import UUID

from services.user_service.service import UserService
from services.user_service.schemas import UserDTO
from gateway.clients.base import UserClientProtocol


class UserClient(UserClientProtocol):
    def __init__(self, service: Optional[UserService] = None) -> None:
        self._service = service or UserService()

    def get_user_by_id(self, user_id: UUID | str) -> Optional[UserDTO]:
        return self._service.get_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[UserDTO]:
        return self._service.get_by_email(email)

    def get_current_user(self) -> Optional[UserDTO]:
        return self._service.get_current_user()

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserDTO]:
        return self._service.list_users(skip=skip, limit=limit)
