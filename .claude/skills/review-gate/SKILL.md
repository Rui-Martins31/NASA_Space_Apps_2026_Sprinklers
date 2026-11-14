---
name: review-gate
description: "Independent review pass before work is called done — checks completeness against the spec, doc accuracy, test exhaustiveness, and YAGNI. Use when an implementation agent reports finished, before opening or merging a change request (MR/PR), or whenever you're about to say 'this is done'. Named review-gate (not review) because it gates the done claim, not the code style."
trigger: /review-gate
---

# /review-gate

An implementation agent reporting "finished" is a **trigger, not a conclusion**.

This skill runs the review that decides whether work is actually done. It is deliberately
adversarial: the implementer's self-report is evidence, not proof.

## When to run it

- An implementation agent (or you) reports an issue is implemented.
- Before opening a change request (MR/PR), and again before merging one.
- Any time you're about to write "this is done" / "this works" / "tests pass".

Run it on **every unit of work, every time**. This instruction has a known failure mode: on
long sessions it quietly lapses — the first few issues get reviewed, later ones don't, because
nobody restated it. **A lapse is a bug in the process, not an acceptable shortcut.** If you
notice it lapsed, the fix is to review the units you skipped, not to move on.

## How to run it

**Spawn a separate agent.** The point is independence — an agent reviewing its own diff shares
its own blind spots. Give the reviewer the diff and the original spec (the issue), not the
implementer's summary of them.

Cheap, well-scoped fixes the review surfaces (a missing test, a doc overclaim) — apply directly.
Reserve a fresh implementation agent for genuinely substantial follow-up.

## The four lenses

Run all four. Most reviews check only the first and call it done.

### 1. Completeness — against the spec, not against "looks reasonable"

Re-read the original issue's acceptance criteria yourself. Do not trust the implementer's
restatement of them. Ask: does this satisfy what was asked, or does it satisfy a *drifted*
version of what was asked?

### 2. Doc accuracy

Docs are the source of truth, not paperwork written afterward. Check both directions:

- **Omission** — does a doc still describe the old behavior?
- **Overclaim** — does a doc assert something the code doesn't do? ("this is index-backed" when
  it isn't; "not yet set up" next to a suite that's clearly been running for weeks).

Overclaims are the more dangerous half, because the next agent builds against the doc. Weight
them accordingly when the doc is a contract another team reads.

### 3. Test exhaustiveness — not "tests pass"

"Tests pass" is necessary, never sufficient. Ask:

- Do the new tests cover the **edge cases the issue implies**, or only the happy path?
- Is a regression test **provably red before the fix and green after** — checked, not assumed?
- Are assertions **exact**, not vacuous? (`len(result.unstaffed) == 3`, not "the solve succeeded")

If a review claims "the tests would catch a regression here", trace that claim yourself. Don't
take it on faith.

#### Hunt for reimplementation — the tautology check

**Go looking for this one specifically; it doesn't announce itself.** A test that reimplements
its subject passes whenever the two copies agree, including when both are wrong. The suite is
green, coverage is up, and none of it means anything.

For each new test, ask: **if the implementation were deleted, would this test still pass?**

Four things to actually look for in the diff:

1. **Is the real function imported and called?** Or has a copy of it appeared in the test file?
2. **Where does the expected value come from?** This is the one that slips through. An expected
   value computed by the same formula the code uses —
   `expected = sum(l.duration for l in legs) * RATE` — is the implementation written twice. It
   should be a **literal**, traceable to the spec or a hand-worked example.
3. **Is anything hard-to-import rewritten rather than loaded?** A service worker or bundled
   script reimplemented in the test guards nothing.
4. **Is the thing under test mocked?** Mock the boundary — network, clock, DB. Mocking the
   subject means the test asserts your mocks agree with each other.

This is a **blocking** finding, not a nit. A tautological test is worse than no test: it costs
the same to maintain and buys a false sense of coverage, so nobody writes the real one.

See `/test-design` for the full rules this lens checks against.

### 4. YAGNI and simplicity

Two questions, not one:

- **Does the issue justify this code existing?** No speculative abstractions, no generality
  nobody asked for, no scope creep past what was asked.
- **Is it simple to understand?** Overly complicated logic is a defect in its own right, even
  when it's correct. If the same result is achievable in fewer lines, it should be.

#### The ladder

For anything being added, walk this ladder and **stop at the first rung that holds**:

1. **Does this need to exist at all?** Speculative need → skip it, and say so in one line.
2. **Already in this codebase?** A helper, util, type, or pattern that already lives here →
   reuse it. **Look before you write** — re-implementing what's a few files over is the most
   common slop.
3. **Stdlib does it?** Use it.
4. **Native platform feature covers it?** `<input type="date">` over a picker lib, CSS over JS,
   a DB constraint over app code. Where the platform supports it, claim it — and say so
   explicitly ("used native X instead of adding Y" is a design decision worth recording).
5. **Already-installed dependency solves it?** Use it. **Never add a new dependency for what a
   few lines can do.**
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

#### The rules around the ladder

