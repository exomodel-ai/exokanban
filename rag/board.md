# Board

## Definition

**Entity:** Board  
A Board is the central visual management tool of a Kanban system. It represents a complete workflow — from the moment a work item is identified to its final completion. The Board provides a shared, real-time view of all ongoing work, making progress and bottlenecks immediately visible to everyone involved.

## Objective

- Provide full visibility of the current state of work across all stages.
- Enable teams or individuals to manage flow, identify bottlenecks, and make informed prioritization decisions.
- Serve as a single source of truth for what is being worked on, what is waiting, and what has been completed.

## Relationships

- **Parent:** None. The Board is the root entity of the Kanban system.
- **Children:** Columns (must have at least 2; represents workflow stages).
- **Relationship type with Columns:** One Board has many Columns (1:N). A Column belongs to exactly one Board.

## Fields

| Field | Description |
|---|---|
| `name` | Short, descriptive name that identifies the board's purpose |
| `description` | A sentence or two explaining what work this board manages |
| `context` | Free-form text that provides background information to guide AI analysis and suggestions |
| `archived` | Whether the board is inactive and no longer in active use |
| `created_at` | ISO 8601 timestamp of when the board was created |
| `columns` | Ordered list of workflow stages (Column entities) |

---

## Instructions

### Field: `name`
Choose a name that immediately communicates the board's scope and owner. Avoid generic names like "My Board" or "Work". Prefer names that answer "what kind of work?" and "for whom?".

Good examples: `Product Launch Q3`, `Personal Weekly Goals`, `Client Onboarding`, `Household Tasks`.

### Field: `description`
Write one or two sentences describing the purpose of this board. Include: what type of work it tracks, who uses it, and what a completed item looks like at a high level.

### Field: `context`
Use this field to give the AI assistant rich background about the work environment. Include: team size, work cadence (daily, weekly), priorities, constraints, and any domain-specific language. The richer this field is, the more accurate and useful the AI suggestions will be.

Example: *"Personal productivity board for a freelance consultant. Weekly review on Sundays. Work tasks are billed by project; personal tasks are health, family and learning related."*

### Field: `archived`
Set to `true` only when the board is permanently inactive. Do not use archiving as a way to temporarily pause work — leave the board active and stop adding cards instead.

### Field: `created_at`
Set automatically at creation. Do not modify manually.

### Field: `columns`
Design your columns to represent the real stages your work goes through. Columns should be ordered left to right from "not started" to "done". Every board must have at least a starting column and a completion column.

---

## Recommendations (Do's and Don'ts)

**Do's:**
- Keep the board focused on a single type of work or a single area of responsibility.
- Review and update the `context` field whenever the team, cadence, or priorities change.
- Limit the number of columns to what you actually use — between 3 and 7 is ideal.
- Archive boards that have been inactive for more than 30 days.
- Make the board visible and accessible to everyone involved in the work.

**Don'ts:**
- Don't create one board for all types of work mixed together without a clear structure.
- Don't leave the `description` and `context` empty — they are essential for meaningful AI assistance.
- Don't create more than 8 columns — it signals that the workflow needs simplification, not more stages.
- Don't delete a board with historical cards — archive it instead.
- Don't use vague names that require opening the board to understand its purpose.

---

## Validation Checklist

- [ ] `name` is specific and self-explanatory without needing to open the board.
- [ ] `description` explains the purpose in one or two sentences.
- [ ] `context` contains enough background for an outside reader to understand the work environment.
- [ ] The board has at least 2 columns.
- [ ] Column order represents a logical left-to-right workflow progression.
- [ ] The board scope is focused — it does not mix unrelated types of work.

---

## EXAMPLES

### EXAMPLE 1

```
name: Personal Weekly Goals
description: Tracks personal and professional tasks for a self-employed consultant on a weekly cycle.
context: Solo consultant working across 3 active clients. Week runs Monday to Friday. Tasks are reviewed every Sunday evening. High-priority items are client deliverables with deadlines; medium are proactive improvements; low are nice-to-haves.
archived: false
columns: [Inbox, This Week, Today, Done]
```

### EXAMPLE 2

```
name: Home Renovation Project
description: Manages all tasks related to the kitchen and living room renovation, coordinated between the homeowner and two contractors.
context: Renovation runs for 8 weeks. Owner handles purchasing and decisions; contractors handle execution. Tasks blocked by supplier delays are common. Budget approval is required before any purchase above $500.
archived: false
columns: [Backlog, Waiting for Approval, In Progress, Done]
```
