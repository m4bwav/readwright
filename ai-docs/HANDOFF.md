# Handoff

## Current state
readwright 0.18.0 (2026-11-02): a giant PDF section is also split at running heads (`Chapter N ■ Title`) where N changes, and contents dot leaders (U+FFFD runs, dot runs) print as ` … ` (CHANGELOG C-20261102-15, LEARNINGS L-027, L-028). `python tests/test_rw.py` passes; `tests/real_files.py` 38/38.

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
- PDF tables, definition lists and sidebars still come out flat (code blocks fixed in 0.11.0, L-022). Why not done: `pdftotext -layout` lines interleave the columns of a table or a sidebar with the body, so finding them needs block coordinates. Next step: run `pdftotext -bbox-layout` (XHTML with <block>/<line>/<word> xMin/yMin per page) on pages flagged by a cheap hint (many short lines, aligned gaps of 3+ spaces in the -layout page), group lines into rows by yMin and columns by xMin, and emit `row` paragraphs (Para kind "row" exists) for tables and a separate paragraph for blocks whose xMin sits outside the body column (sidebars). Needs a real PDF with tables to calibrate; none was at hand.
- Two-column PDFs were not changed: plain pdftotext already reads each column in order on the test files seen.
- MuPDF 1.24 to 1.27 outline format unchecked (only 1.23); a DRM-protected KFX never seen on disk; pdftotext `-remove-hyphens` undecided (RESEARCH.md, Open questions).
- ubuntu-latest moves to Ubuntu 26 from 2026-10-19; the `routes` job's apt package names may need a look then.
- A partly scanned book (text on some pages only) is not flagged; no real example to calibrate on.

## Next single action
None owed. Next scheduled work is the evergreen refresh due 2026-11-03 (or the EPUB 3.4 event after 2026-10-19).
