"""Turn one user correction into one reusable rule."""

from __future__ import annotations

from .llm import LLM

_SYSTEM = (
    "You extract ONE reusable behavior rule from a user's correction to an AI agent. "
    "Output a single imperative sentence in the user's language, no explanation, no markdown. "
    "If the correction is too situational to reuse, output exactly: NONE"
)


def extract_rule(correction: str, context: str = "", llm: LLM | None = None) -> str:
    llm = llm or LLM()
    if llm.available():
        out = llm.chat(_SYSTEM, f"correction: {correction}\ncontext: {context}")
        if out:
            text = out.strip().strip("`").strip()
            if text.upper() == "NONE" or not text:
                return ""
            return text
    # graceful fallback: store the raw correction as the rule
    return correction.strip()
