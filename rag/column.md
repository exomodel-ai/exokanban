# Column

## Definition

**Entity:** Column  
A Column represents a distinct stage in the workflow of a Board. It defines a state that a work item (Card) occupies at a given moment. Columns create the visual structure of the Kanban board and embody the steps through which work flows from beginning to completion.

## Objective

- Define the stages through which work progresses.
- Make the current state of every work item immediately visible.
- Enable flow control through Work In Progress (WIP) limits, preventing overload and exposing bottlenecks.

## Relationships

- **Parent:** Board (each Column belongs to exactly one Board).
- **Children:** Cards (a Column contains zero or more Cards).
- **Relationship with Board:** Many Columns belong to one Board (N:1).
- **Relationship with Cards:** One Column holds many Cards (1:N). A Card belongs to one Column at a time.

## Fields

| Field | Description |
|---|---|
| `name` | Label that identifies the workflow stage this column represents |
| `position` | Numeric order of the column on the board (left to right, starting at 0) |
| `wip_limit` | Maximum number of cards allowed in this column simultaneously (0 = no limit) |
| `cards` | List of Card entities currently in this stage |

---

## Instructions

### Field: `name`
The name should describe a state of work, not an action. Prefer nouns or short phrases that answer "what is happening to this item right now?".

Good examples: `Inbox`, `In Progress`, `Waiting for Approval`, `Under Review`, `Done`.  
Poor examples: `Do Work`, `Review It`, `Stuff`, `Column 3`.

### Field: `position`
Positions must be unique within a Board and increase left to right. The leftmost column (entry point) should have position 0. Reorder positions whenever columns are added or removed to maintain a clean sequence.

### Field: `wip_limit`
Setting a WIP limit is one of the most powerful practices in Kanban. It forces the team to finish work before pulling new items in. A limit of 0 means no constraint is enforced.

Guidelines:
- For active work stages (e.g. `In Progress`), a WIP limit of 1–3 per person is typical.
- For buffer or waiting stages (e.g. `Waiting for Approval`), a limit of 3–5 is reasonable.
- For entry and completion columns (`Inbox`, `Done`), no limit (0) is usually appropriate.

### Field: `cards`
Cards are managed by the system — do not manipulate this list directly. New cards are added through `create_card_from_prompt` or `insert_card`. The first position in the list represents the most recently added card.

---

## Recommendations (Do's and Don'ts)

**Do's:**
- Name columns to reflect genuine stages of your workflow, not organizational units or people's names.
- Set WIP limits on all active work stages.
- Keep the number of columns between 3 and 7 for clarity.
- Place buffer columns (e.g. `Waiting`, `Blocked`) between active stages when handoffs cause delays.
- Review column names periodically — if a column is always empty or always full, reconsider its purpose.

**Don'ts:**
- Don't create columns just to track who owns work — that belongs on the Card.
- Don't skip setting WIP limits on columns where work is actively being done.
- Don't merge unrelated stages into a single column to keep the count low.
- Don't allow cards to sit in a column indefinitely without a process review.
- Don't use identical or near-identical names for different columns.

---

## Validation Checklist

- [ ] `name` describes a state, not an action or a person.
- [ ] `position` is unique within the board and follows a left-to-right order.
- [ ] `wip_limit` is set for all active work stages (not 0).
- [ ] The column's purpose is distinct from all other columns on the board.
- [ ] The column is reachable — cards can naturally flow into it from the previous stage.

---

## EXAMPLES

### EXAMPLE 1

```
name: In Progress
position: 2
wip_limit: 3
cards: [...]
```
*An active work stage with a WIP limit of 3, positioned third on the board. No more than 3 items should be worked on simultaneously.*

### EXAMPLE 2

```
name: Waiting for Response
position: 3
wip_limit: 5
cards: [...]
```
*A buffer column for items blocked by an external party (e.g. awaiting a reply, approval, or delivery). WIP limit of 5 signals that if more than 5 items are stuck waiting, the process itself needs attention.*
