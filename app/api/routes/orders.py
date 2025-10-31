from fastapi import APIRouter, Depends, Header, Path
from sqlalchemy.orm import Session
from typing import Annotated
import uuid

from app.db.session import get_db_with_tenant
from app.schemas.order import OrderCreate, OrderRead
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead)
def create_order(data: OrderCreate, db: Annotated[Session, Depends(get_db_with_tenant)]):
    return OrderService.create_order(db, data)


@router.post("/{order_id}/confirm")
def confirm_order(
    db: Annotated[Session, Depends(get_db_with_tenant)],
    order_id: Annotated[uuid.UUID, Path(..., description="Order ID to confirm")],
    idempotency_key: Annotated[str | None, Header()] = None,
):
    return OrderService.confirm_order(db, order_id, idempotency_key)
