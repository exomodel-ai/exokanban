"""
SQLAlchemy/SQLModel engine.

Single configuration point for the database. No other module
should create engines or import connection strings.
"""
import os
from sqlmodel import SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///exokanban.db")

_echo = os.getenv("DB_ECHO", "false").lower() == "true"
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=_echo, connect_args=_connect_args)


def create_tables() -> None:
    """Creates all tables registered in the metadata."""
    import models.board   # noqa: F401
    import models.column  # noqa: F401
    import models.card    # noqa: F401
    SQLModel.metadata.create_all(engine)
