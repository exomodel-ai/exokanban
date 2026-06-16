# Kanban To-Do — Regras do Fluxo

## Colunas e seus papéis

### Inbox
Destino padrão de todo card novo. Representa a caixa de entrada — tarefas capturadas mas ainda não avaliadas. Nenhum comprometimento de prazo ou prioridade é feito aqui.

### Prioridade
Cards que foram qualificados e priorizados saem do Inbox e entram aqui. Para mover um card para Prioridade, ele deve ter título claro, descrição suficiente para ser executado e, opcionalmente, uma data limite (`due_date`).

### Nesta Semana
Coluna de planejamento macro da semana. Representa as prioridades e metas escolhidas para a semana corrente — uma visão agregada do que precisa acontecer, sem o nível de detalhe do dia a dia. Serve de guia para o planejamento diário: ao montar o "Hoje", o responsável consulta esta coluna para decidir o que avança. 

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
