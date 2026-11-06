# Learnings: readwright

Procedural lessons for [SKILL.md](SKILL.md). Research findings live in [RESEARCH.md](RESEARCH.md); every change is logged in [CHANGELOG.md](CHANGELOG.md); test runs in [TESTS.md](TESTS.md); state in `evergreen.json`. Format and write-time gate: MAINTENANCE.md (LEARNINGS-FORMAT). Retired entries go to LEARNINGS-ARCHIVE.md with a reason.

Write an entry the moment a real signal happens: a user correction, the same error twice, a discovered workaround, an environment fact, a stated preference, a failed test or a failure in use. Check existing entries first, by meaning (`evergreen.py search "<the lesson>" --kinds learnings` finds near-duplicates in every registered unit): add / update / retire / none. Trigger and Hypothesis are required. Promote after three confirmations; retire when harmful > helpful.

## Active

### L-054 · 2026-11-05 · `short-chapter-heads`, `glued-folio-caption`: few copies need proof from the rhythm, a glued folio needs a caption
- Trigger: a chapter of a few pages cannot reach the five-copy bar, so its heads stayed; `122 Exhibit 4-3` kept the page's number glued to a caption.
- Hypothesis: lowering the bar would catch real headings, while the book's own rhythm separates them. `122 people came` may be a sentence, and `Table of Contents` has no number, so it is no caption.
- Rule: a short head counts only with the same gap as the proven heads, the same edge, and a proven head on the pages between. One copy alone is kept. A glued number comes off only when it matches the page's shift and the rest opens with `Exhibit 4-3`, `Figure 5.14` and the like.
- Evidence: on 46 cached PDF texts every dropped short head with no exact copy left had a similar real heading in the text (`13.3 Poses` under head `13.3. Poses`); `514 Exhibit 13-5` and `Figure 6.12 Tearing the mesh. 139` lost only the number. test_short_chapter_head_drops, test_short_run_needs_the_books_rhythm, test_glued_folio_leaves_the_caption. C-20261105-6. Kept active: new.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-05

### L-053 · 2026-11-05 · `spread-headings-stay`: running heads cluster, repeated real headings spread out
- Trigger: the count tests could not tell `Summary` closing each chapter from a head, and took out `Summary`, `Exercises`, `OBJECTIVE` and `Chapter 5` openers on books whose chapters open at a page edge.
- Hypothesis: a head sits page after page or every other page, so half its gaps are 3 or under; real headings are many pages apart.
- Rule: a line that recurs spread out stays. Two exceptions are furniture however spread: a number that keeps one shift from the page (`57 Salt Roads`), and a line on a fifth of a book of 100 or more pages (a picture credit on 134 pages of one textbook left only by this rule).
- Evidence: 46 cached PDF texts, 23 changed, words moved by under 0.3% (-332 to +943). What came back includes margin marks like `LO 3`, harmless; `APPENDIX IV` on 4 pages came back on one book, too spread to prove. test_spread_headings_stay, test_recurring_chapter_label_stays_a_numbered_head_does_not. C-20261105-6. Kept active: new, with these limits open.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-05

### L-052 · 2026-11-05 · `alternating-folio-heads`: two heads by a folio pass every share test
- Trigger: a textbook sets `368` over the part name on even pages and the chapter over `369` on odd ones. No text reaches a fifth of the pages, each head changes by chapter, and only the bare number was on the edge line, so about 100 heads opened false sections.
- Hypothesis: what proves a head is the number beside it matching the page's own shift, not how often the text recurs.
- Rule: count recurrence beside such a number, on exact text: with digits folded, `Exhibit 9-3` beside a folio looks like a head. pdftotext can read a sidebar before the head, so the drop reaches four lines in.
- Evidence: `toc` 357 to 258 sections, the split section 125 to 7,399 words, 30 sampled PDFs lose under 1.8% of words. test_alternating_heads_and_folios_drop. C-20261105-3. Kept active: new, and L-053 and L-054 tune the same code.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-05

