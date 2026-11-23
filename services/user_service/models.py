"""
User Service ORM Models: roles, users.
Database: user_db
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.common.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Intra-database relationship
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, code='{self.code}')>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Intra-database relationship
    role: Mapped["Role"] = relationship("Role", back_populates="users")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role_id={self.role_id})>"


__all_models__ = [Role, User]
