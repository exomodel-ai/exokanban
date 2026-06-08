# Card

## Definition

**Entity:** Card  
A Card represents a single, discrete unit of work within a Kanban system. It captures everything relevant about a task — what needs to be done, how important it is, how much effort it requires, and when it is due. Cards move through the Board's Columns as work progresses, providing a visible and traceable history of each work item.

## Objective

- Represent one clear, actionable, and deliverable unit of work.
- Carry all the information needed to understand, prioritize, and complete the task.
- Enable flow visibility by moving through workflow stages as work advances.

## Relationships

- **Parent:** Column (each Card belongs to exactly one Column at a time).
- **Children:** None in this version.
- **Relationship with Column:** Many Cards belong to one Column (N:1). Moving a card means changing its Column.

## Fields

| Field | Description |
|---|---|
| `title` | Short, action-oriented description of the work item |
| `description` | Detailed explanation of what needs to be done and what done looks like |
| `column_name` | Name of the workflow stage this card currently occupies |
| `position` | Numeric order within the column (lower = higher on the list) |
| `due_date` | ISO 8601 date by which this card should be completed |
| `priority` | Urgency level: `low`, `medium`, `high`, or `critical` |
| `tag` | Optional context label. Allowed values: `comercial`, `marketing`, `projeto`, `produto`, `reunião`, `financeiro`, `administrativo`, `jurídico`, `tecnologia`, `networking`, `eventos`, `família`, `saúde`, `educação`, `casa`, `compras`, `viagem`, `hobby`, `social`, `ideia`, `pesquisa` |
| `archived` | Whether this card has been removed from the active board |
| `created_at` | ISO 8601 timestamp of when the card was created |
| `updated_at` | ISO 8601 timestamp of the last modification |

---

## Instructions

### Field: `title`
Write a title that is self-explanatory without needing to open the card. Use an action verb followed by a clear object.

Good examples: `Draft proposal for client ABC`, `Buy groceries for Sunday dinner`, `Review insurance policy renewal`.  
Poor examples: `Task`, `Important thing`, `Follow up`, `Meeting`.

### Field: `description`
Describe what needs to be done and what the outcome looks like when it is complete. A good description answers: *What is the work? What does done look like? Are there any constraints or dependencies?*

For complex tasks, use a short list of acceptance criteria. Keep it objective and actionable.

### Field: `column_name`
Reflects the current stage of the card. This field is updated when the card moves between columns. It should always match the name of the Column it currently belongs to.

### Field: `position`
Determines the card's order within its column. Position 0 is the top of the list (highest priority within the column). Positions are managed by the system when cards are added or reordered.

### Field: `due_date`
Set a due date whenever there is a real deadline or commitment. Use ISO 8601 format (e.g. `2026-06-15`). Do not fabricate due dates — leave blank if there is no real deadline.

### Field: `priority`
Use priority consistently:
- `critical` — must be addressed immediately; blocks other work or has severe consequences if delayed.
- `high` — important and time-sensitive; should be worked on before medium and low items.
- `medium` — standard work item with no immediate urgency.
- `low` — valuable but can be deferred without impact.

### Field: `effort`
Effort reflects the relative size of the work, not hours:
- `xs` — a few minutes to an hour.
- `s` — a few hours.
- `m` — one to two days.
- `l` — three to five days.
- `xl` — more than a week; consider breaking it down.

### Field: `tag`
Use a tag to classify the card by context or area of life. Always choose the single most relevant tag from the list below. Prefer an imperfect match over leaving the field blank — only leave blank if the card is genuinely ambiguous across multiple unrelated areas. Do not invent tags outside the list.

**Work tags:**

| Tag | Use when the card is about... |
|---|---|
| `comercial` | Sales, client relationships, proposals, contracts, business development |
| `marketing` | Campaigns, content, brand, social media, communication, advertising |
| `projeto` | Coordinating a multi-step initiative with a defined scope and deadline |
| `produto` | Product features, roadmap, user stories, releases, specs |
| `reunião` | Preparing for, following up on, or summarizing a meeting |
| `financeiro` | Invoices, payments, budgets, expenses, taxes, accounting |
| `administrativo` | Paperwork, bureaucracy, registrations, compliance, internal processes |
| `jurídico` | Contracts, legal review, compliance, intellectual property |
| `tecnologia` | Software, infrastructure, development, IT, tools, integrations |
| `networking` | Relationship-building, introductions, industry connections |
| `eventos` | Organizing, attending, or following up on events and conferences |

**Personal tags:**

| Tag | Use when the card is about... |
|---|---|
| `família` | Anything involving family members, household coordination, caregiving |
| `saúde` | Medical appointments, fitness, nutrition, mental health, wellbeing |
| `educação` | Learning, courses, books, skills, certifications |
| `casa` | Home maintenance, repairs, renovation, furnishing |
| `compras` | Buying goods or services for personal or household use |
| `viagem` | Planning, booking, or preparing for a trip |
| `hobby` | Personal interests, recreation, creative activities outside of work |
| `social` | Social plans, friendships, community activities |

**General tags:**

| Tag | Use when the card is about... |
|---|---|
| `ideia` | An unexplored concept, hypothesis, or creative spark worth capturing |
| `pesquisa` | Investigating, gathering information, or comparing options before deciding |

### Field: `archived`
Set to `true` when the card is no longer relevant and should not appear in active views. Do not delete cards — archive them to preserve history.

### Field: `created_at` / `updated_at`
Set automatically by the system. Do not edit manually.

---

## Recommendations (Do's and Don'ts)

**Do's:**
- Write one card per unit of work — each card should be completable independently.
- Keep titles short and action-oriented (under 10 words when possible).
- Fill in `description` before moving a card out of the first column.
- Set `due_date` only when there is a real deadline.
- Break down cards with `effort` of `xl` into smaller cards before starting work.
- Archive completed cards regularly to keep the board clean.

**Don'ts:**
- Don't create cards so broad they represent entire projects — those belong as separate boards.
- Don't use `critical` priority for everything — reserve it for genuine emergencies.
- Don't leave `description` empty for cards that involve more than a trivial action.
- Don't move a card backward in the workflow as a shortcut — reflect the real state instead.
- Don't create duplicate cards for the same work item.

---

## Validation Checklist

- [ ] `title` is self-explanatory and starts with an action verb.
- [ ] `description` explains what needs to be done and what done looks like.
- [ ] `priority` reflects the real urgency relative to other cards on the board.
- [ ] `effort` is set and aligns with the scope described in the description.
- [ ] `due_date` is set if and only if there is a real deadline.
- [ ] The card represents a single, independent unit of work.
- [ ] Cards with `effort: xl` have been reviewed for possible breakdown.

---

## EXAMPLES

### EXAMPLE 1

```
title: Prepare quarterly budget report
description: Compile income and expenses from the last 3 months. Cross-check with bank statements. Export final report as PDF and share with the finance team by end of month. Done when the PDF is sent and acknowledged.
column_name: In Progress
position: 0
due_date: 2026-06-30
priority: high
effort: m
archived: false
```

### EXAMPLE 2

```
title: Research home insurance options
description: Compare at least 3 insurance providers. Focus on coverage for natural disasters and theft. Note premium costs, deductibles, and renewal terms. Done when a comparison table is ready for review.
column_name: Inbox
position: 1
due_date: null
priority: medium
effort: s
archived: false
```
