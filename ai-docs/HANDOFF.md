# Handoff

## Current state

readwright 0.44.1 (2026-11-05): alternating running heads set beside a bare page number leave PDF text and no longer open sections (L-052). Open: heads with no number beside them on any page are still found only by the older share test; a short chapter with under 5 head pages keeps its heads, though its folios go; a glued `122 Exhibit 4-3` line stays. `rw.py` caches pdftotext output with no lock, so concurrent first reads of one PDF can read a partial file.

readwright 0.44.0 (2026-11-05): `<pre>` in a table cell stays a code block, `read --max-row-words N` cuts long table rows (L-051). Paragraph numbers shift in books with code in tables. Tried on one Manning EPUB.

readwright 0.43.2 (2026-11-05): `--skip-code` also drops listing captions and callout legends, and the footer counts them (L-050). Tried on one publisher's EPUB only.
readwright 0.43.1 (2026-11-04): nested HTML and EPUB lists keep their depth (L-049). Open: PDF and other formats keep flat lists.

readwright 0.43.0 (2026-11-04): `read --lang CODE` and `grep --lang CODE` keep one language's paragraphs (en, de, es, fr, it, nl, pt), `info` names the flag on a polyglot book, an open foot note takes its tail over the page, and fixed-layout folios are found on two-page spreads and in roman numerals (L-047, L-048).

Open from this work: when a note and the body sentence above both run on, the next page's top paragraph stays with the body, because nothing tells them apart. Interleaved lines inside one paragraph stay mixed under `--lang`; 2 of 40 sampled on the real book. Spread and roman folios and carried notes are checked on synthetic fixtures only: no such real EPUB was at hand, and 4 real PDFs tried had no lifted notes. A list at a page foot with a stray call can still read as notes (one case in 12 PDFs; the words stay, only the mark is wrong): no signal separates it, so left.

readwright 0.42.0 (2026-11-04): PDF page-foot notes leave the sentence as `[note N: text]`, page-break hyphens are judged by the book's word counts, and a PDF whose lines are whole paragraphs splits at each line (L-045, L-046). Paragraph numbers from before 0.42.0 no longer match on most PDFs.

readwright 0.41.2 (2026-11-04): `--skip-code` drops numbered code callout markers. Before that 0.41.1 (2026-11-04): strict UTF-8 is tried before a meta charset hint (mojibake fix, L-043), the `no text layer` note names `rw.py page` and `rw.py ocr`, and picture markers and folios stay out of fixed-layout sentences below the caption rule (L-044). `python -m unittest discover -s tests`: 179 tests pass.

readwright 0.39.0 (2026-11-03): for OCR text, `info` notes printed-page jumps that suggest leaves missing from a scan (CHANGELOG C-20261103-21); both gaps in a real two-up scan were found. Double-page scans can over-report when one page number was misread, so the note says to look at the images.

readwright 0.30.0 (2026-11-03): an EPUB whose outline collapsed into one giant section is split at the chapters of a one-line printed contents page (`1 TITLE`), cutting at a bare chapter-number paragraph above the title; contents-page lines no longer open false sections (CHANGELOG C-20261103-9, LEARNINGS L-039). `python tests/test_rw.py`: 137 tests pass; `tests/real_files.py` 38/38.

Earlier: readwright 0.29.0 (2026-11-03): Cengage textbook PDF fixes: outline titles give printed pages, per-page copyright footers dropped by default, smart-case grep, a warning for symbol-font math (CHANGELOG C-20261103-8, LEARNINGS L-035 to L-038). `python tests/test_rw.py`: 136 tests pass.

Open: symbol-font math is detected, not repaired. pdftotext's text has no font per character; a repair would read `mutool draw -F stext` (font name per char) and map Mathematical Pi codes to Unicode, only where mutool is present (L-036).

