# Learnings archive: readwright

Retired or promoted entries from [LEARNINGS.md](LEARNINGS.md), each with a reason.

## Consolidation 2026-11-05 (C-20261105-7)

Each entry below is unchanged except for its last line. `promoted` names where the rule is now read; `retired` names the entry it merged into. A rule that is also code has its test named in the entry or in tests/test_rw.py by ID.

### L-050 · 2026-11-05 · `skip-code-legends`: listing captions and legends outlive their code
Dropping a code block left its `Listing N.N` caption and circled-number legend lines in the text. Tied to position (caption right before a block, legends in a run right after one), so prose that merely names a listing stays. Measured on one Manning EPUB: 45 lines gone from one section, no prose line lost in the two sections checked.
- Status: retired: 2026-11-05 · merged into L-051 `table-cell-code` (same trigger family: what `--skip-code` leaves behind)

### L-049 · 2026-11-04 · `nested-lists`: flattened sub-items read as new points
- Trigger: a testing book's four kinds of bad metric printed level with their own examples, and only the sense showed where one ended.
- Rule: keep each list item's depth from its opening tag; the parent's text is flushed after the inner list has already raised the depth.
- Evidence: test on three levels; ch. 9 of the real book now indents. Formats other than HTML and EPUB keep flat lists.
- Status: promoted: C-20261105-7 · references/formats.md, Built in (one new sentence)

### L-048 · 2026-11-04 · `fixed-folio-kinds`: folios rise by two on a spread, and front matter counts in roman
- Trigger: L-044 left spreads and roman front matter as numbers in the text.
- Rule: a bare number is a folio when number minus position is constant at one a file, or at two a file allowing the pair. Lowercase roman runs separately and needs only 3 files, since front matter is short; a repeated `i` never rises, so it stays.
- Evidence: Tests: TestFixedLayoutMarkers; synthetic only, no real spread EPUB at hand. Applied: C-20261104-6.
- Status: retired: 2026-11-05 · merged into L-044 `fixed-folio-rises` (same rule, spreads and roman numerals)

### L-045 · 2026-11-04 · `pdf-lines-are-paragraphs`: some PDFs give one line per paragraph and no blank lines
- Trigger: a PDF whose pdftotext output had 929-character lines and blank lines only at page ends. Whole pages became one paragraph, gluing lowercase subheads and chapter-opening epigraphs into the body.
- Rule: when at least half the characters sit on lines over 200 characters, no page could print them, so each line on a page holding such a line is a paragraph. Marked code blocks and pages of only short lines stay as they were. An unfolded file also loses its bare folio at the foot and the double-spacing rule.
- Evidence: five sections went from 53 to 224 paragraphs with the subhead and epigraph on their own. All 12 other PDFs sampled from one folder also met the test, so this changes paragraph numbers on most PDFs, with about 0.1 to 0.8% more characters. Tests: TestPdfNotesAndUnfolding. Applied: C-20261104-5.
- Status: promoted: C-20261105-7 · references/formats.md, External tools (one new paragraph)

### L-046 · 2026-11-04 · `pdf-foot-notes`: tell a note from a list by the call in the body
- Trigger: `N. text` lines at the page foot stopped the page join, so a sentence, and a word split by a hyphen, broke around the note. The same book has numbered lists in the body with the same shape.
- Rule: walk up from the page foot; a note has a call to its number straight after a letter or punctuation in the body above, and its number is one below the note under it. Lifted notes go after the page's last paragraph once pages are joined. For a hyphen at a break, compare the joined and hyphenated counts in the book; with neither printed, join only a fragment (a left half seen once, or a left half under 3 letters with a right half seen once), so `well-documented` keeps its hyphen.
- A digit straight after a letter or a dot is often math or a section number (`x1`, `2.1`), and steps on a page foot fooled the first version: the call must follow a lowercase word or a sentence's punctuation, and a run that continues at the top of the next page is a list. A list item just above a note can carry the number below it, so that is no signal.
- Evidence: 15 notes lifted in five sections, list items untouched, all five reported split words healed. Applied: C-20261104-5. Since C-20261104-6 a note left open takes its lower-case tail from the next page's foot, or from its top when the body sentence above is closed; with both open the top paragraph stays with the body (test TestFootNoteCarried).
- Status: promoted: C-20261105-7 · references/formats.md, External tools (PDF page-foot notes)

