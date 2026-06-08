"""
ExoKanban MCP Server

Exposes KanbanService as MCP tools over HTTP with Bearer token authentication.
Run with: python mcp_server.py
"""
import logging
import os
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import html2text as _html2text

from db.engine import create_tables
from db.uow import UnitOfWork
from models.board import Board
from kanban_service import KanbanService

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
MCP_HOST       = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT       = int(os.getenv("MCP_PORT", "8000"))
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")
BOARD_NAME     = os.getenv("MCP_BOARD_NAME", "Kanban to-do")

if not MCP_AUTH_TOKEN:
    logger.warning("MCP_AUTH_TOKEN is not set — server will accept unauthenticated requests.")

create_tables()

# ── Board service singleton ────────────────────────────────────────────────────
_service_instance: Optional[KanbanService] = None


def _get_service() -> KanbanService:
    global _service_instance
    if _service_instance is None:
        with UnitOfWork() as uow:
            board = Board.first(name=BOARD_NAME)
            if not board:
                raise RuntimeError(
                    f"Board '{BOARD_NAME}' not found. "
                    "Run 'python main.py' once to initialise the database."
                )
            board_id = board.id
        _service_instance = KanbanService(board_id)
    return _service_instance


# ── Output helper ──────────────────────────────────────────────────────────────
def _html_to_md(html: str) -> str:
    """Converts HTML-formatted board output to clean Markdown for MCP clients."""
    h = _html2text.HTML2Text()
    h.ignore_links = True
    h.body_width = 0
    return h.handle(html).strip()


# ── Auth middleware ────────────────────────────────────────────────────────────
class BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str = ""):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if self.token:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {self.token}":
                return Response("Unauthorized", status_code=401, media_type="text/plain")
        return await call_next(request)


# ── MCP server ─────────────────────────────────────────────────────────────────
mcp = FastMCP("ExoKanban")


@mcp.tool()
def show_board() -> str:
    """Show the full Kanban board with all visible columns and their cards."""
    return _html_to_md(_get_service().show_board())


@mcp.tool()
def list_cards(column_hint: str = "") -> str:
    """
    List cards on the board.
    Pass a column name or numeric id to filter by column; leave blank for all columns.
    """
    return _html_to_md(_get_service().list_cards(column_hint))


@mcp.tool()
def create_card(prompt: str) -> str:
    """
    Create a new card from a natural language description.
    The AI will populate title, description, priority, tag, and due_date from the prompt.
    Returns the created card.
    """
    card = _get_service().create_card(prompt)
    return card.to_ui(format="markdown")


@mcp.tool()
def get_card(card_id: int) -> str:
    """Get a card by its numeric id. Returns the full card details."""
    try:
        card = _get_service().get_card(card_id)
        return card.to_ui(format="markdown")
    except ValueError as e:
        return str(e)


@mcp.tool()
def find_card(prompt: str) -> str:
    """Find a card by semantic description. Searches across all active cards on the board."""
    card = _get_service().find_card(prompt)
    if not card:
        return "No card found matching that description."
    return card.to_ui(format="markdown")


@mcp.tool()
def update_card(card_id: int, prompt: str) -> str:
    """
    Update a card's fields using a natural language instruction.
    Example: update_card(3, "change priority to critical and set due date to next friday")
    Returns the updated card.
    """
    try:
        card = _get_service().update_card(card_id, prompt)
        return card.to_ui(format="markdown")
    except ValueError as e:
        return str(e)


@mcp.tool()
def move_card(card_id: int, column_prompt: str) -> str:
    """
    Move a card to a column identified by name or description.
    Example: move_card(3, "Today") or move_card(3, "Done")
    """
    try:
        dest = _get_service().move_card(card_id, column_prompt)
        return f"Card #{card_id} moved to '{dest}'."
    except ValueError as e:
        return str(e)


@mcp.tool()
def archive_card(card_id: int) -> str:
    """Archive a card, removing it from all active views."""
    try:
        return _get_service().archive_card(card_id)
    except ValueError as e:
        return str(e)


@mcp.tool()
def show_due_cards() -> str:
    """Show cards with due dates: overdue, due today, and due in the next 7 days."""
    return _html_to_md(_get_service().show_due_cards())


@mcp.tool()
def move_old_cards() -> str:
    """Move cards older than 30 days from the penultimate column to the last (archive) column."""
    return _get_service().move_old_cards()


@mcp.tool()
def export_to_csv() -> str:
    """Export all board, column, and card data to board.csv, column.csv, and card.csv."""
    return _get_service().export_to_csv()


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=MCP_HOST,
        port=MCP_PORT,
        middleware=[Middleware(BearerTokenMiddleware, token=MCP_AUTH_TOKEN)],
    )
