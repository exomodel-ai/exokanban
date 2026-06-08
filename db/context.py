"""
Implicit session via ContextVar.

Thread-safe and async-safe: each thread/coroutine has its own session.
Never import Session directly in models — use get_current_session().
"""
from contextvars import ContextVar, Token
from typing import Optional

from sqlmodel import Session

_session_var: ContextVar[Optional[Session]] = ContextVar("db_session", default=None)


def get_current_session() -> Optional[Session]:
    return _session_var.get()


def _set_session(session: Optional[Session]) -> Token:
    """Internal use — only UnitOfWork should call this."""
    return _session_var.set(session)


def _reset_session(token: Token) -> None:
    """Internal use — only UnitOfWork should call this."""
    _session_var.reset(token)