### L-043 · 2026-11-04 · utf8-before-meta: a wrong meta charset turned every non-ASCII character to mojibake
- Trigger: an EPUB with `encoding='utf-8'` in the XML line and a `charset=iso-8859-1` meta, in UTF-8 bytes: `html_charset` preferred the meta, and latin-1 never fails, so body text and titles came out with `â` and `Ã¶`, and no-break spaces as lone `Â` paragraphs.
- Rule: non-ASCII bytes that are valid UTF-8 are UTF-8; the hint comes second, except a UTF-16 or UTF-32 hint, whose BOM-less data can pass as UTF-8. `clean` already drops a paragraph of only no-break space.
- Evidence: Tests: TestCharsetHints (fail before the fix, pass after). Applied: C-20261104-3.
- Status: promoted: C-20261105-7 · references/formats.md, Detection (one new sentence) and SKILL.md Distilling a book (`â` output)

### L-001 · 2026-09-29 · A chapter's title page and its body are often separate sections
- Trigger: smoke test on a real EPUB novel, 2026-09-29: `read --title <chapter title>` returned a 72-word section (chapter number, title, epigraph); the chapter's 6,330 words were the next spine file, titled by its date line in the NCX.
- Hypothesis: publishers and calibre split each chapter's opener into its own XHTML file, and the NCX gives the body its own entry, so a title match lands on the opener.
- Rule: when a selection is short, read the next section too. rw.py says so at the end of the output (C-20260929-2), and `read --title` now adds the next section by itself when the match is under 300 words (C-20260929-5).
- Evidence: T-20260929-1, C-20260929-2, C-20260929-5, confirmed 2026-09-29
- Scope: skill
- Status: promoted: C-20261105-7 · SKILL.md Step 2 and Step 3 (short title sections, `--with-next`); `read --title` does it by itself

### L-002 · 2026-09-29 · claude plugin eval graders: JavaScript regex, one tool name, a compressed fixture
- Trigger: first WSL2 run of action-1 and outcome-1, 2026-09-29: `(?i)` threw "Invalid regular expression"; `tool: Bash|PowerShell` counted zero calls although the trace held three Bash calls to rw.py; and a stored (uncompressed) fixture EPUB could be read by plain Grep.
- Hypothesis: the harness compiles patterns as JavaScript RegExp (flags go in `flags:`), matches `tool` as a literal name in 2.1.281, and a stored zip keeps the XHTML as plain text.
- Rule: write `flags: i`, one literal tool name per grader, and build fixture archives with ZIP_DEFLATED.
- Evidence: T-20260929-2, C-20260929-3, confirmed 2026-09-29
- Scope: skill (applies to any plugin eval suite on this harness)
- Status: promoted: C-20261105-7 · AGENTS.md Rules (eval graders)

### L-004 · 2026-09-29 · A failed tool's first lines say nothing; markitdown needs its extras and its own output file
- Trigger: `--via markitdown` on DOCX, PDF and XLS failed with the message "Traceback (most recent call last):", because rw.py kept the first 300 characters of stderr. The cause, on the last line, was a missing extra (`markitdown[docx]`). markitdown also returned an RTF file unchanged as its "Markdown", and on Windows it encodes stdout with the console code page.
- Hypothesis: Python tools print the traceback first and the exception last; markitdown 0.1.8 falls back to plain text for types it does not know; its `-o` path writes UTF-8.
- Rule: report a tool's error from its last exception line; run pandoc and markitdown with `-o FILE`; treat output that starts with the input's own first bytes as "does not read this format".
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: promoted: C-20261105-7 · references/formats.md, External tools (one new sentence); `tool_error` in rw.py

### L-009 · 2026-09-29 · Keep a read under the agent's output limit
- Trigger: full-size eval (Moby-Dick), 2026-09-29: `read --section 24-25 --max-chars 50000` printed about 52,000 characters; Claude Code kept 30,000 inline and saved the output to a file, and the agent then read the chapters twice more (with `--out` and its Read tool). rw.py's own default, 40,000, was over that limit as well.
- Hypothesis: Claude Code's Bash tool shows at most 30,000 characters of a command's output.
- Rule: default `--max-chars` 25,000; SKILL.md says to read long chapters one call each or write them with `--out` and open that file. After the change, three runs of the case read chapter by chapter and paged with `--offset 25000` as the output told them.
- Evidence: T-20260929-4, C-20260929-6, confirmed 2026-09-29
- Scope: skill
- Status: promoted: C-20261105-7 · SKILL.md Step 3 (`--max-chars`, `--out`); `DEFAULT_MAX_CHARS` in rw.py

