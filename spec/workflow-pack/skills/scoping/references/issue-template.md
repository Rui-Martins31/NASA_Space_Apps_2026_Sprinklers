# Issue template

Copy this, fill the `<placeholders>`, delete the sections that don't apply.

Sections are marked **required** or **optional**. The required ones — a problem/context statement
and real file citations — are what make an issue executable. The optional ones are **earned**: add
them because the situation demands it, not because the template lists them.

Do **not** add labels, milestones, or assignees unless the project actually uses them. List what
the tracker defines first (`glab label list` on GitLab, or the equivalent in your tracker's
interface skill).

**No tracker?** This same skeleton is the file you write. Save each issue as its own markdown file
under `issues/` — one file per issue — instead of filing it. Nothing else about the structure
changes.

---

**Title:** `<Area>: <specific finding, stated as a finding not a topic>`

> Good: `Scenarios list page never refreshes run status — only opening a scenario re-checks it`
> Bad: `Fix scenarios page`

```markdown
## Problem                                                          <!-- REQUIRED -->

<What is wrong, concretely. The user-visible symptom first, then the mechanism.>
<Cite the real code: `path/to/file.py:120`. Always a file; a line number where you can.>

<!-- Use `## Context` instead when nothing is broken and you're specifying new work. -->

## Why it matters                                                   <!-- OPTIONAL -->

<Who is hurt, and how. Skip if the Problem section already makes it obvious.>
<This is also where you pre-empt the reviewer's "isn't this trivial / isn't this just UI?"
 objection — cite the doc or rule that makes it real work.>

## Proposal                                                         <!-- REQUIRED -->

<What to build or change. Name the real symbols and files it lands in.>
<Give the why inline, not as a separate essay.>

## Reference                                                        <!-- REQUIRED -->

- `docs/<relevant-doc>.md` — <what it says that governs this>
- `path/to/<file>.py` — <the canonical definition this must match>

## Ask                                                              <!-- REQUIRED -->

<!-- Or `## Acceptance criteria`. Use a checklist so the implementing change request can tick it off. -->

- [ ] <criterion 1 — observable, not "works correctly">
- [ ] <criterion 2>

## Tests                                                            <!-- REQUIRED if it has boundaries -->

<!-- The highest-value section in this template, and the most often skipped. When it's here, the
     implementing change request reports back against exactly these cases. Make it standard. -->

- **Boundary cases** — state the exact values and the expected classification:
  - <input at the boundary> → `<expected>`
  - <input one step past it> → `<expected>`
  - <input with a NON-DEFAULT config value> → <expected shifts accordingly — proves it isn't
    hardcoded>
- **Coverage** — <each distinct position/shape the change must handle>
- **Degenerate cases** — <empty, zero, one, missing — and what the expected behaviour IS,
  decided here rather than left to the implementer>
- **Integration** — <the API/route-level test that proves it end to end>
- **Consistency regression** — <if this duplicates an existing computation, the test that stops
  the two drifting apart>

## Decision (confirmed)                                             <!-- OPTIONAL -->

<!-- Record decisions already made, so nobody relitigates them.
     This is the issue's teaching surface — see /teach-me. Name the fork you took AND the one you
     rejected, one line each. The reader learns the trade-off for free, and nobody reopens it in
     six weeks. -->

<Decision, the one-line reason, and the alternative you rejected. e.g. "Measures, not pass/fail —
the goal is to guide a planner, not to grade them.">

## Open questions                                                   <!-- OPTIONAL -->

<!-- Park genuine unknowns openly rather than guessing. If the whole issue is
     blocked on an answer, say "Placeholder issue" in the first line and mean it. -->

- <question, and what it blocks>

## Out of scope                                                     <!-- OPTIONAL -->

<Explicitly excluded work, NAMING the sibling issue that covers it — #N.>

## Related                                                          <!-- OPTIONAL -->

- #<N> — <how it relates>
```

---

## Checklist before you file

- [ ] Title states a finding, not a topic
- [ ] At least one real file cited (ideally `file.py:line`)
- [ ] The governing doc referenced, if one exists
- [ ] **Nothing here contradicts the docs.** If it does: you flagged it, the user ruled, and
      fixing the doc is in this issue's scope — or it's written out under `## Open questions`
      with both readings. Never silently left wrong.
- [ ] Tests specified with actual boundary values, including a non-default case
- [ ] Out-of-scope work named, with its sibling issue
- [ ] No invented labels/milestones/assignees
- [ ] An agent could execute this cold, without asking you anything
