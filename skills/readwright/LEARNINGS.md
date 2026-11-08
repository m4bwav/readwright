# Learnings: readwright

Procedural lessons for [SKILL.md](SKILL.md). Research findings live in [RESEARCH.md](RESEARCH.md); every change is logged in [CHANGELOG.md](CHANGELOG.md); test runs in [TESTS.md](TESTS.md); state in `evergreen.json`. Format and write-time gate: MAINTENANCE.md (LEARNINGS-FORMAT). Retired entries go to LEARNINGS-ARCHIVE.md with a reason.

Write an entry the moment a real signal happens: a user correction, the same error twice, a discovered workaround, an environment fact, a stated preference, a failed test or a failure in use. Check existing entries first, by meaning (`evergreen.py search "<the lesson>" --kinds learnings` finds near-duplicates in every registered unit): add / update / retire / none. Trigger and Hypothesis are required. Promote after three confirmations; retire when harmful > helpful.

## Active

### L-088 · 2026-11-07 · `ocr-resume`: a partial OCR looked finished
Trigger: everscout ai-music run on Boulanger, The Csound Book (MIT 2000, 746-page scan). `rw.py ocr FILE --pages 1-24` first, to read the contents cheaply; then `rw.py ocr FILE` answered "already OCR'd" because the cache file existed, and the book read as 3k words. Fix (0.71.1): a plain run OCRs pages still empty and remembers the ones that stay empty. OCR on Windows ran at about 9 pages a second here, so OCR the whole scan up front rather than sampling.

### L-087 · 2026-11-07 · `long-captions`: figure captions as long as body paragraphs
Trigger: everscout downtempo run on Wilson, Make: Analog Synthesizers (Maker Media 2013 EPUB): ch. 3 carries a caption under every figure (Figure 3-1. ... up to 60 words), so a 16-section read was a fifth captions, and --min-para-words could not drop them without dropping real paragraphs; the reader piped the output through grep -v. Fix (0.71.0): `read --drop-captions` drops body paragraphs that start Figure/Fig./Table/Plate/Exhibit/Listing, a number and a stop or colon; prose that names a figure (Figure 3-8 shows) stays.

### L-086 · 2026-11-07 · `overprinted-blurb`: a back-cover blurb on every page
A 2002 Addison-Wesley PDF rip (Beck, Test-Driven Development: By Example) carries the book's blurb and a credits block as a hidden layer on every one of its 218 pages. pdftotext interleaves it with the page's own sentences, sometimes mid-sentence, so paragraphs ran half blurb; `--drop-repeated` only dropped short whole paragraphs. 8-word runs that recur on 30% or more of the pages are now cut out of paragraphs too (31,066 words gone; 79k to 48k words). Where the two layers overlap glyph by glyph the text is letter-interleaved salad that no text pass can undo; read around it or OCR the page.