### L-012 · 2026-11-01 · Early-stopping bookmarks leave one giant section with no way in
- Trigger: reading a 1,600-page technical PDF, 2026-11-01: the bookmarks stop in chapter 3, so toc showed 51 sections and the last held 1.85M chars (87% of the text). grep gave only `para 1070/1354`, so the reader binary-searched `read --offset` by hand.
- Rule: grep prints each hit's character offset in `read --section` terms, `read --at-para P` jumps to a paragraph, and toc notes any section over 200k chars and a quarter of the text.
- Evidence: on that PDF, `grep "8.4.4 GENERATE AND TEST"` printed `offset 1236036` and `read -s 51 --offset 1236036` began on the heading. Applied: C-20261101-1.
- Scope: skill
- Status: promoted: C-20261105-7 · SKILL.md Step 4 (hit offsets, `--at-para`, the giant-section note)

### L-011 · 2026-10-22 · Scanned books report 0 words with no hint why
- Trigger: book dump, 2026-10-22: `info` on Gurney's *Color and Light* (226 pages), *Imaginative Realism*, Framed Ink 1 and 2 and Roberts' *Mastering Composition* printed `words: 0` and nothing else. The Mascelli EPUB was page images as well. With no OCR installed, the agents worked it out and rendered pages with `mutool draw -r 50` to read as images. The DjVu copy next to Mascelli had a text layer, and calibre extracted it.
- Hypothesis: these are image-only scans; info cannot tell a scan from an empty file.
- Rule: when a PDF or EPUB has pages but almost no words, info, toc and read say "no text layer" and name the ways in: a same-name copy in another format beside it (DjVu often carries OCR), OCR if installed, or page images (`mutool draw -r 60` or `pdftoppm -r 60`) read with the agent's image reader.
- Evidence: 2026-10-23, 83 real PDFs and EPUBs: the 6 scans had 0 words a page, the thinnest text book 132, so the floor of 10 words a page fires on exactly the 6. Eval outcome-2 (scanned EPUB, text copy beside it): with the skill 3 of 3 answered from the copy, without 0 of 3 (T-20261023-1). Applied: C-20261023-1.
- Scope: skill
- Status: promoted: C-20261105-7 · SKILL.md Step 1 (`no text layer`)

### L-016 · 2026-11-01 · code-heavy-batch-reads: code blocks and per-section hints swamped batch reads of an ML book
- Trigger: distilling an O'Reilly ML book (EPUB): a range read of short sections drowned in advice lines, one 2,259-word code walkthrough took most of a batch, and the reader's own line filter for code also removed real prose.
- Hypothesis: advice was printed per condition rather than once; `--max-words` gave no exact resume point; code is marked by structure (`<pre>`) in EPUB but a line regex cannot tell code from prose.
- Rule: one combined advice line per read, `--quiet` to drop it; every cut gives a `--section S --offset C` that resumes at the cut; skip code by paragraph kind, never by line pattern; in technical books read the troubleshooting and tips sections first.
- Evidence: C-20261101-6, 73 tests; on the real file `--skip-code` on sections 60-70 left out 1,024 words in 9 code blocks and grep "import" fell from 154 matches to 31.
- Status: promoted: C-20261105-7 · SKILL.md Step 3 (`--skip-code`, `--quiet`) and Distilling a book (Troubleshooting sections first)

### L-018 · 2026-11-01 · scans-need-ocr: a scanned art book stopped a book run cold
- Trigger: everscout `lit ingest` refused 3dtotal's *Color & Light* (384 pages, 0 words); a session made a worktree and stopped there. The scan note offered only page images (a 384-page read by eye) and OCR tools that were not installed.
- Hypothesis: Windows 10 and 11 ship an OCR engine (`Windows.Media.Ocr`) reachable from Windows PowerShell 5.1 with no install; mutool already renders pages.
- Rule: on a scanned PDF run `rw.py ocr FILE` (in the background for a whole book), then read it like any PDF; sections are pages.
- Evidence: 2026-11-01, the whole book OCR'd at about 0.8 s a page at 200 dpi; body text, headings and captions read cleanly with a few misread letters ("beginnefs"). Tests: test_ocr_* in tests/test_rw.py. Applied: C-20261101-9.
- Status: promoted: C-20261105-7 · SKILL.md Step 1 (`RW ocr`)

