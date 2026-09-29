#!/usr/bin/env python3
"""Exercise every readwright route on a real, public-domain book. Standard library only.

    python tests/real_files.py [--dir DIR] [--no-download] [--json FILE]

Downloads Pride and Prejudice (Project Gutenberg ebook 1342: EPUB, the Gutenberg AZW3 and MOBI, plain text),
builds the other formats with calibre and LibreOffice when they are installed, runs rw.py on each file through
every route it advertises, and checks the result: whole book present, chapters found, a known sentence found in
chapter 1, DRM refused, missing tools named. Prints a Markdown table for TESTS.md. A route whose tool is absent
is reported as skipped, not failed.

Nothing here is committed: the files live in DIR (default: <temp>/readwright-realfiles). The book is in the
public domain in the United States; see https://www.gutenberg.org/policy/permission.html.
Exit code 0 when every route that could run passed.
"""
from __future__ import annotations

import argparse
import csv
import json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rw  # noqa: E402

GUTENBERG = "https://www.gutenberg.org/ebooks/1342."
DOWNLOADS = {"pp.epub": "epub.noimages", "pp-gutenberg.azw3": "kf8.images", "pp-gutenberg.mobi": "kindle.images",
             "pp.txt": "txt.utf-8"}
CHAPTER_ONE = "truth universally acknowledged"   # the novel's first sentence
CHAPTERS = 61


