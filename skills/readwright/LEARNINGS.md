# Learnings: readwright

Procedural lessons for [SKILL.md](SKILL.md). Research findings live in [RESEARCH.md](RESEARCH.md); every change is logged in [CHANGELOG.md](CHANGELOG.md); test runs in [TESTS.md](TESTS.md); state in `evergreen.json`. Format and write-time gate: MAINTENANCE.md (LEARNINGS-FORMAT). Retired entries go to LEARNINGS-ARCHIVE.md with a reason.

Write an entry the moment a real signal happens: a user correction, the same error twice, a discovered workaround, an environment fact, a stated preference, a failed test or a failure in use. Check existing entries first, by meaning (`evergreen.py search "<the lesson>" --kinds learnings` finds near-duplicates in every registered unit): add / update / retire / none. Trigger and Hypothesis are required. Promote after three confirmations; retire when harmful > helpful.

## Active

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

### L-062 · 2026-11-06 · `viewport-attribute-order`: fixed-layout detection needed name before content
Murch, Suddenly Something Clicked, writes `<meta content="width=818, height=1065" name="viewport"/>`. The pattern wanted name first, so every printed line, folio, running head and margin quote came out as its own paragraph, with page furniture mixed into the sentences and line-end hyphens kept. A book that reads as one line per paragraph points here. Separately, `--offset` past the end printed nothing and exited 0; it now refuses.

### L-061 · 2026-11-06 · `outline-named-dests`: LaTeX outlines lost most of their entries
`mutool show` prints `#nameddest=section.7.2` instead of a page for hyperref PDFs, and the parser only took page numbers. Müller's 287 outline entries came out as 132 sections, with section 7.2 inside "7.1.2.2 Fingerprint Matching" and no warning. An earlier reader had to interpolate page numbers. `pdfinfo -dests` gives the pages. 10 of the first 40 PDFs in the book folder have such entries. When a toc shows one huge leaf, compare its entry count with the PDF's outline.

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

### L-010 · 2026-09-29 · On EPUB, a strong model without the skill does about as well
- Trigger: action-2 with `--ablation with-without`, 3 runs per arm: without the skill the model wrote a zipfile-and-regex extractor and answered correctly, 12.9k to 13.1k tokens of tool output and $0.29 to $0.31; with it, 12.1k to 12.2k and $0.29 to $0.30. A first guess that the no-skill arm answered from memory was wrong: the saved trace showed the extraction.
- Hypothesis: EPUB is a zip of HTML, which a capable model parses on the fly; the skill's margin is elsewhere (converter formats, refusing a whole-book dump, chapter numbers mapped to sections, no new code per book).
- Rule: claim token savings only against the routes measured (whole-book dump 25 times, raw XHTML 3 times); keep the eval's baseline arm; save traces in the same WSL call that runs the eval (`--keep-temp` folders in `/tmp` were gone by the next `wsl` call).
- Evidence: T-20260929-4, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-057 · 2026-11-05 · A typed hyphen missed a book's U+2010
J.K. Lasser's Small Business Taxes 2024 (Wiley EPUB) prints U+2010: grep for self-employment tax found 2 matches where the true count was 73, and the small count looked like an answer. grep now treats the hyphen and apostrophe forms as one. It was tried on this one EPUB; en and em dashes stay distinct, since they often mean something else.

The routes CI job hung in its apt install step on PR #73 and #75 (cause not found); that step now has a 12-minute timeout and DEBIAN_FRONTEND=noninteractive.

### L-058 · 2026-11-06 · Notes sections looked like second copies of the chapters
Quietly Powerful (one-file EPUB) split its endnotes at headings named Chapter 1, Chapter 2 and so on, so the outline showed each chapter twice, and a citation could point at the wrong one. Repeats at the book's end under half the first copy's words are now titled as notes. A book built from interviews with people the author already admires selects on the outcome: that is now a distilling tip.

### L-059 · 2026-11-06 · A cap could end on a bare section title
Reading The Argument Culture, a batch ended at the title of section 135 with no body, which looked like an empty section until the footer was read. A cut now backs up to before such a header.

### L-069 · 2026-11-07 · `margin-folio-in-text`: a side-margin page number lands inside sentences
Refining Sound sets folios at mid-page height in the margin, so pdftotext read "close together in 65 frequency". The number is removed only when one shift holds on a quarter of the pages, twice the runner-up, and the page has one plain occurrence. Of 40 other PDFs 5 qualified; sampled removals were real folios except line references and contents leaders, which are now blocked. The sample was small, so an odd number could still go.

