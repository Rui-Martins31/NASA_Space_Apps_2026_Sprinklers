---
name: using-glab
description: "How to drive the GitLab CLI (glab) effectively — flag semantics that differ per subcommand, the gh-isms that don't exist, passing multi-line descriptions safely, and glab api as the escape hatch. Use whenever creating/viewing/merging MRs or issues, checking CI, or scripting against GitLab."
trigger: /using-glab
---

# /using-glab

`glab` looks like `gh`. It is not `gh`. Almost every failure comes from assuming otherwise.

Read the meta-pattern first; it explains the rest.

> **This is the GitLab flavor of the tracker interface.** The workflow skills — `/scoping`,
> `/good-mr`, `/review-gate`, `/delivery-loop` — drive issues and change requests through
> whatever tracker your project uses; this skill is the concrete `glab` implementation of that
> role, and the default flavor in the examples throughout the pack. On GitHub, Jira, or Azure
> DevOps you'd reach for that tool's CLI (`gh`, the Jira CLI, `az`) the same way — the shape of
> the advice carries over; the specific flags below are GitLab's.

## The meta-pattern

**glab's flag semantics are inconsistent across subcommands, and most mistakes are `gh`-isms.**

The same word means different things — or nothing — depending on the subcommand:

| Flag | Works on | Fails on |
|---|---|---|
| `--branch` | `ci status` | `ci list` (use `-b`) |
| `--output json` | `mr view`, `issue view`, `issue list`, `mr list` | `mr diff` |
| `-a` | `list` — but it means **assignee**, not "all" | anywhere you meant "all" |
| `-m` | `issue note` | `issue close` |

**The rule: run `glab <sub> --help` before porting a flag from a sibling subcommand or from
`gh`.** One `--help` call is cheaper than the three failed attempts it replaces. If you find
yourself reasoning "well `mr view` takes `--output`, so `mr diff` must too" — stop and check.

## Read the output, not the exit code

**Most glab failures are soft.** Pipe through `2>&1` — and you will, to capture the error — and
glab's own errors exit **0**, hiding in stdout. Check for a non-zero exit and you'll miss most
real failures.

**Read what came back.** Don't infer success from the command not throwing. This bites hardest
in scripts and loops, where a silent `ERROR  Unknown flag` scrolls past and you "successfully"
create nothing.

## Auth: check, don't re-authenticate

Run `glab auth status` once at the start. Credentials persist across sessions
(`~/.config/glab-cli/config.yml`), so authenticate only if it actually reports logged-out — then
do it per your team's method for the host. Re-authenticating every session is a round-trip you
don't need.

Tokens do expire, so the re-auth path is real. If auth starts failing,
`glab api personal_access_tokens/self` shows `expires_at`, `active`, and `revoked`.

## The seven that will bite you

Each of these costs multiple attempts if you don't know it. The fix is on the right.

### 1. `--state` does not exist — the most common

```
glab issue list --state opened
→ ERROR  Unknown flag: --state.
```
**Fix:** `--opened` / `--closed` / `--all`.

**Do not "fix" it with `-a all`** — `-a` is *assignee*:
```
glab mr list -a all
→ ERROR  Failed to find user by name: all.
```
For real state filtering beyond these, use `glab api` (below).

### 2. `--branch` on `ci list`

```
glab ci list --branch main
→ ERROR  Unknown flag: --branch.
```
**Fix:** `-b main`. Note `glab ci status --branch main` is *fine*. Same word, two subcommands,
two answers — this is the meta-pattern in miniature.

### 3. `-L` is not `--limit`

```
glab issue list -L 10
→ ERROR  Unknown shorthand flag: 'L' in -L.
```
**Fix:** `--per-page 10` (or `-P 10`).

### 4. You cannot close an issue *with* a comment

```
glab issue close 45 -m "Superseded by the new engine"
→ ERROR  Unknown shorthand flag: 'm' in -m.
```
A pure `gh`-ism — `gh issue close -c` exists, glab has no equivalent. **Fix: two calls.**
```bash
glab issue note 45 -m "Superseded by the new engine"
glab issue close 45
```

### 5. `--description-file` does not exist

```
glab issue create --title '...' --description-file ./issue.md
→ ERROR  Unknown flag: --description-file.
```
**Fix:** `-d "$(cat ./issue.md)"`. There is no `-F` either.

### 6. `mr merge` refuses drafts

```
→ ERROR  This merge request is still a draft; run `glab mr update 62 --ready` to mark it as ready for review.
```
glab hands you the fix. It's a standing two-step:
```bash
glab mr update <n> --ready
glab mr merge <n> --yes
```

### 7. Guessed repo paths 404

