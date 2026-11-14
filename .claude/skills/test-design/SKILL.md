---
name: test-design
description: "How to design tests that are comprehensive but focused — call the real code (never reimplement it in the test), exact assertions, meaningful coverage over maximal, and regression tests proven red-before/green-after. Use when writing or reviewing tests, when specifying tests in an issue, or when a test suite is green and you're about to call the work done."
trigger: /test-design
---

# /test-design

This is the part of the process that bends least. Everything else — architecture, naming, how a
fan-out organises itself — is negotiable. Test discipline is not.

A test suite exists to tell you something you don't already know. Most of the ways tests fail are
ways of quietly telling you nothing.

## The one gate that never bends

**A regression test is provably red before the fix and green after. Checked, not assumed.**

No exceptions for "obviously correct" fixes. If you did not watch it fail, you do not know it
tests the bug.

How to actually check it:

- Write the test **before** the fix, or `git stash` the fix once it's written.
- Run the test. Confirm it fails **exactly as predicted** — not for an unrelated reason (import
  error, wrong fixture, typo) that would also fail on correct code. A test that fails for the
  wrong reason is telling you nothing.
- Restore the fix (`git stash pop`), run it again, confirm green.

A real case worth internalising: an agent reverted its own fix specifically to confirm the test
failed as predicted, then re-applied it. That is the standard, not paranoia.

The subtle version of this failure: you *replace* an existing test. If a test used to assert
`pytest.raises(RuntimeError)` and you swap it for something new, the new one must still fail on
the old code. **Otherwise it isn't a regression test, it's decoration.**

## Never reimplement the code under test

**Call the real function. Always. There is one implementation, and the test imports it.**

If the logic exists twice — once in the source, once in the test — the test is a **tautology**. It
passes whenever the two copies agree, *including when both are wrong*, and it cannot fail for the
reason you wrote it. You have not tested the code. You have tested that you can write the same
bug twice.

It's the most damaging anti-pattern in testing because it's invisible: the suite is green, the
coverage is up, and none of it means anything.

### The four forms it takes

**1. Copying the function into the test file.** The blatant one. The copy is correct by
construction and the real code rots freely behind it. Import it instead — always, even if the
import is awkward.

**2. Computing the expected value with the same algorithm.** The common one, and the one that
slips through review:

```python
# WRONG — the test re-derives the answer the same way the code does
expected = sum(leg.duration for leg in legs) * RATE
assert compute_cost(legs) == expected     # passes even if RATE is wrong

# RIGHT — the expected value is a literal you worked out independently
assert compute_cost(legs) == 340.0        # 4h × 85/h, from the rate card
```

If your expected value is an expression that mirrors the implementation, you've written the
function twice. **Expected values are literals, or come from an independent source** — the spec,
the rate card, a hand-worked example, the client's own document. Work it out on paper, then hard-
code it. A magic number with a comment explaining where it came from is *better* than a formula.

**3. Reimplementing instead of loading, when the runtime is awkward.** For a service worker, a
bundled script, anything hard to import: load the **real source** into a sandboxed harness. It's
more work than rewriting the logic, and it's the only version that tests anything.

**4. Mocking so much the real code never runs.** If every collaborator is a mock, the test
asserts your mocks agree with each other. Mock the *boundary* — the network, the clock, the
database — never the thing under test.

### The check

> **If the implementation were deleted, would this test still pass?**

If yes, it's testing a copy. Ask it about the *expected values* too, not just the call: if the
implementation's formula changed to something wrong, would the expected value change with it and
keep the test green?

This is `/review-gate` lens 3's sharpest question, and it's worth asking yourself before it gets
asked of you.

## Exact assertions, not vacuous ones

`len(result.unstaffed) == 3` — not "the solve succeeded".

A test that asserts the code ran is a test that passes when the code is wrong. Assert the value,
the count, the shape, the specific field. If the assertion would still hold after you break the
feature, it isn't an assertion.

## Meaningful coverage, not maximal coverage

Cover logic and interactive components. Do not cover trivial wrappers to move a percentage.

Write them **during the build, not as cleanup after**. Tests written afterwards are shaped by the
implementation you already wrote; tests written alongside are shaped by the spec. The second kind
finds bugs.

Coverage percentage is not a goal. "Every branch of this rule, both sides of this boundary, and
the error path" is a goal.

## Boundary specs — the highest-value pattern

