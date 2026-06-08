# ExoSQLModel

`ExoSQLModel` é a classe base que combina persistência em banco de dados (via SQLModel/SQLAlchemy) com manipulação de campos por linguagem natural (via ExoModel/Gemini). Qualquer entidade que herde dela ganha automaticamente os dois mundos.

## Herança

```
pydantic.BaseModel
       ↑           ↑
   ExoModel     SQLModel
       ↑           ↑
       └─ExoSQLModel─┘   (db/base.py — sem table=True)
                  ↑
    Board / Column / Card  (table=True — tabelas concretas)
```

`ExoModel` permanece independente — funciona sem banco de dados. `ExoSQLModel` é quem introduz a dependência do SQLModel.

---

## Configuração

O banco é configurado via variável de ambiente. Se não definida, usa SQLite local:

```bash
# .env
DATABASE_URL=sqlite:///exokanban.db   # padrão
DATABASE_URL=sqlite:///:memory:       # in-memory (testes)
DATABASE_URL=postgresql://user:pw@host/db  # produção futura
```

As tabelas são criadas chamando `init_db()` na inicialização da aplicação:

```python
from db.engine import init_db
init_db()  # executa CREATE TABLE IF NOT EXISTS para todos os modelos
```

---

## Campos herdados

| Campo | Tipo           | Descrição                                      |
|-------|----------------|------------------------------------------------|
| `id`  | `Optional[int]` | Chave primária, preenchida automaticamente pelo banco |

---

## Métodos

### `create(prompt, **initial_values)` — classmethod

Cria uma instância com campos preenchidos via IA e persiste imediatamente.

```python
card = Card.create("Tarefa de revisão de código do módulo de autenticação")
print(card.id)  # 1 — já está no banco
```

Equivalente a:
```python
card = Card()
card.update_object("...")  # IA preenche os campos
card = card.save()          # persiste
```

---

### `save(session=None)` — método de instância

Persiste ou atualiza a instância no banco. Retorna o objeto salvo (pode ser uma instância diferente se o objeto estava desanexado da sessão).

```python
card = Card(title="Nova tarefa", priority="high")
card = card.save()  # INSERT — id preenchido após o retorno
print(card.id)      # 1

card.priority = "critical"
card = card.save()  # UPDATE
```

Usa `session.merge()` internamente, que trata corretamente tanto INSERT (id=None) quanto UPDATE (id existente).

---

### `delete(session=None)` — método de instância

Remove a linha do banco. A instância em memória não é alterada.

```python
card = Card.get_by_id(1)
card.delete()
# card.id ainda é 1 em memória, mas a linha foi removida do banco
```

---

### `get_by_id(record_id, session=None)` — classmethod

Busca um registro pelo id. Retorna `None` se não encontrado.

```python
card = Card.get_by_id(1)
if card is None:
    print("Não encontrado")
```

---

### `all(session=None)` — classmethod

Retorna todos os registros da tabela como lista.

```python
cards = Card.all()
for card in cards:
    print(card.title)
```

---

## Sessão explícita

Todos os métodos aceitam um parâmetro `session` opcional. Quando fornecido, o método opera dentro dessa sessão e **não faz commit automaticamente** — o controle da transação fica com o chamador.

Use sessão explícita quando precisar de:
- Múltiplas operações em uma única transação
- Controle de rollback manual
- Acesso a relacionamentos após a operação

```python
from db.engine import get_session

with get_session() as session:
    board = Board.get_by_id(1, session)
    board.name = "Novo nome"
    board = board.save(session)
    # relacionamentos acessíveis aqui, sessão ainda está aberta
    print(board.columns)
```

---

## Relacionamentos e sessão

Relacionamentos (campos com `Relationship()`) são carregados sob demanda pelo SQLAlchemy. Fora de uma sessão ativa, acessar um relacionamento pode retornar uma lista vazia ou lançar `DetachedInstanceError`.