### L-051 · 2026-11-05 · `table-cell-code`, `skip-code-legends`: what `--skip-code` leaves behind
- Trigger: a Manning book sets each chat turn in a table, so a `<pre>` in a cell passed `--skip-code` (Winteringham, Software Testing with Generative AI); dropped blocks also left their `Listing N.N` captions and circled-number legends, 45 lines in one section (L-050, merged here).
- Hypothesis: flattening cells into one row loses the block's kind and line breaks; captions and legends are separate paragraphs tied to a block only by position.
- Rule: keep a block's kind by structure. Tie captions and legends to position (a caption right before a block, a run of legends right after), so prose that merely names a listing stays. Cut long rows only on request (`--max-row-words`): no general mark says which speaker is the model.
- Evidence: test_skip_code_finds_pre_in_a_table_cell, test_max_row_words_cuts_long_rows_only, test_skip_code_drops_captions_and_legends_only; no prose line lost in the two sections checked. C-20261105-1, C-20261105-2. Kept active because it was tried on one publisher's EPUBs only.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-05

### L-047 · 2026-11-04 · `read-lang`: common words sort a polyglot edition, once words inside glued tokens count
- Trigger: a type manual printing German, English and French paragraphs in one scrambled OCR layer: `read` gave three copies of everything, and a throwaway word filter was needed.
- Hypothesis: short common words identify a paragraph's language, and OCR hides them inside tokens like `thelinearbranchesofthetree`.
- Rule: score each paragraph by short common words; a word inside a token of 12 or more letters counts half. Needs 4 words, a score of 2 and a clear winner. Headings stay unless they clearly favour another language.
- Evidence: of 24.8k words, `--lang en` printed 9.0k, de 7.9k, fr 5.6k. Counting only token ends kept 8.0k English paragraph words; anywhere 8.5k. A 40-paragraph sample of the English: none wholly in another language, 2 interleaved with other lines, which a paragraph filter cannot split. Five single-language books: no `info` note. TestReadLang, C-20261104-6. Kept active because only one polyglot book was tried.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-04

### L-044 · 2026-11-04 · `fixed-folio-rises`, `fixed-folio-kinds`: tell a folio by its number when size cannot separate it
- Trigger: a synthetic fixed-layout EPUB in one type size gave `1 The sentence starts [image omitted: a.jpg] and ends here.`; with a caption size, a marker with alt text still glued. Spreads and roman front matter then stayed in the text as numbers (L-048, merged here).
- Hypothesis: size and height may be unknown, but printed number minus spine position stays constant, and a year in a sentence does not fit that.
- Rule: a bare number is a folio when number minus position is constant at one a file, or at two a file allowing the pair. Lowercase roman runs separately and needs only 3 files, since front matter is short; a repeated `i` never rises, so it stays.
- Evidence: TestFixedLayoutMarkers; C-20261104-3, C-20261104-6. Kept active because it is synthetic only: no real spread EPUB was at hand, so confirm on the first one met.
- Scope: skill
- Status: active · helpful 0 · harmful 0 · last_confirmed 2026-11-04

### L-041 · 2026-11-04 · `scrambled-text-layer`: long lowercase runs separate a bad OCR layer from clean books
- Trigger: Arcade Game Typography (PDF, 129 MB): an embedded OCR layer glues and interleaves words, and upside-down lines become contents titles.
- Hypothesis: glued OCR words make lowercase runs far longer than clean text does. Measured, runs of 18+ letters per 1,000 words, URLs and identifiers excluded: that book 1.43 (35 runs); clean PDFs from the same folder 0.08, 0.06, 0.01, 0.01, and 0.00 on six others. At 14+ letters the groups overlap (5.08 against up to 5.17), so length 18 is what separates them.
- Rule: note at 5+ runs and 0.5+ per 1,000 (`SCRAMBLED_MIN_RUNS`, `SCRAMBLED_MIN_RATE`). Kept active because it has fired on one book and is untested on German or Dutch, whose long compounds may trip it; the note says "looks".
- Evidence: `scrambled_note`; the same book had 89 words a page against 219 to 416 on clean books.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-04

