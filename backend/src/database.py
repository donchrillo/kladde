"""SQLAlchemy-Setup: Engine, Session-Factory, Base, `get_db`-Dependency."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# check_same_thread nur für SQLite relevant (mehrere Threads im Dev-Server).
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Gemeinsame Basis aller ORM-Modelle."""


def get_db() -> Iterator[Session]:
    """FastAPI-Dependency: liefert eine Session und schließt sie sauber."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