### L-070 · 2026-11-07 · `contents-page-survivors`: lines of a contents page that repeat nothing opened false sections
Power Tools for Synthesizer Programming has a contents file with no heading. `contents_entry` rejected Chapter 1 to 8 because a later cut shared the word, but Introduction, Chapter 9 and Appendix survived, giving three false sections at the front. A short-line block that names itself contents, or lost three or more cuts, now keeps none.

### L-071 · 2026-11-07 · `caption-credit-heading`: a photographer's name closing a caption opened a section
split_caps took small-caps credits at the end of captions as inline headings, so body text sat under the photographer's name in a Crowood EPUB. A caps run closing a paragraph of 150 words or fewer now stays in the caption; OCR page paragraphs run longer.

### L-073 · 2026-11-07 · `same-page-runin-titles`: names run into one paragraph gave their outline entries 0 words
The Foley Grail's ch. 15 lists 44 experts as outline entries, several per page, each name run into one long paragraph ("... received. Mark Mangini (supervising ..."). Only numbered titles were split inside running text, so all but the last name on a page read as 0 words. When several entries share a page, an unnumbered title of two or more words in its exact case right after a sentence end now splits the paragraph; a lone entry never does.

### L-072 · 2026-11-07 · `chapter-mini-contents`: a chapter's own contents printed every heading twice
MIT Press EPUBs (Roads, The Computer Music Tutorial) open each chapter with paragraphs that are each one link to a heading further down the file. Read printed them as bare lines before the body, which reader agents took for empty paragraphs. A run of three or more such blocks at the start or after a heading is now one `[chapter contents: N headings]` line; `--headings` still lists them.

### L-063 · 2026-11-07 · `page-is-not-section`: printed page numbers were turned into section numbers
An OCR PDF of Introduction to Computer Music has several outline sections per page, so `--section p264` silently read printed p. 71. The selector now maps pages through `pageN` section ids. A wrong page with plausible text gives no error, so check the `printed N` in the header when citing.

### L-064 · 2026-11-07 · `caps-list-acronym`: small-caps names opened sections, and ruled headings went unseen
In an Oxford handbook, a list broken after DEC, IBM and glossary names such as CSIRAC became sections, while real headings over a rule of dots were missed by `read --headings`. A caps run ending in a comma, or one word also used inside sentences, is no longer a heading; `--headings` falls back to the rule of dots. A split two-line caps title still gives two sections.

### L-065 · 2026-11-07 · `code-in-classed-divs`: --skip-code dropped nothing on Springer EPUBs
Springer sets listings as div.ProgramCode with one div per line and no pre, so a third of Sound Analysis and Synthesis with R stayed in and ate the character cap. A div or p whose class names code now becomes one pre block, lines and no-break-space indents kept. When a skip flag leaves code in, look at the EPUB markup first.

### L-066 · 2026-11-07 · `numbered-headings`: --headings saw nothing in a flat numbered PDF
The Effects of Sound on People keeps 96% of its text in one section, with headings only as plain `5.2 Annoyance` lines, so `read --headings` reported none and the reader wrote the section to a file and grepped it. Five or more short numbered lines now count as headings; lines of figures and sentences do not.

### L-069 · 2026-11-07 · `bare-numbered-heads`: list heads without a dot, one page per section
Collins, Game Sound (MIT Press PDF, no outline) comes out as one section per page, and ch. 8 sets its ten approaches as `1 Variable Tempo` with no dot. Every heading rule counted per section, so a page with one or two heads never passed a threshold and `read --headings` said none. Fixed in 0.52.0: bare-number heads count across the whole selection when they run 1, 2, 3 or longer. Checked on ch. 8: all ten found, nothing else.

### L-068 · 2026-11-07 · `caps-headings`: subheadings set only in capitals
Chion, Audio-Vision (Columbia University Press PDF) has no heading marks, numbers or rules; its subheadings are whole lines in capitals (THE UNITY ILLUSION, MATERIALIZING SOUND INDICES (MSIs)). `read --headings` said the chapter had none, so the reader fell back to grep. Fixed in 0.51.0: at least three whole-caps lines of two to ten words, each followed by a paragraph of 20 or more words, count as headings; a short gloss in brackets at the end is allowed. The minimum and the body check keep caps lists and acronyms out (L-064). Checked on ch. 1, 5 and 9 of the book, every line a real heading.

### L-067 · 2026-11-07 · `duplicate-picture-marker`: a repeated ornament read as a formula
You're the Only One I Can Tell sets each chapter ornament as two img tags with one src, for EPUB and Kindle. The first got an image marker, and the marker made the block look like running text, so the second became `[formula: image]`. A false formula sends a reader looking for maths that is not there. Fixed in 0.50.1, with a test.