```python
# ERRADO — sessão já fechou, relacionamento pode estar vazio
board = Board.get_by_id(1)
print(board.columns)  # pode ser []

# CORRETO — acessa dentro da sessão
with get_session() as session:
    board = Board.get_by_id(1, session)
    print(board.columns)  # carregado corretamente
```

---

## Exemplos práticos

### Criação via IA

```python
from dotenv import load_dotenv
from db.engine import init_db
from models.board import Board
from models.column import Column
from models.card import Card

load_dotenv()
init_db()

# IA preenche name, description, context e persiste
board = Board.create("Kanban de lançamento do produto v2.0, time de 5 pessoas")
print(board.id)           # 1
print(board.name)         # "Lançamento v2.0"
print(board.description)  # preenchido pela IA
```

---

### Criação manual e update via IA

```python
card = Card(title="Revisar documentação", priority="medium")
card = card.save()
print(card.id)  # 1

# IA atualiza apenas os campos mencionados no prompt
card.update_object("Aumentar prioridade para crítica e definir prazo para amanhã")
card = card.save()
print(card.priority)   # "critical"
print(card.due_date)   # data de amanhã em ISO 8601
```

---

### Recuperação e listagem

```python
# Por id
card = Card.get_by_id(1)
print(card.title)

# Todos os registros
all_cards = Card.all()
print(f"{len(all_cards)} cards encontrados")

# Retorna None se não existir
missing = Card.get_by_id(9999)
assert missing is None
```

---

### Update dentro de uma sessão

```python
with get_session() as session:
    card = Card.get_by_id(1, session)
    card.update_object("Adicionar tag de urgência e atribuir ao João")
    card = card.save(session)
```

---

### Delete

```python
card = Card.get_by_id(1)
card.delete()

assert Card.get_by_id(1) is None
```

---

### Transação com rollback por regra de negócio

Quando uma operação envolve múltiplas entidades que devem ser salvas atomicamente, use sessão explícita e faça rollback em caso de violação de regra de negócio.

```python
from db.engine import get_session
from models.column import Column
from models.card import Card

class WipLimitExceeded(Exception):
    pass

def move_card(card: Card, target_column: Column) -> None:
    with get_session() as session:
        try:
            col = Column.get_by_id(target_column.id, session)

            # regra de negócio: wip_limit > 0 significa que há limite
            cards_in_col = Card.all(session)
            cards_count = sum(1 for c in cards_in_col if c.column_id == col.id)
            if col.wip_limit > 0 and cards_count >= col.wip_limit:
                raise WipLimitExceeded(
                    f"Coluna '{col.name}' atingiu o limite WIP de {col.wip_limit} cards."
                )

            card.column_id = col.id
            card.save(session)

        except WipLimitExceeded:
            session.rollback()
            raise
```

Uso:

```python
card = Card.get_by_id(3)
col_in_progress = Column.get_by_id(2)

try:
    move_card(card, col_in_progress)
    print("Card movido com sucesso.")
except WipLimitExceeded as e:
    print(f"Bloqueado: {e}")
```

> **Nota:** `get_session()` usa `Session` do SQLModel, que faz rollback automaticamente ao sair do bloco `with` se `commit()` não foi chamado. O `session.rollback()` explícito é necessário apenas quando você quer garantir o rollback *antes* de sair do bloco — por exemplo, para logar o estado ou relançar a exceção com contexto adicional.

---

## Definindo um novo modelo

```python
from typing import Optional
from sqlmodel import Field, Relationship
from db.base import ExoSQLModel

class Sprint(ExoSQLModel, table=True):
    __tablename__ = "sprints"

    name: str = ""
    goal: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "planned"  # "planned" | "active" | "done"

    @classmethod
    def get_rag_sources(cls) -> list[str]:
        return ["rag/sprint.md"]  # contexto RAG opcional
```

Após definir o modelo, chame `init_db()` para criar a tabela:

```python
init_db()

sprint = Sprint.create("Sprint 3 focada em estabilidade, começa segunda-feira, duração de 2 semanas")
print(sprint.id)      # 1
print(sprint.name)    # "Sprint 3"
print(sprint.goal)    # preenchido pela IA
```
