from dotenv import load_dotenv
load_dotenv()

import pytest
from unittest.mock import patch
from types import SimpleNamespace
from sqlmodel import create_engine, SQLModel

import db.engine as engine_module
from db.uow import UnitOfWork
from models.board import Board
from models.column import Column
from models.card import Card
from main import KanbanInteraction
from kanban_service import KanbanService


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
def interaction(db_engine):
    with UnitOfWork() as uow:
        board = Board(name="Test Board").save()
        uow.flush()
        board_id = board.id
        Column(name="Inbox", board_id=board_id, position=0.0).save()
        Column(name="Feito", board_id=board_id, position=1.0).save()
        uow.commit()

    ki = KanbanInteraction()
    ki.board = SimpleNamespace(id=board_id)
    ki._service = KanbanService(board_id)
    ki._current_card_id = None
    return ki


@pytest.fixture
def card_id(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col = board.columns[0]
        card = Card(title="Tarefa Teste", description="Descrição", priority="high", column_id=col.id).save()
        uow.commit()
        uow.refresh(card)
        return card.id


# ---------------------------------------------------------------------------
# show_cards
# ---------------------------------------------------------------------------

def test_show_cards_vazio(interaction):
    assert interaction.show_cards([]) == "No cards found."


def test_show_cards_retorna_ui_de_cada_card(db_engine, interaction, card_id):
    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
        result = interaction.show_cards([card])
    assert "Tarefa Teste" in result


# ---------------------------------------------------------------------------
# get_current_card
# ---------------------------------------------------------------------------

def test_get_current_card_sem_selecao(interaction):
    assert interaction.get_current_card() == "No card selected."


def test_get_current_card_com_selecao(interaction, card_id):
    interaction._current_card_id = card_id
    result = interaction.get_current_card()
    assert "Tarefa Teste" in result


# ---------------------------------------------------------------------------
# get_card_by_id
# ---------------------------------------------------------------------------

def test_get_card_by_id_nao_encontrado(interaction):
    result = interaction.get_card_by_id(9999)
    assert "9999" in result
    assert "not found" in result
    assert interaction._current_card_id is None


def test_get_card_by_id_encontrado(interaction, card_id):
    result = interaction.get_card_by_id(card_id)
    assert "Tarefa Teste" in result
    assert interaction._current_card_id == card_id


# ---------------------------------------------------------------------------
# archive_current_card
# ---------------------------------------------------------------------------

def test_archive_current_card_sem_selecao(interaction):
    result = interaction.archive_current_card()
    assert "No card selected" in result


def test_archive_current_card_delega_para_archive_by_id(interaction, card_id):
    interaction._current_card_id = card_id
    result = interaction.archive_current_card()
    assert "archived" in result


# ---------------------------------------------------------------------------
# archive_card_by_id
# ---------------------------------------------------------------------------

def test_archive_card_by_id_nao_encontrado(interaction):
    result = interaction.archive_card_by_id(9999)
    assert "9999" in result
    assert "not found" in result


def test_archive_card_by_id_marca_archived(interaction, card_id):
    interaction.archive_card_by_id(card_id)
    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
    assert card.archived is True


def test_archive_card_by_id_retorna_confirmacao(interaction, card_id):
    result = interaction.archive_card_by_id(card_id)
    assert "Tarefa Teste" in result
    assert "archived" in result


def test_archive_card_by_id_limpa_current_card_id_se_for_o_atual(interaction, card_id):
    interaction._current_card_id = card_id
    interaction.archive_card_by_id(card_id)
    assert interaction._current_card_id is None


def test_archive_card_by_id_nao_limpa_current_card_id_de_outro_card(db_engine, interaction, card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col = board.columns[0]
        outro = Card(title="Outro Card", column_id=col.id).save()
        uow.commit()
        uow.refresh(outro)
        outro_id = outro.id

    interaction._current_card_id = card_id
    interaction.archive_card_by_id(outro_id)
    assert interaction._current_card_id == card_id


# ---------------------------------------------------------------------------
# Archived cards excluded from listings
# ---------------------------------------------------------------------------

def test_get_cards_exclui_arquivados(db_engine, interaction, card_id):
    interaction.archive_card_by_id(card_id)
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        all_cards = [c for col in board.columns for c in col.get_cards()]
    assert all(not c.archived for c in all_cards)
    assert not any(c.id == card_id for c in all_cards)


# ---------------------------------------------------------------------------
# update_current_card (guards — no LLM call)
# ---------------------------------------------------------------------------

def test_update_current_card_sem_selecao(interaction):
    result = interaction.update_current_card("qualquer prompt")
    assert "No card selected" in result


def test_update_current_card_sem_prompt(interaction, card_id):
    interaction._current_card_id = card_id
    result = interaction.update_current_card("")
    assert "describe what to update" in result


# ---------------------------------------------------------------------------
# move_current_card (guards without LLM + real move with mock)
# ---------------------------------------------------------------------------

def test_move_current_card_sem_selecao(interaction):
    result = interaction.move_current_card("Feito")
    assert "No card selected" in result


def test_move_current_card_sem_prompt_move_para_proxima_coluna(db_engine, interaction, card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        cols = sorted(board.columns, key=lambda c: c.position)
        source_col_id = cols[0].id
        next_col_id   = cols[1].id
        next_col_name = cols[1].name

    interaction._current_card_id = card_id
    result = interaction.move_current_card("")

    assert next_col_name in result
    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
    assert card.column_id == next_col_id


def test_move_current_card_ultima_coluna_retorna_erro(db_engine, interaction, card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        last_col_id = sorted(board.columns, key=lambda c: c.position)[-1].id
        card = Card.get_by_id(card_id)
        card.column_id = last_col_id
        card.save()
        uow.commit()

    interaction._current_card_id = card_id
    result = interaction.move_current_card("")
    assert "last column" in result


def test_move_current_card_muda_coluna(db_engine, interaction, card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_destino = sorted(board.columns, key=lambda c: c.position)[1]
        col_destino_id = col_destino.id
        col_destino_name = col_destino.name

    interaction._current_card_id = card_id

    def mock_get_column(self, prompt, strict=False):
        return Column.get_by_id(col_destino_id)

    with patch.object(Board, "get_column_from_prompt", mock_get_column):
        result = interaction.move_current_card("feito")

    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
    assert card.column_id == col_destino_id
    assert col_destino_name in result


# ---------------------------------------------------------------------------
# create_card
# ---------------------------------------------------------------------------

def _mock_create_card(board_self, prompt):
    """Mock de Board.create_card_from_prompt: cria um card real sem LLM."""
    col = sorted(board_self.columns, key=lambda c: c.position)[0]
    card = Card(title="Tarefa Criada", column_id=col.id)
    return card.save()


def test_create_card_prompt_vazio(interaction):
    result = interaction.create_card("")
    assert "Please describe" in result


def test_create_card_persiste_e_seleciona(db_engine, interaction):
    with patch.object(Board, "create_card_from_prompt", _mock_create_card):
        result = interaction.create_card("nova tarefa de teste")

    assert "Tarefa Criada" in result
    assert interaction._current_card_id is not None
    with UnitOfWork() as uow:
        card = Card.get_by_id(interaction._current_card_id)
    assert card.title == "Tarefa Criada"


def test_new_command_routing(db_engine, interaction):
    with patch.object(Board, "create_card_from_prompt", _mock_create_card):
        result = asyncio.run(interaction.process_prompt("user", "/new tarefa via comando"))
    assert "Tarefa Criada" in result


def test_n_prefix_routing(db_engine, interaction):
    with patch.object(Board, "create_card_from_prompt", _mock_create_card):
        result = asyncio.run(interaction.process_prompt("user", "n tarefa via prefixo n"))
    assert "Tarefa Criada" in result


# ---------------------------------------------------------------------------
# show_board
# ---------------------------------------------------------------------------

def test_show_board_contem_colunas(db_engine, interaction):
    result = interaction.show_board()
    assert "Inbox" in result
    assert "Feito" in result


def test_board_command_routing(db_engine, interaction):
    result = asyncio.run(interaction.process_prompt("user", "/board"))
    assert "Inbox" in result


# ---------------------------------------------------------------------------
# /cards
# ---------------------------------------------------------------------------

def test_cards_sem_hint_exibe_todas_as_colunas(db_engine, interaction):
    result = asyncio.run(interaction.process_prompt("user", "/cards"))
    assert "Inbox" in result
    assert "Feito" in result


def test_cards_com_id_exibe_coluna(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = sorted(board.columns, key=lambda c: c.position)[0].id

    result = asyncio.run(interaction.process_prompt("user", f"/cards {col_id}"))
    assert "Inbox" in result


def test_cards_com_texto_exibe_coluna(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = sorted(board.columns, key=lambda c: c.position)[0].id

    def mock_col(self, prompt, strict=False):
        return Column.get_by_id(col_id)

    with patch.object(Board, "get_column_from_prompt", mock_col):
        result = asyncio.run(interaction.process_prompt("user", "/cards inbox"))
    assert "Inbox" in result


# ---------------------------------------------------------------------------
# get_card_from_prompt
# ---------------------------------------------------------------------------

def test_get_card_from_prompt_nao_encontrado(db_engine, interaction):
    with patch.object(Board, "get_card_from_prompt", lambda self, p: None):
        result = interaction.get_card_from_prompt("tarefa inexistente")
    assert "No card found" in result
    assert interaction._current_card_id is None


def test_get_card_from_prompt_encontrado(db_engine, interaction, card_id):
    def mock_find(self, prompt):
        return Card.get_by_id(card_id)

    with patch.object(Board, "get_card_from_prompt", mock_find):
        result = interaction.get_card_from_prompt("tarefa teste")

    assert "Tarefa Teste" in result
    assert interaction._current_card_id == card_id


def test_card_prompt_routing(db_engine, interaction, card_id):
    def mock_find(self, prompt):
        return Card.get_by_id(card_id)

    with patch.object(Board, "get_card_from_prompt", mock_find):
        result = asyncio.run(interaction.process_prompt("user", "/card revisar proposta"))

    assert "Tarefa Teste" in result


# ---------------------------------------------------------------------------
# update_current_card — happy path
# ---------------------------------------------------------------------------

def test_update_current_card_persiste_e_retorna_ui(db_engine, interaction, card_id):
    interaction._current_card_id = card_id

    def mock_update(self, prompt):
        self.title = "Título Atualizado"
        return {"title": "Título Atualizado"}

    with patch.object(Card, "update_object", mock_update):
        result = interaction.update_current_card("mude o título")

    assert "Título Atualizado" in result
    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
    assert card.title == "Título Atualizado"


# ---------------------------------------------------------------------------
# export_to_csv
# ---------------------------------------------------------------------------

def test_export_cria_arquivos(db_engine, interaction, card_id, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = interaction.export_to_csv()
    assert "✅" in result
    assert (tmp_path / "board.csv").exists()
    assert (tmp_path / "column.csv").exists()
    assert (tmp_path / "card.csv").exists()


def test_export_board_csv_contem_dados(db_engine, interaction, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    interaction.export_to_csv()
    content = (tmp_path / "board.csv").read_text(encoding="utf-8")
    assert "id" in content          # header
    assert "Test Board" in content  # dado do fixture


def test_export_column_csv_contem_colunas(db_engine, interaction, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    interaction.export_to_csv()
    content = (tmp_path / "column.csv").read_text(encoding="utf-8")
    assert "Inbox" in content
    assert "Feito" in content


def test_export_card_csv_contem_cards(db_engine, interaction, card_id, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    interaction.export_to_csv()
    content = (tmp_path / "card.csv").read_text(encoding="utf-8")
    assert "Tarefa Teste" in content


def test_export_sobrescreve_arquivo_existente(db_engine, interaction, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "board.csv").write_text("conteudo antigo", encoding="utf-8")
    interaction.export_to_csv()
    content = (tmp_path / "board.csv").read_text(encoding="utf-8")
    assert "conteudo antigo" not in content
    assert "id" in content


def test_export_command_routing(db_engine, interaction, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = asyncio.run(interaction.process_prompt("user", "/export"))
    assert "✅" in result
    assert (tmp_path / "card.csv").exists()


# ---------------------------------------------------------------------------
# show_due_cards
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta as td


def _card_with_due(col_id, title, days_offset):
    """Cria e salva um card com due_date relativa a hoje."""
    due = datetime.now() + td(days=days_offset)
    card = Card(title=title, column_id=col_id, due_date=due)
    return card.save()


def test_due_sem_cards_com_prazo(db_engine, interaction):
    result = interaction.show_due_cards()
    assert "No cards with a due date" in result


def test_due_card_atrasado(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id
        _card_with_due(col_id, "Tarefa Atrasada", -3)
        uow.commit()

    result = interaction.show_due_cards()
    assert "🔴" in result
    assert "Tarefa Atrasada" in result
    assert "overdue by 3 day(s)" in result


def test_due_card_vence_hoje(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id
        _card_with_due(col_id, "Tarefa Hoje", 0)
        uow.commit()

    result = interaction.show_due_cards()
    assert "🟡" in result
    assert "Tarefa Hoje" in result
    assert "due today" in result


def test_due_card_proxima_semana(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id
        _card_with_due(col_id, "Tarefa Futura", 5)
        uow.commit()

    result = interaction.show_due_cards()
    assert "🟢" in result
    assert "Tarefa Futura" in result
    assert "in 5 day(s)" in result


def test_due_nao_inclui_cards_sem_prazo(db_engine, interaction, card_id):
    result = interaction.show_due_cards()
    assert "Tarefa Teste" not in result


def test_due_nao_inclui_cards_em_colunas_concluidas(db_engine):
    """Cards in the last two columns (done + archive) must not appear in /due.
    Requires a board with > 2 columns so the [:-2] guard activates."""
    past = datetime.now() - td(days=1)
    with UnitOfWork() as uow:
        board = Board(name="Board 4 cols").save()
        uow.flush()
        board_id = board.id
        for i, name in enumerate(["Inbox", "Today", "Done", "Archive"]):
            Column(name=name, board_id=board_id, position=float(i)).save()
        uow.commit()

    with UnitOfWork() as uow:
        board = Board.get_by_id(board_id)
        cols = sorted(board.columns, key=lambda c: c.position)
        Card(title="Active Overdue",  column_id=cols[0].id, due_date=past).save()
        Card(title="Done Overdue",    column_id=cols[2].id, due_date=past).save()
        Card(title="Archive Overdue", column_id=cols[3].id, due_date=past).save()
        uow.commit()

    ki = KanbanInteraction()
    ki.board = SimpleNamespace(id=board_id)
    ki._service = KanbanService(board_id)
    ki._current_card_id = None

    result = ki.show_due_cards()
    assert "Active Overdue"  in result
    assert "Done Overdue"    not in result
    assert "Archive Overdue" not in result


def test_due_nao_inclui_arquivados(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id
        due = datetime.now() - td(days=1)
        card = Card(title="Arquivada Atrasada", column_id=col_id, due_date=due, archived=True)
        card.save()
        uow.commit()

    result = interaction.show_due_cards()
    assert "Arquivada Atrasada" not in result


def test_due_command_routing(db_engine, interaction):
    result = asyncio.run(interaction.process_prompt("user", "/due"))
    assert "No cards with a due date" in result


# ---------------------------------------------------------------------------
# error handling in process_prompt
# ---------------------------------------------------------------------------

import asyncio

def test_process_prompt_retorna_mensagem_amigavel_em_erro(db_engine, interaction):
    """Any exception in a handler returns ❌ + error description and does not propagate."""
    with patch.object(interaction._service, "show_board", side_effect=RuntimeError("falha simulada")):
        result = asyncio.run(interaction.process_prompt("user1", "/board"))
    assert "❌" in result
    assert "falha simulada" in result


# ---------------------------------------------------------------------------
# move_old_cards
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta


@pytest.fixture
def old_card_id(db_engine, interaction):
    """Card with updated_at 31 days ago in the second-to-last column (source)."""
    past = datetime.now() - timedelta(days=31)
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        source_col = sorted(board.columns, key=lambda c: c.position)[-2]
        card = Card(title="Card Antigo", column_id=source_col.id, updated_at=past).save()
        uow.commit()
        uow.refresh(card)
        return card.id


def test_move_old_cards_board_com_menos_de_2_colunas(db_engine):
    with UnitOfWork() as uow:
        board = Board(name="Board Minimal").save()
        uow.flush()
        board_id = board.id
        Column(name="Única", board_id=board_id, position=0.0).save()
        uow.commit()
    ki = KanbanInteraction()
    ki.board = SimpleNamespace(id=board_id)
    result = ki.move_old_cards()
    assert "at least 2 columns" in result


def test_move_old_cards_sem_cards_antigos(db_engine, interaction, card_id):
    result = interaction.move_old_cards()
    assert "No cards older" in result


def test_move_old_cards_move_para_ultima_coluna(db_engine, interaction, old_card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        dest_id = sorted(board.columns, key=lambda c: c.position)[-1].id

    result = interaction.move_old_cards()

    with UnitOfWork() as uow:
        card = Card.get_by_id(old_card_id)
    assert card.column_id == dest_id
    assert "Card Antigo" in result


def test_move_old_cards_nao_move_cards_recentes(db_engine, interaction, old_card_id, card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        source_col_id = sorted(board.columns, key=lambda c: c.position)[-2].id

    interaction.move_old_cards()

    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
    assert card.column_id == source_col_id


def test_move_old_cards_nao_move_arquivados(db_engine, interaction):
    past = datetime.now() - timedelta(days=31)
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        source_col_id = sorted(board.columns, key=lambda c: c.position)[-2].id
        card = Card(
            title="Arquivado Antigo", column_id=source_col_id,
            updated_at=past, archived=True
        ).save()
        uow.commit()
        uow.refresh(card)
        card_id = card.id

    result = interaction.move_old_cards()

    assert "No cards older" in result
    with UnitOfWork() as uow:
        card = Card.get_by_id(card_id)
    assert card.column_id == source_col_id


# ---------------------------------------------------------------------------
# get_column
# ---------------------------------------------------------------------------

def test_get_column_nao_encontrado(interaction):
    result = interaction.get_column(9999)
    assert "9999" in result
    assert "not found" in result


def test_get_column_retorna_ui(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id

    result = interaction.get_column(col_id)
    assert "Inbox" in result


def test_column_command_sem_id_numerico(db_engine, interaction):
    result = asyncio.run(interaction.process_prompt("user", "/column abc"))
    assert "Usage" in result


def test_column_command_routing(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id

    result = asyncio.run(interaction.process_prompt("user", f"/column {col_id}"))
    assert "Inbox" in result


# ---------------------------------------------------------------------------
# update_column
# ---------------------------------------------------------------------------

def test_update_column_nao_encontrado(interaction):
    result = interaction.update_column(9999, "rename to Foo")
    assert "9999" in result
    assert "not found" in result


def test_updcolumn_command_sem_id_numerico(db_engine, interaction):
    result = asyncio.run(interaction.process_prompt("user", "/updcolumn abc rename"))
    assert "Usage" in result


def test_updcolumn_command_sem_prompt(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id

    result = asyncio.run(interaction.process_prompt("user", f"/updcolumn {col_id}"))
    assert "Usage" in result


def test_update_column_persiste_e_retorna_ui(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id

    def mock_update(self, prompt):
        self.name = "Em Andamento"
        return {"name": "Em Andamento"}

    with patch.object(Column, "update_object", mock_update):
        result = interaction.update_column(col_id, "rename to Em Andamento")

    assert "Em Andamento" in result
    with UnitOfWork() as uow:
        col = Column.get_by_id(col_id)
    assert col.name == "Em Andamento"


def test_updcolumn_command_routing(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col_id = board.columns[0].id

    def mock_update(self, prompt):
        self.name = "Revisão"
        return {"name": "Revisão"}

    with patch.object(Column, "update_object", mock_update):
        result = asyncio.run(
            interaction.process_prompt("user", f"/updcolumn {col_id} rename to Revisão")
        )

    assert "Revisão" in result


# ---------------------------------------------------------------------------
# show_column_cards — título com contagem e WIP
# ---------------------------------------------------------------------------

def test_show_column_cards_titulo_sem_wip(db_engine, interaction, card_id):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col = board.columns[0]
        col_id = col.id
        result = col.show_column_cards()

    assert f"#{col_id}" in result
    assert "Inbox" in result
    assert "(1)" in result
    assert "🚨" not in result


def test_show_column_cards_titulo_sem_cards(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col = board.columns[0]
        col_id = col.id
        result = col.show_column_cards()

    assert f"#{col_id}" in result
    assert "(0)" in result


def test_show_column_cards_wip_nao_ultrapassado(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col = board.columns[0]
        col.wip_limit = 3
        col.save()
        Card(title="C1", column_id=col.id).save()
        Card(title="C2", column_id=col.id).save()
        uow.commit()
        col_id = col.id

    with UnitOfWork() as uow:
        col = Column.get_by_id(col_id)
        result = col.show_column_cards()

    assert "(2/3)" in result
    assert "🚨" not in result


def test_show_column_cards_wip_ultrapassado(db_engine, interaction):
    with UnitOfWork() as uow:
        board = Board.get_by_id(interaction.board.id)
        col = board.columns[0]
        col.wip_limit = 1
        col.save()
        Card(title="C1", column_id=col.id).save()
        Card(title="C2", column_id=col.id).save()
        uow.commit()
        col_id = col.id

    with UnitOfWork() as uow:
        col = Column.get_by_id(col_id)
        result = col.show_column_cards()

    assert "(2/1)" in result
    assert "🚨" in result
