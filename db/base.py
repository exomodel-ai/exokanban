"""
ExoSQLModel — base class for all persisted models.

Combines:
- ExoModel   → AI-native fields (LLM, RAG, llm_function)
- SQLModel   → ORM mapping for the database

The session is never passed as an argument — it is obtained from the ContextVar
injected by UnitOfWork. This keeps signatures clean and business code free of
any reference to db.*.

Write methods do NOT commit — that is the responsibility of UnitOfWork.
This separation ensures multiple operations can be grouped into a single atomic transaction.
"""
from typing import Any, Optional, TypeVar

from sqlalchemy.orm import reconstructor
from sqlmodel import Field, SQLModel, select

from exomodel import ExoModel
from db.context import get_current_session

T = TypeVar("T", bound="ExoSQLModel")


class ExoSQLModel(ExoModel, SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)

    # ------------------------------------------------------------------
    # ORM initialisation (loaded from DB, not Python __init__)
    # ------------------------------------------------------------------

    @reconstructor
    def _init_on_load(self) -> None:
        if self.__pydantic_private__ is None:
            self.__pydantic_private__ = {
                k: (
                    v.default_factory()
                    if v.default_factory is not None
                    else v.default
                )
                for k, v in self.__private_attributes__.items()
            }
        self._rag_sources = self.get_rag_sources()

    # ------------------------------------------------------------------
    # Preserves _sa_instance_state after update_object (ExoModel rewrites
    # __dict__ via model_validate, corrupting ORM change tracking)
    # ------------------------------------------------------------------

    def update_object(self, prompt: str) -> dict:
        state = self.__dict__.get("_sa_instance_state")
        result = super().update_object(prompt)
        if state is not None:
            self.__dict__["_sa_instance_state"] = state
            if result:
                from sqlalchemy.orm.attributes import flag_modified
                for field_name in result:
                    try:
                        flag_modified(self, field_name)
                    except Exception:
                        pass
        return result

    # ------------------------------------------------------------------
    # Session access — never exposed as an argument
    # ------------------------------------------------------------------

    @staticmethod
    def _get_session():
        s = get_current_session()
        if s is None:
            raise RuntimeError(
                "No active session. "
                "Wrap the operation in 'with UnitOfWork() as uow:'."
            )
        return s

    # ------------------------------------------------------------------
    # Write — no commit (responsibility of UnitOfWork)
    # ------------------------------------------------------------------

    def save(self: T) -> T:
        s = self._get_session()
        return s.merge(self)  # type: ignore[return-value]

    def delete(self) -> None:
        s = self._get_session()
        obj = s.get(type(self), self.id)
        if obj is not None:
            s.delete(obj)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @classmethod
    def get_by_id(cls: type[T], record_id: int) -> Optional[T]:
        return cls._get_session().get(cls, record_id)

    @classmethod
    def all(cls: type[T]) -> list[T]:
        return list(cls._get_session().exec(select(cls)).all())

    @classmethod
    def find(cls: type[T], **filters: Any) -> list[T]:
        stmt = select(cls)
        for attr, value in filters.items():
            stmt = stmt.where(getattr(cls, attr) == value)
        return list(cls._get_session().exec(stmt).all())

    @classmethod
    def first(cls: type[T], **filters: Any) -> Optional[T]:
        stmt = select(cls)
        for attr, value in filters.items():
            stmt = stmt.where(getattr(cls, attr) == value)
        return cls._get_session().exec(stmt).first()

    # ------------------------------------------------------------------
    # LLM factory
    # ------------------------------------------------------------------

    @classmethod
    def create(cls: type[T], prompt: str, **initial_values: Any) -> T:
        instance: T = super().create(prompt, **initial_values)  # type: ignore
        return instance.save()

    # ------------------------------------------------------------------
    # Hook for subclasses
    # ------------------------------------------------------------------

    @classmethod
    def get_rag_sources(cls) -> list[str]:
        return []