def fetch(dest: Path, no_download: bool):
    for name, kind in DOWNLOADS.items():
        p = dest / name
        if p.exists() or no_download:
            continue
        req = urllib.request.Request(GUTENBERG + kind, headers={"User-Agent": "readwright-tests (manual run)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            p.write_bytes(r.read())
        time.sleep(2)   # be polite to Project Gutenberg


def sh(cmd, timeout=900) -> bool:
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0


def build(d: Path, tl: dict) -> dict:
    """Make every derived file the tools allow; returns name -> why it is missing."""
    missing = {}
    ec, so = tl["ebook-convert"], tl["soffice"]
    for out in ("pp.fb2", "pp.pdf", "pp.docx", "pp.pdb", "pp.lit", "pp.rtf", "pp.azw3", "pp.mobi", "pp.kfx"):
        if (d / out).exists():
            continue
        if not ec:
            missing[out] = "no calibre"
        elif not sh([ec, d / "pp.epub", d / out]):
            missing[out] = "calibre could not write it" + (" (needs the KFX Output plugin and Kindle Previewer)"
                                                           if out.endswith(".kfx") else "")
    if (d / "pp.mobi").exists() and not (d / "pp.prc").exists():
        shutil.copyfile(d / "pp.mobi", d / "pp.prc")   # PRC is the Mobipocket container under an older name
    src_mobi = d / "pp-gutenberg.mobi"
    if src_mobi.exists() and not (d / "pp-drm.mobi").exists():
        data = bytearray(src_mobi.read_bytes())
        rec0 = int.from_bytes(data[78:82], "big")
        data[rec0 + 12:rec0 + 14] = (2).to_bytes(2, "big")   # the Mobipocket encryption field: DRM-style
        (d / "pp-drm.mobi").write_bytes(bytes(data))
    if not (d / "pp-drm.epub").exists():
        with zipfile.ZipFile(d / "pp.epub") as zin, zipfile.ZipFile(d / "pp-drm.epub", "w", zipfile.ZIP_DEFLATED) as zout:
            for i in zin.infolist():
                zout.writestr(i, zin.read(i.filename))
            first = next(n for n in zin.namelist() if n.endswith((".html", ".xhtml")) and "wrap" not in n)
            zout.writestr("META-INF/encryption.xml", (
                "<encryption xmlns='urn:oasis:names:tc:opendocument:xmlns:container' "
                "xmlns:enc='http://www.w3.org/2001/04/xmlenc#'><enc:EncryptedData>"
                "<enc:EncryptionMethod Algorithm='http://www.w3.org/2001/04/xmlenc#aes128-cbc'/>"
                f"<enc:CipherData><enc:CipherReference URI='{first}'/></enc:CipherData></enc:EncryptedData></encryption>"))
            zout.writestr("META-INF/rights.xml", "<adept:rights xmlns:adept='http://ns.adobe.com/adept'/>")
    if not (d / "chapters.csv").exists():
        toc = json.loads(subprocess.run([sys.executable, SCRIPT, "toc", d / "pp.epub", "--json"],
                                        capture_output=True).stdout)
        with open(d / "chapters.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["n", "title", "words"])
            for s in toc["sections"]:
                w.writerow([s["n"], s["title"], s["words"]])
    if not (d / "slides.pdf").exists():
        import test_rw
        test_rw.make_pdf(d / "slides.pdf", pages=("Quarterly plan: hire two keepers", "Budget: paint the tower white",
                                                  "Timeline: finish by spring"))
    lo = [("pp.docx", "doc", "pp.doc", []), ("pp.docx", "odt", "pp.odt", []), ("pp.docx", "pdf", "pp-lo.pdf", []),
          ("chapters.csv", "xls", "chapters.xls", []),
          ("slides.pdf", "ppt", "slides.ppt", ["--infilter=impress_pdf_import"])]
    for src, fmt, out, extra in lo:
        if (d / out).exists():
            continue
        if not so or not (d / src).exists():
            missing[out] = "no LibreOffice" if not so else f"no {src}"
            continue
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td, "profile").as_uri()
            sh([so, f"-env:UserInstallation={profile}", "--headless", "--norestore", *extra, "--convert-to", fmt,
                "--outdir", td, d / src], 600)
            made = next(Path(td).glob("*." + fmt), None)
            if made:
                shutil.move(str(made), d / out)
            else:
                missing[out] = "LibreOffice conversion failed"
    return missing


def rw_run(args, env=None):
    t = time.perf_counter()
    r = subprocess.run([sys.executable, SCRIPT, *[str(a) for a in args]], capture_output=True, env=env,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"), time.perf_counter() - t


def squeeze(s):
    return re.sub(r"\s+", "", s).lower()


def check_book(path: Path, extra: list, env=None) -> tuple[bool, dict]:
    """Whole book, chapters, chapter 1's first sentence in a chapter-1 section, chapter 61 readable by title."""
    code, out, err, fresh = rw_run(["toc", path, "--json", "--no-cache", *extra], env)
    if code:
        return False, {"note": err.strip()[:200], "fresh": fresh}
    toc = json.loads(out)
    _, _, _, cached = rw_run(["info", path, *extra], env)
    words = sum(s["words"] for s in toc["sections"])
    chapters = sum(1 for s in toc["sections"] if re.match(r"(?:.*\b)?chapter", s["title"], re.I))
    info = {"sections": len(toc["sections"]), "words": words, "chapters": chapters, "fresh": fresh, "cached": cached,
            "fmt": toc["format"]}
    problems = []
    if not 120_000 <= words <= 142_000:
        problems.append(f"{words} words")
    if chapters < CHAPTERS - 1:
        problems.append(f"only {chapters} chapter sections")
    code, out, _, _ = rw_run(["grep", path, CHAPTER_ONE, "-F", "--json", *extra], env)
    hits = json.loads(out)["hits"] if out.strip().startswith("{") else []
    if not hits:
        problems.append("chapter 1's first sentence not found")
    elif not re.search(r"chapter\s*(i|1|one)\b", hits[0]["title"], re.I):
        problems.append(f"first sentence found in section {hits[0]['section']} titled {hits[0]['title'][:40]!r}")
    code, out, err, _ = rw_run(["read", path, "--title", r"chapter\s*lxi\b", "--max-chars", "2000", *extra], env)
    if code or "Pemberley" not in out and "Bennet" not in out:
        problems.append("chapter LXI not readable by title")
    info["note"] = "; ".join(problems)
    return not problems, info


def check_contains(path: Path, extra: list, needle: str, sections=None, env=None):
    code, out, err, fresh = rw_run(["toc", path, "--json", "--no-cache", *extra], env)
    if code:
        return False, {"note": err.strip()[:200], "fresh": fresh}
    toc = json.loads(out)
    _, _, _, cached = rw_run(["info", path, *extra], env)
    _, gout, _, _ = rw_run(["grep", path, needle, "-F", "-i", "--count", *extra], env)
    info = {"sections": len(toc["sections"]), "words": sum(s["words"] for s in toc["sections"]), "fresh": fresh,
            "cached": cached, "fmt": toc["format"]}
    ok = not gout.startswith("0 matches") and " 0 matches" not in gout and "matches" in gout
    if sections and len(toc["sections"]) != sections:
        ok, info["note"] = False, f"{len(toc['sections'])} sections, expected {sections}"
    elif not ok:
        info["note"] = f"{needle!r} not found"
    return ok, info


def check_refused(path: Path, extra: list, must: list, env=None):
    code, out, err, fresh = rw_run(["info", path, *extra], env)
    ok = code == 1 and all(m.lower() in err.lower() for m in must)
    return ok, {"fresh": fresh, "note": err.strip().replace("readwright: ", "")[:160]}


def hidden_env(keep_tool: str | None, tl: dict) -> dict:
    """PATH holding only one tool's folder (or none), with the install-folder search off."""
    env = dict(os.environ, RW_PATH_ONLY="1")
    env["PATH"] = os.path.dirname(tl[keep_tool]) if keep_tool and tl.get(keep_tool) else os.devnull
    return env


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default=str(Path(tempfile.gettempdir()) / "readwright-realfiles"))
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--json", help="also write the results as JSON to this file")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    fetch(d, a.no_download)
    tl = rw.tools()
    missing = build(d, tl)

    def need(*tools):
        return [t for t in tools if not tl.get(t)]

    B, C, R = "book", "contains", "refused"
    cases = [   # (file, route, extra args, check, tools needed, check argument)
        ("pp.epub", "built-in EPUB", [], B, [], None),
        ("pp.txt", "built-in text", [], B, [], None),
        ("pp.fb2", "built-in FB2 (written by calibre)", [], B, [], None),
        ("pp.docx", "built-in DOCX (written by calibre)", [], B, [], None),
        ("pp.odt", "built-in ODT (written by LibreOffice)", [], B, [], None),
        ("pp.rtf", "built-in RTF (written by calibre)", [], B, [], None),
        ("pp-gutenberg.azw3", "calibre: AZW3 (KF8, from Gutenberg)", [], B, ["ebook-convert"], None),
        ("pp-gutenberg.mobi", "calibre: MOBI (from Gutenberg)", [], B, ["ebook-convert"], None),
        ("pp.azw3", "calibre: AZW3", [], B, ["ebook-convert"], None),
        ("pp.mobi", "calibre: MOBI", [], B, ["ebook-convert"], None),
        ("pp.prc", "calibre: PRC", [], B, ["ebook-convert"], None),
        ("pp.pdb", "calibre: PDB (eReader)", [], B, ["ebook-convert"], None),
        ("pp.lit", "calibre: LIT", [], B, ["ebook-convert"], None),
        ("pp.kfx", "calibre: KFX (KFX Input plugin)", [], B, ["ebook-convert"], None),
        ("pp.pdf", "PDF: pdftotext + mutool outline (written by calibre)", [], B, ["pdftotext", "mutool"], None),
        ("pp-lo.pdf", "PDF: pdftotext + mutool outline (written by LibreOffice)", [], B, ["pdftotext", "mutool"], None),
        ("pp.pdf", "PDF: mutool only (pdftotext hidden)", [], B, ["mutool"], "mutool"),
        ("pp.doc", "LibreOffice: DOC", [], B, ["soffice"], None),
        ("pp.doc", "antiword: DOC (LibreOffice hidden)", [], C, ["antiword"], ("antiword", CHAPTER_ONE)),
        ("chapters.xls", "LibreOffice: XLS", [], C, ["soffice"], (None, "CHAPTER LXI")),
        ("slides.ppt", "LibreOffice: PPT", [], C, ["soffice"], (None, "paint the tower", 3)),
        ("pp.epub", "--via pandoc (EPUB)", ["--via", "pandoc"], B, ["pandoc"], None),
        ("pp.docx", "--via pandoc (DOCX)", ["--via", "pandoc"], B, ["pandoc"], None),
        ("pp.odt", "--via pandoc (ODT)", ["--via", "pandoc"], B, ["pandoc"], None),
        ("pp.fb2", "--via pandoc (FB2)", ["--via", "pandoc"], B, ["pandoc"], None),
        ("pp.rtf", "--via pandoc (RTF)", ["--via", "pandoc"], B, ["pandoc"], None),
        ("pp.epub", "--via markitdown (EPUB)", ["--via", "markitdown"], B, ["markitdown"], None),
        ("pp.docx", "--via markitdown (DOCX)", ["--via", "markitdown"], B, ["markitdown"], None),
        ("pp.pdf", "--via markitdown (PDF)", ["--via", "markitdown"], C, ["markitdown"], (None, CHAPTER_ONE)),
        ("chapters.xls", "--via markitdown (XLS)", ["--via", "markitdown"], C, ["markitdown"], (None, "CHAPTER LXI")),
        ("pp.rtf", "--via markitdown (RTF) is refused", ["--via", "markitdown"], R, ["markitdown"], ["unchanged"]),
        ("pp-drm.epub", "DRM: EPUB with ADEPT rights.xml + encryption.xml", [], R, [], ["DRM", "does not remove"]),
        ("pp-drm.mobi", "DRM: MOBI with the encryption field set", [], R, [], ["DRM", "does not remove"]),
        ("pp.pdf", "missing tool: PDF", [], R, [], ["pdftotext", "Nothing was installed"], ),
        ("pp.mobi", "missing tool: MOBI", [], R, [], ["ebook-convert", "calibre"]),
        ("pp.doc", "missing tool: DOC", [], R, [], ["LibreOffice", "antiword"]),
        ("pp.epub", "missing tool: --via pandoc", ["--via", "pandoc"], R, [], ["pandoc"]),
        ("pp.epub", "missing tool: --via markitdown", ["--via", "markitdown"], R, [], ["markitdown"]),
    ]
    results = []
    for name, route, extra, kind, tools_needed, arg in cases:
        path = d / name
        row = {"file": name, "route": route}
        lacking = need(*tools_needed)
        if lacking or not path.exists():
            row |= {"result": "skipped", "note": ("no " + ", ".join(lacking)) if lacking else missing.get(name, "file missing")}
            results.append(row)
            continue
        env = None
        if route.startswith("missing tool"):
            env = hidden_env(None, tl)
        elif kind == B and arg == "mutool":
            env = hidden_env("mutool", tl)
        elif kind == C and arg and arg[0] == "antiword":
            env = hidden_env("antiword", tl)
        if kind == B:
            ok, info = check_book(path, extra, env)
        elif kind == C:
            ok, info = check_contains(path, extra, arg[1], arg[2] if len(arg) > 2 else None, env)
        else:
            ok, info = check_refused(path, extra, arg, env)
        row |= info | {"result": "pass" if ok else "FAIL"}
        results.append(row)
        print(f"{row['result']:>7}  {name:<18} {route}  {info.get('note', '')}", file=sys.stderr)

    print("| File | Route | Result | Sections | Chapters | Words | Fresh s | Cached s | Note |")
    print("|---|---|---|---:|---:|---:|---:|---:|---|")
    for r in results:
        def n(k, f="{:,}"):
            return f.format(r[k]) if k in r else ""
        print(f"| {r['file']} | {r['route']} | {r['result']} | {n('sections')} | {n('chapters')} | {n('words')} | "
              f"{n('fresh', '{:.2f}')} | {n('cached', '{:.2f}')} | {r.get('note', '').replace('|', '/')} |")
    if a.json:
        Path(a.json).write_text(json.dumps({"tools": tl, "results": results}, indent=1), encoding="utf-8")
    failed = [r for r in results if r["result"] == "FAIL"]
    skipped = [r for r in results if r["result"] == "skipped"]
    print(f"\n{len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed, {len(skipped)} skipped "
          f"(readwright {rw.VERSION}, Python {sys.version.split()[0]}, {sys.platform})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
