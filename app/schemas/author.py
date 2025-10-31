from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import ClassVar

import uuid

# Author base schema
class AuthorBase(BaseModel):
    name: str
    email: EmailStr | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

# Author create schema
class AuthorCreate(AuthorBase):
    pass

# Author read schema
class AuthorRead(AuthorBase):
    id: uuid.UUID

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
