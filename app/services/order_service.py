from collections.abc import Mapping
from typing import cast
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.schemas.order import OrderCreate, OrderItemRead, OrderRead
from app.repos.order_repo import OrderRepository
import uuid

from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


JSONValue = str | int | bool | float | None | dict[str, "JSONValue"] | list["JSONValue"]

class OrderService:
    @staticmethod
    def create_order(db: Session, data: OrderCreate) -> OrderRead:
        try:
            order = OrderRepository.create_draft(db, data)
            items = [
                OrderItemRead(product_id=it.product_id, qty=it.qty)
                for it in OrderRepository.list_items(db, order.id)
            ]
            return OrderRead(
                id=order.id, status=order.status, created_at=order.created_at, items=items
            )
        except IntegrityError as e:
            db.rollback()
            # Let the global error handler convert this to a proper 400 response
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Referenced resource not found") from e

    @staticmethod
    def confirm_order(
        db: Session, order_id: uuid.UUID, idempotency_key: str | None
    ) ->  Mapping[str, str | int | bool]:
        # Idempotency: if key exists, return stored response immediately
        if idempotency_key:
               cached = OrderRepository.get_idempotency(db, idempotency_key)
               if cached:
                   return cast(Mapping[str, str | int | bool], cached.response)

        order = OrderRepository.get(db, order_id)
        if not order:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="order not found")

        if order.status != "DRAFT":
            # Already confirmed/cancelled → treat as idempotent success for CONFIRMED
            response: dict[str, str | int | bool] = {
                "id": str(order.id),
                "status": order.status,
                "created_at": order.created_at.isoformat(),
            }

            if idempotency_key:
                    OrderRepository.save_idempotency(
                        db,
                        idempotency_key,
                        order.id,
                        cast(dict[str, JSONValue], dict(response)),
                    )
                    db.commit()

            return response

        # Try to decrement stock for each item using optimistic locking
        items = OrderRepository.list_items(db, order.id)
        shortages: list[dict[str, int | str]] = []

        # Use a transaction boundary
        try:
            for it in items:
                ok, available = OrderRepository.try_decrement_book_optimistic(
                    db, it.product_id, it.qty
                )
                if not ok:
                    shortages.append(
                        {
                            "product_id": str(it.product_id),
                            "requested": it.qty,
                            "available": available,
                        }
                    )

            if shortages:
                db.rollback()
                raise HTTPException(status_code=HTTP_409_CONFLICT, detail={"shortages": shortages})

            OrderRepository.set_status(db, order.id, "CONFIRMED")
            db.commit()

        except HTTPException:
            # rethrow 409, etc.
            raise
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Data integrity violation") from e
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="confirm failed") from e

        # Build response
        response = {
            "id": str(order.id),
            "status": "CONFIRMED",
            "created_at": order.created_at.isoformat(),
        }

        # Save idempotency record if provided (after success)
        if idempotency_key:
            OrderRepository.save_idempotency(
                db,
                idempotency_key,
                order.id,
                cast(dict[str, JSONValue], dict(response)),
            )
            db.commit()

        return response
