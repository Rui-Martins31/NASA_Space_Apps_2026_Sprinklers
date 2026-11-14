# Change request template

Copy this, fill the `<placeholders>`, delete what doesn't apply.

"Change request" is the tracker-neutral name for the thing you're opening — a **merge request** on
GitLab, a **pull request** on GitHub / Azure DevOps. The skeleton is the same everywhere; only the
issue-linking syntax (`Closes #N` / `!N` below) is GitLab/GitHub's — swap it for your tracker's.

Two sections are load-bearing: `## Summary` and `## Test plan`. Everything else is **earned** —
add a section because the situation demands it, not because the template lists it.

---

## Title

Pick by size — the split tracks change surface, not taste:

| Change | Form | Example |
|---|---|---|
| Surgical | `type(scope): imperative summary` | `fix(pairing-board): stop overnight bar overlapping the next day's break` |
| Large | `Imperative prose (#N)` | `Migrate pairing engine to integrated-MILP model + reconfig (issues #73, #82, #84)` |

Scope = package or feature area, never a layer. Imperative mood: *Add, Fix, Migrate, Remove*.

---

## Standard skeleton

```markdown
## Summary

Closes #<N>.

<!-- Repeat the keyword per issue: `Closes #61, Closes #62` — NEVER `Closes #61, #62`.
     Partial: `Closes #<N> (frontend half — backend landed in !<M>, already merged)`.
     Closes nothing: `Part of #<N>, part of epic #<M>.` -->

<Prose lede: the USER-VISIBLE effect, in one or two sentences. What someone would notice —
 not what you refactored.>

- **`<RealSymbol.method()>`** — <what changed, and the why inline>.
- **`<path/to/file>`** — <what changed, and the why inline>.
- `docs/<file>.md` updated to <what it now says>.

## Test plan

- [x] `<the real command you ran>` — <the real count: "398 passed">
- [x] <N> new tests in `<file>` covering: <what each one PROVES, not that it exists>
- [x] <the issue's specified boundary cases, checked off by name>
- [ ] <anything you did NOT verify — say so plainly, with why>
```

---

## Bugfix variant

```markdown
## Problem

<The symptom someone would report — the user-visible failure first.>

<Then the mechanism: the real symbol, the real reason. Why it LOOKS like it works
 (`<Thing>` polls every 4s) but doesn't (it re-reads the same stale row forever).>

## Fix

`<RealSymbol.method()>` now:
- <change 1, with the reasoning inline>
- <change 2 — including any ordering/timing subtlety and why it matters>

`docs/<file>.md` updated to <what it now says>.

## Test plan

- [x] ...
```

---

## Earned sections — add only when the situation calls for it

```markdown
## Scope (read before reviewing)

<When the diff is wider than the ask — orient the reviewer before they start.>

## Notable side effect

<When your change moved something ELSE's blast radius. Volunteer it.
 "`<other endpoint>` also calls `<method>` — it will now additionally <effect>. Flagging so
 reviewers know its blast radius moved too.">

## Verify-before-merge item (not blocking, but flagging)

<A residual risk you investigated but couldn't fully close — WITH the reading behind it.
 "Checked <source>: <what you found>. Worst case is <X>, not <Y>. Considered safe for this
 scale, but flagging since <what your tests can't exercise>.">

## What's NOT in this change

<Deliberate omissions, and where they went (#N / !M).>

## Design decisions

<The fork you took and why — see /teach-me. One or two, not an essay.>

## Notes / found along the way

<Things you discovered that the reviewer should know but that aren't this change's job to fix.
 File them as issues and link them.>
```

---

## The test plan, in detail

**Never write "tests pass."** Cite the command and the number.

Good:
- `- [x] <full suite command> — 398 passed`
- `- [x] <frontend test command> — 524/524 passing`
- `- [x] 5 new tests in <file> covering: refresh progresses a run to done via list() alone, a terminal run isn't re-polled, the status filter re-applies after refresh in both directions`

**Pre-existing failures — say how you proved they're pre-existing:**
- `- [x] 3 failures unrelated to this change — verified via `git stash` as present on main too`
- `- [x] <file> confirmed byte-identical to `origin/main``

**Unchecked boxes are a feature, not a confession:**
- `- [ ] Manual smoke test against a live deployment (not done from this environment)`
- `- [ ] A real end-to-end run has not been observed — recommended before treating this as production-validated (see the caveat above)`

An unchecked box tells the reviewer where to look. A silent gap looks complete and isn't.

---

## Checklist before you open it

- [ ] Title form matches the change's size
- [ ] `Closes #N.` on the first line of Summary, keyword repeated per issue
- [ ] Lede states the user-visible effect, not the refactor
- [ ] Bullets cite real symbols, with the why inline
- [ ] Docs updated in this change request, and named
- [ ] Every test-plan line has a real command and a real count
- [ ] The issue's specified test cases checked off by name
- [ ] Everything you didn't verify is an unchecked box, not an omission
- [ ] Any claim you inherited from the issue was checked, and the check narrated
