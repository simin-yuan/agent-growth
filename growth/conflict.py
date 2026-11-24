"""Detect whether a new rule contradicts existing active rules."""

from __future__ import annotations

from .llm import LLM

_SYSTEM = (
    "You are a rule conflict detector for an AI agent's rule store. "
    "Given existing rules (each with an id) and one new rule, decide if the new rule "
    "contradicts or makes any existing rule unsafe. "
    "Reply in exactly two lines:\n"
    "Line 1: OK or CONFLICT\n"
    "Line 2: a one-line reason. If CONFLICT, append ' |ids=id1,id2' listing the conflicting rule ids."
)


def check_conflict(new_rule: str, active_rules: list[dict], llm: LLM | None = None) -> dict:
    llm = llm or LLM()
    if not llm.available() or not active_rules:
        return {"conflict": False, "reason": "", "ids": []}
    existing = "\n".join(f"- {r['id']}: {r['text']}" for r in active_rules)
    out = llm.chat(_SYSTEM, f"existing rules:\n{existing}\n\nnew rule:\n{new_rule}")
    if not out:
        return {"conflict": False, "reason": "", "ids": []}
    first, _, rest = out.partition("\n")
    conflict = first.strip().upper().startswith("CONFLICT")
    reason = rest.strip()
    ids: list[str] = []
    if "|ids=" in reason:
        reason, _, idpart = reason.partition("|ids=")
        ids = [x.strip() for x in idpart.replace("|", ",").split(",") if x.strip()]
        reason = reason.strip(" .|")
    return {"conflict": conflict, "reason": reason, "ids": ids}
