from sqlalchemy.orm import Session
from app.schemas.author import AuthorCreate
from app.repos.author_repo import AuthorRepository


class AuthorService:
    @staticmethod
    # Create author
    def create_author(db: Session, data: AuthorCreate):
        # Future: check for duplicates if needed
        return AuthorRepository.create(db, data)

    @staticmethod
    # List authors
    def list_authors(db: Session):
        return AuthorRepository.list(db)
