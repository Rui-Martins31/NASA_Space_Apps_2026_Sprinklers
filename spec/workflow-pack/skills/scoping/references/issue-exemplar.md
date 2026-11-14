# Issue exemplar — a real, well-scoped issue

This is a **real issue from an internal LTP project**, reproduced close to verbatim. Only the
GitLab project path has been removed; the structure, prose, and symbol names are as filed. It was
tracked in GitLab, so the commentary below says "MR" — read it as **change request**, the
tracker-neutral term the rest of the pack uses.

It was picked because it demonstrates every convention in `issue-template.md` at once, and
because the MR that implemented it reported its test plan back against exactly these cases —
the issue→MR mirroring that makes an issue executable.

Read it for the shape, not the domain. You don't need to know what a "pairing" is.

---

**Title:** `backend: compute + expose per-day break classification (break / rest-room / violation) for the Pairing Board`

> ## Why
>
> `GET /runs/{id}/pairing-board`'s `TeamDay` currently returns raw `sos`/`eos`/`trips` only. To
> align the Pairing Board with the pairing definition (see `docs/pairing-planning-rules.md`'s
> "legal-but-costed band" and the `pairing_engine` rewrite's `kpis.py`/`duties.py`), the
> frontend needs to show, per in-day gap, whether it's:
>
> - a plain break
> - a **rest-room booking** (`>180min`, legal but costed — matches the existing
>   `restroom_bookings` KPI's threshold, see `seed/importer.py:376`)
> - a **hard-cap violation** (`>= max_daytime_break_min`, currently seeded as `240` via the
>   `pairing.max_daytime_break_min` run parameter, `seed/importer.py:184` — configurable per
>   run, not a fixed constant)
>
> This classification is a business rule (and a *configurable* one) — it must not be
> duplicated/hardcoded client-side. It belongs in the backend.
>
> ## Proposal
>
> Extend the `TeamDay` schema (wherever `PairingBoardResponse` is assembled) with a computed
> `breaks` list per day — one entry per gap (SoS→first trip, trip→trip, last trip→EoS), each
> with:
>
> - `start` / `end` (`HH:MM`)
> - `duration_min`
> - `kind`: `"break" | "rest_room" | "violation"`
>
> computed server-side from the run's actual configured `max_daytime_break_min` (and the 180min
> rest-room threshold), not a hardcoded value. Consider also exposing a per-day `duty_span_min`
> (EoS − SoS) if useful for a "duty span" display.
>
> ## Reference
>
> - `docs/pairing-planning-rules.md` — "legal-but-costed band" (§ around lines 54-68)
> - `pairing_engine/duties.py` — canonical `<240min` hard cap / `>180min` rest-room definitions,
>   kept deliberately distinct
> - `services/kpi_service.py` + `seed/importer.py` — existing (scenario-level, not per-day)
>   `restroom_bookings` KPI computed the same way
>
> ## Tests
>
> - **Boundary tests** for the classification, against the run's actual configured
>   `max_daytime_break_min` (not a hardcoded 240):
>   - gap = 180min → `"break"` (not `"rest_room"` — exclusive lower bound, matches the existing
>     `restroom_bookings` KPI test)
>   - gap = 181min → `"rest_room"`
>   - gap = configured cap − 1min → `"rest_room"`
>   - gap = configured cap exactly → `"violation"`
>   - gap run with a *non-default* `max_daytime_break_min` (e.g. 200) shifts the violation
>     boundary accordingly — proves it isn't hardcoded
> - **Per-gap coverage**: a day with SoS before the first trip's departure, a mid-day gap between
>   two trips, and a gap between the last trip's arrival and EoS — all three gap positions must
>   appear in `breaks`, each independently classified
> - **Zero/one-trip days**: a day with no trips (no in-day gaps to classify — decide & test
>   whether `breaks` is `[]` or omitted); a day with exactly one trip (still classifies the
>   SoS→trip and trip→EoS gaps if non-zero)
> - **Overnight days**: no trailing "last trip → EoS" break entry once EoS marks the start of the
>   overnight stay (don't double-count that boundary as a break)
> - **API-level test**: `GET /runs/{id}/pairing-board` on a fixture run returns the expected
>   `breaks` array (start/end/duration_min/kind) for at least one day of each kind (break,
>   rest_room, violation)
> - **Consistency regression**: the sum of `rest_room`-kind gaps across `breaks` for a run matches
>   that run's existing scenario-level `restroom_bookings` KPI (guards the two implementations
>   from drifting apart)
>
> ## Out of scope
>
> Frontend rendering of this data — tracked separately (#43) so this issue only covers the
> data/API side.

---

## Why this works

**The title states a finding.** It names the area (`backend:`), the thing to build, and the
three output states. You know what you're getting before you open it.

**It cites everything.** Two docs sections, three source files, and two of them with line
numbers (`seed/importer.py:376`, `:184`). Nobody has to search. This is the single biggest
difference between an issue an agent can execute and one it has to interview you about.

**It argues for its own existence.** *"This classification is a business rule (and a
*configurable* one) — it must not be duplicated/hardcoded client-side. It belongs in the
backend."* That paragraph exists to pre-empt the reviewer thinking this is a UI tweak. If you
can predict the objection, answer it in the issue.

**It names the trap, not just the requirement.** `240` is a *configured run parameter*, not a
constant — and the issue says so twice, in the Why and again in the Proposal. That's the fact
an implementer would otherwise get wrong.

**The tests are a spec, not a gesture.** Look at what they specify:

- Exact boundary values (`180 → break`, `181 → rest_room`, `cap → violation`), including the
  exclusive-bound subtlety and *why* it's exclusive (it matches an existing KPI's test).
- **A non-default config value (200) that proves the constant isn't hardcoded.** This is the
  best line in the issue. The happy path can't catch a hardcoded 240; this case can.
- Every structural position the feature must handle (three gap positions).
- The degenerate cases — *and it forces the decision*: "decide & test whether `breaks` is `[]`
  or omitted". It doesn't leave that to the implementer's taste.
- A **consistency regression** tying the new per-day computation to the existing scenario-level
  KPI, so the two can't silently drift apart. That test exists because the author thought about
  what breaks in six months, not what breaks today.

**It scopes itself and names its sibling.** *"Frontend rendering — tracked separately (#43)."*
The reviewer knows the boundary is deliberate, and where the other half went.

**What happened next:** the implementing MR's test plan reported back against exactly these
cases — *"classify correctly against both the default and a non-default (200min) hard cap"*.
The issue and the MR agree because the issue said what agreement would look like.
