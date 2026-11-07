# Changelog: readwright

Every change to [SKILL.md](SKILL.md) and its companions, newest first, each with the reason. Reasons cite findings in [RESEARCH.md](RESEARCH.md) (`R-`), lessons in [LEARNINGS.md](LEARNINGS.md) (`L-`), and test runs in [TESTS.md](TESTS.md) (`T-`). State in `evergreen.json`. Protocol: MAINTENANCE.md.

Entry shape: `### C-YYYYMMDD-n · date · one-line summary`, then `because:` (IDs or "user request"), `files:` (file and section), and a sentence on what changed. Cite section headings, not line numbers.

### C-20261107-6 · 2026-11-07 · Release 0.49.0: printed pages select all their sections; read --min-para-words
- because: L-063 and user request (every book run adds to readwright)
- files: scripts/rw.py (printed_selector, drop_short_paras), tests, SKILL.md (Distilling a book). A printed page was used as a section number, so `p264` read p. 71 of a book whose pages have sub-headings. Pages now resolve through section ids.

### C-20261107-5 · 2026-11-07 · Release 0.48.2: a photo credit closing a short caption no longer opens a section
- because: user request (every book run adds to readwright); a Crowood EPUB's chapter 8 listed PHILIP CARTER and MANUEL HARLAN as sections, with body text filed under the photographers' names
- files: scripts/rw.py (split_caps), SKILL.md (Distilling a book), tests
A caps run of up to four words that closes a paragraph of 150 words or fewer is now left in the caption. Long OCR page paragraphs keep their old treatment.

### C-20261107-4 · 2026-11-07 · Release 0.48.1: PDF math-font plus and times repaired, running heads glued to a section title cut, `toc --hide`
- because: user request (every book run adds to readwright); a Cengage PDF printed a thorn for plus, A-circumflex for times and "220 Book Title The Mixolydian Mode", and exercises and CD tracks filled much of its toc
- files: scripts/rw.py (repair_symbol_font, fix_glued_section_heads, running_head_keys, toc), SKILL.md (Distilling a book), tests

### C-20261107-3 · 2026-11-07 · Release 0.48.0: OCR heads glued to a page's first words leave PDF text, letter-spaced ones too
- because: user request (every book run adds to readwright); a 2004 OCR scan set a letter-spaced head and page number before the body, in greps and toc titles
- files: scripts/rw.py (strip_colon_heads), SKILL.md (Distilling a book), tests

### C-20261107-2 · 2026-11-07 · Release 0.47.4: a printed contents page stays one section; tip for reference books
- because: L-061 `contents-page-survivors`
- files: scripts/rw.py (contents_page, refine), SKILL.md (Distilling a book), tests

### C-20261107-1 · 2026-11-07 · Release 0.47.3: side-margin page numbers leave PDF running text
- because: L-060 `margin-folio-in-text`
- files: scripts/rw.py (margin_folio_shift, strip_margin_folio), SKILL.md (Distilling a book), tests

### C-20261106-10 · 2026-11-06 · Release 0.47.2: grep says how to read a hit from its paragraph's start; tip for interview books
- because: user request (every book run adds to readwright)
- files: scripts/rw.py (grep), SKILL.md (Distilling a book), tests

A hit's offset is the match, so `read --offset` opened mid-sentence; grep now names `--at-para`.

### C-20261106-9 · 2026-11-06 · Release 0.47.1: fixed-layout EPUBs found with the viewport attributes in either order; `--offset` past the end is an error
- because: user request (fix what a book run reports); L-062
- files: scripts/rw.py FIXED_VIEWPORT, cmd_read, tests

### C-20261106-8 · 2026-11-06 · Release 0.47.0: `--drop-repeated` removes running heads glued to page text
- because: user request (fix what a book run reports)
- files: scripts/rw.py strip_glued_heads, SKILL.md Distilling a book, tests
In Case's Sound FX the head stayed in sentences split across pages, as in "EQ can be / Chapter 5 Equalization patched between". The head goes and the sentence is joined, when the same head also stands alone five times or more. Tested on synthetic text and that book. Added a tip: for craft books aimed at a neighbouring field, read for the reason behind each setting and carry over the reason, not the number.

### C-20261106-7 · 2026-11-06 · Release 0.46.3: `read --from` no longer matches the header line
- because: user request (fix what a book run reports)
- files: scripts/rw.py read, SKILL.md Distilling a book, tests
`--from` searched the printed header too, so a word in the chapter title cut into the header and returned the chapter from its start. Added a tip for project-based tutorials.

### C-20261106-6 · 2026-11-06 · Release 0.46.2: distilling tip for polemics that build a taxonomy
- because: user request (every book run adds to readwright)
- files: SKILL.md (Distilling a book)
From *How to Suppress Women's Writing*. No reader feature was missing: `--each-chars` covers sampling chapter openings; the run looped over sections by hand before noticing it.

### C-20261106-5 · 2026-11-06 · Release 0.46.1: PDF outline entries linked by name keep their sections
- because: L-061
- files: scripts/rw.py (`pdf_outline`, `parse_dests`, `parse_outline`), tests/test_rw.py
LaTeX PDFs link most outline entries by name, and those entries were dropped, so their text merged into the entry before. Their pages now come from `pdfinfo -dests`. Müller's book goes from 132 sections to 288.

