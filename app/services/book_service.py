from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import uuid
from app.schemas.book import BookCreate
from app.repos.book_repo import BookRepository
from app.models.book import Book


class BookService:
    @staticmethod
    # Create book
    def create_book(db: Session, data: BookCreate) -> Book:
        year = data.published_at.year if data.published_at else None

        query = select(func.count()).where(
            Book.title == data.title,
            Book.author_id == data.author_id,
            func.extract("year", Book.published_at) == year,
        )

        if db.scalar(query):
            raise ValueError("Duplicate book (title + author + year)")

        return BookRepository.create(db, data)

    @staticmethod
    # List books
    def list_books(
        db: Session,
        author_id: uuid.UUID | None = None,
        q: str | None = None,
        sort: str = "title",
        limit: int = 20,
        offset: int = 0,
    ) -> list[Book]:
        return BookRepository.list(
            db,
            author_id=author_id,
            q=q,
            sort=sort,
            limit=limit,
            offset=offset,
        )
