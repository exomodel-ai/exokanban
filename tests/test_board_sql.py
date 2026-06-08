from dotenv import load_dotenv
load_dotenv()

import pytest
from sqlmodel import create_engine, SQLModel, select

import db.engine as engine_module
from db.uow import UnitOfWork
from models.board import Board
from models.column import Column
from models.card import Card


# ---------------------------------------------------------------------------
# Fixture: isolated in-memory database per test
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine():
    """Creates a clean in-memory SQLite database for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    original = engine_module.engine
    engine_module.engine = test_engine

    SQLModel.metadata.create_all(test_engine)
    yield test_engine

    SQLModel.metadata.drop_all(test_engine)
    engine_module.engine = original


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def test_save_atribui_id(db_engine):
    """save() persists the object and fills the id."""
    with UnitOfWork() as uow:
        card = Card(title="Revisar PR de autenticação", priority="high").save()
        uow.commit()
        uow.refresh(card)

    assert card.id is not None
    assert card.id == 1


def test_save_multiplos_ids_unicos(db_engine):
    """Each save() generates a distinct id."""
    with UnitOfWork() as uow:
        c1 = Card(title="Tarefa A").save()
        c2 = Card(title="Tarefa B").save()
        c3 = Card(title="Tarefa C").save()
        uow.commit()
        uow.refresh(c1)
        uow.refresh(c2)
        uow.refresh(c3)

    assert c1.id != c2.id != c3.id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def test_get_by_id(db_engine):
    """get_by_id() returns the object with the saved fields."""
    with UnitOfWork() as uow:
        original = Card(title="Corrigir bug no login", priority="critical").save()
        uow.commit()
        uow.refresh(original)
        original_id = original.id

    with UnitOfWork() as uow:
        recuperado = Card.get_by_id(original_id)

    assert recuperado is not None
    assert recuperado.id == original_id
    assert recuperado.title == "Corrigir bug no login"
    assert recuperado.priority == "critical"


def test_get_by_id_nao_encontrado(db_engine):
    """get_by_id() returns None for a non-existent id."""
    with UnitOfWork() as uow:
        assert Card.get_by_id(9999) is None


def test_all(db_engine):
    """all() returns all records in the table."""
    with UnitOfWork() as uow:
        Card(title="Tarefa 1").save()
        Card(title="Tarefa 2").save()
        Card(title="Tarefa 3").save()
        uow.commit()

    with UnitOfWork() as uow:
        todos = Card.all()

    assert len(todos) == 3
    assert {c.title for c in todos} == {"Tarefa 1", "Tarefa 2", "Tarefa 3"}


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_via_campo(db_engine):
    """Changing a field and calling save() persists the change."""
    with UnitOfWork() as uow:
        card = Card(title="Tarefa inicial", priority="low").save()
        uow.commit()
        uow.refresh(card)
        card_id = card.id

    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
        card.priority = "critical"
        card.title = "Tarefa urgente"
        card.save()
        uow.commit()

    with UnitOfWork() as uow:
        recarregado = Card.get_by_id(card_id)

    assert recarregado.priority == "critical"
    assert recarregado.title == "Tarefa urgente"


def test_update_nao_cria_duplicata(db_engine):
    """save() on an already-persisted object performs UPDATE, not INSERT."""
    with UnitOfWork() as uow:
        card = Card(title="Original").save()
        uow.commit()
        uow.refresh(card)
        card_id = card.id

    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
        card.title = "Atualizado"
        card.save()
        uow.commit()

    with UnitOfWork() as uow:
        assert Card.get_by_id(card_id).title == "Atualizado"
        assert len(Card.all()) == 1


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete(db_engine):
    """delete() removes the record from the database."""
    with UnitOfWork() as uow:
        card = Card(title="Remover depois").save()
        uow.commit()
        uow.refresh(card)
        card_id = card.id

    with UnitOfWork() as uow:
        Card.get_by_id(card_id).delete()
        uow.commit()

    with UnitOfWork() as uow:
        assert Card.get_by_id(card_id) is None


def test_delete_nao_afeta_outros(db_engine):
    """delete() removes only the target object."""
    with UnitOfWork() as uow:
        c1 = Card(title="Manter").save()
        c2 = Card(title="Remover").save()
        uow.commit()
        uow.refresh(c1)
        uow.refresh(c2)
        c1_id, c2_id = c1.id, c2.id

    with UnitOfWork() as uow:
        Card.get_by_id(c2_id).delete()
        uow.commit()

    with UnitOfWork() as uow:
        assert Card.get_by_id(c1_id) is not None
        assert Card.get_by_id(c2_id) is None
        assert len(Card.all()) == 1


# ---------------------------------------------------------------------------
# Foreign key and relationship
# ---------------------------------------------------------------------------

def test_fk_board_column_card(db_engine):
    """Board → Column → Card with correct FKs."""
    with UnitOfWork() as uow:
        board = Board(name="Sprint 1").save()
        uow.flush()
        col = Column(name="To Do", board_id=board.id).save()
        uow.flush()
        card = Card(title="Implementar login", column_id=col.id).save()
        uow.commit()
        board_id, col_id, card_id = board.id, col.id, card.id

    with UnitOfWork() as uow:
        col_recarregada  = Column.get_by_id(col_id)
        card_recarregado = Card.get_by_id(card_id)

    assert col_recarregada.board_id == board_id
    assert card_recarregado.column_id == col_id


def test_relacionamento_acessivel_dentro_da_sessao(db_engine):
    """board.columns is accessible while the session is open."""
    with UnitOfWork() as uow:
        board = Board(name="Meu Board").save()
        uow.flush()
        Column(name="Inbox",       board_id=board.id).save()
        Column(name="In Progress", board_id=board.id).save()
        uow.commit()
        board_id = board.id

    with UnitOfWork() as uow:
        b = Board.get_by_id(board_id)
        nomes = [c.name for c in b.columns]

    assert set(nomes) == {"Inbox", "In Progress"}


# ---------------------------------------------------------------------------
# Atomic commit
# ---------------------------------------------------------------------------

def test_sessao_explicita_commit_atomico(db_engine):
    """Multiple saves in a single atomic transaction."""
    with UnitOfWork() as uow:
        board = Board(name="Board Compartilhado").save()
        uow.flush()
        col = Column(name="Backlog", board_id=board.id).save()
        uow.commit()
        board_id, col_id = board.id, col.id

    with UnitOfWork() as uow:
        board_db = Board.get_by_id(board_id)
        col_db   = Column.get_by_id(col_id)

    assert board_db.name == "Board Compartilhado"
    assert col_db.board_id == board_id


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def test_rollback_sem_commit(db_engine):
    """UoW closed with an exception reverts changes (flush ≠ commit)."""
    id_temporario = None

    with pytest.raises(ValueError):
        with UnitOfWork() as uow:
            card = Card(title="Tarefa temporária", priority="low")
            uow.session.add(card)
            uow.flush()
            id_temporario = card.id
            raise ValueError("Business rule violated — UoW closed without commit")

    assert id_temporario is not None
    with UnitOfWork() as uow:
        assert Card.get_by_id(id_temporario) is None


def test_rollback_wip_limit(db_engine):
    """Explicit rollback on WIP limit violation after flush."""

    class WipLimitExceeded(Exception):
        pass

    with UnitOfWork() as uow:
        col = Column(name="Em Progresso", wip_limit=2).save()
        uow.flush()
        col_id = col.id
        Card(title="Tarefa 1", column_id=col_id).save()
        Card(title="Tarefa 2", column_id=col_id).save()
        uow.commit()
        wip_limit = col.wip_limit
        col_name  = col.name

    id_temporario = None

    with pytest.raises(WipLimitExceeded):
        with UnitOfWork() as uow:
            card3 = Card(title="Tarefa 3", column_id=col_id)
            uow.session.add(card3)
            uow.flush()
            id_temporario = card3.id

            ocupacao = uow.session.exec(
                select(Card).where(Card.column_id == col_id)
            ).all()
            if wip_limit > 0 and len(ocupacao) > wip_limit:
                uow.rollback()
                raise WipLimitExceeded(
                    f"Column '{col_name}' reached its WIP limit of {wip_limit}."
                )

    assert id_temporario is not None
    with UnitOfWork() as uow:
        assert Card.get_by_id(id_temporario) is None
        cards_na_coluna = uow.session.exec(
            select(Card).where(Card.column_id == col_id)
        ).all()
    assert len(cards_na_coluna) == 2


# ---------------------------------------------------------------------------
# AI integration (calls LLM)
# ---------------------------------------------------------------------------

def test_create_via_ia(db_engine):
    """Board.create() populates fields via AI and persists after explicit commit."""
    with UnitOfWork() as uow:
        board = Board.create("Kanban de lançamento do produto v2.0, time de 4 pessoas")
        uow.commit()
        uow.refresh(board)
        board_id = board.id

    assert board_id is not None
    assert board.name != ""
    assert board.description != ""

    with UnitOfWork() as uow:
        recarregado = Board.get_by_id(board_id)
    assert recarregado.name == board.name
    print(f"\nname: {board.name}")
    print(f"description: {board.description}")
