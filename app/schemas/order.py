from pydantic import BaseModel, ConfigDict, field_validator
import uuid
from datetime import datetime
from typing import ClassVar


# Order item base
class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    qty: int

    @field_validator("qty")
    @classmethod
    def positive_qty(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("qty must be > 0")
        return v

# Order create
class OrderCreate(BaseModel):
    items: list[OrderItemCreate]

# Order item read
class OrderItemRead(BaseModel):
    product_id: uuid.UUID
    qty: int

# Order read
class OrderRead(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    items: list[OrderItemRead] = []

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
