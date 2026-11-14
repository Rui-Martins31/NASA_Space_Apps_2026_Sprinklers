---
name: scoping
description: "Turn a rough ask into a filed issue an agent can execute unattended — in whatever tracker you use (GitLab, GitHub, Jira, Azure DevOps), or a markdown file if there's no tracker. Read the docs first, answer what you can yourself, ask only the genuine unknowns, then write the issue with real file citations and a test spec. Use for small and medium changes, bug reports, and follow-ups. For greenfield or a big architectural pivot, use /extensive-interview instead."
trigger: /scoping
---

# /scoping

A well-scoped issue is one an agent can pick up cold and execute end to end, without coming
back to ask you anything. That is the bar.

Getting there is mostly **research, not conversation**. The questions you ask are what's left
over after you've answered everything you could yourself.

## The flow

1. **Read the docs.** Not after — first.
2. **Answer everything you can** from the docs and the code.
3. **File the verified bugs** you found on the way. Don't ask about them.
4. **Ask only the genuine delta** — the unknowns research cannot close.
5. **Write the issue**, citing real files and specifying the tests.

## 1. Read the docs first

**Docs are the source of truth.** Before you scope anything, read the docs covering the area
you're touching — the route table, the component list, the implementation contract, the data
model, the rules doc. Whatever exists.

**Cite the requirement, not a paraphrase.** If the project has numbered requirements, the issue
names them: *"Implements FR-RUN-4"* beats a paragraph restating it, and it makes the chain
traceable end to end:

```
FR-<AREA>-<n>  →  issue (cites it)  →  change-request test plan  →  test
```

If you can't find a requirement your change serves, that's worth a beat: either one is missing,
or the change is (`/review-gate`, rung 1 — does this need to exist at all?).

**If there are no docs at all**, don't quietly proceed on vibes and don't write the missing docs
yourself mid-scope. Say so, and pick deliberately: for a genuinely small change, note the absence
in the issue and cite the code instead. If the area is big or contested enough that the absence
is *why* it's hard to scope, that's the signal for `/extensive-interview` and
`references/docs-bootstrap.md` over there — not a bigger guess.

**A question already answered in the docs is a cost, not a courtesy.** It burns the reviewer's
attention on something they already wrote down, and it signals you didn't look.

This cuts the other way too: if the docs *are* clear, the design is settled. Don't reopen it as
an open question just because you'd have done it differently. A divergence between the docs and
what you want to build is a thing to reconcile explicitly, not to quietly decide alone.

### If something contradicts the docs, flag it — don't route around it

Scoping is where contradictions surface, because it's the one step that reads the docs and the
code together. You'll hit these:

- **The code does something the docs say it doesn't.** (Often the docs were right when written.)
- **The ask contradicts a documented decision.**
- **Two docs disagree**, or the same word means two different things in two places.

**Don't route around it.** Don't file the issue against what the code happens to do and leave the
doc lying, and don't file against the doc and let the implementer discover reality on their own.
Both bury the problem in someone else's afternoon.

**Instead:**

1. **Flag it to the user before filing**, quoting both sides with their locations — *"`docs/<file>.md`
   says X; `<file>.py:120` does Y. Which is right?"* Quote, don't paraphrase.
2. **Let them rule.** Which is authoritative, and is the other stale, wrong, or a different thing
   wearing the same name? It's their call, not yours — and it's usually a ten-second answer.
3. **Then fix the doc**, in the same breath as filing the issue. If the doc was wrong, correcting
   it *is* part of the work — put it in the issue's scope explicitly, so it can't be dropped.

**Never leave a known inconsistency in the docs.** A doc with one known-false line in it isn't a
source of truth anymore — it's a thing everyone has learned to double-check, which costs more than
having no doc at all. If it's genuinely unresolved, it goes into the issue's `## Open questions`
with both readings written out, not into silence.

The cheap tell you're routing around one: you catch yourself writing "the docs say X, but
actually…" anywhere in the issue. That "but actually" is a doc bug you just decided not to fix.

## 2. Research collapses the question count

Every question you can answer yourself, answer yourself.

Read the client's requirement documents before scoping an offline-mode feature and a ten-question
list collapses to one: *"now the one real question before drafting."* That's the shape to aim for.
The research does the work the interview would otherwise have done badly.

The inverse is the tell: a long question list usually means shallow reading, not thoroughness.

## 3. File bugs, don't ask about them

If your research turns up a **verified** bug — you traced it, you can point at the line — file
it as its own issue and move on. Don't put it in the question list.

File them, and the questions you *do* ask come back answered cleanly and in full — because none
of them are triage the reader could have done themselves.

**Don't make the user triage.** Escalate decisions, not findings.

## 4. Ask only the genuine delta

When you do ask:

- **Four questions maximum** if you're using an options prompt. Longer thematic lists are fine
  in prose, but only after deep research.
- **Number them.** Numbered questions earn numbered answers, every time — including rejections.
- **Group by theme**, with a bold header per group.
- **Name the conflict inside the question**, with evidence. Never make the reader reconstruct
  why you're asking. "The client doc says X, the schema says Y, your rule 1 says Z — all three
  are live right now" costs you a sentence and saves them five minutes.
- **State your instinct and label it as yours.** *"My instinct: X — but it's your call."*
  *"That's my read, so I want it confirmed rather than assumed."* This is the highest-yield
  habit in the whole skill: it converts a question into a one-second confirmation.
