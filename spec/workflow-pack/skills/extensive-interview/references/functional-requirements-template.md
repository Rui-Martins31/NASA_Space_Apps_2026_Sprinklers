# Functional requirements — template

What the system **does**. One file, grouped by area, stable IDs.

Copy the skeleton below. Delete the areas that don't apply; add the ones that do. The structure
is what matters — the areas are examples.

> **Functional vs non-functional, the test that actually works:** if a user could *watch it
> happen*, it's functional. If it describes *how well, how fast, how safely, or built with what*,
> it's non-functional → `non-functional-requirements-template.md`.
>
> "The planner shall filter the schedule by date" — functional.
> "Filtering shall feel instant on the seeded dataset" — non-functional.
> Same feature. Two requirements. Two files. Don't merge them: they're checked at different
> times by different people, and merging is how performance quietly becomes optional.

---

## The skeleton

````markdown
# 2. Functional Requirements

Requirements are grouped by area and carry stable IDs (`FR-<AREA>-<n>`) for
traceability. Priority: **M** = must-have, **S** = should-have,
**C** = could-have (drop first if time-constrained).

---

## 2.1 <Area name> (`FR-<AREA>`)

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-<AREA>-1 | M | The <actor> shall <observable behaviour>. |
| FR-<AREA>-2 | S | The system shall <observable behaviour>, <qualifying condition>. |

## 2.2 <Next area> (`FR-<AREA2>`)

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-<AREA2>-1 | M | ... |
````

Common areas to consider — take what applies, don't force the rest:
data ingestion · each main view or screen · the core workflow (create/run/track something) ·
detail drill-downs · the end-user (non-admin) surface · auth & roles · reporting/KPIs.

---

## The rules

**IDs are stable and permanent.** `FR-DATA-6` means one thing forever. Never renumber to close a
gap — a retired requirement gets struck through or marked removed, not recycled. The ID is what
issues, change requests, and tests point at; renumbering silently re-points all of them.

**One requirement per row.** If it has an "and" joining two testable things, it's two rows. The
tell: you can't tick it off without saying "well, half of it."

**Use "shall", and name the actor.** "The planner shall…", "The system shall…". Not "should",
not "we want to". `shall` is a commitment; `should` is a hope, and hopes don't get tested.

**Write it observable.** Someone must be able to sit down and check it without asking you what
you meant. "The system shall handle errors gracefully" is not a requirement — it's a feeling.
"A failed run shall surface an error reason to the planner (verbatim string; no error taxonomy)"
is a requirement: you can look at the screen and see whether it's true.

**Priority is a real decision, not decoration.** **M** = the thing is broken/pointless without it.
**S** = clearly wanted, survives a bad week. **C** = drop first, and expect to.
If everything is M, you haven't prioritised — you've just written M forty times, and the first
schedule squeeze will make the call for you, badly.

**Record the cut, don't delete it.** When something is dropped, say so in place with one line of
why. A requirement that vanishes silently gets re-proposed in six weeks by someone who wasn't
in the room.

**Cite what governs it.** Link the rules doc, the data model, the client source, the issue. A
requirement that cites nothing is a claim.

**Bold the load-bearing words.** These get skimmed. `**28-day window**`, `**idempotent**`,
`**never exposed to the browser**` — the bold is what survives the skim.

---

## Where requirements come from, and where they go

```
interview / client docs  →  FR-<AREA>-<n>  →  issue (cites the FR)  →  change-request test plan  →  test
```

That chain is the whole point of the ID. Concretely:

- `/scoping` — an issue names the FR it implements. "Implements FR-RUN-4" beats a paragraph.
- `/test-design` — **every M requirement should be answerable by a test.** If you can't imagine
  the test, the requirement is too vague — fix it now, while it's a sentence.
- `/good-mr` — the change request closes the issue and reports the test back.

**If you can't trace a line of code to an FR, ask why it exists** (`/review-gate`, rung 1 of the
simplicity ladder: does this need to exist at all?).

---

## Refining an existing set

**Answers fold in; they don't start a parallel document.** A new fact from an interview becomes a
new numbered row in the area it belongs to. A second requirements doc is how a project ends up
with two sources of truth and no way to tell which won.

**A contradiction is a bug in this file.** If an answer contradicts a row, don't just add the new
one — flag it, get a ruling, and fix or strike the old row. Two rows that disagree are worse than
one row that's wrong, because the wrong one at least loses arguments. See `/extensive-interview`
("When an answer contradicts the docs").

**Propose cuts against the numbers.** "Cut FR-RUN-9 and FR-KPI-5" is actionable. "Simplify the
run flow" is a conversation you'll have three more times.

---

## Anti-patterns

- Renumbering to close a gap after a requirement is dropped.
- `should`/`could` where you mean `shall` — or `shall` where you mean "it'd be nice".
- Everything marked M.
- Requirements nobody could test without asking you what you meant.
- Two testable things joined by "and" in one row.
- Non-functional requirements smuggled in as functional ones ("shall load quickly").
- A second requirements doc, because editing the first one felt harder.
- Deleting a cut requirement instead of recording the cut.
