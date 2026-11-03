# Learnings archive: readwright

Retired or promoted entries from [LEARNINGS.md](LEARNINGS.md), each with a reason.

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
