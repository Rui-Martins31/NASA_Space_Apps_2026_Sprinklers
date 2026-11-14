---
name: delivery-loop
description: "The end-to-end sequence for shipping one issue: get latest → branch → implement → test → open a change request → independent review → merge → clean up → verify live. Use when starting work on an issue, when you're unsure which step comes next, or when learning how work ships here. This is the connective tissue the other skills hang off — it owns the order and the gates, they own the detail."
trigger: /delivery-loop
---

# /delivery-loop

**One issue. One branch. One change request.**

This is the sequence work ships through. Each step points at the skill that owns its detail —
this skill owns the **order**, and the **gates** between steps. The steps aren't ceremony: each
one catches a class of failure the next step can't.

> Throughout: **"change request"** means whatever your tracker calls the reviewable unit of change
> — an MR on GitLab, a PR on GitHub / Azure DevOps. The mechanics live in your tracker's interface
> skill (`glab` on GitLab — see `/using-glab`; the equivalent CLI elsewhere), which is the default
> flavor in the examples below.

## The sequence

```
get latest
  → branch per issue
  → implement (read the docs first)
  → full suite + typecheck + lint
  → open the change request (closes the issue)
  → independent review
  → conflict-check against main
  → mark ready → merge
  → switch back to main, pull, drop the branch
  → verify it's actually live
```

## 1. Start from an issue

If there isn't one, write one first — see `/scoping`. The issue is what makes the work small
enough to execute unattended, and it's what the change request closes.

**One issue = one branch = one change request.** If the work doesn't fit that, it's two issues.

## 2. Get the latest — before you read anything

`git fetch`, then confirm you're actually current, *before* reading code or planning. A stale
checkout wastes the whole loop: a shared checkout once sat **88 commits behind** `origin/main`,
and the research done against it described a file structure that no longer existed. Everything
downstream of that was wrong and nobody noticed until the change request.

Check you're current first. It costs one command.

## 3. Branch per issue

Branch off an up-to-date `main`, named for the work:

```bash
git switch main && git pull
git switch -c fix/<n>-<short-slug>      # or feat/, docs/, chore/, test/
```

Isolation is the point: an abandoned attempt costs nothing, and `main` always stays shippable.
Never commit straight to `main` — even for a one-liner, even when you're sure.

**Never mix two issues on one branch.** It sounds efficient and it isn't: the change request
becomes un-reviewable, the `Closes #N` trailer can only be honest about one of them, and if one half
needs reverting you can't. If you find a second bug while working, file it (`/scoping`) and leave
it.

> **When you're ready for more: worktrees.**
> Once branches are second nature — and especially once you're running several agents at once —
> `git worktree` gives each branch its own directory, so parallel work can't collide and you
> never stash to switch tasks. Swap step 3 and step 9 for worktree equivalents when you get
> there. Nothing else in this loop changes.
>
> **One hazard, if you do:** never `cd` to the main checkout from inside a worktree session — not
> even briefly, not even to "just compare." A `cd <main> && git stash -u` really did stash
> someone's untracked files in their real checkout. Some harnesses reset the working directory
> **after** the command already ran there: the reset protects the *next* command, it doesn't undo
> the one that just ran. If you need pre-change state, use `git show <ref>:<path>` or
> `git diff <ref> -- <path>` — read without mutating another working tree.

## 4. Implement

**Read the relevant docs before writing code**, not only update them after. Docs state
authoritative conventions and gotchas the code alone doesn't reveal — and they're the source of
truth, so a divergence is a bug to reconcile, not a judgment call you get to make alone.

**Update the docs in the same change.** Not a follow-up. See `/review-gate` lens 2.

