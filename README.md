# agent-growth

**A Git-like, auditable, rollback-able growth layer for AI agents.**

Your agent remembers. But does it get *better* — and can you prove it?

Most "AI memory" stores facts. `agent-growth` stores **rules learned from your corrections**, versioned in Git, reviewable, conflict-checked, and revertible with one command. It is the missing *governance* layer between "the agent remembered something" and "the agent is trustworthy enough to keep improving."

> 记住 ≠ 成长。可信的成长 = 纠正一次 → 沉淀一条规则 → 可审查、可冲突检测、可一键回滚。

---

## Why

Every self-evolving agent today has the same black hole: **it changes, but you can't see what changed, why, or undo it.** That is not growth — that is drift.

`agent-growth` fixes the three things that make agent growth untrustworthy:

| Problem | What this layer does |
|---|---|
| "It forgot my correction next session" | Rules persist in a Git repo and are injected into every prompt |
| "It got worse and I can't tell why" | Every rule is a commit with source + timestamp |
| "Two corrections now contradict" | New rules are conflict-checked before they go active |
| "I want the old behavior back" | `growth rollback <id>` — literally `git revert` |

---

## 30-second demo

```bash
$ growth add "don't use emojis in code comments"
stored 20261124-031500-a1b2c3: Never use emojis in code comments.

$ growth rules
## Growth Rules (learned from your past corrections)

- [20261124-031500-a1b2c3] Never use emojis in code comments.

$ growth log
1f3c2a1  2026-11-24  rule: Never use emojis in code comments.

$ growth rollback 20261124-031500-a1b2c3
reverted 1f3c2a1
```

That is the whole idea: **a correction becomes a versioned, reviewable rule that an agent actually obeys — and that you can undo.**

---

## Install

```bash
pip install -e .
```

Requires Python 3.9+ and `git` on PATH. No other dependencies.

Optional — for LLM-powered rule extraction and conflict detection (otherwise the raw correction is stored as-is):

```bash
export GROWTH_LLM_KEY=sk-...          # DeepSeek / Doubao / Tongyi / OpenAI compatible
export GROWTH_LLM_BASE=https://api.deepseek.com/v1
export GROWTH_LLM_MODEL=deepseek-chat
```

---

## CLI

```bash
growth add "<correction>" [--context TEXT]   # extract + store a rule
growth rules                                 # print the active rules block
growth log [-n 20]                           # rule history
growth rollback <id>                         # git revert a rule
growth inject [--out prompt.md]              # write the rules block to a file
growth mcp                                   # run as an MCP server over stdio
```

---

## Use it from Claude Code / Cursor (MCP)

Add the server to your MCP config:

```json
{
  "mcpServers": {
    "growth": {
      "command": "growth",
      "args": ["mcp"]
    }
  }
}
```

The agent then gets four tools:

- `growth_get_rules` — pull the current growth rules into its context
- `growth_add_correction` — record a correction; a rule is extracted and stored
- `growth_log` — inspect history
- `growth_rollback` — undo a rule

A minimal loop:

1. Agent does a task.
2. You correct it once.
3. The agent calls `growth_add_correction`.
4. Next session it calls `growth_get_rules` first — and stops making that mistake.

---

## How it works

```
correction ──▶ extract (LLM) ──▶ conflict check (LLM) ──▶ store (Git commit)
                                                              │
                              prompt injection ◀── rules block ┘
                                      │
                              rollback = git revert
```

- **Storage**: `.growth/rules/*.md`, one file per rule, frontmatter = metadata.
- **History**: the `.growth/` directory is its own Git repo. `git log` is the audit trail.
- **Safety**: conflicting rules are stored with `status: conflict` and never injected until reviewed.
- **Integration**: plain prompt block + MCP tools. No vendor lock-in.

A rule file looks like this:

```markdown
---
{
  "id": "20261124-031500-a1b2c3",
  "created": "2026-11-24T03:15:00",
  "source": "cli",
  "status": "active"
}
---

Never use emojis in code comments.
```

---

## Tests

```bash
python -m pytest -q
```

---

## Roadmap

- [ ] Rule decay: age out stale rules, surface them for review
- [ ] Team mode: shared rule repo with per-author attribution
- [ ] Diff view: render a rule's full evolution
- [ ] Conflict resolution UI

---

## License

MIT.
