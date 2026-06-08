# ExoSQLModel — Implementation Plan

## Goal

Create `ExoSQLModel`, a base class that combinesExoModel's AI-powered field population with SQLModel's SQLite persistence. Migrate `Board`, `Column`, and `Card` to use it, replacing in-memory `ExoModelList` relationships with proper FK-based SQLModel relationships.

---

## Architecture Overview

```
pydantic.BaseModel
       ↑                 ↑
   ExoModel           SQLModel  (SQLModelMetaclass extends ModelMetaclass)
       ↑                 ↑
       └────ExoSQLModel──┘   (no table=True — abstract base)
                  ↑
         Board / Column / Card  (table=True — concrete tables)
```

Python resolves the metaclass conflict automatically: `SQLModelMetaclass` already extends Pydantic's `ModelMetaclass`, so it wins the MRO and governs all subclasses.

MRO for a concrete model:
`Board → ExoSQLModel → ExoModel → SQLModel → BaseModel`

---

## Key Technical Constraints

### 1. Multiple Inheritance and `__init__`

SQLModel's `__init__` calls `sqlmodel_init()`, which handles SQLAlchemy instrumentation. ExoModel's `__init__` calls `super().__init__(**data)` then sets private attrs. With the MRO above, the chain is:

```
Board.__init__ → ExoSQLModel.__init__ → ExoModel.__init__ → SQLModel.__init__ → BaseModel.__init__
```

This chain works as-is as long as every `__init__` calls `super().__init__(**data)`. ExoModel already does. No override needed in ExoSQLModel unless we need to inject DB-specific setup after Pydantic validation.

### 2. Private Attributes

SQLModel's `__new__` already calls `init_pydantic_private_attrs()`, which initializes Pydantic `PrivateAttr` values. ExoModel's `_rag_sources`, `_exo_agent`, and `_llm_tools_cache` are `PrivateAttr` — they are handled automatically and do **not** become columns.

### 3. Reserved SQL Table Names

`column` is a SQL reserved word. We must set explicit table names:

```python
class Column(ExoSQLModel, table=True):
    __tablename__ = "columns"
```

Apply to all three models to be explicit and safe.

### 4. ExoModelList → SQLModel Relationship

`ExoModelList` cannot be used as a SQLModel relationship field. SQLModel relationship fields must be plain `list[Model]`. The AI list-manipulation methods currently on `ExoModelList` (e.g., `create_list`) must move to `@llm_function` methods on the parent model.

### 5. `_build_extraction_schema` Compatibility

ExoModel's schema builder already skips `ExoModel` and `ExoModelList` subclasses. The FK fields (`board_id`, `column_id`) are plain `Optional[int]` — they will be included in AI extractions, which is harmless (LLM will leave them as `None`).

---

## File Structure

```
exokanban/
  db/
    __init__.py
    engine.py        ← DatabaseManager: engine, session factory, init_db()
    base.py          ← ExoSQLModel base class + Active Record methods
  models/
    board.py         ← migrated to ExoSQLModel, table=True
    column.py        ← migrated to ExoSQLModel, table=True
    card.py          ← migrated to ExoSQLModel, table=True
```

---

## `db/engine.py` — DatabaseManager

Responsibilities:
- Creates the SQLite engine from `DATABASE_URL` env var (default: `sqlite:///exokanban.db`)
- Provides a `get_session()` context manager
- Exposes `init_db()` to create all tables (`SQLModel.metadata.create_all`)

```python
import os
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///exokanban.db")

# connect_args only needed for SQLite (enables WAL + thread safety)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

@contextmanager
def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)
```

**Why a module-level engine:** SQLite has no connection pool overhead; a single engine shared across the process is the standard SQLModel pattern. For PostgreSQL later, swap the URL and remove `connect_args`.

---

## `db/base.py` — ExoSQLModel

### Fields added

```python
from typing import Optional
from sqlmodel import Field

class ExoSQLModel(ExoModel, SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
```

`id` is `Optional[int]` so it can be `None` before the first `session.add()` and SQLite fills it on insert.

### Active Record methods

All methods accept an optional `session` parameter. If omitted, they open one automatically via `get_session()`. This keeps the API ergonomic for one-off calls while allowing callers to batch multiple operations in one transaction.

```python
def save(self, session=None) -> "ExoSQLModel":
    """INSERT or UPDATE depending on whether id is set."""

def delete(self, session=None) -> None:
    """DELETE this row from DB."""

@classmethod
def get_by_id(cls, id: int, session=None) -> Optional["ExoSQLModel"]:
    """SELECT by PK."""

@classmethod
def all(cls, session=None) -> list["ExoSQLModel"]:
    """SELECT * FROM table."""
```

