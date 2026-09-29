# Learnings: readwright

Procedural lessons for [SKILL.md](SKILL.md). Research findings live in [RESEARCH.md](RESEARCH.md); every change is logged in [CHANGELOG.md](CHANGELOG.md); test runs in [TESTS.md](TESTS.md); state in `evergreen.json`. Format and write-time gate: MAINTENANCE.md (LEARNINGS-FORMAT). Retired entries go to LEARNINGS-ARCHIVE.md with a reason.

Write an entry the moment a real signal happens: a user correction, the same error twice, a discovered workaround, an environment fact, a stated preference, a failed test or a failure in use. Check existing entries first, by meaning (`evergreen.py search "<the lesson>" --kinds learnings` finds near-duplicates in every registered unit): add / update / retire / none. Trigger and Hypothesis are required. Promote after three confirmations; retire when harmful > helpful.

## Active

### L-001 · 2026-09-29 · A chapter's title page and its body are often separate sections
- Trigger: smoke test on a real EPUB novel, 2026-09-29: `read --title <chapter title>` returned a 72-word section (chapter number, title, epigraph); the chapter's 6,330 words were the next spine file, titled by its date line in the NCX.
- Hypothesis: publishers and calibre split each chapter's opener into its own XHTML file, and the NCX gives the body its own entry, so a title match lands on the opener.
- Rule: when a selection is short, read the next section too. rw.py says so at the end of the output (C-20260929-2), and `read --title` now adds the next section by itself when the match is under 300 words (C-20260929-5).
- Evidence: T-20260929-1, C-20260929-2, C-20260929-5, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 2 · harmful 0 · last_confirmed 2026-09-29

