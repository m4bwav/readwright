#!/usr/bin/env python3
"""rw.py - readwright: read text out of documents and ebooks a piece at a time.

Standard library only, Python 3.10+, Windows/macOS/Linux. Output is UTF-8 with LF
line endings on every platform.

The practice it supports: `info` (how big is it), `toc` (what is in it), `read`
only the sections needed, `grep` for names and phrases, `dump` a whole book to a
scratch file for the agent's own search tools. A whole book never goes to stdout.

Commands
  info  FILE                        format, size, metadata, sections, words, ~tokens
  toc   FILE [--limit N]            numbered sections with titles, word counts, ids
  read  FILE [--section N|N-M|N,M] [--title REGEX] [--max-chars N] [--offset N] [--out FILE] [--format txt|md]
                                    [--with-next]
  grep  FILE PATTERN [-C N] [-i] [-F] [--max N] [--width N] [--count]
  dump  FILE --out FILE [--format txt|md]
  formats                           supported formats and which external tools are present

Common options: --member NAME (a file inside a zip), --via pandoc|markitdown,
--json (info, toc, grep, formats), --no-cache.

Pure standard library: EPUB, DOCX, ODT/ODS/ODP, PPTX, XLSX, FB2, HTML, TXT, MD, RST,
RTF, CSV/TSV, JSON, EML, ZIP. External tools when installed: PDF (pdftotext or
mutool), MOBI/AZW/AZW3/PRC/PDB/LIT/DJVU/CHM (calibre ebook-convert), DOC/XLS/PPT
(LibreOffice soffice, or antiword for DOC). Nothing is ever installed. DRM is
detected and reported, never removed. Macros and scripts are never run.

Exit codes: 0 ok, 1 error, 2 refused (text larger than --max-chars and no selector).
"""
from __future__ import annotations

import argparse
import csv
import email
import email.policy
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import posixpath
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag
import xml.etree.ElementTree as ET

VERSION = "0.1.0"

MB = 1024 * 1024
MAX_MB = int(os.environ.get("RW_MAX_MB", "512"))       # cap on bytes read from one file or zip member
MAX_ROWS = 200_000                                      # cap on spreadsheet rows per sheet
MAX_COLS = 1_000                                        # cap on spreadsheet columns
CHUNK_WORDS = 3_000                                     # unstructured text is split into parts this size
DEFAULT_MAX_CHARS = 40_000
SHORT_WORDS = 300                                       # a section this short is probably a chapter's title page

EXIT_OK, EXIT_ERR, EXIT_REFUSED = 0, 1, 2


class RWError(Exception):
    """A clean, user-facing failure (missing tool, DRM, unsupported format)."""


# ---------------------------------------------------------------- model

@dataclass
class Para:
    kind: str   # p, h, li, pre, row, quote
    text: str
    level: int = 0


@dataclass
class Section:
    title: str
    paras: list = field(default_factory=list)
    level: int = 1
    sid: str = ""

    def words(self) -> int:
        return sum(len(p.text.split()) for p in self.paras)

    def chars(self) -> int:
        return len(render_paras(self.paras, "txt"))


@dataclass
class Doc:
    path: str
    fmt: str
    meta: dict = field(default_factory=dict)
    sections: list = field(default_factory=list)
    notes: list = field(default_factory=list)      # things the reader should know (conversions, caps)
    members: list = field(default_factory=list)    # zip listing: (name, size, fmt)


