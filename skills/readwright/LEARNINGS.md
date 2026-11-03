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

### L-013 · 2026-11-01 · toc-lists-bare-chapter-numbers: Packt chapters show as "12. 1 (1 w)" then the title
- Trigger: distilling "Deep Reinforcement Learning Hands-On" (3rd ed., Packt EPUB): each chapter number is its own one-word nav entry before the title, so the agent counted numbers by hand to cite chapters.
- Hypothesis: the nav lists the number and the title as separate entries at the same level.
- Rule: toc merges a 0-3 word number-only section into the next titled section as `Ch. N: Title`, and `toc --depth 1` lists only parts and chapters; plan a book from that, cite by chapter number.
- Evidence: C-20261101-3, 62 tests; on the real file `toc --depth 1` gives 22 chapters, 4 parts, front and back matter.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-01

<!-- Example (delete once you have a real entry):
### L-001 · 2026-09-29 · One-line lesson in plain words
- Trigger: what happened, with dates or counts
- Hypothesis: why
- Rule: the shortest instruction that prevents the trigger
- Evidence: C-20260929-1, T-20260929-1, confirmed 2026-09-29
- Scope: skill | repo:<slug> | env:<name> | global
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29
-->

### L-014 · 2026-11-01 · pdf-sections-start-a-page-early: each PDF section opened with the end of the one before
- Trigger: distilling Graesser & Keng, Foundations of Deep RL (PDF): `read --section 116` (14.5) mostly held the end of 14.4, and a reader missed that `grep --section` exists.
- Hypothesis: outline entries give a page, and sections were cut at page tops; headings sit mid-page, often in capitals and run into the paragraph text.
- Rule: cut at the heading paragraph on the start page; a numbered title is matched case-insensitively inside running text and splits the paragraph; an unnumbered title is never searched inside prose. When grep fills up, narrow with `--section`.
- Evidence: C-20261101-4, 63 tests; on the real file sections 90, 113 and 116 open with 10.2 DEBUGGING TIPS, 14.2 ACTIONS and 14.5 SUMMARY.

### L-015 · 2026-11-01 · same-page-outline-entries: PDF siblings on one page shared one text and lost spaces in titles
- Trigger: reading a MEAP PDF with `toc`: titles read "approachto", "agentscan"; three entries on page 20 showed 0, 0 and 431 words; "strengths" was empty and "weaknesses" opened with its text; a title showed `\"important\"`; `--section 23 --section 24` printed only 24; every page carried a forum footer and page number.
- Hypothesis: the producer dropped spaces where a heading wrapped; pdftotext runs the heading line into the paragraph above it, so the whole-paragraph match missed it and every same-page entry fell back to one index; outline entries went through a set, losing their order; MuPDF escapes quotes; argparse keeps the last `--section`.
- Rule: isolate outline-title lines (1-3 wrapped lines, matched ignoring case, punctuation and spacing) as their own paragraphs before splitting; place each same-page entry on the whole page and order by position; take the title's spacing from the heading line; unescape quotes; repeated `--section` adds up; page furniture is found by frequency (40% of pages anywhere, or 5 pages in the top or bottom two lines, digits ignored) and dropped with `--strip-boilerplate`.
- Evidence: C-20261101-5, 69 tests; on the real file no title loses a space, sections 15-17 have 119/215/177 words, 23/24 have 163/354, and footer grep matches drop from 398 to 7.

### L-016 · 2026-11-01 · code-heavy-batch-reads: code blocks and per-section hints swamped batch reads of an ML book
- Trigger: distilling an O'Reilly ML book (EPUB): a range read of short sections drowned in advice lines, one 2,259-word code walkthrough took most of a batch, and the reader's own line filter for code also removed real prose.
- Hypothesis: advice was printed per condition rather than once; `--max-words` gave no exact resume point; code is marked by structure (`<pre>`) in EPUB but a line regex cannot tell code from prose.
- Rule: one combined advice line per read, `--quiet` to drop it; every cut gives a `--section S --offset C` that resumes at the cut; skip code by paragraph kind, never by line pattern; in technical books read the troubleshooting and tips sections first.
- Evidence: C-20261101-6, 73 tests; on the real file `--skip-code` on sections 60-70 left out 1,024 words in 9 code blocks and grep "import" fell from 154 matches to 31.

