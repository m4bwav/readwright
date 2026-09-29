#!/usr/bin/env python3
"""Measure what reading two chapters of a full-size novel costs an agent, by route. Standard library only.

    python tests/measure_tokens.py [--book FILE] [--dir DIR]

The book is Moby-Dick (Project Gutenberg ebook 2701, public domain in the United States; about 1.2 million
characters), downloaded to DIR unless --book is given. The task is the one an agent gets: "what happens in
chapters 16 and 17?". For each route the script runs the commands an agent would run and adds up what they
print, which is what would enter the agent's context. Tokens are characters divided by 4, the estimate rw.py
itself prints; words are shown too. Routes:

  a  readwright: info, toc, read the two chapters by title, grep a name with --count
  b  whole-book dump printed to the context: epr -d, pandoc -t plain, markitdown (each if installed)
  b' whole-book dump to a file, grep for the chapter headings, print only the lines between them
  c  no skill: list the zip, print the NCX table of contents, print the raw XHTML files holding the chapters
     (what an agent does with unzip -l and unzip -p; emulated with zipfile so it runs anywhere)

Prints a Markdown table for TESTS.md and the README.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "readwright" / "scripts" / "rw.py"
sys.path.insert(0, str(SCRIPT.parent))
import rw  # noqa: E402

URL = "https://www.gutenberg.org/ebooks/2701.epub.noimages"
FIRST, SECOND = 16, 17


def run(cmd) -> tuple[str, float]:
    t = time.perf_counter()
    r = subprocess.run([str(c) for c in cmd], capture_output=True, stdin=subprocess.DEVNULL,
                       env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"))
    return r.stdout.decode("utf-8", "replace"), time.perf_counter() - t


def row(route, steps, outputs, seconds, note=""):
    chars = sum(len(o) for o in outputs)
    return {"route": route, "steps": steps, "chars": chars, "words": sum(len(o.split()) for o in outputs),
            "tokens": chars // 4, "seconds": seconds, "note": note}


def route_readwright(book):
    rwc = [sys.executable, SCRIPT]
    outs, secs = [], 0.0
    for args in (["info", book], ["toc", book], ["read", book, "--title", rf"chapter {FIRST}\.|chapter {SECOND}\."],
                 ["grep", book, "Pequod", "--count"]):
        o, s = run(rwc + args)
        outs.append(o)
        secs += s
    both = f"CHAPTER {FIRST}." in outs[2] and f"CHAPTER {SECOND}." in outs[2]
    split = ", ".join(f"{n} {len(o) // 4:,}" for n, o in zip(("info", "toc", "read", "grep"), outs))
    return row("a  readwright (info, toc, read 2 chapters, grep --count)", 4, outs, secs,
               f"tokens by command: {split}" if both else "the read did not return both chapters")


def dumps(book):
    tl = rw.tools()
    epr = shutil.which("epr") or next((str(Path(d, n)) for d in rw.tool_dirs("markitdown")
                                       for n in ("epr", "epr.exe") if Path(d, n).is_file()), None)
    out = []
    if epr:
        out.append(("epr -d", [epr, "-d", book]))
    if tl["pandoc"]:
        out.append(("pandoc -t plain", [tl["pandoc"], book, "-t", "plain", "--wrap=none"]))
    if tl["markitdown"]:
        out.append(("markitdown", [tl["markitdown"], book]))
    return out


def route_dump_printed(name, cmd):
    o, s = run(cmd)
    return row(f"b  {name}, whole book printed", 1, [o], s), o


def route_dump_to_file(name, text, seconds):
    """Dump written to a file (not printed), then grep -n for the headings, then print the lines between."""
    lines = text.splitlines()
    heads = [f"{i + 1}:{ln}" for i, ln in enumerate(lines) if re.match(r"\s*(#+\s*)?CHAPTER \d+\.", ln, re.I)]
    grep_out = "\n".join(heads) + "\n"
    # Gutenberg books repeat every heading in a contents list at the front, so the first "CHAPTER 16." to the
    # next "CHAPTER 18." is two lines of that list. An agent learns this after one wasted read; the widest span
    # is the chapters themselves.
    starts = [i for i, ln in enumerate(lines) if re.match(rf"\s*(#+\s*)?CHAPTER {FIRST}\.", ln, re.I)]
    ends = [i for i, ln in enumerate(lines) if re.match(rf"\s*(#+\s*)?CHAPTER {SECOND + 1}\.", ln, re.I)]
    spans = [(e - s, s, e) for s in starts for e in ends if e > s and not any(s < s2 < e for s2 in starts)]
    start, end = (max(spans)[1:] if spans else (None, None))
    if start is None or end is None:
        return row(f"b' {name} to a file, grep, print the range", 3, [grep_out], seconds,
                   "chapter headings not found in the dump")
    body = "\n".join(lines[start:end]) + "\n"
    return row(f"b' {name} to a file, grep, print the range", 3, [grep_out, body], seconds)


def route_by_hand(book):
    t = time.perf_counter()
    outs = []
    with zipfile.ZipFile(book) as z:
        outs.append("\n".join(f"{i.file_size:>9}  {i.filename}" for i in z.infolist()) + "\n")   # unzip -l
        ncx = next(n for n in z.namelist() if n.endswith(".ncx"))
        ncx_text = z.read(ncx).decode("utf-8", "replace")
        outs.append(ncx_text)                                                                     # unzip -p toc.ncx
        srcs = []
        for n in (FIRST, SECOND, SECOND + 1):
            m = re.search(rf"CHAPTER {n}\..*?<content src=\"([^\"#]+)", ncx_text, re.S)
            if m and m.group(1) not in srcs:
                srcs.append(m.group(1))
        # every file from chapter 16's to chapter 18's: chapter 17 may start in the middle of one
        names = z.namelist()
        base = posix_dir(ncx)
        files = [base + s for s in srcs]
        spine = [n for n in names if n.endswith((".html", ".xhtml", ".htm"))]
        if files and files[0] in spine and files[-1] in spine:
            files = spine[spine.index(files[0]):spine.index(files[-1]) + 1]
        for f in files:
            outs.append(z.read(f).decode("utf-8", "replace"))                                     # unzip -p chapter files
    return row("c  no skill: unzip -l, the NCX, the raw XHTML files holding the chapters", 2 + len(files), outs,
               time.perf_counter() - t, f"{len(files)} XHTML files with markup")


def posix_dir(p):
    return p.rsplit("/", 1)[0] + "/" if "/" in p else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--book")
    ap.add_argument("--dir", default=str(Path(tempfile.gettempdir()) / "readwright-realfiles"))
    a = ap.parse_args(argv)
    book = Path(a.book) if a.book else Path(a.dir) / "moby.epub"
    if not book.exists():
        book.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "readwright-tests (manual run)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            book.write_bytes(r.read())
    info, _ = run([sys.executable, SCRIPT, "info", book])
    rows = [route_readwright(book)]
    for name, cmd in dumps(book):
        r_, text = route_dump_printed(name, cmd)
        rows.append(r_)
        rows.append(route_dump_to_file(name, text, r_["seconds"]))
    rows.append(route_by_hand(book))
    base = rows[0]["tokens"]
    print(f"Book: {book.name}; " + "; ".join(ln.strip() for ln in info.splitlines()
                                             if ln.startswith(("title", "sections", "words", "tokens_approx"))))
    print(f"Task: what happens in chapters {FIRST} and {SECOND}.\n")
    print("| Route | Commands | Printed to the context: words | ~tokens | vs readwright | Time s | Note |")
    print("|---|---:|---:|---:|---:|---:|---|")
    for r_ in rows:
        print(f"| {r_['route']} | {r_['steps']} | {r_['words']:,} | {r_['tokens']:,} | {r_['tokens'] / base:.1f}x | "
              f"{r_['seconds']:.2f} | {r_['note']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
