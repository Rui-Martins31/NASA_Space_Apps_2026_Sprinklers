# The Workflow Pack — 9 skills for shipping with AI agents

Skills for shipping real work with AI agents: how to scope it, build it, test it, review it, and
know when it's actually done.

They describe what holds up in practice, not what sounds right in a style guide — which is why
some of the advice is deliberately counter-conventional (commit subjects run to ~70 characters,
not 50; an unchecked box in a change request is a feature, not an admission).

The skills are **tracker-agnostic**: issues and code review run through whatever you use —
GitLab, GitHub, Jira, Azure DevOps — via that tool's CLI, and fall back to plain markdown files
when there's no tracker at all. "Change request" is the neutral term for the reviewable unit (a
*merge request* on GitLab, a *pull request* on GitHub / Azure DevOps). The concrete examples use
`glab` as the default flavor, and `/using-glab` is the GitLab implementation of that interface
role.

**Start here:** open `workflow-pack.html` in a browser. It's the whole pack, readable, with a
copy button on every skill and template. Nothing to install to read it.

## Install

Each skill is a folder containing a `SKILL.md`. Copy the `skills/` contents into
`~/.codex/skills/`:

```bash
unzip workflow-pack.zip
cp -R workflow-pack/skills/* ~/.codex/skills/
```

Then invoke a skill by its slash command — `/review-gate`, `/scoping`, `/delivery-loop` — or just
work, and the agent will trigger it from the description.

**Take what helps.** They're independent enough to adopt one at a time. If you only take one,
take `/delivery-loop` — it's the backbone the others hang off.

## What's in here

```
skills/
  delivery-loop/SKILL.md          the backbone: issue → branch → test → change request → review → merge
  extensive-interview/SKILL.md    inception, a big pivot, a critical new domain
    references/README.md              functional vs non-functional, and how to tell
    references/functional-requirements-template.md
    references/non-functional-requirements-template.md
    references/docs-bootstrap.md      the doc set to start from when there are none
  scoping/SKILL.md                a small or medium change → a filed issue
    references/issue-template.md      copy-pasteable
    references/issue-exemplar.md      a real, well-structured issue
  test-design/SKILL.md            comprehensive but focused; the gate that never bends
  commit-message/SKILL.md         what it contains, and what it addresses
    references/commit-template.md
  using-glab/SKILL.md             the GitLab CLI, and its potholes
  review-gate/SKILL.md            four lenses + the simplicity ladder, before you call it done
  good-mr/SKILL.md                a change request a reviewer can trust
    references/mr-template.md
    references/mr-exemplar.md         a real, well-executed change request
  teach-me/SKILL.md               explaining how and why, so people learn from what they read

workflow-pack.html                the whole pack as a readable field guide
```

## The thesis, in one breath

Hand the agent a lot of rope — a terse instruction and an issue number is often the whole spec —
and hold a small number of gates that never move:

- A regression test is **provably red before the fix and green after**.
- A claim of "it works" needs **real output behind it**. ("Did you run it?")
- **Docs are the source of truth**, not paperwork written afterward.
- Every unit of work gets an **independent review** before it's called done.
- **Ask before guessing** on anything genuinely open.

Almost everything else — how the work organises itself internally, which agent does what, which
recommended option wins — matters much less than people think.

## Three ideas worth stealing even if you take nothing else

1. **The unchecked box.** In a change request, `- [ ] Manual smoke test — not done from this
   environment` is worth more than any amount of prose. A silent gap looks complete; the reviewer
   finds out in production.

2. **"I can't see this from the repo."** The biggest way clarifying questions fail: an agent
   offers four reasonable options and all four are wrong, because the real answer is
   infrastructure only the human knows about. Before offering a multiple choice, ask whether the
   answer could live outside the repo. If it might, ask openly instead.

3. **Verify the reviewer, not just the implementer.** A reviewer reporting "2 pre-existing test
   failures" when there are 5, plus a flaky 6th it never saw. A review pass producing 6 findings
   of which 1 survives checking. Reviewers are agents too, with the same failure modes.

## Notes

- **Project- and tracker-agnostic** — no repo paths, no project-specific test commands, and no
  assumption about which issue tracker or code-review tool you use. `glab` (GitLab) is the
  concrete default flavor in the examples because a real command beats an abstraction; swap in
  your tracker's CLI, or drop to markdown files, and the workflow is unchanged.
- **AIR ships separately** (`develop-for-air`), since it's internal infrastructure and most
  projects don't touch it.
- **A skill has to be invoked.** It can't fire itself when an agent finishes — that needs a hook,
  or a standing line in a project's `AGENTS.md`. The known failure mode is that a standing
  instruction (review every unit, update the docs, exhaustive tests) quietly lapses on a long
  session. Treat that as a bug in the process, not an acceptable shortcut.
