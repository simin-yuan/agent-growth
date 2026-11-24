"""Zero-dependency MCP server (JSON-RPC 2.0 over stdio).

Tools:
    growth_get_rules
    growth_learn      host-driven rule extraction -> zero API key in MCP mode
    growth_resolve
    growth_rollback
    growth_log
"""

from __future__ import annotations

import json
import sys

from .conflict import check_conflict
from .extract import extract_rule
from .inject import build_prompt_block
from .store import RuleStore

_SERVER_INFO = {"name": "growth", "version": "0.2.0"}

_INSTRUCTIONS = (
    "agent-growth is a Git-like, conflict-checked growth layer for you. "
    "At session start call growth_get_rules and follow them. "
    "Before calling growth_learn, call growth_get_rules first: (1) distill the user's correction into ONE clear rule "
    "and pass it as `rule`; (2) if that rule contradicts an existing rule, pass the conflicting rule id in "
    "`conflicts_with` (an empty list if none). This enables zero-API-key mode. "
    "If `rule` is omitted, the server falls back to GROWTH_LLM_KEY or stores the raw correction. "
    "If growth_learn returns status=conflict, show the user the conflicting rule and, after they decide, call "
    "growth_resolve with action keep-new | keep-old | keep-both. "
    "Report the new rule id and the rollback command."
)

_TOOLS = [
    {
        "name": "growth_get_rules",
        "description": "Get the active growth rules to inject into your system prompt.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "growth_learn",
        "description": (
            "Record a user correction as a reusable rule. "
            "Pass `rule` (one clear sentence you extracted) and `conflicts_with` "
            "(ids of existing rules it contradicts, [] if none) to work without any API key."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "correction": {"type": "string", "description": "What the user corrected"},
                "context": {"type": "string", "description": "Optional task context"},
                "rule": {
                    "type": "string",
                    "description": "Host-extracted one-line rule (recommended; enables zero-API-key mode)",
                },
                "conflicts_with": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of existing active rules this rule contradicts (from growth_get_rules)",
                },
            },
            "required": ["correction"],
        },
    },
    {
        "name": "growth_resolve",
        "description": "Resolve a conflict rule: keep-new, keep-old, or keep-both.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string"},
                "action": {"type": "string", "enum": ["keep-new", "keep-old", "keep-both"]},
            },
            "required": ["rule_id", "action"],
        },
    },
    {
        "name": "growth_rollback",
        "description": "Roll back a rule by id (git revert).",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "growth_log",
        "description": "Show recent rule history.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "default": 20}},
        },
    },
]


def _text(payload) -> dict:
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False)
    return {"content": [{"type": "text", "text": payload}]}


def _learn(
    store: RuleStore,
    correction: str,
    context: str = "",
    rule: str | None = None,
    conflicts_with: list[str] | None = None,
) -> dict:
    """Host-driven learning.

    Priority for the rule text:
      1. `rule` supplied by the host agent (zero API key)
      2. LLM extraction (if GROWTH_LLM_KEY is set)
      3. raw correction fallback
    Priority for conflict detection:
      1. `conflicts_with` supplied by the host (zero API key) — [] means "no conflict"
      2. LLM conflict check (if GROWTH_LLM_KEY is set)
      3. no conflict
    """
    if rule and rule.strip():
        rule_text = rule.strip()
    else:
        rule_text = extract_rule(correction, context)
    if not rule_text:
        return {"status": "skipped", "reason": "not a reusable rule"}

    if conflicts_with is not None:
        ids = [str(x).strip() for x in conflicts_with if str(x).strip()]
        reason = "host-detected conflict" if ids else ""
    else:
        conf = check_conflict(rule_text, store.active_rules())
        ids = conf["ids"]
        reason = conf["reason"]

    active_ids = {r["id"] for r in store.active_rules()}
    ids = [i for i in ids if i in active_ids]
    status = "conflict" if ids else "active"
    rid = store.add_rule(
        rule_text,
        source="mcp",
        status=status,
        conflicts_with=ids if ids else None,
    )
    payload = {"id": rid, "rule": rule_text, "status": status, "rollback": f"growth rollback {rid}"}
    if ids:
        payload["conflict"] = {"reason": reason or "host-detected conflict", "ids": ids}
        payload["hint"] = "call growth_resolve(rule_id, action) after the user decides"
    return payload


def _handle(msg: dict, store: RuleStore) -> dict | None:
    method = msg.get("method")
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": _SERVER_INFO,
            "instructions": _INSTRUCTIONS,
        }
    if method == "tools/list":
        return {"tools": _TOOLS}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {}) or {}

        if name == "growth_get_rules":
            return _text(build_prompt_block(store))

        if name in ("growth_learn", "growth_add_correction"):
            payload = _learn(
                store,
                args.get("correction", ""),
                args.get("context", ""),
                args.get("rule"),
                args.get("conflicts_with"),
            )
            return _text(payload)

        if name == "growth_resolve":
            try:
                res = store.resolve(args["rule_id"], args["action"])
            except Exception as exc:  # noqa: BLE001
                return {**_text(f"error: {exc}"), "isError": True}
            return _text(res)

        if name == "growth_rollback":
            try:
                commit = store.rollback(args["id"])
            except Exception as exc:  # noqa: BLE001
                return {**_text(f"error: {exc}"), "isError": True}
            return _text(f"reverted {commit}")

        if name == "growth_log":
            return _text(store.log(args.get("n", 20)))

    return None


def main() -> None:
    store = RuleStore()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in msg:
            continue  # notification
        result = _handle(msg, store)
        if result is None:
            resp = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "method not found"}}
        else:
            resp = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
