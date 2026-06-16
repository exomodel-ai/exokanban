# /analyze — Métricas do Board

As 2 últimas colunas por `position` (Feito + Antigos) são excluídas das métricas de carga ativa.
A penúltima coluna (Feito) é usada exclusivamente para lead time.

## Colunas

| Métrica | Cálculo |
|---|---|
| Cards ativos | `count(not archived)` por coluna 
| WIP status | `count / wip_limit` → `OK / AT_LIMIT / EXCEEDED` (ignora se `wip_limit == 0`) |

## Prazo

| Métrica | Cálculo |
|---|---|
| Vencidos | `count(due_date < hoje)` fora das 2 últimas colunas |
| Vencendo em 7 dias | `count(hoje <= due_date <= hoje+7)` |
| High/critical sem prazo | `count(priority in [high,critical] and due_date is null)` |

## Prioridade

| Métrica | Cálculo |
|---|---|
| Distribuição | `{critical: N, high: N, medium: N, low: N}` |
| % fire-fighting | `(critical + high) / total_ativo * 100` |

## Envelhecimento

| Métrica | Cálculo |
|---|---|
| Estagnados >7d | `count(updated_at < hoje-7)` por coluna |
| Estagnados >30d | `count(updated_at < hoje-30)` por coluna |

## Tags

| Métrica | Cálculo |
|---|---|
| Distribuição | `{tag: count}` ordenado por frequência |
| Sem tag | `count(tag == "")` |

## Board geral

| Métrica | Cálculo |
|---|---|
| Total ativo | `count(not archived and coluna not in 2 últimas por position)` |
| Coluna mais carregada | `argmax(count)` excluindo as 2 últimas |
| Coluna gargalo | `argmax(count(updated_at < hoje-7))` |

## Lead time (coluna Feito)

| Métrica | Cálculo |
|---|---|
| Médio / mediano | `mean / median(updated_at - created_at)` dos cards na penúltima coluna |
| Mínimo / máximo | `min / max(updated_at - created_at)` |
