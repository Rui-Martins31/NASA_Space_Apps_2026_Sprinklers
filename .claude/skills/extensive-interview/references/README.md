# Requirements & docs templates

Templates for turning interview answers into documentation someone else can build from.

> **Functional requirements** are what the system **does** — behaviours a user could watch happen.
> *"The planner shall filter the schedule by date."*
>
> **Non-functional requirements** are how well it does it, and what it's made of — qualities and
> constraints. *"Filtering shall feel instant."* *"Secrets come from environment, not source."*
>
> Same feature usually produces one of each. They live in **separate files**, on purpose — see
> "Why split them" below.

## The templates

| # | File | Purpose |
|---|------|---------|
| 1 | [functional-requirements-template.md](./functional-requirements-template.md) | What the system does. `FR-<AREA>-<n>`, MoSCoW priority, one behaviour per row. |
| 2 | [non-functional-requirements-template.md](./non-functional-requirements-template.md) | How well/fast/safely, and built with what. `NFR-<AREA>-<n>`, with a Note column recording what's deliberately relaxed. |
| 3 | [docs-bootstrap.md](./docs-bootstrap.md) | The doc set to start from when the project has **no docs at all**. Four files earn day one; the rest wait. |

Start at 3 if there's nothing. Start at 1 and 2 if there's somewhere to fold answers into.

---

## Telling them apart

**The test that works in the moment:** *could a user watch it happen?*

| | Functional | Non-functional |
|---|---|---|
| **Asks** | What does it do? | How well? Made of what? |
| **Reads like** | "The planner **shall** browse the crew list." | "Read screens shall render responsively on the seeded dataset." |
| **Checked by** | Doing it and looking. | Measuring, profiling, reading the config — or a bad day in production. |
| **Maps to** | Roughly one issue each. | Constrains *every* issue. |
| **Discovered late as** | "We forgot that screen." | "It's slow." / "The key is in the browser." |

Side by side on the same feature:

| Feature | Functional | Non-functional |
|---|---|---|
| Schedule filter | "The planner shall filter the schedule by date and station." | "Filtering shall not create request waterfalls." |
| Login | "The user shall authenticate via Keycloak (OIDC)." | "The API key shall live server-side only, never in the browser." |
| Run a job | "A run shall move through `queued → running → done`." | "Long-running work shall be asynchronous; the API shall never block." |

Notice: **the functional half is the part someone asks for. The non-functional half is the part
that bites you.** Nobody files a ticket saying "please don't put the key in the browser."

## Why split them

Not tidiness — a failure mode. **Merged, the non-functional ones get skipped.** Nobody reads
"…and it should be fast" tacked onto the end of a feature bullet, so it isn't designed for, isn't
tested, and surfaces when the demo is slow in front of the client.

They're also read at different times by different people. Functional requirements get walked
through in a demo. Non-functional ones get checked at review, at deploy, and at 2am. A file each
means the second list actually exists.

## When it's genuinely ambiguous

The taxonomy is fuzzier than most write-ups admit. "The screen shall be mobile-friendly" is a
quality — but if it's true of exactly one screen, it belongs *with that screen's* functional
requirements, not marooned in a global UX section where nobody building that screen will read it.

**The rule of thumb: put it where the person who has to satisfy it will read it.**

- **Global** (applies across the system, or nobody owns it) → non-functional.
- **Scoped to one feature** → with that feature, functional.
- **Genuinely both** → write both, and cross-reference. That's not duplication; the feature-level
  one is the instance, the global one is the rule.

**What actually matters is that it's written down once, somewhere it'll be checked.** Don't spend
an interview arguing the taxonomy — that's a question the docs can answer later, and a
requirement in the "wrong" file still gets built. A requirement in neither file does not.

## The NFR categories people forget

Non-functional requirements are the ones nobody thinks to ask about. Walk the list — most will be
"not applicable", and the two that aren't are why you walked it:

**Stack** · **Architecture & integration** (the seams) · **Performance & scale** ·
**Security & access** · **Deployment & operations** · **Internationalization** ·
**Usability & UX** · **Accessibility** · **Observability** (logs, traces, how you'll debug it
live) · **Data retention & privacy** · **Compliance**

For each: is it a real requirement here, or deliberately out of scope? **Both answers go in the
file** — "Full RBAC and audit logging are out of scope (future)" is a decision. Silence is an
omission, and only one of those survives a client meeting.

## Where these fit

```
interview  →  FR-<AREA>-<n> / NFR-<AREA>-<n>  →  issue (cites it)  →  change-request test plan  →  test
```

The ID is the thread. Prose has nothing to point at, so people paraphrase it, and paraphrases
drift.

- `/extensive-interview` — produces these
- `/scoping` — issues cite them
- `/test-design` — every **must-have** requirement should be answerable by a test
- `/review-gate` — if code traces to no requirement, ask why it exists
