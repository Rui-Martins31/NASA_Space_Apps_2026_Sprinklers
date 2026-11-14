---
name: extensive-interview
description: "Structured interview to extract requirements and surface hidden assumptions before building — for project inception, big architectural pivots, or a critical new domain. Default is extensive; check the docs first and go small only when the docs already answer it. Use when scope is greenfield or genuinely open, when a decision would be expensive to get wrong, or when you catch yourself about to guess."
trigger: /extensive-interview
---

# /extensive-interview

The most expensive bug is a wrong assumption nobody said out loud.

This skill extracts what you need to build the right thing, and — just as importantly — forces
the assumptions you're already making into the open where they can be corrected cheaply.

## When to run it

- **Project inception** — greenfield, no spec yet.
- **A big architectural pivot** — the shape of the solution is genuinely open.
- **A critical new domain** — the rules are the product, and getting them wrong is expensive.
- **Mid-task**, when you hit an ambiguity or a fact that doesn't add up.

For scoped work (a named issue, a reported bug), don't run this — use `/scoping` instead.

## The mode gate — read this before you ask a single question

**Default to extensive.** Then check the docs:

1. **Do the docs already answer it?** → Don't interview. Ask the small gap-filling question
   instead, or nothing at all.
2. **Can't tell whether docs exist?** → **Ask.** "Are there docs covering this?" is a better
   first question than any of the ten you were about to ask.
3. **No docs, or the docs aren't clear enough?** → **Go extensive.**

**Why the gate exists:** a question already answered in the docs is a cost, not a courtesy.

"Keep interviews small and rare" and "make it a very detailed interview" are both right advice —
the docs are what decides between them. Where a client has already handed over a detailed
requirements list, the shape of the solution is settled and reviewed; interviewing around it
burns attention and signals you didn't read it. Where there's nothing written, or the rules
*are* the product and getting them wrong is expensive, go exhaustive.

**The docs are the variable, not the appetite.** Don't read "interviews should be small" as a
universal — read the docs first and let them decide.

## Before you ask anything

**Research first.** Every question you can answer yourself, answer yourself. Read the docs, the
source material, the code. Done properly this collapses the question count — read the client's
requirement PDFs and a ten-question list becomes *"now the one real question before drafting."*
Unresearched questions are the ones that get ignored.

**State your understanding before asking.** Open with what you think you know:

> "Here's what I understand before we start: ..."

It lets the person correct your frame in one sentence instead of discovering the misread six
questions later.

**File what you verified; ask only what you couldn't.** A verified bug — one you traced, one you
can point at the line for — gets filed as an issue, not raised as a question (no tracker? it
becomes its own markdown file under `issues/`, one per bug — see `/scoping`). Escalate decisions,
not findings. Don't make the person triage.

## What makes a question land

The mechanism is subtler than "broad questions fail, narrow ones work":

> **When the answer depends on context you haven't discovered, your options get overridden.
> When it's a genuine design fork you've fully characterized, people pick clean — usually the
> one you recommended.**

**Tag your recommendation.** On a genuine technical fork you've characterized — "Polars only for
now", "process, not pipeline" — a `(Recommended)` pick is usually just taken. That's the cheap
case, and it costs the reader nothing.

The expensive case is the other one: a question gets a paragraph of free text instead of a pick
almost always because the answer lived somewhere you couldn't see.

Watch for **picked-but-qualified** answers too: *"Agent-centric, but with the more granular
view."* A pick is not full agreement. Read the qualifier.

### The out-of-repo escape hatch — the #1 failure mode

The classic shape: you offer four options on how the app should exchange data with the optimizer,
or how auth should work, or where it deploys. Every option is reasonable. Every option is wrong —
because the real answer is infrastructure only the person knew existed: an internal
optimization-run platform (AIR), Keycloak, the internal deploy pipeline. None of it was inferable
from the repo, so no amount of careful option-writing was going to land it.

