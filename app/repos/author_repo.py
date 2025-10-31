from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.author import Author
from app.schemas.author import AuthorCreate
from app.utils.pagination import clamp_pagination


class AuthorRepository:

    @staticmethod
    # Create a new author
    def create(db: Session, data: AuthorCreate) -> Author:
        author = Author(name=data.name, email=data.email)
        db.add(author)
        db.commit()
        db.refresh(author)
        return author

    @staticmethod
    # List authors
    def list(
        db: Session,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Author]:
        limit, offset = clamp_pagination(limit, offset)

        stmt = select(Author)

        if q:
            stmt = stmt.where(Author.name.ilike(f"%{q.strip()}%"))

        stmt = stmt.order_by(Author.name.asc()).limit(limit).offset(offset)
        return list(db.scalars(stmt).all())

    @staticmethod
    # Get an author by email
    def get_by_email(db: Session, email: str) -> Author | None:
        stmt = select(Author).where(Author.email == email)
        return db.scalars(stmt).first()
