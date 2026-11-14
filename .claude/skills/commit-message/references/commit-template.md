# Commit message template

Copy the skeleton, replace every `<placeholder>`, delete what doesn't apply.

## Skeleton

```
<type>(<scope>): <imperative summary, lowercase, no period, ~70 chars>

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
<type>(<scope>): <imperative summary>
```

Use this only when the change genuinely explains itself. If you're unsure, it doesn't.

## Types

| type | use |
|---|---|
| `fix` | a bug |
| `feat` | new capability |
| `docs` | documentation only |
| `test` | tests only |
| `chore` | housekeeping, no runtime effect |
| `ci` | pipeline config |
| `perf` | performance work |
| `refactor` | behaviour-preserving restructure |
| `ops` | deployment / infra |
| `data` | seed files, fixtures, data assets |
| `test+docs` | compound — legitimate when it genuinely is both |

## Scopes

- **underscore** for code packages — `backend`, `webapp`, `data_pipeline`, `solver_engine`
- **hyphen** for UI feature areas — `search-panel`, `user-settings`
- **comma** for multi — `feat(backend,webapp):`
- **one spelling per target, always.** Never `data_pipeline` in one commit and
  `data-pipeline` in the next — `git log --grep` will quietly miss half your history.

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

- [ ] Subject is imperative, lowercase after the colon (unless it starts with an identifier or
      proper noun), no trailing period
- [ ] Subject is ~70–72 chars — **not** padded down to 50
- [ ] Subject says the finding, not the type (`fix: fix the thing` is not a message)
- [ ] Body exists — it almost always should — and leads with **why**, not what
- [ ] Body names the alternative you rejected — "instead of ..."
- [ ] Bullets use `- ` only; wrapped at 72
- [ ] `Verified:` line present if "it works" isn't self-evident from the diff
- [ ] Issue trailer on the last line, keyword repeated per issue
- [ ] Addressing a review comment? Quote the claim you're responding to
- [ ] One logical change — if you can't name it in one subject, it's two commits
