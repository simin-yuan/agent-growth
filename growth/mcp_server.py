"""Zero-dependency MCP server (JSON-RPC 2.0 over stdio).

Exposes four tools:
    growth_get_rules        -> prompt block of active rules
    growth_add_correction   -> extract + store a rule from a correction
    growth_log              -> recent rule history
    growth_rollback         -> revert a rule by id
"""

from __future__ import annotations

import json
import sys

from .conflict import check_conflict
from .extract import extract_rule
from .inject import build_prompt_block
from .store import RuleStore

_SERVER_INFO = {"name": "growth", "version": "0.1.0"}

_TOOLS = [
    {
        "name": "growth_get_rules",
        "description": "Get the active growth rules to inject into your system prompt.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "growth_add_correction",
        "description": "Record a user correction; extract and store a reusable rule.",
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
        "name": "growth_log",
        "description": "Show recent rule history.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "default": 20}},
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
]


def _handle(msg: dict, store: RuleStore) -> dict | None:
    method = msg.get("method")
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": _SERVER_INFO,
        }
    if method == "tools/list":
        return {"tools": _TOOLS}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        if name == "growth_get_rules":
            return {"content": [{"type": "text", "text": build_prompt_block(store)}]}
        if name == "growth_add_correction":
            rule = extract_rule(args.get("correction", ""), args.get("context", ""))
            if not rule:
                return {"content": [{"type": "text", "text": "NONE: not a reusable rule"}]}
            conf = check_conflict(rule, store.active_rules())
            rid = store.add_rule(rule, source="mcp", status="conflict" if conf["conflict"] else "active")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"id": rid, "rule": rule, "conflict": conf}, ensure_ascii=False
                        ),
                    }
                ]
            }
        if name == "growth_log":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(store.log(args.get("n", 20)), ensure_ascii=False),
                    }
                ]
            }
        if name == "growth_rollback":
            try:
                commit = store.rollback(args["id"])
            except Exception as exc:  # noqa: BLE001
                return {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True}
            return {"content": [{"type": "text", "text": f"reverted {commit}"}]}
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
