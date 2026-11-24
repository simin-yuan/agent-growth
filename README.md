# agent-growth

**A Git-like, auditable, rollback-able growth layer for AI agents.**

Your agent remembers. But does it get *better* — and can you prove it?

Most "AI memory" stores facts. `agent-growth` stores **rules learned from your corrections**, versioned in Git, reviewable, conflict-checked, and revertible with one command. It is the missing *governance* layer between "the agent remembered something" and "the agent is trustworthy enough to keep improving."

> 记住 ≠ 成长。可信的成长 = 纠正一次 → 沉淀一条规则 → 可审查、可冲突检测、可一键回滚。

---

## Why

Every self-evolving agent today has the same black hole: **it changes, but you can't see what changed, why, or undo it.** That is not growth — that is drift.

`agent-growth` fixes the four things that make agent growth untrustworthy:

| Problem | What this layer does |
|---|---|
| "It forgot my correction next session" | Rules persist in a Git repo and are injected into every prompt |
| "It got worse and I can't tell why" | Every rule is a commit with source + timestamp |
| "Two corrections now contradict" | New rules are conflict-checked before they go active |
| "I want the old behavior back" | `growth rollback <id>` — literally `git revert` |

---

## What's new in v0.2

- **Agent-driven learning** — the agent calls `growth_learn` itself when you correct it; no terminal commands needed.
- **Conflict gate + resolution loop** — a contradicting rule is stored as `status: conflict`, never injected, and surfaced for a one-command decision: `keep-new` / `keep-old` / `keep-both`.
- **One-command MCP setup** — `growth init --target claude|cursor` writes the MCP config for you (with `--dry-run` preview).
- **Bring your own model** — any OpenAI-compatible endpoint (DeepSeek / Doubao / Tongyi / SiliconFlow / OpenAI) via `GROWTH_LLM_BASE_URL`.

---

## 30-second demo

```bash
$ growth add "注释用中文"
stored 20261124-031500-a1b2c3: 注释用中文 (status=active)

$ growth add "注释全用英文"
stored 20261124-031600-d4e5f6: 注释全用英文 (status=conflict)
!! conflict: contradicts a1b2c3 (注释用中文)
run `growth conflicts`, then `growth resolve <id> --keep-new|--keep-old|--keep-both`

$ growth conflicts
[20261124-031600-d4e5f6] 注释全用英文
  conflicts with [20261124-031500-a1b2c3] 注释用中文

$ growth resolve 20261124-031600-d4e5f6 --keep-new
{"id": "20261124-031600-d4e5f6", "action": "keep-new", "superseded": ["20261124-031500-a1b2c3"]}
```

The conflicting rule is now active, the old one is `superseded`, and `git log` shows exactly what happened and why.

---

## Install

```bash
pip install -e .
```

Requires Python 3.9+ and `git` on PATH. No other dependencies.

Optional — for LLM-powered rule extraction and conflict detection (otherwise the raw correction is stored as-is):

```bash
export GROWTH_LLM_KEY=sk-...                       # DeepSeek / Doubao / Tongyi / OpenAI compatible
export GROWTH_LLM_BASE_URL=https://api.deepseek.com/v1
export GROWTH_LLM_MODEL=deepseek-chat
```

---

## CLI

```bash
growth add "<correction>" [--context TEXT]   # extract + conflict-check + store a rule
growth rules                                 # print the active rules block
growth conflicts                             # show unresolved conflict rules
growth resolve <id> --keep-new|--keep-old|--keep-both
growth log [-n 20]                           # rule history
growth rollback <id>                         # git revert a rule
growth inject [--out prompt.md]              # write the rules block to a file
growth init --target claude|cursor|both [--dry-run]
growth mcp                                   # run as an MCP server over stdio
```

---

## Use it from Claude Code / Cursor (MCP)

One command:

```bash
growth init --target claude     # writes .mcp.json
growth init --target cursor     # writes .cursor/mcp.json
```

The agent then gets five tools:

- `growth_get_rules` — pull the current growth rules into its context
- `growth_learn` — record a correction; a rule is extracted, conflict-checked and stored
- `growth_resolve` — decide a conflict: `keep-new` / `keep-old` / `keep-both`
- `growth_rollback` — undo a rule
- `growth_log` — inspect history

A minimal loop:

1. Agent does a task.
2. You correct it once.
3. The agent calls `growth_learn` on its own.
4. Next session it calls `growth_get_rules` first — and stops making that mistake.

If a correction contradicts an existing rule, the agent gets `status=conflict` back, asks you which one wins, then calls `growth_resolve`.

---

## How it works

```
correction ──▶ extract (LLM) ──▶ conflict check (LLM) ──▶ store (Git commit)
                                                              │
                              prompt injection ◀── rules block ┘
                                      │
                         resolve = keep-new / keep-old / keep-both
                                      │
                              rollback = git revert
```

- **Storage**: `.growth/rules/*.md`, one file per rule, frontmatter = metadata.
- **History**: the `.growth/` directory is its own Git repo. `git log` is the audit trail.
- **Safety**: conflicting rules are stored with `status: conflict` and are never injected until resolved.
- **Integration**: plain prompt block + MCP tools. No vendor lock-in.

A rule file looks like this:

```markdown
---
{
  "id": "20261124-031500-a1b2c3",
  "created": "2026-11-24T03:15:00",
  "source": "mcp",
  "status": "active"
}
---

Never use emojis in code comments.
```

---

## Tests

```bash
python -m unittest discover -s tests -v
```

Covers: add → active, conflict gate, `keep-new` / `keep-old` / `keep-both`, rollback restore, MCP surface.

---

## Roadmap

- [ ] Rule decay: age out stale rules, surface them for review
- [ ] Team mode: shared rule repo with per-author attribution
- [ ] Diff view: render a rule's full evolution
- [ ] Web UI for conflict review

---

## License

MIT.