### L-017 · 2026-11-01 · repeated-credit-lines: a per-image credit line in every section of a film book
- Trigger: distilling a film-technique EPUB: almost every section ends with a frame-grab credit (film, director, studio, year, "All Rights Reserved"), and the reader looped `read --section N` one section at a time, not knowing ranges and `--quiet` existed, so output overflowed.
- Hypothesis: the credit lines differ in names and years, so exact-repeat detection (PDF `--strip-boilerplate`) misses them; their shared ending is the stable part.
- Rule: compare short paragraphs by whole text and by their last four words with digits folded, and drop keys found in 30% or more of sections; keep it opt-in, since templated short body lines can share an ending. Tell distilling readers to batch ranges with `--quiet --max-words`.
- Evidence: C-20261101-7; on the real file `--drop-repeated` dropped 212 paragraphs, all credit lines (213 "Rights Reserved" matches; the one left is the acknowledgments page), and nothing else; 75 tests pass.

### L-018 · 2026-11-01 · scans-need-ocr: a scanned art book stopped a book run cold
- Trigger: everscout `lit ingest` refused 3dtotal's *Color & Light* (384 pages, 0 words); a session made a worktree and stopped there. The scan note offered only page images (a 384-page read by eye) and OCR tools that were not installed.
- Hypothesis: Windows 10 and 11 ship an OCR engine (`Windows.Media.Ocr`) reachable from Windows PowerShell 5.1 with no install; mutool already renders pages.
- Rule: on a scanned PDF run `rw.py ocr FILE` (in the background for a whole book), then read it like any PDF; sections are pages.
- Evidence: 2026-11-01, the whole book OCR'd at about 0.8 s a page at 200 dpi; body text, headings and captions read cleanly with a few misread letters ("beginnefs"). Tests: test_ocr_* in tests/test_rw.py. Applied: C-20261101-9.


### L-019 · 2026-11-01 · printed-page-offset: citations off by one page, and a case-sensitive miss
- Trigger: the Color & Light reader was told printed page = PDF page - 1; the pages said + 1 (PDF page 20 carries "21"). It also reported `grep "value key"` finding nothing; with `-i` it finds 3.
- Rule: take the offset from `info` (`printed_pages`), never from a guess; a zero-hit grep footer names the `-i` count.
- Evidence: 2026-11-01, Color & Light: printed_offset gives +1, matching the book's own cross-references. Tests: test_printed_page_offset, test_grep_without_i_names_case_hits. Applied: C-20261101-10.

### L-020 · 2026-11-02 · image-only-epub-ocr: a scanned EPUB had a note that said no OCR was available
- Trigger: an everscout book run on a film-technique EPUB made of 256 JPEG page images (pdftohtml pages wrapped by calibre). `info` said "OCR it (... none is available)" on a machine with Windows OCR, and `rw.py ocr` refused anything but a PDF.
- Rule: an EPUB whose spine shows page images is OCR'd like a scanned PDF: `rw.py ocr FILE` reads the images in spine order (no rendering), keeps the text in the OCR cache, and info, toc, read and grep use it. An image-only EPUB often has a DjVu twin in the same folder with OCR text already in it: try that first.
- Evidence: 2026-11-02, the real EPUB: 247 page images OCR'd in 35 s with Windows OCR, 88k words; `grep -i triple-take` 20 hits. Tests: TestFiveCs (epub_page_images, note, cache, engine run). Applied: C-20261102-4.

### L-033 · 2026-11-03 · page-join-empties-page: joining a run-on page moved the whole page
- Trigger: the same handbook PDF: a page whose single paragraph starts lower case was moved onto the previous page, chained across pages, so 172 held 172-175 and cites were off by up to three pages.
- Rule: across a page break move only the run-on sentence (to the first sentence end) when at least 20 words stay behind.
- Evidence: 2026-11-03; test_page_join_moves_only_the_run_on_sentence; empty pages 45 to 4 on the real file. Applied: C-20261103-2.

### L-032 · 2026-11-03 · contents-title-then-page: a contents page with the page number on the next line
- Trigger: a 2017 game-business handbook PDF with no outline and no running heads listed as 277 one-page sections; its contents page read `1 Personal Finance` then `15`.
- Rule: with no running heads, fold pages by the printed contents: title line, then page-number line, pages rising; shift by the printed-page offset.
- Evidence: 2026-11-03; test_group_uses_printed_contents; the real file went from 277 lines to 17 parts. Applied: C-20261103-2.

