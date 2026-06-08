from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import pytest
from models.board import Board
from models.column import Column
from models.card import Card


COLUMN_NAMES = ["Inbox", "Próximas Prioridades", "Hoje", "Realizado", "Arquivo"]


@pytest.fixture
def board_todo():
    """Personal and professional to-do board with pre-defined columns. No LLM calls."""
    board = Board(
        name="To-Do Pessoal e Profissional",
        description="Gerenciamento de tarefas diárias de trabalho e pessoais.",
        context=(
            "Kanban pessoal para organização do dia a dia. "
            "Tarefas de trabalho e pessoais convivem no mesmo board. "
            "O foco é clareza sobre o que fazer hoje e o que vem a seguir."
        ),
    )
    columns = []
    for i, name in enumerate(COLUMN_NAMES):
        columns.append(Column(name=name, position=float(i)))
    board.columns = columns

    inbox = columns[0]
    inbox.insert_card(Card(title="Responder e-mails pendentes da semana", priority="medium"))
    inbox.insert_card(Card(title="Revisar proposta comercial do cliente Acme", priority="high"))
    inbox.insert_card(Card(title="Agendar consulta médica anual", priority="low"))

    board._current_card = inbox.cards[0]

    return board


# --- Default state tests ---

def test_board_defaults():
    board = Board()

    assert board.name == ""
    assert board.description == ""
    assert board.context == ""
    assert board.archived is False
    assert isinstance(board.created_at, datetime)


# --- LLM tests ---

def test_create_board_from_prompt():
    board = Board()
    board.update_object("Board de desenvolvimento do produto Kanban AI, para um time de 3 pessoas")

    assert board.name != ""
    assert board.description != ""
    assert board.archived is False
    print(f"\nname: {board.name}")
    print(f"description: {board.description}")
    print(f"context: {board.context}")


def test_create_board_from_prompt_2():
    board = Board()
    board.update_object(
        "Crie um board de kanban to-do, feito para o gerenciamento "
        "de tarefas do dia a dia de uma pessoa, tanto de trabalho como pessoais.")

    assert board.name != ""
    assert board.description != ""
    assert board.archived is False
    print(f"\nname: {board.name}")
    print(f"description: {board.description}")
    print(f"context: {board.context}")


def test_create_columns():
    board = Board()
    board.create_columns_from_prompt(
        "Crie as colunas do board: Inbox, To Do, In Progress, Review, Done.")
    assert len(board.columns) > 0
    assert board.columns[0].name == "Inbox"
    assert board.columns[1].name == "To Do"
    assert board.columns[2].name == "In Progress"
    assert board.columns[3].name == "Review"
    assert board.columns[4].name == "Done"

    for c in board.columns:
        print(c)
        print("-----")


# --- Tests using the board_todo fixture ---

def test_get_columns(board_todo):
    columns = board_todo.get_columns()
    assert len(columns) == len(COLUMN_NAMES)
    assert [c.name for c in columns] == COLUMN_NAMES

def test_board_todo_structure(board_todo):
    assert board_todo.name != ""
    assert board_todo.description != ""
    assert board_todo.context != ""
    assert board_todo.archived is False
    assert len(board_todo.columns) == len(COLUMN_NAMES)
    for i, col in enumerate(board_todo.columns):
        assert col.name == COLUMN_NAMES[i]
        assert col.position == float(i)

def test_create_card_from_column_prompt(board_todo):
    column = board_todo.columns[0]
    column.create_card_from_prompt("Criar um card para estudar o relatório e analisar os risos do projeto")
    print(column.cards[0])
    assert column.cards[0].title != ""

def test_get_column_from_prompt(board_todo):
    column = board_todo.get_column_from_prompt(
        "retorne a coluna das tarefas que tenho que fazer hoje"
    )
    print(column.to_ui())
    assert column.name == "Hoje"

def test_get_column_from_prompt2(board_todo):
    column = board_todo.get_column_from_prompt(
        "insira uma nova tarefa no board"
    )
    print(column)
    assert column == board_todo.columns[0]

def test_create_card_from_board_prompt(board_todo):
    card = board_todo.create_card_from_prompt("Criar um card para estudar o relatório e analisar os risos do projeto na coluna Hoje")
    print(f"card: {card}")
    column_hoje = next((col for col in board_todo.columns if col.name == "Hoje"), None)
    assert column_hoje is not None, "Coluna 'Hoje' não foi encontrada"
    assert len(column_hoje.cards) > 0
    assert column_hoje.cards[0] == card

def test_move_card_from_column_to_column(board_todo):
    card = board_todo._current_card
    column_from = board_todo.get_column_by_card(card)
    assert column_from.name == "Inbox"
    board_todo.move_card_from_column_to_column(card, "Mover card para a coluna 'Hoje'")
    column_to = board_todo.get_column_by_card(card)
    assert column_to.name == "Hoje"


# --- Tag tests ---

from models.tags import TAGS

@pytest.mark.parametrize("prompt,expected_tag", [
    ("montar nova proposta para cliente ABC", "comercial"),
    ("consulta médica de rotina", "saúde"),
    ("configurar CI/CD no GitHub Actions", "tecnologia"),
    ("comprar presentes de natal", "compras"),
    ("planejar viagem para Lisboa em julho", "viagem"),
    ("agendar e preparar pauta para reunião de alinhamento semanal", "reunião"),
])
def test_card_tag_is_filled(prompt, expected_tag):
    card = Card()
    card.update_object(prompt)

    print(f"\nprompt: {prompt!r}")
    print(f"  tag esperada:  {expected_tag!r}")
    print(f"  tag retornada: {card.tag!r}")

    assert card.tag in TAGS, f"tag {card.tag!r} não está na lista permitida"
    assert card.tag == expected_tag, f"esperado {expected_tag!r}, obtido {card.tag!r}"
