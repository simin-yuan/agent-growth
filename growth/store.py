"""Rule store backed by a standalone Git repository.

Every rule is a markdown file under ``<root>/rules/`` with YAML-ish frontmatter
(JSON inside a ``---`` fence, to stay dependency-free). Every mutation is a git
commit, which gives us audit trail and one-command rollback for free.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
import subprocess
import uuid

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n\n?(.*)$", re.S)


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

    # -- rules ------------------------------------------------------------
    def add_rule(
        self,
        rule_text: str,
        source: str = "",
        status: str = "active",
        supersedes: str | None = None,
    ) -> str:
        rid = _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        path = self.rules_dir / f"{rid}.md"
        meta = {
            "id": rid,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "status": status,
        }
        if supersedes:
            meta["supersedes"] = supersedes
        path.write_text(
            "---\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n---\n\n" + rule_text.strip() + "\n",
            encoding="utf-8",
        )
        self._git("add", self._rel(path))
        self._git("commit", "-m", f"rule: {rule_text.strip()[:60]}")
        return rid

    def active_rules(self) -> list[dict]:
        out: list[dict] = []
        for p in sorted(self.rules_dir.glob("*.md")):
            m = _FRONTMATTER.match(p.read_text(encoding="utf-8"))
            if not m:
                continue
            try:
                meta = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if meta.get("status") != "active":
                continue
            out.append({"id": meta.get("id", p.stem), "text": m.group(2).strip(), "meta": meta})
        return out

    def set_status(self, rid: str, status: str) -> None:
        path = self.rules_dir / f"{rid}.md"
        m = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not m:
            raise ValueError(f"malformed rule file: {rid}")
        meta = json.loads(m.group(1))
        meta["status"] = status
        path.write_text(
            "---\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n---\n\n" + m.group(2).strip() + "\n",
            encoding="utf-8",
        )
        self._git("add", self._rel(path))
        self._git("commit", "-m", f"rule {rid}: status -> {status}")

    def log(self, n: int = 20) -> list[tuple[str, str, str]]:
        r = self._git("log", f"-n{n}", "--format=%h|%s|%cd", "--date=short")
        return [tuple(line.split("|", 2)) for line in r.stdout.strip().splitlines() if line]

    def rollback(self, rid: str) -> str:
        path = self.rules_dir / f"{rid}.md"
        rel = self._rel(path)
        r = self._git("log", "--format=%H", "--", rel)
        commits = r.stdout.strip().splitlines()
        if not commits:
            raise ValueError(f"rule {rid} not found in history")
        self._git("revert", "--no-edit", commits[0])
        return commits[0]
