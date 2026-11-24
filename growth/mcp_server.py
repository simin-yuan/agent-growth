"""Zero-dependency MCP server (JSON-RPC 2.0 over stdio).

Exposes five tools:
    growth_get_rules      -> prompt block of active rules
    growth_learn          -> extract + conflict-check + store a rule from a correction
    growth_resolve        -> resolve a conflict rule (keep-new / keep-old / keep-both)
    growth_rollback       -> revert a rule by id
    growth_log            -> recent rule history
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
    "agent-growth is a Git-like growth layer. At session start call growth_get_rules and follow them. "
    "When the user corrects you or states a preference, call growth_learn with the correction. "
    "If growth_learn returns status=conflict, show the user the conflicting rule and, after they decide, "
    "call growth_resolve with action keep-new | keep-old | keep-both. "
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
        "description": "Record a user correction; extract, conflict-check and store a reusable rule.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "correction": {"type": "string", "description": "What the user corrected"},
                "context": {"type": "string", "description": "Optional task context"},
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
            rule = extract_rule(args.get("correction", ""), args.get("context", ""))
            if not rule:
                return _text({"status": "skipped", "reason": "not a reusable rule"})
            conf = check_conflict(rule, store.active_rules())
            status = "conflict" if conf["conflict"] else "active"
            rid = store.add_rule(
                rule,
                source="mcp",
                status=status,
                conflicts_with=conf["ids"] if conf["conflict"] else None,
            )
            payload = {"id": rid, "rule": rule, "status": status, "rollback": f"growth rollback {rid}"}
            if conf["conflict"]:
                payload["conflict"] = {"reason": conf["reason"], "ids": conf["ids"]}
                payload["hint"] = "call growth_resolve(rule_id, action) after the user decides"
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
