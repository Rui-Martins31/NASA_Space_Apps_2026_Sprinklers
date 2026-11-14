---
name: teach-me
description: "Explain how the code works and why it was built this way — package choices, design decisions, trade-offs — so the reader understands a little more each day. Four modes: inline explanation on demand, a 'why this way' section in issues and change requests, durable decision records folded into the docs, and short proactive notes on non-obvious calls. Use when asked to explain something, when making a non-obvious call, and when writing any issue or change request."
trigger: /teach-me
---

# /teach-me

The goal is not to answer the question. The goal is that the person asking needs to ask it less
often next time.

Code that only its author understands is a liability, and an agent that explains nothing leaves
the humans around it less capable every sprint. This skill is the counterweight: every artifact
carries a little of the reasoning behind it.

## When to run it

- **Someone asks you to explain something** — explicitly, or by asking "why" or "how".
- **You're writing an issue or a change request** — the rationale goes in, every time (modes 2 and 3).
- **You just made a non-obvious call** — a package choice, a trade-off, a rejected alternative.

### A "why" or "how" question is a teaching trigger, not a lookup request

These are all real questions from real sessions:

> *"How was it so fast?"* · *"are we using tuples and native python or polars?"* ·
> *"what is the comm[p,t]?"* · *"How is the coverage created?"* · *"what are trechos?"*

None of them wants a one-word answer. Each is someone building a model of the system in their
head and finding a gap. **Answer the question, then answer the question behind it** — the thing
they'd have asked next if they knew to.

## Mode 1 — Inline explanation on demand

Socratic, and it doesn't end at your first paragraph.

The real shape, from a session where someone was reviewing a TypeScript change:

> **Them:** "I am not really proficient in TypeScript, so can you explain in more detail?"
> **You:** *(explains)*
> **Them:** "But should the test fail if I go to that, or is that the behavior that you just put?
> What is the goal of this test?"
> **You:** *(explains deeper — the actual point of the test, not just its mechanics)*
> **Them:** "ok I think I understand a little bit better now, you can merge it."

Three things to take from that:

1. **Expect the probe. Invite it.** The first explanation is never the last one. End with the
   thing they're most likely to still be unsure about, not with "let me know if you have
   questions."
2. **The probe is usually better than the original question.** "What is the goal of this test?"
   is the real question. Treat a follow-up as a signal you explained the *what* and skipped the
   *why*.
3. **Understanding gated the merge.** The change didn't ship until it was understood. That's the
   standard — not "it's correct, trust me."

Practical rules:

- **Never answer with just the mechanism.** "It's memoized" is a fact. "It's memoized because the
  parent re-renders on every keystroke, and this recomputes a 13k-row aggregate" is an explanation.
- **Say what you'd have done otherwise**, and why you didn't. The rejected alternative teaches
  more than the chosen one.
- **If they're not proficient in the language or the domain, say so out loud and adjust.** Someone
  telling you "I am not really proficient in TypeScript" is giving you the level to pitch at. Use it.

## Mode 2 — "Why this way" in issues and change requests

Every issue and change request carries a short rationale for the non-obvious calls in it, so people
learn passively from artifacts they already read.

There's precedent to follow rather than invent — `## Design decisions` in change requests,
`## Decision (confirmed)` in issues. Keep it to what's genuinely non-obvious:

- **Why this package** and not the obvious alternative.
- **Why this shape** — why the logic lives in the backend rather than the client, why the
  classification is computed rather than stored.
- **What you rejected**, in one line.

Anti-pattern: a `## Design decisions` section that explains the obvious. If the call was obvious,
it isn't a design decision — it's just the code.

See `/scoping` and `/good-mr` for where these sections sit in the artifact.

## Mode 3 — Durable decision records

Explanations that only exist in chat evaporate. Decisions that will still matter in three months
go into the docs.

**Fold them into the doc the decision belongs to — do not build a parallel ADR tree.** A decision
about the optimizer belongs next to the optimizer docs; a decision about the API contract belongs
in the contract doc. The docs are already the source of truth; a second source of truth is just
drift with extra steps.

What earns a record:

- A decision someone will otherwise re-litigate ("why isn't this cached?").
- A constraint that isn't visible from the code ("this is capped at 2 because the combinatorics
  explode above it — we tried").
- A deliberate non-goal.

What doesn't: anything a reader can see by opening the file.

## Mode 4 — Proactive teaching moments

Volunteer a short explanation when you make a genuinely non-obvious call, even if nobody asked.

**Cap it at ~3 sentences. Non-obvious calls only. Never on routine work.**

The cap is the whole point. Summaries get skimmed — that's a fact about how people read, not a
failing. Unbounded proactive teaching fights the thing that makes delegation work in the first
place: if every status update carries a lecture, the updates stop getting read, and the one that
mattered gets skimmed with the rest.

Good:

> Used the DB's own unique constraint rather than a check in the service layer — the service
> can't see concurrent writes, so an app-level check would pass and then still collide under load.

Bad: three paragraphs on the history of optimistic locking. Bad: explaining that you renamed a
variable.

## Writing for a mixed audience

These artifacts get read by people at very different levels. Assume the room.

- **Define jargon on first use** — including domain jargon. If a term arrived from a client
  document in another language, define it the first time it appears and then use it consistently.
- **Prefer a worked example over an abstraction.** One concrete case with real values beats a
  paragraph of theory.
- **Don't hide the hard part.** If the tricky bit is the boundary condition, spend your words
  there, not on the setup.
- **Explain the package choice, not just the API call.** "We use X" is trivia; "we use X because
  Y couldn't do Z, and here's what that costs us" is the thing worth knowing.

## Anti-patterns

- Answering the literal question and stopping, when the gap behind it was obvious.
- Explaining the mechanism (*what the code does*) and calling it an explanation.
- Treating a follow-up question as a nuisance rather than as evidence you under-explained.
- A `## Design decisions` section full of obvious decisions.
- Building an ADR folder nobody reads instead of updating the doc that governs the thing.
- Proactive teaching on routine work, until the summaries stop being read.
- Merging something the reviewer said they didn't understand.

## Related

- `/scoping` — where the "why this way" rationale lands in an issue
- `/good-mr` — where it lands in a change request, alongside disclosing what wasn't verified
- `/review-gate` — the review checks docs are accurate, not just present
- `/delivery-loop` — teaching is a step in the loop, not an optional extra
