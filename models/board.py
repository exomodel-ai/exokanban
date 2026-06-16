from datetime import datetime
from typing import Optional, TYPE_CHECKING
from exomodel import ExoAgent, llm_function
from pydantic import BaseModel
from db.base import ExoSQLModel
from sqlmodel import Field, Relationship

if TYPE_CHECKING:
    from models.column import Column
    from models.card import Card


class Board(ExoSQLModel, table=True):
    __tablename__ = "boards"

    name: str = ""
    description: str = ""
    context: str = ""
    archived: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    _current_card = None

    columns: list["Column"] = Relationship(back_populates="board")

    @llm_function
    def get_columns(self) -> list["Column"]:
        """
        Get the columns of the board.
        """
        return self.columns

    @llm_function
    def create_columns_from_prompt(self, prompt: str) -> str:
        """
        Create a column list from a prompt.
        It can receive a prompt describing the workflow and crate the board columns.
        """
        from exomodel.exomodel_list import ExoModelList
        from models.column import Column
        temp = ExoModelList(item_class=Column)
        temp.create_list(prompt=prompt)
        self.columns = list(temp.items)
        for col in self.columns:
            col.board_id = self.id

    @llm_function
    def get_cards_from_prompt(self, prompt: str) -> list["Card"]:
        """
        Use this tool whenever the user wants to see, list or retrieve cards or tasks.
        Pass the full user prompt as the argument.
        If the prompt refers to a specific column (e.g. "cards in Inbox", "what's in Today"),
        returns only the cards from that column.
        If the prompt refers to the whole board or is ambiguous (e.g. "all cards", "everything",
        "show my tasks", "cards do board"), returns cards from all columns.
        """
        try:
            column = self.get_column_from_prompt(prompt, strict=True)
            return column.get_cards()
        except ValueError:
            cards = []
            for col in self.get_columns():
                cards.extend(col.get_cards())
            return cards

    @llm_function
    def get_card_from_prompt(self, prompt: str) -> "Card":
        """
        Use this tool whenever the user wants to see, list or retrieve a specific card or task.
        Pass the full user prompt as the argument.
        """
        from typing import Optional
        from pydantic import BaseModel as PydanticBaseModel

        cards = []
        for col in self.get_columns():
            cards.extend(col.get_cards())

        if not cards:
            return None

        cards_string = cards[0].to_csv(include_header=True) + "\n"
        for c in cards[1:]:
            cards_string += c.to_csv(include_header=False) + "\n"

        class _CardMatch(PydanticBaseModel):
            card_id: Optional[int] = None

        agent = ExoAgent()
        result = agent.run(
            f"Cards disponíveis:\n{cards_string}\n"
            f"Solicitação do usuário: '{prompt}'\n"
            "Identifique o card que melhor corresponde à solicitação e retorne seu card_id. "
            "Se nenhum card corresponder, retorne card_id como null.",
            response_schema=_CardMatch,
            mode="generalist"
        )

        if result and result.card_id is not None:
            card = next((c for c in cards if c.id == result.card_id), None)
            self._current_card = card
            return card

        return None

    @llm_function
    def move_current_card_from_column_to_column(self, prompt: str) -> str:
        """
        Move the current card from one column to another column.
        """
        card = self._current_card
        if card is None:
            return "No current card selected."
        self.move_card_from_column_to_column(card, prompt)
        return f"Card '{card.title}' movido com sucesso."

    def move_card_from_column_to_column(self, card: "Card", prompt: str) -> str:
        """
        Move a card from one column to another column.
        """
        column_from = self.get_column_by_card(card)
        column_to = self.get_column_from_prompt(prompt, strict=True)
        if column_from != column_to:
            column_from.remove_card(card)
            column_to.insert_card(card)
        self._current_card = card

    def get_column_by_card(self, card: "Card") -> "Column":
        if card.column_id is not None:
            for col in self.columns:
                if col.id == card.column_id:
                    return col
        for col in self.columns:
            if col.contains_card(card):
                return col
        raise ValueError(f"Card '{card.title}' not found in any column.")

    def get_column_from_prompt(self, prompt: str, strict: bool = False) -> "Column":
        if not self.columns:
            raise ValueError(f"Board '{self.name}' has no columns.")

        if prompt.strip().isdigit():
            col_id = int(prompt.strip())
            for col in self.columns:
                if col.id == col_id:
                    return col
            if strict:
                raise ValueError(f"No column found with id: '{col_id}'")
            return self.columns[0]

        column_names = [col.name for col in self.columns]

        class _Match(BaseModel):
            column_name: str

        agent = ExoAgent()
        result = agent.run(
            f"Available columns: {column_names}\n"
            f"User request: '{prompt}'\n"
            "Return the exact column_name if the request explicitly references or clearly implies one "
            "of the available columns (e.g. 'para hoje' → Hoje, 'prioritária' → Prioridade). "
            "If the request has no column reference, return 'none'.",
            response_schema=_Match,
            mode="generalist"
        )

        matched = result.column_name.strip() if result else ""
        for col in self.columns:
            if col.name.lower() == matched.lower():
                return col

        if strict:
            raise ValueError(f"No column found matching: '{prompt}'")

        return self.columns[0]

    @llm_function
    def create_card_from_prompt(self, prompt: str):
        """
        Create a new card on the board from a natural language description.
        If the prompt identifies a target column (e.g. "add task X to Inbox",
        "nova tarefa Y em Hoje"), the card is placed in that column.
        Otherwise, the card is placed in the first column of the board.
        Pass the full user prompt as the argument.
        """
        try:
            column = self.get_column_from_prompt(prompt=prompt, strict=True)
        except ValueError:
            if not self.columns:
                raise ValueError("Board has no columns")
            column = self.columns[0]
        card = column.create_card_from_prompt(prompt)
        self._current_card = card
        return card

    @llm_function
    def show_column_cards_from_prompt(self, prompt: str) -> str:
        """
        Use this tool whenever the user wants to see, list or retrieve column cards.
        Pass the full user prompt as the argument.
        If the prompt refers to a specific column (e.g. "cards in Inbox", "what's in Today"),
        returns only the cards from that column.
        """
        try:
            column = self.get_column_from_prompt(prompt=prompt, strict=True)
        except ValueError:
            return "No column found"
        return column.show_column_cards()

    def show_column_cards(self, column: "Column" = None) -> str:
        if column:
            return column.show_column_cards()
        columns = [col for col in self.get_columns() if col.visible]
        return "\n\n".join(col.show_column_cards() for col in columns)

    def active_columns(self) -> list["Column"]:
        import os
        n = int(os.getenv("NUM_ACTIVE_COLUMNS", "4"))
        return sorted(self.columns, key=lambda c: c.position)[:n]

    def done_column(self) -> Optional["Column"]:
        import os
        n = int(os.getenv("NUM_ACTIVE_COLUMNS", "4"))
        sorted_cols = sorted(self.columns, key=lambda c: c.position)
        return sorted_cols[n] if len(sorted_cols) > n else None

    def archive_column(self) -> Optional["Column"]:
        import os
        n = int(os.getenv("NUM_ACTIVE_COLUMNS", "4"))
        sorted_cols = sorted(self.columns, key=lambda c: c.position)
        return sorted_cols[n + 1] if len(sorted_cols) > n + 1 else None

    @classmethod
    def get_rag_sources(cls) -> list[str]:
        return ["rag/board.md", "rag/kanban-to-do.md"]
