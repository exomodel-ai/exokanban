from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlmodel import Field, Relationship
from exomodel import llm_function
from db.base import ExoSQLModel

if TYPE_CHECKING:
    from models.board import Board
    from models.card import Card


class Column(ExoSQLModel, table=True):
    __tablename__ = "columns"

    name: str = ""
    description: str = ""
    position: float = 0.0
    wip_limit: int = 0
    visible: bool = True

    board_id: Optional[int] = Field(default=None, foreign_key="boards.id")
    board: Optional["Board"] = Relationship(back_populates="columns")
    cards: list["Card"] = Relationship(back_populates="column")

    @llm_function
    def create_card_from_prompt(self, prompt: str) -> None:
        """
        Creates a single card belonging to this column from a prompt.
        """
        from models.card import Card
        card = Card()
        card.update_object(prompt)
        self.insert_card(card)
        return card

    @llm_function
    def get_cards(self) -> list["Card"]:
        """
        Get the cards of the column.
        """
        return sorted(
            (c for c in self.cards if not c.archived),
            key=lambda c: c.updated_at,
            reverse=True
        )

    @llm_function
    def show_column_cards(self, limit: int = None) -> str:
        cards = self.get_cards()
        count = len(cards)
        if self.wip_limit > 0:
            wip_exceeded = count > self.wip_limit
            wip_indicator = " 🚨" if wip_exceeded else ""
            count_str = f"{count}/{self.wip_limit}"
        else:
            wip_indicator = ""
            count_str = str(count)
        lines = [f"<b>#{self.id} {self.name}</b> <i>({count_str})</i>{wip_indicator}", "━━━━━━━━━━━━━━━━━━━━"]
        if not cards:
            lines.append("<i>No cards</i>")
        displayed = cards[:limit] if limit else cards
        for card in displayed:
            parts = [f"#{card.id} {card.title}"]
            if card.tag:
                parts.append(f"[{card.tag}]")
            if card.priority == "high":
                parts.append("🔴 high")
            if card.due_date:
                parts.append(f"📅 {card.due_date.strftime('%d/%m/%Y')}")
            lines.append(" · ".join(parts))
        if limit and count > limit:
            lines.append(f"<i>[... +{count - limit} more — use /cards {self.id} to see all]</i>")
        return "\n".join(lines)

    def insert_card(self, card: "Card") -> None:
        if self.id is not None:
            card.move_to(self.id)
        try:
            self.cards.insert(0, card)
        except DetachedInstanceError:
            pass

    def remove_card(self, card: "Card") -> None:
        self.cards.remove(card)

    def contains_card(self, card: "Card") -> bool:
        return card in self.cards

    def active_count(self) -> int:
        return sum(1 for c in self.cards if not c.archived)

    def wip_status(self) -> str:
        if self.wip_limit == 0:
            return "NO_LIMIT"
        count = self.active_count()
        if count > self.wip_limit:
            return "EXCEEDED"
        if count == self.wip_limit:
            return "AT_LIMIT"
        return "OK"

    def stale_cards(self, days: int) -> list["Card"]:
        return [c for c in self.cards if not c.archived and c.is_stale(days)]

    @classmethod
    def get_rag_sources(cls) -> list[str]:
        return ["rag/column.md", "rag/kanban-to-do.md"]
