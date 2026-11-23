"""Command line interface for agent-growth."""

from __future__ import annotations

import argparse

from .conflict import check_conflict
from .extract import extract_rule
from .inject import build_prompt_block
from .store import RuleStore


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="growth", description="Git-like growth layer for AI agents")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="add a correction and extract a rule")
    add.add_argument("correction")
    add.add_argument("--context", default="")

    sub.add_parser("rules", help="print active rules block")

    log = sub.add_parser("log", help="show rule history")
    log.add_argument("-n", type=int, default=20)

    rb = sub.add_parser("rollback", help="revert a rule by id")
    rb.add_argument("id")

    inj = sub.add_parser("inject", help="write rules block to a file")
    inj.add_argument("--out", default=None, help="output file, default stdout")

    sub.add_parser("mcp", help="run the MCP server over stdio")

    args = parser.parse_args(argv)
    store = RuleStore()

    if args.cmd == "add":
        rule = extract_rule(args.correction, args.context)
        if not rule:
            print("NONE: not a reusable rule")
            return
        conf = check_conflict(rule, store.active_rules())
        rid = store.add_rule(rule, source="cli", status="conflict" if conf["conflict"] else "active")
        print(f"stored {rid}: {rule}")
        if conf["conflict"]:
            print(f"!! conflict: {conf['reason']}")
    elif args.cmd == "rules":
        print(build_prompt_block(store))
    elif args.cmd == "log":
        for h, s, d in store.log(args.n):
            print(f"{h}  {d}  {s}")
    elif args.cmd == "rollback":
        print("reverted", store.rollback(args.id))
    elif args.cmd == "inject":
        block = build_prompt_block(store)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(block)
            print(f"written {len(block)} chars to {args.out}")
        else:
            print(block)
    elif args.cmd == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()


if __name__ == "__main__":
    main()
