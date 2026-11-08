#!/usr/bin/env python3
"""rw.py - readwright: read text out of documents and ebooks a piece at a time.

Standard library only, Python 3.10+, Windows/macOS/Linux. Output is UTF-8 with LF
line endings on every platform.

The practice it supports: `info` (how big is it), `toc` (what is in it), `read`
only the sections needed, `grep` for names and phrases, `dump` a whole book to a
scratch file for the agent's own search tools. A whole book never goes to stdout.

Commands
  info  FILE                        format, size, metadata, sections, words, ~tokens
  toc   FILE [--limit N] [--ids] [--depth N] [--hide REGEX] [--group] numbered sections with titles and word counts (ids on request)
  read  FILE [--section N|N-M|N,M,P-Q] [--title REGEX] [--max-words N] [--max-chars N] [--offset N] [--at-para P] [--out FILE] [--format txt|md]
                                    [--with-next]
  grep  FILE PATTERN [-C N] [-A N] [-i] [-F] [--max N] [--width N] [--count]
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
import collections
import email
import email.policy
import hashlib
import html
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import sys
import tempfile
import zipfile
import posixpath
from dataclasses import dataclass, field, replace
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag
import xml.etree.ElementTree as ET

VERSION = "0.57.0"
BIG_SECTION_CHARS = 200_000

MB = 1024 * 1024
MAX_MB = int(os.environ.get("RW_MAX_MB", "512"))       # cap on bytes read from one file or zip member
MAX_ROWS = 200_000                                      # cap on spreadsheet rows per sheet
MAX_COLS = 1_000                                        # cap on spreadsheet columns
CHUNK_WORDS = 3_000                                     # unstructured text is split into parts this size
DEFAULT_MAX_CHARS = 25_000    # under Claude Code's 30,000-character inline limit for command output (T-20260929-4)
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
    aside: bool = False   # fixed layout: a caption, folio or picture, set beside the body rather than in it


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
    furniture: set = field(default_factory=set)    # furniture_key() of lines repeated on most pages (PDF)


LIGATURES = str.maketrans({"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
                           "\ufb05": "st", "\ufb06": "st"})


FIGURE_LINK = re.compile(r"(?:[\w ,-]{0,30}:\s*)?\[(?:formula: image|image omitted[^\]]*)\]\s*https?://\S+$")


def clean(s: str) -> str:
    s = s.translate(LIGATURES).replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    return " ".join(s.split())


def render_paras(paras, fmt="txt") -> str:
    out = []
    prev = None
    for p in paras:
        if p.kind == "h" and fmt == "md":
            t = "#" * max(1, min(6, p.level or 1)) + " " + p.text
        elif p.kind == "li":
            t = "  " * max(0, p.level - 1) + "- " + p.text   # a nested item stays under its parent
        elif p.kind == "quote" and fmt == "md":
            t = "> " + p.text
        elif p.kind == "pre" and fmt == "md":
            t = "```\n" + p.text + "\n```"
        else:
            t = p.text
        if out:
            # rows, list items and one-line-per-<pre> code listings stay together
            out.append("\n" if (prev in ("row", "li") or (prev == "pre" and fmt != "md")) and p.kind == prev else "\n\n")
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
    # Non-ASCII that is valid UTF-8 is UTF-8, whatever a meta tag claims, since latin-1 never fails (L-043 `utf8-before-meta`).
    # UTF-16 and UTF-32 without a BOM can also pass as UTF-8, so a hint naming them goes first.
    wide = hint and re.match(r"(utf-?(16|32)|ucs-?[24])", hint.lower().replace("_", "-"))
    for enc in ([hint, "utf-8"] if wide or data.isascii() else ["utf-8", hint]):
        if not enc:
            continue
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
    if name in ("pdftotext", "pdfinfo", "pdftoppm", "pdffonts"):   # winget's poppler package is a portable zip under WinGet\Packages
        pk = Path(local, "Microsoft", "WinGet", "Packages") if local else None
        if pk and pk.is_dir():
            dirs += [str(d) for d in sorted(pk.glob("oschwartz10612.Poppler_*/poppler-*/Library/bin"), reverse=True)]
    if name in ("pdftotext", "pdfinfo", "pdftoppm", "pdffonts", "antiword"):   # Git for Windows ships these in its MSYS2 tree
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
    """Paths of the external tools, None when absent. RW_HIDE_TOOLS=soffice,pdftotext treats the named tools
    as absent, to use a fallback route (antiword for DOC, mutool for PDF) or to test one."""
    hide = {t.strip() for t in os.environ.get("RW_HIDE_TOOLS", "").split(",") if t.strip()}
    found = {
        "pdftotext": find_tool("pdftotext"),
        "pdfinfo": find_tool("pdfinfo"),
        "pdffonts": find_tool("pdffonts"),
        "mutool": find_tool("mutool"),
        "ebook-convert": find_tool("ebook-convert"),
        "soffice": find_tool("soffice") or find_tool("libreoffice"),
        "antiword": find_tool("antiword"),
        "pandoc": find_tool("pandoc"),
        "markitdown": find_tool("markitdown"),
    }
    return {k: (None if k in hide else v) for k, v in found.items()}


def run(cmd: list, timeout=600) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")   # Python-based tools (markitdown) print UTF-8
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise RWError(f"{Path(cmd[0]).name} took longer than {timeout} s")


def tmp_cache(cp: Path) -> Path:
    """A private name beside a cache file: tools write here, so a concurrent reader never sees a half-written cache."""
    return cp.with_name(f"{cp.stem}.{os.getpid()}.{threading.get_ident()}.tmp{cp.suffix}")


def publish_cache(tmp: Path, cp: Path) -> None:
    """Move a finished temp file into place. On Windows a reader can hold cp open; its copy is as good, so keep that."""
    try:
        os.replace(tmp, cp)
    except PermissionError:
        if not cp.exists():
            raise
        tmp.unlink(missing_ok=True)


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
CODE_DIV = {"programcode", "programlisting", "sourcecode", "codeblock", "code-block"}   # code set in div or p, line by line (Springer)
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
        self.code_div = None   # [tag, depth] while inside a block that CODE_DIV names
        self.quote = 0
        self.title = ""
        self.in_title = False
        self.cells: list[str] | None = None
        self.row_pres: list[str] = []   # <pre> blocks set inside this table row
        self.cell_lead = ""             # cell text before the <pre> it holds
        self.links: list = []  # (href, text, depth) for nav documents
        self._a = None
        self.local_link = None   # text of the last same-file link (href="#x") closed in this block
        self.local_paras: set = set()   # blocks that are nothing but one same-file link
        self.depth = 0
        self.li_depth = 0
        self.sup = 0
        self.blockid = ""
        self.noteref = 0   # inside a note reference: its number prints as [40], not glued to the sentence

    def flush(self):
        if self.cells is not None:   # inside a table row: blocks within a cell only add a space
            self.buf.append(" ")
            return
        raw = "".join(self.buf)
        self.buf = []
        if self.pre:   # CRLF line ends and no-break-space indents become plain lines and spaces
            t = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").strip("\n")
            if t.strip():
                self.paras.append(Para("pre", t))
        else:
            t = clean(raw)
            if FIGURE_LINK.match(t):   # "top image: <icon> http://enlarge-me": a link to a bigger picture, not a formula
                t = ""
            while t and self.paras and self.paras[-1].text.startswith("[image: "):   # alt text repeated by the caption below it
                alt = self.paras[-1].text[8:-1]
                if len(alt) <= 20 or not t.endswith(alt):
                    break
                self.paras.pop()
            if t:
                kind = self.kind
                if kind == "p" and self.quote:
                    kind = "quote"
                self.paras.append(Para(kind, t, self.li_depth if kind == "li" else self.level))
                if self.local_link and self.local_link == t:
                    self.local_paras.add(len(self.paras) - 1)
        self.local_link = None
        self.kind, self.level = "p", 0

    def handle_starttag(self, tag, attrs):
        if tag == "a" and not dict(attrs).get("href"):   # an index-term anchor sits before punctuation: 'cost <a/>.' reads 'cost.'
            self._empty_anchor = True
        a = dict(attrs)
        if tag in ("ol", "ul"):
            self.depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "math" and not self.skip:   # MathML is skipped; say so, with its alttext when it has one
            alt = clean(a.get("alttext") or "")
            self.buf.append(f" [math: {alt}] " if alt else " [math omitted] ")
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        for key in ("id", "name"):
            if a.get(key) and (key == "id" or tag == "a"):
                pending = 1 if (tag in BLOCK and self.cells is None and clean("".join(self.buf))) else 0
                self.ids.setdefault(a[key], len(self.paras) + pending)
        if self.code_div:   # inner blocks are lines of the one listing
            if tag == self.code_div[0]:
                self.code_div[1] += 1
            if tag in BLOCK or tag == "br":
                self.buf.append("\n")
            return
        if (tag in ("div", "p") and self.cells is None and not self.pre
                and CODE_DIV & set((a.get("class") or "").lower().split())):
            self.flush()
            self.blockid = a.get("id") or ""
            self.pre += 1
            self.code_div = [tag, 1]
            return
        if tag == "sup":
            self.sup += 1
        if tag == "a":
            self._a = [a.get("href") or "", [], self.depth]
            kinds = f"{a.get('role') or ''} {a.get('epub:type') or ''}"
            if "noteref" in kinds or (self.sup and "#" in (a.get("href") or "")):
                self.noteref += 1
        if tag == "br":
            self.buf.append("\n" if self.pre else " ")
            return
        if tag == "img" and a.get("alt") and len(a["alt"]) > 1 and self.kind == "h":
            self.buf.append(a["alt"])
        elif tag == "img":   # an equation set as a picture (<p id="eq_11_32"><img alt="image">) says so, not a silent gap
            m = re.match(r"eq[_.-]?(\d+(?:[_.-]\d+)*)$", a.get("id") or self.blockid or "", re.I)
            if m:
                self.buf.append(f" [equation {re.sub(r'[_-]', '.', m.group(1))}: image] ")
            elif not self.pre and re.search(r"\[image[^\]]*\]\s*$", "".join(self.buf)):   # a second copy of a picture
                pass                                                                  # (EPUB and Kindle variants) is no formula
            elif not self.pre and clean("".join(self.buf)):   # a picture mid-sentence is an inline formula: "then ." loses it
                self.buf.append(" [formula: image] ")
            elif not self.pre and self.kind != "h" and self.cells is None:   # a picture in its own block (a table or
                alt = clean(a.get("alt") or "")                              # formula set as an image) is marked, not dropped
                name = posixpath.basename(a.get("src") or "")
                self.buf.append(f" [image: {alt}] " if len(alt) > 1 and alt.lower() not in ("image", "img", "figure", name.lower())
                                else f" [image omitted: {name}] " if name else " [image omitted] ")
        if tag == "sub" and self.buf and self.buf[-1][-1:].isalnum():   # tf<sub>td</sub> reads tf_td, not tftd
            self.buf.append("_")
        if tag in ("td", "th"):
            if self.cells is not None:
                self.buf = []
            return
        if tag == "tr":
            self.flush()
            self.cells = []
            self.row_pres = []
            self.buf = []
            return
        if tag == "li" and self.cells is not None and clean("".join(self.buf)):   # a list set inside a table cell keeps its items apart
            self.buf = ["".join(self.buf).rstrip() + "; "]
        if tag in BLOCK:
            self.flush()
            self.blockid = a.get("id") or ""
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.kind, self.level = "h", int(tag[1])
            elif tag == "li":
                self.kind = "li"
                self.li_depth = self.depth
            elif tag == "pre":
                self.pre += 1
                if self.cells is not None and self.pre == 1:   # a listing in a cell stays a code block, lines intact
                    self.cell_lead = "".join(self.buf)
                    self.buf = []
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
        if self.code_div:
            if tag == self.code_div[0]:
                self.code_div[1] -= 1
                if not self.code_div[1]:   # markup indentation goes; no-break-space indents stay (flush makes them spaces)
                    lines = [x.strip(" \t\r\n") for x in "".join(self.buf).split("\n")]
                    self.buf = ["\n".join(x for x in lines if x)]
                    self.flush()
                    self.pre = max(0, self.pre - 1)
                    self.code_div = None
                    return
            if tag in BLOCK:
                self.buf.append("\n")
            return
        if tag == "sup":
            self.sup = max(0, self.sup - 1)
        if tag == "a" and self.noteref:
            self.noteref -= 1
        if tag == "a" and self._a is not None:
            self.links.append((self._a[0], clean("".join(self._a[1])), self._a[2]))
            if self._a[0].startswith("#"):
                self.local_link = self.links[-1][1]
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
            for t in self.row_pres:
                self.paras.append(Para("pre", t))
            self.row_pres = []
            self.buf = []
            return
        if tag in BLOCK:
            if tag == "pre" and self.cells is not None and self.pre == 1:
                t = "".join(self.buf).replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").strip()
                if t:
                    self.row_pres.append(t)
                self.buf = [self.cell_lead]
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
        if data.strip():
            lead = data[:len(data) - len(data.lstrip())]
            glued = getattr(self, "_empty_anchor", False) or chr(10) in lead   # pretty-printed markup breaks the line before a comma
            self._empty_anchor = False
            if glued and data.lstrip()[0] in ",.;:)!?":
                data = data.lstrip()
                while self.buf and not self.buf[-1].strip():
                    self.buf.pop()
                if self.buf:
                    self.buf[-1] = self.buf[-1].rstrip()
        if self.noteref and data.strip():
            data = f"[{data.strip()}]"
        elif self.sup and data[:1].isdigit() and "".join(self.buf)[-1:].isdigit():   # 1.1021<sup>5</sup> reads 1.1021^5, not 1.10215
            data = "^" + data
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
    collapse_local_contents(p)
    return p


def collapse_local_contents(p: HTMLText, least: int = 3) -> None:
    """A chapter's own mini-contents (MIT Press: a run of paragraphs that are each one link to a heading
    further down the same file) printed every heading twice before the body (Roads, The Computer Music
    Tutorial, 2026-11-07). A run of `least` or more such blocks at the start or right after a heading
    becomes one marker line; ids are remapped so fragment links still land."""
    keep, remap, i, n = [], {}, 0, len(p.paras)
    while i < n:
        j = i
        while j < n and j in p.local_paras:
            j += 1
        if j - i >= least and (i == 0 or p.paras[i - 1].kind == "h"):
            for k in range(i, j):
                remap[k] = len(keep)
            keep.append(Para("p", f"[chapter contents: {j - i} headings; list them with read --headings]"))
            i = j
            continue
        remap[i] = len(keep)
        keep.append(p.paras[i])
        i += 1
    if len(keep) == n:
        return
    p.ids = {k: remap.get(v, len(keep)) for k, v in p.ids.items()}
    p.paras = keep


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
    words = sum(len(p.text.split()) for p in paras)
    if words > BIG_SECTION:   # plain text with its headings inline in capitals (L-021)
        parts = split_caps(Section(default_title or "(text)", list(paras), 1, "p1"))
        if parts:
            return parts
    if words > CHUNK_WORDS * 1.5:
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


FIXED_VIEWPORT = re.compile(r"""<meta(?=[^>]+name=["']viewport["'])[^>]*width=\s*\d+[^>]*height=\s*\d+""", re.I)
FIXED_SENTENCE_END = re.compile(r"""[.?!:]["'\u201d\u2019)]*$""")


def merge_fixed_layout(paras: list) -> list:
    """A fixed-layout EPUB page places each printed line, and each italic run inside a line, in its own block.
    Rejoin them: a block stays open until a line ends a sentence and the next starts with a capital, or a short
    all-capitals line (a label) follows a finished sentence. Headings, lists and tables pass through."""
    out, open_lines = [], []

    def flush():
        if open_lines:
            out.append(Para("p", join_lines(open_lines)))
            open_lines.clear()

    for p in paras:
        ended = not open_lines or FIXED_SENTENCE_END.search(open_lines[-1])
        label = p.text.isupper() and len(p.text.split()) <= 8 and ended   # mid-sentence capitals are a title: WALL-E
        if p.kind != "p" or label:
            flush()
            out.append(p)
            continue
        if p.text[0] in ".,:;!?)" and (open_lines or (out and out[-1].kind == "p")):   # punctuation after a run
            if open_lines:
                open_lines[-1] += p.text
            else:
                out[-1].text += p.text
            continue
        if open_lines and ended and p.text[:1].isupper():
            flush()
        open_lines.append(p.text)
    flush()
    return out


FIXED_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
FIXED_CAPTION_MIN_SHARE = 0.10   # of the body's characters
FIXED_REPEAT_MIN_PAGES = 0.25   # of the pages with text, for a caption size and for a folio line


def fixed_css(text: str) -> dict:
    """Plain `.class` and `#id` rules of a stylesheet, selector to declarations."""
    rules = {}
    for m in FIXED_CSS_RULE.finditer(re.sub(r"/\*.*?\*/", "", text, flags=re.S)):
        for sel in m[1].split(","):
            sel = sel.strip()
            if re.fullmatch(r"\w*[.#][\w-]+", sel):
                rules[sel[sel.index("." if "." in sel else "#"):]] = m[2]
    return rules


def fixed_styles(page: str, h, css: dict) -> list:
    """(font size, top) in pixels for each block of a page, from its `id` and `class`; None where the CSS is silent."""
    tags = {}
    for t in re.findall(r"<\w+\b[^>]*>", page):
        i, c = re.search(r"""\bid=["']([^"']+)""", t), re.search(r"""\bclass=["']([^"']+)""", t)
        if i and c:
            tags[i[1]] = c[1].split()

    def px(rule, name):
        m = re.search(name + r"\s*:\s*([\d.]+)px", rule or "", re.I)
        return float(m[1]) if m else None

    out = [(None, None)] * len(h.paras)
    for i, idx in h.ids.items():
        if idx < len(out) and i in tags:
            sizes = [px(css.get("." + c), "font-size") for c in tags[i]]
            out[idx] = (next((s for s in sizes if s), None), px(css.get("#" + i), r"(?<![-\w])top"))
    return out


def fixed_plan(pages: list) -> dict | None:
    """From (paras, styles) of every page, the book's type sizes: body is the size with the most characters; caption is
    the heaviest smaller size, if it holds a real share and recurs across the book; folio is a smaller size's usual
    line, repeated at one height. None when no such caption size stands out: then nothing is moved or marked."""
    chars, on_pages, tops = {}, {}, {}
    live = 0
    for paras, styles in pages:
        seen = set()
        for p, (size, top) in zip(paras, styles):
            if size:
                chars[size] = chars.get(size, 0) + len(p.text)
                seen.add(size)
                if top is not None:
                    tops.setdefault(size, {})
                    tops[size][top] = tops[size].get(top, 0) + 1
        live += bool(seen)
        for s in seen:
            on_pages[s] = on_pages.get(s, 0) + 1
    if not chars:
        return None
    body = max(chars, key=chars.get)
    smaller = [s for s in chars if s < body]
    caption = max(smaller, key=chars.get, default=None)
    if caption is None or chars[caption] < FIXED_CAPTION_MIN_SHARE * chars[body] \
            or on_pages[caption] < FIXED_REPEAT_MIN_PAGES * live:
        return None
    folio = {}
    for s in smaller:
        if s != caption and tops.get(s):
            top = max(tops[s], key=tops[s].get)
            if tops[s][top] >= FIXED_REPEAT_MIN_PAGES * live:
                folio[s] = top
    return {"body": body, "caption": caption, "folio": folio}


FIXED_MARKER = re.compile(r"\[(?:image omitted|image:|equation ).*\]")
FIXED_NUMBER = re.compile(r"\d{1,4}")


FIXED_ROMAN = re.compile(r"(?=[ivxlc])c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})")


def roman_value(text: str) -> int:
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    nums = [values[c] for c in text]
    return sum(-n if n < m else n for n, m in zip(nums, nums[1:] + [0]))


def fixed_folio_lines(pages: list) -> set:
    """(spine position, text) of the bare numbers that are folios: arabic or lowercase roman, rising one a file, or two a
    file on a spread that holds two pages. Roman front matter is short, so three files are enough for it (L-048 `fixed-folio-kinds`)."""
    found = set()
    for pattern, value, need in ((FIXED_NUMBER, int, max(3, FIXED_REPEAT_MIN_PAGES * len(pages))), (FIXED_ROMAN, roman_value, 3)):
        lines = [(n, p.text, value(p.text)) for n, paras in pages for p in paras if p.kind == "p" and pattern.fullmatch(p.text)]
        best, best_files = None, 0
        single, double = {}, {}
        for n, _, v in lines:
            single.setdefault(v - n, set()).add(n)
            for o in (v - 2 * n, v - 2 * n - 1):
                double.setdefault(o, set()).add(n)
        for step, table in ((1, single), (2, double)):
            for o, files in table.items():
                if len(files) > best_files:
                    best, best_files = (step, o), len(files)
        if best and best_files >= need:
            step, o = best
            found |= {(n, text) for n, text, v in lines if v - step * n == o or (step == 2 and v - step * n == o + 1)}
    return found


def split_fixed_markers(paras: list, is_folio) -> list:
    """No caption size to go on: still set picture markers and folios beside the text, so a sentence closes over them."""
    asides = [p for p in paras if p.kind == "p" and (FIXED_MARKER.fullmatch(p.text) or is_folio(p))]
    gone = {id(p) for p in asides}
    return merge_fixed_layout([p for p in paras if id(p) not in gone]) + [Para("p", p.text, aside=True) for p in asides]


def split_fixed_page(paras: list, styles: list, plan: dict, is_folio=lambda p: False) -> list:
    """Merge a page's body lines and set its captions, folio lines and pictures after them as asides. A caption is marked
    `[caption] `, unless the page has no body type to tell it from (acknowledgements set small on a page of their own)."""
    roles = []
    for p, (size, top) in zip(paras, styles):
        if p.kind != "p":
            roles.append("body")
        elif FIXED_MARKER.fullmatch(p.text) or is_folio(p):
            roles.append("other")
        elif size == plan["caption"]:
            roles.append("caption")
        elif size in plan["folio"] and top is not None and abs(top - plan["folio"][size]) <= 4:
            roles.append("other")
        elif size and size < plan["caption"]:
            roles.append("small")
        else:
            roles.append("body")
    for i, r in enumerate(roles):   # a label such as TOP LEFT: stands next to its caption
        if r == "small":
            near = roles[i - 1] if i else None, roles[i + 1] if i + 1 < len(roles) else None
            roles[i] = "caption" if "caption" in near else "body"
    has_body = any(r == "body" and p.kind == "p" for r, p in zip(roles, paras))
    out = merge_fixed_layout([p for r, p in zip(roles, paras) if r == "body"])
    for p, r in zip(paras, roles):
        if r == "other":
            out.append(Para("p", p.text, aside=True))
    for p in merge_fixed_layout([p for r, p in zip(roles, paras) if r == "caption"]):
        out.append(Para(p.kind, ("[caption] " if has_body else "") + p.text, p.level, True))
    return out


def rejoin_fixed_pages(paras: list) -> list:
    """A sentence that runs over a page turn becomes one paragraph, with the asides of the page held until it ends."""
    out, held, last = [], [], None
    for p in paras:
        if p.aside:
            held.append(p)
        elif p.kind == "p" and last is not None and not FIXED_SENTENCE_END.search(last.text):
            last.text = join_lines([last.text, p.text])
        else:
            out += held
            held = []
            out.append(p)
            last = p if p.kind == "p" else None
    return out + held


def unbreak_fixed_layout(sections: list) -> None:
    """Printed line breaks leave `explain-ing`. Drop that hyphen when the book also has the unbroken word."""
    pat = re.compile(r"\b([a-z]+)-([a-z]+)\b")
    words = {}
    for s in sections:
        for p in s.paras:
            for w in re.findall(r"[a-z]+", p.text):
                words[w] = words.get(w, 0) + 1
    for s in sections:
        for p in s.paras:
            p.text = pat.sub(lambda m: m[1] + m[2] if m[1] + m[2] in words else m[0], p.text)


def load_epub(path) -> Doc:
    doc = Doc(path, "epub")
    fixed_layout = False
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
                    meta[key] = clean(el.text) if key != "description" else \
                        clean(html.unescape(re.sub(r"<[^>]+>", " ", el.text)))[:300]
                if t == "identifier" and "isbn" not in meta:   # urn:isbn:978..., opf:scheme="ISBN", or a bare 10/13 digits
                    raw = el.text.strip()
                    scheme = " ".join(v for k, v in el.attrib.items() if local(k) == "scheme").lower()
                    digits = re.sub(r"[\s-]", "", re.sub(r"(?i)^urn:isbn:|^isbn:?", "", raw))
                    if re.fullmatch(r"(97[89])?\d{9}[\dXx]", digits) and ("isbn" in scheme or "isbn" in raw.lower()
                                                                          or re.fullmatch(r"[\d\s-]+[\dXx]", raw)):
                        meta["isbn"] = digits.upper()
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

        plan, styles_of, folio_at, folios = None, {}, {}, set()
        spine_files = [manifest[i][0] for i, _ in spine if i in manifest]
        if any(FIXED_VIEWPORT.search(decode_text(get(f) or b"")[:4000]) for f in spine_files[:5]):
            css_cache, census = {}, []
            for pos, f in enumerate(spine_files):
                data = get(f)
                page = decode_text(data, html_charset(data)) if data else ""
                if not FIXED_VIEWPORT.search(page[:4000]) or any(fr for fr, _, _ in by_file.get(f.lower(), [])):
                    continue
                css = {}
                for href in re.findall(r"""<link\b[^>]*\bhref=["']([^"']+\.css)""", page, re.I):
                    name = resolve(href, posixpath.dirname(f))
                    if name not in css_cache:
                        raw = get(name)
                        css_cache[name] = fixed_css(decode_text(raw)) if raw else {}
                    css |= css_cache[name]
                pg = html_paras(page)
                styles_of[f] = fixed_styles(page, pg, css)
                census.append((pg.paras, styles_of[f]))
                folio_at[f] = pos
            plan = fixed_plan(census)
            folios = fixed_folio_lines([(folio_at[f], c[0]) for f, c in zip(folio_at, census)])

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
            page = decode_text(data, html_charset(data))
            h = html_paras(page)
            targets = by_file.get(item[0].lower(), [])
            if FIXED_VIEWPORT.search(page[:4000]) and not any(frag for frag, _, _ in targets):   # fragments index blocks
                pos = folio_at.get(item[0])
                is_folio = lambda p: p.kind == "p" and (pos, p.text) in folios
                h.paras = split_fixed_page(h.paras, styles_of[item[0]], plan, is_folio) if plan and item[0] in styles_of \
                    else split_fixed_markers(h.paras, is_folio)
                fixed_layout = True
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
                doc.sections.append(Section(notes_part_title(doc.sections, h.paras, first_h) or first_h,
                                            h.paras, 1, item[0]))
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
        heal_stray_hyphens(doc.sections)
    oc = ocr_cache(path)
    if oc.exists():   # `rw.py ocr` ran on this image-only EPUB
        pages = oc.read_bytes().decode("utf-8", "replace").split("\f")
        page_paras = [text_paras(p, "txt") for p in pages]
        join_split_pages(page_paras)
        flat = [p for pp in page_paras for p in pp]
        whole = Section(doc.meta.get("title") or "(text)", flat, 1, "ocr")
        parts = split_caps(whole, len(pages)) if whole.words() > BIG_SECTION else None
        if parts:
            doc.sections = parts
        else:
            doc.sections = [Section(f"page {n}" + (f": {pp[0].text[:50]}" if pp else ""), pp, 1, f"page{n}")
                            for n, pp in enumerate(page_paras, 1)]
        doc.notes.append(f"text from OCR (`rw.py ocr`, kept in {oc}); expect misread letters")
        gap = missing_page_note(pages)
        if gap:
            doc.notes.append(gap)
    if fixed_layout:
        if plan or folios:
            for s in doc.sections:
                s.paras = rejoin_fixed_pages(s.paras)
        unbreak_fixed_layout(doc.sections)
    return doc


def missing_page_note(pages: list) -> str | None:
    """A scan can lack whole leaves. The last bare number on each page is its likely printed number; the longest rising
    run of those drops contents lists and figure numbers, and a jump well past the usual step marks a gap."""
    nums = []
    for i, p in enumerate(pages, 1):
        found = re.findall(r"(?m)^\s*(\d{1,4})\s*$", p)
        if found:
            nums.append((i, int(found[-1])))
    best = []
    runs = []
    for i, n in nums:
        run = [(i, n)]
        for r in runs:
            if r[-1][1] < n <= r[-1][1] + 12 and len(r) + 1 > len(run):
                run = r + [(i, n)]
        runs.append(run)
        if len(run) > len(best):
            best = run
    if len(best) < 8:
        return None
    steps = sorted(b[1] - a[1] for a, b in zip(best, best[1:]))
    usual = steps[len(steps) // 2]
    gaps = [f"between p. {a[1]} (section {a[0]}) and p. {b[1]} (section {b[0]})"
            for a, b in zip(best, best[1:]) if b[1] - a[1] >= max(3, 2 * usual)]
    if not gaps:
        return None
    return ("printed pages may be missing from this scan " + "; ".join(gaps[:6]) +
            "; look at those page images and say so in any notes")


IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp")


def epub_page_images(path) -> list:
    """Zip member names of the images an EPUB's spine shows, in reading order: <img src>, SVG <image href>, or an
    image as a spine item. An image-only EPUB (scanned pages wrapped by pdftohtml or calibre) is read by OCR-ing
    these (L-020 `image-only-epub-ocr`)."""
    out = []
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        return []
    with z:
        names = z.namelist()
        lower = {n.lower(): n for n in names}
        opf_path = None
        if "META-INF/container.xml" in names:
            m = re.search(rb'full-path="([^"]+)"', zread(z, "META-INF/container.xml"))
            opf_path = m.group(1).decode("utf-8", "replace") if m else None
        if not opf_path or opf_path not in names:
            opf_path = next((n for n in names if n.lower().endswith(".opf")), None)
        if not opf_path:
            return []
        base = posixpath.dirname(opf_path)
        manifest, spine = {}, []
        for el in xml_root(zread(z, opf_path)).iter():
            t = local(el.tag)
            if t == "item":
                manifest[el.get("id")] = posixpath.normpath(posixpath.join(base, unquote(el.get("href", ""))))
            elif t == "itemref":
                spine.append(el.get("idref"))
        for idref in spine:
            real = lower.get((manifest.get(idref) or "").lower())
            if not real:
                continue
            if real.lower().endswith(IMAGE_EXT):
                out.append(real)
                continue
            html = decode_text(zread(z, real))
            fb = posixpath.dirname(real)
            for m in re.finditer(r"<(?:\w+:)?(?:img|image)\b[^>]*?\s(?:src|xlink:href|href)\s*=\s*[\"']([^\"']+)", html, re.I):
                href = unquote(m.group(1).split("#")[0])
                q = lower.get(posixpath.normpath(posixpath.join(fb, href)).lower())
                if q and q.lower().endswith(IMAGE_EXT) and q not in out:
                    out.append(q)
    return out


NOTES_TITLE = re.compile(r"^\s*(?:end\s*notes|notes|references)\b", re.I)


def notes_part_title(sections, paras, first_h) -> str:
    """A file the toc skips that follows a notes section and is mostly numbered notes continues that section:
    a heading like 'Chapter 13' there names whose notes they are, not a chapter of the book."""
    if not sections or not NOTES_TITLE.match(sections[-1].title):
        return ""
    lines = [p.text for p in paras if p.kind != "h" and p.text]
    numbered = sum(1 for t in lines if re.match(r"^\[?\d{1,4}[\].)]?\s", t))
    if numbered < max(3, len(lines) * 0.6):
        return ""
    base = sections[-1].title.split(": ")[0]
    return f"{base}: {first_h}" if first_h else base


def title_repeated_notes(doc):
    """Notes sections that sit at the end and repeat their chapters' titles read as second copies of the chapters in
    the outline. Three or more trailing sections, each repeating an earlier title at under half its words, become
    'Notes: Chapter 8' (Quietly Powerful, 2026-11-06)."""
    secs = doc.sections
    first = {}
    for i, s in enumerate(secs):
        first.setdefault(s.title.strip().lower(), i)
    start = len(secs)
    while start > 0:
        s = secs[start - 1]
        j = first.get(s.title.strip().lower(), start - 1)
        if j >= start - 1 or not s.title.strip() or s.words() * 2 >= secs[j].words():
            break
        start -= 1
    if len(secs) - start >= 3:
        for s in secs[start:]:
            s.title = f"Notes: {s.title.strip()}"
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


BREAK_HYPHENS = "‐­"   # a word split at a line end by typesetting: always rejoined


def join_lines(lines) -> str:
    """Join a paragraph's lines with spaces, rejoining a word split at a line end: a U+2010 or soft hyphen before a
    letter is dropped ("conven-" + "tions" = "conventions", "Lang-" + "Chain" = "LangChain"); an ASCII hyphen
    before a lower-case letter is kept and the lines joined without a space ("well-" + "known" = "well-known"), since it may be a real compound."""
    out = ""
    for line in lines:
        if out and line[:1].isalpha() and out[-1] in BREAK_HYPHENS:
            out = out[:-1] + ("-" if keep_break_hyphen(out[:-1], line) else "") + line
        elif out and line[:1].islower() and out[-1] == "-" and out[-2:-1].isalpha():
            out += line
        else:
            out = out + " " + line if out else line
    # pdftotext can already have joined the lines ("conven‐ tions"); "pre‐ and post-war" keeps its hyphen
    out = SPLIT_WORD.sub(lambda m: "-" if keep_break_hyphen(out[:m.start()], out[m.end():]) else "", out)
    return SPLIT_THOUSANDS.sub(r"\1,", out)


# "3, 097Hz", "1, 000 through 50, 000RPM": the thin space after a thousands comma came out as a space. A group that
# starts with 0 or runs into a unit is one number; "pages 3, 100 and" stays a list.
SPLIT_THOUSANDS = re.compile(r"(?<![\d,])(\d{1,3}), (?=0\d\d(?!\d)|\d{3}[A-Za-z])")


SPLIT_WORD = re.compile(r"(?<=[^\W\d_])[‐­] (?!(?:and|or|nor|to)\b)(?=[^\W\d_])")


RUNNING_HEAD = re.compile(r"^((?:\d{1,4}|[ivxlc]{1,7}) \| [^|]{1,80}|[^|]{1,80} \| (?:\d{1,4}|[ivxlc]{1,7}))$")   # front matter numbers pages in roman


NUMBERED_HEAD = re.compile(r"^(?:#\s+(\S.{1,79})|(\S.{1,79}?)\s+#)$")


CAPTION_LINE = re.compile(r"(?:exhibit|figure|fig\.|table|listing|chart|box|map|plate|illustration)\s+[a-z]?[\d#]+[a-z]?(?:[-.:][\d#]+[a-z]?)*(?!\w)", re.I)
EDGE_NUMBER = re.compile(r"(\d+)\s+\S.*|.*\S\s+(\d+)")
HEAD_GAP = 3   # pages between two copies of a running head; a figure page can take one copy out of an every-other-page run


def pages_cluster(where: list) -> bool:
    """A running head sits on page after page or every other page; a real heading that recurs ("Key Takeaways" closing
    each chapter) is spread out (L-053 `spread-headings-stay`). True when at least half the gaps are short."""
    gaps = [b - a for a, b in zip(where, where[1:])]
    return sum(g <= HEAD_GAP for g in gaps) * 2 >= len(gaps)


def head_key(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line)).strip().casefold()


def edge_lines(page: str) -> list:
    idx = [i for i, l in enumerate(page.split("\n")) if l.strip()]
    return sorted({idx[0], idx[-1]}) if idx else []


def running_head_keys(pages, titles=()) -> set:
    """Pipe-less running heads ("42  Chapter 3: Standard Practices", "Chunking Text 85", a bare repeated book title,
    a bare page number): keys (digits as #, case folded) of page-edge lines that repeat at the edges of several pages,
    or whose text beside the number is a chapter or section title from the outline. A line ending in . ? ! : , ; is
    prose and never a head; a bare title must open or close a fifth of the pages."""
    seen, shifts = collections.defaultdict(list), collections.defaultdict(collections.Counter)
    for n, p in enumerate(pages):
        lines = p.split("\n")
        for k, line in {head_key(lines[i]): lines[i] for i in edge_lines(p)}.items():
            seen[k].append(n)
            m = EDGE_NUMBER.fullmatch(line.strip())
            if m:
                shifts[k][int(m.group(1) or m.group(2)) - n] += 1
    known = {re.sub(r"\s", "", head_key(t)) for t in titles}   # "Addi tive": pdftotext may split a word of a head
    keys = set()
    for k, where in seen.items():
        n = len(where)
        if not k or len(k) > 90 or k[-1] in ".?!:,;":
            continue
        m = NUMBERED_HEAD.match(k)
        if k == "#":
            keys.add(k)
        elif m:
            title = (m.group(1) or m.group(2)).strip()
            if CAPTION_LINE.match(title):
                continue   # "122 Exhibit 4-3": a caption with the folio glued on; strip_glued_folio takes the number
            if title.strip("# ") and (re.sub(r"\s", "", title) in known or n >= 3 and (pages_cluster(where) or
                                                  shifts[k].most_common(1)[0][1] * 2 > n)):
                keys.add(k)
        elif n >= max(5, len(pages) // 5) and len(k.split()) >= 2 and (pages_cluster(where) or len(pages) >= 100):
            keys.add(k)
    return keys


COLON_HEAD_AFTER = re.compile(r"\s*([^\W\d][^:\n]{2,110}?) ?: ?\d(?: ?\d){0,3}(?=\s|$)")
COLON_HEAD_BEFORE = re.compile(r"\s*\d(?: ?\d){0,3} ?: ?([^\W\d][^:\n]{2,110})")
COLON_HEAD_LEAST = 5


def colon_head_key(title: str) -> str:
    return re.sub(r"[\W\d_]", "", title).casefold()


def strip_colon_heads(pages: list) -> list:
    """OCR that glues a head to the page's first words, sometimes letter-spaced: "T h e B a c k g r o u n d to 1 9 4 5 : 13
    wire that". The left-hand form, "10 : The Background to 1945 body", has no end mark, so its length comes from the
    right-hand form: a key seen at least COLON_HEAD_LEAST times with the number after it. Spacing and digits are ignored
    in the key; a left-hand head is cut where the words so far spell that key, and the rest of the page stays."""
    ends, count = {}, collections.Counter()
    for n, p in enumerate(pages):
        m = COLON_HEAD_AFTER.match(p)
        if m:
            k = colon_head_key(m.group(1))
            count[k] += COLON_HEAD_LEAST if re.search(r"(?:\b\w ){3}", m.group(1)) else 1   # letter-spaced: one is proof
            ends[n] = (k, m.end())
    keys = {k for k, c in count.items() if len(k) >= 6 and c >= COLON_HEAD_LEAST}
    out = []
    for n, p in enumerate(pages):
        cut = ends[n][1] if n in ends and ends[n][0] in keys else 0
        m = COLON_HEAD_BEFORE.match(p) if not cut else None
        if m:
            spelled = ""
            for w in re.finditer(r"\S+", p[m.start(1):m.start(1) + 170]):
                spelled += colon_head_key(w.group())
                if spelled in keys:
                    cut = m.start(1) + w.end()
                if not any(k.startswith(spelled) for k in keys):
                    break
        out.append(p[cut:].lstrip() if cut else p)
    return out


SYMBOL_FONT_PLUS = re.compile(r"(?<=\d)þ(?=\d)|(?<=[\w)] )þ(?= [\w(])|(?<=[A-Za-z\d])þ(?=[\s.,;)]|$)", re.M)
SYMBOL_FONT_TIMES = re.compile(r"(?<=\d)Â(?=\d)")


def repair_symbol_font(page: str) -> str:
    """A math font with no Unicode map extracts plus as thorn and times as A-circumflex ("3þ3", "12Â7"). Only between
    digits, as a spaced operator, or closing a chord symbol: an Icelandic thorn opens a word and so stays."""
    return SYMBOL_FONT_TIMES.sub("×", SYMBOL_FONT_PLUS.sub("+", page))


def fix_glued_section_heads(doc: Doc) -> int:
    """A running head on the line of the next section's title ("220 Book Title The Mixolydian Mode",
    "Chapter 22 Exotic Scales 249 Japanese Scales"): keep the title. The head must carry a page number at one end."""
    fixed = 0
    for s in doc.sections:
        title = re.sub(r"\s*\(p\. [^)]*\)$", "", s.title).strip()
        if s.paras and title and s.paras[0].text.endswith(" " + title):
            head = s.paras[0].text[:-len(title)].strip()
            if re.fullmatch(r"\d{1,4} \D{3,90}|.{3,90}\D \d{1,4}", head) and len(head.split()) >= 2:
                s.paras[0].text = title
                fixed += 1
    return fixed


def strip_running_heads(page: str, keys=frozenset()) -> str:
    """Drop a running header or footer that carries the page number ("4 | Chapter 1: Title", "Section Title | 5")
    when it is the first or last non-blank line of a page. Frequency-based furniture misses these: the number and
    the title change from page to page. A table row has more pipes, so it never matches. `keys` from
    running_head_keys drops the pipe-less kinds at the same places."""
    lines = page.split("\n")
    for i in edge_lines(page):
        if RUNNING_HEAD.match(lines[i].strip()) or head_key(lines[i]) in keys:
            lines[i] = ""
    return "\n".join(lines)


MARGIN_FOLIO_TOKEN = re.compile(r"(?<![\w.,:;/–-])\d{1,4}(?![\w%°/–-]|[.,:]\d)")
MARGIN_FOLIO_BLOCK = re.compile(r"(?:figure|fig\.|table|pages?|pp?\.|chapter|ch\.|section|sec\.|demo|audio|images?|exhibit|lines?|and|to|or|\.{2,}|[,(×=+$])\s*$", re.I)
MARGIN_FOLIO_SHARE = 4   # at least one page in this many must hold its own number in the running text


def margin_folio_shift(pages):
    """The printed-minus-position shift of a page number set in the side margin, which pdftotext drops into the running
    text at that height ("close together in 65 frequency"). Runs after the head and folio passes, so a book whose folios
    sit at the page edges has nothing left to count. None unless one shift clearly leads."""
    count = collections.Counter()
    for n, p in enumerate(pages):
        count.update({int(m.group()) - n for m in MARGIN_FOLIO_TOKEN.finditer(p)})
    top = count.most_common(2)
    if not top or top[0][1] < max(20, len(pages) // MARGIN_FOLIO_SHARE):
        return None
    if len(top) > 1 and top[0][1] < 2 * top[1][1]:
        return None
    return top[0][0]


def strip_margin_folio(page: str, n: int, shift) -> str:
    """Take the page's own number out of the running text, only when it is the one plain occurrence on the page."""
    if shift is None:
        return page
    want = str(n + shift)
    hits = [m for m in MARGIN_FOLIO_TOKEN.finditer(page)
            if m.group() == want and not MARGIN_FOLIO_BLOCK.search(page[max(0, m.start() - 12):m.start()])]
    if len(hits) != 1:
        return page
    before, after = page[:hits[0].start()], page[hits[0].end():]
    if after.startswith(" "):
        after = after[1:]
    elif before.endswith(" "):
        before = before[:-1]
    return before + after


def strip_glued_folio(page: str, n: int, shifts) -> str:
    """Take the page's own number off a caption at the first or last line ("122 Exhibit 4-3", "Exhibit 4-3 122"). Only a
    caption: "122 people came" could be a sentence that happens to start with the page number (L-054 `glued-folio-caption`)."""
    if not shifts:
        return page
    lines = page.split("\n")
    for i in edge_lines(page):
        s = lines[i].strip()
        m = re.fullmatch(r"(\d{1,4})\s+(\S.*)", s)
        num, rest = (m.group(1), m.group(2)) if m else (None, None)
        if not m:
            m = re.fullmatch(r"(\S.*?)\s+(\d{1,4})", s)
            num, rest = (m.group(2), m.group(1)) if m else (None, None)
        if num and int(num) - n in shifts and CAPTION_LINE.match(rest):
            lines[i] = rest
    return "\n".join(lines)


BESIDE_FOLIO_LEAST = 5   # a heading that sits by a page number fewer times than this is still a heading
HEAD_TOP_LINES, HEAD_FOOT_LINES = 4, 3
FOLIO_LINE = re.compile(r"\s*\d{1,4}\s*")


def folio_pairs(page: str) -> list:
    """(index of a bare number line, index of the line beside it) at the top and at the foot of a page, for heads set
    over two lines ("Chapter 9 Title" then "369", "370" then "Part 1 Title")."""
    lines = page.split("\n")
    idx = [i for i, l in enumerate(lines) if l.strip()]
    if len(idx) < 2:
        return []
    out = []
    for a, b in ((idx[0], idx[1]), (idx[-1], idx[-2])):
        for num, other in ((a, b), (b, a)):
            if FOLIO_LINE.fullmatch(lines[num]) and not FOLIO_LINE.fullmatch(lines[other]):
                out.append((num, other))
    return out


def folio_shifts(pages) -> set:
    """Printed number minus page position, for the shifts that hold on many pages: what makes a number a folio and not
    a figure in a table. Several shifts can hold when the numbering jumps."""
    count = collections.Counter()
    for n, p in enumerate(pages):
        lines = p.split("\n")
        count.update({int(lines[i]) - n for i, _ in folio_pairs(p)})
    least = max(BESIDE_FOLIO_LEAST, sum(count.values()) // 10)
    return {s for s, c in count.items() if c >= least}


def beside_folio_keys(pages, shifts) -> set:
    """Keys of lines that sit beside the page's own number on several pages: alternating heads, where the part name
    fills the even pages and "Chapter N Title" the odd ones, so no one text reaches a share of the book. Page after page
    or every other page only: a real heading that recurs is spread out (L-053). A short chapter's head has fewer copies;
    it counts when it keeps the book's own rhythm with a proven head on the pages between (L-054 `short-chapter-heads`)."""
    seen, edge_of, upper = collections.defaultdict(list), collections.defaultdict(set), {}
    beside_at = collections.defaultdict(set)
    for n, p in enumerate(pages):
        lines = p.split("\n")
        idx = [i for i, l in enumerate(lines) if l.strip()]
        for num, other in folio_pairs(p):
            if int(lines[num]) - n in shifts:
                k = line_key(lines[other])
                if not k or len(k) > 90 or k[-1] in ".?!:,;" or len(letters_key(k)) < 3 or CAPTION_LINE.match(k):
                    continue
                if n not in seen[k]:
                    seen[k].append(n)
                edge_of[k].add("top" if min(num, other) == idx[0] else "foot")
                upper[k] = not lines[other].lstrip()[:1].islower()
                beside_at[n].add(k)
    proven = {k for k, w in seen.items() if len(w) >= BESIDE_FOLIO_LEAST and pages_cluster(w)}
    if not proven:
        return proven
    gaps = collections.Counter(b - a for k in proven for a, b in zip(seen[k], seen[k][1:]))
    rhythm = gaps.most_common(1)[0][0]
    edges = collections.Counter(e for k in proven for e in edge_of[k])
    edge = edges.most_common(1)[0][0]
    short = set()
    for k, w in seen.items():
        if k in proven or len(w) < 2 or len(w) >= BESIDE_FOLIO_LEAST or not upper[k] or edge_of[k] != {edge}:
            continue
        if rhythm > 2 or any(b - a != rhythm for a, b in zip(w, w[1:])):
            continue
        if rhythm == 1 or all(beside_at[m] & proven for m in range(w[0] + 1, w[-1], 2)):
            short.add(k)
    return proven | short


def line_key(text: str) -> str:
    return " ".join(text.split()).casefold()   # digits count: "Exhibit 9-3" and "Exhibit 9-4" are two lines


def letters_key(text: str) -> str:
    return re.sub(r"[\W\d_]+", "", text).casefold()


def near_edge(lines: list) -> list:
    """Where a head can land when pdftotext reads a sidebar or an exhibit caption first: the first four and last three
    non-blank lines."""
    idx = [i for i, l in enumerate(lines) if l.strip()]
    return sorted(set(idx[:HEAD_TOP_LINES] + idx[-HEAD_FOOT_LINES:]))


def first_near_edge(pages, keys) -> dict:
    """Head key -> first page it appears on near an edge: a copy there, not beside a number, is the opener."""
    first = {}
    for n, p in enumerate(pages):
        lines = p.split("\n")
        for i in near_edge(lines):
            k = line_key(lines[i])
            if k in keys:
                first.setdefault(k, n)
    return first


def strip_folio_heads(page: str, n: int, shifts, keys, first=None, titles=()) -> str:
    """Drop the page's own number from the top or foot of page `n` (counted from 0), and a recurring head near the
    edge. Stays: a line that matches an outline title of this page, and the first copy in the book unless a number sits
    beside it. Those are the real openers."""
    lines = page.split("\n")
    own = [letters_key(t) for t in titles]
    first = first or {}
    beside, numbers = set(), set()
    for num, other in folio_pairs(page):
        if int(lines[num]) - n in shifts:
            numbers.add(num)
            beside.add(other)
    idx = [i for i, l in enumerate(lines) if l.strip()]
    for pos, i in enumerate(idx):
        if i not in near_edge(lines):
            continue
        k = line_key(lines[i])
        if k not in keys or (i not in beside and first.get(k, n) >= n):
            continue
        text = letters_key(lines[i])
        if any(t and (t in text or text in t) for t in own):
            continue
        numbers.discard(i)
        lines_i = [idx[j] for j in (pos - 1, pos + 1) if 0 <= j < len(idx)]
        numbers.update(j for j in lines_i if FOLIO_LINE.fullmatch(lines[j]) and int(lines[j]) - n in shifts)
        lines[i] = "\0"
    for i in numbers:
        lines[i] = ""
    return "\n".join("" if l == "\0" else l for l in lines)


SENTENCE_END = ".?!:\u201d\""
EXACT: dict = {}   # case-sensitive word counts, for rejoining "Inter viewChain"
COMPOUNDS: dict = {}   # "commaseparated" -> "comma-separated" for hyphenated words printed in the PDF
VOCAB: dict = {}   # word counts of the PDF being read (lower case); empty outside load_pdf
WORD = re.compile(r"[^\W\d_]+")


def keep_break_hyphen(left: str, right: str) -> bool:
    """A U+2010 at a line end is usually a syllable break, but a printed compound ("comma-separated") loses its hyphen
    when rejoined. With the book's word counts: the joined word seen elsewhere means join; both halves real words
    (3+ letters, seen twice) means keep the hyphen."""
    a, b = WORD.findall(left)[-1:], WORD.findall(right)[:1]
    if not VOCAB or not a or not b:
        return False
    a, b = a[0].lower(), b[0].lower()
    if VOCAB.get(a + "-" + b, 0) > VOCAB.get(a + b, 0):
        return True
    if VOCAB.get(a + b, 0) >= 1:
        return False
    return len(a) >= 3 and len(b) >= 3 and VOCAB.get(a, 0) >= 2 and VOCAB.get(b, 0) >= 2


STRAY_HYPHEN = re.compile(r"(?<![\w-])([a-z]+)-([a-z]+)(?![\w-])")
REAL_PREFIXES = {"anti", "co", "de", "multi", "non", "over", "post", "pre", "pro", "re", "self", "semi", "sub", "un"}


def heal_stray_hyphens(sections) -> None:
    """Scanned-then-converted EPUBs keep print line-break hyphens mid-line ("in-formation", "stu-dent"). Join a pair when
    the book prints the joined word at least three times and the hyphenated form at most once or a tenth as often. A real prefix with a real right half
    ("re-sign") stays."""
    paras = [p for s in sections for p in s.paras if p.kind not in ("h", "pre")]
    counts = collections.Counter(w for p in paras for w in re.findall(r"[a-z]+(?:-[a-z]+)*", p.text))

    def fix(m):
        a, b = m.group(1), m.group(2)
        if counts[a + b] < 3 or counts[a + "-" + b] > max(1, counts[a + b] // 10):
            return m.group(0)
        if a in REAL_PREFIXES and counts[b] >= 1:
            return m.group(0)
        return a + b

    for p in paras:
        p.text = STRAY_HYPHEN.sub(fix, p.text)


def rejoin_spaced_words(text: str) -> str:
    """pdftotext sometimes drops a line-end hyphen entirely ("tikto ken"): join two tokens when one half is rare in the
    book (seen at most twice) and the joined word, with the same capitals, appears at least twice. Also put back a
    printed hyphen pdftotext lost ("commaseparated") when the book prints the hyphenated form at least as often."""
    if not VOCAB:
        return text
    def fix(m):
        a, b = m.group(1), m.group(2)
        if a[:1].isupper() and a[1:].islower() and b[:1].isupper():
            return m.group(0)   # two capitalised words: a name ("Shivam Shrirao") or a label, not a split
        if EXACT.get(a + b, 0) >= 2 and min(VOCAB.get(a.lower(), 0), VOCAB.get(b.lower(), 0)) <= 2:
            return a
        return m.group(0)
    text = re.sub(r"(?<![\w-])([^\W\d_]{2,}) (?=([^\W\d_]{2,})(?![\w-]))", fix, text)

    def hyph(m):
        w = m.group(0)
        before, after = text[max(0, m.start() - 1):m.start()], text[m.end():m.end() + 2]
        if w[1:] != w[1:].lower() or before in ("/", ".") or after[:1] in ("/", ".") and after[1:].isalnum():
            return w   # CamelCase names and URL or path parts keep their spelling
        h = COMPOUNDS.get(w.lower())
        if h and VOCAB.get(h, 0) >= VOCAB.get(w.lower(), 0):
            i = h.index("-")
            return w[:i] + "-" + w[i:]
        return w
    return re.sub(r"(?<![\w-])[^\W\d_]{5,}(?![\w-])", hyph, text) if COMPOUNDS else text


CODE_LINE = re.compile(r"[{};]\s*$|^\s*(?:def|class|return|import|from|for|while|if|elif|else|try|except|public|private|"
                       r"static|void|var|let|const|function|async|await|package|#include|#define|SELECT|INSERT)\b|"
                       r"^\s*(?:[}\])]|//|/\*|\*/|#!|>>>|\$ )|\w\([^ ]*\)\s*;?$|^\s*[\w.\[\]]+\s*[-+*/]?=\s*\S|"
                       # a line that is one whole call, spaces inside allowed: print(f"Top hits"), co.rerank(query=q, top_n=3)
                       r"^\s*[\w.]+\(.*\)\s*;?$|"
                       # a Python or shell comment line (# Load the model); a PDF has no Markdown headings to mistake for it
                       r"^\s*# [\w`'\"(]")
PRE_OPEN, PRE_CLOSE = "PRE", "/PRE"   # fences text_paras() turns into a `pre` paragraph (private use:
#                                                  str.strip() eats \x1c-\x1f)
CODE_RUN = 3   # code lines in a row (blank lines allowed) before a stretch is called a code block


def code_blocks(lines: list) -> list:
    """(start, end) line ranges that read as program code: CODE_RUN or more lines in a row matching CODE_LINE, where a
    line between two code lines may be anything short (a lone identifier, a closing word)."""
    out, i, n = [], 0, len(lines)
    while i < n:
        if not lines[i].strip() or not CODE_LINE.search(lines[i]):
            i += 1
            continue
        j, last, hits = i, i, 0
        while j < n:
            t = lines[j]
            if t.strip() and CODE_LINE.search(t):
                hits, last = hits + 1, j
            elif t.strip() and (len(t.split()) > 6 or j - last > 1):
                break
            j += 1
        if hits >= CODE_RUN:
            out.append((i, last + 1))
        i = last + 1
    return out


def mark_code(page: str, layout: str | None) -> str:
    """Fence the code blocks of one page of plain pdftotext output as `pre`, with the lines and indentation
    `pdftotext -layout` kept. The plain mode reads indented lines as flowing text and joins them into the prose
    around them, so blocks are found in the layout page and then located in the plain page by their words
    (L-022 `pdf-code-layout`). A block whose words are not found in order is left as it was."""
    if not layout:
        return page
    lay = [ln.rstrip() for ln in layout.replace("\r", "").split("\n")]
    for a, b in code_blocks(lay):
        body = lay[a:b]
        pad = min(len(x) - len(x.lstrip()) for x in body if x.strip())
        body = [x[pad:] for x in body]
        pat = r"\s+".join(re.escape(t) for t in " ".join(body).split())
        m = re.search(pat, page)
        if m:
            fence = "\n\n" + "\n".join([PRE_OPEN] + body + [PRE_CLOSE]) + "\n\n"
            page = page[:m.start()] + fence + page[m.end():]
    return page


CODE_HINT = re.compile(r"(?m)[{}]\s*$|\bdef \w+\(|\w\([^\s)]*\)\s*[;{:]|^\s*(?:#include|import \w|>>> |from [\w.]+ import \w)")


CAPTION_SPLIT = re.compile(r"(?<=[.!?:\u201d\"])\s+(?=(?:Figure|Table|Example) \d+[-.]\d+\. )")


SPLIT_TAIL_RE = re.compile(r"[.?!][\"”’)]*\s+(?=[\"“‘(]?[A-Z0-9])")


def ends_open(text: str) -> bool:
    """No sentence end at the close of TEXT; a note call after the end mark ('home.1') still closes the sentence."""
    return text[-1:] not in SENTENCE_END and not re.search(r"[.?!:\"”’)]\d{1,3}$", text)


def join_broken(a: str, b: str) -> str:
    """Join text over a break. After an ASCII hyphen the book's own words decide: "dead-" + "lines" loses the hyphen
    when "deadlines" is printed more often than "dead-lines". With neither printed, a left half under 3 letters or
    seen only here is a fragment ("in-evitably", "ver-sion"); anything else keeps its hyphen ("well-documented")."""
    w = WORD.findall(a)[-1:] + WORD.findall(b)[:1]
    if a.endswith("-") and len(w) == 2 and b[:1].islower():
        left, right = w[0].lower(), w[1].lower()
        whole, hyph = VOCAB.get(left + right, 0), VOCAB.get(left + "-" + right, 0)
        if whole > hyph or not whole and not hyph and left not in REAL_PREFIXES and (
                len(left) < 3 and VOCAB.get(right, 0) < 2 or VOCAB.get(left, 0) < 2):
            return a[:-1] + b
    return join_lines([a, b])


UNFOLDED_LINE = 200   # longer than any printed line: pdftotext has already joined this block's lines
UNFOLDED_SHARE = 0.5
BARE_FOLIO = re.compile(r"(?:\d{1,4}|[ivxlc]{1,7})$")


def unfolded_text(pages: list) -> bool:
    """True when most of the text sits on lines no page could print, so each line is a whole paragraph and blank lines
    mean nothing (L-045 `pdf-lines-are-paragraphs`)."""
    lengths = [len(s) for p in pages for s in map(str.strip, p.splitlines()) if s]
    return sum(n for n in lengths if n > UNFOLDED_LINE) >= sum(lengths) * UNFOLDED_SHARE > 0


def unfold_page(page: str) -> str:
    """Give each line of an unfolded page its own paragraph; marked code blocks stay whole, and so does a page with no
    long line (a contents page, a bibliography), whose lines may still be printed ones."""
    if not any(len(s.strip()) > UNFOLDED_LINE for s in page.splitlines()):
        return page
    out, code = [], False
    for line in page.splitlines():
        s = line.strip()
        code = code or s == PRE_OPEN
        out.append(line if code else line + "\n")
        code = code and s != PRE_CLOSE
    return "\n".join(out) + "\n"


FOOT_NOTE = re.compile(r"(\d{1,3})\.\s+(\S.*)$", re.S)


def lift_foot_notes(pp: list, drop_folio: bool = False, nxt: list | None = None) -> list:
    """Take the notes off a page's foot and return them as `[note N: ...]` paragraphs, for the caller to set after the
    paragraph they interrupted. Walking up from the foot, a note is `N. text` with N one below the note under it and a
    call to N (a number straight after a word or a sentence's punctuation) in the body above. Numbered lists have no
    such call and stay; a run that goes on at the top of the next page (NXT) is a list too. A bare folio under the notes goes too, since it would stop the sentence rejoining (L-046 `pdf-foot-notes`)."""
    end = len(pp)
    folio = end > 0 and pp[-1].kind == "p" and bool(BARE_FOLIO.match(pp[-1].text))
    if folio:
        end -= 1
    notes, want = [], None
    i = end - 1
    while i > 0:
        m = FOOT_NOTE.match(pp[i].text) if pp[i].kind == "p" else None
        if not m or (want is not None and int(m.group(1)) != want):
            break
        n = m.group(1)
        call = re.compile(r"(?:[a-z]{3}|[a-zA-Z)][.,;:?!][\"'”’)\]]?|[a-zA-Z.,;:?!][\"”’])" + n + r"(?=[\s.,;:)]|$)")
        if not any(call.search(p.text) for p in pp[:i]):
            break
        notes.insert(0, Para("p", f"[note {n}: {m.group(2)}]"))
        want = int(n) - 1
        i -= 1
    if notes:
        last = int(notes[-1].text[6:].split(":")[0])
        below = FOOT_NOTE.match(nxt[0].text) if nxt else None
        if below and int(below.group(1)) == last + 1:
            notes = []
    if notes:
        del pp[i + 1:]
    elif folio and drop_folio:
        pp.pop()
    return notes


def carry_foot_notes(page_paras: list, foot_notes: list) -> None:
    """A note left open at a page foot goes on over the page, either at the foot of the next page (where it is set) or at
    its top (where some layers put it). Move a lower-case paragraph there into the note, unless the body sentence above
    is open too: then the top paragraph is more likely the body's (L-046 `pdf-foot-notes`)."""
    for n in range(len(page_paras) - 1):
        if not foot_notes[n] or not page_paras[n + 1]:
            continue
        note, nxt = foot_notes[n][-1], page_paras[n + 1]
        inner = note.text[:-1]
        if not (ends_open(inner) or inner[-1:] in "-" + BREAK_HYPHENS):
            continue
        body = page_paras[n][-1].text if page_paras[n] else ""
        foot = len(nxt) - 1
        if foot > 0 and nxt[foot].kind == "p" and BARE_FOLIO.match(nxt[foot].text):
            foot -= 1
        at = None
        if foot > 0 and nxt[foot].kind == "p" and nxt[foot].text[:1].islower() and not ends_open(nxt[foot - 1].text):
            at = foot
        elif nxt[0].kind == "p" and nxt[0].text[:1].islower() and body and not ends_open(body) and body[-1:] not in "-" + BREAK_HYPHENS:
            at = 0
        if at is not None:
            note.text = join_broken(inner, nxt[at].text) + "]"
            nxt.pop(at)


def join_split_pages(page_paras) -> None:
    """A word hyphenated across a page break ("conven-" at the bottom, "tions" at the top of the next), or a sentence
    that runs on (no . ? ! : or closing quote before the break, a lower-case letter after it), becomes one paragraph:
    the next page's first paragraph is moved onto the previous page's last."""
    prev = None
    for pp in page_paras:
        if prev and pp and prev[-1].kind == "p" and pp[0].kind == "p" and (
                prev[-1].text[-1:] in BREAK_HYPHENS and pp[0].text[:1].isalpha()
                or prev[-1].text[-1:] == "-" and pp[0].text[:1].islower()
                or ends_open(prev[-1].text) and pp[0].text[:1].islower()):
            m = SPLIT_TAIL_RE.search(pp[0].text)
            if m and len(pp[0].text[m.end():].split()) >= 20:
                # only the run-on sentence moves; the rest stays on its own page (L-033 `page-join-empties-page`)
                prev[-1].text = join_broken(prev[-1].text, pp[0].text[:m.end()].rstrip())
                pp[0].text = pp[0].text[m.end():].lstrip()
            else:
                prev[-1].text = join_broken(prev[-1].text, pp[0].text)
                pp.pop(0)
        if pp:
            prev = pp


def merge_wrapped(pp, unfolded: bool = False) -> None:
    """Some PDFs come out of pdftotext double-spaced: a blank line after every printed line, so each line became its
    own paragraph and a word hyphenated at a line or column break ("fre-" ... "quency") stayed split (L-030
    `pdf-double-spaced`). Within one page a paragraph is joined to the next (lower case start) when it ends in a
    hyphen or has no sentence end. On a double-spaced page (most paragraphs one line of about the same width) a
    full-width line is joined to the next whatever it ends with: the paragraph went on past the line end."""
    ps = [p for p in pp if p.kind == "p"]
    one = sorted(len(p.text) for p in ps)
    width = one[int(len(one) * 0.8)] if len(one) >= 8 else 0
    double = not unfolded and width >= 40 and sum(width * 0.8 <= len(p.text) <= width * 1.1 for p in ps) >= len(ps) * 0.5
    i = 0
    while i < len(pp) - 1:
        a, b = pp[i], pp[i + 1]
        if a.kind == "p" and b.kind == "p" and (
                b.text[:1].islower() and (a.text[-1:] in "-" + BREAK_HYPHENS or ends_open(a.text))
                or double and width * 0.9 <= len(a.text) <= width * 1.1 and b.text[:1].isalnum()
                and not REPO_MARK.match(b.text) and not LISTING_CAPTION.match(b.text)):
            a.text = join_broken(a.text, b.text)   # "fre-" + "quency": the book prints "frequency" more often
            pp.pop(i + 1)
            continue
        i += 1


CELL_RE = re.compile(r"^\S{1,10}$")   # one table cell on its own line: "0", "0.38", "v(3)"
CELL_RUN = 6   # one-token paragraphs in a row before they are called a table


def collapse_cells(pp) -> None:
    """A PDF table read by pdftotext prints one cell per paragraph ("v(0)", "1", "v(1)", "0", ...). A run of
    CELL_RUN or more one-token paragraphs becomes one row paragraph with the cells separated by " | ", so a table
    takes a few lines instead of dozens (L-031 `pdf-table-cells`; the real layout needs block coordinates, HANDOFF)."""
    i = 0
    while i < len(pp):
        j = i
        while j < len(pp) and pp[j].kind == "p" and CELL_RE.match(pp[j].text):
            j += 1
        if j - i >= CELL_RUN:
            pp[i:j] = [Para("row", " | ".join(p.text for p in pp[i:j]))]
        i += 1


REPO_MARK = re.compile(r"^(?:Repo \d+:\s*\S+\.(?:m|py|c|cpp|js|r|jl)\b\s*)+$", re.I)   # "Repo 2: X.m Repo 3: X.py"
ML_LINE = re.compile(r"^\s*%|;\s*$|^\s*(?:end|function)\b")   # MATLAB comment, statement, block keyword
LISTING_CAPTION = re.compile(r"^(?:Listing|Code) \d+[.-]\d+\b")


def split_listing(lines: list, after_marker: bool) -> tuple:
    """Code printed as plain lines and glued by pdftotext to the caption and prose after it (L-030
    `pdf-listing-glued`): the leading lines of a paragraph that read as code (CODE_LINE, MATLAB comments and
    statements) are split off. After a "Repo N: file.m" marker one code line is enough; elsewhere CODE_RUN in a row.
    Returns (code lines, caption line or None, remaining lines)."""
    k = 0
    while k < len(lines) and (CODE_LINE.search(lines[k]) or ML_LINE.search(lines[k])) \
            and not LISTING_CAPTION.match(lines[k]):
        k += 1
    if k == 0 or (not after_marker and k < CODE_RUN):
        return [], None, lines
    rest = lines[k:]
    cap = rest.pop(0) if rest and LISTING_CAPTION.match(rest[0]) else None
    return lines[:k], cap, rest


def text_paras(text: str, fmt: str) -> list:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    paras, buf = [], []
    fence = False

    def flush():
        if buf and fmt == "txt":
            code, cap, rest = split_listing(buf, bool(paras) and paras[-1].kind == "p"
                                            and bool(REPO_MARK.match(paras[-1].text)))
            if code:
                paras.append(Para("pre", "\n".join(code)))
                if cap:
                    paras.append(Para("p", clean(cap)))
                buf[:] = rest
        if buf:
            t = clean(join_lines(buf))
            if t:
                paras.append(Para("p", t))
            buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s == PRE_OPEN:
            flush()
            j = i + 1
            code = []
            while j < len(lines) and lines[j].strip() != PRE_CLOSE:
                code.append(lines[j].rstrip())
                j += 1
            if code:
                paras.append(Para("pre", "\n".join(code)))
            i = j + 1
            continue
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
            tmp = tmp_cache(cp)
            r = run([tl["pdftotext"], "-enc", "UTF-8", path, str(tmp)])
            if r.returncode != 0 or not tmp.exists():
                tmp.unlink(missing_ok=True)
                raise RWError("pdftotext failed: " + tool_error(r))
            publish_cache(tmp, cp)
        text = cp.read_bytes().decode("utf-8", "replace")
    elif tl["mutool"]:
        cp = cache_path(path, "mutool", ".txt")
        if CACHE_OFF or not cp.exists():
            tmp = tmp_cache(cp)
            r = run([tl["mutool"], "draw", "-q", "-F", "txt", "-o", str(tmp), path])
            if r.returncode != 0 or not tmp.exists():
                tmp.unlink(missing_ok=True)
                raise RWError("mutool failed: " + tool_error(r))
            publish_cache(tmp, cp)
        text = cp.read_bytes().decode("utf-8", "replace")
    else:
        raise RWError("PDF needs pdftotext (poppler-utils; Windows: `choco install poppler` or `scoop install poppler`, "
                      "macOS: `brew install poppler`, Linux: `apt install poppler-utils`) or mutool (MuPDF). "
                      "Nothing was installed. An agent with a Read tool that takes PDF page ranges can read it "
                      "directly instead.")
    oc = ocr_cache(path)
    if oc.exists():   # `rw.py ocr` ran on this scan
        text = oc.read_bytes().decode("utf-8", "replace")
        doc.notes.append(f"text from OCR (`rw.py ocr`, kept in {oc}); expect misread letters")
    text = text.translate(LIGATURES)   # "Diﬃcult": a search for "difficult" must find it
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if oc.exists():
        gap = missing_page_note(pages)
        if gap:
            doc.notes.append(gap)
    shift = printed_offset(pages)
    labels = {} if shift else printed_labels(pages)
    if labels:
        doc.meta["printed_labels"] = labels
        doc.meta["printed_pages"] = (f"numbers found on {len(labels)} of {len(pages)} pages and the offset drifts; "
                                     f"toc shows each page's (p. N), and read --section p{min(labels.values())} reads by printed page")
    if shift:
        doc.meta["page_shift"] = shift
        doc.meta["printed_pages"] = f"PDF page {'+' if shift > 0 else '-'} {abs(shift)} (from the page numbers on the pages)"
    math = pdf_math_fonts(path, tl)
    if math:
        doc.notes.append(math_note(math))
    outline = pdf_outline(path, tl["mutool"], tl["pdfinfo"]) if tl["mutool"] else []
    raw_pages = pages
    on_page = {}
    for t, pg, _ in outline:
        if 1 <= pg <= len(pages):
            on_page.setdefault(pg, []).append(t)
    shifts = folio_shifts(pages)
    beside = beside_folio_keys(pages, shifts)
    first_copy = first_near_edge(pages, beside)
    pages = [strip_folio_heads(p, n, shifts, beside, first_copy, on_page.get(n + 1, ())) for n, p in enumerate(pages)]
    head_keys = running_head_keys(pages, [t for t, _, _ in outline])
    pages = [strip_glued_folio(strip_running_heads(p, head_keys), n, shifts) for n, p in enumerate(pages)]
    pages = strip_colon_heads(pages)
    pages = [repair_symbol_font(p) for p in pages]
    margin = margin_folio_shift(pages)
    pages = [strip_margin_folio(p, n, margin) for n, p in enumerate(pages)]
    if not oc.exists() and CODE_HINT.search(text):   # a cheap gate before a second pdftotext run
        lay = pdf_layout(path, tl)
        pages = [mark_code(p, lay[n] if n < len(lay) else None) for n, p in enumerate(pages)]
    unfolded = not oc.exists() and unfolded_text(pages)
    if unfolded:
        pages = [unfold_page(p) for p in pages]
    VOCAB.clear()
    for w in WORD.findall(text):
        EXACT[w] = EXACT.get(w, 0) + 1
        w = w.lower()
        VOCAB[w] = VOCAB.get(w, 0) + 1
    for h in re.findall(r"(?<![\w-])[^\W\d_]{2,}-[^\W\d_]{2,}(?![\w-])", text):
        h = h.lower()
        COMPOUNDS[h.replace("-", "")] = h
        VOCAB[h] = VOCAB.get(h, 0) + 1
    try:
        page_paras = [text_paras(isolate_headings(p, on_page.get(n, [])), "txt") for n, p in enumerate(pages, 1)]
        foot_notes = [lift_foot_notes(pp, unfolded, page_paras[n + 1] if n + 1 < len(page_paras) else None)
                      for n, pp in enumerate(page_paras)]
        carry_foot_notes(page_paras, foot_notes)
        join_split_pages(page_paras)
        for pp in page_paras:
            collapse_cells(pp)
            merge_wrapped(pp, unfolded)
        for pp in page_paras:
            for i in range(len(pp) - 1, -1, -1):
                if pp[i].kind not in ("h", "pre"):
                    parts = CAPTION_SPLIT.split(rejoin_spaced_words(pp[i].text))
                    pp[i].text = parts[0]
                    pp[i + 1:i + 1] = [Para(pp[i].kind, t) for t in parts[1:]]
    finally:
        VOCAB.clear()
        EXACT.clear()
        COMPOUNDS.clear()
    for pp, notes in zip(page_paras, foot_notes):
        pp.extend(notes)   # the page's last paragraph now holds the sentence the page break cut
    for pp in page_paras:
        for p in pp:
            if p.kind == "h":
                p.kind = "p"
    gone = drop_page_footers(page_paras)
    if gone:
        doc.notes.append(f"dropped {gone} copies of a copyright footer printed on most pages (RW_KEEP_FOOTERS=1 keeps them)")
    doc.furniture = page_furniture(page_paras)
    if outline:
        seen, starts = set(), []
        for t, pg, d in outline:   # outline order is kept within a page; a set lost it (L-015 `same-page-outline-entries`)
            if 1 <= pg <= len(pages) and (pg, t, d) not in seen:
                seen.add((pg, t, d))
                starts.append((pg, t, d))
        starts.sort(key=lambda x: x[0])
        starts = place_on_pages(starts, page_paras)
        starts = run_head_chapters(starts, raw_pages, [sum(len(p.text) for p in pp) for pp in page_paras])
        if starts and starts[0][0] > 1:
            doc.sections.append(Section(f"pages 1-{starts[0][0] - 1}", sum(page_paras[:starts[0][0] - 1], []), 1, "page1"))
        # a section starts at its heading line, not at the top of its page: the page's first lines end the section before
        flat, first = [], []
        for pp in page_paras:
            first.append(len(flat))
            flat += pp
        cuts = [first[pg - 1] + j for pg, _, _, j in starts]
        if doc.sections:
            doc.sections[0].paras = flat[:cuts[0]]
        elif cuts[0]:
            doc.sections.append(Section("page 1 (before the first heading)", flat[:cuts[0]], 1, "page1"))
        for k, (pg, t, d, _) in enumerate(starts):
            end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(pages)
            end = max(end, pg)
            stop = cuts[k + 1] if k + 1 < len(starts) else len(flat)
            doc.sections.append(Section(f"{t} (p. {pg}-{end}{printed_span(pg, end, shift, labels)})",
                                        flat[cuts[k]:stop], d, f"page{pg}"))
    else:
        for n, pp in enumerate(page_paras, 1):
            first = " ".join(pp[0].text[:50].split()) if pp else ""
            lab = f" (p. {labels[n]})" if n in labels else ""
            doc.sections.append(Section(f"page {n}{lab}" + (f": {first}" if first else ""), pp, 1, f"page{n}"))
    fix_chapter_openers(doc)
    fix_glued_section_heads(doc)
    return doc


RUN_HEAD_RE = re.compile(r"﻿?\s*Chapter\s+(\d{1,3})\s*[■|:\-–—]\s*(\S.{0,120})$", re.I)
OPENER_LINE_RE = re.compile(r"﻿?\s*CHAPTER\s+(\d{1,3})\s*$", re.I)


def run_head_chapters(starts: list, raw_pages: list, page_chars: list) -> list:
    """Outline starts [(page, title, depth, para)] plus chapter starts read from running heads such as
    'Chapter 2 | The bpy Module' on each page's first line, added only inside a section that holds over half the
    text and BIG_SECTION_CHARS (the outline stops early; L-027 `pdf-running-head-split`). A chapter starts at its
    'CHAPTER N' opener page, else at the page before its first head when that page has no head, else at the first
    head. Needs CONTENTS_MIN chapters numbered in order; else STARTS comes back unchanged."""
    total = sum(page_chars) or 1
    heads, openers = {}, {}
    for n, t in enumerate(raw_pages, 1):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        if not lines:
            continue
        m = RUN_HEAD_RE.match(lines[0])
        if m:
            heads[n] = (int(m.group(1)), m.group(2).strip())
        m = OPENER_LINE_RE.match(lines[0])
        if m:
            openers[n] = (int(m.group(1)), lines[1] if len(lines) > 1 else "")
    if not heads:
        return starts
    out = list(starts)
    for k, (pg, _, d, _) in enumerate(starts):
        end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(raw_pages)
        chars = sum(page_chars[pg - 1:end])
        if chars <= BIG_SECTION_CHARS or chars <= total // 2:
            continue
        firsts, titles = {}, {}
        for n in range(pg + 1, end + 1):
            if n in heads:
                c, title = heads[n]
                firsts.setdefault(c, n)
                titles.setdefault(c, collections.Counter())[title] += 1
        nums = sorted(firsts)
        if len(nums) < CONTENTS_MIN or nums != list(range(nums[0], nums[0] + len(nums))) \
                or [firsts[c] for c in nums] != sorted(firsts.values()):
            continue
        prev = pg
        for c in nums:
            f = firsts[c]
            op = [n for n in range(prev + 1, f) if openers.get(n, (None,))[0] == c]
            at = op[0] if op else (f - 1 if f - 1 > prev and f - 1 not in heads else f)
            title = titles[c].most_common(1)[0][0]
            if op and 0 < len(openers[op[0]][1]) <= 120:
                title = openers[op[0]][1]
            out.append((at, f"Chapter {c}: {title}", d, 0))
            prev = at
    out.sort(key=lambda x: (x[0], x[3]))
    return out


def pdf_layout(path, tl) -> list:
    """Pages of `pdftotext -layout` output (cached), or [] without pdftotext: used only for the indentation of code."""
    if not tl["pdftotext"]:
        return []
    cp = cache_path(path, "pdftotext-layout", ".txt")
    if CACHE_OFF or not cp.exists():
        tmp = tmp_cache(cp)
        r = run([tl["pdftotext"], "-layout", "-enc", "UTF-8", path, str(tmp)])
        if r.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            return []
        publish_cache(tmp, cp)
    return cp.read_bytes().decode("utf-8", "replace").split("\f")


def isolate_headings(text: str, titles) -> str:
    """Put blank lines around each line (or run of up to three wrapped lines) that spells an outline title, so the
    heading becomes its own paragraph: pdftotext runs a heading into the paragraph above it (L-015). Matching ignores
    case, punctuation and spacing; wrapped heading lines are joined with a space."""
    def key(x):
        return "".join(re.findall(r"[a-z0-9]+", x.lower()))
    want = {key(t) for t in titles if len(key(t)) >= 3}
    if not want:
        return text
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        for span in (1, 2, 3):
            chunk = lines[i:i + span]
            if len(chunk) == span and all(c.strip() for c in chunk) and key(" ".join(chunk)) in want:
                out += ["", " ".join(c.strip() for c in chunk), ""]
                i += span
                break
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def place_on_pages(starts, page_paras) -> list:
    """(page, title, depth, paragraph index) for each outline entry. Entries that share a page are each looked up on
    the whole page and ordered by where their heading sits, so siblings get their own text (L-015); an entry whose
    heading is not found starts where the entry before it does. Titles with spaces lost at a line join take the
    spacing of the heading line on the page ("approachto" -> "approach to", L-015)."""
    out, k = [], 0
    while k < len(starts):
        pg = starts[k][0]
        group = []
        while k < len(starts) and starts[k][0] == pg:
            group.append(starts[k])
            k += 1
        paras = page_paras[pg - 1]
        runin = len(group) > 1
        for _, t, _ in group:   # the first pass may split a run-in heading; the second reads stable indices
            heading_at(paras, t, 0, None, runin)
        found, used = [], set()
        for g, (_, t, _) in enumerate(group):
            j = heading_at(paras, t, 0, None, runin)
            if j is not None and j in used:   # one line carries one heading: look further on
                j = heading_at(paras, t, j + 1, None, runin)
            if j is not None:
                used.add(j)
            found.append((j, g))
        placed, last = [], 0
        for j, g in found:
            if j is not None:
                last = j
            placed.append((j if j is not None else last, g))
        placed.sort()
        for j, g in placed:
            _, t, d = group[g]
            if j < len(paras):
                t = respace_title(t, paras[j].text)
            out.append((pg, t, d, j))
    return out


def respace_title(title: str, line: str) -> str:
    """The title with the spaces of the heading line when the two differ only in spacing (letters kept from the title)."""
    a, b = re.sub(r"\s+", "", title), re.sub(r"\s+", "", line)
    if not a or a.lower() != b.lower() or title == line:
        return title
    out, i = [], 0
    for ch in clean(line):
        if ch == " ":
            out.append(" ")
        else:
            out.append(a[i])
            i += 1
    return "".join(out)


FOOTER_RE = re.compile(r"^\W{0,3}(copyright|\u00a9|\(c\))", re.I)
FOOTER_WORDS_RE = re.compile(r"all rights reserved|may not be (copied|reproduced|scanned|duplicated)|"
                             r"not for (sale|distribution)", re.I)
FOOTER_MAX_WORDS = 150


def drop_page_footers(page_paras, share: float = 0.3, least: int = 5) -> int:
    """Drop a publisher's copyright footer ('Copyright 2013 Cengage Learning. All Rights Reserved. May not be
    copied...') from every page it is printed on, by default: a paragraph that starts with Copyright or (c), says
    'all rights reserved' or 'may not be copied', and recurs (digits folded) on at least `share` of the pages, plus a
    repeated paragraph right after it (the footer's second line). Too long for page_furniture and drop_repeated, it
    ate a tenth of every read (L-037 `per-page-copyright-footer`). RW_KEEP_FOOTERS=1 turns it off. Returns how many
    paragraphs went."""
    if os.environ.get("RW_KEEP_FOOTERS") or len(page_paras) < least:
        return 0
    key = lambda t: re.sub(r"\s+", " ", re.sub(r"\d+", "#", t.lower())).strip()
    count = collections.Counter()
    for pp in page_paras:
        count.update({key(q.text) for q in pp if len(q.text.split()) <= FOOTER_MAX_WORDS})
    need = max(least, share * len(page_paras))
    gone = 0
    for pp in page_paras:
        keep, prev_bad = [], False
        for q in pp:
            k = key(q.text)
            common = count.get(k, 0) >= need and len(q.text.split()) <= FOOTER_MAX_WORDS
            bad = common and (bool(FOOTER_RE.match(q.text) and FOOTER_WORDS_RE.search(q.text)) or prev_bad)
            if bad:
                gone += 1
            else:
                keep.append(q)
            prev_bad = bad
        pp[:] = keep
    return gone


def furniture_key(text: str) -> str:
    return re.sub(r"\d+", "#", clean(text).lower())


def page_furniture(page_paras) -> set:
    """Lines that repeat across pages (footers, bare page numbers, running headers), found by frequency, not by
    wording: a short line on 40% of the pages, or one among a page's top or bottom two lines on 5 or more pages."""
    n = len(page_paras)
    if n < 4:
        return set()
    anywhere, edge = {}, {}
    for pp in page_paras:
        for key in {furniture_key(p.text) for p in pp if len(p.text) <= 120}:
            anywhere[key] = anywhere.get(key, 0) + 1
        for key in {furniture_key(p.text) for p in pp[:2] + pp[-2:] if len(p.text) <= 100}:
            edge[key] = edge.get(key, 0) + 1
    out = {key for key, c in anywhere.items() if c >= max(3, 0.4 * n)}
    out |= {key for key, c in edge.items() if c >= 5}
    return {key for key in out if key.strip()}


def strip_furniture(doc: Doc) -> int:
    """Drop page furniture from every section; returns how many paragraphs went. A section's first paragraph stays:
    it is usually the heading, and a running header repeats exactly that heading. In a PDF with no outline each
    page is a section: there the first paragraph goes too when it repeats the previous page's running head
    (L-024 `page-running-head`)."""
    gone, prev = 0, None
    for s in doc.sections if doc.furniture else []:
        first = s.paras[:1]
        key = furniture_key(first[0].text) if first else None
        if re.match(r"page \d+", s.title):
            if key in doc.furniture and prev is not None and prev.startswith(key):
                first = []
            prev = key
        keep = first + [p for p in s.paras[1:] if furniture_key(p.text) not in doc.furniture]
        gone += len(s.paras) - len(keep)
        s.paras = keep
    return gone


IN_SECTION_MAX_WORDS, IN_SECTION_LEAST = 8, 10   # a short line repeated this often inside one section is a back-link or marker
REPEAT_MAX_WORDS = 40   # only short paragraphs (credit lines, captions, notices) can count as repeated boilerplate


def repeat_keys(text: str) -> list:
    """Keys a short paragraph is compared by: its whole text and its last four words, lower-cased with digits folded,
    so "Film A. Directed by X. Studio, 1999. All Rights Reserved." and the same line for another film share a key."""
    w = re.findall(r"[a-z#]+", re.sub(r"\d+", "#", text.lower()))
    if not w or len(w) > REPEAT_MAX_WORDS:
        return []
    keys = ["all:" + " ".join(w)]
    if len(w) >= 6:
        keys.append("end:" + " ".join(w[-4:]))
    return keys


def fix_chapter_openers(doc: Doc) -> int:
    """PDF chapters of a numbered book: a drop-cap chapter number lands inside the first words ("1Text Su6mmarization"),
    and a running head joins the next paragraph ("8.3 Scorer 155 and return"). Restore the title and cut the heads,
    only where the numbers match the section's own chapter. Returns how many paragraphs changed."""
    fixed = 0
    word = r"(?:[A-Z][\w'-]*|of|and|the|for|in|on|a|an|to|with)"
    for s in doc.sections:
        m = re.match(r"(\d+)\.\s+(\S.*)", s.title)
        if not m:
            continue
        ch, title = m.group(1), re.sub(r"\s*\(p\. [^)]*\)$", "", m.group(2))
        want = re.sub(r"\s", "", title).lower()
        if s.paras:
            t, got, end = s.paras[0].text, "", 0
            for end, c in enumerate(t, 1):
                if not c.isspace() and not c.isdigit():
                    got += c.lower()
                if len(got) == len(want):
                    break
            if got == want and any(c.isdigit() for c in t[:end]):
                s.paras[0].text = title + t[end:]
                fixed += 1
        heads = re.compile(rf"(?:{ch}\.\d+ {word}(?: {word})* \d{{1,4}}|\d{{1,4}} Chapter {ch} {re.escape(title)})(?: |$)")
        keep = []
        for p in s.paras:
            cut = heads.match(p.text)
            if cut:
                p.text = p.text[cut.end():]
                fixed += 1
                if not p.text.strip():
                    continue
            keep.append(p)
        s.paras = keep
    return fixed


def strip_glued_heads(doc: Doc, least: int = 5, max_words: int = 8) -> int:
    """Remove a running head glued to the first line of a PDF page ("Chapter 5 X Equalization patched between..."),
    and join the sentence it split back onto the paragraph before. A head is a short paragraph that also stands alone
    `least` times or more; it counts as glued only when lower-case text follows it. Returns how many went."""
    count = {}
    for s in doc.sections:
        for p in s.paras[1:]:
            if p.kind != "h" and len(p.text.split()) <= max_words:
                count[p.text.strip()] = count.get(p.text.strip(), 0) + 1
    heads = sorted((t for t, c in count.items() if c >= least and len(t.split()) >= 2), key=len, reverse=True)
    if not heads:
        return 0
    gone = 0
    for s in doc.sections:
        keep = s.paras[:1]
        for p in s.paras[1:]:
            head = next((h for h in heads if p.kind != "h" and p.text.startswith(h + " ")
                         and p.text[len(h) + 1:1 + len(h) + 1].islower()), None)
            if head is None:
                keep.append(p)
                continue
            gone += 1
            p.text = p.text[len(head) + 1:]
            prev = keep[-1] if len(keep) > 1 else None
            if prev is not None and prev.kind == "p" and prev.text.rstrip()[-1:] not in ".?!:;\"\u201d":
                prev.text = prev.text.rstrip() + " " + p.text
            else:
                keep.append(p)
        s.paras = keep
    return gone


def drop_repeated(doc: Doc, share: float = 0.3, least: int = 5) -> int:
    """Drop short paragraphs that recur, verbatim or with the same last four words, in at least `share` of the
    sections that have text (and at least `least` sections), or a line of at most eight words repeated verbatim ten
    times or more inside one section, a quarter of its paragraphs (endnote back-links). A section's first paragraph (its heading) stays.
    Returns how many paragraphs went."""
    secs = [s for s in doc.sections if s.words()]
    seen = {}
    for k, s in enumerate(secs):
        for p in s.paras[1:]:
            if p.kind != "h":
                for key in repeat_keys(p.text):
                    seen.setdefault(key, set()).add(k)
    need = max(least, share * len(secs))
    bad = {key for key, ks in seen.items() if len(ks) >= need}
    for s in secs:   # a back-link line after every endnote ("GO TO NOTE REFERENCE IN TEXT") recurs inside one section
        body = [p for p in s.paras[1:] if p.kind != "h"]
        count = {}
        for p in body:
            if len(p.text.split()) <= IN_SECTION_MAX_WORDS:
                for key in repeat_keys(p.text)[:1]:
                    count[key] = count.get(key, 0) + 1
        bad.update(key for key, c in count.items() if c >= IN_SECTION_LEAST and c >= 0.25 * len(body))
    gone = 0
    for s in secs if bad else []:
        keep = s.paras[:1] + [p for p in s.paras[1:] if p.kind == "h" or not bad.intersection(repeat_keys(p.text))]
        gone += len(s.paras) - len(keep)
        s.paras = keep
    return gone


EPIGRAPH_MAX_WORDS = 80   # a quotation epigraph is short
ATTRIB_MAX_WORDS = 8      # and its attribution is a name
QUOTED_RE = re.compile(r'^\s*["\u201c\u201e\u00ab].*["\u201d\u00bb]\s*$', re.S)
ATTRIB_RE = re.compile(r"^\s*(\u2014|\u2013|--)\s*\S")


IMAGE_MARKER = re.compile(r"\s*\[image omitted[^\]]*\]")


def drop_short_paras(doc: Doc, least: int) -> int:
    """Remove body paragraphs under `least` words: figure labels and music-notation debris in OCR text. Headings,
    code and table paragraphs stay. Returns how many went."""
    gone = 0
    for s in doc.sections:
        kept = [p for p in s.paras if p.kind != "p" or len(p.text.split()) >= least]
        gone += len(s.paras) - len(kept)
        s.paras = kept
    return gone


def drop_images(doc: Doc) -> int:
    """Remove `[image omitted: NAME]` markers; a paragraph holding nothing else goes. `[image: ALT]` stays, since it
    carries words. Returns how many markers went."""
    gone = 0
    for s in doc.sections:
        kept = []
        for p in s.paras:
            text, n = IMAGE_MARKER.subn("", p.text)
            gone += n
            if n:
                p.text = text.strip()
            if p.text or not n:
                kept.append(p)
        s.paras = kept
    return gone


def drop_epigraphs(doc: Doc) -> int:
    """Drop quotation epigraphs: a paragraph of at most EPIGRAPH_MAX_WORDS wholly in quotation marks (straight or
    curly) followed at once by an attribution of at most ATTRIB_MAX_WORDS starting with an em dash, en dash or `--`.
    Both go; a quotation without an attribution line stays. Returns how many paragraphs went."""
    gone = 0
    for s in doc.sections:
        keep, ps, i = [], s.paras, 0
        while i < len(ps):
            p, q = ps[i], ps[i + 1] if i + 1 < len(ps) else None
            if (q is not None and p.kind != "h" and q.kind != "h" and QUOTED_RE.match(p.text)
                    and len(p.text.split()) <= EPIGRAPH_MAX_WORDS and ATTRIB_RE.match(q.text)
                    and len(ATTRIB_RE.sub("x", q.text, 1).split()) <= ATTRIB_MAX_WORDS):
                gone += 2
                i += 2
                continue
            keep.append(p)
            i += 1
        s.paras = keep
    return gone


def heading_at(paras, title, lo=0, missing=-1, runin=False) -> int:
    """Index of the paragraph on a page that carries an outline title (from lo on); lo when none matches.
    A numbered title run into a paragraph ("... checklist. 10.2.1 Signs of Life To know ...") splits that paragraph in place.
    runin (several entries share the page): an unnumbered title of two or more words, in its exact case right after a
    sentence end ("... received. Mark Mangini (supervising ..."), splits too (L-073 `same-page-runin-titles`)."""
    def norm(x):
        return " ".join(re.findall(r"[a-z0-9]+", x.lower()))
    t = norm(re.sub(r"^\s*(chapter\s+)?[\divxlc]+(\.\d+)*\.?\s+", "", title, flags=re.I)) or norm(title)
    if missing == -1:
        missing = lo
    if len(t) < 3:
        return missing
    for j in range(lo, len(paras)):
        q = norm(paras[j].text)
        if t in q and len(q) <= len(t) + 40:
            return j
    tn = t.replace(" ", "")
    for j in range(lo, len(paras)):   # spaces lost or moved at a line join in the outline ("approachto", L-015)
        q = norm(paras[j].text).replace(" ", "")
        if tn in q and len(q) <= len(tn) + 35:
            return j
    if re.match(r"\s*\d+(\.\d+)+\s", title):  # only a numbered title is safe to find inside running text
        rx = re.compile(r"\s+".join(re.escape(w) for w in title.split()), re.I)  # headings are often in capitals
        for j in range(lo, len(paras)):
            m = rx.search(paras[j].text)
            if m and m.start() > 0:
                p = paras[j]
                paras[j:j + 1] = [Para(p.kind, p.text[:m.start()].rstrip(), p.level), Para(p.kind, p.text[m.start():], p.level)]
                return j + 1
            if m:
                return j
    elif runin and len(title.split()) >= 2:
        rx = re.compile(r"(?:^|(?<=[.!?:;\u201d\")]\s))" + r"\s+".join(re.escape(w) for w in title.split()) + r"\b")
        for j in range(lo, len(paras)):
            m = rx.search(paras[j].text)
            if m and m.start() > 0:
                p = paras[j]
                paras[j:j + 1] = [Para(p.kind, p.text[:m.start()].rstrip(), p.level), Para(p.kind, p.text[m.start():], p.level)]
                return j + 1
            if m:
                return j
    return missing


def pdf_outline(path, mutool, pdfinfo=None) -> list:
    """(title, page, depth) from `mutool show FILE outline`; best effort, empty on any surprise.
    LaTeX PDFs link most entries by name, so pdfinfo -dests supplies their pages (L-061 `outline-named-dests`)."""
    try:
        r = run([mutool, "show", path, "outline"], 60)
    except RWError:
        return []
    text = r.stdout.decode("utf-8", "replace")
    dests = {}
    if pdfinfo and "#nameddest=" in text:
        try:
            d = run([pdfinfo, "-dests", path], 120)
            dests = parse_dests(d.stdout.decode("utf-8", "replace"))
        except RWError:
            pass
    return parse_outline(text, dests)


def parse_dests(text: str) -> dict:
    """{name: page} from `pdfinfo -dests`: page, a bracketed destination, then the quoted name."""
    out = {}
    for line in text.splitlines():
        m = re.match(r'^\s*(\d+)\s+\[.*\]\s+"(.*)"\s*$', line)
        if m:
            out[m.group(2)] = int(m.group(1))
    return out


def parse_outline(text: str, dests=None) -> list:
    dests = dests or {}
    out = []
    # MuPDF 1.23: a marker (| leaf, + closed, - open), one tab per level, the quoted title, a tab, then
    # #page=N&zoom=... (checked on real files, L-005). Older builds indented with spaces.
    # A named destination reads #nameddest=NAME instead of a page; dests gives its page.
    for line in text.splitlines():
        n = re.match(r'^(.*"\s+)#nameddest=(\S+)\s*$', line)
        if n:   # MuPDF percent-encodes the name (InDesign 'Book.indd%3APage%201%3A3914'); pdfinfo prints it plain (L-076)
            name = n.group(2) if n.group(2) in dests else unquote(n.group(2))
            if name in dests:
                line = f"{n.group(1)}#page={dests[name]}"
        m = re.match(r'^( *)[|+\-]?(\t*) *"(.*)"\s+#?(?:page=)?(\d+)', line)
        if m:
            # MuPDF escapes quotes and backslashes (L-015) and writes a line break in a title as \r or \n
            title = re.sub(r'\\(["\\rnt])', lambda e: e.group(1) if e.group(1) in '"\\' else " ", m.group(3))
            title = " ".join(title.translate(LIGATURES).split())
            out.append((title, int(m.group(4)), max(1, len(m.group(2))) + len(m.group(1)) // 2))
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
        tmp = tmp_cache(out)
        r = run([exe, path, str(tmp)], 900)
        if r.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            err = (r.stdout + r.stderr).decode("utf-8", "replace")
            if "DRM" in err:
                raise RWError("calibre reports this book is DRM-protected. readwright does not remove DRM.")
            raise RWError("ebook-convert failed: " + tool_error(r))
        publish_cache(tmp, out)
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
                tmp = tmp_cache(out)
                shutil.copyfile(made, tmp)
                publish_cache(tmp, out)
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
    tmp = tmp_cache(cp)
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
            tmp.unlink(missing_ok=True)
            hint = " (markitdown reads most formats only with its extras: `markitdown[all]`)" \
                if via == "markitdown" and b"MissingDependency" in r.stderr else ""
            raise RWError(f"{via} failed on {Path(path).name}: {tool_error(r)}{hint}")
        publish_cache(tmp, cp)
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


CAPS_ACRONYM_USES = 2     # a one-word caps run seen this often inside sentences is a name
CAPS_RUN_MAX = 8          # a longer all-caps stretch is a caps paragraph (credits, a shouted line), not a heading
CREDIT_PARA_WORDS = 150   # a caps run closing a paragraph this short is a credit; OCR page paragraphs run longer
CAPS_SPLIT_MIN = 3        # fewer headings than this and a big section is left whole


def caps_token(t: str) -> bool:
    return not re.search(r"[a-z]", t) and bool(re.search(r"[A-Z]", t))


def letters(ws) -> int:
    return sum(len(re.sub(r"[^A-Z]", "", w)) for w in ws)


def caps_runs(words: list) -> list:
    """(start, end) word ranges of ALL-CAPS runs; '&' and dashes may sit inside one; one-letter words ('A', 'I')
    and bare numbers at either end are not part of it."""
    runs, i, n = [], 0, len(words)
    while i < n:
        if not caps_token(words[i]):
            i += 1
            continue
        j = i
        while j < n and (caps_token(words[j]) or words[j] in ("&", "-", "\u2014")):
            j += 1
        a, b = i, j
        while a < b and (letters([words[a]]) < 2 or not caps_token(words[a])):
            a += 1
        while b > a and (letters([words[b - 1]]) < 2 or not caps_token(words[b - 1])):
            b -= 1
        if b > a and letters(words[a:b]) >= 4:
            runs.append((a, b))
        i = j
    return runs


def caps_key(ws) -> str:
    return " ".join(ws).strip(" ,.:;")


def split_caps(s: Section, pages: int = 0) -> list | None:
    """Sections for one huge section whose headings sit inline in ALL CAPS, the way calibre turns a DjVu's OCR text
    into a few hundred page-long paragraphs ('TRIPLE-TAKE TECHNIQUE The simplest method ...', L-021
    `inline-caps-headings`). An ALL-CAPS phrase repeated on many pages is a running head: the book's title when it
    runs through most of the book (dropped), else a chapter name (a level-1 section from its first page; dropped
    elsewhere). Heads are counted near paragraph starts only and stripped from the front of a caps run. Any other caps run of 1-8 words (one word only when it is six letters or more) after a paragraph
    start or a sentence end, and before a capital letter or the paragraph's end, is a topic heading (level 2).
    None when fewer than CAPS_SPLIT_MIN headings turn up."""
    paras = [p for p in s.paras if p.kind in ("p", "h", "li", "quote")]
    if len(paras) < len(s.paras) or not paras:
        return None
    words = [p.text.split() for p in paras]
    runs = [caps_runs(w) for w in words]
    count = collections.Counter()
    for w, rs in zip(words, runs):
        for a, b in rs:   # running heads open a page, and a page is a paragraph or starts one
            if a <= 3:
                count.update(tuple(w[a:a + k]) for k in range(1, min(b - a, 5) + 1))
    least = max(5, (pages or len(paras)) // 40)   # a running head is on most pages of its chapter
    freq = {k for k, c in count.items() if c >= least and letters(k) >= 4}
    freq = {k for k in freq if not any(count[k[:j]] >= least and count[k[j:]] >= least
                                       for j in range(1, len(k)))}   # two heads side by side
    heads = {k for k in freq if not any(len(q) > len(k) and count[q] >= 0.7 * count[k] and q[:len(k)] == k
                                        for q in freq)
             and not any(count[k] < 0.7 * count[k[:j]] for j in range(1, len(k)))}   # a head plus a topic
    acronym = collections.Counter(x.strip(".,:;()") for w in words for x in w[1:-1])
    hits = collections.defaultdict(list)     # head -> paragraph indexes
    plan = []                                 # per paragraph: [(a, b, kind, key)], kind 'rh' or 'topic'
    for i, (w, rs) in enumerate(zip(words, runs)):
        items = []
        for a, b in rs:
            lead = []
            while a < b:
                k = next((tuple(w[a:a + n]) for n in range(min(b - a, 5), 0, -1) if tuple(w[a:a + n]) in heads), None)
                if not k:
                    break
                lead.append((a, a + len(k), "rh", caps_key(k)))
                a += len(k)
            items += lead
            if b > a:
                before = w[a - 1] if a else ""
                after = w[b] if b < len(w) else ""
                one = b - a == 1
                if b - a > CAPS_RUN_MAX:
                    continue
                if a and not after and b - a <= 4 and len(w) <= CREDIT_PARA_WORDS:
                    continue   # the end of a short caption: a photo credit, not a heading (L-071 `caption-credit-heading`)
                if w[b - 1][-1:] == ",":
                    continue   # a list running on: 'DEC, IBM, Hewlett-Packard' (L-064 `caps-list-acronym`)
                if one and acronym[w[a].strip(".,:;")] >= CAPS_ACRONYM_USES:
                    continue   # also used mid-sentence: a name (FORTRAN, ILLIAC), not a heading
                if (not before or lead or before[-1:] in SENTENCE_END + ")\u2019") \
                        and (not after or after[:1].isupper() or after[:1] in "\"\u201c'(") \
                        and (not one or re.fullmatch(r"[A-Z]{6,}", w[a].strip(".,:;"))):
                    items.append((a, b, "topic", caps_key(w[a:b])))
        for a, b, kind, key in items:
            if kind == "rh" and a <= 3:
                hits[key].append(i)
        plan.append(items)
    n = len(paras)
    chapters = {}
    window = 15 * n / (pages or n)   # 15 pages, in paragraphs
    for k, v in hits.items():   # stray hits (an index, a cross-reference) must not stretch a chapter
        if len(v) >= 3 and v[len(v) * 9 // 10] - v[len(v) // 10] < 0.6 * n:
            first = next((h for j, h in enumerate(v) if sum(1 for x in v[j:] if x - h <= window) >= 3), None)
            if first is not None:
                chapters[k] = first
    # a topic head that runs on the facing pages of a chapter (ACTION AXIS inside CONTINUITY) has its span inside
    # that chapter's span; chapters follow one another and never nest
    # a topic head that runs on the facing pages of a chapter (ACTION AXIS inside CONTINUITY in an OCR'd film book)
    # starts while that chapter's own running head is still on most pages: chapters follow one another, never nest
    kept = []
    for k in sorted(chapters, key=chapters.get):
        v = [h for h in hits[k] if h >= chapters[k]]
        mid = v[len(v) // 2]
        if kept and sum(1 for h in hits[kept[-1]] if chapters[k] <= h <= mid) >= 3:
            continue
        kept.append(k)
    chapters = {k: chapters[k] for k in kept}
    starts = {(v, k) for k, v in chapters.items()}
    topics = sum(1 for items in plan for x in items if x[2] == "topic")
    if len(starts) + topics < CAPS_SPLIT_MIN:
        return None
    sub = s.level + (1 if chapters else 0)
    out = [Section(s.title, [], s.level, s.sid)]
    cur_topic = None
    for i, (w, items) in enumerate(zip(words, plan)):
        pieces, last = [], 0
        for a, b, kind, key in items:
            pieces.append((w[last:a], None))
            if kind == "topic" or (i, key) in starts:
                pieces.append(([], (kind, key)))
                starts.discard((i, key))
            last = b
        pieces.append((w[last:], None))
        for ws, cut in pieces:
            if cut:
                kind, key = cut
                if kind == "topic" and key == cur_topic:
                    continue   # the same heading repeated on the next page
                cur_topic = key if kind == "topic" else None
                level = s.level if kind == "rh" else sub
                out.append(Section(key, [Para("h", key, level - s.level + 1)], level, f"{s.sid}@p{i + 1}"))
            elif ws:
                out[-1].paras.append(Para(paras[i].kind, " ".join(ws)))
    seen = collections.Counter()
    for x in out[1:]:
        seen[x.sid] += 1
        if seen[x.sid] > 1:
            x.sid += f".{seen[x.sid]}"
    return [x for x in out if x.paras]


def contents_entry(s: Section, j: int, cuts: list) -> bool:
    """True when the heading-like line at J is a line of a printed contents page, not the heading: the same opening
    word is a later cut too, and the lines beside it are short (the contents list) rather than prose (L-039
    `epub-oneline-contents`: 'INTRODUCTION' and 'EPILOGUE: ...' on an EPUB's contents page opened false sections)."""
    key = lambda k: (s.paras[k].text.split() or [""])[0].strip(":.").lower()   # 'EPILOGUE: ...' then 'EPILOGUE'
    if not any(k > j and key(k) == key(j) for k in cuts):
        return False
    near = s.paras[max(0, j - 2):j] + s.paras[j + 1:j + 3]
    return len(near) >= 2 and all(len(p.text.split()) <= 12 for p in near)


def contents_page(s: Section, cuts: list) -> bool:
    """True when an untitled block is a printed contents page and none of its lines opens a chapter (L-070
    `contents-page-survivors`): nearly every line is short, and it names itself or `contents_entry` already
    rejected several lines. The entries that repeat nothing ('Introduction', the last 'Chapter 9') survive that test."""
    if len(s.paras) < 12 or sum(len(p.text.split()) <= 12 for p in s.paras) < 0.9 * len(s.paras):
        return False
    named = any(re.fullmatch(r"(table of )?contents", p.text.strip(), re.I) for p in s.paras[:3])
    return named or len(cuts) >= 3


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
            kept = [j for j in cuts if not contents_entry(s, j, cuts)]
            cuts = [] if untitled_ and contents_page(s, [j for j in cuts if j not in kept]) else kept
        if len(cuts) < (1 if untitled_ else 2):
            parts = split_caps(s) if s.words() > BIG_SECTION else None
            out.extend(parts or [s])
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


RUNNING_HEAD_NUM = (re.compile(r"(\d{1,4})\s+([^a-z\d]{3,60})"), re.compile(r"([^a-z]{3,80}?)\s+(\d{1,4})"))
HEAD_NUM_MIXED = (re.compile(r"(\d{1,4})\s+([A-Z][^.!?]{2,80})"), re.compile(r"[A-Z][^.!?]{2,80}?\s(\d{1,4})"))
FOOTER_NUM = re.compile(r"(?:©|\(c\)|copyright).{0,80}?\s(\d{1,4})", re.I)


def printed_labels(pages: list) -> dict:
    """Printed page number of each PDF page {pdf page: printed}, for books whose offset drifts (a dropped blank page
    per chapter) so printed_offset finds no single shift (L-034 `printed-page-drift`). Reads bare numbers, numbers
    beside an upper-case running head ('154 A. STYHRE', 'IN THE VENTURE CAPITAL MARKET 155') and a copyright footer
    ending in a number; keeps a number only when a page within three has the same offset, then fills the pages
    between two anchors of one offset. {} when fewer than five pages agree."""
    cand = {}
    for n, t in enumerate(pages, 1):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        vs = set()
        for ln in lines[:2] + lines[-4:]:   # a chapter opener's number sits above a two-line DOI footer
            if re.fullmatch(r"\d{1,4}", ln):
                vs.add(int(ln))
                continue
            m = RUNNING_HEAD_NUM[0].fullmatch(ln)
            if m and re.search(r"[A-Z]{2}", m.group(2)):
                vs.add(int(m.group(1)))
            m = RUNNING_HEAD_NUM[1].fullmatch(ln)
            if m and re.search(r"[A-Z]{2}", m.group(1)):
                vs.add(int(m.group(2)))
            m = FOOTER_NUM.fullmatch(ln)
            if m:
                vs.add(int(m.group(1)))
        if lines:   # a mixed-case running head on the top line: '130 PART 2 Fundamentals', 'Chapter 6 Prices 131'
            m = HEAD_NUM_MIXED[0].fullmatch(lines[0]) or HEAD_NUM_MIXED[1].fullmatch(lines[0])
            if m:
                vs.add(int(m.group(1)))
        cand[n] = vs
    labels = {}
    for n, vs in cand.items():
        for v in sorted(vs):
            if v < 1 or v > n + 60:
                continue
            if any(w - m == v - n for m in range(n - 3, n + 4) if m != n for w in cand.get(m, ())):
                labels[n] = v
                break
    keys = sorted(labels)
    for a, b in zip(keys, keys[1:]):
        if labels[a] - a == labels[b] - b:
            for m in range(a + 1, b):
                labels[m] = m + labels[a] - a
    return labels if len(keys) >= 5 else {}


def printed_span(first: int, last: int, shift: int, labels: dict) -> str:
    """', printed 129-134' after an outline section's PDF pages, so an outline title gives the page a reader of the
    printed book cites (L-035 `outline-printed-pages`); '' when the book has no printed numbers."""
    if not (shift or labels):
        return ""
    a = labels.get(first, first + shift if shift else None)
    b = labels.get(last, last + shift if shift else None)
    if not a or a < 1:
        return ""
    return f", printed {a}" + (f"-{b}" if b and b > a else "")


MATH_FONT_RE = re.compile(r"MathematicalPi|MathPi|Universal-?(Greek|News)", re.I)


def pdf_math_fonts(path: str, tl: dict) -> list:
    """Names of symbol fonts with a known broken text map (Linotype Mathematical Pi, Universal Greek/News), from
    pdffonts, cached: pdftotext reads their '=' '+' '-' 'x' as '5' '1' '2' '3' (L-036 `symbol-font-math`).
    [] when pdffonts is missing."""
    if not tl.get("pdffonts"):
        return []
    cp = cache_path(path, "pdffonts", ".txt")
    if not cp.exists():
        r = run([tl["pdffonts"], path], 180)
        tmp = tmp_cache(cp)
        tmp.write_bytes(r.stdout)
        publish_cache(tmp, cp)
    names = [ln.split()[0] for ln in cp.read_bytes().decode("utf-8", "replace").splitlines()[2:] if ln.strip()]
    return sorted({re.sub(r"^[A-Z]{6}[+]", "", n) for n in names if MATH_FONT_RE.search(n)})


def math_note(fonts: list) -> str:
    return (f"math symbols are likely garbled: the PDF sets them in {', '.join(fonts[:3])}, a symbol font whose text "
            "map is wrong, so '=' reads as '5', '+' as '1', '-' (minus) as '2', 'x' (times) as '3', and fraction bars "
            "come out as underscores; check formulas against the page image or a second source")


def printed_offset(pages: list) -> int:
    """Printed page number minus PDF page number, from bare numbers in each page's first or last lines; 0 when
    they agree or too few pages say (L-019 `printed-page-offset`)."""
    votes = collections.Counter()
    for n, t in enumerate(pages, 1):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        nums = {int(ln) for ln in lines[:2] + lines[-2:] if re.fullmatch(r"\d{1,4}", ln)}
        for v in nums:
            votes[v - n] += 1
    if not votes:
        return 0
    shift, k = votes.most_common(1)[0]
    return shift if k >= 5 and k * 2 >= sum(votes.values()) else 0


CONTENTS_MIN = 3   # chapters from the printed contents that must turn up, in order, before a giant section is split


def contents_chapters(doc: Doc, listed=None) -> list:
    """(number, title, where) from a printed contents page laid out as a bare chapter number, the title (one to
    three lines) and its page number, the way pdftotext reads a Packt-style contents page ('1' / 'Understanding
    Prompting' / '3'). Numbers must run 1, 2, 3... (one may be skipped when LISTED has it); `where` is (section index, paragraph index) of the entry."""
    out, want, at = [], 1, (0, 0)
    while True:
        got = contents_run(doc, want, at)
        out += got
        if got:
            want, at = got[-1][0] + 1, got[-1][3]
        if not out or not listed or want not in listed:
            return out
        want += 1   # the contents page lost this chapter; the 'Chapter N, Title' list has it


def contents_run(doc: Doc, want: int, at: tuple) -> list:
    """Entries numbered WANT, WANT+1, ... in order from position AT on (see contents_chapters)."""
    out = []
    for si, s in enumerate(doc.sections):
        ps = s.paras
        for j, p in enumerate(ps):
            if (si, j) < at or p.text.strip() != str(want) or j + 1 >= len(ps):
                continue
            title = ps[j + 1].text.strip()
            if not re.match(r"[^\W\d_]", title) or len(title.split()) > 15 or re.search(r"\s\d{1,4}$", title):
                continue   # a section entry with its page number on the same line, not a chapter title
            k = j + 2
            while k < len(ps) and k < j + 4 and not re.fullmatch(r"\d{1,4}", ps[k].text.strip()) \
                    and len((title + " " + ps[k].text).split()) <= 15:
                title += " " + ps[k].text.strip()
                k += 1
            if k >= len(ps) or not re.fullmatch(r"\d{1,4}", ps[k].text.strip()):
                title, k = ps[j + 1].text.strip(), j + 1   # no page number after it: keep the one line
            out.append((want, title, ps[j + 1].text.strip(), (si, k)))
            want += 1
    return out


OPENER_RE = re.compile(r"\bChapter (\d{1,3}), (.{3,160}?)(?=\s+[•●*]|\s+Chapter \d|\.\s|$)")


def listed_chapters(doc: Doc) -> dict:
    """{number: title} from 'Chapter 6, Applications of LLMs...' lists (part openers, 'What this book covers')."""
    out = {}
    for s in doc.sections:
        for p in s.paras:
            for m in OPENER_RE.finditer(p.text):
                out.setdefault(int(m.group(1)), m.group(2).strip())
    return out


ONELINE_RE = re.compile(r"(\d{1,3})[\s.:\u2002-\u200b\ufffd]+([^\W\d_].{1,100})")


def oneline_contents(doc: Doc) -> list:
    """(number, title, title, where) from a printed contents page with each chapter on one line ('1 INTENTIONAL
    SUCCESS', '2 ...'), the way an EPUB's contents page reads: CONTENTS_MIN or more paragraphs in a row numbered
    1, 2, 3... with no page number at the end (L-039 `epub-oneline-contents`). The first such run wins."""
    for si, s in enumerate(doc.sections):
        run = []
        for j, p in enumerate(s.paras + [Para("p", "")]):
            m = ONELINE_RE.fullmatch(p.text.strip())
            if m and int(m.group(1)) == len(run) + 1 and len(m.group(2).split()) <= 15 \
                    and not re.search(r"\s\d{1,4}$", m.group(2)):
                run.append((len(run) + 1, m.group(2).strip(), m.group(2).strip(), (si, j)))
                continue
            if len(run) >= CONTENTS_MIN:
                return run
            run = [(1, m.group(2).strip(), m.group(2).strip(), (si, j))] if m and m.group(1) == "1" else []
    return []


def chapter_list(doc: Doc) -> list:
    """(number, [titles to try], where) for chapters 1, 2, 3...: titles from the printed contents page first, then
    from 'Chapter N, Title' lists, since pdftotext can scramble a two-column contents page. One gap is allowed.
    A one-line-per-chapter contents page (EPUB) comes first: the two-line reader would take the body's own
    chapter openers ('1' then 'TITLE') for contents entries."""
    listed = listed_chapters(doc)
    printed = {n: (t, line, w) for n, t, line, w in (oneline_contents(doc) or contents_chapters(doc, listed))}
    out, n, gap = [], 1, 0
    while gap < 2 and n < 200:
        tries = [x for x in (printed.get(n, (None,) * 3)[:2] + (listed.get(n),)) if x]
        if tries:
            out.append((n, list(dict.fromkeys(tries)), printed[n][2] if n in printed else None))
            gap = 0
        else:
            gap += 1
        n += 1
    return out


def title_pattern(title: str):
    """A regex for a paragraph that opens with TITLE (an optional 'Chapter N' or bare N first); punctuation and
    spacing between its words may differ ('Text - AI' in the contents, 'Text: AI' in the body)."""
    toks = re.findall(r"[^\W_]+", title)
    if not toks:
        return None
    return re.compile(r"(?:chapter\s+)?(?:\d{1,3}\W+)?" + r"\W+".join(map(re.escape, toks)) + r"(?![^\W_])", re.I)


def split_at_contents(doc: Doc) -> Doc:
    """Bookmarks that stop early leave one section with most of the book (L-012, L-026 `printed-contents-split`).
    Cut that section where each chapter of the printed contents page opens: the first paragraph, in order, that
    begins with the chapter's title (pdftotext runs a chapter's opening page into one paragraph, so the title is
    split off as the heading). Needs CONTENTS_MIN chapters found in order; else the section stays whole."""
    total = sum(section_chars(s) for s in doc.sections) or 1
    big = [i for i, s in enumerate(doc.sections)
           if section_chars(s) > BIG_SECTION_CHARS and section_chars(s) > total // 2]
    if not big or len(doc.sections) < 2:
        return doc
    bi = big[0]
    s = doc.sections[bi]
    chapters = chapter_list(doc)
    start = max([w[1] + 1 for _, _, w in chapters if w and w[0] == bi], default=0)
    cuts, j = [], start
    for n, titles, _ in chapters:
        pats = [(t, title_pattern(t)) for t in titles]
        for q in range(j, len(s.paras)):
            text = s.paras[q].text.strip()
            m = next(((t, m) for t, pat in pats if pat and (m := pat.match(text))), None)
            if m:
                if q > j and m[1].end() == len(text) and s.paras[q - 1].text.strip() == str(n):
                    q -= 1   # the chapter number sits in its own paragraph above the title (EPUB): cut there
                    cuts.append((q, n, m[0], len(str(n))))
                    j = q + 2
                    break
                cuts.append((q, n, m[0], m[1].end()))
                j = q + 1
                break
    if len(cuts) < CONTENTS_MIN:
        return doc
    out = [Section(s.title, s.paras[:cuts[0][0]], s.level, s.sid)] if cuts[0][0] else []
    for k, (q, n, title, end) in enumerate(cuts):
        stop = cuts[k + 1][0] if k + 1 < len(cuts) else len(s.paras)
        rest = s.paras[q].text.strip()[end:].lstrip(" :.,–—-").strip()
        paras = [Para("h", f"{n}. {title}", 1)] + ([Para(s.paras[q].kind, rest)] if rest else []) + s.paras[q + 1:stop]
        out.append(Section(f"{n}. {title}", paras, s.level, f"{s.sid}@p{q + 1}"))
    doc.sections[bi:bi + 1] = out
    return doc


LEADER_RE = re.compile(r"(?<=\S)\s*(?:�{3,}|\.{4,}|·{4,}|…{2,}|(?:\. ){3,}\.?)\s*(?=(?:\d{1,4}|[ivxlcdm]{1,7})\b)")


def collapse_leaders(doc: Doc) -> Doc:
    """Contents dot leaders ('About the Author' + 60 U+FFFD or dots + 'xiii') become ' ... ' with one ellipsis
    character, in titles and text, so every output path prints them short (L-028 `contents-dot-leaders`)."""
    for s in doc.sections:
        s.title = LEADER_RE.sub(" … ", s.title)
        for p in s.paras:
            if "���" in p.text or "..." in p.text or "··" in p.text or "……" in p.text \
                    or ". . ." in p.text:
                p.text = LEADER_RE.sub(" … ", p.text)
    return doc


def load(path: str, member: str | None = None, via: str | None = None) -> Doc:
    doc = title_repeated_notes(split_at_contents(refine(collapse_leaders(load_raw(path, member, via)))))
    if doc.fmt in ("pdf", "epub") and not member and not via:
        scan_note(doc, path)
    return doc


SCAN_WORDS_PER_PAGE = 10   # 82 real PDFs and EPUBs: the 6 scans had 0 words a page, the thinnest text book 132 (L-011)
SIBLING_EXTS = (".djvu", ".epub", ".pdf", ".mobi", ".azw3", ".fb2", ".docx", ".txt", ".html")


def scan_note(doc: Doc, path: str) -> None:
    """A PDF or EPUB with pages but almost no words is page images. Say so and name the ways in, or the reader sees
    `words: 0` and has to work it out (L-011)."""
    n = str(doc.meta.get("pages") or "")
    pages = int(n) if n.isdigit() else len(doc.sections)
    words = sum(s.words() for s in doc.sections)
    if ocr_cache(path).exists():
        return
    if not pages or words >= SCAN_WORDS_PER_PAGE * pages:
        return
    p = Path(path)
    sibs = [q.name for q in sorted(p.parent.iterdir()) if q != p and q.is_file()
            and q.stem.lower() == p.stem.lower() and q.suffix.lower() in SIBLING_EXTS]
    djvu = " (DjVu copies often carry OCR text)" if any(s.lower().endswith(".djvu") for s in sibs) else ""
    routes = [f"read the copy beside it: {', '.join(sibs)}{djvu}"] if sibs else []
    eng = ocr_engine() if doc.fmt == "pdf" or epub_page_images(path) else None
    if eng:
        how = "the OCR built into Windows" if eng == "windows" else "tesseract"
        routes.append(f"OCR it once with `rw.py ocr \"{p.name}\"` ({how}; then info, toc, read and grep use the text)")
    elif find_tool("ocrmypdf"):
        routes.append("add a text layer with `ocrmypdf --skip-text IN OUT` (installed)")
    elif doc.fmt == "pdf":
        routes.append("OCR it: `rw.py ocr` needs Windows' built-in OCR or tesseract, and neither is available (ocrmypdf also works)")
    else:
        routes.append("OCR it: `rw.py ocr` needs Windows' built-in OCR or tesseract, and neither is available")
    if doc.fmt == "pdf":
        routes.append("look at pages: " + (f"`rw.py page \"{p.name}\" 1-5` writes PNGs for the agent's image reader"
                                           if tools()["mutool"] or find_tool("pdftoppm")
                                           else "`rw.py page` writes PNGs for the agent's image reader, once mutool or pdftoppm is installed"))
    else:
        routes.append("the page images are inside the EPUB (a zip): extract a few and view them with the agent's image reader")
    unit = "pages" if doc.fmt == "pdf" else "sections"
    doc.notes.append(f"no text layer: {fmt_n(words)} words in {fmt_n(pages)} {unit}, so this is probably a scan. "
                     "Ways in: " + "; ".join(routes))


# ---------------------------------------------------------------- OCR for scanned PDFs

WIN_OCR_PS = r'''param([string]$Dir)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(); $task.Result }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { Write-Error 'no OCR language installed (Settings > Time & language > Language)'; exit 2 }
$utf8 = New-Object System.Text.UTF8Encoding $false
Get-ChildItem -Path $Dir -Filter 'p*.png' | ForEach-Object {
  $f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($_.FullName)) ([Windows.Storage.StorageFile])
  $s = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $d = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $b = Await ($d.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $r = Await ($engine.RecognizeAsync($b)) ([Windows.Media.Ocr.OcrResult])
  $out = New-Object System.Collections.Generic.List[string]
  $prevBottom = -1
  foreach ($line in $r.Lines) {
    $top = ($line.Words | ForEach-Object { $_.BoundingRect.Y } | Measure-Object -Minimum).Minimum
    $h = ($line.Words | ForEach-Object { $_.BoundingRect.Height } | Measure-Object -Maximum).Maximum
    if ($prevBottom -ge 0 -and ($top - $prevBottom) -gt 0.9 * $h) { $out.Add('') }
    $out.Add($line.Text)
    $prevBottom = $top + $h
  }
  $s.Dispose()
  [System.IO.File]::WriteAllText(($_.FullName -replace '\.png$', '.txt'), ($out -join "`n"), $utf8)
}
'''


def ocr_dir() -> Path:
    d = Path(os.environ.get("READWRIGHT_OCR_DIR") or Path.home() / ".readwright" / "ocr")
    return d


def ocr_cache(path: str) -> Path:
    """Where `ocr` keeps a PDF's text: lasting (OCR of a book takes minutes), keyed by path, size and mtime."""
    st = os.stat(path)
    key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:20]
    return ocr_dir() / f"{key}.txt"


def ocr_engine() -> str | None:
    """`windows` (the OCR built into Windows 10 and 11, through Windows PowerShell 5.1), `tesseract`, or None."""
    hide = {t.strip() for t in os.environ.get("RW_HIDE_TOOLS", "").split(",") if t.strip()}
    if os.name == "nt" and "windows-ocr" not in hide and find_tool("powershell"):
        return "windows"
    if "tesseract" not in hide and find_tool("tesseract"):
        return "tesseract"
    return None


def ocr_pages(path: str, first: int, last: int, dpi: int, engine: str, images: list | None = None) -> list:
    """Render pages first..last and OCR them; one text per page, blank lines between paragraphs. With `images`
    (an EPUB's page images in spine order) the pages are those images, copied out of the zip instead of rendered;
    both engines read a JPEG by its content whatever the file's name says."""
    mt, pp = tools()["mutool"], find_tool("pdftoppm")
    td = tempfile.mkdtemp(prefix="readwright-ocr-")
    try:
        if images is not None:
            with zipfile.ZipFile(path) as z:
                for n in range(first, last + 1):
                    Path(td, f"p{n}.png").write_bytes(zread(z, images[n - 1]))
            r = subprocess.CompletedProcess([], 0)
        elif mt:
            r = run([mt, "draw", "-q", "-r", str(dpi), "-o", os.path.join(td, "p%d.png"), path, f"{first}-{last}"])
        elif pp:
            r = run([pp, "-r", str(dpi), "-f", str(first), "-l", str(last), "-png", path, os.path.join(td, "p")])
        else:
            raise RWError("ocr needs mutool or pdftoppm to render pages; nothing was installed")
        if r.returncode != 0:
            raise RWError("rendering pages failed: " + tool_error(r))
        imgs = {}
        for q in Path(td).glob("p*.png"):
            m = re.match(r"p-?0*(\d+)$", q.stem)
            if m:
                imgs[int(m.group(1))] = q
        if engine == "windows":
            ps = os.path.join(td, "ocr.ps1")
            with open(ps, "w", encoding="utf-8-sig") as f:
                f.write(WIN_OCR_PS)
            r = run([find_tool("powershell"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                     "-File", ps, "-Dir", td], timeout=60 + 30 * len(imgs))
            if r.returncode != 0:
                raise RWError("Windows OCR failed: " + tool_error(r))
        else:
            for q in imgs.values():
                r = run([find_tool("tesseract"), str(q), str(q.with_suffix(""))], 300)
                if r.returncode != 0:
                    raise RWError("tesseract failed: " + tool_error(r))
        texts = []
        for n in range(first, last + 1):
            q = imgs.get(n)
            t = q.with_suffix(".txt") if q else None
            texts.append(t.read_bytes().decode("utf-8", "replace").strip() if t and t.exists() else "")
        return texts
    finally:
        shutil.rmtree(td, ignore_errors=True)


def page_numbers(spec: str, total: int) -> list:
    """`N`, `N-M` and `N,M` as a sorted list of page numbers; anything else or past the last page is an error."""
    nums = set()
    for part in spec.split(","):
        m = re.fullmatch(r"\s*(\d+)(?:-(\d+))?\s*", part)
        if not m:
            raise RWError(f"pages take N, N-M or N,M, not `{spec}`")
        lo, hi = int(m[1]), int(m[2] or m[1])
        if lo < 1 or hi < lo or (total and hi > total):
            raise RWError(f"pages {part.strip()} out of range: the PDF has {fmt_n(total)} pages" if total
                          else f"pages {part.strip()} out of range")
        nums.update(range(lo, hi + 1))
    return sorted(nums)


def cmd_page(a) -> int:
    if not os.path.isfile(a.file):
        raise RWError(f"no such file: {a.file}")
    if detect(a.file) != "pdf":
        raise RWError("page renders PDF pages; for a picture inside an EPUB use `rw.py image`")
    mt, pp = tools()["mutool"], find_tool("pdftoppm")
    if not mt and not pp:
        raise RWError("page needs mutool (MuPDF) or pdftoppm (poppler) to render pages; nothing was installed")
    if a.dpi < 1:
        raise RWError("--dpi must be a positive number")
    doc = load_pdf(a.file)
    n = str(doc.meta.get("pages") or "")
    nums = page_numbers(a.pages, int(n) if n.isdigit() else len(doc.sections))
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"\W+", "_", Path(a.file).stem)[:40].strip("_") or "page"
    td = tempfile.mkdtemp(prefix="readwright-page-")
    try:
        for num in nums:
            raw = os.path.join(td, "r")
            if mt:
                r = run([mt, "draw", "-q", "-r", str(a.dpi), "-o", raw + ".png", a.file, str(num)])
            else:
                r = run([pp, "-r", str(a.dpi), "-f", str(num), "-l", str(num), "-png", "-singlefile", a.file, raw])
            made = Path(raw + ".png")
            if r.returncode != 0 or not made.exists():
                raise RWError(f"rendering page {num} failed: " + tool_error(r))
            dest = out_dir / f"{stem}-p{num}.png"
            shutil.move(str(made), str(dest))
            print(dest)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    return EXIT_OK


def cmd_ocr(a) -> int:
    fmt = detect(a.file)
    images = epub_page_images(a.file) if fmt == "epub" else None
    if fmt != "pdf" and not images:
        raise RWError("ocr reads scanned PDFs and EPUBs made of page images" +
                      ("; this EPUB shows no images" if fmt == "epub" else ""))
    engine = ocr_engine()
    if not engine:
        raise RWError("no OCR engine: on Windows 10 or 11 the built-in one needs powershell.exe; elsewhere install "
                      "tesseract (`brew install tesseract`, `apt install tesseract-ocr`). Nothing was installed.")
    doc = load_pdf(a.file) if images is None and not ocr_cache(a.file).exists() else None
    n = str((doc.meta if doc else {}).get("pages") or "")
    total = int(n) if n.isdigit() else (len(doc.sections) if doc else 0)
    cache = ocr_cache(a.file)
    pages = cache.read_bytes().decode("utf-8").split("\f") if cache.exists() else []
    if images:
        total = len(images)
    if not total:
        total = len(pages)
    if a.force:
        pages = []
    pages += [""] * (total - len(pages))
    done = cache.exists() and not a.force
    if done and not a.pages:
        print(f"already OCR'd: {fmt_n(total)} pages in {cache} (--force redoes it)")
        return EXIT_OK
    first, last = 1, total
    if a.pages:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", a.pages)
        if not m:
            raise RWError("--pages takes N or N-M")
        first, last = int(m.group(1)), int(m.group(2) or m.group(1))
        last = min(last, total)
    batch = max(1, a.batch)
    for lo in range(first, last + 1, batch):
        hi = min(last, lo + batch - 1)
        pages[lo - 1:hi] = ocr_pages(a.file, lo, hi, a.dpi, engine, images)
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = tmp_cache(cache)
        tmp.write_bytes("\f".join(pages).encode("utf-8"))
        publish_cache(tmp, cache)
        print(f"ocr: pages {lo}-{hi} of {total}", file=sys.stderr, flush=True)
    words = sum(len(p.split()) for p in pages)
    print(f"ocr ({engine}): {fmt_n(total)} pages, {fmt_n(words)} words, kept in {cache}. info, toc, read and grep "
          f"on the {fmt.upper()} now use this text; OCR misreads letters, so check a quote against a page image.")
    return EXIT_OK


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


def printed_selector(doc: Doc, spec: str) -> str:
    """`p153`, `p153-p160` or `p153-160`: printed page numbers turned into the page sections that carry them."""
    labels = doc.meta.get("printed_labels") or {}
    shift = doc.meta.get("page_shift", 0)
    inv = {v: k for k, v in sorted(labels.items(), reverse=True)}

    starts = []   # (PDF page, section number): a page holding sub-headings has several sections, so a page is not a section number
    for i, s in enumerate(doc.sections, 1):
        m = re.fullmatch(r"page(\d+)", s.sid or "")
        if m:
            starts.append((int(m.group(1)), i))

    def sections_of(page: int, tok: str) -> tuple:
        """First and last section for a PDF page; a page inside a longer section gives that section."""
        if not starts:
            return page, page
        here = [i for p, i in starts if p == page]
        if here:
            return here[0], here[-1]
        before = [i for p, i in starts if p < page]
        if not before:
            raise RWError(f"printed page {tok[1:]} falls before the first section; toc shows each page's (p. N)")
        return before[-1], before[-1]

    def one(tok: str) -> tuple:
        tok = tok.strip()
        if not tok.lower().startswith("p"):
            return tok, tok
        if not tok[1:].isdigit():
            raise RWError(f"bad --section {spec!r}: printed pages are pN or pN-pM")
        v = int(tok[1:])
        if labels:
            if v not in inv:
                raise RWError(f"no page carries the printed number {v}; toc shows each page's (p. N)")
            return sections_of(inv[v], tok)
        if shift:
            return sections_of(v - shift, tok)
        raise RWError("this document has no printed page numbers to go by; use section numbers")
    out = []
    for part in spec.split(","):
        a, sep, b = part.partition("-")
        if sep and a.strip().lower().startswith("p") and b.strip().isdigit():
            b = "p" + b.strip()
        first, last = one(a)
        if sep:
            out.append(f"{first}-{one(b)[1]}" if b.strip() else f"{first}-")
        else:
            out.append(str(first) if first == last else f"{first}-{last}")
    return ",".join(out)


def chapter_selector(doc: Doc, spec: str) -> str:
    """--chapter 78,81-83: sections by the number printed in their titles ("78 / Title", "Chapter 78"), which toc's
    position numbers drift from once part openers and front matter are counted."""
    wanted = set(parse_selector(spec, 9999))
    hits = []
    for i, s in enumerate(doc.sections, 1):
        m = re.match(r"\s*(?:chapter\s+)?(\d+)\b", s.title, re.I)
        if m and int(m.group(1)) in wanted:
            hits.append(i)
    if not hits:
        raise RWError(f"no section title starts with chapter number {spec}; run toc to see the titles")
    return ",".join(str(i) for i in hits)


def select(doc: Doc, section: str | None, title: str | None) -> list:
    n = len(doc.sections)
    if section and "p" in section.lower():
        section = printed_selector(doc, section)
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


GENERIC_REPEATS = 3   # a title used this often ("How to do it...", "There's more...") says nothing on its own


def context_titles(doc: Doc) -> dict:
    """Section number -> nearest earlier distinctive title, for sections whose title repeats GENERIC_REPEATS+ times."""
    def key(t):
        return re.sub(r"\W+", " ", t).strip().lower()
    counts = {}
    for sec in doc.sections:
        counts[key(sec.title)] = counts.get(key(sec.title), 0) + 1
    out, last = {}, None
    for i, sec in enumerate(doc.sections, 1):
        if counts[key(sec.title)] >= GENERIC_REPEATS:
            if last:
                out[i] = last
        else:
            last = sec.title
    return out


def in_context(doc: Doc, i: int) -> str:
    """' (in: Recipe title)' for a section with a generic title, else ''. Computed once per Doc."""
    ctx = doc.__dict__.get("_ctx")
    if ctx is None:
        ctx = doc.__dict__["_ctx"] = context_titles(doc)
    return f" (in: {ctx[i]})" if i in ctx else ""


def md_head(doc: Doc, i: int, s: Section) -> str:
    ctx = in_context(doc, i)
    return (f"<!-- readwright section {i}/{len(doc.sections)} id={s.sid} words={s.words()}"
            + (f" in={ctx[6:-1]!r}" if ctx else "") + " -->")


def cap_words(paras: list, n: int) -> tuple:
    """The first n words of paras (whole paragraphs, the last one cut at a word end with its spacing kept),
    the words left out, and the cut paragraph's prefix without the ellipsis (None when the cut fell between paragraphs)."""
    out, left = [], n
    total = sum(len(p.text.split()) for p in paras)
    part = None
    for p in paras:
        if left <= 0:
            break
        w = p.text.split()
        if len(w) <= left:
            out.append(p)
        else:
            end = list(re.finditer(r"\S+", p.text))[left - 1].end()
            part = replace(p, text=p.text[:end])
            out.append(replace(p, text=p.text[:end] + " ..."))
        left -= len(w)
    return out, max(0, total - n), part


def cut_offset(body: list, part, fmt: str) -> int:
    """Where the shown text of a capped section ends, counted as `read --offset` counts within the section body."""
    mark = chr(0)
    if part is None:
        return len(render_paras(body, fmt)) + 2   # the next paragraph starts after the blank line
    return render_paras(body[:-1] + [replace(part, text=part.text + mark)], fmt).index(mark)


CODE_CALLOUT = re.compile(r"\[image omitted: \d+\.\w+\]")
CODE_LEGEND = re.compile("[①-⑳❶-➓]")   # a circled number opens a line explaining a listing
CODE_CAPTION = re.compile(r"(?:Listing|Example|Code) \d+(?:[.-]\d+)*\b")


def skip_code(doc: Doc) -> dict:
    """Drop code blocks: paragraphs of kind pre (HTML and EPUB <pre>, fenced or indented Markdown), found by
    structure, never by guessing from a line's look. A prose paragraph or list item that ends with ':' and sits
    right before a dropped block goes too (its lead-in, noise once the code is gone); a colon line before prose
    stays. A picture marker named only by a number (a publisher's code callout, `[image omitted: 1.png]`) goes too,
    in a section with code, since it points into the dropped code. So do a short caption right before a block
    (`Listing 5.1 ...`) and the run of circled-number legend lines right after one. Returns {section number:
    (blocks, words, lead-ins, captions and legends)} for sections that had any."""
    out = {}
    for n, s in enumerate(doc.sections, 1):
        code = [p for p in s.paras if p.kind == "pre"]
        if code:
            ps = s.paras
            lead = {i for i in range(len(ps) - 1)
                    if ps[i + 1].kind == "pre" and ps[i].kind in ("p", "li") and ps[i].text.rstrip().endswith(":")}
            notes = {i for i in range(len(ps) - 1)
                     if ps[i + 1].kind == "pre" and CODE_CAPTION.match(ps[i].text.strip())
                     and len(ps[i].text.split()) <= 25} - lead
            for i in range(1, len(ps)):   # legends chain: each follows the code or another legend
                if CODE_LEGEND.match(ps[i].text.strip()) and (ps[i - 1].kind == "pre" or i - 1 in notes):
                    notes.add(i)
            out[n] = (len(code), sum(len(p.text.split()) for p in code), len(lead), len(notes))
            s.paras = [p for i, p in enumerate(ps)
                       if p.kind != "pre" and i not in lead and i not in notes
                       and not CODE_CALLOUT.fullmatch(p.text.strip())]
    return out


def cut_rows(doc: Doc, limit: int) -> int:
    """Cut table rows longer than limit words, marking each cut. Some books set whole chat replies in table rows;
    a long row is a sample more often than an argument. Prose paragraphs stay whole. Returns the rows cut."""
    cut = 0
    for s in doc.sections:
        for p in s.paras:
            words = p.text.split()
            if p.kind == "row" and len(words) > limit:
                p.text = " ".join(words[:limit]) + f" [row cut: {fmt_n(len(words) - limit)} more words]"
                cut += 1
    return cut


def code_note(doc: Doc, skipped: dict, idx) -> str:
    blocks = sum(skipped[i][0] for i in idx if i in skipped)
    words = sum(skipped[i][1] for i in idx if i in skipped)
    leads = sum(skipped[i][2] for i in idx if i in skipped)
    notes = sum(skipped[i][3] for i in idx if i in skipped)
    if blocks:
        return (f"--skip-code left out {fmt_n(words)} words in {fmt_n(blocks)} code blocks"
                + (f" and {fmt_n(leads)} lead-in lines" if leads else "")
                + (f" and {fmt_n(notes)} captions and legends" if notes else ""))
    if doc.fmt.startswith("pdf"):
        return "--skip-code found no code blocks: a PDF has no structural code marker, so code stays in (EPUB, HTML and Markdown only)"
    return "--skip-code found no code blocks"


def header_line(doc: Doc, i: int, s: Section, offsets: list, total_words: int) -> str:
    start = offsets[i - 1]
    pct = 100 * start // total_words if total_words else 0
    return (f"=== [{i}/{len(doc.sections)}] {s.title}{in_context(doc, i)} | id {s.sid} | {fmt_n(s.words())} words | "
            f"starts at word {fmt_n(start + 1)} of {fmt_n(total_words)} ({pct}%) ===")


def word_offsets(doc: Doc) -> list:
    out, acc = [], 0
    for s in doc.sections:
        out.append(acc)
        acc += s.words()
    return out


def compact_text(text: str) -> str:
    """One newline between paragraphs instead of a blank line: fewer lines for an agent to page through."""
    return re.sub(r"\n[ \t]*\n+", "\n", text)


def compose(doc: Doc, idx: list, fmt: str, max_words: int | None = None, flags: str = "") -> str:
    offs = word_offsets(doc)
    total = offs[-1] + doc.sections[-1].words() if doc.sections else 0
    blocks = []
    for i in idx:
        s = doc.sections[i - 1]
        if fmt == "md":
            head = md_head(doc, i, s)
            paras = s.paras if (s.paras and s.paras[0].kind == "h") else [Para("h", s.title, min(6, s.level + 1))] + s.paras
            body = paras
        else:
            head, body = header_line(doc, i, s, offs, total), s.paras
        cut, total_s = 0, sum(len(p.text.split()) for p in body)
        if max_words:
            body, cut, part = cap_words(body, max_words)
        text = render_paras(body, fmt)
        if cut:
            at = len(head) + 2 + cut_offset(body, part, fmt)
            text += (f"\n[readwright: cut at {fmt_n(total_s - cut)} of {fmt_n(total_s)} words; continue with "
                     f"--section {i} --offset {at}{flags}]")
        blocks.append(head + "\n\n" + text)
    return "\n\n".join(blocks) + "\n"


def clean_cut(piece: str) -> str:
    """End a --max-chars cut at the last paragraph break, else line break, else sentence end, in the piece's last
    quarter, so a reader never gets half a sentence; the footer's --offset then resumes there."""
    floor = len(piece) * 3 // 4
    for mark, keep in (("\n\n", 2), ("\n", 1), (". ", 2), ("? ", 2), ("! ", 2), (" ", 1)):
        k = piece.rfind(mark, floor)
        if k >= 0:
            piece = piece[:k + keep]
            break
    # A section's header and title with no body wastes the cap and reads as an empty section: resume there.
    orphan = re.search(r"(?:^|\n)=== \[\d+/\d+\][^\n]*===\n(?:[^\n]*\n)?\s*$", piece)
    if orphan and orphan.start() > 0:
        piece = piece[:orphan.start() + 1]
    return piece


def para_offsets(doc: Doc, i: int, fmt: str = "txt") -> list:
    """Character offset of each paragraph's text in `read --section i` output (what --offset counts)."""
    s = doc.sections[i - 1]
    if fmt == "md":
        head = md_head(doc, i, s)
        paras = s.paras if (s.paras and s.paras[0].kind == "h") else [Para("h", s.title, min(6, s.level + 1))] + s.paras
    else:
        offs = word_offsets(doc)
        head = header_line(doc, i, s, offs, offs[-1] + doc.sections[-1].words())
        paras = s.paras
    skip = len(paras) - len(s.paras)
    out, pos = [], len(head) + 2
    for k, p in enumerate(paras):
        if k:
            pos += 1 if (paras[k - 1].kind in ("row", "li") and p.kind == paras[k - 1].kind) else 2
        r = render_paras([p], fmt)
        if k >= skip:
            out.append(pos + max(0, r.find(p.text)))
        pos += len(r)
    return out


def section_chars(s: Section) -> int:
    return sum(len(p.text) for p in s.paras)


def big_section_notes(doc: Doc) -> list:
    """Bookmarks that stop early leave one giant section (L-012); say so and point at grep offsets."""
    total = sum(section_chars(s) for s in doc.sections) or 1
    out = []
    for i, s in enumerate(doc.sections, 1):
        c = section_chars(s)
        if c > BIG_SECTION_CHARS and c > total // 4 and len(doc.sections) > 1:
            out.append(f"note: section {i} holds {fmt_n(c)} chars ({100 * c // total}% of the text); the outline likely "
                       f"stops early. List its sub-headings with paragraph numbers first: read --section {i} --headings; "
                       f"or find places with grep (it prints each hit's offset); then read --section {i} "
                       f"--offset N or --at-para P")
    return out


def write_out(path: str, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


BARE_NUMBER = re.compile(r"^(?:chapter\s+)?(\d{1,3})\.?$", re.I)
BARE_NUMBER_WORDS = 3   # a number-only section holds at most this many words (Packt-style chapter openers)


def chapter_numbers(doc: Doc) -> dict:
    """{title section number: (chapter number, number section number)} where a bare "12" or "Chapter 12" section
    (0-3 words) is followed by a titled section of the same level. Section numbers are never changed."""
    out, secs = {}, doc.sections
    for i in range(len(secs) - 1):
        m = BARE_NUMBER.match(secs[i].title.strip())
        nxt = secs[i + 1]
        if (m and secs[i].words() <= BARE_NUMBER_WORDS and nxt.level == secs[i].level
                and not BARE_NUMBER.match(nxt.title.strip()) and not nxt.title.startswith("(untitled")):
            out[i + 2] = (int(m.group(1)), i + 1)
    return out


def rolled_words(doc: Doc) -> list:
    """Words of each section plus all deeper sections that follow it (its subtree)."""
    secs = doc.sections
    own = [s.words() for s in secs]
    out = []
    for i, s in enumerate(secs):
        t, j = own[i], i + 1
        while j < len(secs) and secs[j].level > s.level:
            t += own[j]
            j += 1
        out.append(t)
    return out


def page_groups(doc: Doc) -> list:
    """Runs of one-page sections that share a running head ("page 21: Testimonial Injustice"), for a PDF
    with no outline: [(first, last, head, words)]. A chapter's opening page carries the head plus its first
    words ("page 20: Testimonial Injustice In Anthony..."), so it joins the run when the next page's head
    starts it. [] when the sections are not bare pages."""
    heads = []
    for s in doc.sections:
        m = re.match(r"page \d+(?: \(p\. [^)]*\))?(?:: (.*))?$", s.title)
        if not m:
            return []
        heads.append((m.group(1) or "").strip())
    groups = []
    for i, h in enumerate(heads, 1):
        w = doc.sections[i - 1].words()
        if groups and h and h == groups[-1][2]:
            f, _, g, gw = groups[-1]
            groups[-1] = (f, i, g, gw + w)
            continue
        nxt = heads[i] if i < len(heads) else ""
        if len(nxt) > 3 and h.startswith(nxt + " "):
            h = nxt
        groups.append((i, i, h, w))
    return groups


CONTENTS_HEAD_RE = re.compile(r"(table of )?contents", re.I)


LEADER_ENTRY_RE = re.compile(r"((?:\d{1,3}\s+)?[^\W\d_](?:(?!\s(?:…|\.\s\.)).)*?)\s+(?:…|\.(?:\s\.)+)\s*(\d{1,4})(?=\s|$)")


def leader_groups(doc: Doc) -> list:
    """Page runs from a printed contents whose entries run on inside one paragraph, 'Title ... 21 Next title ... 26'
    (L-040 `group-labelled-pages`). Printed pages map through printed_labels or page_shift, so a drifting offset
    lands on the right page. Needs three entries with rising pages; [] otherwise."""
    if not page_groups(doc):
        return []
    n = len(doc.sections)
    shift = doc.meta.get("page_shift", 0)
    labels = doc.meta.get("printed_labels") or {}
    inv = {v: k for k, v in sorted(labels.items(), reverse=True)}
    ents = []
    for s in doc.sections[: max(20, n // 10)]:
        for p in s.paras:
            for t, num in LEADER_ENTRY_RE.findall(p.text):
                pg = inv.get(int(num)) if labels else int(num) - shift
                if pg and pg <= n and (not ents or pg > ents[-1][1]):
                    ents.append((t.strip(), pg))
    if len(ents) < 3:
        return []
    out = [(1, ents[0][1] - 1, "(front matter)")] if ents[0][1] > 1 else []
    out += [(pg, (ents[k + 1][1] - 1 if k + 1 < len(ents) else n), t) for k, (t, pg) in enumerate(ents)]
    return [(f, l, t, sum(doc.sections[i - 1].words() for i in range(f, l + 1))) for f, l, t in out]


def contents_groups(doc: Doc) -> list:
    """Page runs from a printed contents page whose entries sit on two lines, the title ('1 Personal Finance',
    'Foreword') then its page number ('15'), for a PDF with no outline and no running heads (L-032
    `contents-title-then-page`): [(first, last, title, words)] like page_groups. Needs three entries with rising
    pages; [] otherwise."""
    if not page_groups(doc):
        return []
    shift = doc.meta.get("page_shift", 0)
    n = len(doc.sections)
    for si, s in enumerate(doc.sections[: max(20, n // 10)]):
        ps = [p.text.strip() for p in s.paras]
        if not ps or not CONTENTS_HEAD_RE.fullmatch(ps[0]):
            continue
        ents = []
        for a, b in zip(ps[1:], ps[2:]):
            if re.fullmatch(r"\d{1,4}", b) and re.match(r"(\d{1,3}\s+)?[^\W\d_]", a) and len(a.split()) <= 12:
                pg = int(b) - shift
                if (not ents or pg > ents[-1][1]) and si + 1 < pg <= n:
                    ents.append((a, pg))
        if len(ents) < 3:
            continue
        out = [(1, ents[0][1] - 1, "(front matter)")] if ents[0][1] > 1 else []
        out += [(pg, (ents[k + 1][1] - 1 if k + 1 < len(ents) else n), t) for k, (t, pg) in enumerate(ents)]
        return [(f, l, t, sum(doc.sections[i - 1].words() for i in range(f, l + 1))) for f, l, t in out]
    return []


def group_lines(doc: Doc) -> list:
    out = []
    groups = page_groups(doc)
    if len(groups) * 3 >= len(doc.sections):   # no running heads to fold by: try the printed contents
        groups = contents_groups(doc) or leader_groups(doc) or groups
    for f, l, h, w in groups:
        rng = f"{f}-{l}" if l > f else str(f)
        out.append(f"{rng:>9}. {h or '(no text)'}  ({fmt_n(w)} w)")
    return out


def code_words(doc: Doc, roll: bool = False) -> list:
    """Words in code blocks (kind pre, as skip_code finds them) per section; roll adds the sections below it."""
    own = [sum(len(p.text.split()) for p in s.paras if p.kind == "pre") for s in doc.sections]
    if not roll:
        return own
    out = []
    for i, s in enumerate(doc.sections):
        j, n = i + 1, own[i]
        while j < len(doc.sections) and doc.sections[j].level > s.level:
            n += own[j]
            j += 1
        out.append(n)
    return out


def toc_lines(doc: Doc, limit: int, ids: bool = False, depth: int | None = None, code: bool = False) -> list:
    """One line per section. A bare chapter-number section is merged into the titled section after it
    ("Ch. 12: Title", printed under the title's number; the number section stays readable). depth keeps
    sections at indent depth <= depth, with word counts rolled up from the sections below."""
    lines = []
    chap = chapter_numbers(doc)
    skip = {n for _, n in chap.values()}
    roll = rolled_words(doc) if depth else None
    cw = code_words(doc, bool(depth)) if code else None
    keep = [i for i, s in enumerate(doc.sections, 1) if i not in skip and not (depth and s.level > depth)]
    for k, i in enumerate(keep):
        if k >= limit:
            lines.append(f"... {len(keep) - limit} more sections (raise --limit)")
            break
        s = doc.sections[i - 1]
        title = s.title
        w = roll[i - 1] if roll else s.words()
        if i in chap:
            title = f"Ch. {chap[i][0]}: {title}"
            w += doc.sections[chap[i][1] - 1].words()
        ind = "  " * (s.level - 1)
        c = f", {fmt_n(cw[i - 1])} code" if cw and cw[i - 1] else ""
        lines.append(f"{i:>4}. {ind}{title}{in_context(doc, i)}  ({fmt_n(w)} w{c})" + (f"  [{s.sid}]" if ids else ""))
    return lines


def doc_head(doc: Doc) -> str:
    sm = summary(doc)
    t = doc.meta.get("title")
    return (f"# {Path(doc.path).name if ' :: ' not in doc.path else doc.path} | {doc.fmt}"
            + (f" | {t}" if t else "")
            + f" | {len(doc.sections)} sections | {fmt_n(sm['words'])} words | ~{fmt_n(sm['tokens'])} tokens")


# ---------------------------------------------------------------- commands

def meta_swapped(meta, name):
    """A note when the title field holds a person's name and the author field the book title, both in the file name."""
    t, au = meta.get("title") or "", meta.get("author") or ""
    norm = lambda s: " ".join(re.findall(r"[a-z0-9]+", s.lower()))
    key = f" {norm(name)} "
    if (re.fullmatch(r"[A-Z][\w'.-]*(?: [A-Z][\w'.-]*){1,3}", t) and len(au.split()) > len(t.split())
            and f" {norm(t)} " in key and f" {norm(au.split(':')[0])} " in key):
        return f"title and author look swapped in the metadata: the title is probably {au!r}, by {t}"
    return ""


SCRAMBLED_RUN = re.compile(r"(?<![A-Za-z/._@-])[a-z]{18,}(?![A-Za-z/._@-])")   # URLs and identifiers do not count
SCRAMBLED_MIN_RUNS, SCRAMBLED_MIN_RATE = 5, 0.5   # per 1,000 words; see LEARNINGS L-041 for the measurements


def scrambled_note(doc: Doc) -> str | None:
    """An embedded OCR layer can glue and interleave words. Words of 18 or more lowercase letters are rare in clean text."""
    if doc.fmt != "pdf" or any("text from OCR" in n for n in doc.notes):
        return None
    runs, words = 0, 0
    for s in doc.sections:
        for p in s.paras:
            runs += len(SCRAMBLED_RUN.findall(p.text))
            words += len(p.text.split())
    rate = 1000 * runs / max(words, 1)
    if runs < SCRAMBLED_MIN_RUNS or rate < SCRAMBLED_MIN_RATE:
        return None
    name = Path(doc.path).name
    return (f"the embedded text layer looks scrambled: {fmt_n(runs)} lowercase runs of 18 or more letters ({rate:.1f} per "
            f"1,000 words), so words may be glued or interleaved and titles garbled. Treat exact wording with care; "
            f"re-OCR with `rw.py ocr \"{name}\"` or view pages with `rw.py page \"{name}\" N`")


LANG_WORDS = {   # short common words; a word two languages share simply counts for both
    "en": "the and of to in that is was for with as on are this be by it an from at or have not which but they their has were been",
    "de": "der die das und ist nicht ein eine einer einem einen den dem des von zu mit auf für im auch sich als bei wird sind aus oder wie dass daß durch nach werden sie es",
    "fr": "le la les des du et est une un dans que qui pour sur pas par au aux avec ce cette sont ses plus ou en il elle nous",
    "es": "el la los las del es una un en que por con para se no su sus como más pero al lo muy entre",
    "it": "il la le gli dei delle della del degli è una un in che per con non si di da nel nella sono come più ma anche",
    "pt": "os as do da dos das um uma em que por com para não se no na nas nos mais como mas ao aos são à",
    "nl": "de het een en van dat op te zijn voor met niet aan er ook bij door naar worden",
}
LANG_SETS = {k: frozenset(v.split()) for k, v in LANG_WORDS.items()}
LANG_INSIDE = {k: tuple(w for w in v if len(w) >= 3) for k, v in LANG_SETS.items()}
LANG_WORD = re.compile(r"[^\W\d_]+")
LANG_GLUED = 12         # letters; a token this long may be OCR-glued words, so the words inside it count too
LANG_INSIDE_WEIGHT = 0.5  # weak evidence: `comparatively` holds Spanish `para`
LANG_SHORT = 4          # words; a paragraph under this says too little to judge
LANG_MIN_SCORE = 2      # a winner needs this much evidence, so one stray `la` decides nothing
LANG_NOTE_WORDS, LANG_NOTE_SCORE = 25, 4   # a substantial paragraph, for the `info` note
LANG_NOTE_MIN, LANG_NOTE_SHARE = 20, 0.1   # a second language needs this many paragraphs and this share of them


def lang_scores(text: str) -> dict:
    """Common-word evidence per language: an exact word counts 1, and a word inside a long token counts half (L-047 `read-lang`)."""
    scores = dict.fromkeys(LANG_SETS, 0.0)
    for w in LANG_WORD.findall(text.lower()):
        for k, words in LANG_SETS.items():
            if w in words:
                scores[k] += 1
            elif len(w) >= LANG_GLUED:
                scores[k] += LANG_INSIDE_WEIGHT * sum(x in w for x in LANG_INSIDE[k])
    return scores


def para_lang(text: str) -> str | None:
    """The language a paragraph's common words favour; None for a tie, too few words or too little evidence."""
    if len(text.split()) < LANG_SHORT:
        return None
    ranked = sorted(lang_scores(text).items(), key=lambda kv: -kv[1])
    return ranked[0][0] if ranked[0][1] >= LANG_MIN_SCORE and ranked[0][1] > ranked[1][1] else None


def filter_lang(doc: Doc, code: str) -> dict:
    """`--lang CODE`: keep the paragraphs that favour CODE, plus code, tables, picture markers and undecided headings.
    A heading that clearly favours another language goes. Returns {section number: paragraphs dropped}."""
    dropped = {}
    for i, s in enumerate(doc.sections, 1):
        kept = []
        for p in s.paras:
            who = para_lang(p.text)
            if p.kind == "h":
                keep = who is None or who == code
            elif p.kind == "p" and not FIXED_MARKER.fullmatch(p.text):
                keep = who == code
            else:
                keep = True
            if keep:
                kept.append(p)
        if len(kept) != len(s.paras):
            dropped[i] = len(s.paras) - len(kept)
            s.paras = kept
    return dropped


def lang_note(doc: Doc) -> str | None:
    """Name the languages when a book has many substantial paragraphs in two or more: a quotation or an abstract does not count."""
    counts = {}
    for s in doc.sections:
        for p in s.paras:
            if p.kind == "p" and len(p.text.split()) >= LANG_NOTE_WORDS and max(lang_scores(p.text).values()) >= LANG_NOTE_SCORE:
                if (who := para_lang(p.text)):
                    counts[who] = counts.get(who, 0) + 1
    total = sum(counts.values())
    many = sorted((k for k, n in counts.items() if n >= LANG_NOTE_MIN and n >= LANG_NOTE_SHARE * total), key=lambda k: -counts[k])
    if len(many) < 2:
        return None
    return (f"paragraphs in {len(many)} languages ({', '.join(f'{k} {fmt_n(counts[k])}' for k in many)}): "
            f"read one with `read --lang {many[0]}`")


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
    info |= {k: v for k, v in doc.meta.items() if v and k != "printed_labels"}
    info |= {"sections": len(doc.sections), "words": sm["words"], "chars": sm["chars"], "tokens_approx": sm["tokens"]}
    if doc.sections:
        big = max(range(len(doc.sections)), key=lambda i: doc.sections[i].words())
        info["largest_section"] = f"{big + 1} ({fmt_n(doc.sections[big].words())} words)"
    swapped = meta_swapped(doc.meta, os.path.basename(a.file))
    scrambled = scrambled_note(doc)
    languages = lang_note(doc)
    notes = doc.notes + ([swapped] if swapped else []) + ([scrambled] if scrambled else []) + ([languages] if languages else [])
    if notes:
        info["notes"] = notes
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        return 0
    for k, v in info.items():
        if k == "notes":
            for n in v:
                print(f"note: {n}")
        else:
            print(f"{k}: {fmt_n(v) if isinstance(v, int) and k not in ('bytes',) else v}")
    print("next: toc, then read --section N" if sm["chars"] > DEFAULT_MAX_CHARS
          else "next: no text to read; see the note" if not sm["words"] and doc.notes else "next: read (small enough to read whole)")
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
        ctx = context_titles(doc)
        chap, roll = chapter_numbers(doc), rolled_words(doc)
        print(json.dumps({"file": doc.path, "format": doc.fmt, "meta": doc.meta, "sections": [
            {"n": i, "title": s.title, "level": s.level, "id": s.sid, "words": s.words(), "start_word": offs[i - 1],
             "words_total": roll[i - 1],
             **({"in": ctx[i]} if i in ctx else {}), **({"chapter": chap[i][0]} if i in chap else {})}
            for i, s in enumerate(doc.sections, 1) if (not a.depth or s.level <= a.depth) and not (a.hide and re.search(a.hide, s.title, re.I))]}, ensure_ascii=False, indent=1))
        return 0
    print(doc_head(doc))
    for n in doc.notes:
        print(f"note: {n}")
    if a.group:
        lines = group_lines(doc)
        if not lines:
            raise RWError("--group folds the one-page sections of a PDF with no outline; this file has titled sections")
        print("\n".join(lines))
        print("read a run: rw.py read FILE --section N-M")
        return 0
    lines = toc_lines(doc, a.limit, a.ids, a.depth, a.code)
    if a.hide:
        hide = re.compile(a.hide, re.I)
        lines = [l for l in lines if not hide.search(l)]
    print("\n".join(lines))
    if a.code and doc.fmt.startswith("pdf"):
        print("note: --code found nothing to count: a PDF has no structural code marker (EPUB, HTML and Markdown only)")
    groups = page_groups(doc)
    if len(doc.sections) > 40 and groups and len(groups) * 3 < len(doc.sections):
        print(f"note: {len(doc.sections)} pages share {len(groups)} running heads; rw.py toc FILE --group lists them as page ranges")
    elif len(doc.sections) > 40 and groups and (cg := contents_groups(doc)):
        print(f"note: the printed contents page lists {len(cg)} parts; rw.py toc FILE --group lists them as page ranges")
    for n in big_section_notes(doc):
        print(n)
    return 0


def flags_used(a) -> str:
    """The paragraph-dropping flags given, to repeat with --at-para (paragraph numbers count what is left)."""
    return "".join(f for f, on in ((" --skip-code", getattr(a, "skip_code", False)),
                                   (f" --max-row-words {getattr(a, 'max_row_words', '')}", getattr(a, "max_row_words", None)),
                                   (" --strip-boilerplate", getattr(a, "strip_boilerplate", False)),
                                   (" --drop-repeated", getattr(a, "drop_repeated", False)),
                                   (" --drop-epigraphs", getattr(a, "drop_epigraphs", False)),
                                   (" --drop-images", getattr(a, "drop_images", False)),
                                   (f" --min-para-words {getattr(a, 'min_para_words', '')}", getattr(a, "min_para_words", None)),
                                   (f" --lang {getattr(a, 'lang', '')}", getattr(a, "lang", None))) if on)


RULE_LINE = re.compile(r"^[.\u2026_\u2013\u2014=-]{20,}$")
LETTER_HEAD = re.compile(r"^[A-Z]\. [A-Z][^.!?]{0,70}$")


def ruled_headings(paras) -> list:
    """(index, level) for headings a PDF marks only by layout: a short line over a rule of dots, level 1, or a short
    'A. Title' line, level 2, once a ruled heading has appeared (L-064 `caps-list-acronym`)."""
    out, seen = [], False
    for k, p in enumerate(paras):
        text = clean(p.text)
        nxt = clean(paras[k + 1].text) if k + 1 < len(paras) else ""
        if len(text) <= 90 and RULE_LINE.match(nxt) and not RULE_LINE.match(text):
            out.append((k, 1))
            seen = True
        elif seen and LETTER_HEAD.match(text):
            out.append((k, 2))
    return out if seen else []


DECIMAL_HEAD = re.compile(r"^(\d{1,2})((?:\.\d{1,2}){1,2}) +[A-Z][^|]*$")
DECIMAL_HEAD_MIN = 5   # fewer than this are likely stray figures or list items


def numbered_headings(paras: list) -> list:
    """(index, level) for short 'N.M Title' or 'N.M.K Title' lines in a PDF with no heading marks, level by depth
    (L-066 `numbered-headings`). A title ending in a period is a sentence, and a line of numbers is a table."""
    out = []
    for k, p in enumerate(paras):
        text = clean(p.text)
        m = DECIMAL_HEAD.match(text)
        if m and len(text) <= 90 and not text.endswith((".", ",", ";", ":")):
            out.append((k, m.group(2).count(".")))
    return out if len(out) >= DECIMAL_HEAD_MIN else []


CAPS_HEAD = re.compile(r"^[A-Z0-9][A-Z0-9 ,'’&:;?!-]{4,69}$")
CAPS_HEAD_MIN = 3        # fewer whole-caps lines in a section are likely a sign, an acronym or a shouted phrase
CAPS_HEAD_BODY = 20      # words the next paragraph needs, so a caps list or table column is not read as headings


def caps_headings(paras: list) -> list:
    """(index, 1) for whole-caps lines of two to ten words followed by a body paragraph, in a PDF with no heading
    marks (Chion, Audio-Vision ch. 5: THE UNITY ILLUSION). A trailing '(MSIs)' style gloss is allowed (L-068)."""
    out = []
    for k, p in enumerate(paras):
        text = clean(p.text)
        bare = re.sub(r"\s*\([^()]{1,12}\)$", "", text)
        nxt = clean(paras[k + 1].text) if k + 1 < len(paras) else ""
        if (CAPS_HEAD.match(bare) and 2 <= len(bare.split()) <= 10 and not bare.endswith((".", ","))
                and len(nxt.split()) >= CAPS_HEAD_BODY and not nxt.isupper()):
            out.append((k, 1))
    return out if len(out) >= CAPS_HEAD_MIN else []


BARE_NUM_HEAD = re.compile(r"^(\d{1,2}) +[A-Z][^.|]{2,70}$")
BARE_NUM_MIN = 3   # a run 1, 2, 3 at least: fewer are footnote markers or list items


def bare_numbered_heads(doc: "Doc", idx: list) -> set:
    """(section, para) of '1 Variable Tempo' style heads across the selected sections, kept only as a run counting up
    from 1 (Collins, Game Sound ch. 8: one PDF page per section, so a per-section count never reaches a threshold;
    L-069 `bare-numbered-heads`)."""
    cands = []
    for i in idx:
        for k, p in enumerate(doc.sections[i - 1].paras):
            text = clean(p.text)
            m = BARE_NUM_HEAD.match(text)
            if m and len(text.split()) <= 10 and not text.endswith((",", ";", ":")):
                cands.append((int(m.group(1)), i, k))
    best, run = [], []
    for n, i, k in cands:
        if n == 1:
            run = [(i, k)]
        elif run and n == len(run) + 1:
            run.append((i, k))
        if len(run) > len(best):
            best = list(run)
    return set(best) if len(best) >= BARE_NUM_MIN else set()


def heading_lines(doc: Doc, idx: list) -> list:
    """`read --headings`: each heading paragraph of the selected sections, indented by level, with its paragraph
    number (for --at-para) and the words up to the next heading."""
    out = []
    bare = bare_numbered_heads(doc, idx)
    for i in idx:
        s = doc.sections[i - 1]
        out.append(f"[{i}] {s.title} ({fmt_n(s.words())} words)")
        hs = [k for k, p in enumerate(s.paras) if p.kind == "h" and clean(p.text).lower() != clean(s.title).lower()]
        if not hs:
            ruled = [(k, lv) for k, lv in ruled_headings(s.paras) if k]
            for n, (k, lv) in enumerate(ruled):
                end = ruled[n + 1][0] if n + 1 < len(ruled) else len(s.paras)
                w = sum(len(p.text.split()) for p in s.paras[k + 1:end] if not RULE_LINE.match(clean(p.text)))
                out.append(f"{'  ' * lv}{clean(s.paras[k].text)}  (para {k + 1}, {fmt_n(w)} words)")
            if ruled:
                continue
            numbered = numbered_headings(s.paras)
            for n, (k, lv) in enumerate(numbered):
                end = numbered[n + 1][0] if n + 1 < len(numbered) else len(s.paras)
                w = sum(len(p.text.split()) for p in s.paras[k + 1:end])
                out.append(f"{'  ' * lv}{clean(s.paras[k].text)}  (para {k + 1}, {fmt_n(w)} words)")
            if numbered:
                continue
            caps = [(k, lv) for k, lv in caps_headings(s.paras) if k]
            for n, (k, lv) in enumerate(caps):
                end = caps[n + 1][0] if n + 1 < len(caps) else len(s.paras)
                w = sum(len(p.text.split()) for p in s.paras[k + 1:end])
                out.append(f"{'  ' * lv}{clean(s.paras[k].text)}  (para {k + 1}, {fmt_n(w)} words)")
            if caps:
                continue
            mine = sorted(k for j, k in bare if j == i)
            for n, k in enumerate(mine):
                end = mine[n + 1] if n + 1 < len(mine) else len(s.paras)
                w = sum(len(p.text.split()) for p in s.paras[k + 1:end])
                out.append(f"  {clean(s.paras[k].text)}  (para {k + 1}, {fmt_n(w)} words)")
            if mine:
                continue
            out.append("  (no headings under the title in this section; a PDF without structure has none: try toc --group, "
                       "or grep for the words you want)")
            continue
        top = min(s.paras[k].level for k in hs)
        for n, k in enumerate(hs):
            end = hs[n + 1] if n + 1 < len(hs) else len(s.paras)
            w = sum(len(p.text.split()) for p in s.paras[k + 1:end])
            out.append(f"{'  ' * (1 + s.paras[k].level - top)}{s.paras[k].text}  (para {k + 1}, {fmt_n(w)} words)")
    return out


def cmd_read(a) -> int:
    doc = load(a.file, a.member, a.via)
    if getattr(a, "strip_boilerplate", False):
        strip_furniture(doc)
    if doc.fmt == "zip":
        raise RWError("this is a zip archive; list it with toc and pick a member with --member NAME")
    hints = []
    skipped = skip_code(doc) if getattr(a, "skip_code", False) else None
    if getattr(a, "max_row_words", None):
        n = cut_rows(doc, a.max_row_words)
        hints.append(f"--max-row-words cut {n} long table row(s) across the book; read without it to see them whole")
    if getattr(a, "drop_repeated", False):
        glued = strip_glued_heads(doc)
        n = drop_repeated(doc)
        hints.append(f"--drop-repeated dropped {n} short paragraph(s) that recur across the book (credit lines, notices)"
                     + (f" and {glued} running head(s) glued to page text" if glued else ""))
    if getattr(a, "drop_epigraphs", False):
        n = drop_epigraphs(doc)
        hints.append(f"--drop-epigraphs dropped {n} paragraph(s): quotation epigraphs and their attribution lines")
    if getattr(a, "min_para_words", None):
        n = drop_short_paras(doc, a.min_para_words)
        hints.append(f"--min-para-words dropped {n} short paragraph(s); figure captions and list items can go too")
    if getattr(a, "drop_images", False):
        n = drop_images(doc)
        hints.append(f"--drop-images removed {n} image marker(s); `RW image` still writes a picture")
    lang_dropped = filter_lang(doc, a.lang) if getattr(a, "lang", None) else None
    if not any(s.words() for s in doc.sections):   # a scan's pages are sections with no words (L-011)
        print(doc_head(doc))
        for n in doc.notes:
            print(f"note: {n}")
        print("(no text found)")
        return 0
    if a.chapter:
        a.section = chapter_selector(doc, a.chapter)
    idx = select(doc, a.section, a.title) if (a.section or a.title) else list(range(1, len(doc.sections) + 1))
    added = []
    for i in list(idx):   # a chapter's title page and its body are often separate sections (L-001)
        short = a.title and not a.section and doc.sections[i - 1].words() < SHORT_WORDS
        if (a.with_next or short) and i < len(doc.sections) and i + 1 not in idx:
            idx.insert(idx.index(i) + 1, i + 1)
            added.append(i + 1)
    if getattr(a, "headings", False):
        print("\n".join(heading_lines(doc, idx)))
        print(f"jump to one: rw.py read FILE --section N --at-para P{flags_used(a)}")
        return 0
    if a.max_words is not None and a.max_words < 1:
        raise RWError("--max-words must be 1 or more")
    if lang_dropped is not None:
        hints.append(f"--lang {a.lang} dropped {fmt_n(sum(lang_dropped.get(i, 0) for i in idx))} paragraph(s) in the selection: "
                     f"other languages, ties and fragments under {LANG_SHORT} words")
    if skipped is not None:
        hints.insert(0, code_note(doc, skipped, idx))
    flags = "".join(f for f, on in ((" --skip-code", getattr(a, "skip_code", False)),
                                   (f" --max-row-words {getattr(a, 'max_row_words', '')}", getattr(a, "max_row_words", None)),
                                    (" --strip-boilerplate", getattr(a, "strip_boilerplate", False)),
                                    (" --drop-repeated", getattr(a, "drop_repeated", False)),
                                    (" --drop-epigraphs", getattr(a, "drop_epigraphs", False)),
                                   (" --drop-images", getattr(a, "drop_images", False)),
                                   (f" --min-para-words {getattr(a, 'min_para_words', '')}", getattr(a, "min_para_words", None)),
                                    (f" --lang {getattr(a, 'lang', '')}", getattr(a, "lang", None)),
                                    (" --compact", getattr(a, "compact", False)),
                                    (" --format md", a.format == "md"),
                                    (f" --until {shlex.quote(getattr(a, 'until_re', None) or '')}", getattr(a, "until_re", None))) if on)
    shape = compact_text if getattr(a, "compact", False) else (lambda t: t)
    until_re = None
    if getattr(a, "until_re", None):
        try:
            until_re = re.compile(a.until_re, re.M)
        except re.error as e:
            raise RWError(f"--until: bad regex: {e}")
    no_until = []

    def cut_until(raw: str, i: int) -> str:
        """A section up to its first --until match. The search starts after the section's header and title, so a
        pattern that also names the section cannot empty it; no match prints the section whole and is reported."""
        if not until_re:
            return raw
        pos = raw.find("\n\n") + 2
        nxt = raw.find("\n\n", pos)
        if nxt >= 0 and clean(raw[pos:nxt].lstrip("# ")) == clean(doc.sections[i - 1].title):   # the title as a first paragraph
            pos = nxt + 2
        m = until_re.search(raw, pos)
        if not m:
            no_until.append(i)
            return raw
        return raw[:m.start()].rstrip() + "\n"

    def note_until():
        if no_until:
            shown = ",".join(map(str, no_until[:10])) + (",..." if len(no_until) > 10 else "")
            hints.append(f"--until {a.until_re!r}: no match in {len(no_until)} section(s) ({shown}), printed whole")
    lead = leadin_hint(doc, idx)
    if lead:
        hints.append(lead)
    if getattr(a, "out_dir", None):   # one file per section: a reader agent opens only the ones it needs
        os.makedirs(a.out_dir, exist_ok=True)
        ext = "md" if a.format == "md" else "txt"
        total = 0
        for i in idx:
            body = shape(cut_until(compose(doc, [i], a.format, a.max_words, flags), i))
            slug = re.sub(r"[^a-z0-9]+", "-", doc.sections[i - 1].title.lower()).strip("-")[:40] or "section"
            path = os.path.join(a.out_dir, f"{i:03d}-{slug}.{ext}")
            write_out(path, body)
            total += len(body)
            print(f"{path}  {fmt_n(len(body))} chars (~{fmt_n(len(body) // 4)} tokens)")
        print(f"wrote {len(idx)} section file(s), {fmt_n(total)} chars (~{fmt_n(total // 4)} tokens) to {a.out_dir}")
        note_until()
        shown = [h for h in hints if h.startswith(("--lang", "--until", "section "))]
        if shown and not getattr(a, "quiet", False):
            print("[readwright: " + "; ".join(shown) + "]")
        return 0
    each = getattr(a, "each_chars", None)
    if each is not None and each < 1:
        raise RWError("--each-chars must be 1 or more")
    from_re = None
    if getattr(a, "from_re", None):
        if a.at_para:
            raise RWError("--from and --at-para both set the start; use one")
        try:
            from_re = re.compile(a.from_re, re.M)
        except re.error as e:
            raise RWError(f"--from: bad regex: {e}")
    if from_re:   # the end of each section from the match on: chapter summaries without the chapters
        parts = []
        for i in idx:
            body = shape(compose(doc, [i], a.format, a.max_words, flags))
            m = from_re.search(body, body.find("\n") + 1 if body.startswith("=== [") else 0)   # never match the header line, which holds the title
            if m:
                end = until_re.search(body, m.end()) if until_re else None
                if until_re and not end:
                    no_until.append(i)
                piece = body[m.start():end.start() if end else None]
                if each and each >= 1 and len(piece) > each:
                    piece = clean_cut(piece[:each]).rstrip("\n") + "\n"
                parts.append(f"=== [{i}] {doc.sections[i - 1].title} ===\n{piece.rstrip()}\n\n")
        if not parts:
            raise RWError(f"--from {a.from_re!r}: no match in the {len(idx)} selected section(s)")
        text = "".join(parts)
    elif each and not a.at_para:   # several sections in one call, each cut on its own so a long one cannot crowd out the rest
        parts = []
        for i in idx:
            body = shape(cut_until(compose(doc, [i], a.format, a.max_words, flags), i))
            if len(body) > each:
                cut = clean_cut(body[:each]).rstrip("\n")
                body = (f"{cut}\n[readwright: section {i} cut at chars 0-{fmt_n(len(cut))} of {fmt_n(len(body))}; "
                        f"continue with --section {i} --offset {len(cut)}{flags}]\n\n")
            parts.append(body)
        text = "".join(parts)
    elif until_re:
        text = shape("\n".join(cut_until(compose(doc, [i], a.format, a.max_words, flags), i) for i in idx))
    else:   # with a start (--offset, --at-para) the word cap counts from there, not from the section top (empty output, 2026-11-07)
        text = shape(compose(doc, idx, a.format, None if (a.offset or a.at_para) else a.max_words, flags))
    note_until()

    def para_start() -> int:   # --at-para: where that paragraph starts in the text as printed, compact or not
        if not a.section:
            raise RWError("--at-para needs --section N")
        po = para_offsets(doc, idx[0], a.format)
        if not 1 <= a.at_para <= len(po):
            raise RWError(f"--at-para {a.at_para}: section {idx[0]} has {len(po)} paragraphs")
        off = po[a.at_para - 1]
        if getattr(a, "compact", False):   # grep counts paragraphs of the full layout; map the offset onto the compact text
            off = len(compact_text(compose(doc, idx, a.format, None, flags)[:off]))
        if until_re and off >= len(text):
            raise RWError(f"--until {a.until_re!r} matches before paragraph {a.at_para} of section {idx[0]}")
        return off

    if a.out:   # --at-para counts here too (it was ignored with --out, 2026-11-07)
        full, start = len(text), (a.offset or 0) + (para_start() if a.at_para else 0)
        text = text[start:]
        cut = bool(a.max_chars) and len(text) > a.max_chars
        if cut:   # same clean break as the stdout path, and say where to resume (a reader could not tell it was cut)
            text = clean_cut(text[:a.max_chars])
        write_out(a.out, text)
        print(f"wrote {fmt_n(len(text))} chars ({fmt_n(len(text.split()))} words, ~{fmt_n(len(text) // 4)} tokens) "
              f"from {len(idx)} section(s) to {a.out}")
        if cut:
            end = start + len(text)
            print(f"[readwright: cut at chars {fmt_n(start)}-{fmt_n(end)} of {fmt_n(full)}; write the rest with "
                  f"--offset {end}, or drop --max-chars to write it all]")
        if hints and not getattr(a, "quiet", False):
            print("[readwright: " + "; ".join(hints) + "]")
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
    if start and start >= len(text):
        raise RWError(f"--offset {start} is past the end: the selection has {len(text)} characters")
    if a.at_para:
        start += para_start()
    if start >= len(text):
        raise RWError(f"the start ({start}) is past the end: the selection has {len(text)} characters")
    word_cap = False
    if a.max_words and (a.offset or a.at_para):   # cap the words from the start point
        m = list(re.finditer(r"\S+", text[start:start + limit + 1]))
        if len(m) > a.max_words:
            limit, word_cap = m[a.max_words - 1].end() + 1, True
    piece = text[start:start + limit]
    if start + limit < len(text) and not word_cap:
        piece = clean_cut(piece)
    sys.stdout.write(piece)
    end = start + len(piece)
    if end < len(text):
        if not piece.endswith("\n"):
            sys.stdout.write("\n")
        rest = (f"show the rest with --offset {start} --max-chars {len(text) - start}" if start
                else f"show it all with --max-chars {len(text)}")
        # say why fewer chars than asked came back: a reader took the short cut for a bug (Roads, 2026-11-07)
        short = (f" (cut at --max-words {a.max_words})" if word_cap
                 else f" (cut at a break, {fmt_n(limit - len(piece))} short of --max-chars)" if len(piece) < limit else "")
        print(f"[readwright: shown chars {fmt_n(start)}-{fmt_n(end)} of {fmt_n(len(text))}{short}; continue with "
              f"--offset {end}, {rest}, or write it all with --out FILE]")
    if added and not a.with_next:
        hints.append(f"the title matched a short section, so the section after it was added ({', '.join(map(str, added))}): "
                     f"a chapter's body often follows its title page; use --section to read exactly one section")
    last = idx[-1]
    nxt = doc.sections[last] if last < len(doc.sections) else None
    if (nxt is not None and last + 1 not in idx and sum(doc.sections[i - 1].words() for i in idx) < SHORT_WORDS
            and continues(doc, last, idx)):   # a chapter opener or a split section, not every small subsection
        hints.append(f"the selection is short; the text may continue in section {last + 1}: {nxt.title} "
                     f"({fmt_n(nxt.words())} words), read it with --section {last + 1}")
    if hints and not getattr(a, "quiet", False):   # one combined line at the end, however many sections were read
        print("[readwright: " + "; ".join(hints) + "]")
    return 0


def leadin_hint(doc: Doc, idx: list) -> str:
    """Name the sections a selection's lead-in points to: an encyclopedia entry that ends 'Here is a list of
    techniques:' keeps its list in the subsections after it, so a reader took the list for lost text
    (The Sound Effects Bible ch. 18, 2026-11-07)."""
    found = []
    for i in idx:
        s = doc.sections[i - 1]
        last = next((p.text.strip() for p in reversed(s.paras) if p.text.strip()), "")
        if not last.endswith(":") or len(last.split()) < 3 or i >= len(doc.sections) or i + 1 in idx:
            continue
        j = i
        while j < len(doc.sections) and doc.sections[j].level > s.level:   # the subsections under this one
            j += 1
        end = max(j, i + 1)
        found.append(f"{i + 1}" if end == i + 1 else f"{i + 1}-{end}")
        if len(found) >= 5:
            break
    if not found:
        return ""
    return ("section ends on a lead-in (a colon) whose list or entries follow in the next sections: read "
            + ", ".join(found) + " with --section")


TITLE_PAGE_WORDS = 60   # a selection this short is a title page or an epigraph, so the next section is the text


def continues(doc: Doc, last: int, idx: list) -> bool:
    """True when section last+1 probably carries on section last: the selection is only a title page, or the next
    section is untitled, marked continued, or repeats the last one's title."""
    if sum(doc.sections[i - 1].words() for i in idx) < TITLE_PAGE_WORDS:
        return True
    cur, nxt = doc.sections[last - 1], doc.sections[last]

    def key(t):
        return re.sub(r"\W+", " ", re.sub(r"(?i)\(?\bcont(inued|'d|\.)?\)?\s*$", "", t)).strip().lower()
    if not nxt.title.strip() or nxt.title.startswith("(untitled") or re.search(r"(?i)\bcont(inued|'d)\b", nxt.title):
        return True
    return key(nxt.title) == key(cur.title)


def chapter_key(title: str) -> str:
    """'Chapter 4: The Myth of Meritocracy' -> 'chapter 4'; other titles as they are, lower case."""
    m = re.match(r"\s*((?:chapter|part)\s+[\divxlc]+)\b", title, re.I)
    return clean(m.group(1)).lower() if m else clean(title.split(":")[0]).lower()


def cmd_note(a) -> int:
    """The endnote a marker like [39] in section S points at: notes restart per chapter, so the chapter is needed."""
    doc = load(a.file, a.member, a.via)
    src = select(doc, a.section, None)
    if len(src) != 1:
        raise RWError("give the one section the marker is in (--section N)")
    key = chapter_key(doc.sections[src[0] - 1].title)
    notes = [s for s in doc.sections if NOTES_TITLE.match(s.title)]
    if not notes:
        raise RWError("no notes section (titled Notes, Endnotes or References) in the outline")
    num = re.compile(rf"^\[?{a.number}[\].)]?\s")
    blocks, current, seen = {}, "", []
    for s in notes:
        for p in s.paras:
            if p.kind == "h" or (len(p.text) < 80 and re.match(r"^(?:chapter|part)\s+[\divxlc]+\b", p.text, re.I)):
                current = chapter_key(p.text)
                if not NOTES_TITLE.match(current) and current not in seen:
                    seen.append(current)
            elif num.match(p.text):
                blocks.setdefault(current, p.text)
    hit = blocks.get(key) or (blocks.get("") if len(blocks) == 1 else None)
    if not hit:
        have = ", ".join(seen[:12]) + (", ..." if len(seen) > 12 else "") if seen else "none"
        raise RWError(f"note {a.number} not found under '{key}' (note headings seen: {have})")
    print(f"[{key}, note {a.number}] {hit[:a.width]}")
    return 0


GLOSSARY_TITLE = re.compile(r"^\s*(glossary|key terms|terms|definitions)\b", re.I)
TERM_SPLIT = re.compile(r"^(.{1,60}?)(?:\s*[:—–]\s+|\s+-\s+|\s+(?=(?:A|An|The|[A-Z][a-z]+)\s))(.*)$")


def glossary_term(text: str):
    """(headword, definition) for a glossary paragraph: `Term: def`, `Term - def`, or a run-together `Backlight A process...`."""
    m = TERM_SPLIT.match(text.strip())
    if not m or len(m.group(2)) < 15:
        return None
    return m.group(1).strip(" .,;"), m.group(2).strip()


def cmd_image(a) -> int:
    """Write a picture the text marks `[image omitted: NAME]` to a file, so a table or formula set as an image can be looked at."""
    load(a.file)
    calibre = cache_path(a.file, "calibre", ".epub")
    src = calibre if calibre.exists() else a.file
    if not zipfile.is_zipfile(src):
        raise RWError("no named pictures to pull out here; `image` works on EPUB, DOCX and calibre-converted files")
    want = posixpath.basename(a.name)
    with zipfile.ZipFile(src) as z:
        hits = [n for n in z.namelist() if posixpath.basename(n) == want and not n.endswith("/")]
        if not hits:
            raise RWError(f"no picture named {want} in this file")
        os.makedirs(a.out_dir, exist_ok=True)
        out = os.path.join(a.out_dir, want)
        with open(out, "wb") as f:
            f.write(z.read(hits[0]))
    print(out)
    return 0


def cmd_terms(a) -> int:
    """Headwords of a glossary: the sections titled Glossary (or --section), one term per line with its definition's opening."""
    doc = load(a.file, a.member, a.via)
    src = select(doc, a.section, None) if a.section else [i + 1 for i, s in enumerate(doc.sections) if GLOSSARY_TITLE.match(s.title)]
    if not src:
        raise RWError("no section titled Glossary, Key terms or Definitions; give --section N")
    n = 0
    for i in src:
        s = doc.sections[i - 1]
        for p in s.paras:
            if p.kind == "h" or GLOSSARY_TITLE.match(p.text):
                continue
            t = glossary_term(p.text)
            if t:
                n += 1
                print(f"{t[0]}  | {t[1][:a.width]}")
    print(f"--- {n} terms in section {', '.join(map(str, src))}; read one in full with grep FILE '^TERM'")
    return 0


# ---------------------------------------------------------------- rank: which section to read first (BM25)

RANK_STOP = set("a an and are as at be but by for from has have how i if in into is it its of on or that the their then "
                "there these they this to was were what when where which who why will with you your".split())


def rank_terms(text: str) -> list:
    """Lowercased words with stop words dropped and a light suffix strip, so 'shingles' meets 'shingle'.
    Plain suffix rules, not Porter: a query and a book stemmed the same way is all ranking needs."""
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in RANK_STOP or len(w) < 2:
            continue
        for suf in ("ings", "ing", "ies", "ied", "ed", "es", "s"):
            if len(w) > len(suf) + 2 and w.endswith(suf) and not w.endswith("ss"):
                w = w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
                break
        if len(w) >= 4 and w.endswith("e"):   # shingle, shingles and shingling all meet at shingl
            w = w[:-1]
        out.append(w)
    return out


def bm25(docs: list, query: list, k1: float = 1.2, b: float = 0.75) -> list:
    """Okapi BM25 score of each term list in docs for the query terms (Manning et al. 2008, sec. 11.4.3)."""
    import math
    n = len(docs)
    avg = (sum(len(d) for d in docs) / n) if n else 0
    counts = [collections.Counter(d) for d in docs]
    df = {t: sum(1 for c in counts if t in c) for t in set(query)}
    scores = []
    for d, c in zip(docs, counts):
        sc = 0.0
        for t in set(query):
            tf = c.get(t, 0)
            if tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                sc += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / (avg or 1)))
        scores.append(sc)
    return scores


def back_matter_start(doc) -> int:
    """1-based number of the first back-matter section (a bare NOTES, BIBLIOGRAPHY or INDEX title at least 30% of the
    way through the words), or 0. Everything after it counts as back matter: per-chapter notes files repeat the chapter
    titles and outscore them in rank (The Great Wave, 2026-11-03)."""
    total = sum(s.words() for s in doc.sections) or 1
    seen = 0
    for i, s in enumerate(doc.sections, 1):
        if seen >= 0.3 * total and re.fullmatch(r"(end ?notes|notes(: .*)?|bibliography|references|works cited|index)", s.title.strip(), re.I):
            return i
        seen += s.words()
    return 0


def cmd_rank(a) -> int:
    if not os.path.isfile(a.file) and any(os.path.isfile(q) for q in a.query):
        raise RWError(f"no such file: {a.file}; the file goes first: rank FILE WORDS")
    doc = load(a.file, a.member, a.via)
    if getattr(a, "strip_boilerplate", False):
        strip_furniture(doc)
    if doc.fmt == "zip":
        raise RWError("this is a zip archive; pick a member with --member NAME")
    query = rank_terms(" ".join(a.query))
    if not query:
        raise RWError("the query has no words left after stop words; name the topic, e.g. rank FILE near duplicate shingle")
    idx = select(doc, a.section, a.title) if (a.section or a.title) else range(1, len(doc.sections) + 1)
    if a.body and (cut := back_matter_start(doc)):
        idx = [i for i in idx if i < cut]
    units = []   # (section, paragraph index or None, terms)
    for i in idx:
        s = doc.sections[i - 1]
        if a.paras:
            units += [(i, j, rank_terms(p.text)) for j, p in enumerate(s.paras)]
        else:
            units.append((i, None, rank_terms(" ".join(p.text for p in s.paras))))
    scores = bm25([u[2] for u in units], query, a.k1, a.b)
    uq = list(dict.fromkeys(query))
    missing = [t for t in uq if not any(t in u[2] for u in units)]
    hit = [k for k, sc in enumerate(scores) if sc > 0]
    rows = []
    for k in sorted(hit, key=lambda k: -scores[k])[: a.top]:
        i, j, terms = units[k]
        s = doc.sections[i - 1]
        c = collections.Counter(terms)
        r = {"section": i, "title": s.title, "para": None if j is None else j + 1, "score": round(scores[k], 2),
             "words": s.words() if j is None else len(s.paras[j].text.split()), "terms": {t: c[t] for t in uq if c.get(t)}}
        if j is not None:
            r["text"] = s.paras[j].text[: a.width]
        rows.append(r)
    if a.json:
        print(json.dumps({"query": uq, "missing": missing, "results": rows}, ensure_ascii=False, indent=1))
        return 0 if rows else 1
    for r in rows:
        terms = ", ".join(f"{t} {n}" for t, n in r["terms"].items())
        where = f"[{r['section']}] {r['title']}" + (f" | para {r['para']}" if r["para"] else "")
        print(f"{r['score']:>7}  {where}  ({r['words']:,} w; {terms})")
        if "text" in r:
            print("         " + " ".join(r["text"].split()) + (" ..." if len(r["text"]) >= a.width else ""))
    print(f"[query terms: {' '.join(uq)}" + (f"; not in the book: {' '.join(missing)}" if missing else "")
          + f"; showed {len(rows)} of {len(hit)} with a hit"
          + ("; read the top one with read --section N, or add --paras for paragraphs" if rows and not a.paras else "") + "]")
    return 0 if rows else 1


def smart_case(pattern: str, fixed: bool = False) -> bool:
    """True when the pattern has no capital letter outside a regex escape (\\S, \\W, \\B), so it should match
    any case (L-038 `grep-smart-case`)."""
    return not re.search(r"[A-Z]", pattern if fixed else re.sub(r"\\.", "", pattern))


def loose_typography(pat: str) -> str:
    """Let a hyphen or apostrophe in a pattern match its typographic forms (L-057).

    Books print U+2010 and U+2019 where a typed pattern has - and '. Character classes and inline flags stay as written."""
    out, i, in_class = [], 0, False
    while i < len(pat):
        c = pat[i]
        escaped = c == "\\" and i + 1 < len(pat)
        lit = pat[i + 1] if escaped else c
        if not in_class and lit in "-‐‑" and not re.search(r"\(\?[a-zA-Z]*$", "".join(out)):
            out.append("[-‐‑­]")
        elif not in_class and lit in "'’":
            out.append("['’]")
        else:
            out.append(pat[i:i + 2] if escaped else c)
            if not escaped and c == "[":
                in_class = True
                if pat[i + 1:i + 2] == "^":
                    out.append("^")
                    i += 1
                if pat[i + 1:i + 2] == "]":
                    out.append("]")
                    i += 1
            elif not escaped and c == "]":
                in_class = False
        i += 2 if escaped else 1
    return "".join(out)


def cmd_grep(a) -> int:
    if not os.path.isfile(a.file) and os.path.isfile(a.pattern):   # grep "champion list" FILE (Manning IR reader, 2026-11-03)
        raise RWError(f"no such file: {a.file}; the file goes first: grep FILE PATTERN")
    doc = load(a.file, a.member, a.via)
    if getattr(a, "strip_boilerplate", False):
        strip_furniture(doc)
    if doc.fmt == "zip":
        raise RWError("this is a zip archive; pick a member with --member NAME")
    skipped = skip_code(doc) if getattr(a, "skip_code", False) else None
    if getattr(a, "lang", None):
        filter_lang(doc, a.lang)
    pat = re.escape(a.pattern) if a.fixed else a.pattern
    try:
        if smart_case(a.pattern, a.fixed) and not getattr(a, "case_sensitive", False):
            a.ignore_case = True   # smart case, as in ripgrep -S: 'consumer price index' finds 'Consumer Price Index'
        rx = re.compile(loose_typography(pat), re.I if a.ignore_case else 0)
    except re.error as e:
        raise RWError(f"bad pattern: {e}")
    idx = select(doc, a.section, a.title) if (a.section or a.title) else range(1, len(doc.sections) + 1)
    code_skipped = code_note(doc, skipped, idx) if skipped is not None else ""
    hits = []
    per = {}
    for i in idx:
        s = doc.sections[i - 1]
        for j, p in enumerate(s.paras):
            ms = list(rx.finditer(p.text))
            if ms:
                per[i] = per.get(i, 0) + len(ms)
                hits.append((i, j, ms[0]))
    capped = 0
    if getattr(a, "per_section", 0):   # one code-heavy section took every hit (Wei, Advanced RAG reader, 2026-11-03)
        seen, kept = {}, []
        for h in hits:
            seen[h[0]] = seen.get(h[0], 0) + 1
            if seen[h[0]] <= a.per_section:
                kept.append(h)
        capped, hits = len(hits) - len(kept), kept
    pcache = {}

    def off(i, j, m):
        if i not in pcache:
            pcache[i] = para_offsets(doc, i, a.format)
        return pcache[i][j] + m.start()
    total = sum(per.values())
    if a.json:
        print(json.dumps({"pattern": a.pattern, "matches": total, "paragraphs": len(hits),
                          "by_section": [{"n": i, "title": doc.sections[i - 1].title, "count": c} for i, c in per.items()],
                          "hits": [{"section": i, "title": doc.sections[i - 1].title, "para": j + 1, "offset": off(i, j, m),
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
        print(f"--- [{i}] {s.title} | para {j + 1}/{len(s.paras)} | offset {off(i, j, m)}")
        lo, hi = max(0, j - a.context), min(len(s.paras), j + max(a.context, a.after) + 1)
        if a.context:   # a boxed callout gives one paragraph per PDF line: widen context over short lines
            budget = 8
            while budget and lo > 0 and len(s.paras[lo].text) < SHORT_LINE:
                lo, budget = lo - 1, budget - 1
            budget = 8
            while budget and hi < len(s.paras) and len(s.paras[hi - 1].text) < SHORT_LINE:
                hi, budget = hi + 1, budget - 1
        for k in range(lo, hi):
            t = s.paras[k].text
            if k == j:
                print("> " + trim(t, m, a.width))
            elif j < k <= j + a.after:   # --after: the code block or list after a prose hit, up to --width
                print("  " + (t if len(t) <= a.width else t[:a.width] + " ...").replace("\n", "\n  "))
            else:
                print("  " + (t if len(t) <= a.width // 2 else t[:a.width // 2] + " ..."))
    shown = min(len(hits), a.max)
    if hits:   # offset is the match, usually mid-paragraph; --at-para opens the paragraph (L-grep-offset-is-the-match)
        i0, j0, _ = hits[0]
        print(f"[readwright: a hit's offset is the match itself; to read from the start of its paragraph use read --section {i0} --at-para {j0 + 1}]")
    if not hits and not a.ignore_case:   # "value key" missed "Value keying" (L-019)
        rxi = re.compile(pat, re.I)
        n_i = sum(len(rxi.findall(p.text)) for i in idx for p in doc.sections[i - 1].paras)
        if n_i:
            code_skipped = (code_skipped + "; " if code_skipped else "") + f"{n_i} matches with -i (grep is case-sensitive)"
    if capped:
        code_skipped = (code_skipped + "; " if code_skipped else "") + f"{capped} paragraphs past --per-section {a.per_section} not shown"
    print(f"[{total} matches in {len(hits) + capped} paragraphs across {len(per)} sections; showed {shown}"
          + (f"; raise --max, use --count, or narrow with --section N-M" if len(hits) > a.max else "")
          + (f"; {code_skipped}" if code_skipped else "") + "]")
    return 0 if hits else 1


SHORT_LINE = 60   # grep -C: context grows past paragraphs shorter than this, up to 8 more each side


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
    p = sub.add_parser("toc", aliases=["outline"], help="numbered sections with titles and word counts")
    common(p)
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--ids", action="store_true", help="also print each section's id (file#fragment, page, sheet)")
    p.add_argument("--hide", metavar="REGEX", help="leave out sections whose title matches (Exercises, audio tracks); numbers stay the same")
    p.add_argument("--depth", type=int, default=None, help="only sections at indent depth N or less (1 = parts and chapters); word counts include the sections below")
    p.add_argument("--code", action="store_true", help="also show how many of each section's words are code blocks (EPUB, HTML, Markdown): pick prose sections before reading")
    p.add_argument("--group", action="store_true", help="PDF with no outline: fold pages that share a running head into page ranges (chapters)")
    p = sub.add_parser("read", help="text of chosen sections")
    common(p, False)
    p.add_argument("--section", "-s", action="append", help="N, N-M, N- or N,M (numbers from toc); repeat to add more")
    p.add_argument("--title", "-t", help="regex matched against section titles and ids (case-insensitive)")
    p.add_argument("--chapter", help="N, N-M or N,M: sections by the chapter number printed in their titles, not toc positions")
    p.add_argument("--max-chars", type=int, default=None, help=f"cap on characters printed (default {DEFAULT_MAX_CHARS})")
    p.add_argument("--offset", type=int, default=0, help="start this many characters into the selection")
    p.add_argument("--each-chars", type=int, default=None, metavar="N", help="with several sections: cap each one at N "
                   "chars (a resume line per cut section); --max-chars still caps the total")
    p.add_argument("--from", dest="from_re", default=None, metavar="REGEX",
                   help="print each selected section from its first match on, skip sections without one ('Key takeaways' across chapters); case-sensitive, (?i) to ignore case; ^ and $ match at lines")
    p.add_argument("--until", dest="until_re", default=None, metavar="REGEX",
                   help="print each selected section up to, not including, its first match (after --from's match when both are set); a section without one prints whole. Case and ^ $ as --from")
    p.add_argument("--at-para", type=int, default=None, help="with --section: start at this paragraph (numbers from grep)")
    p.add_argument("--out", help="write the selection to this file instead of stdout")
    p.add_argument("--out-dir", help="write each selected section to its own file in this folder (NNN-title.txt) and list their sizes")
    p.add_argument("--format", choices=["txt", "md"], default="txt")
    p.add_argument("--with-next", action="store_true", help="also read the section after each selected one")
    p.add_argument("--compact", action="store_true", help="no blank line between paragraphs (offsets then count the compact text; pass it again with --offset)")
    p.add_argument("--max-words", type=int, default=None, help="show at most this many words of each section (batch reads)")
    p.add_argument("--strip-boilerplate", action="store_true", help="drop lines repeated on most pages (PDF footers, page numbers, running headers)")
    p.add_argument("--skip-code", action="store_true", help="drop code blocks (<pre> or a code-classed div in EPUB and HTML, fenced Markdown; not PDF) and say how many words went")
    p.add_argument("--max-row-words", type=int, metavar="N", help="read only: cut table rows over N words and mark the cut (books that set chat replies or samples in tables)")
    p.add_argument("--drop-repeated", action="store_true", help="drop short paragraphs that recur in 30%% or more of "
                   "sections, verbatim or with the same last four words (image credits, copyright notices)")
    p.add_argument("--drop-images", action="store_true", help="remove [image omitted: NAME] marker lines (a book with many figures)")
    p.add_argument("--min-para-words", type=int, metavar="N", help="drop body paragraphs under N words: figure labels and notation debris in OCR text")
    p.add_argument("--drop-epigraphs", action="store_true", help="drop quotations of 80 words or fewer followed by a "
                   "dash attribution line of 8 words or fewer (both paragraphs)")
    p.add_argument("--lang", choices=sorted(LANG_WORDS), help="on a multilingual edition keep the paragraphs whose common "
                   "words favour this language; a footer says how many went")
    p.add_argument("--headings", action="store_true", help="list only the headings of the selected sections, indented "
                   "by level, with paragraph numbers for --at-para and the words under each")
    p.add_argument("--quiet", "-q", action="store_true", help="no [readwright: ...] advice lines (cut footers stay)")
    p = sub.add_parser("grep", help="regex search with section and paragraph context")
    common(p)
    p.add_argument("pattern")
    p.add_argument("-C", "--context", type=int, default=0, help="paragraphs of context")
    p.add_argument("-A", "--after", type=int, default=0, help="paragraphs after each hit, shown up to --width "
                   "(the code block after the prose that names it)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="match any case (the default when the pattern is all lower case)")
    p.add_argument("--case-sensitive", action="store_true", help="match case exactly even for an all-lower-case pattern")
    p.add_argument("-F", "--fixed", action="store_true", help="pattern is a plain string")
    p.add_argument("--max", type=int, default=20, help="paragraphs shown (default 20)")
    p.add_argument("--per-section", type=int, default=0, metavar="N",
                   help="at most N paragraphs from each section, so one busy section does not take every hit")
    p.add_argument("--width", type=int, default=600, help="characters shown per matching paragraph")
    p.add_argument("--count", action="store_true", help="only counts per section")
    p.add_argument("--section", "-s", action="append", help="as for read; repeat to add more")
    p.add_argument("--title", "-t")
    p.add_argument("--format", choices=["txt", "md"], default="txt", help="read format the printed offsets count in")
    p.add_argument("--strip-boilerplate", action="store_true", help="as for read; use it on both so paragraph numbers agree")
    p.add_argument("--skip-code", action="store_true", help="as for read: search prose only; use it on both so paragraph numbers agree")
    p.add_argument("--lang", choices=sorted(LANG_WORDS), help="as for read; use it on both so paragraph numbers agree")
    p = sub.add_parser("rank", help="sections (or paragraphs) ranked by BM25 for a few topic words: which to read first")
    common(p)
    p.add_argument("query", nargs="+", help="topic words; stop words and plural or -ing endings are folded")
    p.add_argument("--paras", action="store_true", help="rank paragraphs instead of sections")
    p.add_argument("--body", action="store_true", help="leave out everything from a NOTES, BIBLIOGRAPHY or INDEX section on")
    p.add_argument("--top", "--limit", dest="top", type=int, default=10, help="results shown (default 10)")
    p.add_argument("--width", type=int, default=300, help="characters of each paragraph shown with --paras")
    p.add_argument("--k1", type=float, default=1.2, help="BM25 term-frequency saturation (1.2 to 2.0)")
    p.add_argument("--b", type=float, default=0.75, help="BM25 length normalisation (0 none, 1 full)")
    p.add_argument("--section", "-s", action="append", help="as for read; repeat to add more")
    p.add_argument("--title", "-t")
    p.add_argument("--strip-boilerplate", action="store_true", help="as for read")
    p = sub.add_parser("note", help="the endnote a marker like [39] points at (notes restart per chapter)")
    common(p, False)
    p.add_argument("number", type=int)
    p.add_argument("--section", "-s", required=True, help="the section the marker was read in")
    p.add_argument("--width", type=int, default=600, help="characters shown")
    p = sub.add_parser("image", help="write a picture marked [image omitted: NAME] to a file, to look at a table or formula set as an image")
    p.add_argument("file")
    p.add_argument("name")
    p.add_argument("--out-dir", default=".", help="folder to write it in")
    p = sub.add_parser("terms", help="a glossary's headwords, one per line with the start of each definition")
    common(p, False)
    p.add_argument("--section", "-s", help="glossary section(s); default: those titled Glossary")
    p.add_argument("--width", type=int, default=60, help="definition characters shown")
    p = sub.add_parser("dump", help="whole text to a file with section markers")
    common(p, False)
    p.add_argument("--out")
    p.add_argument("--format", choices=["txt", "md"], default="txt")
    p = sub.add_parser("ocr", help="OCR a scanned PDF or image-only EPUB once; info, toc, read and grep then use the text")
    p.add_argument("file")
    p.add_argument("--pages", help="only these pages, N or N-M (added to what is already kept)")
    p.add_argument("--dpi", type=int, default=200, help="render resolution (default 200)")
    p.add_argument("--batch", type=int, default=25, help="pages per render-and-OCR round; progress is saved after each")
    p.add_argument("--force", action="store_true", help="redo pages already OCR'd")
    p = sub.add_parser("page", help="render PDF pages to PNG files, to look at plates, tables or a doubtful text layer")
    p.add_argument("file")
    p.add_argument("pages", help="N, N-M or N,M")
    p.add_argument("--dpi", type=int, default=60, help="render resolution (default 60)")
    p.add_argument("--out-dir", default=".", help="folder to write them in")
    p = sub.add_parser("formats", help="supported formats and installed tools")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if isinstance(getattr(a, "section", None), list):   # --section 23 --section 24 means 23,24
        a.section = ",".join(a.section)
    CACHE_OFF = getattr(a, "no_cache", False)
    try:
        return {"info": cmd_info, "toc": cmd_toc, "outline": cmd_toc, "read": cmd_read, "grep": cmd_grep, "rank": cmd_rank, "image": cmd_image, "note": cmd_note, "terms": cmd_terms, "dump": cmd_dump,
                "ocr": cmd_ocr, "page": cmd_page, "formats": cmd_formats}[a.cmd](a)
    except RWError as e:
        print(f"readwright: {e}", file=sys.stderr)
        return EXIT_ERR
    except (zipfile.BadZipFile, OSError) as e:
        print(f"readwright: cannot read {getattr(a, 'file', '')}: {e}", file=sys.stderr)
        return EXIT_ERR


if __name__ == "__main__":
    sys.exit(main())
