---
name: good-mr
description: "Write a change request (an MR on GitLab, a PR on GitHub / Azure DevOps) a reviewer can trust — a summary stating the user-visible effect, a test plan citing real commands and real counts, and honest disclosure of what you did NOT verify. Use when opening or updating a merge/pull request, or when its description needs rewriting before review."
trigger: /good-mr
---

# /good-mr

A change request is an argument that a change is safe to land, addressed to someone who wasn't
there when you made it.

> **"Change request"** is the tracker-neutral name for the reviewable unit — a *merge request* on
> GitLab, a *pull request* on GitHub / Azure DevOps. The command examples use `glab` as the
> default flavor; the mechanics for your tracker live in its interface skill (see `/using-glab`).

The reviewer's real question is never "what did you change?" — the diff says that. It's **"what
do you know that I can't see, and what don't you know?"** Everything below serves that.

## The shape

Two sections carry almost every change request: `## Summary` and `## Test plan`. Anything else is earned.

```
## Summary            ← Closes #N, then the user-visible effect, then bullets
## Test plan          ← real commands, real counts, unchecked boxes for what you skipped
```

For a bugfix, split the Summary:

```
## Problem            ← the symptom a user would report, then the mechanism
## Fix                ← what you changed and why this approach
## Test plan
```

Use `references/mr-template.md` for the skeleton, `references/mr-exemplar.md` for a worked
example.

## Titles

Two forms, and **the split tracks size, not taste**:

Every title starts with the team's area prefix — `[BACKEND]`, `[FRONTEND]`, `[DATASET]` or
`[TOOLS]` — exactly as commits do.

- **`[AREA] Imperative summary`** for surgical changes — the common case.
  `[FRONTEND] Stop overnight bar overlapping the next day's break`
- **`[AREA] Imperative prose (#N)`** for large ones — a migration, a rewrite, a multi-issue
  landing. `[BACKEND] Migrate pairing engine to integrated-MILP model + reconfig (issues #73, #82, #84)`

A surgical fix under a grand prose title reads as overclaiming; a rewrite squeezed into a
one-line fix title reads as sneaking it past.

Titles are imperative: *Add, Fix, Migrate, Remove, Store, Export*. See `/commit-message` — the same convention governs both, and a merge
commit's first body line is the change request's title.

## Linking issues

`Closes #N.` goes on the **first line of `## Summary`**, before the prose.

> The `Closes #N` / `!N` syntax below is **GitLab/GitHub's**, the default flavor here. Jira uses
> smart-commit verbs and issue keys (`Closes PROJ-123`); Azure DevOps uses `Fixes AB#123`. Use
> whatever auto-links in your tracker — the discipline (link every issue, be explicit about
> partial work) is the same; only the token changes.

- **Repeat the keyword per issue.** `Closes #61, Closes #62, Closes #63` — **never**
  `Closes #61, #62`. Only the first one closes.
- **Scope partial work explicitly** rather than letting it auto-close something it didn't
  finish: *"Closes #76 (frontend half — the backend endpoint landed in !110, already merged)"*.
- **`Part of #58, part of epic #60.`** when it closes nothing.
- Reference sibling change requests as `!N` (GitLab) / `#N` (GitHub).

## The Summary

Lead with the **user-visible effect**, not the implementation. "The scenarios list showed runs
as still queued long after they'd finished" beats "refactored `list()` to call `_refresh()`".

Then bullets. Each one:

- **Cites the real symbol or path** — `RunService.list()`, not "the service layer". Precision is
  what makes a reviewer able to check you.
- **Gives the why inline.** Not in a separate design essay at the bottom; next to the thing.
- **Says which docs you updated**, in the same change. Name the paths.

## The Test plan

`- [x]` per check, each with a **real command and a real count**.

> `- [x] <full-suite command> — 398 passed`
> `- [x] <frontend test command> — 524/524 passing`
> `- [x] 5 new tests in <file> covering: <what each one proves>`

