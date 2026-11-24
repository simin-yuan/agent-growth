import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from growth.inject import build_prompt_block  # noqa: E402
from growth.store import RuleStore  # noqa: E402


class FlowTests(unittest.TestCase):
    def test_conflict_is_never_injected(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            old = store.add_rule("use Chinese comments")
            new = store.add_rule("use English comments", status="conflict", conflicts_with=[old])
            self.assertNotIn(new, [r["id"] for r in store.active_rules()])
            self.assertIn(new, [r["id"] for r in store.conflict_rules()])
            block = build_prompt_block(store)
            self.assertIn("use Chinese comments", block)
            self.assertNotIn("use English comments", block)

    def test_resolve_keep_new_then_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            old = store.add_rule("use Chinese comments")
            new = store.add_rule("use English comments", status="conflict", conflicts_with=[old])
            res = store.resolve(new, "keep-new")
            self.assertEqual(res["superseded"], [old])
            active = [r["id"] for r in store.active_rules()]
            self.assertIn(new, active)
            self.assertNotIn(old, active)
            self.assertEqual(store.get_rule(old)["meta"]["status"], "superseded")
            # rollback restores the pre-resolve state
            store.rollback(new)
            active = [r["id"] for r in store.active_rules()]
            self.assertIn(old, active)
            self.assertNotIn(new, active)

    def test_resolve_keep_old(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            old = store.add_rule("use Chinese comments")
            new = store.add_rule("use English comments", status="conflict", conflicts_with=[old])
            store.resolve(new, "keep-old")
            active = [r["id"] for r in store.active_rules()]
            self.assertIn(old, active)
            self.assertNotIn(new, active)
            self.assertEqual(store.get_rule(new)["meta"]["status"], "superseded")

    def test_resolve_keep_both(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            old = store.add_rule("use Chinese comments")
            new = store.add_rule("use English comments", status="conflict", conflicts_with=[old])
            store.resolve(new, "keep-both")
            active = [r["id"] for r in store.active_rules()]
            self.assertIn(old, active)
            self.assertIn(new, active)

    def test_resolve_requires_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            rid = store.add_rule("normal rule")
            with self.assertRaises(ValueError):
                store.resolve(rid, "keep-new")

    def test_mcp_surface(self):
        from growth.mcp_server import _handle

        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            init = _handle({"method": "initialize"}, store)
            self.assertEqual(init["serverInfo"]["name"], "growth")
            self.assertIn("instructions", init)
            tools = [t["name"] for t in _handle({"method": "tools/list"}, store)["tools"]]
            for name in ("growth_get_rules", "growth_learn", "growth_resolve", "growth_rollback", "growth_log"):
                self.assertIn(name, tools)

    def test_mcp_learn_and_resolve(self):
        from growth.mcp_server import _handle

        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            out = _handle(
                {
                    "method": "tools/call",
                    "params": {
                        "name": "growth_learn",
                        "arguments": {"correction": "回答用中文"},
                    },
                },
                store,
            )
            payload = json.loads(out["content"][0]["text"])
            self.assertEqual(payload["status"], "active")
            rid = payload["id"]
            self.assertEqual(len(store.active_rules()), 1)
            err = _handle(
                {
                    "method": "tools/call",
                    "params": {
                        "name": "growth_resolve",
                        "arguments": {"rule_id": rid, "action": "keep-new"},
                    },
                },
                store,
            )
            self.assertTrue(err.get("isError"))


if __name__ == "__main__":
    unittest.main()
