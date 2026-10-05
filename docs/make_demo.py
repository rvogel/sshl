#!/usr/bin/env python3
"""Builds docs/demo.gif from the test fixture: each frame is a terminal window
drawn in HTML from sshl's real output, shot by headless Chrome, then joined by
ffmpeg. No packages to install; needs Google Chrome and ffmpeg.

    python3 docs/make_demo.py
"""
import html
import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "config")
OUT = os.path.join(ROOT, "docs", "demo.gif")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
W, H = 820, 470

loader = importlib.machinery.SourceFileLoader("sshl", os.path.join(ROOT, "sshl"))
spec = importlib.util.spec_from_loader("sshl", loader)
sshl = importlib.util.module_from_spec(spec)
loader.exec_module(sshl)

COLOURS = {"1": "font-weight:700;color:#f4f4f5", "2": "color:#71717a", "1;36": "font-weight:700;color:#22d3ee", "33": "color:#facc15"}


def output(query):
    hosts = sshl.parse(sshl.read_lines(FIXTURE, set()))
    if query:
        hosts = [h for h in hosts if query in " ".join(h["names"] + [h.get("hostname", ""), h["section"]]).lower()]
    return sshl.render(sshl.order(hosts), tty=True)


def ansi_to_html(text):
    out, pos = [], 0
    for m in re.finditer(r"\033\[([\d;]+)m(.*?)\033\[0m", text, re.S):
        out.append(html.escape(text[pos:m.start()]))
        out.append(f'<span style="{COLOURS.get(m.group(1), "")}">{html.escape(m.group(2))}</span>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


PROMPT = '<span style="color:#4ade80">~</span> <span style="color:#a1a1aa">$</span> '


def page(body):
    return f"""<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;background:#0b0b0e;}}
.win{{width:{W - 40}px;height:{H - 40}px;margin:20px;border-radius:10px;background:#18181b;
box-shadow:0 10px 30px rgba(0,0,0,.5);overflow:hidden;font:14px/1.45 Menlo,Monaco,monospace;color:#e4e4e7}}
.bar{{height:30px;background:#27272a;display:flex;align-items:center;padding:0 12px;gap:8px}}
.dot{{width:12px;height:12px;border-radius:50%}}
.title{{flex:1;text-align:center;color:#a1a1aa;font-size:12px;margin-right:52px}}
pre{{margin:0;padding:14px 18px;white-space:pre}}
.cur{{display:inline-block;width:8px;height:16px;background:#e4e4e7;vertical-align:-3px}}
</style><div class="win"><div class="bar"><span class="dot" style="background:#ff5f57"></span>
<span class="dot" style="background:#febc2e"></span><span class="dot" style="background:#28c840"></span>
<span class="title">sshl</span></div><pre>{body}</pre></div>"""


def frames():
    """(html body, seconds) pairs: type a command, show its output, pause."""
    seq = []
    for cmd, query, hold in (("sshl", "", 3.2), ("sshl work", "work", 2.6), ("sshl 192.168.20", "192.168.20", 2.8)):
        seq.append((PROMPT + '<span class="cur"></span>', 0.6))
        for i in range(1, len(cmd) + 1):
            seq.append((PROMPT + html.escape(cmd[:i]) + '<span class="cur"></span>', 0.09))
        seq.append((PROMPT + html.escape(cmd) + "\n" + ansi_to_html(output(query)) + "\n\n" + PROMPT + '<span class="cur"></span>', hold))
    return seq


def shoot(html_text, png, tmp):
    src = os.path.join(tmp, "f.html")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={W},{H}", f"--screenshot={png}", "file://" + src],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    for tool in ("ffmpeg",):
        if not shutil.which(tool):
            sys.exit(f"{tool} is needed")
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for n, (body, secs) in enumerate(frames()):
            png = os.path.join(tmp, f"{n:03}.png")
            shoot(page(body), png, tmp)
            lines += [f"file '{png}'", f"duration {secs}"]
        lines.append(f"file '{png}'")
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        vf = f"scale={W}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                        "-vf", vf, "-loop", "0", OUT], check=True)
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
