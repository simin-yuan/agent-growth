"""Generate demo.gif by running the real CLI and rendering it with Pillow.

Usage:  python scripts/make_demo_gif.py
Writes demo.gif at the repository root. Requires Pillow and git.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT = os.path.join(ROOT, "demo.gif")
PY = sys.executable

W, H, PAD, LH = 1100, 760, 22, 23
FONT_PATH = "C:/Windows/Fonts/consola.ttf"
BOLD_PATH = "C:/Windows/Fonts/consolab.ttf"
try:
    FONT = ImageFont.truetype(FONT_PATH, 17)
    BOLD = ImageFont.truetype(BOLD_PATH, 18)
except OSError:
    FONT = ImageFont.load_default()
    BOLD = FONT

COLORS = {
    "cmd": (230, 237, 243),
    "out": (201, 209, 217),
    "ok": (63, 185, 80),
    "warn": (248, 81, 73),
    "dim": (110, 118, 129),
    "hint": (88, 166, 255),
}


def capture(args: list[str], cwd: str, env: dict) -> str:
    r = subprocess.run(
        [PY, "-m", "growth.cli", *args],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return (r.stdout or "").rstrip()


def main() -> None:
    lines: list[tuple[str, str]] = []

    def add(style: str, text: str) -> None:
        for ln in str(text).splitlines() or [""]:
            lines.append((style, ln))

    add("hint", "agent-growth  ·  Git for Agent Memory")
    add("dim", "")

    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ)
        env["PYTHONPATH"] = ROOT
        env["PYTHONIOENCODING"] = "utf-8"
        for key in ("GROWTH_LLM_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
            env.pop(key, None)

        add("cmd", "growth init --target claude")
        init_lines = capture(["init", "--target", "claude"], d, env).splitlines()
        add("out", init_lines[0] if init_lines else "")
        add("dim", "")

        add("cmd", 'growth add "comments in Chinese"')
        a_out = capture(["add", "comments in Chinese"], d, env)
        add("ok", a_out)
        a_id = a_out.split()[1].rstrip(":") if len(a_out.split()) > 1 else ""
        add("dim", "")

        from growth.store import RuleStore

        store = RuleStore(os.path.join(d, ".growth"))
        b_id = store.add_rule("comments must be English", status="conflict", conflicts_with=[a_id])
        add("cmd", 'growth add "comments must be English"')
        add("warn", f"stored {b_id}: comments must be English (status=conflict)")
        add("warn", f"!! conflict: contradicts {a_id} (comments in Chinese)")
        add("dim", "run `growth conflicts`, then `growth resolve <id> --keep-new|--keep-old|--keep-both`")
        add("dim", "")

        add("cmd", "growth conflicts")
        add("hint", capture(["conflicts"], d, env))
        add("dim", "")

        add("cmd", f"growth resolve {b_id} --keep-new")
        add("ok", capture(["resolve", b_id, "--keep-new"], d, env))
        add("dim", "")

        add("cmd", f"growth rollback {b_id}")
        add("ok", capture(["rollback", b_id], d, env))
        add("dim", "")

        add("cmd", "growth log")
        for row in capture(["log"], d, env).splitlines()[:6]:
            add("dim", row)

    total = len(lines)
    print(f"lines: {total}")

    def render(n: int) -> Image.Image:
        img = Image.new("RGB", (W, H), (13, 17, 23))
        dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, W, 32], fill=(22, 27, 34))
        dr.ellipse([12, 10, 20, 18], fill=(248, 81, 73))
        dr.ellipse([27, 10, 35, 18], fill=(210, 153, 34))
        dr.ellipse([42, 10, 50, 18], fill=(63, 185, 80))
        dr.text((66, 7), "agent-growth  ·  Git for Agent Memory", font=BOLD, fill=(230, 237, 243))
        y = 44
        for style, text in lines[:n]:
            color = COLORS.get(style, COLORS["out"])
            prefix = "$ " if style == "cmd" else ("  " if style == "hint" else "")
            dr.text((PAD, y), prefix + text, font=FONT, fill=color)
            y += LH
            if y > H - 22:
                break
        return img

    frames = [render(i) for i in range(1, total + 1)]
    frames += [render(total)] * 10
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=550, loop=0, optimize=True)
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