### L-042 · 2026-11-04 · `fixed-layout-caption-size`: a converter's CSS tells captions from body by type size
- Trigger: Typeset in the Future (272 fixed-layout pages, one absolutely placed block per line, per-page CSS classes, no figcaption or epub:type).
- Hypothesis: type size is the only signal left. Characters by size: 55px 268,712 (body), 61.1px 92,222 (interviews), 45.8px 87,450 on 213 pages (captions, in two families and at least four colours, so neither family nor colour tells), 42.8px 10,670 (folio line and a colophon).
- Rule: the heaviest size below body is the caption size if it holds 10% of the body's characters and is on 25% of the pages. Smaller runs next to a caption join it (TOP LEFT:); others stay, because interview speaker labels are smaller too. A page with no body type stays unmarked, since acknowledgements use the same size.
- Evidence: test_captions_leave_the_body_and_are_marked, test_rare_small_type_is_not_a_caption_size. Kept active because only one book was checked. Known limits: larger pull quotes stay in the flow, all-caption summary pages are marked as captions, some labels sit at a caption's end.
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-11-04

### L-005 · 2026-09-29 · mutool's outline nests with tabs after the marker
- Trigger: first real `mutool show FILE outline` (MuPDF 1.23.0 on Windows, 1.23.10 in CI): lines read `|<TAB><TAB>"Title"<TAB>#page=4&zoom=...`, CRLF-terminated; the 0.1.0 parser read depth from leading spaces, so every entry came out at level 1.
- Hypothesis: MuPDF prints a marker (`|` leaf, `+` closed, `-` open), then one tab per level.
- Rule: depth is the number of tabs after the marker; stay tolerant of the older space-indented form. Kept active because MuPDF 1.24 to 1.28 is unverified: on a real outline from one of them, confirm or correct this.
- Evidence: T-20260929-3, C-20260929-4, test_mutool_outline_format, `parse_outline`, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-008 · 2026-09-29 · A tool installed after the shell started is not on the shell's PATH
- Trigger: after `winget install` of pandoc, poppler, calibre and LibreOffice, `Get-Command` found none in the running shells. winget's poppler is a portable zip, LibreOffice's MSI adds nothing to PATH, `pip install --user markitdown` lands off PATH. The first CI run failed because hiding LibreOffice by trimming PATH hid nothing: on Linux soffice, antiword, mutool and pdftotext all live in `/usr/bin`.
- Hypothesis: a process inherits PATH at start; installers only update the registry.
- Rule: `find_tool` searches PATH, the registry PATH and the install folders (listed in references/formats.md). In tests, hide a tool with `RW_HIDE_TOOLS`, never by trimming PATH.
- Evidence: T-20260929-3, C-20260929-4, confirmed 2026-09-29
- Scope: skill; env:windows
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-010 · 2026-09-29 · On EPUB, a strong model without the skill does about as well
- Trigger: action-2 with `--ablation with-without`, 3 runs per arm: without the skill the model wrote a zipfile-and-regex extractor and answered correctly, 12.9k to 13.1k tokens of tool output and $0.29 to $0.31; with it, 12.1k to 12.2k and $0.29 to $0.30. A first guess that the no-skill arm answered from memory was wrong: the saved trace showed the extraction.
- Hypothesis: EPUB is a zip of HTML, which a capable model parses on the fly; the skill's margin is elsewhere (converter formats, refusing a whole-book dump, chapter numbers mapped to sections, no new code per book).
- Rule: claim token savings only against the routes measured (whole-book dump 25 times, raw XHTML 3 times); keep the eval's baseline arm; save traces in the same WSL call that runs the eval (`--keep-temp` folders in `/tmp` were gone by the next `wsl` call).
- Evidence: T-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-057 · 2026-11-05 · A typed hyphen missed a book's U+2010
J.K. Lasser's Small Business Taxes 2024 (Wiley EPUB) prints U+2010: grep for self-employment tax found 2 matches where the true count was 73, and the small count looked like an answer. grep now treats the hyphen and apostrophe forms as one. It was tried on this one EPUB; en and em dashes stay distinct, since they often mean something else.
