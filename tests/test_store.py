import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from growth.store import RuleStore  # noqa: E402


class StoreTests(unittest.TestCase):
    def test_add_and_active(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            rid = store.add_rule("Always answer in Chinese")
            rules = store.active_rules()
            self.assertTrue(any(r["id"] == rid and r["text"] == "Always answer in Chinese" for r in rules))

    def test_status_filter(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            rid = store.add_rule("temp rule")
            store.set_status(rid, "superseded")
            self.assertTrue(all(r["id"] != rid for r in store.active_rules()))

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            rid = store.add_rule("temp rule")
            store.rollback(rid)
            self.assertTrue(all(r["id"] != rid for r in store.active_rules()))

    def test_log(self):
        with tempfile.TemporaryDirectory() as d:
            store = RuleStore(d)
            store.add_rule("rule one")
            entries = store.log(5)
            self.assertTrue(any("rule one" in s for _, s, _ in entries))


if __name__ == "__main__":
    unittest.main()