### L-031 · 2026-11-02 · pdf-table-cells: pdftotext prints a table one cell per paragraph
- Trigger: a textbook table of key profiles came out as dozens of lines of `0` and `v(3)`.
- Rule: collapse six or more one-token paragraphs in a row into one row paragraph joined with ` | `; real row and column layout still needs `pdftotext -bbox-layout`.
- Evidence: 2026-11-02; test_table_cells_collapse_to_one_row; the real table went from about 40 lines to 4. Applied: C-20261102-20.

### L-030 · 2026-11-02 · pdf-double-spaced: some PDFs give a blank line after every printed line
- Trigger: a signal-processing textbook PDF: each line became a paragraph, `fre-` and `quency` sat in two paragraphs, and a MATLAB listing (after a `Repo 2: X.m Repo 3: X.py` marker) was glued to its caption and the next paragraph, so `--skip-code` kept it.
- Rule: merge a page's paragraphs back when the next starts lower case after a hyphen or a missing sentence end, or when the page is double-spaced and the line is full width; drop the break hyphen when the book prints the joined word more often; split leading code-looking lines off a paragraph as `pre` (one is enough after a Repo marker).
- Evidence: 2026-11-02; TestPdfDoubleSpaced; on the real file section 186 reads as paragraphs, `frequency` rejoined, the listing dropped by `--skip-code`. Applied: C-20261102-20.

### L-029 · 2026-11-02 · quotation-epigraphs: short books that open each section with a quotation and a dash attribution
- Trigger: a short creativity EPUB carried about 40 `"Quote." / —Name` pairs across sections 5-15; reader notes credited the quoted people instead of the author.
- Rule: `read --drop-epigraphs` drops the pair (quote of 80 words or fewer, wholly quoted; attribution of 8 words or fewer starting with a dash); a quote without the attribution line stays.
- Evidence: 2026-11-02; test_drop_epigraphs; on the real file 80 paragraphs dropped, all epigraph pairs. Applied: C-20261102-16.

### L-028 · 2026-11-02 · contents-dot-leaders: pdftotext turns a contents page's dot leaders into runs of U+FFFD
- Trigger: an Apress PDF's Contents section printed `About the Author` followed by 60 replacement characters and `xiii`.
- Rule: collapse 3+ U+FFFD, or 4+ leader dots, between text and a page number to ` … ` at load so every output path is short.
- Evidence: 2026-11-02; test_contents_dot_leaders_collapse. Applied: C-20261102-15.

### L-027 · 2026-11-02 · pdf-running-head-split: bookmarks that stop early, but every page names its chapter in the running head
- Trigger: the same Apress PDF: outline ended at "Introduction", which held 90% of the text; `--group` refused (titled sections); the printed contents page gives printed page numbers, not PDF pages.
- Rule: read each page's first line before running heads are stripped; `Chapter N ■ Title` gives the chapter of every page, and the `CHAPTER N` opener page (no head) is where it starts. Split there.
- Evidence: 2026-11-02: 14 sections, chapters 1-8 at 2.3k to 5.7k words each, the Introduction 1.8k. Applied: C-20261102-15.

### L-026 · 2026-11-02 · printed-contents-split: bookmarks that stop early, but the printed contents page names every chapter
- Trigger: a Packt 2024 PDF: the outline's last entries are the part pages and "Preface", so `toc` gave 12 sections and section 11 held 94% of the text; `--group` refused (titled sections).
- Rule: pdftotext reads the contents page as `1` / title / page lines, and a chapter's opening page as one paragraph starting with its title. Cut the giant section at the first paragraph, in order, opening with each title. A two-column contents page comes out scrambled (chapter 9's number landed before a section entry), so titles also come from the part openers' "Chapter N, Title" lists, and an entry whose title line ends in a page number is a section, not a chapter.
- Evidence: 2026-11-02, the book: 11 chapters, 2.6k to 13k words each, preface 908 words. Applied: C-20261102-14.

