import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from growth.mcp_server import _handle  # noqa: E402
from growth.store import RuleStore  # noqa: E402

PY = sys.executable


class EdgeTests(unittest.TestCase):
    def test_resolve_invalid_action(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            old = store.add_rule("x")
            new = store.add_rule("y", status="conflict", conflicts_with=[old])
            with self.assertRaises(ValueError):
                store.resolve(new, "drop-everything")

    def test_resolve_non_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            rid = store.add_rule("x")
            with self.assertRaises(ValueError):
                store.resolve(rid, "keep-new")

    def test_rollback_twice_is_clean_error(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            rid = store.add_rule("x")
            store.rollback(rid)
            with self.assertRaises(ValueError):
                store.rollback(rid)
            # repo stays usable after the failed revert
            store.add_rule("after failure")
            self.assertEqual(len(store.active_rules()), 1)

    def test_inject_file(self):
        from growth.inject import inject_to_file

        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            store.add_rule("rule A")
            out = os.path.join(d, "prompt.md")
            n = inject_to_file(out, store)
            self.assertGreater(n, 0)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("rule A", fh.read())

    def test_cli_init_merges_existing(self):
        with tempfile.TemporaryDirectory() as d:
            mcp = pathlib.Path(d) / ".mcp.json"
            mcp.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT)}
            r = subprocess.run(
                [PY, "-m", "growth.cli", "init", "--target", "claude"],
                cwd=d,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(mcp.read_text(encoding="utf-8"))
            self.assertIn("other", data["mcpServers"])
            self.assertIn("growth", data["mcpServers"])

    def test_mcp_unknown_method(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            self.assertIsNone(_handle({"method": "nope"}, store))

    def test_mcp_learn_conflicts_with_unknown_id(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            out = _handle(
                {
                    "method": "tools/call",
                    "params": {
                        "name": "growth_learn",
                        "arguments": {"correction": "x", "rule": "x", "conflicts_with": ["does-not-exist"]},
                    },
                },
                store,
            )
            payload = json.loads(out["content"][0]["text"])
            self.assertEqual(payload["status"], "active")

    def test_conflict_multi_old(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            a = store.add_rule("a")
            b = store.add_rule("b")
            c = store.add_rule("c", status="conflict", conflicts_with=[a, b])
            res = store.resolve(c, "keep-new")
            self.assertEqual(set(res["superseded"]), {a, b})
            active = [r["id"] for r in store.active_rules()]
            self.assertIn(c, active)
            self.assertNotIn(a, active)
            self.assertNotIn(b, active)

    def test_mcp_learn_empty_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            out = _handle(
                {"method": "tools/call", "params": {"name": "growth_learn", "arguments": {"correction": ""}}},
                store,
            )
            payload = json.loads(out["content"][0]["text"])
            self.assertEqual(payload["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