**Before offering a multiple choice, ask yourself: could this answer depend on something outside
this repo?** If yes:

- Ask it openly instead, **or**
- Add an explicit option: *"something already exists here that I don't know about."*

And group those questions under the header the agent itself eventually invented:

> **"AIR platform state (I can't see this from the repo)"**

That header is the fix. It tells the person exactly which questions only they can answer, and
stops you from dressing up a knowledge gap as a design choice.

### Don't offer the wrong axis

One batch offered a build-effort axis — "real rule engine" vs "demo-illustrative only" — when
the person cared about a product-meaning axis. He rejected the framing outright: *"think of
measures that will guide a planner instead of evaluation."* If the answer comes back rejecting
your options rather than choosing between them, you offered the wrong axis. Re-ask; don't push.

## Question craft

- **State your instinct and label it.** *"My instinct: X — but it's your call."* /
  *"That's my read... I want it confirmed rather than assumed."* This is the highest-yield habit
  here: it turns a question into a one-second confirmation. *"I agree with your read"* is a much
  cheaper reply than a paragraph.
- **Name the conflict, with evidence, inside the question.** Spell it out: *"the client PDF never
  uses this term... the DB schema uses it for a per-day row... your rule 1 uses it for the
  multi-day concept... all three meanings are live right now."* The person never has to
  reconstruct why you're asking. Questions like this get answered fully and without pushback.
- **Say what the answer unblocks.** *"This decides whether the module needs incremental recompute
  machinery at all."*
- **Number them and group by theme.** Numbered questions earn numbered replies — every time,
  including rejections. Someone rejecting most of your list, each with a reason, is a *good*
  outcome: the format invited the correction instead of burying it.
