from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Text,
    ForeignKey,
    Integer,
    CheckConstraint,
    DateTime,
    func,
    JSON,
    Constraint,
)
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

#Order
class Order(Base):
    __tablename__: str = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__: tuple[Constraint, ...] = (
        CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','CANCELLED')",
            name="orders_status_check",
        ),
    )
#Order Items
class OrderItem(Base):
    __tablename__: str = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("books.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__: tuple[Constraint, ...] = (
        CheckConstraint("qty > 0", name="order_items_qty_positive"),
    )

#Idempotency Keys
class IdempotencyKey(Base):
    __tablename__: str = "idempotency_keys"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    response: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
    )
