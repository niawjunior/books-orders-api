from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Numeric, Integer, Date, CheckConstraint, Text, Constraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from decimal import Decimal
from app.models.base import Base

#Book
class Book(Base):
    __tablename__: str = "books"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published_at: Mapped[Date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        comment="for optimistic locking",
    )
    __table_args__: tuple[Constraint, ...] = (
            CheckConstraint("price >= 0", name="books_price_nonneg"),
            CheckConstraint("stock >= 0", name="books_stock_nonneg"),
    )
