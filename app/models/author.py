from sqlalchemy import  Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, CITEXT
import uuid
from app.models.base import Base
#Author
class Author(Base):
    __tablename__: str = "authors"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True, nullable=True)