- **Deletion over addition.**
- **Boring over clever.** Clever is what someone decodes at 3am.
- **Fewest files possible. Shortest working diff wins** — but *only once you understand the
  problem*. The smallest change in the wrong place isn't lazy, it's a second bug.
- **Two options the same size? Take the one that's correct on edge cases.** Lazy means writing
  less code, not picking the flimsier algorithm.

Reviewing against the ladder means naming the rung: "this reimplements a helper that already
exists in `<file>`" (rung 2) is actionable; "this feels over-engineered" is not.

## Verify the reviewer too

**This is the part everyone skips.** The reviewer is an agent, with the same failure modes as
the implementer. Two failures worth internalizing:

- A reviewer reported "2 pre-existing test failures, confirmed on main." Running the suite
  directly found **5** — plus a flaky 6th it never saw, which needed its own isolation pass to
  confirm it was non-deterministic rather than a real regression.
- An automated review pass produced **6 findings; exactly 1 survived checking.** Two were about
  a file the branch didn't even touch. One rested on the reviewer's own hedged guess.

So before you fix any finding:

1. **Confirm it's in this diff.** `git diff origin/main...HEAD -- <file>`. If the flagged lines
   aren't there, the finding is about pre-existing code and is not yours to "fix".
2. **If the reasoning hedges, verify the premise.** Words like *if*, *likely*, *consistent with*,
   *presumably* mark a guess. Check it with grep/read before acting on it.
3. **If it's about intentional-looking state on the main branch, ask before "fixing" it.**
   Someone may have put it there deliberately, for reasons the diff doesn't show.

Findings that survive all three are usually real. Fix them in the same change request.

If the reviewer states a specific number or fact and it's cheap to check — check it before you
repeat it to anyone. A number you pass along becomes yours.

## Green is necessary, never sufficient

A passing suite is not evidence the feature works. Before calling it done, exercise the real
thing: start the server, run the job, load the page, look at the output. If you claim something
was verified, attach what you actually ran and what it actually printed.

If you *couldn't* verify something, say so plainly rather than omitting it. "Not verified from
this environment" is a respectable line in a change request. A silent gap is not.

## Reporting

Report findings ranked most-severe first, and for each: what's wrong, the concrete failure it
causes, and whether you confirmed it or are flagging it as plausible. Separate:

- **Confirmed** — you traced it and it holds.
- **Plausible** — it looks wrong but you couldn't prove it; say what would settle it.
- **Not verified** — you didn't check; say why.

Then state the verdict plainly: is this done, or not?

### Write the review back to where the work lives — when there's somewhere to write it

A review that exists only in a session transcript is invisible to everyone who wasn't in that
session, and gone by next week. **If the work has a change request or issue in a tracker, post
the review there.** That's the traceable record: why this merged, what was checked, what wasn't.

On GitLab that's a note via `glab` (the default flavor):

```bash
glab mr note <n> -m "$(cat <<'EOF'
## Review — <verdict>
...findings, ranked...
EOF
)"
```

Use `glab issue note <n> -m "..."` when the work is tracked on an issue rather than a change
request. On GitHub / Jira / Azure DevOps, post the same note through that tracker's CLI (see the
tracker's interface skill). **If there's no tracker at all**, append the review to the markdown
file the issue lives in (see `/scoping`) under a `## Review — <verdict>` heading — same record,
different medium.

**"When there's somewhere to write it" is a real gate, not a formality.** Skip posting — and say
so in your summary — if any of these hold:

- No change request, issue, or issue file exists yet (posting to nothing isn't traceability; open
  the change request first).
- The tracker's CLI reports logged-out (`glab auth status` on GitLab), or the host is unreachable.
- The work is purely local/exploratory and isn't going to any durable record.
- The review contains anything that shouldn't be in a durable shared record: secrets, tokens,
  credentials, customer data. **Scrub or omit — a comment is forever.** Never paste a key into
  a note to "show the evidence."

Post the review **before** the merge decision, not after. A review posted after merging documents
a formality; posted before, it's a gate someone can still act on. If the verdict is "not done",
that comment is the reason the change request stays open.

Note that a note is not a merge. If a merge is blocked by a permission gate, that's a decision —
post the review and stop; don't reroute to force the merge through another path.

See `/using-glab` for the GitLab note/heredoc mechanics and the `glab api` escape hatch — or your
tracker's interface skill for the equivalent.

## Anti-patterns

- Taking the implementer's "all tests pass, docs updated" as the review.
- Reviewing the summary instead of the diff.
- Applying findings mechanically because they're labeled CONFIRMED.
- Checking correctness only, and letting docs and tests through unexamined.
- Counting the new tests instead of reading them — a tautological test looks like coverage.
- Letting the review lapse on a long session because nobody restated it.
- Calling work done because it's green, without ever running it.

## Related

- `/test-design` — what "exhaustive tests" actually means (lens 3 checks against it)
- `/good-mr` — how the review's output lands in the change request (esp. disclosing what wasn't verified)
- `/delivery-loop` — where this gate sits in the end-to-end flow
