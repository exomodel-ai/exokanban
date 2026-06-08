# Kanban To-Do — Regras do Fluxo

## Colunas e seus papéis

### Inbox
Destino padrão de todo card novo. Representa a caixa de entrada — tarefas capturadas mas ainda não avaliadas. Nenhum comprometimento de prazo ou prioridade é feito aqui.

### Prioridade
Cards que foram qualificados e priorizados saem do Inbox e entram aqui. Para mover um card para Prioridade, ele deve ter título claro, descrição suficiente para ser executado e, opcionalmente, uma data limite (`due_date`).

### Nesta Semana
Coluna de planejamento semanal. Contém as metas e tarefas selecionadas para a semana atual. Cards entram aqui vindos de Prioridade quando há comprometimento de execução na semana corrente. É o ponto de partida para o planejamento diário — cards de Nesta Semana são promovidos para Hoje conforme a disponibilidade do dia.

### Hoje
Cards que serão executados **no dia atual**. Somente cards vindos da coluna Nesta Semana devem entrar aqui.

Regras obrigatórias:
- **WIP limit: 6.** Nunca deve haver mais de 6 cards simultâneos nesta coluna.
- **Granularidade:** cada card deve ser executável em no máximo algumas horas. Cards grandes demais devem ser quebrados em tarefas menores antes de entrar em Hoje.


### Feito
Cards concluídos são movidos para esta coluna. Nenhuma edição de conteúdo deve ocorrer aqui — apenas registro de conclusão.

### Antigos
Cards na coluna Feito que não foram alterados há mais de 30 dias devem ser movidos para Antigos. Esta coluna é um arquivo histórico e não aparece na visualização padrão do board. Cards em Antigos podem ser arquivados definitivamente (`archived = true`) quando não houver mais valor de referência.

## Fluxo de referência

```
Inbox → Prioridade → Nesta Semana → Hoje → Feito → Antigos
```

Este fluxo é uma referência, não uma regra rígida. Cards podem ser movidos livremente entre colunas conforme o contexto — pular etapas é permitido quando faz sentido.

## Regras gerais

- Cards arquivados (`archived = true`) não aparecem em nenhuma listagem ativa.
- `due_date` deve ser usado com critério: apenas quando há um prazo real, não como estimativa de execução.
- A coluna Antigos é oculta na visualização padrão do board mas pode ser consultada explicitamente.
