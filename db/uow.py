"""
Unit of Work — manages the session lifecycle.

Rules:
- Only the UoW opens, commits, rolls back, and closes the session.
- Injects the session into the ContextVar on enter, clears it on exit.
- Automatic rollback on any unhandled exception.

Usage:
    with UnitOfWork() as uow:
        obj = MyModel.create("prompt")
        uow.commit()
        uow.refresh(obj)
"""
import db.engine as _db_engine
from sqlmodel import Session
from db.context import _set_session, _reset_session


class UnitOfWork:
    def __init__(self):
        self._session: Session | None = None
        self._token = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> "UnitOfWork":
        self._session = Session(_db_engine.engine)
        self._token = _set_session(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
            _reset_session(self._token)
            self._session = None
            self._token = None
        return False  # never suppress the exception

    # ------------------------------------------------------------------
    # Session access (for direct flush, add, exec when needed)
    # ------------------------------------------------------------------

    @property
    def session(self) -> Session:
        self._assert_active()
        return self._session

    # ------------------------------------------------------------------
    # Transaction operations
    # ------------------------------------------------------------------

    def commit(self) -> None:
        self._assert_active()
        self._session.commit()

    def rollback(self) -> None:
        self._assert_active()
        self._session.rollback()

    def refresh(self, obj) -> None:
        self._assert_active()
        self._session.refresh(obj)

    def flush(self) -> None:
        self._assert_active()
        self._session.flush()

    # ------------------------------------------------------------------
    # Savepoints — partial rollback without aborting the transaction
    # ------------------------------------------------------------------

    def savepoint(self):
        """
        Returns a context manager for partial rollback.

            with UnitOfWork() as uow:
                obj_a.save()
                with uow.savepoint():
                    obj_b.save()
                    raise ValueError("only obj_b rolls back")
                uow.commit()   # obj_a persists
        """
        self._assert_active()
        return self._session.begin_nested()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assert_active(self) -> None:
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork is not active. Use 'with UnitOfWork() as uow:'."
            )
