# Docs bootstrap — when the project has no docs

Use this when you've run an interview and there's nowhere to put the answers, or when you inherit
a repo whose docs are a README and a prayer.

**Don't create all of this on day one.** That's rung 1 of the simplicity ladder
(`/review-gate`): does this need to exist at all? An empty doc is worse than a missing one — it
looks like an answer. Create a file when you have something true to put in it.

---

## The minimum that earns its keep

Four files. If you only ever write these, you're ahead of most projects:

| # | File | Answers |
|---|------|---------|
| 1 | `scope-and-goals.md` | What is this, who's it for, what is it **not**? |
| 2 | `functional-requirements.md` | What does it do? (`FR-<AREA>-<n>`) |
| 3 | `non-functional-requirements.md` | How well, how safely, built with what? (`NFR-<AREA>-<n>`) |
| 4 | `architecture.md` | What are the pieces, and where are the seams? |

Templates for 2 and 3 sit next to this file. The other two are sketched below.

## Add these when the project earns them

| File | Add it when |
|------|-------------|
| `data-model.md` | There's a schema anyone else has to join against. |
| `<domain>-rules.md` | The domain has real rules (regulatory, contractual, business) that outlive any one feature. **Write this early if it exists** — it's the doc that stops the same argument recurring. |
| `backend/`, `frontend/` (a `README` + `routes` + `components` + `testing`) | More than one person, or more than one agent, is working in that half. |
| `<subsystem>/` | A subsystem has its own design worth its own folder — especially one another team owns. |
| `README.md` (an index) | You have more than ~4 docs and someone has to find their way in. |

**The pattern worth copying:** a `README.md` per folder that is a **table of contents with a
one-line purpose per doc**, not prose. It's what makes a docs folder navigable by a person in a
hurry or an agent with a budget.

---

## 1. `scope-and-goals.md`

The most-skipped and most-valuable document. It's the one that ends arguments.

````markdown
# 1. Scope & Goals

## 1.1 Goal of this repository

<What this is, in a paragraph a newcomer could read cold.>

> **What this is.** <The honest one-sentence version.>
>
> **What this is NOT.** <The boundary. Name the neighbouring things it gets confused with,
> and who owns them. This paragraph prevents more waste than the rest of the doc combined.>

## 1.2 Business context (for orientation only)

<Why this exists commercially. Marked "orientation only" so nobody mistakes it for scope.>

## 1.3 Personas in scope

<Who uses it. Name them — every functional requirement will start with one of these.>

## 1.4 In scope

<Bulleted, concrete, small.>

## 1.5 Out of scope (context / future phases)

<The things people will assume are included. Say them out loud. This is the section that
gets cited in meetings.>

## 1.6 Success criteria

<How you'll know it worked. Observable, not aspirational.>
````

**Why "What this is NOT" is the highest-value paragraph you'll write:** every project has a
neighbour it gets confused with — the full product vs the demo, the app vs the engine, the
prototype vs the pilot. Left unwritten, that confusion arrives as scope creep wearing the costume
of a reasonable request.

## 2–3. Requirements

→ `functional-requirements-template.md` and `non-functional-requirements-template.md`.

Split them from the start. Merging them "for now" is how performance and security become
optional later.

## 4. `architecture.md`

````markdown
# 4. Architecture

## 4.1 Component overview

<The pieces, and a diagram if it helps. ASCII is fine.>

## 4.2 Responsibilities

<One line per component. If you can't write the line, the boundary is wrong.>

## 4.3 <The key seam> — the contract

<THE most important section. Name the boundary that matters most — the one between you and
another team, another system, or the thing most likely to change. Document the contract
explicitly: the verbs, the format, the columns, who owns it, and what happens when it breaks.>

## 4.4 <Core lifecycle>

<The main flow, end to end, including the async/failure paths.>

## 4.5 Deployment

<How it ships.>
````

**Lead with the seam, not the components.** The component list is the part people can infer from
the folder names. The contract at the boundary — the format, the column names, who owns which
side — is the part that isn't written anywhere else, and the part that breaks in production.
Where a contract is pinned exactly and has no translation layer, say so; that's a design decision
worth recording (`/teach-me`).

---

## Two sections to carry in the index

**"Open items to confirm."** A live list of what's still unknown, with status markers — resolved
items get struck or marked ✅ *with the resolution*, not deleted. This is where honest ignorance
goes to be useful instead of forgotten. Mark real blockers as blockers:

```markdown
## Open items to confirm

- 🚧 **BLOCKER** — <the unknown>, and what it blocks. Not in the source files; must be
  confirmed before <the thing it gates>.
- ✅ **RESOLVED (<date>)** — <what it was> → <what the answer turned out to be>, see <doc>.
- **<Decision>** is an **inferred** decision — confirm <the alternative>.
```

**"Source material."** Where the inputs live and what each one is. When a source file gets
replaced, say so *in place*, with the date and what changed — a source that changed silently is
the hardest class of bug to trace, because nothing in the code moved.

---

## The rules that make docs worth having

**Docs are the source of truth, not a description written afterward.** The order is: settle it in
the doc → build to it. Not: build it → describe it. A divergence is a bug to reconcile, not a
judgment call the implementer makes alone.

**Number the docs and the requirements.** `# 2. Functional Requirements`, `FR-DATA-6`. Numbers
are what issues, change requests, tests, and questions point at. Prose has nothing to point at, so people
paraphrase it, and paraphrases drift.

**Update them in the same change as the code.** Not a follow-up issue. A doc describing last
week's behaviour is worse than no doc: it's a confident lie, and it gets believed.

**Overclaims are more dangerous than omissions.** A doc saying "this is index-backed" when it
isn't will send someone down a day-long dead end. A doc that's silent just sends them to the
code. Check both directions when you review (`/review-gate` lens 2).

**Record decisions where the decision lives** — next to the thing it governs, not in a parallel
ADR tree (`/teach-me`, mode 3).

**Never leave a known inconsistency.** If two docs disagree, that's a bug — flag it, get a ruling,
fix it. If it's genuinely unresolved, write both readings into "Open items", never one presented
as settled.

---

## Anti-patterns

- Creating the full folder structure on day one, with nothing true in most of it.
- A `README.md` that's prose instead of a table of contents.
- Merging functional and non-functional requirements "for now".
- Prose where an ID would do — nothing to cite, so nothing gets cited.
- Docs written after the code, describing whatever the code happened to do.
- Deleting a resolved open item instead of recording how it resolved.
- A source file swapped without a note saying what changed and when.
- Writing "What this is" and skipping "What this is NOT".