**Follow the simplicity ladder** for anything you add — `/review-gate` owns it, rung 1 ("does
this need to exist at all?") through rung 7 ("the minimum code that works"). The most common
slop is reimplementing what already lives a few files over.

**Test during the build, not as cleanup** → `/test-design`.

## 5. Full suite + typecheck + lint

Run the project's full suite, typecheck, and lint before the change request — not just the tests you touched.

- **Scope lint runs to the files you changed**, not the whole repo.
- **If there are pre-existing failures, prove they're pre-existing** — check the same commit on
  main and say so explicitly. Never let someone else's red blur into yours; that's how a real
  regression hides.
- Cite the **real command you ran and the real count**, here and in the change request.

## 6. Open the change request

Open it as a draft, and have it close the issue.

- `/good-mr` owns the description — the summary, the test plan, and the honest disclosure of
  what you did *not* verify.
- **Your tracker's interface skill owns the mechanics** (heredocs, flags, the escape hatch for
  what the CLI can't express). `/using-glab` is the GitLab one; on GitHub / Jira / Azure DevOps
  it's that tool's CLI.
- `/commit-message` owns the commits underneath it.

## 7. Independent review — before merge

→ `/review-gate`. Spawn a *separate* agent; an implementer reviewing its own diff shares its own
blind spots.

This step has a known failure mode: **on long sessions it quietly lapses** because nobody
restated it. **A lapse is a bug in the process, not an acceptable shortcut.** Apply it to every
unit of work, every time.

Post the review to the change request when your tracker's CLI is available — a review that lives
only in a session transcript is invisible next week.

## 8. Conflict-check, mark ready, merge

- Get the latest changes from main again and **conflict-check** before merging.
- **A draft change request refuses to merge.** Mark it ready first — on GitLab that's
  `glab mr update <n> --ready`, then `glab mr merge <n> --yes`; other trackers have the same
  ready-then-merge two-step in their own CLI.

## 9. Clean up

Get back to a clean starting point, so the next task doesn't inherit this one's mess:

```bash
git switch main && git pull
git branch -d fix/<n>-<short-slug>      # -d, not -D: it refuses if the work isn't merged
```

Use `-d` deliberately. It's a safety net — if it refuses, your work isn't actually merged and you
want to know that now rather than after you've deleted it. (Deleting the source branch on merge —
`--remove-source-branch` on GitLab, the equivalent toggle elsewhere — handles the remote side.)

Leaving old branches around is how you end up starting work on a stale base three weeks later.

## 10. Verify it's actually live

**Green tests are necessary, never sufficient.** If the change has to land in a deployed
environment, check it there: use `argocd` for sync status and pod logs, hit the real endpoint,
load the real page.

**"Did you run it?" is the reflex to internalize.** A claim of "it works" needs real output
behind it. If you couldn't verify something, say so plainly — "not verified from this
environment" is a respectable line. A silent gap is not.

## The engagement contract

Who gets interrupted, and when:

- **Scoped work** (a named issue, a reported bug) gets one terse instruction and **full
  autonomy**. Engage at **kickoff** and the **merge decision** — not in between. Don't ask for
  status approval mid-loop on work that's already well-scoped; just run the loop.
- **Ambiguous or greenfield work** gets a plan reviewed **before any code** → use
  `/extensive-interview` rather than guessing and building.
- **A blocked action is a decision, not a transient error.** If a merge (or anything else) is
  blocked by a permission gate, **stop and ask**. Do not retry it, and do not reroute through a
  different command to achieve the same effect — an agent once retried a blocked destructive git
  command via another command. That's the anti-pattern, and it's worse than the original block.
- **Queue follow-up work rather than waiting serially.** Prefer being notified when background
  work finishes over polling it.

## Anti-patterns

- Planning or reading code against a stale checkout.
- Branching off a `main` you never pulled.
- Committing straight to `main` because it was "just a one-liner".
- Two issues on one branch, because they were both small.
- Writing code before reading the docs for the area you're touching.
- Leaving docs for a follow-up change request that never comes.
- Letting pre-existing failures blur into yours instead of proving which is which.
- Merging without an independent review because the session got long.
- Trying to merge a draft, then treating the refusal as a mystery (it tells you the fix).
- Retrying or rerouting a blocked action instead of stopping and asking.
- Calling it done because the suite is green, without ever running the real thing.
- Leaving merged branches lying around, then branching off one of them next month.

## Related

- `/scoping` — write the issue this loop starts from
- `/extensive-interview` — when the work is too ambiguous to scope yet
- `/test-design` — what to build in step 4/5
- `/good-mr` — the change request description in step 6
- `/review-gate` — the gate in step 7 (and the simplicity ladder used in step 4)
- `/commit-message` — the commits underneath the change request
- `/using-glab` — the GitLab CLI mechanics for steps 6 and 8 (or your tracker's equivalent)
- `/develop-for-air` — when the thing you're shipping runs on AIR
