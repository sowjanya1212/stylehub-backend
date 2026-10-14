"""Database engine, session factory and base class (SQLAlchemy ORM)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# check_same_thread=False is required for SQLite when used with FastAPI.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: gives each request its own DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
