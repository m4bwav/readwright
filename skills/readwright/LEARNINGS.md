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
- Rule: depth is the number of tabs after the marker; the parser stays tolerant of the older space-indented form. Unverified on MuPDF 1.24 to 1.28.
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

### L-012 · 2026-11-01 · Early-stopping bookmarks leave one giant section with no way in
- Trigger: reading a 1,600-page technical PDF, 2026-11-01: the bookmarks stop in chapter 3, so toc showed 51 sections and the last held 1.85M chars (87% of the text). grep gave only `para 1070/1354`, so the reader binary-searched `read --offset` by hand.
- Rule: grep prints each hit's character offset in `read --section` terms, `read --at-para P` jumps to a paragraph, and toc notes any section over 200k chars and a quarter of the text.
- Evidence: on that PDF, `grep "8.4.4 GENERATE AND TEST"` printed `offset 1236036` and `read -s 51 --offset 1236036` began on the heading. Applied: C-20261101-1.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-01

### L-011 · 2026-10-22 · Scanned books report 0 words with no hint why
- Trigger: book dump, 2026-10-22: `info` on Gurney's *Color and Light* (226 pages), *Imaginative Realism*, Framed Ink 1 and 2 and Roberts' *Mastering Composition* printed `words: 0` and nothing else. The Mascelli EPUB was page images as well. With no OCR installed, the agents worked it out and rendered pages with `mutool draw -r 50` to read as images. The DjVu copy next to Mascelli had a text layer, and calibre extracted it.
- Hypothesis: these are image-only scans; info cannot tell a scan from an empty file.
- Rule: when a PDF or EPUB has pages but almost no words, info, toc and read say "no text layer" and name the ways in: a same-name copy in another format beside it (DjVu often carries OCR), OCR if installed, or page images (`mutool draw -r 60` or `pdftoppm -r 60`) read with the agent's image reader.
- Evidence: 2026-10-23, 83 real PDFs and EPUBs: the 6 scans had 0 words a page, the thinnest text book 132, so the floor of 10 words a page fires on exactly the 6. Eval outcome-2 (scanned EPUB, text copy beside it): with the skill 3 of 3 answered from the copy, without 0 of 3 (T-20261023-1). Applied: C-20261023-1.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-10-23

### L-016 · 2026-11-01 · code-heavy-batch-reads: code blocks and per-section hints swamped batch reads of an ML book
- Trigger: distilling an O'Reilly ML book (EPUB): a range read of short sections drowned in advice lines, one 2,259-word code walkthrough took most of a batch, and the reader's own line filter for code also removed real prose.
- Hypothesis: advice was printed per condition rather than once; `--max-words` gave no exact resume point; code is marked by structure (`<pre>`) in EPUB but a line regex cannot tell code from prose.
- Rule: one combined advice line per read, `--quiet` to drop it; every cut gives a `--section S --offset C` that resumes at the cut; skip code by paragraph kind, never by line pattern; in technical books read the troubleshooting and tips sections first.
- Evidence: C-20261101-6, 73 tests; on the real file `--skip-code` on sections 60-70 left out 1,024 words in 9 code blocks and grep "import" fell from 154 matches to 31.

### L-018 · 2026-11-01 · scans-need-ocr: a scanned art book stopped a book run cold
- Trigger: everscout `lit ingest` refused 3dtotal's *Color & Light* (384 pages, 0 words); a session made a worktree and stopped there. The scan note offered only page images (a 384-page read by eye) and OCR tools that were not installed.
- Hypothesis: Windows 10 and 11 ship an OCR engine (`Windows.Media.Ocr`) reachable from Windows PowerShell 5.1 with no install; mutool already renders pages.
- Rule: on a scanned PDF run `rw.py ocr FILE` (in the background for a whole book), then read it like any PDF; sections are pages.
- Evidence: 2026-11-01, the whole book OCR'd at about 0.8 s a page at 200 dpi; body text, headings and captions read cleanly with a few misread letters ("beginnefs"). Tests: test_ocr_* in tests/test_rw.py. Applied: C-20261101-9.

### L-019 · 2026-11-01 · printed-page-offset: citations off by one page, and a case-sensitive miss
- Trigger: the Color & Light reader was told printed page = PDF page - 1; the pages said + 1 (PDF page 20 carries "21"). It also reported `grep "value key"` finding nothing; with `-i` it finds 3.
- Rule: take the offset from `info` (`printed_pages`), never from a guess; a zero-hit grep footer names the `-i` count.
- Evidence: 2026-11-01, Color & Light: printed_offset gives +1, matching the book's own cross-references. Tests: test_printed_page_offset, test_grep_without_i_names_case_hits. Applied: C-20261101-10.

