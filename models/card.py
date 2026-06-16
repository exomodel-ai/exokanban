from datetime import datetime
from typing import Literal, Optional, TYPE_CHECKING
from pydantic import create_model
from sqlmodel import Field, Relationship
from db.base import ExoSQLModel
from models.tags import TAGS

if TYPE_CHECKING:
    from models.column import Column


class Card(ExoSQLModel, table=True):
    __tablename__ = "cards"

    title: str = ""
    description: str = ""
    priority: str = "medium"
    tag: str = ""
    due_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    archived: bool = False

    column_id: Optional[int] = Field(default=None, foreign_key="columns.id")
    column: Optional["Column"] = Relationship(back_populates="cards")

    def update_object(self, prompt: str) -> dict:
        result = super().update_object(prompt)
        if result:
            self.updated_at = datetime.now()
        if not self.title:
            # LLM skipped title — request it explicitly from the available context
            context = self.description or prompt
            title = self.update_field("title", context)
            if title:
                self.updated_at = datetime.now()
        return result

    def move_to(self, column_id: int) -> None:
        self.column_id = column_id
        self.updated_at = datetime.now()

    def archive(self) -> None:
        self.archived = True
        self.updated_at = datetime.now()

    @classmethod
    def _build_extraction_schema(cls):
        base = super()._build_extraction_schema()
        fields = {}
        for name, field in base.model_fields.items():
            if name == "tag":
                fields[name] = (Optional[Literal[tuple(TAGS)]], None)
            else:
                fields[name] = (field.annotation, field.default)
        return create_model(f"{cls.__name__}Extraction", **fields)

    def is_overdue(self) -> bool:
        return self.due_date is not None and self.due_date.date() < datetime.now().date()

    def is_due_within(self, days: int) -> bool:
        from datetime import timedelta
        if self.due_date is None:
            return False
        today = datetime.now().date()
        return today <= self.due_date.date() <= today + timedelta(days=days)

    def is_stale(self, days: int) -> bool:
        from datetime import timedelta
        return self.updated_at < datetime.now() - timedelta(days=days)

    def lead_time_days(self) -> float | None:
        delta = self.updated_at - self.created_at
        return delta.total_seconds() / 86400 if delta.total_seconds() > 0 else None

    @classmethod
    def get_rag_sources(cls) -> list[str]:
        return ["rag/card.md", "rag/kanban-to-do.md"]
