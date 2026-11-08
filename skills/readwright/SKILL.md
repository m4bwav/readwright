---
name: readwright
description: "Read text out of ebooks and documents a section at a time instead of dumping the whole file into context: outline first, then only the chapters needed, then search. One command-line tool (standard-library Python) for EPUB, MOBI, AZW3, FB2, DOCX, ODT, RTF, PPTX, XLSX, HTML, EML, CSV, JSON, Markdown and zip archives of them, plus PDF and legacy DOC, XLS and PPT when poppler, calibre or LibreOffice is installed. Use whenever the user asks to read, quote, summarise, search or extract text from one of those files: 'read chapter 14 of this book', 'what does this document say about X', 'find every mention of Y in the novel', 'extract the text from this .docx', 'summarise this epub'. Also for a PDF when reading it by page ranges is awkward, and for 'refresh readwright' and 'is readwright stale'. Not for images, notebooks, PDFs the agent's own Read tool handles well, or writing and editing Office files."
metadata:
  version: "0.67.0"
---

# readwright

A novel is 150,000 to 300,000 tokens. Dumping it with a converter (`epr -d`, `pandoc -t plain`, `ebook-convert book.txt`) fills the context before the question is answered. readwright gives the agent a table of contents with word counts, then the chosen sections, then search results with section and paragraph numbers, so it reads what the task needs and nothing else.

`RW` below means `python "<this folder>/scripts/rw.py"` (`python3` on macOS and Linux). The launchers `scripts/rw.sh` and `scripts/rw.ps1` do the same. It needs Python 3.10 or newer and nothing else for the built-in formats; `RW formats` shows which external tools this machine has.

## Step 0: freshness

Read [evergreen.json](evergreen.json). If `contradiction` is set or today is on or after `next_due`, say so in one line, do the task, then refresh (MAINTENANCE.md). Converter versions and ebook formats change; the procedure below does not depend on them.

Discord: a live channel is not a file; read it with everscout's `scripts/es_discord.py` (the user's own invited bot, everscout `kb/discord.md`). A channel export the user made (JSON or HTML) reads like any JSON or HTML file here.

## Step 1: size it up

Run `RW info FILE`. It prints the detected format (from the file's bytes, not its extension), title, author, language, section count, words and approximate tokens (characters divided by 4). Under about 6,000 tokens (25,000 characters), `RW read FILE` prints the whole text and you can stop here.

If info reports DRM, say so plainly and stop. readwright never removes DRM, and neither should you: suggest the store's own reader or a DRM-free copy from the seller. If it names a missing tool (pdftotext, calibre's ebook-convert, LibreOffice), pass on the install line it prints. Never install anything without the user's yes. For a PDF, the agent's own Read tool with page ranges is often the better route.

If info prints `note: no text layer`, the book is page images (a scan) and readwright has nothing to read. Take the routes the note names, in its order. First, a copy of the same book in another format beside it; a DjVu copy often carries OCR text. Then, for a PDF, `RW ocr FILE`: it renders the pages and runs the OCR built into Windows 10 and 11 (or tesseract where installed), about a second a page, saving after every 25 pages, and keeps the text in `~/.readwright/ocr/` so `info`, `toc`, `read` and `grep` on the same file use it from then on (`--pages N-M` for a few pages, `--force` to redo). Run a whole book in the background. OCR misreads some letters and has no headings, so sections are pages; check a quote against a page image. Last, a few pages rendered with `RW page FILE 1-5` (60 dpi, `--dpi`, `--out-dir`) and viewed with your own image reader. Ask before installing an OCR tool.

## Step 2: outline

Run `RW toc FILE`. Each line is `N. title (words w)`, indented by level; `--ids` adds each section's id (file and fragment, page, sheet), which you rarely need. EPUB titles come from the book's own navigation (nav document or NCX), DOCX and ODT titles from heading styles, HTML from h1 to h3, plain text and Markdown from headings or CHAPTER lines. Text with no structure is cut into parts of about 3,000 words. For a zip archive, toc lists the members; add `--member NAME` (or its number) to every later command.

