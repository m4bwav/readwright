---
title: "readwright as its own stdlib CLI plugin: outline, then sections, then search"
kind: decision
status: active
date: 2026-09-29
verified: 2026-09-29
stale_after: never
tags: [design, formats, tokens, drm]
summary: read before adding a format, a command or an external tool, or moving work into an MCP server
---

# readwright as its own stdlib CLI plugin: outline, then sections, then search

## Context

On 2026-09-29 an agent needed chapters 14 and 15 of an EPUB novel. The only tool at hand, `epr -d book.epub`, dumped the whole 1.2 MB book (about 300k tokens) as text. Agents need an outline first, then only the sections they need, then search, without a whole book ever entering the context. Claude Code's Read tool already covers PDF by pages, images and notebooks, and separate docx, xlsx and pptx skills exist for writing Office files; nothing gave one reading interface across ebook and document formats.

## Decision

readwright is its own public plugin (m4bwav/readwright) with one skill and one CLI, `skills/readwright/scripts/rw.py`:

- Standard-library Python 3.10+, one file, cross-platform, UTF-8 and LF output. Built-in readers for EPUB, DOCX, ODF, PPTX, XLSX, FB2, HTML, text, Markdown, RST, RTF, CSV, TSV, JSON, EML and zip.
- Five verbs in the order an agent should use them: `info`, `toc`, `read` (by section number, range or title regex, capped by `--max-chars`, refusing whole-book reads), `grep` (paragraph context with section numbers), `dump` (to a file only).
- External tools (poppler, MuPDF, calibre, LibreOffice, antiword, pandoc, markitdown) are found at run time and never installed; their conversions are cached in the temp folder.
- DRM is detected from well-known markers and reported; there is no route to remove it. Macros and scripts are never run.
- Detection by magic bytes and zip contents, not extension.
- Launchers sit next to `rw.py`; no top-level `bin/` (Cowork refuses such plugins, per the everlast research R-20260927-1).
- Evergreen unit, tier moderate (converter releases are monthly, the EPUB spec moves slowly).

## Reasons

- Token cost: a toc line per section plus the chosen sections is a few thousand tokens against a whole novel's 150k to 300k.
- Portability: the standard library runs wherever the agent has Python, with no install step and nothing to vet.
- Evidence: the eval baseline (TESTS.md T-20260929-2) shows that without the skill the model writes its own zip-and-regex parser for each book; with it, two `rw.py` calls.

## Rejected

- Wrapping markitdown or pandoc as the main route: both convert whole files, need installs, and give no outline; they stay available through `--via`.
- An MCP server: EPUB-only MCP servers already exist (onebirdrocks/ebook-mcp, kajuberdut/epub-mcp); a CLI works in every agent with a shell and costs no always-on tool definitions.
- Borrowing from epy: GPL-3.0, incompatible with an MIT repo. epr (MIT) is credited, not copied.
- A top-level `bin/` wrapper folder (Cowork install failure).

## Consequences

The agent needs a shell and Python. Formats outside the standard library depend on what the machine has; `rw.py formats` reports it. Chapter openers split from their bodies are common in real EPUBs, so `read` points at the next section when a selection is short (LEARNINGS L-001).

Related: see also [../../skills/readwright/RESEARCH.md](../../skills/readwright/RESEARCH.md)