### L-025 · 2026-11-02 · pre-crlf-nbsp-code: a publisher's EPUB writes code with CRLF and no-break-space indents
- Trigger: reader agents on a Python-for-Blender book saw one listing whose loop body had no indent and suspected `--compact`.
- Rule: the missing indent was in the EPUB source itself (the book's error); readwright now turns `<pre>` CR line ends into LF and U+00A0 into spaces, and joins listings the publisher split into one `<pre>` per line. When a reader reports mangled code, check the raw XHTML before blaming the renderer, and tell readers to trust code over prose but check API names against current docs.
- Evidence: 2026-11-02, the book's chapter 2 and 4 XHTML; TestReaderFixes. Applied: C-20261102-10.
### L-034 · 2026-11-03 · printed-page-drift: one offset does not fit a book that drops a page per chapter
- Trigger: everscout book run (Styhre, *Indie Video Game Development Work*, Palgrave 2020 PDF). The printed page is PDF minus 10 at ch. 5, 9 at ch. 6, 8 at ch. 7 and 7 at ch. 8; `printed_offset` found no majority and printed nothing, and two reader agents each took one chapter's offset for the whole book.
- Rule: when no single shift holds, label each page from its own number (bare, beside an upper-case running head, or under a copyright footer within the last four lines), keep a number only when a page within three shares its offset, fill gaps between anchors of one offset, and let `read --section pN` select by printed page.
- Evidence: 2026-11-03, 237 of 252 pages labelled, every chapter opener right; test_printed_labels_follow_a_drifting_offset. Applied: C-20261103-7.

### L-035 · 2026-11-03 · outline-printed-pages: outline titles gave PDF pages only
- Trigger: a reader of Arnold's *Economics* (Cengage PDF) saw `6-1 ... (p. 165-170)` in `toc` while the page prints 129, and guessed the offset drifted from 36 to 35. It does not: every running head in the book gives PDF minus 36.
- Rule: an outline section title carries `printed A-B` beside its PDF pages whenever a shift or per-page labels are known; `printed_labels` also reads a mixed-case running head on the top line.
- Evidence: 2026-11-03, 850 of 871 labelled pages agree on -36. Test: test_outline_titles_carry_printed_pages. Applied: C-20261103-8.

### L-036 · 2026-11-03 · symbol-font-math: '=' reads as '5' in Mathematical Pi fonts
- Trigger: the same book printed `CPI 5 _$ _1_6_7_3 100`: '=' as '5', '+' as '1', minus as '2', times as '3', fraction bars as underscores.
- Rule: detect by font name (pdffonts lists `MathematicalPiLTStd`), warn in `info`/`toc`, and do not repair: pdftotext's plain text does not say which font each character came from, so mapping '5' back to '=' would also turn real fives into equals signs. Repair needs per-glyph font data (pdftotext -bbox-layout gives none; mutool stext does), left open in HANDOFF.
- Evidence: 2026-11-03, pdffonts on the book (about 7 s, cached). Test: test_symbol_font_math_warning. Applied: C-20261103-8.

### L-037 · 2026-11-03 · per-page-copyright-footer: a 60-word footer on every page
- Trigger: the Cengage footer ('Copyright 2013 Cengage Learning. All Rights Reserved. May not be copied...') is too long for page furniture (120 characters) and for `--drop-repeated` (40 words), so it stayed in every read, about 10% of the text.
- Rule: drop by default a paragraph that starts with Copyright or (c), carries rights wording, and recurs on 30% of pages, plus a repeated paragraph right after it.
- Evidence: 2026-11-03, 719 copies dropped, chars 3.28M to 2.95M. Test: test_page_copyright_footer_dropped. Applied: C-20261103-8.

### L-038 · 2026-11-03 · grep-smart-case: readers kept missing capitalised terms
- Trigger: `grep "consumer price index"` found nothing and only said how many `-i` would find.
- Rule: smart case as in ripgrep: no capital letter outside a regex escape means any case; `--case-sensitive` forces exact case.
- Evidence: Test: test_grep_smart_case. Applied: C-20261103-8.

### L-039 · 2026-11-03 · epub-oneline-contents: a calibre EPUB with bold-paragraph chapters stayed one section
- Trigger: an EPUB with a one-entry NCX: `toc` gave 6 sections, one with 90% of the words; its contents page read `1 TITLE` per line, each chapter opened with a `1` paragraph then a title paragraph, and the contents lines `INTRODUCTION` and `EPILOGUE: ...` matched HEAD_RE, so the sections after them were titled one off.
- Rule: read one-line contents entries before the two-line PDF form; cut at the number paragraph above a title; drop a heading cut whose first word opens a later cut when the lines beside it are short.
- Evidence: 2026-11-03, the book went to 12 sections: Introduction, chapters 1-8 (7,200 to 11,100 words), Epilogue. Test: test_epub_section_splits_at_oneline_contents. Applied: C-20261103-9.

### L-040 · 2026-11-03 · group-labelled-pages: toc --group refused a PDF that was only pages
- Trigger: a PDF with no outline and drifting printed labels: titles read `page 14 (p. 3): ...`, some with line breaks from code at the page top, so `--group` said the file had titled sections. Its contents ran on in one paragraph, `Title ... 21 Next ... 26`.
- Rule: page titles are one line; the page match allows a label; run-on leader entries map printed pages through the labels.
- Evidence: Web Typography went from a refusal to 33 runs. A chapter whose entry straddles two contents pages can lose its title and join the run before. Test: test_group_reads_runon_leader_contents_and_page_labels.