### C-20261106-4 · 2026-11-06 · Release 0.46.0: read --until; tips for chapter summaries and pull quotes
- because: user request (a 445-page PDF's chapter summaries each ended in exercises and web links), L-060
- files: scripts/rw.py (cmd_read, read's arguments), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places
`read --until REGEX` prints each selected section up to its first match, searched after the section's header and title (after the `--from` match when both are set). It works with `--title`, `--section`, `--each-chars`, `--max-chars`, `--at-para`, `--out` and `--out-dir`; resume lines carry it, and a section with no match prints whole with a footer note. `^` and `$` in `--from` and `--until` now match at lines. No fragment filter: see L-060.

### C-20261106-3 · 2026-11-06 · Release 0.45.1: no empty section at a character cut
- because: L-059
- files: scripts/rw.py (`clean_cut`, rank's `--limit`), SKILL.md (distilling), tests
A `--max-chars` cut no longer ends on a section header and title with no body, and the footer resumes at that header. `rank --limit` works as `--top`. Tip for endnotes with no markers.

### C-20261106-1 · 2026-11-06 · Trailing notes that repeat chapter titles are titled as notes
because: L-058
files: scripts/rw.py (title_repeated_notes, load, back_matter_start), tests, SKILL.md (Distilling a book). Three or more trailing sections repeating an earlier title at under half its words become `Notes: Chapter N`, and `rank --body` treats them as back matter. Section numbers do not change. Tried on one EPUB.

### C-20261106-2 · 2026-11-06 · read --drop-images; a tip for rule books
because: user request (every book run adds to readwright); Typography for Lawyers run, everscout T-20261106-2
files: scripts/rw.py (read), SKILL.md (Distilling a book), tests. Figure-heavy sections carried many bare image marker lines. The flag removes them and keeps `[image: ALT]`.

### C-20261105-8 · 2026-11-05 · grep matches typographic hyphens and apostrophes
because: L-057
files: scripts/rw.py (loose_typography, cmd_grep), tests. A typed - or ' in a grep pattern now also matches U+2010, U+2011, a soft hyphen and U+2019, outside character classes.

### C-20261105-7 · 2026-11-05 · Learnings consolidation: 34 active to 11
because: consolidate:34>25
files: LEARNINGS.md (Active), LEARNINGS-ARCHIVE.md, SKILL.md (Step 4), references/formats.md (Detection, Built in, External tools), AGENTS.md (eval graders pointer). Promoted L-001, L-002, L-004, L-009, L-011, L-012, L-016, L-018, L-025, L-034, L-036, L-037, L-038, L-039, L-040, L-043, L-045, L-046, L-049. Merged and archived L-019 and L-035 into L-034 `printed-page-drift`, L-048 into L-044, L-050 into L-051. Tightened and put in the standard fields L-005, L-008, L-010, L-041, L-042, L-044, L-047, L-051, L-052, L-053, L-054. Dropped L-052's advice to run first reads one at a time, which the atomic caches of 0.44.2 and 0.44.4 made stale. Step 4 now states smart case. rw.py is unchanged.

### C-20261105-6 · 2026-11-05 · Release 0.44.4: heads of short chapters go, repeated real headings and captions stay, converter caches are atomic
because: L-053, L-054; open items left by 0.44.1 and 0.44.2.
files: scripts/rw.py (`pages_cluster`, `CAPTION_LINE`, `running_head_keys`, `beside_folio_keys`, `strip_glued_folio`, `load_pdf`, `load_via_calibre`, `load_via_office`, `load_via`), tests/test_rw.py. A head with 2 to 4 copies beside a folio goes when it keeps the book's every-other-page rhythm, sits on the book's head edge, and a proven head fills the pages between. A line that recurs spread out stays, at a page edge or beside a folio, unless its number follows the page or it fills a fifth of a book of 100 pages or more. A caption is never a head, and the page's own number comes off `122 Exhibit 4-3` and `Exhibit 4-3 122`. calibre, soffice, pandoc and markitdown caches use `tmp_cache` and `publish_cache`; a failed tool leaves no temp file. Paragraph numbers shift on PDFs with such heads.

### C-20261105-5 · 2026-11-05 · Release 0.44.3: no stray space before punctuation in EPUB text
because: a pretty-printed O'Reilly EPUB read "is cost ." and "Figure 4-9 )." from index anchors and line breaks in its markup, which also breaks phrase searches.
files: scripts/rw.py (`HTMLText.handle_data`, `handle_starttag`), tests/test_rw.py, SKILL.md (distilling tip). Space before punctuation goes after an anchor with no link or across a line break; other spacing stays.

### C-20261105-4 · 2026-11-05 · Release 0.44.2: cache files appear whole or not at all
because: a run during the 0.44.1 check reported 94% fewer words for one PDF and no error, when two first reads of one file ran at once.
files: scripts/rw.py (`tmp_cache`, `publish_cache`, PDF text, layout, font and OCR caches), tests/test_rw.py. Tools write to a private temp name that moves into place when finished. The other converters' caches (calibre, soffice, pandoc) were not changed.

### C-20261105-3 · 2026-11-05 · Release 0.44.1: alternating running heads set beside a page number leave the text
because: L-052; a textbook PDF printed the part name on even pages and the chapter on odd ones, each on its own line by a bare folio, so about 100 heads opened false sections and split real ones.
files: scripts/rw.py (`folio_pairs`, `folio_shifts`, `beside_folio_keys`, `first_near_edge`, `strip_folio_heads`, `load_pdf`), tests/test_rw.py, SKILL.md (distilling section). A number that matches the page's own shift goes from the top or foot of a PDF page. A line beside it on 5 or more pages is a head and goes wherever it lands in the first four or last three lines. An outline title of that page and the book's first copy, when no number sits beside it, stay. Paragraph numbers and section numbers shift on such books.

### C-20261105-2 · 2026-11-05 · Release 0.44.0: code in table cells counts as code; `read --max-row-words`
because: L-051; a Manning book sets each chat turn in a two-cell table, so its listings passed `--skip-code` and model replies filled much of the sections read.
files: scripts/rw.py (HTML parser, `cut_rows`, `read`), tests/test_rw.py, SKILL.md (distilling section). A `<pre>` in a cell becomes its own code block after its row, so its lines stay and `--skip-code` drops it, which shifts paragraph numbers in such books. `--max-row-words N` cuts long rows and marks each cut. Tried on this one EPUB.

### C-20261105-1 · 2026-11-05 · Release 0.43.2: `--skip-code` also drops listing captions and callout legends
because: L-050; a Manning testing book printed `Listing 5.23 ...` and circled-number lines with no code to explain, 45 of them in one section.
files: scripts/rw.py (`skip_code`, `code_note`), tests/test_rw.py, SKILL.md (distilling section). A short caption right before a block and the run of legends right after one go, and the footer counts them; paragraph numbers under `--skip-code` shift on such books. A legend's explanation goes with it, so read without the flag when a listing matters.

### C-20261104-7 · 2026-11-04 · Release 0.43.1: nested lists keep their depth; distilling tip on the sources a book leans on
because: L-049; a testing book's list of four bad metrics printed each metric level with its examples, so sub-points read as new points.
files: scripts/rw.py (`render_paras`, HTML parser), tests/test_rw.py, SKILL.md (distilling section). HTML and EPUB items two levels down now print indented; paragraph numbers do not change, character offsets inside lists can.

### C-20261104-6 · 2026-11-04 · Release 0.43.0: `read --lang`, a note carried over a page, spread and roman folios
because: L-047, L-048; user request after a trilingual type manual's OCR layer printed everything three times; HANDOFF open items from 0.42.0 and L-044.
files: scripts/rw.py (lang_scores, para_lang, filter_lang, lang_note, cmd_info, cmd_read, cmd_grep, carry_foot_notes, fixed_folio_lines); tests/test_rw.py; SKILL.md (Step 3, Distilling a book)
`read --lang CODE` and `grep --lang CODE` keep one language's paragraphs, and `info` names the flag on a book with substantial paragraphs in two or more. A foot note left open takes its lower-case tail from the next page's foot, or from its top when the body sentence above is closed. Fixed-layout folios are also found at two pages a file and in lowercase roman numerals.

### C-20261104-5 · 2026-11-04 · Release 0.42.0: PDF foot notes leave the sentence, page-break hyphens heal, long lines are paragraphs
because: L-045, L-046; a book run on a PDF printed notes in mid-sentence, kept `pol-ish` and `dead-lines`, and glued subheads and epigraphs into body text; user request for the how-to book tip.
files: scripts/rw.py (join_broken, unfolded_text, unfold_page, lift_foot_notes, merge_wrapped, load_pdf); tests/test_rw.py; SKILL.md (Distilling a book); references/formats.md
A note at a page foot, with a call to its number in the body above, moves after the interrupted paragraph as `[note N: text]`, and the sentence and any split word rejoin. A hyphen at a break is judged by the book's own word counts. When most text sits on lines over 200 characters, each line is a paragraph, so lowercase subheads and `Q /` epigraphs stand alone.

### C-20261104-4 · 2026-11-04 · Release 0.41.2: `--skip-code` drops numbered code callout markers
because: an O'Reilly EPUB read with `--skip-code` left lines such as `[image omitted: 1.png]` pointing into removed code.
files: scripts/rw.py (CODE_CALLOUT, skip_code); tests/test_rw.py; SKILL.md (Distilling a book)
In a section with code, a paragraph that is only a picture marker with a numeric name goes with the code. Named pictures and sections without code keep theirs. Tip on code-heavy books added.

### C-20261104-3 · 2026-11-04 · Release 0.41.1: UTF-8 beats a wrong meta charset, `no text layer` names rw.py commands, markers and folios stay out of fixed-layout sentences
because: L-043, L-044; a book run printed "Donât" and "Ã¶" from an EPUB declaring UTF-8 in its XML line and iso-8859-1 in its meta; open items on the scan note and on markers below the caption rule.
files: scripts/rw.py (decode_text, scan_note, FIXED_MARKER, fixed_folio_offset, split_fixed_markers, split_fixed_page, load_epub); tests/test_rw.py; SKILL.md (Distilling a book); references/formats.md
`decode_text` tries strict UTF-8 first on non-ASCII data, then the hint, then cp1252; a UTF-16 or UTF-32 hint still goes first, and real latin-1 still reads. No cache change: conversion cache keys include VERSION and the EPUB text is not cached. The no-break-space paragraphs that printed "Â" now clean to nothing and are dropped. The scan note names `rw.py page` and `rw.py ocr`. In a fixed-layout EPUB, picture markers (`[image: alt]` too) and folios go beside the text with or without a caption size; a folio is a bare number rising with the spine through a quarter of the pages, at least 3. With such folios a sentence over a page turn also rejoins.

### C-20261104-2 · 2026-11-04 · Release 0.41.0: `page` command, scrambled text layer note, fixed-layout captions leave the body
because: L-041, L-042. A 129 MB plate book is too big for an agent's image reader and its OCR layer glues words; Typeset in the Future had captions and folios in the middle of sentences.
files: scripts/rw.py (cmd_page, page_numbers, scrambled_note, cmd_info, fixed_css, fixed_styles, fixed_plan, split_fixed_page, rejoin_fixed_pages, load_epub); tests/test_rw.py; SKILL.md (Step 1, Distilling a book); README.md (Commands); references/formats.md; metadata.version and evergreen.json version, which had fallen behind
`rw.py page FILE PAGES` writes PNGs with mutool or pdftoppm. `info` notes a PDF text layer with 5 or more lowercase runs of 18+ letters at 0.5 or more per 1,000 words; `read` output is unchanged. A fixed-layout EPUB whose CSS shows a recurring smaller type size moves those blocks after the body paragraph, marked `[caption] `, sets folios and pictures beside it, and rejoins sentences over a page turn; a book without that signal behaves as in 0.40.2.

### C-20261104-1 · 2026-11-04 · Release 0.40.2: fixed-layout EPUB lines rejoin into paragraphs
because: Typeset in the Future run: every printed line and italic run was its own block, so `--drop-repeated` deleted 1,495 of them, film titles included, and sentences lost their subjects.
files: scripts/rw.py (merge_fixed_layout, load_epub); tests/test_rw.py; SKILL.md (Distilling a book)
A page whose viewport meta gives a width and height is read as fixed layout, and its lines join until a sentence ends. Captions still sit among the body text in file order.

### C-20261103-23 · 2026-11-03 · Release 0.40.1: a list inside a table cell keeps its items apart
because: Bogleheads' Guide run: a ranked list in a one-cell table came out as one run-on line, hiding where each item ended.
files: scripts/rw.py (HTML parser), SKILL.md (Distilling a book), tests/test_rw.py.

### C-20261103-22 · 2026-11-03 · Release 0.40.0: `read --chapter` selects by printed number
because: Universal Principles of Typography run: section numbers from toc were asked for as if they were chapter numbers, and `--section 78` returned ch. 68.
files: scripts/rw.py (read), SKILL.md (Distilling a book), tests/test_rw.py.

### C-20261103-21 · 2026-11-03 · Release 0.39.0: `info` flags pages missing from a scan
because: Detail in Typography run: the two-up scan lacks pp. 12-13 and 44-45, losing most of the Emphasis chapter, and nothing said so; only a reader who compared the contents would notice.
files: scripts/rw.py (missing_page_note), SKILL.md (Distilling a book), plugin.json, tests. For OCR text, the longest rising run of each page's last bare number gives printed pages; a jump of at least 3 and twice the usual step gets a note.

### C-20261103-20 · 2026-11-03 · Release 0.38.0: `image`, superscript powers
because: Little Book of Valuation run: tables and formulas are JPEGs marked `[image omitted: NAME]` with no way to open them, and `1.1021<sup>5</sup>` read as 1.10215, a wrong number.
files: scripts/rw.py (cmd_image, handle_data), SKILL.md (Distilling a book), plugin.json, tests. `image FILE NAME --out-dir D` writes the picture; a digit in `<sup>` after a digit reads `^`. The root plugin.json had stayed at 0.34.0; a test now keeps both manifests on the script's version.

### C-20261103-19 · 2026-11-03 · Release 0.37.0: `rank --body`
because: The Great Wave run: `rank` put a bibliography section first and per-chapter notes files beside the chapters they annotate.
files: scripts/rw.py (rank, back_matter_start), SKILL.md (Distilling a book), tests. Leaves out everything from a bare NOTES, BIBLIOGRAPHY or INDEX section at least 30% into the words; off by default.

### C-20261103-18 · 2026-11-03 · Release 0.36.0: `read --from REGEX`
because: Better Web Typography run: `grep "Key takeaways"` printed long context per chapter, when only the tail of each section was wanted.
files: scripts/rw.py (read), SKILL.md (Distilling a book), tests. Each selected section prints from its first match on; sections with no match are skipped.

### C-20261103-17 · 2026-11-03 · Release 0.35.1: figure link lines no longer read as formulas; a caption replaces its repeated alt text
because: Web Form Design run: each figure printed its alt, its caption and "top image: [formula: image] http://..." lines, a noticeable share of some sections.
- files: scripts/rw.py (`FIGURE_LINK`, flush), SKILL.md (Distilling).

### C-20261103-16 · 2026-11-03 · Release 0.35.0: toc --group works on labelled pages and run-on contents
because: Web Typography run: `toc --group` refused a 348-page PDF with no outline, because printed labels and line breaks in page titles failed its match (L-040).
- files: scripts/rw.py (`page_groups`, `leader_groups`, page titles), SKILL.md (Step 2, Distilling).

### C-20261103-15 · 2026-11-03 · Release 0.34.0: toc --code shows the code words per section; distilling tip on printed outputs and cited sources
because: Building LLM Powered Applications run: the outline listed a section at 867 words that held 92 of prose, and the reader spent tokens on console transcripts before reaching for --skip-code.
files: scripts/rw.py (code_words, toc_lines, toc --code), SKILL.md (distilling), tests/test_rw.py.

### C-20261103-14 · 2026-11-03 · Release 0.33.0: stray print hyphens in EPUB text are healed
- because: book distill of Tannen, You Just Don't Understand: `stu-dent`, `ex-ample` and `in-formation` sat mid-line and hid words from `grep`.
- files: scripts/rw.py (`heal_stray_hyphens`), tests/test_rw.py, plugin versions, SKILL.md Distilling a book. A pair joins only when the book prints the joined word three times or more and the hyphenated form at most once or a tenth as often; real prefixes stay.

### C-20261103-13 · 2026-11-03 · Release 0.32.2: running heads with roman page numbers are dropped
- because: book distill of Huss and Zonca, Generative AI on Kubernetes: `xxx | Introduction` stayed in the front matter text.
- files: scripts/rw.py (RUNNING_HEAD), tests/test_rw.py. The pipe form now accepts lower-case roman numerals at page edges.

### C-20261103-12 · 2026-11-03 · Release 0.32.1: distilling tip on glued words and surprising figures
- because: book distill of Raff, Farris and Biderman, How Large Language Models Work: glued words were in the EPUB source, and a 10 GB vocabulary figure failed against the 2.1 MB tokenizer file
- files: SKILL.md (Distilling a book). No reader code changed.

### C-20261103-11 · 2026-11-03 · Release 0.32.0: clean PDF chapter openers and glued running heads
- because: book distill of Zhai and Massung, Text Data Management and Analysis: chapters opened "1Text Su6mmarization" and running heads such as "8.3 Scorer 155" joined the next paragraph
- files: scripts/rw.py (fix_chapter_openers, run by load_pdf), SKILL.md (Distilling a book), tests/test_rw.py. Only numbers matching the section's own chapter are touched.

### C-20261103-10 · 2026-11-03 · Release 0.31.0: per-section caps for multi-section reads, image and math markers, ISBN in info
- because: user request (a reader distilling an EPUB textbook: a formula and TABLE 15-1 set as images vanished silently, one long section crowded out the rest of a multi-section read, and the copyright page lacked authors)
- files: scripts/rw.py (HTMLText.handle_starttag, EPUB metadata, cmd_read, read --each-chars), SKILL.md Distilling a book, ../../tests/test_rw.py, version in the five places
`read --each-chars N` cuts each selected section at N characters with its own resume line (`--max-chars` still caps the total). An `<img>` alone in a block now prints `[image omitted: NAME]` or `[image: ALT]` when the alt text says something; MathML prints `[math: ALTTEXT]` or `[math omitted]`. `info` adds `isbn` from an ISBN-shaped `dc:identifier` and decodes entities in the description. Word counts of image-heavy books rise slightly, since the markers count as words.

### C-20261103-9 · 2026-11-03 · Release 0.30.0: collapsed EPUB sections split at a one-line printed contents page
- because: L-039 (a book run on an EPUB whose only outline entry was Start: one section held 90% of the text and two contents-page lines opened false sections)
- files: scripts/rw.py (oneline_contents, chapter_list, split_at_contents, contents_entry, refine), SKILL.md Distilling a book, ../../tests/test_rw.py, version in the five places
A printed contents page with one chapter per line (`1 TITLE`, no page numbers) now gives the chapter list for the giant-section split, ahead of the two-line PDF reader, which took the body's own `1` / `TITLE` openers for contents entries and so found nothing to cut. When the chapter number sits in its own paragraph above the title, the cut is at the number. A heading-like line (`INTRODUCTION`, `EPILOGUE: ...`) that opens a later cut with the same first word and sits among short lines is a contents-page line and no longer starts a section. Books that do not trigger keep their section ids.

### C-20261103-8 · 2026-11-03 · Release 0.29.0: Cengage textbook PDF fixes (printed pages in outline titles, copyright footers, smart-case grep, symbol-font math warning)
- because: L-035, L-036, L-037, L-038 (a book run on Arnold, *Economics*, 11th ed., Cengage PDF)
- files: scripts/rw.py (printed_span, printed_labels, drop_page_footers, pdf_math_fonts, math_note, smart_case, cmd_grep, tools), SKILL.md Distilling a book, ../../tests/test_rw.py, version in the five places
Outline section titles in a PDF now give the printed pages beside the PDF pages; `printed_labels` also reads a mixed-case running head on a page's top line (`130 PART 2 ...`, `Chapter 6 ... 131`). A copyright footer that starts with Copyright and says all rights reserved or may not be copied, on 30% or more of the pages, is dropped by default (RW_KEEP_FOOTERS=1 keeps it); on the test book it was 719 copies and about 10% of the text. `grep` is smart case: an all-lower-case pattern matches any case, `--case-sensitive` turns that off, a pattern with a capital is unchanged. `info` and `toc` warn when pdffonts lists a Mathematical Pi or Universal Greek/News font; the symbols are not repaired (see L-036).

### C-20261103-7 · 2026-11-03 · Release 0.28.0: printed page labels for PDFs whose offset drifts
- because: L-034 (an everscout book run, Styhre *Indie Video Game Development Work*: two reader agents took different offsets, -7 and -9, and cited pages wrongly)
- files: scripts/rw.py (printed_labels, printed_selector, pdf page sections, info), SKILL.md Reading tips, ../../tests/test_rw.py, version in the five places
When no single printed-page shift holds, each page section's toc title carries its own `(p. N)` from the running head, a bare number or a copyright footer, `info` says the offset drifts, and `read --section p153` or `p153-p160` reads by printed page (also through a single shift).

### C-20261103-6 · 2026-11-03 · Learnings consolidation: 34 active to 13
- because: consolidate:34>25
- files: LEARNINGS.md (Active), LEARNINGS-ARCHIVE.md (new)
- Promoted to archive the 21 entries whose rules rw.py now implements and tests: L-003, L-006, L-007, L-013, L-014, L-015, L-017, L-020 to L-034. Fixed the duplicate L-033 ID (pdf-python-listings is now L-034), removed the template example, widened L-005's unverified range to MuPDF 1.28.

### C-20261103-5 · 2026-11-03 · Refresh: converter versions, EPUB 3.4 CRD, one-level disclosure
- because: R-20261103-1, R-20261103-2
- files: RESEARCH.md (Current understanding, Open questions, Search plan)
- Fact updates only; SKILL.md unchanged. Search plan gains forum lines (MobileRead, calibre tracker), MuPDF and LibreOffice sources, and EPUBCheck for testing.

### C-20261103-4 · 2026-11-03 · Release 0.27.0: grep --per-section N spreads hits across sections
- because: an everscout book run (*Advanced Retrieval-Augmented Generation*, Wei and Wu): one section's code block took every hit of a 20-hit grep
- files: scripts/rw.py (cmd_grep, grep parser), SKILL.md Distilling a book, ../../tests/test_rw.py, version in the five places
`grep --per-section N` shows at most N paragraphs from each section and says how many it held back. The skill gains a tip: EPUB formulas print as `[formula: image]`, and a sentence cut short (`with 75.`) is usually in the EPUB itself.

### C-20261103-3 · 2026-11-03 · Release 0.26.0: --skip-code finds Python listings in PDFs
- because: L-033 `pdf-python-listings` (an everscout book run, *Hands-On Large Language Models* PDF)
- files: scripts/rw.py (CODE_LINE, CODE_HINT), SKILL.md Distilling a book, ../../tests/test_rw.py, version in the five places
A `# word` comment line and a line that is one whole call (spaces inside allowed) now count as code lines when a PDF layout page is scanned for listings, and `from x import y` opens the gate that runs the layout pass. Program output printed as prose stays in. The skill gains a tip: with several copies of one book, read the final edition, not an early-access draft.

### C-20261103-2 · 2026-11-03 · Release 0.25.0: toc --group from a printed contents page; a page join no longer empties the page
- because: L-032 `contents-title-then-page` (an everscout book run, Futter, *The GameDev Business Handbook* PDF: no outline, no running heads, so `toc` listed 277 pages and `--group` folded nothing)
- files: scripts/rw.py (join_split_pages, SPLIT_TAIL_RE, contents_groups, CONTENTS_HEAD_RE, group_lines, cmd_toc note, load_pdf page_shift), SKILL.md Step 2 toc, ../../tests/test_rw.py, version in the five places
When pages share no running heads, `--group` reads a page that opens with Contents, takes each title line followed by a bare page number (shifted by the printed-page offset) and prints the page runs, front matter first. Plain `toc` notes it. Index entries with no page number join the last part. A page that opens mid-sentence gives only that run-on sentence to the previous page; before, pdftotext's one-paragraph pages moved whole and the book showed about 45 empty pages with their text piled on the page before (L-033).

### C-20261103-1 · 2026-11-03 · Release 0.24.0: rank sections by BM25; equation pictures marked; grep names swapped arguments
- because: user request (every book run adds a reader feature); the reader of Manning, Raghavan and Schutze, *Introduction to Information Retrieval* got grep hits in book order with no ranking, and `grep "champion list" FILE` failed with a bare no-such-file
- files: scripts/rw.py (RANK_STOP, rank_terms, bm25, cmd_rank, cmd_grep, rank parser, the HTML parser img and sub handling), SKILL.md Step 4 and Distilling a book, ../../tests/test_rw.py, version in the five places
`rank FILE WORDS` scores each section (or paragraph with `--paras`) by Okapi BM25 (k1 1.2, b 0.75, the book's sec. 11.4.3) over lowercased words with stop words dropped and a light suffix strip, and names query words the book lacks. grep and rank say the file goes first when the second argument is the file. An EPUB equation set as a picture prints `[equation 11.32: image]` (from its `eq_` id) and a picture mid-sentence `[formula: image]`, so a gap no longer reads as a finished sentence; `<sub>` prints as `_` after a letter (`tf_td`, `k_1`). The formula text itself is a picture and stays unread.

### C-20261102-20 · 2026-11-02 · Release 0.23.0: double-spaced PDF pages, glued MATLAB listings, one-cell-per-line tables
- because: L-030 `pdf-double-spaced`, L-031 `pdf-table-cells` (a signal-processing textbook PDF: every printed line came out as its own paragraph, a word split across a column break stayed `fre- quency`, a MATLAB listing after a `Repo N: file.m` marker was glued into the prose so `--skip-code` missed it, and a table printed one cell per line)
- files: scripts/rw.py (merge_wrapped, collapse_cells, CELL_RE, CELL_RUN, REPO_MARK, ML_LINE, LISTING_CAPTION, split_listing, text_paras, load_pdf, load_ocr), SKILL.md Distilling a book, ../../tests/test_rw.py (TestPdfDoubleSpaced), version in the five places
Within a PDF page, a paragraph ending in a hyphen or without a sentence end joins the next when that starts lower case; on a double-spaced page (most paragraphs one line of about the same width) a full-width line joins the next too. A hyphen at the break is dropped when the book prints the joined word more often than the hyphenated one. The leading lines of a paragraph that read as code (CODE_LINE, MATLAB `%` comments, lines ending in `;`) become a `pre` block, after a Repo marker from one line, elsewhere from CODE_RUN lines; a following `Listing N.N` caption becomes its own paragraph. Six or more one-token paragraphs in a row become one row paragraph joined with ` | `. The full table layout is still open (HANDOFF).

### C-20261102-19 · 2026-11-02 · Release 0.22.0: --skip-code drops code lead-ins
- because: a book distill (a Packt LLM tutorial EPUB, 4 sections): with the code gone, 14 sentences ending in ':' that introduced the blocks stayed behind, dangling
- files: scripts/rw.py (skip_code, code_note), SKILL.md Distilling a book, ../../tests/test_rw.py (test_skip_code_drops_colon_lead_ins), version in the five places (SKILL.md and evergreen.json had stayed at 0.20.0)
With `--skip-code`, a paragraph or list item ending in ':' directly before a dropped code block is dropped too and counted in the trailer ("and K lead-in lines"); a colon line before prose stays.

### C-20261102-18 · 2026-11-02 · Release 0.21.0: info flags swapped title and author
- because: an everscout book run (Tannen, Conversational Style EPUB): the metadata title was the author's name and the author field held the title, so the book was filed under the author
- files: scripts/rw.py (meta_swapped, cmd_info), SKILL.md Distilling a book, tests/test_rw.py
`info` prints a note naming the probable title and author when the title is a person's name and the author field is the book title, both found in the file name.

### C-20261102-17 · 2026-11-02 · Release 0.20.0: read --headings
- because: an everscout book run (a Unity for Android tutorial EPUB): to skim a long chapter the reader wanted only its subheadings and filtered short lines with awk, which also caught figure captions and code
- files: scripts/rw.py (flags_used, heading_lines, cmd_read, main), SKILL.md (Reading options, Distilling a book), ../../tests/test_rw.py (TestHeadings), version in the five places
`read --section N --headings` prints the heading paragraphs (Para kind `h`) of each chosen section, indented by level, with the paragraph number `--at-para` takes and the words up to the next heading; a heading equal to the section title is left out. A section without headings says so and points to `toc --group` or grep. The last line repeats any paragraph-dropping flags to pass with `--at-para`, since they change the numbering. On the real book, section 12 listed 20 headings in three levels.

### C-20261102-16 · 2026-11-02 · Release 0.19.0: read --drop-epigraphs; one-pass tip for short books
- because: L-029 `quotation-epigraphs` (a short creativity book opened most sections with a quotation and a dash attribution, about 40 of them)
- files: scripts/rw.py (EPIGRAPH_MAX_WORDS, ATTRIB_MAX_WORDS, QUOTED_RE, ATTRIB_RE, drop_epigraphs, cmd_read, main), SKILL.md (Distilling a book), ../../tests/test_rw.py (test_drop_epigraphs), version in the five places
`read --drop-epigraphs` drops a paragraph of 150 words or fewer wholly in straight or curly quotation marks when the next paragraph starts with an em dash, en dash or `--` and is 8 words or fewer; both go and one advice line gives the count. A quotation with no attribution line stays. Off by default. Distilling tip: read a book under about 30k tokens in one `--section A-B --out FILE` pass; with `--drop-epigraphs`, cite the author's ideas, not the people quoted. On the real book 80 paragraphs went (40 pairs) and no body text.

### C-20261102-15 · 2026-11-02 · Release 0.18.0: split a giant PDF section at running heads; collapse contents dot leaders
- because: L-027 `pdf-running-head-split` and L-028 `contents-dot-leaders` (an Apress PDF: the outline stops at the Introduction, which held 90% of the text; its contents printed 60-character runs of U+FFFD)
- files: scripts/rw.py (RUN_HEAD_RE, OPENER_LINE_RE, run_head_chapters, load_pdf, LEADER_RE, collapse_leaders, load), SKILL.md (Distilling a book), ../../tests/test_rw.py (test_giant_pdf_section_splits_at_running_heads, test_contents_dot_leaders_collapse), version in the five places
Inside a PDF section over half the text and BIG_SECTION_CHARS, pages whose first line is `Chapter N <sep> Title` (sep ■, |, :, -, en or em dash) start chapter sections where N changes, from the `CHAPTER N` opener page when there is one, else the head-less page before the first head. Needs 3 chapters in order; files without such heads are unchanged. Chosen over the printed contents page because these page numbers are printed numbers (offset from PDF pages) and the contents layout varies; the heads give PDF pages directly. Runs of 3+ U+FFFD or 4+ `.`, `·`, `…` between text and a page number become ` … ` in every section title and paragraph at load. The Apress book went from 6 sections to 14, chapters 1-8.

### C-20261102-14 · 2026-11-02 · Release 0.17.0: a giant section splits at the printed contents' chapters
- because: L-026 `printed-contents-split` (a Packt 2024 PDF whose bookmarks stop at the Preface: one section held 94% of the text)
- files: scripts/rw.py (contents_chapters, contents_run, listed_chapters, chapter_list, title_pattern, split_at_contents, load), SKILL.md (search, Distilling a book), ../../tests/test_rw.py (test_giant_section_splits_at_printed_contents, test_giant_section_stays_whole_without_contents), version in the five places
Automatic, like refine: when one section holds over half the text and BIG_SECTION_CHARS, chapter titles are read from the printed contents page (bare number, title lines, page number; numbers in order) and from "Chapter N, Title" lists, and the section is cut at the first paragraph, in order, that opens with each title (punctuation-insensitive). Needs 3 chapters found; else the section and the grep note stay. The Packt book went from 12 sections to 23, chapters 1-11.

### C-20261102-13 · 2026-11-02 · point Discord to everscout's invited-bot reader
- because: user request (2026-11-02): a legal way to read Discord
- files: SKILL.md (before Step 1)
- One line: live channels go through everscout's es_discord.py; a user's own export reads as JSON or HTML. Unreleased.

### C-20261102-12 · 2026-11-02 · Release 0.16.0: `terms` lists a glossary's headwords
- because: the FilmCraft run (everscout ai-video): its glossary runs each term into its definition (`Backlight A process...`), so picking vocab meant reading 2,000 words by eye
- files: scripts/rw.py (glossary_term, cmd_terms), SKILL.md (Reading), ../../tests/test_rw.py (TestGlossaryTerms), version in the five places
`RW terms FILE` finds sections titled Glossary, Key terms or Definitions (or `--section N`) and prints one headword per line with the opening of its definition.

### C-20261102-11 · 2026-11-02 · Release 0.15.1: `read --out` says when --max-chars cut the selection
- because: an AI Superpowers reader agent (everscout global-economics run) could tell a 40,000-character `--out` file was cut only by comparing word counts; the stdout path already had a footer
- files: scripts/rw.py (cmd_read --out branch), SKILL.md (Reading), ../../tests/test_rw.py (test_read_out_cut_says_where_to_resume), version in the five places
`read --out FILE --max-chars N` now cuts at the same clean break as stdout and prints where to resume (`--offset B`). Also noted from that run, not built: grep's first 20 hits can all come from early chapters; narrow with `--section`.

### C-20261102-10 · 2026-11-02 · Release 0.15.0: code listings, grep --after, quieter continue hint, cut footer after --offset
- because: two reader agents on a programming-book run (Python scripting for Blender animation) reported a lost indent in a `--compact` read, a misleading cut footer after `--offset`, no way to see the code after a prose grep hit, and the short-selection hint on nearly every subsection (L-025 `pre-crlf-nbsp-code`)
- files: scripts/rw.py (HTMLText.flush, render_paras, cmd_read footer and hint, continues, cmd_grep, grep parser, usage), SKILL.md (Reading, search, Distilling a book), ../../tests/test_rw.py (TestReaderFixes), version in the five places AGENTS.md lists
`<pre>` text loses CR line ends and no-break-space indents become spaces; consecutive one-line `<pre>` blocks print as one listing. The reported unindented `ob.select_set(False)` is in the EPUB's own source, so it stays. After `--offset K` the footer says `show the rest with --offset K --max-chars N`. `grep --after N` shows the paragraphs after each hit up to `--width`. The short-selection hint fires only for a title page (under 60 words) or a next section that is untitled, continued, or same-titled. `--section 61,80,87` and `12,189-190` already worked; now documented.

### C-20261102-9 · 2026-11-02 · Release 0.14.0: toc --group folds outline-less PDF pages into chapters
- because: L-023 `pdf-pages-by-running-head` (everscout run on Fricker, Epistemic Injustice)
- files: scripts/rw.py (page_groups, group_lines, cmd_toc, toc parser), SKILL.md (toc), README.md (toc), tests/test_rw.py, version in the five places AGENTS.md lists
`rw.py toc FILE --group` prints page ranges per running head ("20-40. Testimonial Injustice (9,135 w)"), so a reader plans and reads by chapter with `--section 20-40`. `--strip-boilerplate` now also drops a page's repeated running head (L-024 `page-running-head`; strip_furniture), and the distilling tip gives readers grep's `--width`, `--max` and `--count`.

### C-20261102-8 · 2026-11-02 · Release 0.13.1: clean PDF outline titles and ligatures
- because: two reader agents on an everscout book run (Mateer, Coppock, Essentials of Economics) saw section titles ending in a literal `\r` and words with ligature characters (Diﬃcult) that a grep for "difficult" misses
- files: scripts/rw.py (parse_outline, clean, PDF loading), tests/test_rw.py
MuPDF's escaped `\r`, `\n` and `\t` in an outline title become a space; ligature characters (U+FB00-FB06) are spelled out in titles and PDF text. Still open: small-caps titles split by pdftotext (Tabl e), and sections that open with the previous section's continued text or mix sidebar text into the body (the PDF layout item).

### C-20261102-7 · 2026-11-02 · Release 0.13.0: read --compact; reader-agent brief tip
- because: a reader agent on an everscout book run (Levinson, Guerrilla Marketing) stripped blank lines with grep to save tokens, missed `--out`, and first sampled 3,500 characters per section
- files: scripts/rw.py (read), SKILL.md (Reading, Distilling a book), tests/test_rw.py
`read --compact` prints one newline between paragraphs; it refuses `--at-para`, whose counts follow the full layout. The distilling section gives the full read line to brief reader agents with.

### C-20261102-6 · 2026-11-02 · Release 0.12.0: read --out-dir writes one file per section
- because: a reader agent on an everscout book run (Doctorow, The Reverse Centaur's Guide to Life After AI) found multi-section reads produced one very large output and asked for per-section files
- files: scripts/rw.py (cmd_read, read parser), SKILL.md (reading section), tests/test_rw.py
`rw.py read FILE --section 12,14,16 --out-dir DIR` writes `NNN-title.txt` per section and prints each file's size, so an agent opens only the chapters it needs.

### C-20261102-5 · 2026-11-02 · Release 0.11.1: a --max-chars cut ends at a paragraph or sentence break
- because: a reader agent on an everscout book run (Kuang and Fabricant, User Friendly) had a chapter cut mid-sentence 750 characters before its end
- files: scripts/rw.py (clean_cut, cmd_read), SKILL.md (reading limits, Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- A cut read now backs off to the last paragraph break, else line break, else sentence end, else space, within the piece's last quarter; the footer's `--offset` resumes exactly there, so nothing is lost or repeated. The distilling tip says to size a reader's cap with a margin.

### C-20261102-4 · 2026-11-02 · Release 0.11.0: OCR for image-only EPUBs, ALL-CAPS headings split one-section books, PDF code blocks keep their lines
- because: an everscout book run on a film-technique book (L-020 `image-only-epub-ocr`, L-021 `inline-caps-headings`) and the everscout handoff's PDF layout item (L-022 `pdf-code-layout`)
- files: scripts/rw.py (epub_page_images, load_epub, scan_note, ocr_pages, cmd_ocr, caps_runs, split_caps, refine, structure, code_blocks, mark_code, pdf_layout, text_paras, load_pdf), SKILL.md (Distilling a book), references/formats.md (scans, PDF), ../../tests/test_rw.py (TestFiveCs), version in the five places AGENTS.md lists
- `rw.py ocr` takes an EPUB whose spine shows page images: it OCRs them in spine order with the same engines and cache, and the EPUB then reads from that text; the no-text note offers it (and says "neither is available" for EPUBs, where ocrmypdf does not apply). A section over 12,000 words with no headings, from any loader (calibre's DjVu output, plain text, OCR), is split at ALL-CAPS headings, inline ones included: repeated page-opening caps phrases become chapters (or are dropped as the book's title), other caps runs after a sentence end become topics. PDFs whose text hints at code get a second, cached `pdftotext -layout` pass; code blocks found there replace their flattened words as `pre` paragraphs with indentation. Tables, definition lists and sidebars are still flat.
- The ALL-CAPS split no longer makes a chapter of a topic head on a chapter's facing pages (ACTION AXIS and MATCHING inside CONTINUITY in the OCR'd book): a head that starts while the previous chapter's own head still shows on most pages is a topic.

### C-20261102-3 · 2026-11-02 · Release 0.10.2: pipe-less PDF running heads, sentences split across pages, words split without a hyphen, captions
- because: two reader reports on an O'Reilly PDF read through pdftotext (heads like "42  Chapter 3: ..." and bare page numbers; "current user" / "message to" split by a page break; "tikto ken", "Inter viewChain"; "commaseparated"; "Figure 4-6." captions inside paragraphs)
- files: scripts/rw.py (running_head_keys, strip_running_heads, join_split_pages, keep_break_hyphen, rejoin_spaced_words, CAPTION_SPLIT, load_pdf), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- A page-edge line that is a number plus a title (either order, no pipe) is dropped when that title opens or closes 3+ pages or is an outline title; a bare page number and a bare title on a fifth of the pages go too; a line ending in . ? ! : , ; never does. A paragraph is joined across a page break when it lacks sentence-end punctuation and the next page starts lower case. Using the book's own word counts: a line-end U+2010 is kept when the hyphenated form is printed more often than the joined one; two tokens are joined when the joined word (same capitals) appears twice and one half is rare, never two capitalised words; a hyphen pdftotext lost is put back when the book prints the hyphenated form at least as often (not in URLs, paths or CamelCase). "Figure/Table/Example N-N." captions start a new paragraph. Checked on the reported book: every join listed and reviewed. Not fixed: code blocks flattened, tables and two-column text read column-major, definition lists and sidebar headings run into the body (pdftotext's plain output keeps no font or position data to find them).

### C-20261102-2 · 2026-11-02 · Release 0.10.1: PDF line-end hyphens rejoined; page-numbered running heads dropped
- because: reader report on an O'Reilly PDF (words printed as "conven- tions" with U+2010; "4 | Chapter 1: ..." and "Title | 179" mid-sentence)
- files: scripts/rw.py (join_lines, SPLIT_WORD, strip_running_heads, join_split_pages, text_paras, load_pdf), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- A U+2010 or soft hyphen at a line end (or followed by a space mid-line, as pdftotext joins them) before a letter is removed and the word rejoined, except before and/or/nor/to; an ASCII hyphen before a lower-case line is kept and joined without a space. A word split across a page break is joined too. PDF pages lose a first or last line shaped `N | title` or `title | N` (no other pipes, at most 80 characters), on by default: frequency-based furniture missed them because the number and title vary. Checked on the reported book's sections 12, 17, 59 and 111: no split words or heads left.

### C-20261102-1 · 2026-11-02 · Release 0.10.0: `rw.py note` resolves a note marker; untocced notes files are titled as notes
- because: reader reports on Criado Perez, Invisible Women for everscout tech-hiring (a second endnotes file showed in the outline as `Chapter 13` after Endnotes; agents had to match chapter and number by hand to check a marker)
- files: scripts/rw.py (notes_part_title, chapter_key, cmd_note), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- An EPUB file the toc skips, right after a Notes/Endnotes/References section and mostly numbered lines, is titled `Endnotes: <its heading>`. `rw.py note FILE N --section S` finds the chapter of section S and prints note N under that chapter's heading in the notes sections, or lists the chapter headings it saw.

### C-20261101-12 · 2026-11-01 · Release 0.9.3: EPUB note references print as [40]
- because: reader report on Lalka, The Venture Alchemists for everscout global-economics (note numbers glued to sentences, "after that.40 Uber", were misread as figures)
- files: scripts/rw.py (HTMLText), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- An `<a>` with role `doc-noteref` or epub:type `noteref`, or a `<sup>` link to an anchor, prints its text in brackets. Plain superscripts (x<sup>2</sup>) are unchanged. `rw.py outline` is an alias of `toc` (a reader agent's first call used the skills' word). The conversion cache is keyed by version, so old text is rebuilt.

### C-20261101-11 · 2026-11-01 · Release 0.9.2: the character-cut footer offers --max-chars for the rest
- because: reader reports on Tannen, Talking From 9 to 5 for everscout tech-hiring (two agents read 50-85k-character chapters in 25k slices or sampled them, not knowing --max-chars existed)
- files: scripts/rw.py (cmd_read footer), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- A `read` cut by the character cap now says `show it all with --max-chars N` (N = the rest of the selection) beside `--offset` and `--out`. The skill tells book runs to give reader agents that flag.

### C-20261101-10 · 2026-11-01 · Release 0.9.1: printed-page offset in info; grep names case-insensitive hits
- because: L-019 `printed-page-offset`; reader report on Color & Light for everscout ai-video
- files: scripts/rw.py (printed_offset, load_pdf, cmd_grep), SKILL.md (Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- A PDF whose page numbers (a bare number in a page's first or last two lines, five or more pages agreeing) differ from its page index gets `printed_pages: PDF page + N` in `info`. A grep with no matches that would match with `-i` says how many.

### C-20261101-9 · 2026-11-01 · Release 0.9.0: rw.py ocr reads scanned PDFs with Windows' built-in OCR
- because: L-018 `scans-need-ocr`; found on 3dtotal's Artists' Master Series: Color & Light (384 scanned pages) for everscout ai-video
- files: scripts/rw.py (WIN_OCR_PS, ocr_dir, ocr_cache, ocr_engine, ocr_pages, cmd_ocr, load_pdf, scan_note, main), SKILL.md (Step 1, Distilling a book), references/formats.md (scans), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- `rw.py ocr FILE [--pages N-M] [--dpi] [--batch] [--force]` renders a scanned PDF's pages and OCRs them with the engine built into Windows 10 and 11 (Windows PowerShell 5.1, nothing to install) or tesseract, saving after each batch to a lasting cache keyed by path, size and mtime. `info`, `toc`, `read` and `grep` then use that text, with a `text from OCR` note. The scan note names the command first when an engine exists.

### C-20261101-8 · 2026-11-01 · Release 0.8.1: --drop-repeated drops endnote back-links inside one section
- because: user request (book runs fix every reader bug); found reading Mollick, Co-Intelligence, for everscout tech-hiring
- files: scripts/rw.py (drop_repeated, IN_SECTION_MAX_WORDS), SKILL.md (read, Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- The Notes section of a Penguin EPUB put "GO TO NOTE REFERENCE IN TEXT" after each of its 100 notes; `--drop-repeated` only compared lines across sections, so all 100 stayed. A line of eight words or fewer repeated verbatim ten times or more, and a quarter of a section's paragraphs, now goes too. Distilling tip: read a chapter's endnotes for its studies.

### C-20261101-7 · 2026-11-01 · Release 0.8.0: read --drop-repeated, batch-read tip for distilling
- because: L-017 `repeated-credit-lines`
- files: scripts/rw.py (repeat_keys, drop_repeated, cmd_read, main), SKILL.md (read, Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- `read --drop-repeated` drops short paragraphs that recur in 30% or more of the sections with text (and at least 5), compared whole or by their last four words with digits folded, so a credit line naming a different film each time still matches; the section heading stays and one advice line gives the count. Off by default: a synthetic fixture whose body lines shared a templated ending lost them too. "Distilling a book" now says to read a chapter's sections in one `--section N-M --quiet --max-words N` call sized under 25k characters, and when to add `--drop-repeated`.

### C-20261101-6 · 2026-11-01 · Release 0.7.0: one combined hint, --quiet, --max-words offsets, --skip-code, technical-book tips
- because: L-016 `code-heavy-batch-reads`
- files: scripts/rw.py (cap_words, cut_offset, skip_code, code_note, compose, cmd_read, cmd_grep, main), SKILL.md (read, Distilling a book), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- `read` gathers its advice into one `[readwright: ...]` line at the end and `--quiet` drops it. A `--max-words` cut ends `[cut at N of M words; continue with --section S --offset C]`, where C resumes exactly at the cut (the cut keeps the paragraph's spacing). `--skip-code` on read and grep drops `pre` paragraphs (EPUB/HTML `<pre>`, fenced Markdown) and counts the words skipped in the selection; on a PDF it says there is no structural marker. SKILL.md: read Troubleshooting, Common Issues, Tips and Production sections of a technical book first.

### C-20261101-5 · 2026-11-01 · Release 0.6.0: same-page PDF sections, spaced titles, --strip-boilerplate, repeated --section
- because: L-015 `same-page-outline-entries`
- files: scripts/rw.py (load_pdf, isolate_headings, place_on_pages, respace_title, page_furniture, strip_furniture, heading_at, parse_outline, cmd_read, cmd_grep, main), SKILL.md (read, grep), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- PDF outline entries that start on one page are each found on the page and ordered by position, so each gets its own text and word count; heading lines run into a paragraph are split out first. Titles whose spaces were lost or moved at a line join take the heading line's spacing; escaped quotes in outline titles are unescaped. `--section` may be repeated (adds up like `N,M`). `read` and `grep` take `--strip-boilerplate` to drop lines repeated across pages (found by frequency). `grep -C` widens over runs of short lines such as boxed callouts.

### C-20261101-4 · 2026-11-01 · Release 0.5.1: PDF sections start at their heading; grep points to --section
- because: L-014 `pdf-sections-start-a-page-early`
- files: scripts/rw.py (load_pdf, heading_at, grep footer), tests/test_rw.py.
A PDF outline section now starts at its heading line on the start page (a numbered heading run into a paragraph splits it), so the previous section's tail stays with it; a cut-off grep suggests `--section N-M`.

### C-20261101-3 · 2026-11-01 · Release 0.5.0: toc --depth, chapter numbers merged, "Distilling a book" tips
- because: L-013 `toc-lists-bare-chapter-numbers`
- files: scripts/rw.py (chapter_numbers, rolled_words, toc_lines, cmd_toc, main), SKILL.md (Step 2, Distilling a book), ../../README.md, ../../tests/test_rw.py (TestTocChapters), version in the five places AGENTS.md lists
- A section that is only a number or "Chapter N" (0-3 words) followed by a titled section of the same level prints as `Ch. N: Title` under the title's section number; section numbers are unchanged and the number section stays readable. `toc --depth N` keeps sections at indent depth N or less with word counts rolled up from the sections below; toc JSON gains `chapter` and `words_total`. SKILL.md gains a short section on distilling a book.

### C-20261101-2 · 2026-11-01 · Release 0.4.0: context for generic section titles, read --max-words
- because: user request (reading a recipe cookbook whose sections are all "Getting ready", "How to do it...", "There's more...")
- files: scripts/rw.py (context_titles, in_context, md_head, cap_words, header_line, compose, toc_lines, cmd_toc, cmd_read, main), SKILL.md (read), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- A title that repeats 3 or more times in the book counts as generic; such a section's read header, md comment, toc line and toc JSON (`in`) name the nearest earlier distinctive title, so a "There's more..." section says which recipe it belongs to. `read --max-words N` caps every selected section at N words and notes the words left out, so a batch range read stays lean (ranges `N-M` already existed).

### C-20261101-1 · 2026-11-01 · Release 0.3.0: grep offsets, read --at-para, giant-section note
- because: L-012
- files: scripts/rw.py (para_offsets, big_section_notes, cmd_grep, cmd_read, cmd_toc, main), SKILL.md (grep), ../../tests/test_rw.py, version in the five places AGENTS.md lists
- grep hit lines end `| offset N` (JSON hits gain `offset`), counted the way `read --section S --offset N` counts, with `--format` for md offsets. `read --at-para P` with `--section` starts at paragraph P. toc prints a note when one section holds over 200k chars and over a quarter of the text. A test now runs the script under a cp1252 console encoding with arrows in the text (stdout was already reconfigured to UTF-8 with errors replaced). The calibre route test now prints calibre's error and passes over PDB when calibre's own PDB writer crashes (`use_alt_text_for_images`, the Ubuntu calibre package on CI, 2026-11-01).

### C-20261023-1 · 2026-10-23 · Scanned books say so and name the ways in
- because: L-011, T-20261023-1
- files: scripts/rw.py (load, scan_note, cmd_info, cmd_read, tool_dirs), SKILL.md (Step 1), references/formats.md (External tools), ../../tests/test_rw.py, ../../evals/outcome-2, evals/evals.json
- A PDF or EPUB under 10 words a page (an EPUB counts sections) gets a `no text layer` note in info, toc and read. The note names a same-name copy in another format beside the file, ocrmypdf when installed, and a `mutool draw` or `pdftoppm` line for the first pages. `read` on such a file prints the note instead of empty sections, and info's next line says there is no text to read. pdftoppm is looked for in poppler's usual folders. The threshold comes from 83 real books (6 scans at 0, the thinnest text book 132). New eval outcome-2; outcome-1 is now the suite's held-out case. Version unchanged.

### C-20261003-1 · 2026-10-03 · Prepared for the Claude plugin directory
- because: user request (directory submission)
- files: ../../.claude-plugin/plugin.json, ../../README.md (Privacy)
- plugin.json gains documentationUrl, supportUrl and privacyPolicyUrl. The README gains a Privacy section: the skill makes no network calls and reads no credentials; only the developer tests download public-domain books from Project Gutenberg. No code changed, so the version stays 0.2.0.

### C-20260929-7 · 2026-09-29 · Release 0.2.0; no MCP server and no launcher on PATH
- because: user request (kickoff plan item 4), T-20260929-3, T-20260929-4
- files: ../../.claude-plugin/plugin.json, ../../plugin.json, scripts/rw.py (VERSION), SKILL.md (metadata), evergreen.json, ../../README.md, ../../ai-docs/decisions
- Version 0.2.0 across the five places AGENTS.md lists. Decided against an MCP server and a `bin/` launcher: the CLI already runs in every agent with a shell, an MCP server adds tool definitions to every session, and Cowork refuses plugins with a top-level `bin/` (decision entry of 2026-09-29).

### C-20260929-6 · 2026-09-29 · read prints at most 25,000 characters by default
- because: L-009, T-20260929-4
- files: scripts/rw.py (DEFAULT_MAX_CHARS), SKILL.md (Step 1, Step 3, Step 5), ../../README.md
- Claude Code shows 30,000 characters of a command's output and saves the rest to a file, so the old 40,000 default sent long reads to a file the agent then had to open. SKILL.md says to read long chapters one call each, or write them with `--out` and open that.

### C-20260929-5 · 2026-09-29 · Title matching, the next section, and a leaner toc
- because: L-001, L-006, T-20260929-4 (toc cost), kickoff plan item 4
- files: scripts/rw.py (select, cmd_read, toc_lines, main), SKILL.md (Step 2, Step 3), ../../tests/test_rw.py (TestRealWorldShapes), ../../README.md
- `read --title` adds the following section when the match is under 300 words and says so; `--with-next` does it for any selection. A title with no match is tried again with spaces ignored (`CHAPTERXXVII`, `WEST GATE`). `toc` prints ids only with `--ids`: on Moby-Dick they were over half of the toc's 3,829 tokens (1,782 without).

### C-20260929-4 · 2026-09-29 · Every external-tool route run on real files, and what broke fixed
- because: L-003, L-004, L-005, L-006, L-007, L-008, R-20260929-7, R-20260929-8, R-20260929-9, T-20260929-3
- files: scripts/rw.py (find_tool, tool_dirs, windows_path_dirs, tools, run, tool_error, load_epub, heading_line, GUTENBERG_RE, HEAD_RE, refine, load_text, xlsx_date_styles, excel_date, load_xlsx, parse_outline, load_via, load_via_calibre, detect), references/formats.md, ../../tests/test_rw.py (TestToolDiscovery, TestRoutes, make_novel, make_outlined_pdf), ../../tests/real_files.py, ../../tests/measure_tokens.py, ../../evals/action-2, evals/evals.json, ../../.github/workflows/tests.yml
- Tools are found in their install folders and the registry PATH; `RW_HIDE_TOOLS` and `RW_PATH_ONLY` control the search. EPUB text split across files stays in its chapter; bracketed and glued CHAPTER lines and Gutenberg's START and END lines are headings; long or untitled sections split at CHAPTER lines; Markdown with no headings uses CHAPTER lines; the mutool outline keeps its nesting; KFX is detected by `CONT` and its version on any extension; XLSX dates print as dates; tool errors show the exception line; pandoc and markitdown write UTF-8 files and a passthrough is reported. New: route tests that convert invented fixtures with each installed tool, a real-file sweep, a token measurement, the full-size eval case action-2 and a CI job that installs the tools on Linux.

### C-20260929-3 · 2026-09-29 · Eval suite made runnable: regex flags, grader tool names, deflated fixture
- because: T-20260929-2, L-002
- files: ../../evals/*/graders (answer, chapter, ran-rw, searched, no-dump-to-context), ../../evals/*/fixture.sh, evals/evals.json
- Graders now pass `flags: i` and name `tool: Bash`; the fixture book is written with ZIP_DEFLATED like a real EPUB, so only a zip-aware route can read it.

### C-20260929-2 · 2026-09-29 · A short selection points to the next section
- because: L-001 (smoke test on a real novel)
- files: scripts/rw.py (cmd_read), SKILL.md (Step 2, Step 3), ../../tests/test_rw.py (test_short_selection_points_to_next_section)
- When the selected sections hold under 300 words, `read` ends with a line naming the next section and the range to read, because chapter-opener pages hold only a title and an epigraph.

### C-20260929-1 · 2026-09-29 · Created as an evergreen unit
- because: user request
- files: SKILL.md, RESEARCH.md, LEARNINGS.md, evergreen.json, TESTS.md, evals/evals.json, MAINTENANCE.md; also scripts/rw.py, scripts/rw.sh, scripts/rw.ps1, references/formats.md, ../../tests/test_rw.py
- Initial version 0.1.0: `rw.py` info, toc, read, grep, dump, formats; built-in readers for EPUB, DOCX, ODT/ODS/ODP, PPTX, XLSX, FB2, HTML, TXT, Markdown, RST, RTF, CSV, TSV, JSON, EML and zip; PDF, MOBI family and legacy Office through external tools; DRM detection. Tier `moderate`, interval 30 days. Research basis R-20260929-1 to R-20260929-6.
