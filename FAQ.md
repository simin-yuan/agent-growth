# FAQ

## How is this different from just editing `CLAUDE.md`?

`CLAUDE.md` is a static file you edit by hand. `agent-growth` is a runtime layer:
the agent captures a correction itself, stores it as a versioned rule, checks it
against existing rules, and can roll it back. Rules live in Git, so you get an
audit trail and `git revert` for free.

## Does this add token cost?

In MCP mode, no — the host model extracts the rule and passes `conflicts_with`
itself. Only rules with `status: active` are injected, so conflicting drafts never
reach the prompt.

## The conflict detector is too strict / too loose. Can I tune it?

Yes. The detection prompt lives in `growth/conflict.py` (`_SYSTEM`). Point
`GROWTH_LLM_BASE_URL` / `GROWTH_LLM_MODEL` at any OpenAI-compatible model, or let
the host agent do the comparison and pass `conflicts_with` directly.

## Which models are supported?

Any OpenAI-compatible endpoint: DeepSeek, Doubao, Tongyi, SiliconFlow, OpenAI, local
vLLM, etc. Set `GROWTH_LLM_BASE_URL`, `GROWTH_LLM_KEY`, `GROWTH_LLM_MODEL`.

## Where is data stored? Any telemetry?

All data is plain markdown under `.growth/rules/`, inside a local Git repo. No
server, no telemetry, no vector DB.

## Can I share rules across a team or across projects?

Not built in yet (see Roadmap: team mode). Today you can commit `.growth/` or
symlink a shared store.

## What happens if I roll back a rule?

`growth rollback <id>` runs `git revert` on the commit that added the rule. The rule
disappears and the previous state is restored. `growth log` shows the full history.
A second rollback of the same rule gives a clear error instead of a broken repo.

## Does it work on Windows / macOS / Linux?

Yes — pure Python stdlib + `git` on PATH.

## Why Git instead of a vector database?

Because the problem is governance, not retrieval. Git gives versioning, diffs,
authorship, and rollback for free — the three things that make memory *auditable*.
Vector DBs are great at "find similar"; they are terrible at "who changed this,
why, and how do I undo it".
