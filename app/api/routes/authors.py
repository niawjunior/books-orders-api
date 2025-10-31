from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db_with_tenant
from app.services.author_service import AuthorService
from app.schemas.author import AuthorCreate, AuthorRead
from app.core.logging import get_logger
from typing import Annotated
from starlette.status import (
    HTTP_400_BAD_REQUEST,
)
router = APIRouter(prefix="/authors", tags=["authors"])


@router.post("", response_model=AuthorRead)
def create_author(
    data: AuthorCreate,
    db: Annotated[Session, Depends(get_db_with_tenant)],
):
    try:
        return AuthorService.create_author(db, data)
    except Exception as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[AuthorRead])
def list_authors(
    db: Annotated[Session, Depends(get_db_with_tenant)],
):
    logger = get_logger(__name__)
    logger.info("Listing authors")
    return AuthorService.list_authors(db)
