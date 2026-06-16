from dotenv import load_dotenv
load_dotenv()

import asyncio
import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace
from sqlmodel import create_engine, SQLModel

import db.engine as engine_module
from db.uow import UnitOfWork
from models.board import Board
from models.column import Column
from models.card import Card
from kanban_service import KanbanService
from main import KanbanInteraction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine():
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


@pytest.fixture
def board_6cols(db_engine):
    """Board com 6 colunas: 4 ativas + Feito + Antigos (NUM_ACTIVE_COLUMNS=4)."""
    with UnitOfWork() as uow:
        board = Board(name="Test Board").save()
        uow.flush()
        board_id = board.id
        for i, name in enumerate(["Inbox", "Prioridade", "Nesta Semana", "Hoje", "Feito", "Antigos"]):
            Column(name=name, board_id=board_id, position=float(i)).save()
        uow.commit()
    return board_id


@pytest.fixture
def service(board_6cols):
    return KanbanService(board_6cols)


@pytest.fixture
def interaction(board_6cols):
    ki = KanbanInteraction()
    ki.board = SimpleNamespace(id=board_6cols)
    ki._service = KanbanService(board_6cols)
    ki._current_card_id = None
    return ki


def _inbox_id(board_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_id)
        return sorted(board.columns, key=lambda c: c.position)[0].id


def _col_id(board_id, index):
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_id)
        return sorted(board.columns, key=lambda c: c.position)[index].id


# ---------------------------------------------------------------------------
# Card — is_overdue
# ---------------------------------------------------------------------------

def test_is_overdue_true():
    card = Card(title="X", due_date=datetime.now() - timedelta(days=1))
    assert card.is_overdue() is True


def test_is_overdue_false_futura():
    card = Card(title="X", due_date=datetime.now() + timedelta(days=1))
    assert card.is_overdue() is False


def test_is_overdue_false_sem_prazo():
    assert Card(title="X").is_overdue() is False


# ---------------------------------------------------------------------------
# Card — is_due_within
# ---------------------------------------------------------------------------

def test_is_due_within_true():
    card = Card(title="X", due_date=datetime.now() + timedelta(days=5))
    assert card.is_due_within(7) is True


def test_is_due_within_hoje():
    card = Card(title="X", due_date=datetime.now())
    assert card.is_due_within(7) is True


def test_is_due_within_false_alem():
    card = Card(title="X", due_date=datetime.now() + timedelta(days=10))
    assert card.is_due_within(7) is False


def test_is_due_within_false_vencida():
    card = Card(title="X", due_date=datetime.now() - timedelta(days=1))
    assert card.is_due_within(7) is False


def test_is_due_within_false_sem_prazo():
    assert Card(title="X").is_due_within(7) is False


# ---------------------------------------------------------------------------
# Card — is_stale
# ---------------------------------------------------------------------------

def test_is_stale_true():
    card = Card(title="X", updated_at=datetime.now() - timedelta(days=10))
    assert card.is_stale(7) is True


def test_is_stale_false():
    card = Card(title="X", updated_at=datetime.now() - timedelta(days=3))
    assert card.is_stale(7) is False


def test_is_stale_no_limite():
    card = Card(title="X", updated_at=datetime.now() - timedelta(days=7, seconds=1))
    assert card.is_stale(7) is True


# ---------------------------------------------------------------------------
# Card — lead_time_days
# ---------------------------------------------------------------------------

def test_lead_time_positivo():
    card = Card(
        title="X",
        created_at=datetime.now() - timedelta(days=5),
        updated_at=datetime.now(),
    )
    lt = card.lead_time_days()
    assert lt is not None
    assert 4.9 < lt < 5.1


def test_lead_time_none_quando_igual():
    now = datetime.now()
    card = Card(title="X", created_at=now, updated_at=now)
    assert card.lead_time_days() is None


# ---------------------------------------------------------------------------
# Column — active_count
# ---------------------------------------------------------------------------