### Override `create()`

ExoModel's `create()` populates fields via AI but does not persist. ExoSQLModel overrides it to call `save()` after:

```python
@classmethod
def create(cls, prompt: str, **initial_values) -> "ExoSQLModel":
    instance = super().create(prompt, **initial_values)
    instance.save()
    return instance
```

This preserves the same public API — callers still do `Board.create("...")` and get back a persisted instance.

---

## Relationship Design: Board → Column → Card

### FK fields and Relationships

```python
# board.py
class Board(ExoSQLModel, table=True):
    __tablename__ = "boards"

    name: str = ""
    description: str = ""
    context: str = ""
    archived: bool = False
    created_at: str = ""

    columns: list["Column"] = Relationship(back_populates="board")

# column.py
class Column(ExoSQLModel, table=True):
    __tablename__ = "columns"

    name: str = ""
    position: float = 0.0
    wip_limit: int = 0
    board_id: Optional[int] = Field(default=None, foreign_key="boards.id")

    board: Optional[Board] = Relationship(back_populates="columns")
    cards: list["Card"] = Relationship(back_populates="column")

# card.py
class Card(ExoSQLModel, table=True):
    __tablename__ = "cards"

    title: str = ""
    description: str = ""
    position: float = 0.0
    due_date: Optional[str] = None
    priority: str = "medium"
    archived: bool = False
    created_at: str = ""
    updated_at: str = ""
    column_id: Optional[int] = Field(default=None, foreign_key="columns.id")

    column: Optional[Column] = Relationship(back_populates="cards")
```

**Lazy loading note:** SQLModel relationships are lazy-loaded by default (SQLAlchemy `lazy="select"`). This means accessing `board.columns` inside a closed session will raise `DetachedInstanceError`. Solutions in order of preference:
1. Always access relationships within an open session.
2. Use `session.refresh(instance)` after reopening.
3. Use `selectinload` for eager loading in bulk queries.

---

## ExoModelList → `@llm_function` Migration

Methods currently on `ColumnList` and `CardList` move to the parent model as `@llm_function` methods.

| Old | New location |
|-----|-------------|
| `ColumnList.create_list(prompt)` | `Board.create_columns_from_prompt(prompt)` (already exists) — adapt to save each Column |
| `CardList.create_card(prompt)` | `Column.create_card_from_prompt(prompt)` (already exists) — adapt to save each Card |

The `@llm_function` wrappers already exist. They only need to call `column.save()` / `card.save()` after creating child objects, and append to the in-memory list so the relationship stays in sync within the session.

---

## CRUD Usage Examples

```python
# Create and persist (AI populates, then saves)
board = Board.create("Personal kanban for my side project")

# Fetch
with get_session() as session:
    board = Board.get_by_id(1, session)
    board.update("rename the board to 'Q3 Goals'")
    board.save(session)

# Delete
board.delete()

# List all
all_boards = Board.all()
```

---

## Implementation Steps (ordered)

1. **Create `db/engine.py`** with `DatabaseManager`, `get_session`, `init_db`.
2. **Create `db/base.py`** with `ExoSQLModel`: add `id` field, Active Record methods, override `create()`.
3. **Migrate `card.py`**: inherit from `ExoSQLModel`, add `column_id` FK, add `column` back-ref, set `__tablename__ = "cards"`.
4. **Migrate `column.py`**: inherit from `ExoSQLModel`, add `board_id` FK, replace `CardList` field with `Relationship`, set `__tablename__ = "columns"`. Adapt `create_card_from_prompt` to call `card.save()`.
5. **Migrate `board.py`**: inherit from `ExoSQLModel`, replace `ColumnList` field with `Relationship`, set `__tablename__ = "boards"`. Adapt `create_columns_from_prompt` and `create_card_from_prompt` to call `save()` on child objects.
6. **Wire `init_db()` in `main.py`**: call `init_db()` on startup after `load_dotenv()`.
7. **Update tests**: inject sessions where needed; test save/load roundtrip.

---

## What is NOT in scope (deferred)

- **Alembic migrations**: use `SQLModel.metadata.create_all()` for now. Add Alembic when schema changes need to be versioned.
- **Async sessions**: SQLModel supports `AsyncSession`; add when needed.
- **PostgreSQL**: change `DATABASE_URL` and drop `connect_args`. No other changes needed.
- **Soft delete**: `archived` field already exists on models; a filtered `all()` query can be added later.
- **`created_at` / `updated_at` as `datetime`**: currently `str`; a future migration can tighten the type.