- **Say what the answer unblocks.** "This decides whether we need incremental recompute
  machinery at all."
- **Rank your own blockers** when you ask several: "those three change the issue's shape most."

### The out-of-repo escape hatch

**This is the single most common way scoping questions fail.**

Before you offer a multiple choice, ask yourself: *could the answer depend on infrastructure or
context that doesn't exist in this repo?*

The classic failure: you offer four options on how the app talks to the optimizer, or how auth
works, or where it deploys. Every option is reasonable. Every option is wrong — because the real
answer is infrastructure only the user knew about: an internal optimization platform, Keycloak,
the internal deployment pipeline. None of it was inferable from the repo, so no amount of careful
option-writing was ever going to land it.

So when the answer might live outside the repo:

- Ask **openly**, not as a multiple choice, or
- Include an explicit **"something already exists here that I can't see"** option, and
- Label the group honestly: **"<platform> state (I can't see this from the repo)"**. That header
  is the fix — it tells the reader exactly which questions only they can answer, and stops you
  dressing up a knowledge gap as a design choice.

Conversely, when you've fully characterized a genuine technical fork — two libraries, two
architectures, and you understand both — a multiple choice with a labeled **(Recommended)** pick
is exactly right, and gets picked cleanly.

### Surface your assumed constraints

The costliest corrections are never the questions you asked badly — they're the assumptions you
never surfaced at all. Two real ones:

- An agent proposed a module structure as settled fact, never asking how it should be organized.
  The user rewrote it wholesale: *"I would organize things a little bit differently."*
- An agent silently treated data preservation as a hard constraint. It wasn't, and had never been
  stated: *"There isn't an issue with losing data to achieve that."*

If you're treating something as fixed, say so: **"I'm treating X as a hard constraint — correct
me if not."** An unstated constraint is invisible until it's cost you a branch.

## 5. Write the issue

Use `references/issue-template.md` as the skeleton and `references/issue-exemplar.md` as the
worked example.

- **Title: `Area: specific finding`.** State the **finding**, not the topic. Long and specific
  beats short and vague. *"Scenarios list page never refreshes run status — only opening a
  scenario re-checks it"*, not *"Fix scenarios page"*.
- **Cite real files** — the source file, the governing doc, and `file.py:line` where you can.
  An issue that names no file is a wish, not a spec.
- **Record decisions, park unknowns.** `## Decision (confirmed)` and `## Open questions` are
  both honest. A placeholder issue should say it's a placeholder rather than fake a spec.
- **Say why this way, not just what.** When you settled a fork — a package, a layer, a data
  structure — name the option you took *and* the one you rejected, one line each. This is the
  issue's teaching surface: the next person reads it as part of picking up the work, learns the
  trade-off for free, and doesn't reopen the decision in six weeks. See `/teach-me` — a couple of
  lines here is worth more than an essay nobody reads later.
- **Check the project's conventions before inventing any.** Some projects define zero labels and
  zero milestones — in those, don't invent a taxonomy. List what the tracker actually defines
  before you reach for metadata (`glab label list` on GitLab, or the equivalent in your tracker's
  interface skill — see `/using-glab` for the GitLab one).

**No tracker? Write the issue to a markdown file instead.** Everything above still holds — the
docs research, the citations, the test spec — it just lands as a file rather than a filed issue.
Put each issue in its own file under a local `issues/` directory (e.g. `issues/<area>-<slug>.md`),
**one file per issue** — a bug you found on the way (step 3) is its own file, not an appendix to
this one. The file *is* the spec an agent picks up; keep the same structure the template gives.

### Specify the tests — this is the pattern worth stealing

Most issues never spec their tests. The ones that do are the ones that go right: **when the
issue names the boundary cases, the implementing change request reports back against exactly those cases.**
That mirroring is the most valuable convention in this skill, and it's rare because people forget
it, not because it doesn't work.

**Make it standard.** Write the boundaries in the issue:

> - gap = 180min → `"break"` (exclusive lower bound)
> - gap = 181min → `"rest_room"`
> - gap = configured cap exactly → `"violation"`
> - a **non-default** cap (e.g. 200) shifts the boundary accordingly — proves it isn't hardcoded

That last line is the one that earns its keep: it specifies a test that catches a hardcoded
constant, which the happy path never will. The change request then checks each case off by name.

See `/test-design` for what makes those cases good.

## Anti-patterns

- Asking a question the docs already answer.
- Offering four reasonable options when the real answer is infrastructure you can't see.
- Handing the user a list of findings to triage instead of filing them yourself.
- An issue with no file citations — nobody can start from it.
- Writing "the docs say X, but actually…" instead of getting the doc fixed.
- Filing against what the code does and leaving the contradicting doc standing.
- Inventing labels, milestones, or an assignee scheme the project doesn't use.
- Leaving tests to the implementer's imagination when you know the boundaries.
- Scoping a greenfield or architectural pivot as if it were a small change — that's
  `/extensive-interview`, not this.

## Related

- `/extensive-interview` — when the ask turns out to be greenfield, a big pivot, or a new
  critical domain, and the docs don't cover it
- `/test-design` — what to put under `## Tests`
- `/teach-me` — for the "why this way" rationale that belongs in the issue
- `/good-mr` — the change request that closes this issue mirrors its test spec back
- `/using-glab` — filing it on GitLab (`glab issue create`, and the flags that actually work);
  on another tracker, the equivalent lives in that tool's interface skill
- `/delivery-loop` — where scoping sits in the end-to-end flow
