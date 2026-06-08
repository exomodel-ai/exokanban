from dotenv import load_dotenv
load_dotenv()

import logging
from typing import Optional

logger = logging.getLogger(__name__)

from db.engine import create_tables
from db.seed import seed

from models.board import Board
from kanban_service import KanbanService
from userinteraction import UserInteraction


create_tables()


class KanbanInteraction(UserInteraction):
    board = seed()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._service = KanbanService(self.board.id)
        self._current_card_id: Optional[int] = None

    async def process_prompt(self, user_id, text):
        try:
            return await self._handle(user_id, text)
        except Exception as e:
            logger.error("Erro ao processar prompt (user=%s): %s", user_id, e, exc_info=True)
            return f"❌ {e}"

    async def _handle(self, user_id, text):
        msg = text.strip()
        msg_clean = text.lower().strip()

        if msg_clean in ["help", "h", "/help", "/h"]:
            return (
                "This is a Kanban Board AI Agent\n"
                "Commands:\n"
                "/board - Show board\n"
                "/card - Get current card\n"
                "/card [id] - Get card by id\n"
                "/card [prompt] - Get card from prompt\n"
                "/cards [column id - optional] - Get cards from the board or a specific column\n"
                "/new [prompt] - Create a new card\n"
                "<space>[prompt] - Create a new card (same as /new)\n"
                "/update [prompt] - Update current card\n"
                "/move [column] - Move current card to column\n"
                "/archive - Archive current card\n"
                "/archive [id] - Archive card by id\n"
                "/old - Move old cards to old cards column\n"
                "/due - Cards with due dates: overdue, today and next 7 days\n"
                "/export - Export board.csv, column.csv and card.csv\n"
                "or type the prompt and interact with the board AI agent\n"
            )
        elif "/instructions" in msg_clean:
            return self.board.run_filling_instructions()
        elif "/board" in msg_clean:
            return self._service.show_board()
        elif "/cards" in msg_clean:
            column_hint = msg_clean.replace("/cards", "").strip()
            return self._service.list_cards(column_hint)
        elif text.startswith(" "):
            return self.create_card(msg)
        elif "/new" in msg_clean:
            prompt = msg[msg.lower().index("/new") + len("/new"):].strip()
            return self.create_card(prompt)
        elif "/update" in msg_clean:
            prompt = msg[msg.lower().index("/update") + len("/update"):].strip()
            return self.update_current_card(prompt)
        elif "/move" in msg_clean:
            prompt = msg[msg.lower().index("/move") + len("/move"):].strip()
            return self.move_current_card(prompt)
        elif "/old" in msg_clean:
            return self._service.move_old_cards()
        elif "/due" in msg_clean:
            return self._service.show_due_cards()
        elif "/export" in msg_clean:
            return self._service.export_to_csv()
        elif "/archive" in msg_clean:
            hint = msg[msg.lower().index("/archive") + len("/archive"):].strip()
            if hint.isdigit():
                return self.archive_card_by_id(int(hint))
            else:
                return self.archive_current_card()
        elif "/card" in msg_clean:
            hint = msg[msg.lower().index("/card") + len("/card"):].strip()
            if not hint:
                return self.get_current_card()
            elif hint.isdigit():
                return self.get_card_by_id(int(hint))
            else:
                return self.get_card_from_prompt(hint)
        else:
            return self.run_master_prompt(msg)

    # ------------------------------------------------------------------
    # Conversational wrappers — manage _current_card_id around service calls
    # ------------------------------------------------------------------

    def show_cards(self, cards) -> str:
        if not cards:
            return "No cards found."
        return "\n\n".join(card.to_ui() for card in cards)

    def get_current_card(self) -> str:
        if not self._current_card_id:
            return "No card selected."
        return self.get_card_by_id(self._current_card_id)

    def get_card_by_id(self, card_id: int) -> str:
        try:
            card = self._service.get_card(card_id)
            self._current_card_id = card_id
            return card.to_ui()
        except ValueError as e:
            return str(e)

    def create_card(self, prompt: str) -> str:
        if not prompt:
            return "Please describe the card. Ex: /new Review proposal for client ABC"
        card = self._service.create_card(prompt)
        self._current_card_id = card.id
        return card.to_ui()

    def move_current_card(self, prompt: str) -> str:
        if not self._current_card_id:
            return "No card selected. Use /card to select one first."
        if not prompt:
            return "Please specify the destination column. Ex: /move Priority"
        dest_name = self._service.move_card(self._current_card_id, prompt)
        return f"Card moved to '{dest_name}'."

    def update_current_card(self, prompt: str) -> str:
        if not self._current_card_id:
            return "No card selected. Use /card to select one first."
        if not prompt:
            return "Please describe what to update. Ex: /update change priority to high"
        try:
            card = self._service.update_card(self._current_card_id, prompt)
            return card.to_ui()
        except ValueError as e:
            return str(e)

    def archive_current_card(self) -> str:
        if not self._current_card_id:
            return "No card selected. Use /card to select one first."
        result = self._service.archive_card(self._current_card_id)
        self._current_card_id = None
        return result

    def archive_card_by_id(self, card_id: int) -> str:
        try:
            result = self._service.archive_card(card_id)
            if self._current_card_id == card_id:
                self._current_card_id = None
            return result
        except ValueError as e:
            return str(e)

    def get_card_from_prompt(self, prompt: str) -> str:
        card = self._service.find_card(prompt)
        if not card:
            return "No card found."
        self._current_card_id = card.id
        return card.to_ui()

    def run_master_prompt(self, msg: str) -> str:
        result, new_card_id = self._service.run_board_prompt(msg, self._current_card_id)
        if new_card_id is not None:
            self._current_card_id = new_card_id
        return result

    # Delegated directly — no state management needed
    def show_board(self) -> str:        return self._service.show_board()
    def show_due_cards(self) -> str:    return self._service.show_due_cards()
    def move_old_cards(self) -> str:    return self._service.move_old_cards()
    def export_to_csv(self) -> str:     return self._service.export_to_csv()


def main():
    bot = KanbanInteraction()
    bot.run()


if __name__ == "__main__":
    main()
