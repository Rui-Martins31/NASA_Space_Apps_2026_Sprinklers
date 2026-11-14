# Non-functional requirements — template

Quality attributes and constraints — **how well**, not **what**. Stack, architecture, performance,
security, ops, i18n, UX.

> **The test:** if a user could *watch it happen*, it's functional (→
> `functional-requirements-template.md`). If it says how fast, how safely, at what scale, or built
> with what, it's here.

**Why this file exists at all.** Non-functional requirements are the ones that get skipped, and
they're the ones that kill you late: nobody notices the missing performance requirement until the
demo is slow in front of the client, and nobody notices the missing security requirement until
the key is in the browser. Writing them down early is cheap. Discovering them in production is
not.

---

## The skeleton

Note the column difference from the FR table — **this one carries a Note, not a Priority**, and
the Note is the most valuable column in the file.

````markdown
# 3. Non-Functional Requirements

Quality attributes and constraints. IDs: `NFR-<AREA>-<n>`.
Because this is a **<demo / MVP / v1>**, several enterprise NFRs are deliberately
relaxed and recorded as *future* — see the right-hand notes.

---

## 3.1 Technology stack (`NFR-STACK`)

| ID | Requirement | Note |
|----|-------------|------|
| NFR-STACK-1 | **Backend**: <language + framework>, <structure/layering>. | <why — existing scaffold? team skill?> |
| NFR-STACK-2 | **Database**: <choice>. | <what this replaces//assumes> |
| NFR-STACK-3 | **Frontend**: <framework + design system>. | <the visual/structural baseline> |
| NFR-STACK-4 | **<Integration>**: <client library> against <platform>; the app contains no <X> code. | Boundary owned by another team. |
| NFR-STACK-5 | Dependency management: <tools>. | |

## 3.2 Architecture & integration (`NFR-ARCH`)

| ID | Requirement |
|----|-------------|
| NFR-ARCH-1 | The <component> shall be the **single source of truth** for <X>; <other> shall hold no business logic beyond presentation. |
| NFR-ARCH-2 | The **<external> contract shall be a clean seam**: a small abstraction (<the 3-4 verbs>) so <the real thing> can plug in without <UI/API> changes. |
| NFR-ARCH-3 | Long-running <work> shall be **asynchronous**; the API shall never block a request waiting for it. |
| NFR-ARCH-4 | <The seam> shall provide a **fixture/mock mode** so the app can be built and demoed without a live <dependency>. Config-driven; switching requires no code change. |

## 3.3 Performance & scale (`NFR-PERF`)

| ID | Requirement | Note |
|----|-------------|------|
| NFR-PERF-1 | The system shall handle **<the actual dataset, with real numbers>** responsively. | Not sized for <the real production scale>. |
| NFR-PERF-2 | <Specific known trap, stated as a rule.> | <How you found it — a production log, a profile.> |

## 3.4 Security & access (`NFR-SEC`)

| ID | Requirement | Note |
|----|-------------|------|
| NFR-SEC-1 | Users authenticate via **<mechanism>**. | |
| NFR-SEC-2 | <Credential> lives **server-side only**, never in the browser. | |
| NFR-SEC-3 | Secrets shall come from **environment / deployment secrets**, not source. | |
| NFR-SEC-4 | Full **<RBAC / audit / versioning>** are **out of scope** (future). | Per scope doc §<n>. |

## 3.5 Deployment & operations (`NFR-OPS`)

| ID | Requirement |
|----|-------------|
| NFR-OPS-1 | The system shall deploy via **<the standard pipeline>**. |
| NFR-OPS-2 | Each component shall be **containerized**. |
| NFR-OPS-3 | Configuration shall be injected via **env vars / deployment values**. |
| NFR-OPS-4 | <What durability/backup is, and isn't, in scope.> |

## 3.6 Internationalization (`NFR-I18N`)

| ID | Requirement | Note |
|----|-------------|------|
| NFR-I18N-1 | The UI is **<language>-only**. | Full product needs <langs>. |

## 3.7 Usability & UX (`NFR-UX`)

| ID | Requirement |
|----|-------------|
| NFR-UX-1 | Screens shall follow **<the layout/design system>** for consistency. |
````

---

## The rules

**The Note column is where the honesty lives — use it.** It records *why* a constraint is what it
is, and *what you deliberately gave up*. "Not sized for 2,100 crew." "Replaces the scaffold's
Postgres assumption for the demo." "Full RBAC out of scope (future)."

This is what stops the two failure modes that kill NFRs:

- Someone reads a relaxed NFR as an oversight and "fixes" it, gold-plating a demo.
- Someone reads it as a promise and ships it to production at 40× the scale.

An empty Note on a deliberately-relaxed requirement is a bug in this file.

**Write the constraint you'd actually defend.** "The demo shall handle ~49 agents × 28 days
responsively. Not sized for 2,100 crew." — that's a real boundary you can hold. A hard SLA you
invented ("p95 < 200ms") is a number you'll either ignore or be beaten with. Don't write one you
don't mean.

**Qualitative is allowed — say so.** "Read screens shall render responsively on the seeded
dataset. *Qualitative — no hard SLA for a demo.*" That's more honest than a fake threshold, and
more useful than silence.

**Out-of-scope items belong here, written down.** `NFR-SEC-4: Full RBAC, audit logging, and
override history are out of scope (future).` This is not a confession — it's the difference
between a decision and an omission. An omission gets discovered in a client meeting; a decision
gets pointed at.

**A named tool choice is a hard constraint, not a suggestion.** Once `NFR-STACK-3` names the
table library, that's the answer — including for a reviewer who prefers another one. If the
choice deserves to change, change *this row* first, then the code. Not the reverse.

**Performance rules earned from real incidents are the best rows in the file.** When you find a
real trap — a request waterfall, an N+1, a lock — write it as an NFR with the evidence in the
Note. It stops the next person re-finding it the expensive way.

---

## Refining an existing set

- **New constraint from an interview → a new numbered row**, in the area it belongs to. Not a
  new document.
- **A contradiction is a bug in this file** — flag it, get a ruling, fix the row. See
  `/extensive-interview`.
- **Watch for functional requirements drifting in here** ("the planner shall see a chart") and
  send them to the FR file. The drift usually goes one way: someone writes a UX requirement,
  then hangs behaviour off it.

---

## Anti-patterns

- An SLA number you invented and don't mean.
- A relaxed requirement with an empty Note — indistinguishable from an oversight.
- "The system shall be secure / fast / scalable." Not requirements. Feelings.
- Out-of-scope decisions living only in someone's memory.
- Letting a code review override a stack choice this file already settled, instead of changing
  this file.
- Functional behaviour smuggled in under UX.
- Skipping this file because the project is "just a demo" — the demo is exactly where the
  relaxations need writing down, because that's where you're making them.
