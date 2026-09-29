---
name: readwright
description: "Read text out of ebooks and documents a section at a time instead of dumping the whole file into context: outline first, then only the chapters needed, then search. One command-line tool (standard-library Python) for EPUB, MOBI, AZW3, FB2, DOCX, ODT, RTF, PPTX, XLSX, HTML, EML, CSV, JSON, Markdown and zip archives of them, plus PDF and legacy DOC, XLS and PPT when poppler, calibre or LibreOffice is installed. Use whenever the user asks to read, quote, summarise, search or extract text from one of those files: 'read chapter 14 of this book', 'what does this document say about X', 'find every mention of Y in the novel', 'extract the text from this .docx', 'summarise this epub'. Also for a PDF when reading it by page ranges is awkward, and for 'refresh readwright' and 'is readwright stale'. Not for images, notebooks, PDFs the agent's own Read tool handles well, or writing and editing Office files."
metadata:
  version: "0.1.0"
---

# readwright

A novel is 150,000 to 300,000 tokens. Dumping it with a converter (`epr -d`, `pandoc -t plain`, `ebook-convert book.txt`) fills the context before the question is answered. readwright gives the agent a table of contents with word counts, then the chosen sections, then search results with section and paragraph numbers, so it reads what the task needs and nothing else.

`RW` below means `python "<this folder>/scripts/rw.py"` (`python3` on macOS and Linux). The launchers `scripts/rw.sh` and `scripts/rw.ps1` do the same. It needs Python 3.10 or newer and nothing else for the built-in formats; `RW formats` shows which external tools this machine has.

## Step 0: freshness

Read [evergreen.json](evergreen.json). If `contradiction` is set or today is on or after `next_due`, say so in one line, do the task, then refresh (MAINTENANCE.md). Converter versions and ebook formats change; the procedure below does not depend on them.

## Step 1: size it up

Run `RW info FILE`. It prints the detected format (from the file's bytes, not its extension), title, author, language, section count, words and approximate tokens (characters divided by 4). Under about 10,000 tokens, `RW read FILE` prints the whole text and you can stop here.

If info reports DRM, say so plainly and stop. readwright never removes DRM, and neither should you: suggest the store's own reader or a DRM-free copy from the seller. If it names a missing tool (pdftotext, calibre's ebook-convert, LibreOffice), pass on the install line it prints. Never install anything without the user's yes. For a PDF, the agent's own Read tool with page ranges is often the better route.

## Step 2: outline

Run `RW toc FILE`. Each line is `N. title (words w) [id]`, indented by level. EPUB titles come from the book's own navigation (nav document or NCX), DOCX and ODT titles from heading styles, HTML from h1 to h3, plain text and Markdown from headings or CHAPTER lines. Text with no structure is cut into parts of about 3,000 words. For a zip archive, toc lists the members; add `--member NAME` (or its number) to every later command.

Match the user's words to toc lines. "Chapter 14" usually means the line titled CHAPTER FOURTEEN, which in many ebooks holds only the chapter title and an epigraph: its body is the next section. The word counts show this (72 words, then 6,330).

## Step 3: read only what is needed

- `RW read FILE --section 43-44` (also `N`, `N-`, `N,M`) or `--title "REGEX"` (case-insensitive, matched against titles and ids).
- Every section starts with a header line: `=== [43/80] title | id ... | words | starts at word N of TOTAL (P%) ===`.
- Output stops at `--max-chars` (default 40,000). The last line then says where to continue: `--offset N`.
- A short selection ends with a hint naming the next section, since that is where the text usually continues.
- `read` without a selector refuses when the text is over the limit (exit code 2) and prints the toc instead. That refusal is the tool working: pick sections.
- `--format md` keeps headings and lists as Markdown; `--out FILE` writes the selection to a file.

## Step 4: search

`RW grep FILE "PATTERN" -C 1 --max 5` prints each matching paragraph with its section number and title, paragraph number and one paragraph of context on each side. Long paragraphs are trimmed around the match (`--width`). Use `-i` for case-insensitive and `-F` for a plain string; `--count` gives matches per section, the quickest way to find where a character or term appears. Exit code 1 means no match. Search before reading when the user asks where or whether something is mentioned.

## Step 5: whole book to a scratch file

For work that needs many passes over a long book (every scene with a character, a timeline), run `RW dump FILE --out <scratch>/book.txt` once. Then use your own search and read tools on that file, never `cat`. Section markers are lines starting `=== [N/`; `--format md` writes `<!-- readwright section N/... -->` comments with Markdown headings. Dump writes to stdout only when the text is under 40,000 characters. Put the file in the session's scratch or temp folder, never in the user's repository.

## Step 6: answer

Quote briefly. For a copyrighted book, summarise and quote a sentence or two at a time, never whole pages or chapters, even when the user owns the copy. Cite where each point came from (section number and title) so the user can check it. When a conversion note was printed (calibre, LibreOffice, pdftotext), mention that the text came through a converter if the wording matters.

## Formats

Read [references/formats.md](references/formats.md) when a format misbehaves, when the user asks what is supported, or before using `--via pandoc|markitdown`. It lists what each format reads, the external tools and their install lines, the DRM checks and the caps on huge files.

## Maintenance

Evergreen unit: [RESEARCH.md](RESEARCH.md), [CHANGELOG.md](CHANGELOG.md), [LEARNINGS.md](LEARNINGS.md), [TESTS.md](TESTS.md), state in [evergreen.json](evergreen.json), protocol in [MAINTENANCE.md](MAINTENANCE.md). Record a learning in LEARNINGS.md when a real file breaks the tool (wrong titles, missing text, a converter surprise), with the fix and a test in `tests/test_rw.py`.
