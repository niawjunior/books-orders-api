from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db_with_tenant
from app.services.book_service import BookService
from app.schemas.book import BookCreate, BookRead
from typing import Annotated
import uuid
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_422_UNPROCESSABLE_CONTENT,
)
router = APIRouter(prefix="/books", tags=["books"])


@router.post("", response_model=BookRead)
def create_book(
    data: BookCreate,
    db: Annotated[Session, Depends(get_db_with_tenant)],
):
    try:
        return BookService.create_book(db, data)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Handle database constraint violations
        error_msg = str(e).lower()
        if "foreign key constraint" in error_msg or "is not present in table" in error_msg:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid author_id - author does not exist")
        elif "check constraint" in error_msg or "price must be >= 0" in error_msg or "stock must be >= 0" in error_msg:
            raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
        else:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=f"Database constraint violation: {str(e)}")


@router.get("", response_model=list[BookRead])
def list_books(
    db: Annotated[Session, Depends(get_db_with_tenant)],
    author_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    sort: Annotated[str, Query(pattern="^(title|published_at)$")] = "title",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return BookService.list_books(
        db,
        author_id=author_id,
        q=q,
        sort=sort,
        limit=limit,
        offset=offset,
    )
