---
name: commit-message
description: "How to write a commit message that says what the commit contains and why, and points at the issue or comment it addresses. Conventional-commit subject, a why-first body, and Closes/Refs/Part of trailers. Use whenever you're about to commit."
trigger: /commit-message
---

# /commit-message

A commit message is the only explanation of your change that survives. The diff shows *what*
changed; nobody can reconstruct *why* from it six weeks later — including you.

**Almost every commit needs a body.** Subject-only is the exception, reserved for changes that
genuinely explain themselves.

## The shape

```
type(scope): imperative summary, lowercase, no period, ~70 chars

Problem or root cause first: the observed symptom, then why it happens.
Wrapped at 72 columns.

The fix, and why this approach instead of the obvious alternative.
Note explicit non-goals when a bigger change was deliberately avoided.

Verified: how you know it works.

Closes #N
```

## Subject line

**Type.** Pick from what your history actually uses. A working set:

| type | use |
|---|---|
| `fix` | a bug — the most common type by a wide margin |
| `feat` | new capability |
| `docs` | documentation only |
| `test` | tests only |
| `chore` | housekeeping with no runtime effect |
| `ci` | pipeline config |
| `perf` | performance work |
| `refactor` | behaviour-preserving restructure |
| `ops` | deployment/infra |
| `data` | seed files, fixtures, data assets — a real and useful type |

Compound types are legitimate when a change genuinely is both: `test+docs:`.

**Scope.** Name the target, and hold one spelling for it:

- **underscore for code packages** — `backend`, `webapp`, `data_pipeline`, `solver_engine`
- **hyphen for UI feature areas** — `search-panel`, `user-settings`
- **comma-separate for multi** — `feat(backend,webapp):`

Adopt whatever split your project already uses. The rule that matters is the next one.

**Scope drift is a real cost.** Spell the same package with an underscore in some commits and a
hyphen in others and both stay readable — but together they make `git log --grep` lie to you.
You search one spelling and silently miss everything filed under the other. Pick one spelling per
target and never vary it.

**Style.** Imperative ("add", "fix", "stop", "drop", "replace"), lowercase after the colon, no
trailing period.

**Length: target ~70–72 characters, not the textbook 50.** This is deliberate and
counter-conventional. A 50-char cap forces vagueness; `fix(pairing-board): stop overnight bar at
next day's SoS, not its train` is 71 characters and tells you the whole story. Take the room.

Exception to lowercase: when the first word is an identifier or proper noun, keep its real
casing — `fix(air): AIR_APP_ID was a typo`, `GET /runs lazily refreshes status`.

## Body — why first

Skip it only when the change is genuinely trivial. Otherwise, three paragraphs:

**¶1 — the problem or root cause.** Lead with the observed symptom, ideally the live one:
"both seeded scenarios still showed 'Double rest days: 0' for every agent live". Then why it
happens. Someone reading this in a year needs the *situation*, not your solution.

**¶2 — the fix, and why this approach.** Name the alternative you rejected — **"instead of"** is
the phrase doing the work, and it's what turns a description into an explanation. State non-goals
too, when you deliberately avoided a bigger change.

**¶3 (optional) — consequences, and a `Verified:` line.** Add an explicit `Verified:` note
whenever "it works" isn't self-evident from the diff.

Bullets use `- ` only. Never `*`, never `1.`. Wrap at 72.

## Pointing at the issue

Trailer on the **last line of the body**:

- `Closes #N` — this commit resolves it
- `Refs #N` — related, doesn't close it
- `Part of #N` — one piece of a larger issue or epic

> The `Closes #N` form is **GitLab/GitHub's**, the default flavor here. Jira reads smart-commit
> verbs against an issue key (`Closes PROJ-123`); Azure DevOps links with `Fixes AB#123`. Use
> whatever your tracker auto-links — the rule (one keyword, applied consistently, greppable) holds
> regardless of the token. If there's no tracker, point at the issue's markdown file by path.

