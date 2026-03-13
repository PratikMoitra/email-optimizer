"""
Database connection and session management.
Uses SQLAlchemy for ORM. Supports both PostgreSQL and SQLite.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

db_url = settings.DATABASE_URL

# SQLite support (for local development without PostgreSQL)
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    **({"pool_size": 10, "max_overflow": 20} if not db_url.startswith("sqlite") else {}),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables if they don't exist."""
    from models import Base as ModelsBase  # noqa: F811
    ModelsBase.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session, auto-closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
