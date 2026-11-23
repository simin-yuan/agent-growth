"""Build the prompt block that gets injected into an agent's system prompt."""

from __future__ import annotations

import pathlib

from .store import RuleStore

HEADER = "## Growth Rules (learned from your past corrections)"


def build_prompt_block(store: RuleStore | None = None) -> str:
    store = store or RuleStore()
    rules = store.active_rules()
    if not rules:
        return ""
    lines = [HEADER, "", "Apply these rules. They were learned from explicit user corrections.", ""]
    for r in rules:
        lines.append(f"- [{r['id']}] {r['text']}")
    return "\n".join(lines)


def inject_to_file(target: str, store: RuleStore | None = None) -> int:
    block = build_prompt_block(store)
    pathlib.Path(target).write_text(block, encoding="utf-8")
    return len(block)