def test_active_count(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C").save()
        uow.flush()
        Card(title="A", column_id=col.id).save()
        Card(title="B", column_id=col.id).save()
        Card(title="Arq", column_id=col.id, archived=True).save()
        uow.commit()
        assert col.active_count() == 2


def test_active_count_vazio(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C").save()
        uow.commit()
        assert col.active_count() == 0


# ---------------------------------------------------------------------------
# Column — wip_status
# ---------------------------------------------------------------------------

def test_wip_status_no_limit(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C", wip_limit=0).save()
        uow.commit()
        assert col.wip_status() == "NO_LIMIT"


def test_wip_status_ok(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C", wip_limit=3).save()
        uow.flush()
        Card(title="A", column_id=col.id).save()
        uow.commit()
        assert col.wip_status() == "OK"


def test_wip_status_at_limit(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C", wip_limit=2).save()
        uow.flush()
        Card(title="A", column_id=col.id).save()
        Card(title="B", column_id=col.id).save()
        uow.commit()
        assert col.wip_status() == "AT_LIMIT"


def test_wip_status_exceeded(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C", wip_limit=1).save()
        uow.flush()
        Card(title="A", column_id=col.id).save()
        Card(title="B", column_id=col.id).save()
        uow.commit()
        assert col.wip_status() == "EXCEEDED"


# ---------------------------------------------------------------------------
# Column — stale_cards
# ---------------------------------------------------------------------------

def test_stale_cards_retorna_apenas_antigos(db_engine):
    old    = datetime.now() - timedelta(days=10)
    recent = datetime.now() - timedelta(days=2)
    with UnitOfWork() as uow:
        col = Column(name="C").save()
        uow.flush()
        Card(title="Antiga",    column_id=col.id, updated_at=old).save()
        Card(title="Recente",   column_id=col.id, updated_at=recent).save()
        Card(title="Arquivada", column_id=col.id, updated_at=old, archived=True).save()
        uow.commit()
        stale = col.stale_cards(7)
    assert len(stale) == 1
    assert stale[0].title == "Antiga"


def test_stale_cards_vazio(db_engine):
    with UnitOfWork() as uow:
        col = Column(name="C").save()
        uow.flush()
        Card(title="Recente", column_id=col.id).save()
        uow.commit()
        assert col.stale_cards(7) == []


# ---------------------------------------------------------------------------
# Board — active_columns / done_column / archive_column
# ---------------------------------------------------------------------------

def test_active_columns_retorna_primeiras_n(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        cols = board.active_columns()
    assert len(cols) == 4
    names = {c.name for c in cols}
    assert names == {"Inbox", "Prioridade", "Nesta Semana", "Hoje"}


def test_active_columns_exclui_feito_e_antigos(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        names = {c.name for c in board.active_columns()}
    assert "Feito" not in names
    assert "Antigos" not in names


def test_active_columns_respeita_env_var(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "2")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        cols = board.active_columns()
    assert len(cols) == 2
    assert {c.name for c in cols} == {"Inbox", "Prioridade"}


def test_done_column_retorna_feito(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        assert board.done_column().name == "Feito"


def test_done_column_respeita_env_var(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "2")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        assert board.done_column().name == "Nesta Semana"


def test_archive_column_retorna_antigos(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        assert board.archive_column().name == "Antigos"


def test_done_column_none_sem_colunas_suficientes(db_engine):
    with UnitOfWork() as uow:
        board = Board(name="Mini").save()
        uow.flush()
        Column(name="Única", board_id=board.id, position=0.0).save()
        uow.commit()
        board_id = board.id
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_id)
        assert board.done_column() is None


# ---------------------------------------------------------------------------
# analyze_board — saída e métricas
# ---------------------------------------------------------------------------

def test_analyze_contem_todas_secoes(db_engine, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    result = service.analyze_board()
    for section in ["Colunas", "Prazo", "Prioridade", "Envelhecimento", "Tags", "Board geral", "Lead time"]:
        assert section in result


def test_analyze_total_ativo_exclui_feito_e_antigos(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        cols = sorted(board.columns, key=lambda c: c.position)
        Card(title="Ativo 1",    column_id=cols[0].id).save()
        Card(title="Ativo 2",    column_id=cols[1].id).save()
        Card(title="No Feito",   column_id=cols[4].id).save()
        Card(title="No Antigos", column_id=cols[5].id).save()
        uow.commit()
    result = KanbanService(board_6cols).analyze_board()
    assert "Total ativo: 2" in result


def test_analyze_overdue(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="Vencida", column_id=col_id, due_date=datetime.now() - timedelta(days=3)).save()
        uow.commit()
    assert "Vencidos: 1" in service.analyze_board()


def test_analyze_overdue_em_feito_nao_conta(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        feito_id = _col_id(board_6cols, 4)
        Card(title="Vencida no Feito", column_id=feito_id, due_date=datetime.now() - timedelta(days=1)).save()
        uow.commit()
    result = KanbanService(board_6cols).analyze_board()
    assert "Vencidos: 0" in result


def test_analyze_high_critical_sem_prazo(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="H", column_id=col_id, priority="high").save()
        Card(title="C", column_id=col_id, priority="critical").save()
        Card(title="M", column_id=col_id, priority="medium").save()
        uow.commit()
    assert "High/critical sem prazo: 2" in service.analyze_board()


def test_analyze_prioridade_distribuicao(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="C", column_id=col_id, priority="critical").save()
        Card(title="H", column_id=col_id, priority="high").save()
        Card(title="M", column_id=col_id, priority="medium").save()
        uow.commit()
    result = service.analyze_board()
    assert "critical: 1" in result
    assert "high: 1" in result
    assert "medium: 1" in result


def test_analyze_fire_fighting(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="C",  column_id=col_id, priority="critical").save()
        Card(title="M1", column_id=col_id, priority="medium").save()
        Card(title="M2", column_id=col_id, priority="medium").save()
        Card(title="M3", column_id=col_id, priority="medium").save()
        uow.commit()
    assert "Fire-fighting: 25%" in service.analyze_board()


def test_analyze_estagnados_7d(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="Antiga",  column_id=col_id, updated_at=datetime.now() - timedelta(days=10)).save()
        Card(title="Recente", column_id=col_id).save()
        uow.commit()
    assert "Estagnados >7d: 1" in service.analyze_board()


def test_analyze_estagnados_nao_conta_feito(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        feito_id = _col_id(board_6cols, 4)
        Card(title="Antiga no Feito", column_id=feito_id, updated_at=datetime.now() - timedelta(days=10)).save()
        uow.commit()
    assert "Estagnados >7d: 0" in KanbanService(board_6cols).analyze_board()


def test_analyze_tag_distribuicao(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="C1", column_id=col_id, tag="comercial").save()
        Card(title="C2", column_id=col_id, tag="comercial").save()
        Card(title="T1", column_id=col_id, tag="tecnologia").save()
        uow.commit()
    result = service.analyze_board()
    assert "comercial: 2" in result
    assert "tecnologia: 1" in result


def test_analyze_sem_tag(db_engine, board_6cols, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        col_id = _inbox_id(board_6cols)
        Card(title="Sem tag", column_id=col_id).save()
        uow.commit()
    assert "Sem tag: 1" in service.analyze_board()


def test_analyze_wip_exceeded(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        board = Board.get_by_id(board_6cols)
        col = sorted(board.columns, key=lambda c: c.position)[0]
        col.wip_limit = 1
        col.save()
        uow.flush()
        Card(title="C1", column_id=col.id).save()
        Card(title="C2", column_id=col.id).save()
        uow.commit()
    assert "EXCEEDED" in KanbanService(board_6cols).analyze_board()


def test_analyze_lead_time_com_dados(db_engine, board_6cols, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    with UnitOfWork() as uow:
        feito_id = _col_id(board_6cols, 4)
        Card(
            title="Concluída",
            column_id=feito_id,
            created_at=datetime.now() - timedelta(days=5),
            updated_at=datetime.now(),
        ).save()
        uow.commit()
    result = KanbanService(board_6cols).analyze_board()
    assert "Médio" in result
    assert "Sem dados" not in result


def test_analyze_lead_time_sem_dados(db_engine, service, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    assert "Sem dados" in service.analyze_board()


# ---------------------------------------------------------------------------
# analyze_board — command routing
# ---------------------------------------------------------------------------

def test_analyze_command_routing(db_engine, interaction, monkeypatch):
    monkeypatch.setenv("NUM_ACTIVE_COLUMNS", "4")
    result = asyncio.run(interaction.process_prompt("user", "/stats"))
    assert "Colunas" in result
    assert "Lead time" in result
