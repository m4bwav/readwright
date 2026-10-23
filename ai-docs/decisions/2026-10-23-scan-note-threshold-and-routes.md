---
title: Scan note threshold and routes
kind: decision
status: active
date: 2026-10-23
tags: [pdf, epub, scans, ocr]
summary: why the scan note fires under 10 words a page, why EPUBs count sections, and what it names
---

# Scan note threshold and routes

## Decision

`rw.py` adds a `no text layer` note to a PDF or EPUB whose words per page fall under 10 (an EPUB counts sections, since it has no pages). The note names, in order: a same-name file in another format in the same folder, OCR (ocrmypdf when installed, else that none is), and a command that renders the first five pages at 60 dpi (mutool, else pdftoppm) for the agent's image reader. For an EPUB it says the page images are inside the zip.

## Why

- 83 real PDFs and EPUBs (a mixed folder of art books, Blender manuals, novels and AI books): the 6 scans had 0 words a page; the thinnest text book had 132. Any floor between 1 and 131 separates them; 10 leaves room for a scan with page numbers in a text layer.
- Words per section for EPUBs: the scanned EPUB had 2 sections holding 247 images; text EPUBs ran 159 to 6,695 words a section.
- The sibling copy comes first because it was what worked on the real books: a DjVu beside the scanned EPUB had OCR text that calibre extracts.
- No OCR is run or installed: the skill never installs anything, and the note says when nothing is installed.
- A partly scanned book (text on some pages) is not flagged. None of the 83 had one (the most empty pages in a text PDF was 10%), so no rule could be tested.

Related: builds on [../../skills/readwright/LEARNINGS.md](../../skills/readwright/LEARNINGS.md)