When a rule has a threshold, spec the boundary from both sides **and** prove the value isn't
hardcoded.

For a configurable threshold that classifies a gap:

- gap = 180min → `"break"` (exclusive lower bound — the boundary itself, from below)
- gap = 181min → `"rest_room"` (first value past it)
- gap = configured cap − 1min → `"rest_room"`
- gap = configured cap exactly → `"violation"` (the boundary from the other side)
- **a run with a non-default cap (e.g. 200 instead of 240) shifts the violation boundary
  accordingly** — this is the one that proves the threshold is read from config, not baked in

That last case is the one people skip, and it's the one that catches a hardcoded constant.

Alongside the boundary, spec:

- **Every position the case can occur in** — first, middle, last. A classifier that works on a
  mid-list element and breaks on the first one is a real bug that per-case tests miss.
- **Zero and one-element cases** — and *decide* what the right answer is (empty list? omitted
  field?) rather than discovering it in production.
- **A consistency regression** — when a new computation overlaps an existing one, assert they
  agree (e.g. the sum of the new per-day classifications equals the existing scenario-level KPI).
  This is what stops two implementations of the same rule drifting apart later.

## Issue → change-request test mirroring

**When the issue specs the boundary cases, the implementing change request's test plan reports
back against exactly those cases.** Same list, same order, ticked off.

This is the standard, not a nice-to-have. It makes the review mechanical: the reviewer diffs the
issue's `## Tests` against the change request's `## Test plan` and any gap is visible without
reading a line of code. If you're writing the issue, spec the cases (see `/scoping`). If you're
writing the change request, answer them (see `/good-mr`).

## Green is necessary, never sufficient

A passing suite is not evidence the feature works. Before calling it done, exercise the real
thing: server up, job actually run, page actually loaded, output actually looked at.

If you claim you verified something, attach what you ran and what it printed. If you couldn't
verify it, say so plainly — see `/good-mr` on disclosing what wasn't done.

## Two questions to ask yourself before claiming done

1. **"Is this just a workaround for the test to pass, or am I actually handling what the test
   should be covering?"** If you changed the test to match the code rather than the code to match
   the spec, stop.
2. **"What is the goal of this test?"** If you can't say what it proves in one sentence, it isn't
   a test yet.

## Changing a test is not the same as weakening one

Sometimes a test's premise becomes false **by design** — the feature legitimately changed. That's
fine. Rewrite it, and **say so explicitly**, naming the premise that died and why.

Real precedent: a change request rewrote a test whose premise ("this endpoint never polls the upstream
service") was now false by design, and explained that in the test plan. A reviewer could evaluate
the decision.

What's not fine is loosening an assertion, deleting a case, or adding a skip to get to green.
The difference is whether you can name the design decision behind it. If you can't, you're
bending the test.

## Structuring the suite

Portable shape — the specific libraries are an example, not the law:

- **Layer the tests.** Router / service / repository (or equivalent) tested separately, so a
  failure localises. An integration test that's the only coverage tells you *something* broke.
- **Use a fake or in-memory stand-in** when a test doesn't need the real database. Keep a real
  one for the tests that are actually about persistence.
- **Shared factories and helpers** so tests build real fixtures instead of duplicating setup.
  Duplicated setup drifts, and drifted setup hides bugs.
- Example instantiation: pytest + an async HTTP client + session-scoped temp-DB fixtures on the
  backend; Vitest + Testing Library + jsdom with shared factories on the frontend.

## Anti-patterns

- Claiming a regression test works without watching it fail on the old code.
- Assertions that pass whether or not the feature works ("it returned something").
- Writing tests after the build, shaped by the code instead of the spec.
- Speccing a threshold's boundary but never a non-default value — the hardcoded constant survives.
- **Reimplementing the logic under test inside the test** — in any of its four forms, and
  especially as an expected value computed the same way the code computes it.
- Mocking the thing under test instead of the boundary around it.
- Loosening an assertion or adding a skip to get green, without naming a design decision.
- Chasing a coverage number by testing trivial wrappers.
- Calling it done because it's green, without ever running the real thing.

## Related

- `/review-gate` — the review lens that checks work against these rules
- `/scoping` — speccing the boundary cases in the issue, so the change request can mirror them
- `/good-mr` — reporting the test plan, and disclosing what you didn't verify
- `/delivery-loop` — where testing sits in the end-to-end flow