### L-085 · 2026-11-07 · `chapter-subsections`: --chapter dropped a chapter's unnumbered subsections
Tidy First? (O'Reilly EPUB) nests Never, Later, After, First, Summary under 21. First, After, Later, Never; --chapter matched only titles starting with the number, so the reader got a 65-word opener and had to fetch five sections by position. A matched chapter now takes the deeper sections that follow it.

### L-084 · 2026-11-07 · `file-label-outline`: bookmarks named after production files
Trigger: everscout ai-sfx run on Bilbao, Numerical Sound Synthesis (Wiley 2009 PDF): every bookmark was a typesetter file name (Unlock-fmatter, Unlock-ch1 ... Unlock-biblio, Unlock-index), so `toc` and `lit ingest` printed no chapter titles. Fix (0.69.0): `label_title` swaps such a name for the section's first short line (number prefixed for chN; Chapter N and Appendix A lines joined to the next; Index, Bibliography and the like keep only that word). A front-matter label whose first line is prose stays as it was.

### L-083 · 2026-11-07 · `two-line-heads`: layout heads wrapped onto two lines; Symbol-font signs
Trigger: open item from L-082 (Continuous Delivery heads cut at the line end) and the everscout ai-sfx run on Francis, The Audio Effects Workshop (Cengage 2011 PDF), whose text read À24.0 dB and þ2 dB. Cause: layout_head_titles took the next non-blank line as body, so a wrapped second line (under eight words) cut or dropped the head; pdftotext maps the Symbol font minus and plus to À and þ. Fix (0.68.0): a short Title Case second line (lowercase start allowed) with body after it is joined; À and þ before a digit become - and + when a book has three or more.

### L-082 · 2026-11-07 · `minor-word-heads`: Title Case heads with lowercase minor words
Trigger: everscout multi-agent-grind run on Humble and Farley, Continuous Delivery (2010 PDF): `read --section 28 --headings` listed 5 of 9 rule headings. Cause: layout_head_titles rejected any lowercase word longer than three letters, and Title Case keeps before, from, with, your lowercase. Fix: a TITLE_MINOR set of such words passes; long two-line heads still list cut at the line end.

### L-081 · 2026-11-07 · `run-in-pdf-heads`: headings glued to the paragraph under them
Trigger: everscout ai-sfx run on Zizza, Game Audio Fundamentals (Focal 2023 PDF, outline at chapter level only): `read --section 19 --headings` said no headings, though the chapter has about 40. Cause: plain pdftotext runs a heading line into the next paragraph (The Importance of Sound From the ambience ...), so no paragraph looked like a heading. Fix (0.66.0): `pdftotext -layout` keeps the heading on its own line after a blank line; short Title Case lines there with body text under them become titles, and a paragraph starting with one, followed by a capital, is a heading. Running heads (indented far right) and the chapter's own title are skipped; at least three per section.

### L-080 · 2026-11-07 · `letter-spaced-cells`: tracked-out table text split into letters
Trigger: reading Zizza, Game Audio Fundamentals (Focal 2023 PDF) for everscout ai-sfx, the asset-list figure printed file names as `cp_sfx_penguin_ l a s e r_ 0 2 .w av`. Cause: pdftotext emits a space between widely tracked glyphs. Fix (0.65.0): `join_lines` joins runs of four or more one-character tokens that hold a lower-case letter and a `_` or `.` (or five letters), glues `word_ next` in file names and rejoins a split known extension (`.w av`). Prose lists like `a 1 b 2` and capital runs like `U S A` stay.

### L-079 · 2026-11-07 · `mobi-code-as-quote`: a Kindle book's code read as prose
Trigger: reading Lanham, Game Audio Development With Unity 5.x (Packt MOBI, converted by calibre), `--skip-code` said it found no code blocks while C# lines sat inside numbered steps. Cause: calibre writes each listing as `<blockquote>` holding `<tt>` spans split by `<br/>`, not `<pre>`. Fix (0.60.0): a block wholly in monospace that is a blockquote or has line breaks becomes a code block; on this book 2 listings and their lead-ins left section 39. Hypothesis: most Packt and O'Reilly MOBI or AZW3 files convert this way; a book that sets one-line commands as monospace paragraphs without a blockquote still keeps them as prose.

### L-078 · 2026-11-07 · `chapter-heads-on-pages`: a scan had pages but no chapters
Trigger: reading Yewdall, Practical Art of Motion Picture Sound (4th ed., scan, OCR), toc listed 678 page sections and `--group` folded nothing, because the left page carries the chapter head and the right the book title; finding ch. 14 and 19 took a grep of the toc. Fix (0.59.0): `toc --chapters` builds page ranges from Chapter N heads at the top of pages, accepting only rising numbers so a cross-reference cannot start a chapter; it found all 22. Hypothesis: any page-sectioned book with numbered chapter heads, text or OCR, maps this way; books with unnumbered chapters still need `--group` or the printed contents.

### L-077 · 2026-11-07 · `dingbat-bullet-l`: list bullets read as the letter l
Trigger: reading Holman, Sound for Film and Television (3rd ed., Focal/Elsevier PDF), every bullet item began with a lone "l " and a list of premixes ran on one line as "l Dialog l Foley l Ambience". Cause: the bullet is the filled circle of an Advent Pi (AdvPi1) dingbat font, which pdftotext maps to the letter l. Fix (0.58.0): when pdffonts lists an AdvPi, Zapf Dingbats or Wingdings font, a line opening with a lone l and a capital becomes a "- " item, and a run on one line splits into one item per line. Also: several sections read in one call with `--section 248,250,251`, not a shell loop.

### L-076 · 2026-11-07 · `percent-encoded-nameddest`: an InDesign PDF lost 664 of 710 outline entries
Trigger: reading Pirkle, Designing Audio Effect Plugins in C++ (2nd ed.), the toc held 46 entries, each chapter named after its last subsection ("1.8 Bibliography" for all of ch. 1). Cause: MuPDF writes named destinations percent-encoded (`Book.indd%3APage%201%3A3914`) while `pdfinfo -dests` prints them plain, so only the few entries linked by page number survived. Fix (0.57.0): look the name up decoded too. Same run: `--at-para` was refused with `--compact` and silently ignored with `--out` (the file started at the section top); both now start at the paragraph. Hypothesis: a PDF toc whose titles repeat one subsection word (Bibliography, Homework) chapter after chapter is a lost outline, not the book's structure; check `mutool show FILE outline | wc -l` against the toc.

### L-075 · 2026-11-07 · `word-cap-before-start`: --max-words with --at-para printed nothing
Trigger: reading Russ, Sound Synthesis and Sampling, `read -s 17 --at-para 69 --max-words 2300` printed nothing and exited 0, while `--max-chars` worked. Cause: the word cap cut the section from its top before the `--at-para`/`--offset` start was applied, so the start fell past the capped text. Fix (0.56.0): with a start, the cap counts words from it, and a start past the end is an error. The same book's bookmarks stopped at the parts; `read --section N --headings` gave the chapter map, so the giant-section note now names it first. Hypothesis: every cap must apply after the start point.

### L-074 · 2026-11-07 · `lead-in-colon`: an entry's list sat in the sections after it
The Sound Effects Bible ch. 18 is an encyclopedia: each entry ends "Here is a list of techniques and tricks:" and the list items are the next outline entries, one level down. Read by selected section numbers, every entry seemed to end mid-sentence, and the reader first suspected lost lists. Fix: `read` adds a hint naming the sections a selection's closing colon points to (0.55.0). Rule: before calling text lost, read the section after the one that stops on a colon.

### L-060 · 2026-11-06 · `pull-quote-fragments`: a short line repeated in the next paragraph is nearly always a heading
- Trigger: a PDF with pull quotes put a sidebar's fragment in the body, then the same sentence whole. Dropping such a fragment looked cheap.
- Hypothesis: a line of 4 to 25 words found word for word in one of the next two longer paragraphs would mark these fragments.
- Rule: do not drop them. Leave the text and tell the reader to check the page before quoting. A safe filter needs layout data (type size or position) that says the line sits outside the body column.
- Evidence: 81 cached PDF texts, 269k paragraphs, 315 hits; of 40 sampled, about 38 were headings or table labels repeated in running text, and only 17 of the 315 ended in sentence punctuation. Those would be lost body structure. The book that prompted this was not at hand, so the true fragment rate on it is unmeasured.
- Scope: skill
- Status: active · helpful 0 · harmful 0 · last_confirmed 2026-11-06

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
- Evidence: 46 cached PDF texts, 23 changed, words moved by under 0.3% (-332 to +943). What came back includes margin marks like `LO 3`, harmless; `APPENDIX IV` on 4 pages came back on one book, too spread to prove. test_spread_headings_stay, test_recurring_chapter_label_stays_a_numbered_head_does_not. C-20261105-3 (L-052 `alternating-folio-heads`, merged here: count a head beside a folio that matches the page shift, on exact text, up to four lines in), C-20261105-6. Kept active: new, with these limits open.
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

### L-010 · 2026-09-29 · On EPUB, a strong model without the skill does about as well
- Trigger: action-2 with `--ablation with-without`, 3 runs per arm: without the skill the model wrote a zipfile-and-regex extractor and answered correctly, 12.9k to 13.1k tokens of tool output and $0.29 to $0.31; with it, 12.1k to 12.2k and $0.29 to $0.30. A first guess that the no-skill arm answered from memory was wrong: the saved trace showed the extraction.
- Hypothesis: EPUB is a zip of HTML, which a capable model parses on the fly; the skill's margin is elsewhere (converter formats, refusing a whole-book dump, chapter numbers mapped to sections, no new code per book).
- Rule: claim token savings only against the routes measured (whole-book dump 25 times, raw XHTML 3 times); keep the eval's baseline arm; save traces in the same WSL call that runs the eval (`--keep-temp` folders in `/tmp` were gone by the next `wsl` call).
- Evidence: T-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29
