# ExoKanban

An AI-powered personal Kanban board that understands natural language. Create, update, move, and query cards by typing what you want — no forms, no dropdowns.

Available as a CLI tool, a Telegram bot, and an MCP server.

## How it works

Every entity (Board, Column, Card) inherits from **ExoModel**, which exposes:

- `MyClass.create("natural language prompt")` — creates an instance with AI-populated fields
- `instance.update_object("instruction")` — mutates fields via AI without manual routing
- `instance.to_ui()` — renders the object for display

Business logic lives in **KanbanService**, which is provider-agnostic and consumed by the CLI, the Telegram bot, and the MCP server without duplication.

Persistence is handled by **SQLModel** over SQLite (swappable to PostgreSQL via `DATABASE_URL`).

## Default board layout

```
Inbox → Priority → This Week → Today → Done → Archive
```

Cards flow left to right. The last column is hidden from the default board view and acts as a long-term archive.

## Setup

**1. Clone and create the virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and set your API key. Google Gemini is the default provider:

```
GOOGLE_API_KEY=your_key_here
MY_LLM_MODEL=google_genai:gemini-2.5-flash-lite
```

Other supported providers: `anthropic:claude-sonnet-4-6`, `openai:gpt-4o`. See `.env.example` for details.

**3. Run**

```bash
python main.py
```

## Commands

| Command | Description |
|---|---|
| `/new [prompt]` | Create a card from a natural language description |
| `<space> [prompt]` | Same as `/new` |
| `/card` | Show the currently selected card |
| `/card [id]` | Select and show a card by id |
| `/card [prompt]` | Find a card by semantic search |
| `/cards` | Show all visible columns and their cards |
| `/cards [column]` | Show cards in a specific column (by id or name) |
| `/update [prompt]` | Update the current card via natural language |
| `/move [column]` | Move the current card to a column |
| `/archive` | Archive the current card |
| `/archive [id]` | Archive a card by id |
| `/due` | Cards with due dates: overdue, due today, and next 7 days |
| `/old` | Move cards older than 30 days from the second-to-last column to the last |
| `/export` | Export `board.csv`, `column.csv`, and `card.csv` to the current directory |
| `/board` | Show the full board |
| `/instructions` | Show AI-generated filling instructions for the board |
| `/help` | Show this command list |
| free text | Chat with the board AI agent directly |

### Examples

```
>>> /new schedule annual medical checkup
>>> /new prepare proposal for client ABC, high priority, due next friday
>>> /move Today
>>> /update change priority to critical and add due date for tomorrow
>>> /card proposal ABC
>>> /due
>>> /export
```

## Telegram bot

Set `INTERACTION_MODE=telegram` in `.env` and provide a `TELEGRAM_TOKEN`. To restrict access, set `TELEGRAM_ALLOWED_USERS` to a comma-separated list of Telegram user IDs. Leave it blank to make the bot public.

```
INTERACTION_MODE=telegram
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USERS=123456789
```

## Card fields

| Field | Description |
|---|---|
| `title` | Short, action-oriented description |
| `description` | What needs to be done and what done looks like |
| `priority` | `low` / `medium` / `high` / `critical` |
| `tag` | Context label — work: `comercial`, `marketing`, `projeto`, `produto`, `reunião`, `financeiro`, `administrativo`, `jurídico`, `tecnologia`, `networking`, `eventos` / personal: `família`, `saúde`, `educação`, `casa`, `compras`, `viagem`, `hobby`, `social` / general: `ideia`, `pesquisa` |
| `due_date` | ISO 8601 date — only when there is a real deadline |
| `archived` | `true` removes the card from all active views |

## MCP server

ExoKanban exposes all board operations as MCP tools over HTTP, allowing AI assistants (Claude Desktop, Claude Code, etc.) to manage the board directly.

**Start the server**

```bash
python mcp_server.py
# Listening on http://0.0.0.0:8000
```

**Generate a token**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set it in `.env`:

```
MCP_AUTH_TOKEN=your_generated_token
```

**Connect from Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "exokanban": {
      "url": "http://your-server:8000/mcp",
      "headers": { "Authorization": "Bearer your_generated_token" }
    }
  }
}
```

**Available MCP tools**

| Tool | Description |
|---|---|
| `show_board` | Full board with all visible columns |
| `list_cards` | Cards in all columns, or a specific column |
| `create_card` | Create a card from natural language |
| `get_card` | Get a card by id |
| `find_card` | Find a card by semantic description |
| `update_card` | Update a card's fields via natural language |
| `move_card` | Move a card to a column |
| `archive_card` | Archive a card |
| `show_due_cards` | Overdue, due today, and next 7 days |
| `move_old_cards` | Move 30-day-old cards to the archive column |
| `export_to_csv` | Export all data to CSV files |

**MCP env vars**

| Variable | Default | Description |
|---|---|---|
| `MCP_AUTH_TOKEN` | _(empty)_ | Bearer token. Empty = no auth (not recommended in production) |
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `8000` | Port |
| `MCP_BOARD_NAME` | `Kanban to-do` | Board name to connect to |

## Architecture

```
main.py               KanbanInteraction — routes commands, manages conversational state (_current_card_id)
mcp_server.py         FastMCP server    — 11 MCP tools over HTTP with Bearer token auth
kanban_service.py     KanbanService     — pure business logic, shared by all interfaces
userinteraction.py    UserInteraction   — CLI and Telegram I/O adapter
models/               Board, Column, Card (ExoSQLModel = ExoModel + SQLModel)
db/                   Engine, UnitOfWork, session ContextVar
rag/                  Markdown knowledge files indexed into the RAG vector store
```

## Development

```bash
pytest tests/ -v -s          # run all tests
pytest tests/ -v -s -k tag   # run a subset
```

The test suite uses an in-memory SQLite database and mocks LLM calls where possible. LLM-dependent tests call the real API and may be non-deterministic.

## LLM providers

Install the extra for your provider:

```bash
pip install exomodel[google]      # Google Gemini (default)
pip install exomodel[anthropic]   # Anthropic Claude
pip install exomodel[openai]      # OpenAI
```

Then set `MY_LLM_MODEL` accordingly in `.env`.
