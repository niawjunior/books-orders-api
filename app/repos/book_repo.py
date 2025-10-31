from sqlalchemy.orm import Session
from app.models.book import Book
from app.schemas.book import BookCreate
from sqlalchemy import select, update
import uuid
from app.utils.pagination import clamp_pagination
from sqlalchemy.sql.expression import ColumnElement
from typing import cast
class BookRepository:
    @staticmethod

    # Create a new book
    def create(db: Session, data: BookCreate) -> Book:
        book = Book(**data.model_dump())
        db.add(book)
        db.commit()
        db.refresh(book)
        return book

    @staticmethod
    # List books
    def list(
        db: Session,
        author_id: uuid.UUID | None = None,
        q: str | None = None,
        sort: str = "title",
        limit: int = 20,
        offset: int = 0,
    ) -> list[Book]:
        limit, offset = clamp_pagination(limit, offset)

        stmt = select(Book)

        # filters
        if author_id:
            stmt = stmt.where(Book.author_id == author_id)
        if q:
            stmt = stmt.where(Book.title.ilike(f"%{q.strip()}%"))

        # sorting
        if sort in ("title", "published_at"):
            sort_column = cast(ColumnElement[object], getattr(Book, sort))
            stmt = stmt.order_by(sort_column)

        # pagination
        stmt = stmt.limit(limit).offset(offset)

        # execute & return
        return list(db.scalars(stmt).all())

    @staticmethod
    # Get a book by ID
    def get(db: Session, book_id: uuid.UUID) -> Book | None:
        stmt = select(Book).where(Book.id == book_id)
        return db.scalars(stmt).first()

    @staticmethod
    # Get a book by ID for update
    def get_for_update(db: Session, book_id: uuid.UUID) -> Book | None:
        stmt = select(Book).where(Book.id == book_id).with_for_update()
        return db.scalars(stmt).first()

    @staticmethod
    # Update the stock of a book
    def update_stock(db: Session, book_id: uuid.UUID, new_stock: int) -> None:
        stmt = update(Book).where(Book.id == book_id).values(stock=new_stock)
        _ = db.execute(stmt)

    @staticmethod
    # Check if a book exists
    def book_exists(db: Session, title: str, author_id: uuid.UUID, year: int) -> bool:
        from datetime import date
        stmt = (
            select(Book)
            .where(Book.title == title)
            .where(Book.author_id == author_id)
            .where(Book.published_at.between(date(year, 1, 1), date(year, 12, 31)))
        )
        return db.scalars(stmt).first() is not None