```
glab issue list -R git.ltplabs.net/some-group/some-project
→ ERROR  404 Not Found.
```
Project paths are often deeper than you assume (several nested groups). **Fix:** omit `--repo`
entirely when your cwd is inside the repo — glab resolves it from the git remote. If you must
be explicit, hardcode it once:
```bash
REPO="<your-project-path>"   # full nested path, e.g. group/subgroup/team/project
glab issue list -R "$REPO" --opened -P 100
```
**Do not derive it from the remote with `sed`** — a regex that grabs the last two segments
produces a wrong path on nested groups and 404s confusingly.

## Passing descriptions: quoted heredoc

For anything multi-line, this is the idiom:

```bash
glab mr create \
  --title "perf(backend): fix request serialization under concurrent load" \
  --description "$(cat <<'EOF'
## Summary

Closes #<n>. Requests were fully serialized because ...

## Test plan

- [x] Full backend suite — 261 passed
EOF
)" \
  --target-branch main --draft
```

**The quoting on `<<'EOF'` is load-bearing, not style.** Descriptions contain backticks, `$`,
and `#` — unquoted `<<EOF` expands them and you get a mangled body or a shell error.

For long or reusable bodies, write the file first, then `-d "$(cat file)"`. Never reach for
`--description-file` (see #5).

**`-y` / `--yes` is mandatory for non-interactive create** — without it `create` blocks on a
prompt nobody will answer until the call times out.

## `glab api` is the escape hatch

Use it for exactly what the CLI can't express:

```bash
glab api "projects/:id/merge_requests?state=opened&per_page=20"   # real state filtering
glab api "projects/:id/pipelines?ref=main&per_page=3"             # pipelines by ref/sha
glab api -X POST "projects/:id/jobs/<job-id>/retry"               # retry a job
glab api -X PUT projects/:id/merge_requests/<n> -f title="..."    # un-draft / retitle
```

It's also the only way to **merge with a custom commit message** (`glab mr merge` can't set one)
and to upload a file attachment.

**Prefer the `projects/:id/...` shorthand** — it auto-resolves from your cwd's git remote and is
far less error-prone than URL-encoding a nested path (`projects/group%2Fsub%2Fproject/...`),
which you only need from outside the repo.

It emits raw JSON — pipe it: `| python3 -m json.tool`, or
`| python3 -c "import json,sys; print(json.load(sys.stdin)['web_url'])"`.

## Workflow patterns that hold up

- **Create → verify.** After a successful `create`, immediately `glab mr view <n>` (or
  `issue view`). Don't trust the create's own output URL alone — it's the cheapest possible
  confirmation that what you meant to write is what landed.
- **Ready → merge.** `mr update --ready` then `mr merge --yes`.
- **Batch reads in a shell loop:** `for n in 22 23 24; do glab issue view $n; echo "---"; done`.
- **Check the label taxonomy before using one.** Run `glab label list`. If the project defines
  no labels — many don't — **don't invent a taxonomy**. Track work in prose cross-references
  (`Closes #N`, `Part of #N`) instead. Don't add fields the project doesn't use.

## Environment gotchas

- **`_ZO_DOCTOR=0`** — if you use zoxide, its "detected a possible configuration issue" banner
  prints ~7 lines *before* your real output on any `cd`-prefixed call, silently defeating
  `head -n`. Export it to shut the banner up.
- **`status=` is read-only in zsh.** `status=$(glab api ...)` → `read-only variable: status`.
  Use `job_status=` / `pstatus=`. This bites specifically in CI-polling loops, where `status`
  is the natural variable name.
- **Cap polling loops.** A `for i in $(seq 1 20)` loop with 10s sleeps exceeds the 2-minute
  command timeout and gets killed at `Exit code 143`. Keep total loop time under ~120s, or run
  it in the background.

## A blocked merge is a decision, not an error

If a `glab mr merge` is blocked by a permission prompt or a policy classifier — **stop**.

Don't re-run the identical command hoping it passes, and don't reroute through
`glab api -X PUT .../merge` to get the same effect by another path. Both have happened; both
are wrong. The block is a human decision point, not a transient failure. Surface it and ask.

## Anti-patterns

- Porting a flag from `gh`, or from a sibling subcommand, without `--help`.
- Trusting the exit code after `2>&1` instead of reading the output.
- Re-authenticating at the top of every session "just in case".
- Unquoted `<<EOF` for a description containing backticks or `$`.
- `--description-file` / `-F` (they don't exist), or `-a all` (that's assignee).
- Deriving the project path from the git remote with a regex.
- Inventing labels for a project that has none.
- Retrying — or rerouting around — a blocked merge.

## Related

- `/good-mr` — what goes *in* the description you're passing to `mr create`
- `/scoping` — what goes in the issue you're creating
- `/delivery-loop` — where these commands sit in the branch → MR → merge flow