**Never write "tests pass".** It's the single least useful sentence in a change request: it's unfalsifiable,
and it's what someone writes when they didn't run them.

Name what each test *proves*, not that it exists. "covering: refresh progresses a run through to
done via `list()` alone, a terminal run isn't re-polled, the status filter re-applies after
refresh in both directions" tells the reviewer whether your coverage matches the risk.

**Disambiguate pre-existing failures, and say how you proved it.** Not "3 unrelated failures" —
*"3 failures, verified via `git stash` as present on main too"*, or *"confirmed byte-identical
to `origin/main`"*. The method is the point; the claim without it is just an assertion.

If the issue specified test cases (see `/scoping`), **check them off by name**. The issue said
what agreement would look like; this is where you demonstrate it.

## Disclose what you did not do

**This is the heart of the skill.** It's also the thing that most separates a change request a
reviewer can trust from one they have to re-do.

**Ship a deliberate unchecked box for anything you didn't verify.** Not an oversight — a marker:

> `- [ ] Manual smoke test against a live deployment (not done from this environment)`
> `- [ ] A real, full run through the compute server has not been observed end to end —
>   recommended before treating this as production-validated (see the caveat above).`

An unchecked box is **not** a confession of sloppiness. It's the highest-value line in the change request,
because it tells the reviewer exactly where to point their attention. A silent gap does the
opposite: it looks complete, and the reviewer finds out in production.

Beyond the checkbox, invent the section the situation needs:

- `## Scope (read before reviewing)` — when the diff is bigger than the ask, and you want the
  reviewer oriented before they start.
- `## Notable side effect` — when your change moved something else's blast radius. *"This
  endpoint also calls `list()` — it will now additionally catch a run that finishes during that
  same request. Flagging so reviewers know its blast radius moved too."*
- `## Verify-before-merge item (not blocking, but flagging)` — a residual risk you investigated
  but couldn't fully close, **with the reading behind it**.
- `## What's NOT in this change` — the deliberate omissions.
- `## Design decisions` — the fork you took and why (see `/teach-me`).

### Verify claims, don't relay them

When the issue, a comment, or another agent asserts something load-bearing — check it, and
**narrate the check**:

> *"**Verified, not trusted**, one claim in the issue comment: it said the overnight count is
> 'already computed per agent in `client_kpis()`'. That file and function no longer exist in
> this tree..."*

A claim you pass along becomes yours. If you couldn't verify it, mark it as unverified rather
than laundering it into the Summary as fact.

## Depth matches change surface

A big change request earns a big description. A trivial one doesn't need one — **but even a
one-liner carries its own evidence.**

A perfectly good change request can be two sentences with no headings and no test plan, as long as
it's purposeful: say *why* the change exists and link what it relates to. A one-paragraph change
request that carries a single fact and the evidence for it — *"A live test failed with a 404 at the assets
endpoint, confirming that app id was never valid"* — is complete.

The rule isn't "always write 2,000 characters". It's **never assert without evidence, at any
length**.

## Anti-patterns

- "Tests pass." (Which tests? How many? Did you run them?)
- `Closes #61, #62` — closes exactly one issue.
- A Summary that describes the diff instead of the effect.
- Bullets that say "the service layer" when they could say `RunService.list()`.
- Quietly omitting the thing you couldn't verify, so the change request looks complete.
- Relaying a claim from the issue as established fact without checking it.
- Docs left describing the old behaviour while the change request describes the new one.
- Padding a trivial change with ceremony — or shipping a substantial one bare.

## Related

- `/scoping` — the issue this change request closes; mirror its `## Tests` back in your test plan
- `/test-design` — what makes the tests you're citing worth citing
- `/review-gate` — run it before you open the change request, and again before you merge
- `/teach-me` — the "why this way" rationale that belongs in `## Design decisions`
- `/commit-message` — same title convention; the merge commit carries the change request's title
- `/using-glab` — `glab mr create` on GitLab (or your tracker's create command), and passing this
  description without the shell eating it
- `/delivery-loop` — where the change request sits in the end-to-end flow