def clean(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    return " ".join(s.split())


def render_paras(paras, fmt="txt") -> str:
    out = []
    prev = None
    for p in paras:
        if p.kind == "h" and fmt == "md":
            t = "#" * max(1, min(6, p.level or 1)) + " " + p.text
        elif p.kind == "li":
            t = "- " + p.text
        elif p.kind == "quote" and fmt == "md":
            t = "> " + p.text
        elif p.kind == "pre" and fmt == "md":
            t = "```\n" + p.text + "\n```"
        else:
            t = p.text
        if out:
            out.append("\n" if (prev in ("row", "li") and p.kind == prev) else "\n\n")
        out.append(t)
        prev = p.kind
    return "".join(out)


# ---------------------------------------------------------------- io helpers

def read_capped(path, limit=None) -> bytes:
    limit = limit or MAX_MB * MB
    with open(path, "rb") as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise RWError(f"{path} is larger than {MAX_MB} MB; set RW_MAX_MB to raise the cap, or split the file")
    return data


def zread(z: zipfile.ZipFile, name: str) -> bytes:
    info = z.getinfo(name)
    if info.file_size > MAX_MB * MB:
        raise RWError(f"zip member {name} expands to {info.file_size // MB} MB, over the {MAX_MB} MB cap (RW_MAX_MB)")
    with z.open(info) as f:
        data = f.read(MAX_MB * MB + 1)
    if len(data) > MAX_MB * MB:
        raise RWError(f"zip member {name} expands past the {MAX_MB} MB cap")
    return data


def decode_text(data: bytes, hint: str | None = None) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", "replace")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    for enc in ([hint] if hint else []) + ["utf-8"]:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass
    return data.decode("cp1252", "replace")


def xml_root(data: bytes):
    # expat (3.10+ ships 2.4.1 or newer) refuses entity-expansion bombs; ElementTree never fetches external entities.
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise RWError(f"XML parse error: {e}")


def local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def env_dir(var: str, *parts) -> str | None:
    base = os.environ.get(var)
    return os.path.join(base, *parts) if base else None


def windows_path_dirs() -> list:
    """PATH as the registry holds it now. A tool installed after the agent's shell started (winget, an MSI) is on
    this PATH but not on the shell's own, so shutil.which alone misses it."""
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    out = []
    for hive, key in ((winreg.HKEY_CURRENT_USER, "Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(hive, key) as k:
                value = winreg.QueryValueEx(k, "Path")[0]
        except OSError:
            continue
        out += [os.path.expandvars(d) for d in value.split(";") if d.strip()]
    return out


def tool_dirs(name: str) -> list:
    """Folders searched after PATH, most specific first. RW_PATH_ONLY=1 turns the search off (tests use it to
    hide installed tools)."""
    if os.environ.get("RW_PATH_ONLY") == "1":
        return []
    pf = [os.environ.get(v) for v in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")]
    pf = [p for p in dict.fromkeys(pf) if p] or [r"C:\Program Files"]
    local = os.environ.get("LOCALAPPDATA", "")
    dirs = []
    if name == "ebook-convert":
        dirs += [os.path.join(p, "Calibre2") for p in pf] + ["/Applications/calibre.app/Contents/MacOS", "/opt/calibre"]
    elif name == "soffice":
        dirs += [os.path.join(p, "LibreOffice", "program") for p in pf] + ["/Applications/LibreOffice.app/Contents/MacOS"]
    elif name == "pandoc":
        dirs += [env_dir("LOCALAPPDATA", "Pandoc")] + [os.path.join(p, "Pandoc") for p in pf]
    elif name == "mutool":
        dirs += [os.path.join(p, "MuPDF") for p in pf]
    elif name == "markitdown":   # pip --user and virtual environments put scripts beside the interpreter, off PATH
        import sysconfig
        for scheme in (f"{os.name}_user", "osx_framework_user", None):
            try:
                dirs.append(sysconfig.get_path("scripts", scheme) if scheme else sysconfig.get_path("scripts"))
            except KeyError:
                pass
        dirs.append(os.path.dirname(sys.executable))
    if name in ("pdftotext", "pdfinfo"):   # winget's poppler package is a portable zip under WinGet\Packages
        pk = Path(local, "Microsoft", "WinGet", "Packages") if local else None
        if pk and pk.is_dir():
            dirs += [str(d) for d in sorted(pk.glob("oschwartz10612.Poppler_*/poppler-*/Library/bin"), reverse=True)]
    if name in ("pdftotext", "pdfinfo", "antiword"):   # Git for Windows ships these in its MSYS2 tree
        dirs += [os.path.join(p, "Git", "mingw64", "bin") for p in pf] + [os.path.join(p, "Git", "usr", "bin") for p in pf]
    dirs += windows_path_dirs()
    dirs += [env_dir("LOCALAPPDATA", "Microsoft", "WinGet", "Links")] + [os.path.join(p, "WinGet", "Links") for p in pf]
    dirs += [env_dir("USERPROFILE", "scoop", "shims"), env_dir("ProgramData", "chocolatey", "bin"),
             os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    return [d for d in dict.fromkeys(dirs) if d]


def find_tool(name: str):
    p = shutil.which(name)
    if p:
        return p
    exts = [""] + (os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").lower().split(";") if os.name == "nt" else [])
    for d in tool_dirs(name):
        for e in exts:
            c = os.path.join(d, name + e)
            if os.path.isfile(c) and (os.name == "nt" or os.access(c, os.X_OK)):
                return c
    return None


def tools() -> dict:
    return {
        "pdftotext": find_tool("pdftotext"),
        "pdfinfo": find_tool("pdfinfo"),
        "mutool": find_tool("mutool"),
        "ebook-convert": find_tool("ebook-convert"),
        "soffice": find_tool("soffice") or find_tool("libreoffice"),
        "antiword": find_tool("antiword"),
        "pandoc": find_tool("pandoc"),
        "markitdown": find_tool("markitdown"),
    }


def run(cmd: list, timeout=600) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")   # Python-based tools (markitdown) print UTF-8
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise RWError(f"{Path(cmd[0]).name} took longer than {timeout} s")


def tool_error(r: subprocess.CompletedProcess, limit=400) -> str:
    """The informative part of a failed tool's output: from the last exception line on, else the last lines.
    The first lines of a Python traceback say nothing (L-004)."""
    lines = [ln.rstrip() for ln in (r.stderr + r.stdout).decode("utf-8", "replace").splitlines() if ln.strip()]
    lines = [ln for ln in lines if "platform independent libraries" not in ln]   # LibreOffice's harmless warning
    exc = [i for i, ln in enumerate(lines) if re.match(r"^[\w.]*(Error|Exception)\b.*:", ln.strip())]
    text = " ".join(ln.strip() for ln in (lines[exc[-1]:] if exc else lines[-3:]))
    return (text[:limit] + " ...") if len(text) > limit else (text or f"exit code {r.returncode}, no message")


CACHE_OFF = False


def cache_path(src: str, tag: str, ext: str) -> Path:
    st = os.stat(src)
    key = hashlib.sha1(f"{os.path.abspath(src)}|{st.st_size}|{st.st_mtime_ns}|{tag}|{VERSION}".encode()).hexdigest()[:20]
    d = Path(tempfile.gettempdir()) / "readwright-cache"
    d.mkdir(exist_ok=True)
    return d / f"{key}{ext}"


# ---------------------------------------------------------------- detection

ZIP_KINDS = {
    "application/epub+zip": "epub",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
}
CALIBRE_EXT = {".mobi": "mobi", ".azw": "mobi", ".azw3": "mobi", ".prc": "mobi", ".pdb": "pdb", ".lit": "lit",
               ".djvu": "djvu", ".djv": "djvu", ".chm": "chm", ".lrf": "lrf", ".snb": "snb", ".tcr": "tcr",
               ".pml": "pml", ".rb": "rb", ".kfx": "kfx", ".azw4": "azw4", ".cbz": "cbz", ".cbr": "cbr"}
TEXT_EXT = {".txt": "txt", ".text": "txt", ".md": "md", ".markdown": "md", ".rst": "rst", ".csv": "csv",
            ".tsv": "tsv", ".tab": "tsv", ".json": "json", ".log": "txt", ".htm": "html", ".html": "html",
            ".xhtml": "html", ".xht": "html", ".fb2": "fb2", ".eml": "eml", ".mht": "eml", ".mhtml": "eml",
            ".rtf": "rtf", ".xml": "xml", ".jsonl": "txt", ".ndjson": "txt"}
OLE_EXT = {".doc": "doc", ".dot": "doc", ".xls": "xls", ".xlt": "xls", ".ppt": "ppt", ".pps": "ppt", ".pot": "ppt",
           ".msg": "msg", ".docx": "ooxml-encrypted", ".xlsx": "ooxml-encrypted", ".pptx": "ooxml-encrypted"}


def detect(path: str) -> str:
    ext = Path(path).suffix.lower()
    with open(path, "rb") as f:
        head = f.read(8192)
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return detect_zip(path, ext)
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.lstrip()[:5] == b"{\\rtf":
        return "rtf"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if ext in OLE_EXT:
            return OLE_EXT[ext]
        blob = read_capped(path, 4 * MB) if os.path.getsize(path) <= 4 * MB else head
        if "EncryptedPackage".encode("utf-16-le") in blob:
            return "ooxml-encrypted"
        for name, kind in (("WordDocument", "doc"), ("Workbook", "xls"), ("PowerPoint Document", "ppt")):
            if name.encode("utf-16-le") in blob:
                return kind
        return "doc"
    if len(head) >= 68 and head[60:68] in (b"BOOKMOBI", b"TEXtREAd"):
        return "mobi" if head[60:68] == b"BOOKMOBI" else "pdb"
    if head.startswith(b"\xeaDRMION\xee"):
        return "kfx-drm"
    if head.startswith(b"CONT") and head[4:6] in (b"\x01\x00", b"\x02\x00"):   # KFX container, version 1 or 2 (R-20260929-7)
        return "kfx"
    if head.startswith(b"ITOLITLS"):
        return "lit"
    if head.startswith(b"AT&TFORM"):
        return "djvu"
    if head.startswith(b"ITSF"):
        return "chm"
    if head[:3] in (b"\xff\xd8\xff",) or head.startswith(b"\x89PNG") or head[:6] in (b"GIF87a", b"GIF89a"):
        return "image"
    if head.startswith(b"Rar!"):
        return "rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if b"\x00" in head[:4096] and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return CALIBRE_EXT.get(ext, "binary")
    # text-like
    t = decode_text(head).lstrip("\ufeff \t\r\n")
    low = t[:2048].lower()
    if "<fictionbook" in low:
        return "fb2"
    if ext in (".htm", ".html", ".xhtml", ".xht") or re.match(r"(<\?xml[^>]*>\s*)?(<!--.*?-->\s*)*<!doctype html", low, re.S) \
            or low.startswith("<html") or re.search(r"<html[\s>]", low[:1024]):
        return "html"
    if ext in (".eml", ".mht", ".mhtml") or re.match(r"(?:(?:return-path|received|from|to|subject|date|message-id|mime-version|x-[\w-]+|delivered-to):[^\n]*\n(?:[ \t][^\n]*\n)*){3,}", low):
        return "eml"
    if ext in TEXT_EXT:
        return TEXT_EXT[ext]
    if low.startswith("{") or low.startswith("["):
        try:
            json.loads(decode_text(read_capped(path)))
            return "json"
        except ValueError:
            pass
    return "txt"


def detect_zip(path: str, ext: str) -> str:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise RWError(f"{path} starts like a zip but is damaged")
    with z:
        names = set(z.namelist())
        if "mimetype" in names:
            mt = z.read("mimetype")[:200].decode("ascii", "replace").strip()
            if mt in ZIP_KINDS:
                return ZIP_KINDS[mt]
            if mt.startswith("application/vnd.oasis.opendocument"):
                return "odf"
        if "META-INF/container.xml" in names and any(n.lower().endswith(".opf") for n in names):
            return "epub"
        if "word/document.xml" in names:
            return "docx"
        if "ppt/presentation.xml" in names:
            return "pptx"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "content.xml" in names and "META-INF/manifest.xml" in names:
            return "odf"
    if ext == ".kfx-zip":
        return "kfx"
    if ext == ".cbz":
        return "cbz"
    return "zip"


# ---------------------------------------------------------------- HTML -> paragraphs

BLOCK = {"p", "div", "section", "article", "header", "footer", "main", "aside", "nav", "blockquote", "figure",
         "figcaption", "table", "tr", "ul", "ol", "dl", "dt", "dd", "li", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
         "hr", "address", "body", "center", "caption", "details", "summary", "form", "fieldset", "legend"}
SKIP = {"script", "style", "noscript", "template", "svg", "math", "head", "object", "iframe", "button", "select", "nav"}


class HTMLText(HTMLParser):
    """Turns (X)HTML into Para blocks; records element ids -> index of the next block."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras: list[Para] = []
        self.ids: dict[str, int] = {}
        self.buf: list[str] = []
        self.kind = "p"
        self.level = 0
        self.skip = 0
        self.pre = 0
        self.quote = 0
        self.title = ""
        self.in_title = False
        self.cells: list[str] | None = None
        self.links: list = []  # (href, text, depth) for nav documents
        self._a = None
        self.depth = 0

    def flush(self):
        if self.cells is not None:   # inside a table row: blocks within a cell only add a space
            self.buf.append(" ")
            return
        raw = "".join(self.buf)
        self.buf = []
        if self.pre:
            t = raw.strip("\n")
            if t.strip():
                self.paras.append(Para("pre", t))
        else:
            t = clean(raw)
            if t:
                kind = self.kind
                if kind == "p" and self.quote:
                    kind = "quote"
                self.paras.append(Para(kind, t, self.level))
        self.kind, self.level = "p", 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("ol", "ul"):
            self.depth += 1
        if tag == "title":
            self.in_title = True
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        for key in ("id", "name"):
            if a.get(key) and (key == "id" or tag == "a"):
                pending = 1 if (tag in BLOCK and self.cells is None and clean("".join(self.buf))) else 0
                self.ids.setdefault(a[key], len(self.paras) + pending)
        if tag == "a":
            self._a = [a.get("href") or "", [], self.depth]
        if tag == "br":
            self.buf.append("\n" if self.pre else " ")
            return
        if tag == "img" and a.get("alt") and len(a["alt"]) > 1 and self.kind == "h":
            self.buf.append(a["alt"])
        if tag in ("td", "th"):
            if self.cells is not None:
                self.buf = []
            return
        if tag == "tr":
            self.flush()
            self.cells = []
            self.buf = []
            return
        if tag in BLOCK:
            self.flush()
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.kind, self.level = "h", int(tag[1])
            elif tag == "li":
                self.kind = "li"
            elif tag == "pre":
                self.pre += 1
            elif tag == "blockquote":
                self.quote += 1

    def handle_endtag(self, tag):
        if tag in ("ol", "ul"):
            self.depth = max(0, self.depth - 1)
        if tag == "title":
            self.in_title = False
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "a" and self._a is not None:
            self.links.append((self._a[0], clean("".join(self._a[1])), self._a[2]))
            self._a = None
        if tag in ("td", "th") and self.cells is not None:
            self.cells.append(clean("".join(self.buf)))
            self.buf = []
            return
        if tag == "tr" and self.cells is not None:
            cells = self.cells
            self.cells = None
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                self.paras.append(Para("row", "\t".join(cells)))
            self.buf = []
            return
        if tag in BLOCK:
            self.flush()
            if tag == "pre":
                self.pre = max(0, self.pre - 1)
            elif tag == "blockquote":
                self.quote = max(0, self.quote - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title += data
            return
        if self.skip:
            return
        self.buf.append(data)
        if self._a is not None:
            self._a[1].append(data)

    def close(self):
        super().close()
        if self.cells is not None:
            self.handle_endtag("tr")
        self.flush()


def html_paras(text: str) -> HTMLText:
    p = HTMLText()
    p.feed(text)
    p.close()
    return p


def html_charset(data: bytes) -> str | None:
    m = re.search(rb"""<meta[^>]+charset=["']?([\w-]+)""", data[:4096], re.I) or \
        re.search(rb"""<\?xml[^>]+encoding=["']([\w-]+)""", data[:200], re.I)
    return m.group(1).decode("ascii", "replace") if m else None


def split_by_headings(paras, max_level=3, default_title="") -> list:
    """Sections at each heading of level <= max_level; text before the first heading is its own section."""
    secs: list[Section] = []
    cur = Section(default_title, [], 1, "")
    for i, p in enumerate(paras):
        if p.kind == "h" and 1 <= p.level <= max_level:
            if cur.paras or cur.title != default_title:
                secs.append(cur)
            cur = Section(p.text, [p], p.level, f"p{i + 1}")
        else:
            cur.paras.append(p)
    if cur.paras:
        secs.append(cur)
    if secs and not secs[0].sid:
        secs[0].sid = "p1"
        if not secs[0].title:
            secs[0].title = "(start)" if len(secs) > 1 else default_title or "(text)"
    return normalise_levels(secs)


def normalise_levels(secs):
    if secs:
        top = min(s.level for s in secs)
        for s in secs:
            s.level = s.level - top + 1
    return secs


def chunk(paras, title="part", words=CHUNK_WORDS) -> list:
    """Split unstructured text into parts of about `words` words at paragraph boundaries."""
    secs, cur, n, start = [], [], 0, 1
    for i, p in enumerate(paras, 1):
        cur.append(p)
        n += len(p.text.split())
        if n >= words:
            secs.append(Section("", cur, 1, f"p{start}"))
            cur, n, start = [], 0, i + 1
    if cur:
        secs.append(Section("", cur, 1, f"p{start}"))
    for k, s in enumerate(secs, 1):
        first = s.paras[0].text[:60] if s.paras else ""
        s.title = f"{title} {k}: {first}" + ("..." if s.paras and len(s.paras[0].text) > 60 else "")
    return secs


def structure(paras, default_title="", max_level=3) -> list:
    if any(p.kind == "h" and p.level <= max_level for p in paras):
        secs = split_by_headings(paras, max_level, default_title)
        out = []
        for s in secs:   # a huge heading-less stretch still gets parts
            if s.words() > CHUNK_WORDS * 4 and not any(p.kind == "h" for p in s.paras[1:]):
                parts = chunk(s.paras, s.title or "part")
                for p in parts:
                    p.level = s.level
                out.extend(parts)
            else:
                out.append(s)
        return out
    if sum(len(p.text.split()) for p in paras) > CHUNK_WORDS * 1.5:
        return chunk(paras)
    return [Section(default_title or "(text)", list(paras), 1, "p1")] if paras else []


# ---------------------------------------------------------------- EPUB

FONT_OBFUSCATION = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}


def epub_drm(z: zipfile.ZipFile) -> str | None:
    names = set(z.namelist())
    kinds = []
    if "META-INF/rights.xml" in names:
        kinds.append("Adobe ADEPT (META-INF/rights.xml)")
    if "META-INF/license.lcpl" in names:
        kinds.append("Readium LCP (META-INF/license.lcpl)")
    if "META-INF/sinf.xml" in names:
        kinds.append("Apple FairPlay (META-INF/sinf.xml)")
    if "META-INF/encryption.xml" in names:
        root = xml_root(zread(z, "META-INF/encryption.xml"))
        enc = []
        for ed in root.iter():
            if local(ed.tag) != "EncryptedData":
                continue
            alg = next((m.get("Algorithm") for m in ed.iter() if local(m.tag) == "EncryptionMethod"), None)
            uri = next((c.get("URI") for c in ed.iter() if local(c.tag) == "CipherReference"), "")
            if alg not in FONT_OBFUSCATION:
                enc.append(uri)
        if enc:
            kinds.append(f"{len(enc)} encrypted resources in META-INF/encryption.xml (e.g. {enc[0]})")
        elif kinds:
            kinds = []   # rights file present but nothing actually encrypted
    return "; ".join(kinds) if kinds else None


def load_epub(path) -> Doc:
    doc = Doc(path, "epub")
    z = zipfile.ZipFile(path)
    with z:
        drm = epub_drm(z)
        if drm:
            raise RWError(f"DRM-protected EPUB: {drm}. readwright does not remove DRM. Read it in the store's own app, "
                          "or ask the publisher for a DRM-free copy.")
        names = z.namelist()
        lower = {n.lower(): n for n in names}

        def get(name):
            n = name if name in names else lower.get(name.lower())
            if n is None:
                n = lower.get(unquote(name).lower())
            return zread(z, n) if n else None

        opf_path = None
        if "META-INF/container.xml" in names:
            c = xml_root(zread(z, "META-INF/container.xml"))
            for rf in c.iter():
                if local(rf.tag) == "rootfile" and rf.get("full-path"):
                    opf_path = rf.get("full-path")
                    break
        if not opf_path or get(opf_path) is None:
            opf_path = next((n for n in names if n.lower().endswith(".opf")), None)
        if not opf_path:
            raise RWError("EPUB has no package document (.opf)")
        base = posixpath.dirname(opf_path)
        opf = xml_root(get(opf_path))

        def resolve(href, rel_base=base):
            href = unquote(href)
            return posixpath.normpath(posixpath.join(rel_base, href)) if rel_base else posixpath.normpath(href)

        meta = {}
        manifest, spine, toc_id, nav_href = {}, [], None, None
        for el in opf.iter():
            t = local(el.tag)
            if t in ("title", "creator", "language", "publisher", "date", "identifier", "description") and el.text \
                    and el.text.strip():
                key = {"creator": "author"}.get(t, t)
                if key == "author" and "author" in meta:
                    meta[key] += "; " + el.text.strip()
                elif key not in meta:
                    meta[key] = clean(el.text) if key != "description" else clean(re.sub(r"<[^>]+>", " ", el.text))[:300]
            elif t == "item":
                manifest[el.get("id")] = (resolve(el.get("href", "")), el.get("media-type", ""), el.get("properties", "") or "")
                if "nav" in (el.get("properties") or "").split():
                    nav_href = resolve(el.get("href", ""))
            elif t == "spine":
                toc_id = el.get("toc")
            elif t == "itemref":
                spine.append((el.get("idref"), el.get("linear", "yes")))
        doc.meta = meta

        # titles from nav (EPUB 3) or NCX (EPUB 2)
        entries = []   # (file, fragment, title, depth)
        if nav_href and get(nav_href):
            nav = nav_entries(decode_text(get(nav_href)))
            nb = posixpath.dirname(nav_href)
            for href, title, depth in nav:
                f, frag = urldefrag(href)
                if f or frag:
                    entries.append((resolve(f, nb) if f else nav_href, frag, title, depth))
        if not entries:
            ncx = manifest.get(toc_id) if toc_id else None
            if not ncx:
                ncx = next((v for v in manifest.values() if v[1] == "application/x-dtbncx+xml"), None)
            if ncx and get(ncx[0]):
                nb = posixpath.dirname(ncx[0])
                for src, title, depth in ncx_entries(get(ncx[0])):
                    f, frag = urldefrag(src)
                    entries.append((resolve(f, nb), frag, title, depth))

        by_file: dict[str, list] = {}
        for f, frag, title, depth in entries:
            by_file.setdefault(f.lower(), []).append((frag, title, depth))

        def carry_on(paras) -> bool:
            """Text the toc does not point at and with no heading of its own continues the previous section:
            converters split long chapters across files at arbitrary points (L-003)."""
            if entries and doc.sections and paras and not any(p.kind == "h" for p in paras):
                doc.sections[-1].paras.extend(paras)
                return True
            return False

        seen = set()
        for idref, linear in spine:
            item = manifest.get(idref)
            if not item or item[0] in seen:
                continue
            seen.add(item[0])
            if "html" not in item[1] and not item[0].lower().endswith((".html", ".htm", ".xhtml", ".xml")):
                continue
            data = get(item[0])
            if data is None:
                doc.notes.append(f"spine item missing from the zip: {item[0]}")
                continue
            h = html_paras(decode_text(data, html_charset(data)))
            targets = by_file.get(item[0].lower(), [])
            cuts = {}   # block index -> [titles], depth
            for frag, title, depth in targets:
                idx = h.ids.get(frag, 0) if frag else 0
                if idx not in cuts:
                    cuts[idx] = ([title], depth)
                elif title not in cuts[idx][0]:
                    cuts[idx][0].append(title)
            if not cuts:
                if carry_on(h.paras):
                    continue
                first_h = next((p.text for p in h.paras if p.kind == "h"), "")
                doc.sections.append(Section(first_h, h.paras, 1, item[0]))
                continue
            points = sorted(cuts)
            if points[0] > 0:
                lead = h.paras[:points[0]]
                if lead and not carry_on(lead):
                    first_h = next((p.text for p in lead if p.kind == "h"), "")
                    doc.sections.append(Section(first_h, lead, cuts[points[0]][1], item[0]))
            for k, idx in enumerate(points):
                end = points[k + 1] if k + 1 < len(points) else len(h.paras)
                titles, depth = cuts[idx]
                frag = next((fr for fr, t, d in targets if t == titles[0]), "")
                doc.sections.append(Section(" / ".join(titles), h.paras[idx:end], depth,
                                            item[0] + (f"#{frag}" if frag else "")))
        for s in doc.sections:
            if not s.title:
                s.title = untitled(s)
            if base and s.sid.startswith(base + "/"):
                s.sid = s.sid[len(base) + 1:]   # ids relative to the package folder
        normalise_levels(doc.sections)
    return doc


def untitled(s: Section) -> str:
    first = next((p.text for p in s.paras if p.text), "")
    return f"(untitled: {first[:50]}{'...' if len(first) > 50 else ''})" if first else "(untitled, no text)"


def nav_entries(text: str) -> list:
    """(href, title, depth) from the EPUB 3 nav document's toc nav."""
    m = re.search(r"<nav\b[^>]*(?:epub:type|role)\s*=\s*[\"'][^\"']*\b(?:toc|doc-toc)\b[^>]*>(.*?)</nav>", text, re.S | re.I)
    if not m:
        m = re.search(r"<nav\b[^>]*>(.*?)</nav>", text, re.S | re.I)
    if not m:
        return []
    p = HTMLText()
    p.feed(m.group(1))
    p.close()
    return [(h, t, max(1, d)) for h, t, d in p.links if h and t]


def ncx_entries(data: bytes) -> list:
    root = xml_root(data)
    out = []

    def walk(el, depth):
        for np_ in el:
            if local(np_.tag) != "navPoint":
                continue
            label = ""
            src = ""
            for c in np_:
                if local(c.tag) == "navLabel":
                    label = clean(" ".join(x.text or "" for x in c.iter() if local(x.tag) == "text"))
                elif local(c.tag) == "content":
                    src = c.get("src", "")
            if src:
                out.append((src, label, depth))
            walk(np_, depth + 1)

    for el in root.iter():
        if local(el.tag) == "navMap":
            walk(el, 1)
            break
    return out


# ---------------------------------------------------------------- OOXML: DOCX, PPTX, XLSX

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def ooxml_core(z) -> dict:
    meta = {}
    if "docProps/core.xml" in z.namelist():
        r = xml_root(zread(z, "docProps/core.xml"))
        for el in r:
            t = local(el.tag)
            if el.text and el.text.strip() and t in ("title", "creator", "language", "subject", "created"):
                meta[{"creator": "author"}.get(t, t)] = clean(el.text)
    return meta


def load_docx(path) -> Doc:
    doc = Doc(path, "docx")
    with zipfile.ZipFile(path) as z:
        doc.meta = ooxml_core(z)
        styles = {}
        if "word/styles.xml" in z.namelist():
            for st in xml_root(zread(z, "word/styles.xml")).iter(W + "style"):
                sid = st.get(W + "styleId")
                name_el = st.find(W + "name")
                name = (name_el.get(W + "val") if name_el is not None else "") or ""
                ol = st.find(f"{W}pPr/{W}outlineLvl")
                lvl = None
                m = re.match(r"(?i)heading\s*(\d)", name)
                if m:
                    lvl = int(m.group(1))
                elif name.lower() == "title":
                    lvl = 1
                elif ol is not None and ol.get(W + "val", "").isdigit() and int(ol.get(W + "val")) < 9:
                    lvl = int(ol.get(W + "val")) + 1
                if lvl:
                    styles[sid] = lvl
        body = xml_root(zread(z, "word/document.xml")).find(W + "body")
        paras = []
        if body is None:
            return doc
        for el in body:
            t = local(el.tag)
            if t == "p":
                p = docx_para(el, styles)
                if p:
                    paras.append(p)
            elif t == "tbl":
                for tr in el.iter(W + "tr"):
                    cells = [clean(" ".join(filter(None, (docx_text(p) for p in tc.iter(W + "p"))))) for tc in tr.findall(W + "tc")]
                    if any(cells):
                        paras.append(Para("row", "\t".join(cells)))
            elif t == "sdt":
                for p in el.iter(W + "p"):
                    q = docx_para(p, styles)
                    if q:
                        paras.append(q)
        doc.sections = structure(paras, doc.meta.get("title", ""))
    return doc


def docx_text(p) -> str:
    out = []
    for el in p.iter():
        t = local(el.tag)
        if t in ("t", "delText") and el.text and t == "t":
            out.append(el.text)
        elif t == "tab":
            out.append("\t")
        elif t in ("br", "cr"):
            out.append(" ")
        elif t == "noBreakHyphen":
            out.append("-")
    return "".join(out)


def docx_para(p, styles):
    text = clean(docx_text(p))
    if not text:
        return None
    ppr = p.find(W + "pPr")
    lvl = None
    if ppr is not None:
        ps = ppr.find(W + "pStyle")
        if ps is not None:
            lvl = styles.get(ps.get(W + "val"))
            if lvl is None:
                m = re.match(r"(?i)heading(\d)$", ps.get(W + "val") or "")
                lvl = int(m.group(1)) if m else None
        ol = ppr.find(W + "outlineLvl")
        if lvl is None and ol is not None and (ol.get(W + "val") or "").isdigit() and int(ol.get(W + "val")) < 9:
            lvl = int(ol.get(W + "val")) + 1
        if lvl is None and ppr.find(W + "numPr") is not None:
            return Para("li", text)
    return Para("h", text, lvl) if lvl else Para("p", text)


A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def rels(z, path) -> dict:
    d, f = posixpath.split(path)
    rp = posixpath.join(d, "_rels", f + ".rels")
    if rp not in z.namelist():
        return {}
    out = {}
    for r in xml_root(zread(z, rp)):
        tgt = r.get("Target", "")
        if r.get("TargetMode") == "External":
            continue
        out[r.get("Id")] = posixpath.normpath(tgt.lstrip("/") if tgt.startswith("/") else posixpath.join(d, tgt))
    return out


def load_pptx(path) -> Doc:
    doc = Doc(path, "pptx")
    with zipfile.ZipFile(path) as z:
        doc.meta = ooxml_core(z)
        pres = xml_root(zread(z, "ppt/presentation.xml"))
        rel = rels(z, "ppt/presentation.xml")
        slides = [rel.get(s.get(R + "id")) for s in pres.iter(P + "sldId")]
        for n, sp in enumerate(filter(None, slides), 1):
            if sp not in z.namelist():
                continue
            root = xml_root(zread(z, sp))
            title, paras = "", []
            for shape in root.iter(P + "sp"):
                ph = shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                is_title = ph is not None and ph.get("type") in ("title", "ctrTitle")
                for ap in shape.iter(A + "p"):
                    t = clean("".join(x.text or "" for x in ap.iter(A + "t")))
                    if not t:
                        continue
                    if is_title and not title:
                        title = t
                        paras.append(Para("h", t, 1))
                    else:
                        paras.append(Para("p", t))
            for tbl in root.iter(A + "tbl"):
                for tr in tbl.iter(A + "tr"):
                    cells = [clean(" ".join(x.text or "" for x in tc.iter(A + "t"))) for tc in tr.iter(A + "tc")]
                    if any(cells):
                        paras.append(Para("row", "\t".join(cells)))
            notes = [v for v in rels(z, sp).values() if "notesSlide" in v]
            if notes and notes[0] in z.namelist():
                nroot = xml_root(zread(z, notes[0]))
                nt = []
                for shape in nroot.iter(P + "sp"):
                    ph = shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                    if ph is not None and ph.get("type") in ("sldNum", "sldImg", "hdr", "ftr", "dt"):
                        continue
                    for ap in shape.iter(A + "p"):
                        t = clean("".join(x.text or "" for x in ap.iter(A + "t")))
                        if t:
                            nt.append(t)
                if nt:
                    paras.append(Para("p", "Notes: " + " ".join(nt)))
            doc.sections.append(Section(f"slide {n}" + (f": {title}" if title else ""), paras, 1, f"slide{n}"))
    return doc


def col_index(ref: str) -> int:
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return max(0, n - 1)


XLSX_DATE_IDS = set(range(14, 18)) | {22} | set(range(27, 37)) | set(range(50, 59))   # built-in date formats
XLSX_TIME_IDS = {18, 19, 20, 21, 45, 46, 47}


def xlsx_date_styles(z, S) -> dict:
    """cellXfs index -> 'date' or 'time' for cells whose number format shows a date or time. Excel stores
    dates as day serials; without this a LibreOffice-written XLS shows 46294 for 2026-09-29 (L-007)."""
    if "xl/styles.xml" not in z.namelist():
        return {}
    root = xml_root(zread(z, "xl/styles.xml"))
    custom = {}
    for nf in root.iter(S + "numFmt"):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", nf.get("formatCode", "")).lower()
        if "y" in code or "d" in code:
            custom[nf.get("numFmtId")] = "date"
        elif "h" in code or "s" in code:
            custom[nf.get("numFmtId")] = "time"
    out = {}
    xfs = root.find(S + "cellXfs")
    for i, xf in enumerate(xfs if xfs is not None else []):
        fid = xf.get("numFmtId", "0")
        kind = custom.get(fid) or ("date" if fid.isdigit() and int(fid) in XLSX_DATE_IDS else
                                   "time" if fid.isdigit() and int(fid) in XLSX_TIME_IDS else None)
        if kind:
            out[i] = kind
    return out


def excel_date(serial: float, kind: str, d1904: bool) -> str:
    import datetime
    base = datetime.datetime(1904, 1, 1) if d1904 else datetime.datetime(1899, 12, 30)
    if not d1904 and serial < 60:
        base += datetime.timedelta(days=1)   # Excel's 1900 leap-year bug shifts serials before 1900-03-01
    dt = base + datetime.timedelta(seconds=round(serial * 86400))
    if kind == "time" and serial < 1:
        return dt.strftime("%H:%M:%S")
    if dt.hour == dt.minute == dt.second == 0:
        return dt.date().isoformat()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def load_xlsx(path) -> Doc:
    doc = Doc(path, "xlsx")
    S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as z:
        doc.meta = ooxml_core(z)
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in xml_root(zread(z, "xl/sharedStrings.xml")).iter(S + "si"):
                shared.append("".join(t.text or "" for t in si.iter(S + "t")))
        dates = xlsx_date_styles(z, S)
        wb = xml_root(zread(z, "xl/workbook.xml"))
        pr = wb.find(S + "workbookPr")
        d1904 = pr is not None and pr.get("date1904") in ("1", "true")
        rel = rels(z, "xl/workbook.xml")
        for sh in wb.iter(S + "sheet"):
            target = rel.get(sh.get(R + "id"))
            name = sh.get("name", "sheet")
            if not target or target not in z.namelist():
                continue
            paras, capped = [], False
            with z.open(target) as f:
                row_cells: dict = {}
                for ev, el in ET.iterparse(f, events=("end",)):
                    t = local(el.tag)
                    if t == "c":
                        typ = el.get("t")
                        v = el.find(S + "v")
                        if typ == "s" and v is not None and (v.text or "").isdigit():
                            i = int(v.text)
                            val = shared[i] if i < len(shared) else ""
                        elif typ == "inlineStr":
                            val = "".join(x.text or "" for x in el.iter(S + "t"))
                        elif typ == "b" and v is not None:
                            val = "TRUE" if v.text == "1" else "FALSE"
                        else:
                            val = v.text if v is not None and v.text else ""
                            st = el.get("s")
                            if val and typ in (None, "n") and st and st.isdigit() and int(st) in dates:
                                try:
                                    val = excel_date(float(val), dates[int(st)], d1904)
                                except (ValueError, OverflowError):
                                    pass
                        ci = col_index(el.get("r", "")) if el.get("r") else len(row_cells)
                        if ci < MAX_COLS and val != "":
                            row_cells[ci] = clean(val)
                        el.clear()
                    elif t == "row":
                        if row_cells:
                            width = max(row_cells) + 1
                            paras.append(Para("row", "\t".join(row_cells.get(i, "") for i in range(width))))
                        row_cells = {}
                        el.clear()
                        if len(paras) >= MAX_ROWS:
                            capped = True
                            break
            if capped:
                doc.notes.append(f"sheet {name}: stopped at {MAX_ROWS} rows")
            doc.sections.append(Section(f"sheet: {name}", paras, 1, f"sheet:{name}"))
    return doc


# ---------------------------------------------------------------- ODF

NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"


def odf_text(el) -> str:
    out = []

    def walk(e):
        t = local(e.tag)
        if t == "s":
            out.append(" " * int(e.get(f"{{{NS_TEXT}}}c", "1") or 1))
        elif t == "tab":
            out.append("\t")
        elif t == "line-break":
            out.append(" ")
        elif t in ("note", "annotation"):
            pass
        else:
            if e.text:
                out.append(e.text)
            for c in e:
                walk(c)
        if e.tail and e is not el:
            out.append(e.tail)

    walk(el)
    return "".join(out)


def odf_meta(z) -> dict:
    meta = {}
    if "meta.xml" in z.namelist():
        for el in xml_root(zread(z, "meta.xml")).iter():
            t = local(el.tag)
            if el.text and el.text.strip() and t in ("title", "creator", "initial-creator", "language", "subject"):
                key = {"creator": "author", "initial-creator": "author"}.get(t, t)
                meta.setdefault(key, clean(el.text))
    return meta


def load_odf(path, fmt) -> Doc:
    doc = Doc(path, fmt)
    with zipfile.ZipFile(path) as z:
        doc.meta = odf_meta(z)
        root = xml_root(zread(z, "content.xml"))
        body = next((e for e in root.iter() if local(e.tag) == "body"), root)
        if fmt == "ods":
            for tbl in body.iter(f"{{{NS_TABLE}}}table"):
                name = tbl.get(f"{{{NS_TABLE}}}name", "sheet")
                paras, empty_run = [], 0
                for row in tbl.iter(f"{{{NS_TABLE}}}table-row"):
                    cells = []
                    for c in row:
                        if local(c.tag) not in ("table-cell", "covered-table-cell"):
                            continue
                        rep = min(int(c.get(f"{{{NS_TABLE}}}number-columns-repeated", "1")), MAX_COLS)
                        txt = clean(" ".join(odf_text(p) for p in c if local(p.tag) == "p"))
                        cells.extend([txt] * (rep if txt else min(rep, MAX_COLS - len(cells))))
                        if len(cells) >= MAX_COLS:
                            break
                    while cells and not cells[-1]:
                        cells.pop()
                    if cells:
                        rrep = min(int(row.get(f"{{{NS_TABLE}}}number-rows-repeated", "1")), 1000)
                        paras.extend(Para("row", "\t".join(cells)) for _ in range(rrep))
                    if len(paras) >= MAX_ROWS:
                        doc.notes.append(f"sheet {name}: stopped at {MAX_ROWS} rows")
                        break
                doc.sections.append(Section(f"sheet: {name}", paras, 1, f"sheet:{name}"))
            return doc
        if fmt == "odp":
            for n, page in enumerate(body.iter(f"{{{NS_DRAW}}}page"), 1):
                paras = [Para("p", clean(odf_text(p))) for p in page.iter() if local(p.tag) in ("p", "h") and clean(odf_text(p))]
                name = page.get(f"{{{NS_DRAW}}}name", "")
                title = paras[0].text[:80] if paras else name
                doc.sections.append(Section(f"slide {n}" + (f": {title}" if title else ""), paras, 1, f"slide{n}"))
            return doc
        paras = []

        def walk(e):
            for c in e:
                t = local(c.tag)
                if t == "h":
                    txt = clean(odf_text(c))
                    if txt:
                        paras.append(Para("h", txt, int(c.get(f"{{{NS_TEXT}}}outline-level", "1") or 1)))
                elif t == "p":
                    txt = clean(odf_text(c))
                    if txt:
                        paras.append(Para("p", txt))
                elif t == "list-item":
                    for p in c.iter():
                        if local(p.tag) in ("p", "h") and clean(odf_text(p)):
                            paras.append(Para("li", clean(odf_text(p))))
                elif t == "table-row":
                    cells = [clean(" ".join(odf_text(p) for p in cell.iter() if local(p.tag) == "p"))
                             for cell in c if local(cell.tag) == "table-cell"]
                    if any(cells):
                        paras.append(Para("row", "\t".join(cells)))
                elif t in ("sequence-decls", "tracked-changes", "forms"):
                    continue
                else:
                    walk(c)

        walk(body)
        doc.sections = structure(paras, doc.meta.get("title", ""))
    return doc


# ---------------------------------------------------------------- FB2

def load_fb2(path, data: bytes | None = None) -> Doc:
    doc = Doc(path, "fb2")
    root = xml_root(data if data is not None else read_capped(path))
    meta = {}
    for ti in root.iter():
        if local(ti.tag) == "title-info":
            for el in ti:
                t = local(el.tag)
                if t == "book-title" and el.text:
                    meta["title"] = clean(el.text)
                elif t == "author":
                    name = clean(" ".join((x.text or "") for x in el if local(x.tag) in ("first-name", "middle-name", "last-name")))
                    if name:
                        meta["author"] = meta["author"] + "; " + name if "author" in meta else name
                elif t == "lang" and el.text:
                    meta["language"] = el.text.strip()
            break
    doc.meta = meta

    def para_of(el):
        return clean("".join(el.itertext()))

    def content(sec, depth):
        title = ""
        paras = []
        for c in sec:
            t = local(c.tag)
            if t == "title":
                title = " ".join(para_of(p) for p in c if para_of(p))
                if title:
                    paras.append(Para("h", title, depth))
            elif t in ("p", "subtitle", "text-author"):
                if para_of(c):
                    paras.append(Para("p", para_of(c)))
            elif t in ("poem", "cite", "epigraph"):
                for p in c.iter():
                    if local(p.tag) in ("v", "p", "text-author") and para_of(p):
                        paras.append(Para("quote", para_of(p)))
            elif t == "table":
                for tr in c:
                    cells = [para_of(td) for td in tr]
                    if any(cells):
                        paras.append(Para("row", "\t".join(cells)))
        return title, paras

    def walk(sec, depth, prefix):
        title, paras = content(sec, depth)
        if paras:   # a section holding only sub-sections still shows as a (short) heading entry
            doc.sections.append(Section(title or "(untitled)", paras, depth, prefix))
        for i, k in enumerate([c for c in sec if local(c.tag) == "section"], 1):
            walk(k, depth + 1, f"{prefix}.{i}")

    bodies = [b for b in root if local(b.tag) == "body"]
    for bi, body in enumerate(bodies, 1):
        name = body.get("name")   # the main body has no name; notes bodies are usually name="notes"
        title, paras = content(body, 1)
        if paras:
            doc.sections.append(Section(title or (name or "front"), paras, 1, f"b{bi}"))
        for i, sec in enumerate([c for c in body if local(c.tag) == "section"], 1):
            walk(sec, 1, f"{name or 'b' + str(bi)}.{i}")
    normalise_levels(doc.sections)
    return doc


# ---------------------------------------------------------------- plain text family

# "CHAPTERXXVII" happens when a converter drops the line break between word and number (L-006).
HEAD_RE = re.compile(r"^\s*(chapter|part|book|prologue|epilogue|interlude|appendix|introduction|preface|afterword)"
                     r"(?:\b|(?-i:(?=[IVXLCDM]+\b|\d)))[\w .:'-]{0,60}$", re.I)


def heading_line(s: str) -> str | None:
    """The heading text when a line reads like CHAPTER 12. Brackets around it are dropped: Project Gutenberg
    texts end an illustration caption with the heading, as in 'Chapter I.]' (L-003)."""
    t = s.strip().strip("[]").strip()
    if HEAD_RE.match(t):
        return t
    m = GUTENBERG_RE.match(t)   # the licence after the book's end becomes its own section
    return m.group(1).strip() if m else None


GUTENBERG_RE = re.compile(r"^\*{3}\s*((?:START|END) OF (?:THE|THIS) PROJECT GUTENBERG E-?BOOK\b.{0,120}?)\s*\*{3}$", re.I)


def text_paras(text: str, fmt: str) -> list:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    paras, buf = [], []
    fence = False

    def flush():
        if buf:
            t = clean(" ".join(buf))
            if t:
                paras.append(Para("p", t))
            buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if fmt == "md" and s.startswith("```"):
            flush()
            j = i + 1
            code = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            if code:
                paras.append(Para("pre", "\n".join(code)))
            i = j + 1
            continue
        if not s:
            flush()
        elif fmt == "md" and re.match(r"^#{1,6}\s", s):
            flush()
            m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", s)
            paras.append(Para("h", clean(m.group(2)), len(m.group(1))))
        elif fmt == "md" and re.match(r"^([-*+]|\d+[.)])\s+\S", s):
            flush()
            paras.append(Para("li", clean(re.sub(r"^([-*+]|\d+[.)])\s+", "", s))))
        elif fmt in ("rst", "md") and i + 1 < len(lines) and re.match(r"^([=\-~^\"'`#*+])\1{2,}\s*$", lines[i + 1]) \
                and len(lines[i + 1].strip()) >= len(s) and not buf:
            flush()
            ch = lines[i + 1].strip()[0]
            order = "=-~^\"'`#*+"
            paras.append(Para("h", clean(s), 1 + (order.index(ch) if ch in order else 3) if fmt == "rst" else (1 if ch == "=" else 2)))
            i += 2
            continue
        elif fmt == "rst" and re.match(r"^([=\-~^\"'`#*+])\1{2,}\s*$", s):
            pass   # overline
        elif fmt == "txt" and not buf and heading_line(s) and (i + 1 >= len(lines) or not lines[i + 1].strip()):
            flush()
            paras.append(Para("h", clean(heading_line(s)), 1))
        else:
            buf.append(s)
        i += 1
    flush()
    return paras


def load_text(path, fmt, data: bytes | None = None) -> Doc:
    doc = Doc(path, fmt)
    raw = data if data is not None else read_capped(path)
    text = decode_text(raw)
    if fmt in ("csv", "tsv"):
        sample = text[:8192]
        delim = "\t" if fmt == "tsv" else ","
        if fmt == "csv":
            try:
                delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                pass
        rows = []
        for n, r in enumerate(csv.reader(io.StringIO(text), delimiter=delim)):
            if n >= MAX_ROWS:
                doc.notes.append(f"stopped at {MAX_ROWS} rows")
                break
            if any(c.strip() for c in r):
                rows.append(Para("row", "\t".join(clean(c) for c in r)))
        size = 500
        for k in range(0, len(rows), size):
            doc.sections.append(Section(f"rows {k + 1}-{min(k + size, len(rows))}", rows[k:k + size], 1, f"row{k + 1}"))
        return doc
    if fmt == "json":
        try:
            obj = json.loads(text)
        except ValueError as e:
            raise RWError(f"invalid JSON: {e}")
        if isinstance(obj, dict):
            items = [(str(k), v) for k, v in obj.items()]
        elif isinstance(obj, list):
            items = [(f"[{k}-{min(k + 50, len(obj)) - 1}]", obj[k:k + 50]) for k in range(0, len(obj), 50)]
        else:
            items = [("value", obj)]
        for k, v in items:
            lines = json.dumps(v, indent=1, ensure_ascii=False).split("\n")
            doc.sections.append(Section(k, [Para("row", ln) for ln in lines], 1, k))
        return doc
    paras = text_paras(text, "md" if fmt == "md" else ("rst" if fmt == "rst" else "txt"))
    if fmt in ("md", "rst") and not any(p.kind == "h" for p in paras):   # pandoc's Markdown of a heading-less FB2
        for p in paras:
            if p.kind == "p" and len(p.text) <= 80 and heading_line(p.text):
                p.kind, p.level, p.text = "h", 1, heading_line(p.text)
    doc.sections = structure(paras)
    return doc


def load_html(path, data: bytes | None = None) -> Doc:
    doc = Doc(path, "html")
    raw = data if data is not None else read_capped(path)
    h = html_paras(decode_text(raw, html_charset(raw)))
    if h.title.strip():
        doc.meta["title"] = clean(h.title)
    m = re.search(rb"<html[^>]*\blang=[\"']?([\w-]+)", raw[:4096], re.I)
    if m:
        doc.meta["language"] = m.group(1).decode("ascii", "replace")
    m = re.search(rb"""<meta[^>]+name=["']author["'][^>]+content=["']([^"']+)""", raw[:8192], re.I)
    if m:
        doc.meta["author"] = html.unescape(m.group(1).decode("utf-8", "replace"))
    doc.sections = structure(h.paras, doc.meta.get("title", ""))
    return doc


def load_xml(path) -> Doc:
    root = xml_root(read_capped(path))
    paras = [Para("p", clean(t)) for t in root.itertext() if clean(t)]
    doc = Doc(path, "xml")
    doc.sections = structure(paras, local(root.tag))
    return doc


# ---------------------------------------------------------------- RTF

RTF_SKIP = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header", "footer", "headerl", "headerr",
            "headerf", "footerl", "footerr", "footerf", "listtable", "listoverridetable", "rsidtbl", "generator",
            "themedata", "colorschememapping", "datastore", "latentstyles", "xmlnstbl", "fldinst", "revtbl",
            "pgdsctbl", "filetbl", "footnote", "annotation", "atnid", "atnauthor", "private", "nonshppict", "shppict"}
RTF_INFO = {"title", "author", "subject"}
RTF_CHARS = {"par": "\n\n", "sect": "\n\n", "page": "\n\n", "line": "\n", "row": "\n", "cell": "\t", "tab": "\t",
             "emdash": "\u2014", "endash": "\u2013", "lquote": "\u2018", "rquote": "\u2019", "ldblquote": "\u201c",
             "rdblquote": "\u201d", "bullet": "\u2022", "emspace": " ", "enspace": " ", "qmspace": " "}
RTF_SYMS = {"~": "\u00a0", "_": "-", "-": "", "\\": "\\", "{": "{", "}": "}", "\n": "\n\n", "\r": "\n\n"}
RTF_TOKEN = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\([^a-zA-Z'])|([{}])|([^\\{}\r\n]+)|[\r\n]+")


def rtf_to_text(data: str) -> tuple[str, dict]:
    """Basic RTF reader: keeps text, paragraphs, tabs and Unicode; skips destinations; never runs anything."""
    out: list[str] = []
    info: dict = {}
    skip, uc, fld, in_info = False, 1, None, False   # per-group state
    stack = []
    cp = "cp1252"
    pending = 0          # fallback characters still to drop after a Unicode escape
    raw = bytearray()    # hex-escaped bytes waiting to be decoded together (multi-byte code pages)
    star = False
    fresh = False        # the next control word is the first thing in its group

    def put(s):
        if fld is not None:
            info[fld] = info.get(fld, "") + s
        elif not skip:
            out.append(s)

    def flush_raw():
        if raw:
            try:
                s = bytes(raw).decode(cp)
            except (UnicodeDecodeError, LookupError):
                s = bytes(raw).decode("cp1252", "replace")
            raw.clear()
            put(s)

    for m in RTF_TOKEN.finditer(data):
        word, arg, hexa, sym, brace, text = m.groups()
        if hexa is not None:
            if pending:
                pending -= 1
            else:
                raw.append(int(hexa, 16))
            fresh = False
            continue
        flush_raw()
        if brace == "{":
            stack.append((skip, uc, fld, in_info))
            fresh, star = True, False
            continue
        if brace == "}":
            if stack:
                skip, uc, fld, in_info = stack.pop()
            fresh, star, pending = False, False, 0
            continue
        if sym is not None:
            if sym == "*":
                star = True
                continue
            fresh = False
            if pending:
                pending -= 1
                continue
            put(RTF_SYMS.get(sym, ""))
            continue
        if word is not None:
            first, fresh = fresh, False
            if star or (first and word in RTF_SKIP):
                star = False
                if word == "info":
                    skip, in_info = True, True
                else:
                    skip, fld = True, None
                continue
            if in_info and first and word in RTF_INFO:
                fld = word
                continue
            if word == "ansicpg" and arg:
                cp = f"cp{arg}"
            elif word == "uc" and arg:
                uc = int(arg)
            elif word == "u" and arg:
                n = int(arg)
                put(chr(n + 65536 if n < 0 else n))
                pending = uc
            elif word in RTF_CHARS:
                put(RTF_CHARS[word])
            continue
        if text is not None:
            fresh = False
            if pending:
                k = min(pending, len(text))
                text, pending = text[k:], pending - k
            if text:
                put(text)
    flush_raw()
    s = "".join(out).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return s, {k: clean(v) for k, v in info.items() if clean(v)}


def load_rtf(path, data: bytes | None = None) -> Doc:
    raw = data if data is not None else read_capped(path)
    text, info = rtf_to_text(raw.decode("latin-1"))
    doc = Doc(path, "rtf", meta=info)
    paras = []
    for block in re.split(r"\n\s*\n", text):
        rows = [r for r in block.split("\n") if r.strip()]
        if "\t" in block and len(rows) > 1:
            paras.extend(Para("row", "\t".join(clean(c) for c in r.split("\t"))) for r in rows)
        elif clean(block):
            paras.append(Para("p", clean(block)))
    for p in paras:
        if p.kind == "p" and heading_line(p.text):
            p.kind, p.level, p.text = "h", 1, heading_line(p.text)
    doc.sections = structure(paras, info.get("title", ""))
    return doc


# ---------------------------------------------------------------- EML

def load_eml(path, data: bytes | None = None) -> Doc:
    raw = data if data is not None else read_capped(path)
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    doc = Doc(path, "eml")
    for k in ("subject", "from", "to", "cc", "date"):
        if msg.get(k):
            doc.meta[k] = clean(str(msg.get(k)))
    doc.meta["title"] = doc.meta.get("subject", "")

    def body_parts(m, depth=0):
        parts, attachments = [], []
        for part in m.walk():
            ctype = part.get_content_type()
            disp = part.get_content_disposition()
            if part.is_multipart():
                continue
            if disp == "attachment" or (part.get_filename() and ctype not in ("text/plain", "text/html")):
                attachments.append(f"{part.get_filename() or '(unnamed)'} ({ctype}, {len(part.get_payload(decode=True) or b'')} bytes)")
                continue
            if ctype in ("text/plain", "text/html"):
                try:
                    content = part.get_content()
                except (LookupError, UnicodeDecodeError):
                    content = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
                parts.append((ctype, content))
        return parts, attachments

    parts, attachments = body_parts(msg)
    plain = [c for t, c in parts if t == "text/plain"]
    chosen = plain if plain else [c for t, c in parts if t == "text/html"]
    use_html = not plain
    head = [Para("row", f"{k.capitalize()}: {doc.meta[k]}") for k in ("from", "to", "cc", "date", "subject") if k in doc.meta]
    for i, c in enumerate(chosen or [""], 1):
        paras = list(head) if i == 1 else []
        paras += html_paras(c).paras if use_html else text_paras(c, "txt")
        if i == len(chosen or [""]) and attachments:
            paras.append(Para("p", "Attachments: " + "; ".join(attachments)))
        doc.sections.append(Section(doc.meta.get("subject", "(no subject)") if i == 1 else f"part {i}", paras, 1, f"part{i}"))
    return doc


# ---------------------------------------------------------------- external tools

def need(tool: str, what: str, install: str) -> str:
    p = tools().get(tool)
    if not p:
        raise RWError(f"{what} needs {install}. Nothing was installed; install it and run again.")
    return p


def load_pdf(path) -> Doc:
    doc = Doc(path, "pdf")
    tl = tools()
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - 65536))
        tail = f.read()
    if b"/Encrypt" in tail:
        doc.notes.append("the PDF is encrypted; text extraction works only when no password is needed to open it")
    if tl["pdfinfo"]:
        r = run([tl["pdfinfo"], "-enc", "UTF-8", path], 60)
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            k, _, v = line.partition(":")
            k = k.strip().lower()
            if k in ("title", "author", "pages", "subject") and v.strip():
                doc.meta[k] = v.strip()
    if tl["pdftotext"]:
        cp = cache_path(path, "pdftotext", ".txt")
        if CACHE_OFF or not cp.exists():
            r = run([tl["pdftotext"], "-enc", "UTF-8", path, str(cp)])
            if r.returncode != 0 or not cp.exists():
                raise RWError("pdftotext failed: " + tool_error(r))
        text = cp.read_bytes().decode("utf-8", "replace")
    elif tl["mutool"]:
        cp = cache_path(path, "mutool", ".txt")
        if CACHE_OFF or not cp.exists():
            r = run([tl["mutool"], "draw", "-q", "-F", "txt", "-o", str(cp), path])
            if r.returncode != 0 or not cp.exists():
                raise RWError("mutool failed: " + tool_error(r))
        text = cp.read_bytes().decode("utf-8", "replace")
    else:
        raise RWError("PDF needs pdftotext (poppler-utils; Windows: `choco install poppler` or `scoop install poppler`, "
                      "macOS: `brew install poppler`, Linux: `apt install poppler-utils`) or mutool (MuPDF). "
                      "Nothing was installed. An agent with a Read tool that takes PDF page ranges can read it "
                      "directly instead.")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    outline = pdf_outline(path, tl["mutool"]) if tl["mutool"] else []
    page_paras = [text_paras(p, "txt") for p in pages]
    for pp in page_paras:
        for p in pp:
            if p.kind == "h":
                p.kind = "p"
    if outline:
        starts = sorted({(pg, t, d) for t, pg, d in outline if 1 <= pg <= len(pages)}, key=lambda x: x[0])
        if starts and starts[0][0] > 1:
            doc.sections.append(Section(f"pages 1-{starts[0][0] - 1}", sum(page_paras[:starts[0][0] - 1], []), 1, "page1"))
        for k, (pg, t, d) in enumerate(starts):
            end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(pages)
            end = max(end, pg)
            doc.sections.append(Section(f"{t} (p. {pg}-{end})", sum(page_paras[pg - 1:end], []), d, f"page{pg}"))
    else:
        for n, pp in enumerate(page_paras, 1):
            first = pp[0].text[:50] if pp else ""
            doc.sections.append(Section(f"page {n}" + (f": {first}" if first else ""), pp, 1, f"page{n}"))
    return doc


def pdf_outline(path, mutool) -> list:
    """(title, page, depth) from `mutool show FILE outline`; best effort, empty on any surprise."""
    try:
        r = run([mutool, "show", path, "outline"], 60)
    except RWError:
        return []
    return parse_outline(r.stdout.decode("utf-8", "replace"))


def parse_outline(text: str) -> list:
    out = []
    # MuPDF 1.23: a marker (| leaf, + closed, - open), one tab per level, the quoted title, a tab, then
    # #page=N&zoom=... (checked on real files, L-005). Older builds indented with spaces.
    for line in text.splitlines():
        m = re.match(r'^( *)[|+\-]?(\t*) *"(.*)"\s+#?(?:page=)?(\d+)', line)
        if m:
            out.append((m.group(3), int(m.group(4)), max(1, len(m.group(2))) + len(m.group(1)) // 2))
    return out


def load_via_calibre(path, fmt) -> Doc:
    if fmt == "kfx-drm":
        raise RWError("DRM-protected Kindle book (KFX DRMION). readwright does not remove DRM; read it in a Kindle app.")
    if fmt in ("mobi", "pdb"):
        drm = mobi_drm(path)
        if drm:
            raise RWError(f"DRM-protected Kindle/Mobipocket book ({drm}). readwright does not remove DRM; "
                          "read it in a Kindle app or ask the seller for a DRM-free copy.")
    exe = need("ebook-convert", f"Reading a {fmt.upper()} file", "calibre's ebook-convert (https://calibre-ebook.com/download; "
               "macOS: `brew install --cask calibre`, Linux: `apt install calibre`)" +
               ("; KFX also needs the KFX Input calibre plugin" if fmt == "kfx" else ""))
    out = cache_path(path, "calibre", ".epub")
    if CACHE_OFF or not out.exists():
        tmp = out.with_suffix(".tmp.epub")
        r = run([exe, path, str(tmp)], 900)
        if r.returncode != 0 or not tmp.exists():
            err = (r.stdout + r.stderr).decode("utf-8", "replace")
            if "DRM" in err:
                raise RWError("calibre reports this book is DRM-protected. readwright does not remove DRM.")
            raise RWError("ebook-convert failed: " + tool_error(r))
        os.replace(tmp, out)
    doc = load_epub(str(out))
    doc.path, doc.fmt = path, fmt
    doc.notes.append(f"converted to EPUB with calibre ebook-convert (cached at {out})")
    return doc


def mobi_drm(path) -> str | None:
    with open(path, "rb") as f:
        head = f.read(78 + 8)
        if len(head) < 86:
            return None
        off = int.from_bytes(head[78:82], "big")
        f.seek(off)
        rec0 = f.read(16)
    if len(rec0) >= 14:
        enc = int.from_bytes(rec0[12:14], "big")
        if enc == 1:
            return "old Mobipocket encryption"
        if enc == 2:
            return "Mobipocket encryption"
    return None


def load_via_office(path, fmt) -> Doc:
    if fmt == "ooxml-encrypted":
        raise RWError("password-protected Office file (an encrypted OOXML package). Open it in Office with the "
                      "password and save an unprotected copy.")
    if fmt == "msg":
        raise RWError("Outlook .msg files are not read directly; save the message as .eml from the mail program, or use "
                      "--via markitdown with the markitdown[outlook] extra installed.")
    tl = tools()
    target = {"doc": "docx", "xls": "xlsx", "ppt": "pptx"}[fmt]
    if tl["soffice"]:
        out = cache_path(path, "soffice", "." + target)
        if CACHE_OFF or not out.exists():
            with tempfile.TemporaryDirectory() as td:
                profile = Path(td, "profile").as_uri()
                r = run([tl["soffice"], f"-env:UserInstallation={profile}", "--headless", "--norestore",
                         "--convert-to", target, "--outdir", td, path], 600)
                made = next(Path(td).glob("*." + target), None)
                if not made:
                    raise RWError("LibreOffice conversion failed: " + tool_error(r))
                shutil.copyfile(made, out)
        doc = {"docx": load_docx, "xlsx": load_xlsx, "pptx": load_pptx}[target](str(out))
        doc.path, doc.fmt = path, fmt
        doc.notes.append(f"converted to {target.upper()} with LibreOffice (macros are not run in headless conversion)")
        return doc
    if fmt == "doc" and tl["antiword"]:
        r = run([tl["antiword"], "-w", "0", path], 120)
        if r.returncode != 0:
            raise RWError("antiword failed: " + tool_error(r))
        doc = load_text(path, "txt", r.stdout)
        doc.fmt = "doc"
        doc.notes.append("text from antiword (headings are not kept)")
        return doc
    raise RWError(f"legacy .{fmt} files need LibreOffice (`soffice`, https://www.libreoffice.org/download)"
                  + (" or antiword" if fmt == "doc" else "") + ". Nothing was installed.")


def load_via(path, via) -> Doc:
    cp = cache_path(path, via, ".md")
    tmp = cp.with_suffix(".tmp.md")
    if via == "pandoc":
        exe = need("pandoc", "--via pandoc", "pandoc (https://pandoc.org/installing.html)")
        cmd = [exe, path, "-t", "markdown", "--wrap=none", "-o", str(tmp)]
    else:
        exe = need("markitdown", "--via markitdown", "markitdown (`pipx install 'markitdown[all]'` or "
                   "`pip install --user 'markitdown[all]'`)")
        cmd = [exe, path, "-o", str(tmp)]   # -o writes UTF-8; its stdout uses the console code page on Windows
    if CACHE_OFF or not cp.exists():
        r = run(cmd, 600)
        if r.returncode != 0 or not tmp.exists():
            hint = " (markitdown reads most formats only with its extras: `markitdown[all]`)" \
                if via == "markitdown" and b"MissingDependency" in r.stderr else ""
            raise RWError(f"{via} failed on {Path(path).name}: {tool_error(r)}{hint}")
        os.replace(tmp, cp)
    out = cp.read_bytes()
    with open(path, "rb") as f:
        head = f.read(64).lstrip(b"\xef\xbb\xbf \t\r\n")
    if len(head) >= 16 and out.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(head):
        raise RWError(f"{via} does not read this format: it returned {Path(path).name} unchanged. "
                      "Drop --via to use readwright's own reader.")
    doc = load_text(path, "md", out)
    doc.fmt = f"{detect(path)} via {via}"
    doc.notes.append(f"converted to Markdown with {via}")
    return doc


# ---------------------------------------------------------------- dispatch

def zip_members(path) -> list:
    out = []
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            if i.is_dir() or i.filename.startswith("__MACOSX/"):
                continue
            ext = Path(i.filename).suffix.lower()
            kind = TEXT_EXT.get(ext) or {".epub": "epub", ".docx": "docx", ".odt": "odt", ".pptx": "pptx",
                                         ".xlsx": "xlsx", ".pdf": "pdf", ".zip": "zip"}.get(ext) or CALIBRE_EXT.get(ext) \
                or OLE_EXT.get(ext) or "?"
            out.append((i.filename, i.file_size, kind))
    return out


BIG_SECTION = CHUNK_WORDS * 4


def refine(doc: Doc) -> Doc:
    """Split a section of more than BIG_SECTION words at the headings or CHAPTER-style lines inside it. Converters
    often lose the outline: calibre's FB2 writes chapter titles as plain paragraphs, and its PDB round trip keeps
    three toc entries for a whole novel (L-006). Runs after every loader; well-structured files are untouched."""
    out = []
    for s in doc.sections:
        cuts = []
        untitled_ = s.title.startswith("(untitled")
        if s.words() > BIG_SECTION or untitled_:
            cuts = [j for j, p in enumerate(s.paras) if (j > 0 or untitled_) and p.kind in ("h", "p")
                    and len(p.text) <= 80 and (p.kind == "h" or heading_line(p.text))]
        if len(cuts) < (1 if untitled_ else 2):
            out.append(s)
            continue
        lead = s.paras[:cuts[0]]
        if untitled_ and out and not any(p.kind == "h" for p in lead):
            out[-1].paras.extend(lead)   # an untitled block's opening lines finish the chapter before it
        elif lead:
            out.append(Section(s.title, lead, s.level, s.sid))
        for k, j in enumerate(cuts):
            end = cuts[k + 1] if k + 1 < len(cuts) else len(s.paras)
            title = heading_line(s.paras[j].text) or s.paras[j].text
            out.append(Section(title, s.paras[j:end], s.level, f"{s.sid}@p{j + 1}"))
    doc.sections = [s for s in out if s.paras or s.title]
    return doc


def load(path: str, member: str | None = None, via: str | None = None) -> Doc:
    return refine(load_raw(path, member, via))


def load_raw(path: str, member: str | None = None, via: str | None = None) -> Doc:
    if not os.path.isfile(path):
        raise RWError(f"no such file: {path}")
    if via:
        return load_via(path, via)
    fmt = detect(path)
    if fmt == "zip":
        members = zip_members(path)
        readable = [m for m in members if m[2] != "?"]
        if member is None and len(readable) == 1 and len(members) <= 3:
            member = readable[0][0]
        if member is None:
            doc = Doc(path, "zip", members=members)
            return doc
        names = [m[0] for m in members]
        if member.isdigit() and int(member) >= 1 and int(member) <= len(names) and member not in names:
            member = names[int(member) - 1]
        if member not in names:
            cand = [n for n in names if n.lower().endswith(member.lower())]
            if len(cand) != 1:
                raise RWError(f"no single member matches {member!r}; run toc on the zip to list them")
            member = cand[0]
        with zipfile.ZipFile(path) as z:
            data = zread(z, member)
        suffix = Path(member).suffix or ".bin"
        td = tempfile.mkdtemp(prefix="readwright-")
        tmp = os.path.join(td, "member" + suffix)
        with open(tmp, "wb") as f:
            f.write(data)
        try:
            doc = load(tmp)
        finally:
            shutil.rmtree(td, ignore_errors=True)
        doc.path = f"{path} :: {member}"
        doc.notes.append(f"member {member} of {Path(path).name}")
        return doc
    if member:
        raise RWError("--member applies to zip archives only")
    if fmt == "epub":
        return load_epub(path)
    if fmt == "docx":
        return load_docx(path)
    if fmt == "pptx":
        return load_pptx(path)
    if fmt == "xlsx":
        return load_xlsx(path)
    if fmt in ("odt", "ods", "odp", "odf"):
        return load_odf(path, "odt" if fmt == "odf" else fmt)
    if fmt == "fb2":
        return load_fb2(path)
    if fmt == "html":
        return load_html(path)
    if fmt == "rtf":
        return load_rtf(path)
    if fmt == "eml":
        return load_eml(path)
    if fmt == "xml":
        return load_xml(path)
    if fmt in ("txt", "md", "rst", "csv", "tsv", "json"):
        return load_text(path, fmt)
    if fmt == "pdf":
        return load_pdf(path)
    if fmt in ("doc", "xls", "ppt", "msg", "ooxml-encrypted"):
        return load_via_office(path, fmt)
    if fmt in ("mobi", "pdb", "lit", "djvu", "chm", "kfx", "kfx-drm", "lrf", "snb", "tcr", "pml", "rb", "azw4"):
        return load_via_calibre(path, fmt)
    if fmt == "image":
        raise RWError("this is an image; readwright reads text documents (an agent's Read tool can view images)")
    if fmt in ("rar", "7z", "cbz", "cbr"):
        raise RWError(f"{fmt} archives are not supported; extract the file first")
    raise RWError(f"unrecognised binary file ({Path(path).suffix or 'no extension'}); try --via markitdown or --via pandoc if installed")


# ---------------------------------------------------------------- selection and output

def parse_selector(spec: str, n: int) -> list:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)?\s*-\s*(\d+)?", part)
        if m and (m.group(1) or m.group(2)):
            a = int(m.group(1) or 1)
            b = int(m.group(2) or n)
            out.extend(range(a, b + 1))
        elif part.isdigit():
            out.append(int(part))
        else:
            raise RWError(f"bad --section {spec!r}: use N, N-M, N- or N,M")
    bad = [i for i in out if i < 1 or i > n]
    if bad:
        raise RWError(f"section {bad[0]} does not exist; this document has {n} sections (1-{n})")
    seen, res = set(), []
    for i in out:
        if i not in seen:
            seen.add(i)
            res.append(i)
    return res


def select(doc: Doc, section: str | None, title: str | None) -> list:
    n = len(doc.sections)
    idx = parse_selector(section, n) if section else []
    if title:
        try:
            rx = re.compile(title, re.I)
        except re.error as e:
            raise RWError(f"bad --title regex: {e}")
        hits = [i for i, s in enumerate(doc.sections, 1) if rx.search(s.title) or rx.search(s.sid)]
        if not hits:   # "ANWUR AT" and "CHAPTERXXVII" in real tables of contents: retry with spaces ignored
            try:
                rx = re.compile(re.sub(r"\s+", "", title), re.I)
            except re.error:
                rx = None
            hits = [i for i, s in enumerate(doc.sections, 1) if rx and rx.search(re.sub(r"\s+", "", s.title))]
        if not hits:
            raise RWError(f"no section title matches {title!r}; run toc to see the titles, or grep for the text")
        idx = [i for i in idx if i in hits] if section else hits
    return idx


def fmt_n(n: int) -> str:
    return f"{n:,}"


def summary(doc: Doc) -> dict:
    words = sum(s.words() for s in doc.sections)
    chars = sum(s.chars() for s in doc.sections)
    return {"words": words, "chars": chars, "tokens": chars // 4}


def header_line(doc: Doc, i: int, s: Section, offsets: list, total_words: int) -> str:
    start = offsets[i - 1]
    pct = 100 * start // total_words if total_words else 0
    return (f"=== [{i}/{len(doc.sections)}] {s.title} | id {s.sid} | {fmt_n(s.words())} words | "
            f"starts at word {fmt_n(start + 1)} of {fmt_n(total_words)} ({pct}%) ===")


def word_offsets(doc: Doc) -> list:
    out, acc = [], 0
    for s in doc.sections:
        out.append(acc)
        acc += s.words()
    return out


def compose(doc: Doc, idx: list, fmt: str) -> str:
    offs = word_offsets(doc)
    total = offs[-1] + doc.sections[-1].words() if doc.sections else 0
    blocks = []
    for i in idx:
        s = doc.sections[i - 1]
        if fmt == "md":
            head = f"<!-- readwright section {i}/{len(doc.sections)} id={s.sid} words={s.words()} -->"
            paras = s.paras if (s.paras and s.paras[0].kind == "h") else [Para("h", s.title, min(6, s.level + 1))] + s.paras
            blocks.append(head + "\n\n" + render_paras(paras, "md"))
        else:
            blocks.append(header_line(doc, i, s, offs, total) + "\n\n" + render_paras(s.paras, "txt"))
    return "\n\n".join(blocks) + "\n"


def write_out(path: str, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def toc_lines(doc: Doc, limit: int) -> list:
    lines = []
    for i, s in enumerate(doc.sections, 1):
        if i > limit:
            lines.append(f"... {len(doc.sections) - limit} more sections (raise --limit)")
            break
        ind = "  " * (s.level - 1)
        lines.append(f"{i:>4}. {ind}{s.title}  ({fmt_n(s.words())} w)  [{s.sid}]")
    return lines


def doc_head(doc: Doc) -> str:
    sm = summary(doc)
    t = doc.meta.get("title")
    return (f"# {Path(doc.path).name if ' :: ' not in doc.path else doc.path} | {doc.fmt}"
            + (f" | {t}" if t else "")
            + f" | {len(doc.sections)} sections | {fmt_n(sm['words'])} words | ~{fmt_n(sm['tokens'])} tokens")


# ---------------------------------------------------------------- commands

def cmd_info(a) -> int:
    doc = load(a.file, a.member, a.via)
    real = a.file
    if doc.fmt == "zip":
        info = {"file": a.file, "format": "zip", "bytes": os.path.getsize(real), "members": len(doc.members)}
        if a.json:
            print(json.dumps(info | {"members_list": doc.members}, ensure_ascii=False, indent=1))
        else:
            for k, v in info.items():
                print(f"{k}: {v}")
            print("next: toc to list the members, then --member NAME")
        return 0
    sm = summary(doc)
    info = {"file": doc.path, "format": doc.fmt, "bytes": os.path.getsize(real)}
    info |= {k: v for k, v in doc.meta.items() if v}
    info |= {"sections": len(doc.sections), "words": sm["words"], "chars": sm["chars"], "tokens_approx": sm["tokens"]}
    if doc.sections:
        big = max(range(len(doc.sections)), key=lambda i: doc.sections[i].words())
        info["largest_section"] = f"{big + 1} ({fmt_n(doc.sections[big].words())} words)"
    if doc.notes:
        info["notes"] = doc.notes
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        return 0
    for k, v in info.items():
        if k == "notes":
            for n in v:
                print(f"note: {n}")
        else:
            print(f"{k}: {fmt_n(v) if isinstance(v, int) and k not in ('bytes',) else v}")
    print("next: toc, then read --section N" if sm["chars"] > DEFAULT_MAX_CHARS else "next: read (small enough to read whole)")
    return 0


def cmd_toc(a) -> int:
    doc = load(a.file, a.member, a.via)
    if doc.fmt == "zip":
        if a.json:
            print(json.dumps([{"n": i, "name": n, "bytes": b, "format": f} for i, (n, b, f) in enumerate(doc.members, 1)], ensure_ascii=False, indent=1))
            return 0
        print(f"# {Path(a.file).name} | zip | {len(doc.members)} members")
        for i, (n, b, f) in enumerate(doc.members, 1):
            print(f"{i:>4}. {n}  ({fmt_n(b)} bytes, {f})")
        print("read a member: rw.py toc FILE --member NAME (or its number)")
        return 0
    if a.json:
        offs = word_offsets(doc)
        print(json.dumps({"file": doc.path, "format": doc.fmt, "meta": doc.meta, "sections": [
            {"n": i, "title": s.title, "level": s.level, "id": s.sid, "words": s.words(), "start_word": offs[i - 1]}
            for i, s in enumerate(doc.sections, 1)]}, ensure_ascii=False, indent=1))
        return 0
    print(doc_head(doc))
    for n in doc.notes:
        print(f"note: {n}")
    print("\n".join(toc_lines(doc, a.limit)))
    return 0


def cmd_read(a) -> int:
    doc = load(a.file, a.member, a.via)
    if doc.fmt == "zip":
        raise RWError("this is a zip archive; list it with toc and pick a member with --member NAME")
    if not doc.sections:
        print(f"{doc_head(doc)}\n(no text found)")
        return 0
    idx = select(doc, a.section, a.title) if (a.section or a.title) else list(range(1, len(doc.sections) + 1))
    added = []
    for i in list(idx):   # a chapter's title page and its body are often separate sections (L-001)
        short = a.title and not a.section and doc.sections[i - 1].words() < SHORT_WORDS
        if (a.with_next or short) and i < len(doc.sections) and i + 1 not in idx:
            idx.insert(idx.index(i) + 1, i + 1)
            added.append(i + 1)
    text = compose(doc, idx, a.format)
    if a.out:
        if a.offset:
            text = text[a.offset:]
        if a.max_chars:
            text = text[:a.max_chars]
        write_out(a.out, text)
        print(f"wrote {fmt_n(len(text))} chars ({fmt_n(len(text.split()))} words, ~{fmt_n(len(text) // 4)} tokens) "
              f"from {len(idx)} section(s) to {a.out}")
        return 0
    limit = a.max_chars if a.max_chars is not None else DEFAULT_MAX_CHARS
    if not (a.section or a.title) and len(text) > limit:
        print(f"REFUSED: the whole text is {fmt_n(len(text))} chars (~{fmt_n(len(text) // 4)} tokens), over --max-chars "
              f"{fmt_n(limit)}. Pick sections with --section N or --title REGEX, search with grep, or write it all "
              f"to a file with --out FILE (or dump). Contents:\n")
        print(doc_head(doc))
        print("\n".join(toc_lines(doc, 300)))
        return EXIT_REFUSED
    start = a.offset or 0
    piece = text[start:start + limit]
    sys.stdout.write(piece)
    end = start + len(piece)
    if end < len(text):
        if not piece.endswith("\n"):
            sys.stdout.write("\n")
        print(f"[readwright: shown chars {fmt_n(start)}-{fmt_n(end)} of {fmt_n(len(text))}; continue with "
              f"--offset {end} or write it all with --out FILE]")
    if added and not a.with_next:
        print(f"[readwright: the title matched a short section, so the section after it was added ({', '.join(map(str, added))}): "
              f"a chapter's body often follows its title page. Use --section to read exactly one section]")
    last = idx[-1]
    if sum(doc.sections[i - 1].words() for i in idx) < SHORT_WORDS and last < len(doc.sections) and last + 1 not in idx:
        nxt = doc.sections[last]   # chapter-opener pages often hold only a title and an epigraph
        print(f"[readwright: the selection is short; the text may continue in section {last + 1}: "
              f"{nxt.title} ({fmt_n(nxt.words())} words). Read it with --section {last + 1} or --section {idx[0]}-{last + 1}]")
    return 0


def cmd_grep(a) -> int:
    doc = load(a.file, a.member, a.via)
    if doc.fmt == "zip":
        raise RWError("this is a zip archive; pick a member with --member NAME")
    pat = re.escape(a.pattern) if a.fixed else a.pattern
    try:
        rx = re.compile(pat, re.I if a.ignore_case else 0)
    except re.error as e:
        raise RWError(f"bad pattern: {e}")
    idx = select(doc, a.section, a.title) if (a.section or a.title) else range(1, len(doc.sections) + 1)
    hits = []
    per = {}
    for i in idx:
        s = doc.sections[i - 1]
        for j, p in enumerate(s.paras):
            ms = list(rx.finditer(p.text))
            if ms:
                per[i] = per.get(i, 0) + len(ms)
                hits.append((i, j, ms[0]))
    total = sum(per.values())
    if a.json:
        print(json.dumps({"pattern": a.pattern, "matches": total, "paragraphs": len(hits),
                          "by_section": [{"n": i, "title": doc.sections[i - 1].title, "count": c} for i, c in per.items()],
                          "hits": [{"section": i, "title": doc.sections[i - 1].title, "para": j + 1,
                                    "text": trim(doc.sections[i - 1].paras[j].text, m, a.width)}
                                   for i, j, m in hits[:a.max]]}, ensure_ascii=False, indent=1))
        return 0 if hits else 1
    if a.count:
        for i, c in per.items():
            print(f"{i:>4}. {doc.sections[i - 1].title}: {c}")
        print(f"{total} matches in {len(per)} sections")
        return 0 if hits else 1
    for i, j, m in hits[:a.max]:
        s = doc.sections[i - 1]
        print(f"--- [{i}] {s.title} | para {j + 1}/{len(s.paras)}")
        lo, hi = max(0, j - a.context), min(len(s.paras), j + a.context + 1)
        for k in range(lo, hi):
            t = s.paras[k].text
            if k == j:
                print("> " + trim(t, m, a.width))
            else:
                print("  " + (t if len(t) <= a.width // 2 else t[:a.width // 2] + " ..."))
    shown = min(len(hits), a.max)
    print(f"[{total} matches in {len(hits)} paragraphs across {len(per)} sections; showed {shown}"
          + (f"; raise --max or use --count" if len(hits) > a.max else "") + "]")
    return 0 if hits else 1


def trim(t: str, m, width: int) -> str:
    if len(t) <= width:
        return t
    half = width // 2
    a = max(0, m.start() - half)
    b = min(len(t), a + width)
    a = max(0, b - width)
    return ("... " if a else "") + t[a:b] + (" ..." if b < len(t) else "")


def cmd_dump(a) -> int:
    doc = load(a.file, a.member, a.via)
    if doc.fmt == "zip":
        raise RWError("this is a zip archive; pick a member with --member NAME")
    text = compose(doc, list(range(1, len(doc.sections) + 1)), a.format)
    if not a.out:
        if len(text) <= DEFAULT_MAX_CHARS:
            sys.stdout.write(text)
            return 0
        raise RWError(f"the text is {fmt_n(len(text))} chars; dump writes large texts to a file only: add --out FILE")
    write_out(a.out, text)
    print(f"wrote {doc.fmt} as {a.format}: {len(doc.sections)} sections, {fmt_n(len(text))} chars, "
          f"~{fmt_n(len(text) // 4)} tokens to {a.out}")
    print("section markers: " + ("lines starting '=== [N/' " if a.format == "txt" else "'<!-- readwright section N/' comments"))
    return 0


FORMATS = [   # (formats, what, tools that make it work; None = built in)
    ("epub", "EPUB 2/3 (spine order, nav or NCX titles)", None),
    ("docx", "Word 2007+ (headings from styles)", None),
    ("odt/ods/odp", "OpenDocument text, sheets, slides", None),
    ("pptx", "PowerPoint 2007+ (slides, notes)", None),
    ("xlsx", "Excel 2007+ (sheets as TSV)", None),
    ("fb2", "FictionBook 2", None),
    ("html/xhtml", "web pages (h1-h3 sections)", None),
    ("txt/md/rst", "plain text, Markdown, reStructuredText", None),
    ("rtf", "Rich Text Format (basic)", None),
    ("csv/tsv/json", "tables and JSON", None),
    ("eml", "email (text parts, attachment list)", None),
    ("zip", "archives of the above (--member)", None),
    ("pdf", "PDF (outline needs mutool)", ["pdftotext", "mutool"]),
    ("mobi/azw/azw3/prc/pdb/lit/djvu/chm/kfx", "ebooks via calibre", ["ebook-convert"]),
    ("doc/xls/ppt", "legacy Office", ["soffice", "antiword"]),
]


def cmd_formats(a) -> int:
    tl = tools()
    rows = []
    for f, w, need_ in FORMATS:
        if not need_:
            status = "built in"
        elif any(tl.get(t) for t in need_):
            have = [t for t in need_ if tl.get(t)]
            status = "ready (" + ", ".join(have) + ")"
            if f == "doc/xls/ppt" and not tl.get("soffice"):
                status = "doc only (antiword)"
        else:
            status = "needs " + " or ".join(need_)
        rows.append((f, w, status))
    if a.json:
        print(json.dumps({"version": VERSION, "tools": tl,
                          "formats": [{"formats": f, "what": w, "status": s} for f, w, s in rows]}, indent=1))
        return 0
    print(f"readwright {VERSION}")
    for f, w, s in rows:
        print(f"  {f:<40} {w:<45} {s}")
    print("tools: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in tl.items()))
    return 0


def main(argv=None) -> int:
    global CACHE_OFF
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="rw.py", description="Read text from documents and ebooks a section at a time.")
    ap.add_argument("--version", action="version", version=f"readwright {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, json_ok=True):
        p.add_argument("file")
        p.add_argument("--member", help="file inside a zip archive (name, suffix or number from toc)")
        p.add_argument("--via", choices=["pandoc", "markitdown"], help="convert with an installed external tool instead")
        p.add_argument("--no-cache", action="store_true", help="do not reuse cached conversions")
        if json_ok:
            p.add_argument("--json", action="store_true")

    p = sub.add_parser("info", help="format, size, metadata, sections, words, tokens")
    common(p)
    p = sub.add_parser("toc", help="numbered sections with titles and word counts")
    common(p)
    p.add_argument("--limit", type=int, default=1000)
    p = sub.add_parser("read", help="text of chosen sections")
    common(p, False)
    p.add_argument("--section", "-s", help="N, N-M, N- or N,M (numbers from toc)")
    p.add_argument("--title", "-t", help="regex matched against section titles and ids (case-insensitive)")
    p.add_argument("--max-chars", type=int, default=None, help=f"cap on characters printed (default {DEFAULT_MAX_CHARS})")
    p.add_argument("--offset", type=int, default=0, help="start this many characters into the selection")
    p.add_argument("--out", help="write the selection to this file instead of stdout")
    p.add_argument("--format", choices=["txt", "md"], default="txt")
    p.add_argument("--with-next", action="store_true", help="also read the section after each selected one")
    p = sub.add_parser("grep", help="regex search with section and paragraph context")
    common(p)
    p.add_argument("pattern")
    p.add_argument("-C", "--context", type=int, default=0, help="paragraphs of context")
    p.add_argument("-i", "--ignore-case", action="store_true")
    p.add_argument("-F", "--fixed", action="store_true", help="pattern is a plain string")
    p.add_argument("--max", type=int, default=20, help="paragraphs shown (default 20)")
    p.add_argument("--width", type=int, default=600, help="characters shown per matching paragraph")
    p.add_argument("--count", action="store_true", help="only counts per section")
    p.add_argument("--section", "-s")
    p.add_argument("--title", "-t")
    p = sub.add_parser("dump", help="whole text to a file with section markers")
    common(p, False)
    p.add_argument("--out")
    p.add_argument("--format", choices=["txt", "md"], default="txt")
    p = sub.add_parser("formats", help="supported formats and installed tools")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    CACHE_OFF = getattr(a, "no_cache", False)
    try:
        return {"info": cmd_info, "toc": cmd_toc, "read": cmd_read, "grep": cmd_grep, "dump": cmd_dump,
                "formats": cmd_formats}[a.cmd](a)
    except RWError as e:
        print(f"readwright: {e}", file=sys.stderr)
        return EXIT_ERR
    except (zipfile.BadZipFile, OSError) as e:
        print(f"readwright: cannot read {getattr(a, 'file', '')}: {e}", file=sys.stderr)
        return EXIT_ERR


if __name__ == "__main__":
    sys.exit(main())
