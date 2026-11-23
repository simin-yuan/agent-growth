"""Detect whether a new rule contradicts existing active rules."""

from __future__ import annotations

from .llm import LLM

_SYSTEM = (
    "You are a rule conflict detector. Given existing rules and one new rule, "
    "answer CONFLICT if they contradict or make each other unsafe, else OK. "
    "First line: CONFLICT or OK. Second line: one-line reason."
)


def check_conflict(new_rule: str, active_rules: list[dict], llm: LLM | None = None) -> dict:
    llm = llm or LLM()
    if not llm.available() or not active_rules:
        return {"conflict": False, "reason": ""}
    existing = "\n".join(f"- {r['id']}: {r['text']}" for r in active_rules)
    out = llm.chat(_SYSTEM, f"existing rules:\n{existing}\n\nnew rule:\n{new_rule}")
    if not out:
        return {"conflict": False, "reason": ""}
    first, _, reason = out.partition("\n")
    return {
        "conflict": first.strip().upper().startswith("CONFLICT"),
        "reason": reason.strip(),
    }