Books that list each chapter number as its own near-empty section (Packt, some O'Reilly) are shown merged: `Ch. 12: Title`, printed under the title's section number (the number-only section is hidden but keeps its number and can still be read). `RW toc FILE --depth 1` prints only the top level (parts and chapters) with each line's words rolled up from the sections below it (`--depth 2` adds the next level; JSON gets `chapter` and `words_total`). Use it to count chapters instead of counting by hand. A PDF with no outline lists one section per page; `RW toc FILE --group` folds pages that share a running head into page ranges (chapters) to read with `--section 20-40`; with no running heads it uses the printed contents page, where each entry is a title line then a page-number line (0.26.0), or entries run on as `Title ... 21 Next ... 26` (0.35.0), and `toc` says so in a note.

Match the user's words to toc lines. "Chapter 14" usually means the line titled CHAPTER FOURTEEN, which in many ebooks holds only the chapter title and an epigraph: its body is the next section. The word counts show this (72 words, then 6,330). Section numbers are not chapter numbers: front matter comes first, so chapter 16 of a novel may be section 24.

## Step 3: read only what is needed

- `RW read FILE --section 43-44` (also `N`, `N-`, `N,M`; a repeated `--section` adds up) or `--title "REGEX"` (case-insensitive, matched against titles and ids; when nothing matches, spaces are ignored, so `westgate` finds WEST GATE).
- When `--title` lands on a section under 300 words, the section after it is added and a note says so. `--with-next` does the same for any selection.
- A section whose title repeats 3 or more times in the book ("Getting ready", "How to do it...", "There's more...") is shown with the nearest distinctive heading before it, in `read` headers and in `toc`: `How to do it... (in: Following a path)` (`in` in toc JSON).
- `--max-words N` caps each selected section at N words, so a batch like `--section 27-58 --max-words 80` stays small; a cut section ends `[cut at N of M words; continue with --section S --offset C]`.
- `--drop-repeated` (read) drops short paragraphs (40 words or fewer) that recur in 30% or more of the sections, verbatim or with the same last four words once digits are folded: per-image credits and copyright notices in EPUBs. It also drops a line of eight words or fewer repeated ten times or more inside one section (a quarter of its paragraphs), such as the "GO TO NOTE REFERENCE IN TEXT" back-link after every endnote. Off by default.
- `--skip-code` (read and grep) drops code blocks found by structure (EPUB and HTML `<pre>`, fenced Markdown; PDFs have no marker, so not there) and says how many words went. Advice lines come as one line at the end; `--quiet` drops them.
- `--lang CODE` (read and grep, 0.43.0; en, de, es, fr, it, nl, pt) keeps the paragraphs whose short common words favour that language, for an edition printing several side by side. Ties and fragments under 4 words go, except headings; code and tables stay; words glued by OCR still count. The footer says how many went, and `--max-chars` counts what is left. `info` notes a book with many paragraphs in two or more languages.
- `--headings` (read, 0.20.0) prints only the heading paragraphs of the chosen sections, indented by level, each with its paragraph number and the words under it; jump with `--at-para P`. In a PDF bookmarked only at chapter level, headings that pdftotext ran into the next paragraph are found from the page layout (0.66.0). A section with no headings at all says so: use `toc --group` or grep.
- `--strip-boilerplate` (read and grep) drops lines repeated across a PDF's pages: footers, bare page numbers, running headers, found by how often they repeat. Use it on both commands so grep's paragraph numbers match `--at-para`.
- Every section starts with a header line: `=== [43/80] title | id ... | words | starts at word N of TOTAL (P%) ===`.
- Output stops at `--max-chars` (default 25,000). The cut ends at a paragraph, line or sentence break near the limit (0.11.1), and the last line then says where to continue: `--offset N`. Keep each read under your shell tool's output limit: Claude Code shows 30,000 characters of a command's output and saves the rest to a file you would then have to open. For two long chapters, read them one call each. For more than that, write the selection with `--out <scratch>/part.txt` and open it with your own Read tool. To hand a reader agent several chapters, `--out-dir <scratch>/secs` writes each selected section to its own file (`NNN-title.txt`) and lists their sizes (0.12.0).
- `--section` takes a list and ranges in one call: `--section 61,80,87` or `--section 12,189-190`. Sections print in that order, each with its own header.
- A short selection ends with a hint naming the next section when that section probably carries on the text: the selection is a title page or epigraph (under 60 words), or the next section is untitled, marked continued, or repeats the title (0.15.0; it no longer fires on every small subsection).
- `read` without a selector refuses when the text is over the limit (exit code 2) and prints the toc instead. That refusal is the tool working: pick sections.
- `--format md` keeps headings and lists as Markdown; `--out FILE` writes the selection to a file; with `--max-chars` it cuts at a clean break and prints `cut at chars A-B of N; write the rest with --offset B` (0.15.1). `--compact` drops the blank line between paragraphs (0.13.0); give it again with `--offset`.

## Step 4: search

`RW grep FILE "PATTERN" -C 1 --max 5` prints each matching paragraph with its section number and title, paragraph number and one paragraph of context on each side. Long paragraphs are trimmed around the match (`--width`). `--after N` (`-A N`) adds N paragraphs after each hit, shown up to `--width` with their line breaks: the code block or list that follows the sentence naming it (0.15.0). A pattern with no capital letter matches any case (`--case-sensitive` forces exact case, `-i` forces any case), and `-F` takes a plain string; `--count` gives matches per section, the quickest way to find where a character or term appears. Each hit line ends `| offset N`, the character offset `read --section S --offset N` starts at; `read --section S --at-para P` starts at a paragraph. Use them when toc notes one giant section (bookmarks that stop early); since 0.17.0 such a section is first cut at the chapters a printed contents page or a "Chapter N, Title" list names, so the note shows only when that fails. Exit code 1 means no match. Search before reading when the user asks where or whether something is mentioned.

`RW rank FILE topic words` (0.24.0) ranks sections by BM25 for a few topic words and prints score, words and the terms each holds: which section to read first, where grep prints hits in book order. Stop words and plural, -ed and -ing endings are folded, so `shingles` finds `shingling`; a word not in the book is named. `--paras` ranks paragraphs (heading lines often win: read from there), `--top N`, `--section`, `--k1` and `--b` as in BM25. Rank first on a long book, then grep inside the top sections.

## Step 5: whole book to a scratch file

For work that needs many passes over a long book (every scene with a character, a timeline), run `RW dump FILE --out <scratch>/book.txt` once. Then use your own search and read tools on that file, never `cat`. Section markers are lines starting `=== [N/`; `--format md` writes `<!-- readwright section N/... -->` comments with Markdown headings. Dump writes to stdout only when the text is under 25,000 characters. Put the file in the session's scratch or temp folder, never in the user's repository.

## Step 6: answer

Quote briefly. For a copyrighted book, summarise and quote a sentence or two at a time, never whole pages or chapters, even when the user owns the copy. Cite where each point came from (section number and title) so the user can check it. When a conversion note was printed (calibre, LibreOffice, pdftotext), mention that the text came through a converter if the wording matters.

## Distilling a book

Reading a book to distill it (lessons for a beat, a plugin or a study): read [references/distilling.md](references/distilling.md) first. It holds every tip earlier distillation runs taught: batching chapter ranges, toc quirks, checking cited studies, briefing reader agents.

## Formats

Read [references/formats.md](references/formats.md) when a format misbehaves, when the user asks what is supported, or before using `--via pandoc|markitdown`. It lists what each format reads, the external tools and their install lines, the DRM checks and the caps on huge files.

## Maintenance

Evergreen unit: [RESEARCH.md](RESEARCH.md), [CHANGELOG.md](CHANGELOG.md), [LEARNINGS.md](LEARNINGS.md), [TESTS.md](TESTS.md), state in [evergreen.json](evergreen.json), protocol in [MAINTENANCE.md](MAINTENANCE.md). Record a learning in LEARNINGS.md when a real file breaks the tool (wrong titles, missing text, a converter surprise), with the fix and a test in `tests/test_rw.py`.
