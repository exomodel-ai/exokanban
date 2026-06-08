from db.uow import UnitOfWork

BOARD_NAME = "Kanban to-do"


def seed():
    from models.board import Board
    from models.column import Column
    from models.card import Card  # noqa: F401 — forces mapper registration before the query

    with UnitOfWork() as uow:
        existing = Board.first(name=BOARD_NAME)
        if existing:
            for col in existing.columns:
                _ = col.cards
            return existing

        board = Board(
            name=BOARD_NAME,
            description="Gerenciamento de tarefas diárias de trabalho e pessoais.",
        ).save()
        uow.flush()

        columns = [
            Column(name="Inbox",        position=0.0, visible=True),
            Column(name="Prioridade",   position=1.0, visible=True),
            Column(name="Nesta Semana", position=2.0, visible=True),
            Column(name="Hoje",         position=3.0, visible=True),
            Column(name="Feito",        position=4.0, visible=True),
            Column(name="Antigos",      position=5.0, visible=False),
        ]
        for col in columns:
            col.board_id = board.id
            col.save()

        uow.commit()
        uow.refresh(board)
        for col in board.columns:
            _ = col.cards
        return board