- **Rank your own blockers.** *"Those three change the issue list's shape the most."*
- **Surface assumed constraints.** *"I'm treating X as a hard constraint — correct me."* The
  costliest corrections are always assumptions that were never raised as questions: a module
  structure proposed as settled and then rewritten wholesale (*"I would organize things a lit bit
  differently"*), or an assumed data-preservation constraint that was never real (*"There isn't
  an issue with loosing data to achieve that"*). Neither cost anything to ask about. Both cost a
  branch to discover.

### Tool or prose?

- **AskUserQuestion** for closed scoping forks you've fully characterized. Cap at 4 questions.
  Tag your recommendation `(Recommended)`.
- **Free prose** for open domain modeling — thematically grouped under bold headers. Prose batches
  can run longer than four, but only after deep document research has earned them.

## Run it in rounds

Don't fire everything at once. Run 2–3 rounds of ~4 questions, and open each round by summarizing
what the last one locked:

> "Round 1 captured the spine. **Round 2** — pinning the AIR contract."

Rounds keep people engaged rather than exhausted, and an engaged person volunteers constraints
you didn't know to ask for. That's the real return: not the answers to your questions, but the
things offered up after them.

## Mid-task ambiguity flips the order

If *you* spot the problem — an ambiguity, a risk, a fact that doesn't add up — don't ask a bare
question and don't quietly guess. **Write up a short spec capturing the context first, then
interview about that specific point.** The context is what makes the question answerable.

## When an answer contradicts the docs — stop and reconcile

The docs are the source of truth. So the moment something contradicts them, **the docs have a bug
in them** — and you've just found it.

This happens constantly in a real interview: the answer you get contradicts a doc, two docs
disagree, or the code does something the docs say it doesn't. **Never silently pick a winner.**
Not the newest input, not the doc, not the code. Silently picking is how a source of truth
quietly becomes a pile of claims — and the next person reads the doc, not this conversation.

**What to do, every time:**

1. **Stop and say so, immediately.** Don't bank it for later; later is when you've already built
   on it.
2. **Quote both sides, with locations.** *"`docs/<file>.md` says X. You've just said Y. Both
   can't be true."* Don't paraphrase — paraphrase is where the contradiction goes blurry and
   people agree to different things.
3. **Ask which is authoritative** — and whether the other is stale, wrong, or describing
   something genuinely different that's been given the same name.
4. **Fix the doc as part of this work**, in the user's own words, once they've ruled. Not a
   follow-up issue. Not "we should update the docs at some point."

The shape to watch for: three definitions of the same word live at once — the client's document,
the database schema, and the rule you were just told, all using it differently. Surfaced as a
question ("all three meanings are live right now — which one wins?") that's an immediate ruling
and a docs cleanup. Guessed at, the ambiguity ships into the schema, where it costs a migration
instead of a sentence.

**Terminology collisions are the most common form and the easiest to miss** — the same word
meaning different things in two places reads as agreement right up until it doesn't. When you
notice a word carrying two meanings, that's a contradiction, even though nothing looks wrong.

**Never leave a known inconsistency in the docs.** If it's genuinely unresolved, it goes in as an
explicit open question with both readings written out — not as silence, and never as one reading
presented as settled.

## Output

Answers don't live in the chat. They land as:

- **Numbered requirement IDs in the docs**, folded in alongside what's already specified — not a
  parallel document.
  - **Functional** (`FR-<AREA>-<n>`) — what the system *does*. If a user could watch it happen,
    it goes here.
  - **Non-functional** (`NFR-<AREA>-<n>`) — how well, how fast, how safely, built with what.
  - **Keep them in separate files.** Merging them "for now" is how performance and security
    quietly become optional — nobody reads "…and it should be fast" tacked onto a feature
    bullet. Same feature usually produces one of each.
  - New to the distinction, or unsure where something goes? → `references/README.md`.
- **A proposed cut table** — what to drop, and why (see `/review-gate`'s YAGNI ladder). Propose
  cuts against the numbered requirements, not against a hypothetical ideal system.

**If there are no docs to fold into** — which is the usual case when the mode gate sent you here
— don't invent a shape. Start from `references/docs-bootstrap.md`: four files earn their keep on
day one (scope-and-goals, functional, non-functional, architecture), and the rest get created
when the project earns them. An empty doc is worse than a missing one; it looks like an answer.

**Every M (must-have) requirement should be answerable by a test.** If you can't imagine the
test, the requirement is still too vague — fix it now, while it's a sentence and not a sprint
(`/test-design`).

What comes out is an **executable spec** — good enough to turn straight into a pre-written failing
test suite and build against module by module until it goes green. At that point the tests *are*
the spec, not documentation of it.

## Anti-patterns

- Interviewing about something the docs already answer.
- Asking before researching — every unresearched question spends someone's attention.
- Offering four reasonable options when the real answer is infrastructure you can't see.
- Presenting your instinct as a settled decision instead of labeling it as a read.
- Taking an answer that contradicts a doc and just... using it, leaving the doc wrong.
- Letting the same word mean two things because nobody said it out loud.
- Firing 11 questions at once with no themes, no numbers, and no ranking.
- Reading a `(Recommended)` pick as full agreement when it came with a qualifier.
- Guessing silently on genuinely open scope, then discovering the assumption in review.

## Templates

**Start at [`references/README.md`](./references/README.md)** — it explains functional vs
non-functional (with the test for telling them apart, and what to do when it's genuinely
ambiguous), then points at the three templates:

- `functional-requirements-template.md` — what the system does (`FR-<AREA>-<n>`)
- `non-functional-requirements-template.md` — how well/fast/safely (`NFR-<AREA>-<n>`)
- `docs-bootstrap.md` — the doc set to start from when the project has none

## Related

- `/scoping` — the small-change counterpart: read docs, ask the delta, file the issue
- `/teach-me` — for explaining the decisions the interview settles
- `/review-gate` — the YAGNI ladder the cut table is built against
- `/delivery-loop` — where the interview sits before any code gets written
