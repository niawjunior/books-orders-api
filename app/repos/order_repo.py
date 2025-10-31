import uuid
from typing import TypeAlias, cast
from sqlalchemy.engine import Row, CursorResult
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.order import IdempotencyKey, Order, OrderItem
from app.schemas.order import OrderCreate

JSONValue: TypeAlias = str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
JSONDict: TypeAlias = dict[str, JSONValue]

class OrderRepository:
    """Repository for Order model."""

    @staticmethod
    #Create draft order
    def create_draft(db: Session, data: OrderCreate) -> Order:
        order = Order(status="DRAFT")
        db.add(order)
        db.flush()  # ensure order.id

        for it in data.items:
            db.add(OrderItem(order_id=order.id, product_id=it.product_id, qty=it.qty))

        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    # Get order by id
    def get(db: Session, order_id: uuid.UUID) -> Order | None:
        return db.get(Order, order_id)

    @staticmethod
    # Get order items by order id
    def list_items(db: Session, order_id: uuid.UUID) -> list[OrderItem]:
        stmt = select(OrderItem).where(OrderItem.order_id == order_id)
        return list(db.scalars(stmt).all())

    @staticmethod
    # Set order status by order id
    def set_status(db: Session, order_id: uuid.UUID, new_status: str) -> None:
        """Pure UPDATE (service decides when to commit)."""
        stmt = update(Order).where(Order.id == order_id).values(status=new_status)
        _ = db.execute(stmt)

    @staticmethod
    # Try decrement book stock by book id
    def try_decrement_book_optimistic(
        db: Session, book_id: uuid.UUID, qty: int
    ) -> tuple[bool, int]:

        row: Row[tuple[int, int]] | None = db.execute(
                    select(Book.version, Book.stock).where(Book.id == book_id)
        ).one_or_none()

        if row is None:
            return (False, 0)

        typed_row: tuple[int, int] = cast(
                tuple[int, int],
                cast(object, row)
            )

        version: int = typed_row[0]
        stock: int = typed_row[1]

        if stock < qty:
            return (False, stock)

        upd = (
            update(Book)
            .where(
                Book.id == book_id,
                Book.version == version,
                Book.stock >= qty,
            )
            .values(
                stock=Book.stock - qty,
                version=Book.version + 1,
            )
        )
        result = db.execute(upd)
        typed_result = cast(CursorResult[object], result)
        ok = typed_result.rowcount == 1
        return (ok, stock)

    # ---- Idempotency ----
    @staticmethod
    def get_idempotency(db: Session, key: str) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(IdempotencyKey.id == key)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    # Save idempotency key
    def save_idempotency(
        db: Session, key: str, order_id: uuid.UUID, response: JSONDict
    ) -> None:
        stmt = (
                insert(IdempotencyKey)
                .values(
                    id=key,
                    order_id=order_id,
                    response=response,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        _ = db.execute(stmt)
