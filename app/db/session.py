from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from collections.abc import Generator
from fastapi import Request
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Get a database session with the current tenant set as the search path.
def get_db_with_tenant(request: Request) -> Generator[Session, None, None]:
    """
    Set search path to <tenant>, public.
    """
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
        return

    db = SessionLocal()
    try:
        _ = db.execute(text(f'SET search_path TO "{tenant}", public'))

        yield db
    finally:
        db.close()
