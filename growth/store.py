"""Rule store backed by a standalone Git repository.

Every rule is a markdown file under ``<root>/rules/`` with YAML-ish frontmatter
(JSON inside a ``---`` fence, to stay dependency-free). Every mutation is a git
commit, which gives us an audit trail and one-command rollback for free.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
import subprocess
import uuid

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n\n?(.*)$", re.S)

VALID_STATUS = ("active", "conflict", "superseded")


class RuleStore:
    def __init__(self, root: str | pathlib.Path | None = None):
        self.root = pathlib.Path(root or ".growth").resolve()
        self.rules_dir = self.root / "rules"
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self._git_init()

    # -- git plumbing -----------------------------------------------------
    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=check,
        )

    def _git_init(self) -> None:
        if (self.root / ".git").exists():
            return
        self._git("init")
        self._git("config", "user.email", "growth@local")
        self._git("config", "user.name", "growth")
        ignore = self.root / ".gitignore"
        ignore.write_text("*.tmp\n", encoding="utf-8")
        self._git("add", ".gitignore")
        self._git("commit", "-m", "init: growth store")

    def _rel(self, p: pathlib.Path) -> str:
        return p.relative_to(self.root).as_posix()

    # -- rule files -------------------------------------------------------
    def _read_rule(self, rid: str) -> tuple[dict, str] | None:
        path = self.rules_dir / f"{rid}.md"
        if not path.exists():
            return None
        m = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not m:
            return None
        try:
            meta = json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
        return meta, m.group(2).strip()

    def _write_rule(self, rid: str, meta: dict, body: str) -> pathlib.Path:
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        path = self.rules_dir / f"{rid}.md"
        path.write_text(
            "---\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n---\n\n" + body.strip() + "\n",
            encoding="utf-8",
        )
        return path

    def _commit(self, msg: str, paths: list[pathlib.Path]) -> None:
        for p in paths:
            self._git("add", self._rel(p))
        self._git("commit", "-m", msg)

    # -- public API -------------------------------------------------------
    def add_rule(
        self,
        rule_text: str,
        source: str = "",
        status: str = "active",
        supersedes: str | None = None,
        conflicts_with: list[str] | None = None,
    ) -> str:
        if status not in VALID_STATUS:
            raise ValueError(f"invalid status: {status}")
        rid = _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        meta = {
            "id": rid,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "status": status,
        }
        if supersedes:
            meta["supersedes"] = supersedes
        if conflicts_with:
            meta["conflicts_with"] = list(conflicts_with)
        path = self._write_rule(rid, meta, rule_text)
        self._commit(f"rule: {rule_text.strip()[:60]}", [path])
        return rid

    def _rules_by_status(self, status: str) -> list[dict]:
        out: list[dict] = []
        for p in sorted(self.rules_dir.glob("*.md")):
            got = self._read_rule(p.stem)
            if not got:
                continue
            meta, body = got
            if meta.get("status") == status:
                out.append({"id": meta.get("id", p.stem), "text": body, "meta": meta})
        return out

    def active_rules(self) -> list[dict]:
        return self._rules_by_status("active")

    def conflict_rules(self) -> list[dict]:
        return self._rules_by_status("conflict")

    def get_rule(self, rid: str) -> dict | None:
        got = self._read_rule(rid)
        if not got:
            return None
        meta, body = got
        return {"id": rid, "text": body, "meta": meta}

    def set_status(self, rid: str, status: str) -> None:
        if status not in VALID_STATUS:
            raise ValueError(f"invalid status: {status}")
        got = self._read_rule(rid)
        if not got:
            raise ValueError(f"rule {rid} not found")
        meta, body = got
        meta["status"] = status
        path = self._write_rule(rid, meta, body)
        self._commit(f"rule {rid}: status -> {status}", [path])

    def resolve(self, rid: str, action: str) -> dict:
        """Resolve a conflict rule.

        keep-new  -> new rule active, conflicting old rules superseded
        keep-old  -> new rule superseded, old rules untouched
        keep-both -> new rule active, old rules untouched
        """
        if action not in ("keep-new", "keep-old", "keep-both"):
            raise ValueError("action must be keep-new | keep-old | keep-both")
        got = self._read_rule(rid)
        if not got:
            raise ValueError(f"rule {rid} not found")
        meta, body = got
        if meta.get("status") != "conflict":
            raise ValueError(f"rule {rid} is not in conflict (status={meta.get('status')})")
        old_ids = list(meta.get("conflicts_with", []))
        paths: list[pathlib.Path] = []

        if action == "keep-old":
            meta["status"] = "superseded"
            meta.pop("conflicts_with", None)
            paths.append(self._write_rule(rid, meta, body))
        else:
            meta["status"] = "active"
            meta.pop("conflicts_with", None)
            if action == "keep-new" and old_ids:
                meta["supersedes"] = old_ids[0]
                for oid in old_ids:
                    old = self._read_rule(oid)
                    if old:
                        om, ob = old
                        om["status"] = "superseded"
                        paths.append(self._write_rule(oid, om, ob))
            paths.append(self._write_rule(rid, meta, body))

        self._commit(f"resolve {rid}: {action}", paths)
        return {"id": rid, "action": action, "superseded": old_ids if action == "keep-new" else []}

    def log(self, n: int = 20) -> list[tuple[str, str, str]]:
        r = self._git("log", f"-n{n}", "--format=%h|%s|%cd", "--date=short")
        return [tuple(line.split("|", 2)) for line in r.stdout.strip().splitlines() if line]

    def rollback(self, rid: str) -> str:
        path = self.rules_dir / f"{rid}.md"
        if not path.exists():
            raise ValueError(f"rule {rid} not found (already rolled back?)")
        rel = self._rel(path)
        r = self._git("log", "--format=%H", "--", rel)
        commits = r.stdout.strip().splitlines()
        if not commits:
            raise ValueError(f"rule {rid} not found in history")
        try:
            self._git("revert", "--no-edit", commits[0])
        except subprocess.CalledProcessError as exc:
            self._git("revert", "--abort", check=False)
            detail = (exc.stderr or "").strip()
            raise ValueError(f"cannot rollback {rid}: {detail or 'revert failed'}") from exc
        return commits[0]