Repeat the keyword per issue: `Closes #61, Closes #62`. Never `Closes #61, #62` — the second
number doesn't link.

**Never `Fixes #N`.** `Closes` is the convention. Pick one keyword and be consistent, so a reader
can grep for it.

Subjects may also carry the reference inline: `(#76)` or `(issue #84)`. Both are fine; the
trailer is what does the linking.

If you're addressing a **review comment** rather than an issue, say so in the body and quote the
claim you're responding to. "Addresses the review note about X" is a WHY that would otherwise be
invisible.

## Two strong examples

Both from a real history. The first is verbatim; the second has one internal path abstracted out
and is otherwise unchanged.

```
fix(pairing-board): stop overnight bar at next day's SoS, not its train

The overnight bar extended to the next day's first trip departure, but
when check-in (SoS) happens before that train, the backend already
renders that SoS→train gap as its own break block -- so the bar drew
right on top of it (the overlap reported live on the Pairing board).

Stop it at SoS instead: mathematically identical to the break block's
own left edge, so the two spans meet exactly with no gap and no
overlap. Regression test asserts that relationship (overnight.right ==
break.left) directly, since a same-block position check can't catch a
neighboring block being overlapped.
```

*Why it works:* symptom ("the overlap reported live") → root cause → the fix with its
justification ("mathematically identical to...") → and then it explains **why the test is shaped
the way it is**, which is the question a reviewer would otherwise have to ask.

```
data(seed): regenerate seed.db so double-rest days are actually populated

The committed seed.db predates the double-rest reconstruction fix in
air_output_translation.py, so both seeded scenarios still showed
"Double rest days: 0" for every agent live, even after that fix
merged -- the fix only changes what NEW imports produce, not data
already baked into this file.

Rebuilt via the exact same pipeline HydrationService.run() uses on a
fresh DB (importer.py + real_scenario_seeder.py), not a hand-patch:
deleted seed.db and re-seeded through the real translate_engine_output
-> import_results -> KpiService.compute path. Verified byte-identical
row counts and cached KPI values across every other table -- the only
change is assignment.state, with 268 rest days correctly reclassified
to double_rest in each of the two scenarios (1284 total 28-day rest
days now split as expected).
```

*Why it works:* it explains why an **earlier fix was insufficient** — the subtlest kind of why —
then names the rejected alternative ("not a hand-patch") and evidences the verification with real
numbers. The reader never has to trust it.

## Two weak examples

```
fix: Fix backend Dockerfile
```

The subject restates its own type and carries zero information. This one came from a run of ten
near-identical commits — `fix: New fix for backend Dockerfile`, `fix: Fix to backend Dockerfile`
three times over — which is what a message like this always signals: someone iterating blind
against CI and narrating each attempt.

```
Add .db and some fixs
```

No type, vague, and it bundles unrelated work so no part of it can be reverted independently.

**The lesson behind both: a commit that can't say why is usually a commit that hasn't finished
thinking.** If the body won't come, that's information — you probably don't yet know what you
fixed, or you've bundled two changes that want to be separate commits.

## Anti-patterns

- Subject-only on a change that isn't self-evident.
- A subject that restates the type (`fix: fix the thing`).
- Describing *what* the diff already shows, instead of *why*.
- `Fixes #N`, or `Closes #61, #62` (only the first links).
- Padding to 50 characters and losing the actual finding.
- Varying the scope spelling for the same target.
- Bundling unrelated changes so neither can be reverted alone.
- Narrating CI attempts as a commit series instead of squashing them.

## Related

- `references/commit-template.md` — copy-pasteable skeleton
- `/good-mr` — the change request description this rolls up into (same why-first instinct, more room)
- `/review-gate` — verifying the claims before you commit them
- `/scoping` — the issue this commit points at
- `/delivery-loop` — where committing sits in the end-to-end flow