### L-025 · 2026-11-02 · pre-crlf-nbsp-code: a publisher's EPUB writes code with CRLF and no-break-space indents
- Trigger: reader agents on a Python-for-Blender book saw one listing whose loop body had no indent and suspected `--compact`.
- Rule: the missing indent was in the EPUB source itself (the book's error); readwright now turns `<pre>` CR line ends into LF and U+00A0 into spaces, and joins listings the publisher split into one `<pre>` per line. When a reader reports mangled code, check the raw XHTML before blaming the renderer, and tell readers to trust code over prose but check API names against current docs.
- Evidence: 2026-11-02, the book's chapter 2 and 4 XHTML; TestReaderFixes. Applied: C-20261102-10.

### L-023 · 2026-11-02 · pdf-pages-by-running-head: a PDF with no outline listed 199 one-page sections
- Trigger: everscout book run (Fricker, Epistemic Injustice, OUP 2007): no PDF outline, so `toc` printed one line per page; the chapter showed only as each page's running head ("page 21: Testimonial Injustice").
- Rule: `toc --group` folds runs of pages that share a running head into page ranges with word counts; a chapter's opening page (head plus first words) joins the run. Plain `toc` adds a note offering it when pages outnumber heads three to one.
- Evidence: 2026-11-02, the book's 199 pages became 22 ranges (test_group_folds_pages_by_running_head). Applied: C-20261102-9.

### L-024 · 2026-11-02 · page-running-head: each page of an outline-less PDF opened with the chapter's running head
- Trigger: the same Fricker run: the reader agent saw "Testimonial Injustice" as the first line of every page even with `--strip-boilerplate`, because a section's first paragraph is kept as its heading, and per-chapter heads fall below the 40% furniture count.
- Rule: in a bare page section, drop the first paragraph when it is furniture and the previous page's first line starts with it; a chapter's opening page keeps its line. Footnotes printed at the page foot still sit inline (the PDF layout item; needs `-bbox-layout`). The agent also missed grep's `--width`, `--max` and `--count`: now in the brief tip.
- Evidence: 2026-11-02, pages 20-22 of the book; test_strip_drops_repeated_running_head_on_pages. Applied: C-20261102-9.

### L-021 · 2026-11-02 · inline-caps-headings: a DjVu came out of calibre as one 90k-word section
- Trigger: calibre's DjVu conversion of the same book gave one section; each page was one paragraph that opened with running heads ("CAMERA ANGLES THE FIVE C's ...") and carried its topic headings inline ("... dawn. TRIPLE-TAKE TECHNIQUE The simplest method ...").
- Rule: a section over BIG_SECTION words with no headings is split at ALL-CAPS runs. A caps phrase that opens many pages is a running head: the book title if it spans most of the book (dropped), else a chapter (a level-1 section from its first dense run of pages). Other caps runs of 1-8 words (single words only when 6+ letters) after a sentence end and before a capital are topic headings (level 2). Fewer than 3 headings found: nothing changes. Count heads near paragraph starts only, and never strip them from the end of a run, or topic words like FACTORS and TECHNIQUE become chapters.
- Evidence: 2026-11-02, the DjVu: 174 sections, chapters CAMERA ANGLES, CONTINUITY, CUTTING, CLOSE-UPS, COMPOSITION with topics such as TRIPLE-TAKE TECHNIQUE and HOW TO USE TRIPLE-TAKE TECHNIQUE. The OCR'd EPUB splits too but less cleanly (topic heads repeated at page tops: ACTION AXIS, MATCHING and SOUND are taken as chapters). tests/real_files.py 38/38 (no change on Pride and Prejudice). Applied: C-20261102-4.

### L-022 · 2026-11-02 · pdf-code-layout: pdftotext's plain mode merges indented code into the prose
- Trigger: the everscout handoff's open item (code blocks, tables, two columns, definition lists and sidebars flattened). A test PDF showed why: plain mode reads lines at different x positions as flowing text and puts `def f(h):` on the line of the sentence before it; `-layout` keeps lines and indentation.
- Rule: find code blocks in the `-layout` page (3+ code-shaped lines), then find their words in the plain page and replace them with the layout lines as one `pre` paragraph. The second pdftotext run is gated by a cheap code hint over the whole text. Tables, definition lists and sidebars are not handled: `-layout` lines mix columns, so they need `-bbox-layout` block coordinates (next step in HANDOFF Open).
- Evidence: 2026-11-02, synthetic PDF test (test_pdf_code_block_keeps_indentation). Applied: C-20261102-4.