Earlier: readwright 0.23.0 (2026-11-02): double-spaced PDF pages rejoin into paragraphs (break hyphens dropped from the book's word counts), MATLAB/Python listings glued into prose become `pre` blocks for `--skip-code`, one-cell-per-line tables collapse to ` | ` rows (CHANGELOG C-20261102-20, LEARNINGS L-030, L-031). `python -m unittest discover -s tests`: 124 tests pass. Versions 0.21.0 and 0.22.0 are in the CHANGELOG.

Earlier: readwright 0.20.0 (2026-11-02): `read --headings` lists a section's subheadings with paragraph numbers for `--at-para` and word counts (CHANGELOG C-20261102-17). `python tests/test_rw.py`: 119 tests pass.

Earlier: readwright 0.19.0 (2026-11-02): `read --drop-epigraphs` drops quotation epigraphs with their dash attribution lines; distilling tip for reading short books in one pass (CHANGELOG C-20261102-16, LEARNINGS L-029). `python tests/test_rw.py`: 118 tests pass.

Earlier: readwright 0.18.0 (2026-11-02): a giant PDF section is also split at running heads (`Chapter N ■ Title`) where N changes, and contents dot leaders (U+FFFD runs, dot runs) print as ` … ` (CHANGELOG C-20261102-15, LEARNINGS L-027, L-028). `python tests/test_rw.py` passes; `tests/real_files.py` 38/38.

Earlier: readwright 0.17.0 (2026-11-02): a section holding over half the text (bookmarks that stop early) is cut at the chapters the printed contents page or "Chapter N, Title" lists name (CHANGELOG C-20261102-14, LEARNINGS L-026). `python tests/test_rw.py`: 117 tests; `tests/real_files.py` 38/38.

Earlier: readwright 0.15.0 (2026-11-02): `<pre>` code keeps indents through CRLF and no-break spaces, `grep --after N`, the short-selection hint only for title pages and continued sections, the cut footer after `--offset` says how to show the rest (CHANGELOG C-20261102-10, LEARNINGS L-025). `python tests/test_rw.py`: 110 tests.

Earlier: readwright 0.11.0 (2026-11-02): `rw.py ocr` reads image-only EPUBs, one-section books split at ALL-CAPS headings, PDF code blocks keep their lines (CHANGELOG C-20261102-4, LEARNINGS L-020 to L-022). Released as v0.11.0 on GitHub. `python tests/test_rw.py`: 97 tests; `tests/real_files.py` 38/38 (TESTS.md T-20261102-1).

## In progress
Nothing half-done.

## Findings worth knowing
- Token cost for two chapters of Moby-Dick (309k tokens): readwright 12.6k; whole book printed 310k to 317k; by hand 40k; dump to a file then grep 12k to 13k. In the eval, the model without the skill wrote its own zip extractor and matched readwright's cost on EPUB (LEARNINGS L-010). The README says so.
- `read` defaults to 25,000 characters because Claude Code shows 30,000 of a command's output (L-009).
- Scanned PDFs and EPUBs get a `no text layer` note under 10 words a page; on 83 real books it fired on exactly the 6 scans (L-011, [decisions/2026-10-23-scan-note-threshold-and-routes.md](decisions/2026-10-23-scan-note-threshold-and-routes.md)).
- Eval graders on Bash commands: models often call the script through a shell variable (`RW="python3 .../rw.py"; $RW grep ...`), so a pattern must not demand whitespace right after `rw.py` (T-20261023-1).
- In WSL, run `claude plugin eval` with the Linux binary's full path (`~/.local/bin/claude`) from a non-login `bash script.sh`; plain `claude` there finds the Windows one through interop and every scaffold fails.
- This machine now has all the tools, plus Kindle Previewer and calibre's KFX Input and Output plugins; how to make a KFX: [solutions/2026-09-29-test-every-converter-route-on-real-files-including-kfx.md](solutions/2026-09-29-test-every-converter-route-on-real-files-including-kfx.md).

## Decisions made this session
Scan note threshold and routes (decision entry in [INDEX.md](INDEX.md)).

## Open
- PDF tables now collapse runs of one-cell lines into ` | ` rows (0.23.0, L-031), but rows and columns are not recovered and multi-token cell lines stay as prose; definition lists and sidebars still come out flat (code blocks fixed in 0.11.0, L-022). Why not done: `pdftotext -layout` lines interleave the columns of a table or a sidebar with the body, so finding them needs block coordinates. Next step: run `pdftotext -bbox-layout` (XHTML with <block>/<line>/<word> xMin/yMin per page) on pages flagged by a cheap hint (many short lines, aligned gaps of 3+ spaces in the -layout page), group lines into rows by yMin and columns by xMin, and emit `row` paragraphs (Para kind "row" exists) for tables and a separate paragraph for blocks whose xMin sits outside the body column (sidebars). Needs a real PDF with tables to calibrate; none was at hand.
- EPUB equations set as pictures are marked (0.24.0) but not read; OCR of formula images is not attempted (math OCR is poor and no reader has needed the formula text yet).
- Two-column PDFs were not changed: plain pdftotext already reads each column in order on the test files seen.
- MuPDF 1.24 to 1.27 outline format unchecked (only 1.23); a DRM-protected KFX never seen on disk; pdftotext `-remove-hyphens` undecided (RESEARCH.md, Open questions).
- ubuntu-latest moves to Ubuntu 26 from 2026-10-19; the `routes` job's apt package names may need a look then.
- A partly scanned book (text on some pages only) is not flagged; no real example to calibrate on.
- Symbol-font math stays detected, not repaired: the fix needs a per-character font route through mutool, a project of its own (L-036).

## Next single action
None owed. Next scheduled work is the evergreen refresh due 2026-11-03 (or the EPUB 3.4 event after 2026-10-19).

readwright 0.40.0 (2026-11-03): `read --chapter 78,81-83` selects by the number printed in section titles, from the Universal Principles of Typography run. No new open items.