### L-019 · 2026-11-01 · printed-page-offset: citations off by one page, and a case-sensitive miss
- Trigger: the Color & Light reader was told printed page = PDF page - 1; the pages said + 1 (PDF page 20 carries "21"). It also reported `grep "value key"` finding nothing; with `-i` it finds 3.
- Rule: take the offset from `info` (`printed_pages`), never from a guess; a zero-hit grep footer names the `-i` count.
- Evidence: 2026-11-01, Color & Light: printed_offset gives +1, matching the book's own cross-references. Tests: test_printed_page_offset, test_grep_without_i_names_case_hits. Applied: C-20261101-10.
- Status: retired: 2026-11-05 · merged into L-034 `printed-page-drift` (same lesson: take printed pages from the tool). Its `-i` half was overtaken by L-038 smart case; the zero-hit footer stays in rw.py

### L-025 · 2026-11-02 · pre-crlf-nbsp-code: a publisher's EPUB writes code with CRLF and no-break-space indents
- Trigger: reader agents on a Python-for-Blender book saw one listing whose loop body had no indent and suspected `--compact`.
- Rule: the missing indent was in the EPUB source itself (the book's error); readwright now turns `<pre>` CR line ends into LF and U+00A0 into spaces, and joins listings the publisher split into one `<pre>` per line. When a reader reports mangled code, check the raw XHTML before blaming the renderer, and tell readers to trust code over prose but check API names against current docs.
- Evidence: 2026-11-02, the book's chapter 2 and 4 XHTML; TestReaderFixes. Applied: C-20261102-10.
- Status: promoted: C-20261105-7 · SKILL.md Distilling a book (raw XHTML before blaming the reader; trust code, check API names)

### L-034 · 2026-11-03 · printed-page-drift: one offset does not fit a book that drops a page per chapter
- Trigger: everscout book run (Styhre, *Indie Video Game Development Work*, Palgrave 2020 PDF). The printed page is PDF minus 10 at ch. 5, 9 at ch. 6, 8 at ch. 7 and 7 at ch. 8; `printed_offset` found no majority and printed nothing, and two reader agents each took one chapter's offset for the whole book.
- Rule: when no single shift holds, label each page from its own number (bare, beside an upper-case running head, or under a copyright footer within the last four lines), keep a number only when a page within three shares its offset, fill gaps between anchors of one offset, and let `read --section pN` select by printed page.
- Evidence: 2026-11-03, 237 of 252 pages labelled, every chapter opener right; test_printed_labels_follow_a_drifting_offset. Applied: C-20261103-7.
- Status: promoted: C-20261105-7 · SKILL.md Distilling a book (`printed_pages`, `pN`, never carry one chapter's offset); took in L-019 and L-035 (`printed-page-drift`; the archive also holds an older L-034, `pdf-python-listings`)

### L-035 · 2026-11-03 · outline-printed-pages: outline titles gave PDF pages only
- Trigger: a reader of Arnold's *Economics* (Cengage PDF) saw `6-1 ... (p. 165-170)` in `toc` while the page prints 129, and guessed the offset drifted from 36 to 35. It does not: every running head in the book gives PDF minus 36.
- Rule: an outline section title carries `printed A-B` beside its PDF pages whenever a shift or per-page labels are known; `printed_labels` also reads a mixed-case running head on the top line.
- Evidence: 2026-11-03, 850 of 871 labelled pages agree on -36. Test: test_outline_titles_carry_printed_pages. Applied: C-20261103-8.
- Status: retired: 2026-11-05 · merged into L-034 `printed-page-drift` (same lesson, outline titles)

### L-036 · 2026-11-03 · symbol-font-math: '=' reads as '5' in Mathematical Pi fonts
- Trigger: the same book printed `CPI 5 _$ _1_6_7_3 100`: '=' as '5', '+' as '1', minus as '2', times as '3', fraction bars as underscores.
- Rule: detect by font name (pdffonts lists `MathematicalPiLTStd`), warn in `info`/`toc`, and do not repair: pdftotext's plain text does not say which font each character came from, so mapping '5' back to '=' would also turn real fives into equals signs. Repair needs per-glyph font data (pdftotext -bbox-layout gives none; mutool stext does), left open in HANDOFF.
- Evidence: 2026-11-03, pdffonts on the book (about 7 s, cached). Test: test_symbol_font_math_warning. Applied: C-20261103-8.
- Status: promoted: C-20261105-7 · SKILL.md Distilling a book (Cengage line); the open repair stays in ai-docs/HANDOFF.md

### L-037 · 2026-11-03 · per-page-copyright-footer: a 60-word footer on every page
- Trigger: the Cengage footer ('Copyright 2013 Cengage Learning. All Rights Reserved. May not be copied...') is too long for page furniture (120 characters) and for `--drop-repeated` (40 words), so it stayed in every read, about 10% of the text.
- Rule: drop by default a paragraph that starts with Copyright or (c), carries rights wording, and recurs on 30% of pages, plus a repeated paragraph right after it.
- Evidence: 2026-11-03, 719 copies dropped, chars 3.28M to 2.95M. Test: test_page_copyright_footer_dropped. Applied: C-20261103-8.
- Status: promoted: C-20261105-7 · SKILL.md Distilling a book (Cengage line)

### L-038 · 2026-11-03 · grep-smart-case: readers kept missing capitalised terms
- Trigger: `grep "consumer price index"` found nothing and only said how many `-i` would find.
- Rule: smart case as in ripgrep: no capital letter outside a regex escape means any case; `--case-sensitive` forces exact case.
- Evidence: Test: test_grep_smart_case. Applied: C-20261103-8.
- Status: promoted: C-20261105-7 · SKILL.md Step 4 (this pass reworded its `-i` sentence, which still implied case-sensitive by default)

### L-039 · 2026-11-03 · epub-oneline-contents: a calibre EPUB with bold-paragraph chapters stayed one section
- Trigger: an EPUB with a one-entry NCX: `toc` gave 6 sections, one with 90% of the words; its contents page read `1 TITLE` per line, each chapter opened with a `1` paragraph then a title paragraph, and the contents lines `INTRODUCTION` and `EPILOGUE: ...` matched HEAD_RE, so the sections after them were titled one off.
- Rule: read one-line contents entries before the two-line PDF form; cut at the number paragraph above a title; drop a heading cut whose first word opens a later cut when the lines beside it are short.
- Evidence: 2026-11-03, the book went to 12 sections: Introduction, chapters 1-8 (7,200 to 11,100 words), Epilogue. Test: test_epub_section_splits_at_oneline_contents. Applied: C-20261103-9.
- Status: promoted: C-20261105-7 · SKILL.md Distilling a book (one-entry outline line)

### L-040 · 2026-11-03 · group-labelled-pages: toc --group refused a PDF that was only pages
- Trigger: a PDF with no outline and drifting printed labels: titles read `page 14 (p. 3): ...`, some with line breaks from code at the page top, so `--group` said the file had titled sections. Its contents ran on in one paragraph, `Title ... 21 Next ... 26`.
- Rule: page titles are one line; the page match allows a label; run-on leader entries map printed pages through the labels.
- Evidence: Web Typography went from a refusal to 33 runs. A chapter whose entry straddles two contents pages can lose its title and join the run before. Test: test_group_reads_runon_leader_contents_and_page_labels.
- Status: promoted: C-20261105-7 · SKILL.md Step 2 (`toc --group`, run-on contents)

## Consolidation 2026-11-03 (C-20261103-6)

Reason for every entry below: promoted. Each rule is implemented and tested in scripts/rw.py (see its Applied: C- line), so the code now carries it and the entry adds nothing an agent must remember.

### L-003 · 2026-09-29 · Chapter boundaries hide in converter and transcriber artefacts
- Trigger: real-file run, 2026-09-29. Project Gutenberg's EPUB 2 of Pride and Prejudice split chapter I across two files, so `toc` showed "Chapter I." at 152 words and an "(untitled: ...)" section of 718 (the EPUB 3 of the same book: 870); Moby-Dick's chapter 16 split the same way. In the Gutenberg text file, chapter I's heading is `Chapter I.]`, the end of an illustration caption, and the text reader folded the chapter into the preface (5,752 words).
- Hypothesis: Gutenberg's ebookmaker cuts HTML into files by size, not by chapter, and its text keeps the bracketed caption lines of the printed edition.
- Rule: text that no nav entry points at and that has no heading continues the section before it; brackets around a heading line are dropped before matching.
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

### L-013 · 2026-11-01 · toc-lists-bare-chapter-numbers: Packt chapters show as "12. 1 (1 w)" then the title
- Trigger: distilling "Deep Reinforcement Learning Hands-On" (3rd ed., Packt EPUB): each chapter number is its own one-word nav entry before the title, so the agent counted numbers by hand to cite chapters.
- Hypothesis: the nav lists the number and the title as separate entries at the same level.
- Rule: toc merges a 0-3 word number-only section into the next titled section as `Ch. N: Title`, and `toc --depth 1` lists only parts and chapters; plan a book from that, cite by chapter number.
- Evidence: C-20261101-3, 62 tests; on the real file `toc --depth 1` gives 22 chapters, 4 parts, front and back matter.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-01

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

### L-017 · 2026-11-01 · repeated-credit-lines: a per-image credit line in every section of a film book
- Trigger: distilling a film-technique EPUB: almost every section ends with a frame-grab credit (film, director, studio, year, "All Rights Reserved"), and the reader looped `read --section N` one section at a time, not knowing ranges and `--quiet` existed, so output overflowed.
- Hypothesis: the credit lines differ in names and years, so exact-repeat detection (PDF `--strip-boilerplate`) misses them; their shared ending is the stable part.
- Rule: compare short paragraphs by whole text and by their last four words with digits folded, and drop keys found in 30% or more of sections; keep it opt-in, since templated short body lines can share an ending. Tell distilling readers to batch ranges with `--quiet --max-words`.
- Evidence: C-20261101-7; on the real file `--drop-repeated` dropped 212 paragraphs, all credit lines (213 "Rights Reserved" matches; the one left is the acknowledgments page), and nothing else; 75 tests pass.

### L-020 · 2026-11-02 · image-only-epub-ocr: a scanned EPUB had a note that said no OCR was available
- Trigger: an everscout book run on a film-technique EPUB made of 256 JPEG page images (pdftohtml pages wrapped by calibre). `info` said "OCR it (... none is available)" on a machine with Windows OCR, and `rw.py ocr` refused anything but a PDF.
- Rule: an EPUB whose spine shows page images is OCR'd like a scanned PDF: `rw.py ocr FILE` reads the images in spine order (no rendering), keeps the text in the OCR cache, and info, toc, read and grep use it. An image-only EPUB often has a DjVu twin in the same folder with OCR text already in it: try that first.
- Evidence: 2026-11-02, the real EPUB: 247 page images OCR'd in 35 s with Windows OCR, 88k words; `grep -i triple-take` 20 hits. Tests: TestFiveCs (epub_page_images, note, cache, engine run). Applied: C-20261102-4.

### L-033 · 2026-11-03 · page-join-empties-page: joining a run-on page moved the whole page
- Trigger: the same handbook PDF: a page whose single paragraph starts lower case was moved onto the previous page, chained across pages, so 172 held 172-175 and cites were off by up to three pages.
- Rule: across a page break move only the run-on sentence (to the first sentence end) when at least 20 words stay behind.
- Evidence: 2026-11-03; test_page_join_moves_only_the_run_on_sentence; empty pages 45 to 4 on the real file. Applied: C-20261103-2.

### L-034 · 2026-11-03 · pdf-python-listings: Python listings in a PDF slipped past --skip-code
- Trigger: Alammar and Grootendorst, *Hands-On Large Language Models* PDF (LangChain listings): `--skip-code` dropped 107 words of about 1,500 in a chapter; `# comment` lines of eight words and calls with spaces inside (`print(f"Top hits")`) broke each run before it reached three code lines.
- Rule: in a PDF layout page a `# word` line and a line that is one whole call count as code lines; `from x import y` opens the code gate.
- Evidence: 2026-11-03; test_code_blocks_found_and_kept_as_lines; the real chapter went from 107 to 220 words dropped, section 126 from 7 to 32. Applied: C-20261103-3.

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
