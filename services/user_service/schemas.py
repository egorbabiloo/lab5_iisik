"""
Pydantic v2 DTO Schemas for User Service.
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import core_schema


class RoleTypeStr(str):
    """String subclass that allows role.code attribute access while behaving as a standard string."""

    @property
    def code(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
        )


class RoleDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, arbitrary_types_allowed=True)

    id: UUID
    email: str
    phone: str
    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    role: RoleTypeStr
    account_status: str = Field(..., alias="accountStatus")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    @field_validator("role", mode="before")
    @classmethod
    def extract_role_code(cls, v: Any) -> Any:
        if hasattr(v, "code"):
            return getattr(v, "code")
        return v


class UserCreateDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str
    phone: str
    password: str
    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    role: str = "ROLE_CLIENT"