### L-002 · 2026-09-29 · claude plugin eval graders: JavaScript regex, one tool name, a compressed fixture
- Trigger: first WSL2 run of action-1 and outcome-1, 2026-09-29: `(?i)` threw "Invalid regular expression"; `tool: Bash|PowerShell` counted zero calls although the trace held three Bash calls to rw.py; and a stored (uncompressed) fixture EPUB could be read by plain Grep.
- Hypothesis: the harness compiles patterns as JavaScript RegExp (flags go in `flags:`), matches `tool` as a literal name in 2.1.281, and a stored zip keeps the XHTML as plain text.
- Rule: write `flags: i`, one literal tool name per grader, and build fixture archives with ZIP_DEFLATED.
- Evidence: T-20260929-2, C-20260929-3, confirmed 2026-09-29
- Scope: skill (applies to any plugin eval suite on this harness)
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-003 · 2026-09-29 · Chapter boundaries hide in converter and transcriber artefacts
- Trigger: real-file run, 2026-09-29. Project Gutenberg's EPUB 2 of Pride and Prejudice split chapter I across two files, so `toc` showed "Chapter I." at 152 words and an "(untitled: ...)" section of 718 (the EPUB 3 of the same book: 870); Moby-Dick's chapter 16 split the same way. In the Gutenberg text file, chapter I's heading is `Chapter I.]`, the end of an illustration caption, and the text reader folded the chapter into the preface (5,752 words).
- Hypothesis: Gutenberg's ebookmaker cuts HTML into files by size, not by chapter, and its text keeps the bracketed caption lines of the printed edition.
- Rule: text that no nav entry points at and that has no heading continues the section before it; brackets around a heading line are dropped before matching.
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-004 · 2026-09-29 · A failed tool's first lines say nothing; markitdown needs its extras and its own output file
- Trigger: `--via markitdown` on DOCX, PDF and XLS failed with the message "Traceback (most recent call last):", because rw.py kept the first 300 characters of stderr. The cause, on the last line, was a missing extra (`markitdown[docx]`). markitdown also returned an RTF file unchanged as its "Markdown", and on Windows it encodes stdout with the console code page.
- Hypothesis: Python tools print the traceback first and the exception last; markitdown 0.1.8 falls back to plain text for types it does not know; its `-o` path writes UTF-8.
- Rule: report a tool's error from its last exception line; run pandoc and markitdown with `-o FILE`; treat output that starts with the input's own first bytes as "does not read this format".
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-005 · 2026-09-29 · mutool's outline nests with tabs after the marker
- Trigger: first real `mutool show FILE outline` (MuPDF 1.23.0 on Windows, 1.23.10 in CI): lines read `|<TAB><TAB>"Title"<TAB>#page=4&zoom=...`, CRLF-terminated, and the 0.1.0 parser read depth from leading spaces, so every entry came out at level 1.
- Hypothesis: MuPDF prints a marker (`|` leaf, `+` closed, `-` open) and then one tab per level.
- Rule: depth is the number of tabs after the marker; the parser stays tolerant of the older space-indented form. Unverified on MuPDF 1.24 to 1.27.
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-006 · 2026-09-29 · Converters lose outlines; rescue them from CHAPTER lines
- Trigger: calibre 9.15's FB2 output of Pride and Prejudice has one `<title>` in the whole file: chapters are plain `<p>CHAPTER II.</p>` inside 15 untitled sections. Its PDB (eReader) round trip left four sections, one of 105,411 words. The source EPUB writes `CHAPTER<br/>XXVII`, which calibre's FB2 and the book's own nav turn into `CHAPTERXXVII`. `--via pandoc` on that FB2 gave Markdown with no headings at all.
- Hypothesis: calibre's FB2 and PDB writers map only real headings to structure, and a `<br/>` inside a heading becomes nothing in text.
- Rule: split any section over 12,000 words, or with no title, at its headings and CHAPTER lines; accept an uppercase numeral glued to the word; with no Markdown heading at all, use CHAPTER lines; match titles with spaces ignored when nothing matches as typed.
- Evidence: T-20260929-3, C-20260929-4, C-20260929-5, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-007 · 2026-09-29 · Spreadsheet dates are serial numbers unless the cell format is read
- Trigger: a CSV holding `2026-09-29`, saved as XLS by LibreOffice 26.8 and read back through LibreOffice's XLSX, came out as `46294`.
- Hypothesis: Excel formats store dates as day counts; only the cell's number format (styles.xml) says it is a date.
- Rule: map cellXfs to number formats (built-in ids 14 to 22 and the CJK ranges, or a custom code with d or y) and print ISO dates; honour `date1904`.
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-008 · 2026-09-29 · A tool installed after the shell started is not on the shell's PATH
- Trigger: after `winget install` of pandoc, poppler, calibre and LibreOffice, `Get-Command` found none of them in the running PowerShell or Git Bash; the registry PATH listed pandoc, poppler and calibre. winget's poppler is a portable zip under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\...\Library\bin`; LibreOffice's MSI adds nothing to PATH; `pip install --user markitdown` puts `markitdown.exe` in `%APPDATA%\Python\Python314\Scripts`, off PATH; Git for Windows ships pdftotext, pdfinfo and antiword in `mingw64\bin`.
- Hypothesis: a process inherits PATH at start; installers only update the registry.
- Rule: after PATH, search the registry PATH (Windows), the install folders above and pip's user scripts folder. To test a missing tool, hide it with `RW_HIDE_TOOLS` rather than by trimming PATH: on Linux soffice, antiword, mutool and pdftotext all live in `/usr/bin`, and the first CI run failed because hiding LibreOffice by PATH hid nothing.
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill; env:windows
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-009 · 2026-09-29 · Keep a read under the agent's output limit
- Trigger: full-size eval (Moby-Dick), 2026-09-29: `read --section 24-25 --max-chars 50000` printed about 52,000 characters; Claude Code kept 30,000 inline and saved the output to a file, and the agent then read the chapters twice more (with `--out` and its Read tool). rw.py's own default, 40,000, was over that limit as well.
- Hypothesis: Claude Code's Bash tool shows at most 30,000 characters of a command's output.
- Rule: default `--max-chars` 25,000; SKILL.md says to read long chapters one call each or write them with `--out` and open that file. After the change, three runs of the case read chapter by chapter and paged with `--offset 25000` as the output told them.
- Evidence: T-20260929-4, C-20260929-6, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-010 · 2026-09-29 · On EPUB, a strong model without the skill does about as well
- Trigger: action-2 with `--ablation with-without`, 3 runs per arm: without the skill the default model listed the zip, wrote a zipfile-and-regex extractor, found the chapter files and answered correctly, for 12.9k to 13.1k tokens of tool output and $0.29 to $0.31; with it, 12.1k to 12.2k tokens and $0.29 to $0.30. A first guess that the no-skill arm answered from memory was wrong: the saved trace showed the extraction.
- Hypothesis: EPUB is a zip of HTML, which a capable model parses on the fly; the skill's margin is elsewhere (formats that need converters, a refusal instead of a whole-book dump, chapter numbers mapped to sections, no new code per book).
- Rule: claim token savings only against the routes measured (whole-book dump 25 times, raw XHTML 3 times); keep the eval's baseline arm, and save traces in the same WSL call that runs the eval (`--keep-temp` folders in `/tmp` were gone by the next `wsl` call).
- Evidence: T-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

<!-- Example (delete once you have a real entry):
### L-001 · 2026-09-29 · One-line lesson in plain words
- Trigger: what happened, with dates or counts
- Hypothesis: why
- Rule: the shortest instruction that prevents the trigger
- Evidence: C-20260929-1, T-20260929-1, confirmed 2026-09-29
- Scope: skill | repo:<slug> | env:<name> | global
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29
-->
