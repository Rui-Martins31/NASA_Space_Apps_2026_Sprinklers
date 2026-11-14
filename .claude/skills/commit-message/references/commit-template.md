# Commit message template

Copy the skeleton, replace every `<placeholder>`, delete what doesn't apply.

## Skeleton

```
[<AREA>] <Imperative summary, no period, ~70 chars>

<The problem or root cause. Lead with the observed symptom — ideally the
live one someone actually reported. Then why it happens. Wrap at 72.>

<The fix, and why THIS approach instead of <the obvious alternative>.
State non-goals if you deliberately avoided a bigger change.>

<Optional: consequences, blast radius, anything a reviewer should know
that the diff doesn't show.>

Verified: <what you ran and what it showed>

Closes #<N>
```

## Minimal form (trivial change only)

```
[<AREA>] <Imperative summary>
```

Use this only when the change genuinely explains itself. If you're unsure, it doesn't.

## Area prefixes (team rule — mandatory)

```
git commit -m "[BACKEND] Text"
git commit -m "[FRONTEND] Text"
git commit -m "[DATASET] Text"
git commit -m "[TOOLS] Text"
```

| prefix | use |
|---|---|
| `[BACKEND]` | backend code — `backend/` |
| `[FRONTEND]` | frontend code — `frontend/` |
| `[DATASET]` | the data and the pipeline that builds it — `data/` |
| `[TOOLS]` | tooling: scripts, Claude skills/config, CI, dev setup |

- Exactly these four spellings, upper case, in square brackets. Never `[Backend]`, `[DATA]`.
- No `type(scope):` on top. The verb ("Fix", "Add", "Refactor") carries the kind of change.
- Spans two areas? Usually two commits. Fits none? Ask the team before inventing a tag.

## Issue trailers

Last line of the body. Pick one:

```
Closes #<N>                    <- this commit resolves it
Refs #<N>                      <- related, doesn't close it
Part of #<N>                   <- one piece of a larger issue or epic
```

Multiple issues — repeat the keyword:

```
Closes #61, Closes #62
```

Never:

```
Closes #61, #62                <- the second doesn't link
Fixes #61                      <- not the convention here; use Closes
```

## Rules checklist

- [ ] Subject starts with `[BACKEND]`, `[FRONTEND]`, `[DATASET]` or `[TOOLS]`
- [ ] Subject is imperative, capitalised after the tag, no trailing period
- [ ] Subject is ~70–72 chars — **not** padded down to 50
- [ ] Subject says the finding, not the area (`[BACKEND] Fix the backend` is not a message)
- [ ] Body exists — it almost always should — and leads with **why**, not what
- [ ] Body names the alternative you rejected — "instead of ..."
- [ ] Bullets use `- ` only; wrapped at 72
- [ ] `Verified:` line present if "it works" isn't self-evident from the diff
- [ ] Issue trailer on the last line, keyword repeated per issue
- [ ] Addressing a review comment? Quote the claim you're responding to
- [ ] One logical change — if you can't name it in one subject, it's two commits
