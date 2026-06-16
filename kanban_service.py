from typing import Optional, TYPE_CHECKING

from db.uow import UnitOfWork
from models.board import Board

if TYPE_CHECKING:
    from models.card import Card


class KanbanService:
    """Pure business logic — no conversational state, no I/O routing."""

    def __init__(self, board_id: int):
        self.board_id = board_id

    # ------------------------------------------------------------------
    # Card entity operations — return Card or raise ValueError
    # ------------------------------------------------------------------

    def get_card(self, card_id: int) -> "Card":
        from models.card import Card
        with UnitOfWork() as uow:
            card = Card.get_by_id(card_id)
        if not card:
            raise ValueError(f"Card #{card_id} not found.")
        return card

    def create_card(self, prompt: str) -> "Card":
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards
            card = board.create_card_from_prompt(prompt)
            uow.commit()
            uow.refresh(card)
        return card

    def update_card(self, card_id: int, prompt: str) -> "Card":
        from models.card import Card
        with UnitOfWork() as uow:
            card = Card.get_by_id(card_id)
            if not card:
                raise ValueError(f"Card #{card_id} not found.")
            card.update_object(prompt)
            uow.commit()
            uow.refresh(card)
        return card

    def move_card(self, card_id: int, column_prompt: str) -> str:
        """Moves card to the column matched by column_prompt. Returns destination column name."""
        from models.card import Card
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards
            board._current_card = Card.get_by_id(card_id)
            board.move_current_card_from_column_to_column(column_prompt)
            dest = next(
                (c for c in board.columns if c.id == board._current_card.column_id), None
            )
            dest_name = dest.name if dest else column_prompt
            uow.commit()
        return dest_name

    def move_card_to_next_column(self, card_id: int) -> str:
        """Moves card one step forward in position order. Returns destination column name."""
        from models.card import Card
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards
            card = Card.get_by_id(card_id)
            if not card:
                raise ValueError(f"Card #{card_id} not found.")
            sorted_cols = sorted(board.columns, key=lambda c: c.position)
            current_col = next((c for c in sorted_cols if c.id == card.column_id), None)
            if not current_col:
                raise ValueError("Card is not in any column.")
            idx = sorted_cols.index(current_col)
            if idx >= len(sorted_cols) - 1:
                raise ValueError(f"Card is already in the last column ('{current_col.name}').")
            next_col = sorted_cols[idx + 1]
            current_col.remove_card(card)
            next_col.insert_card(card)
            dest_name = next_col.name
            uow.commit()
        return dest_name

    def archive_card(self, card_id: int) -> str:
        from models.card import Card
        with UnitOfWork() as uow:
            card = Card.get_by_id(card_id)
            if not card:
                raise ValueError(f"Card #{card_id} not found.")
            title = card.title
            card.archive()
            card.save()
            uow.commit()
        return f"Card #{card_id} '{title}' archived."

    def get_column(self, column_id: int) -> "Column":
        from models.column import Column
        with UnitOfWork() as uow:
            column = Column.get_by_id(column_id)
        if not column:
            raise ValueError(f"Column #{column_id} not found.")
        return column

    def update_column(self, column_id: int, prompt: str) -> "Column":
        from models.column import Column
        with UnitOfWork() as uow:
            column = Column.get_by_id(column_id)
            if not column:
                raise ValueError(f"Column #{column_id} not found.")
            column.update_object(prompt)
            uow.commit()
            uow.refresh(column)
        return column

    def find_card(self, prompt: str) -> Optional["Card"]:
        """Semantic search across the board. Returns Card or None."""
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            card = board.get_card_from_prompt(prompt)
        return card

    # ------------------------------------------------------------------
    # View / action operations — return strings
    # ------------------------------------------------------------------

    def show_board(self) -> str:
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards
            result = board.show_column_cards()
        return result

    def show_board_data(self) -> tuple[str, list[list[tuple[int, str]]]]:
        """Returns (board_text, card_groups) — each group is a list of (card_id, title) per column."""
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards
            text = board.show_column_cards()
            card_groups = [
                [(c.id, c.title) for c in col.get_cards()]
                for col in sorted(board.columns, key=lambda c: c.position)
                if col.get_cards()
            ]
        return text, card_groups

    def list_cards(self, column_hint: str = "") -> str:
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards
            if column_hint:
                from models.column import Column
                column = (
                    Column.get_by_id(int(column_hint))
                    if column_hint.isdigit()
                    else board.get_column_from_prompt(column_hint)
                )
                result = board.show_column_cards(column)
            else:
                result = board.show_column_cards()
        return result

    def show_due_cards(self) -> str:
        from datetime import datetime, timedelta

        today = datetime.now().date()
        week_end = today + timedelta(days=7)

        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            active_cols = board.active_columns()
            all_cards = []
            for col in active_cols:
                _ = col.cards
                all_cards.extend(col.get_cards())

            due       = [c for c in all_cards if c.due_date is not None]
            overdue   = sorted([c for c in due if c.due_date.date() < today],             key=lambda c: c.due_date)
            due_today = sorted([c for c in due if c.due_date.date() == today],            key=lambda c: c.due_date)
            upcoming  = sorted([c for c in due if today < c.due_date.date() <= week_end], key=lambda c: c.due_date)

            def _fmt(c):
                delta = (c.due_date.date() - today).days
                date_str = c.due_date.strftime("%m/%d")
                if delta < 0:
                    note = f"overdue by {-delta} day(s)"
                elif delta == 0:
                    note = "due today"
                else:
                    note = f"in {delta} day(s) ({date_str})"
                return f"  • <b>#{c.id}</b> {c.title} — {note}"

            sections = []
            if overdue:
                sections.append(f"🔴 <b>Overdue ({len(overdue)})</b>\n" + "\n".join(_fmt(c) for c in overdue))
            if due_today:
                sections.append(f"🟡 <b>Due today ({len(due_today)})</b>\n" + "\n".join(_fmt(c) for c in due_today))
            if upcoming:
                sections.append(f"🟢 <b>Next 7 days ({len(upcoming)})</b>\n" + "\n".join(_fmt(c) for c in upcoming))

            result = "\n\n".join(sections) if sections else "No cards with a due date."

        return result

    def move_old_cards(self) -> str:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=30)
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            col_source = board.done_column()
            col_dest   = board.archive_column()
            if not col_source or not col_dest:
                return "The board needs at least NUM_ACTIVE_COLUMNS + 2 columns."
            source_name = col_source.name
            dest_name   = col_dest.name
            _ = col_source.cards
            _ = col_dest.cards
            old = [c for c in col_source.cards if not c.archived and c.updated_at < cutoff]
            titles = [c.title for c in old]
            for card in old:
                col_source.remove_card(card)
                col_dest.insert_card(card)
            uow.commit()
        if not titles:
            return f"No cards older than 30 days in '{source_name}'."
        names = ", ".join(f"'{t}'" for t in titles)
        return f"{len(titles)} card(s) moved to '{dest_name}': {names}."

    def export_to_csv(self) -> str:
        from models.card import Card
        from models.column import Column

        def _block(entities) -> str:
            if not entities:
                return ""
            rows = [entities[0].to_csv(include_header=True)]
            rows += [e.to_csv(include_header=False) for e in entities[1:]]
            return "\n".join(rows)

        with UnitOfWork() as uow:
            board_csv  = _block(Board.all())
            column_csv = _block(Column.all())
            card_csv   = _block(Card.all())

        for filename, content in [("board.csv", board_csv), ("column.csv", column_csv), ("card.csv", card_csv)]:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

        return "✅ Exported: board.csv, column.csv, card.csv"

    def analyze_board(self) -> str:
        from collections import Counter
        from statistics import mean, median

        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            for col in board.columns:
                _ = col.cards

            active_cols = board.active_columns()
            done_col    = board.done_column()
            active_cards = [c for col in active_cols for c in col.cards if not c.archived]
            total = len(active_cards)

            # Colunas
            col_lines = []
            for col in active_cols:
                count  = col.active_count()
                status = col.wip_status()
                suffix = f" ({count}/{col.wip_limit})" if col.wip_limit > 0 else f" ({count})"
                col_lines.append(f"  {col.name}: {status}{suffix}")

            # Prazo
            overdue_count = sum(1 for c in active_cards if c.is_overdue())
            due_7_count   = sum(1 for c in active_cards if not c.is_overdue() and c.is_due_within(7))
            high_no_due   = sum(1 for c in active_cards if c.priority in ("high", "critical") and c.due_date is None)

            # Prioridade
            priorities   = Counter(c.priority for c in active_cards)
            fire_pct     = round((priorities["critical"] + priorities["high"]) / total * 100) if total else 0
            first_col    = active_cols[0] if active_cols else None
            crit_inbox   = sum(1 for c in (first_col.cards if first_col else []) if not c.archived and c.priority == "critical")

            # Envelhecimento
            stale_7  = [(col.name, len(col.stale_cards(7)))  for col in active_cols]
            stale_30 = [(col.name, len(col.stale_cards(30))) for col in active_cols]
            stale_7_total  = sum(n for _, n in stale_7)
            stale_30_total = sum(n for _, n in stale_30)

            # Tags
            tag_counts = Counter(c.tag for c in active_cards if c.tag)
            no_tag     = sum(1 for c in active_cards if not c.tag)

            # Board geral
            col_counts   = [(col, col.active_count())        for col in active_cols]
            stale_counts = [(col, len(col.stale_cards(7)))   for col in active_cols]
            most_loaded  = max(col_counts,   key=lambda x: x[1])[0] if col_counts else None
            bottleneck   = max(stale_counts, key=lambda x: x[1])[0] if stale_counts and max(n for _, n in stale_counts) > 0 else None

            # Lead time
            lead_times = [lt for c in (done_col.cards if done_col else []) if not c.archived and (lt := c.lead_time_days()) is not None]

            # --- Formatação ---
            lines = [f"<b>📊 {board.name}</b>\n"]

            lines.append("<b>Colunas</b>")
            lines.extend(col_lines)

            lines.append("\n<b>Prazo</b>")
            lines.append(f"  Vencidos: {overdue_count}")
            lines.append(f"  Vencendo em 7 dias: {due_7_count}")
            lines.append(f"  High/critical sem prazo: {high_no_due}")

            lines.append("\n<b>Prioridade</b>")
            dist = " · ".join(f"{k}: {priorities[k]}" for k in ("critical", "high", "medium", "low") if priorities[k])
            lines.append(f"  {dist}" if dist else "  (sem cards)")
            lines.append(f"  Fire-fighting: {fire_pct}%")
            if crit_inbox and first_col:
                lines.append(f"  ⚠️ {crit_inbox} critical em {first_col.name}")

            lines.append("\n<b>Envelhecimento</b>")
            detail_7  = ", ".join(f"{n} em {c}" for c, n in stale_7  if n)
            detail_30 = ", ".join(f"{n} em {c}" for c, n in stale_30 if n)
            lines.append(f"  Estagnados >7d: {stale_7_total}"  + (f" ({detail_7})"  if detail_7  else ""))
            lines.append(f"  Estagnados >30d: {stale_30_total}" + (f" ({detail_30})" if detail_30 else ""))

            lines.append("\n<b>Tags</b>")
            if tag_counts:
                lines.append("  " + " · ".join(f"{tag}: {n}" for tag, n in tag_counts.most_common()))
            lines.append(f"  Sem tag: {no_tag}")

            lines.append("\n<b>Board geral</b>")
            lines.append(f"  Total ativo: {total}")
            if most_loaded:
                ml_count = next(n for col, n in col_counts if col is most_loaded)
                lines.append(f"  Mais carregada: {most_loaded.name} ({ml_count})")
            if bottleneck:
                bt_count = next(n for col, n in stale_counts if col is bottleneck)
                lines.append(f"  Gargalo: {bottleneck.name} ({bt_count} estagnados >7d)")

            lines.append("\n<b>Lead time (Feito)</b>")
            if lead_times:
                lines.append(f"  Médio: {mean(lead_times):.1f}d · Mediano: {median(lead_times):.1f}d")
                lines.append(f"  Mín: {min(lead_times):.1f}d · Máx: {max(lead_times):.1f}d")
            else:
                lines.append("  Sem dados.")

            result = "\n".join(lines)

        return result

    def run_filling_instructions(self) -> str:
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            result = board.run_filling_instructions()
            uow.commit()
        return result

    def run_board_prompt(self, prompt: str, current_card_id: Optional[int] = None) -> tuple[str, Optional[int]]:
        """Routes a free-text prompt through the board's master_prompt.
        Returns (result_str, new_current_card_id)."""
        from models.card import Card
        with UnitOfWork() as uow:
            board = Board.get_by_id(self.board_id)
            if current_card_id:
                board._current_card = Card.get_by_id(current_card_id)
            result = board.master_prompt(prompt)
            uow.commit()
            new_card_id = None
            if board._current_card is not None:
                uow.refresh(board._current_card)
                new_card_id = board._current_card.id
        return result, new_card_id
