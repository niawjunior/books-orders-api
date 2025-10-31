from pydantic import BaseModel, field_validator, ConfigDict
from typing import ClassVar
import uuid
from datetime import date
from decimal import Decimal

# Book base schema
class BookBase(BaseModel):
    title: str
    author_id: uuid.UUID
    price: Decimal
    stock: int = 0
    published_at: date | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("price")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("price must be >= 0")
        return v

    @field_validator("stock")
    @classmethod
    def non_negative_stock(cls, v: int) -> int:
        if v < 0:
            raise ValueError("stock must be >= 0")
        return v

# Book create schema
class BookCreate(BookBase):
    pass

# Book read schema
class BookRead(BookBase):
    id: uuid.UUID
    version: int

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
