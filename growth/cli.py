"""Command line interface for agent-growth."""

from __future__ import annotations

import argparse
import json
import pathlib

from .conflict import check_conflict
from .extract import extract_rule
from .inject import build_prompt_block
from .store import RuleStore

SYSTEM_RULE_TEMPLATE = (
    "At the start of every session, call growth_get_rules and follow the returned rules. "
    "When the user corrects your behavior or states a preference, call growth_learn with that correction. "
    "If growth_learn returns status=conflict, show the user the conflicting rule and call growth_resolve "
    "after they choose keep-new / keep-old / keep-both. "
    "Always report the new rule id and how to roll it back."
)

MCP_ENTRY = {"command": "growth", "args": ["mcp"]}


def _merge_mcp_config(path: str, dry_run: bool) -> str:
    p = pathlib.Path(path)
    data: dict = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    servers["growth"] = dict(MCP_ENTRY)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if dry_run:
        print(f"--- {path} (dry-run) ---\n{text}")
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    return text


def _cmd_init(target: str, dry_run: bool) -> None:
    targets = {
        "claude": [".mcp.json"],
        "cursor": [".cursor/mcp.json"],
        "both": [".mcp.json", ".cursor/mcp.json"],
    }
    if target not in targets:
        raise SystemExit(f"unknown target: {target}")
    for t in targets[target]:
        _merge_mcp_config(t, dry_run)
    print("\nPaste this into your agent's system prompt:\n")
    print(SYSTEM_RULE_TEMPLATE)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="growth", description="Git-like growth layer for AI agents")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="add a correction and extract a rule")
    add.add_argument("correction")
    add.add_argument("--context", default="")

    sub.add_parser("rules", help="print active rules block")
    sub.add_parser("conflicts", help="show unresolved conflict rules")

    log = sub.add_parser("log", help="show rule history")
    log.add_argument("-n", type=int, default=20)

    rb = sub.add_parser("rollback", help="revert a rule by id")
    rb.add_argument("id")

    rs = sub.add_parser("resolve", help="resolve a conflict rule")
    rs.add_argument("id")
    group = rs.add_mutually_exclusive_group(required=True)
    group.add_argument("--keep-new", action="store_true")
    group.add_argument("--keep-old", action="store_true")
    group.add_argument("--keep-both", action="store_true")

    inj = sub.add_parser("inject", help="write rules block to a file")
    inj.add_argument("--out", default=None, help="output file, default stdout")

    ini = sub.add_parser("init", help="generate MCP config for your editor")
    ini.add_argument("--target", choices=["claude", "cursor", "both"], default="claude")
    ini.add_argument("--dry-run", action="store_true")

    sub.add_parser("mcp", help="run the MCP server over stdio")

    args = parser.parse_args(argv)
    store = RuleStore()

    if args.cmd == "add":
        rule = extract_rule(args.correction, args.context)
        if not rule:
            print("NONE: not a reusable rule")
            return
        conf = check_conflict(rule, store.active_rules())
        status = "conflict" if conf["conflict"] else "active"
        rid = store.add_rule(
            rule,
            source="cli",
            status=status,
            conflicts_with=conf["ids"] if conf["conflict"] else None,
        )
        print(f"stored {rid}: {rule} (status={status})")
        if conf["conflict"]:
            print(f"!! conflict: {conf['reason']}")
            print("run `growth conflicts`, then `growth resolve <id> --keep-new|--keep-old|--keep-both`")
    elif args.cmd == "rules":
        print(build_prompt_block(store))
    elif args.cmd == "conflicts":
        conflicts = store.conflict_rules()
        if not conflicts:
            print("no conflicts")
        for c in conflicts:
            print(f"[{c['id']}] {c['text']}")
            for oid in c["meta"].get("conflicts_with", []):
                old = store.get_rule(oid)
                if old:
                    print(f"  conflicts with [{oid}] {old['text']}")
    elif args.cmd == "log":
        for h, s, d in store.log(args.n):
            print(f"{h}  {d}  {s}")
    elif args.cmd == "rollback":
        print("reverted", store.rollback(args.id))
    elif args.cmd == "resolve":
        action = "keep-new" if args.keep_new else "keep-old" if args.keep_old else "keep-both"
        print(json.dumps(store.resolve(args.id, action), ensure_ascii=False))
    elif args.cmd == "inject":
        block = build_prompt_block(store)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(block)
            print(f"written {len(block)} chars to {args.out}")
        else:
            print(block)
    elif args.cmd == "init":
        _cmd_init(args.target, args.dry_run)
    elif args.cmd == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()


if __name__ == "__main__":
    main()
