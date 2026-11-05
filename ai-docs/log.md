# Log

Append-only. One line per operation: `## [YYYY-MM-DD] op | title` where op is one of add, update, supersede, verify, verify-failed, prune, handoff, index. Newest at the bottom. Never edited, only appended; this is the history the entries themselves do not carry.

## [2026-09-29] init | scaffolded
## [2026-09-29] add | solution: Run the readwright eval suite on Windows (native triggers, WSL2 for Bash cases)
## [2026-09-29] handoff | 16 lines
## [2026-09-29] add | project created: an agent needed chapters 14-15 of an EPUB novel and epr -d dumped the whole 1.2 MB book (~300k tokens) into context; readwright gives info, toc, read by section, grep and dump-to-file across ebook and document formats (stdlib Python), 34 unit tests, eval suite 7/7, smoke test on a real novel ~0.3 s per command
## [2026-09-29] update | AGENTS.md pointer added
## [2026-09-29] index | rebuilt (1 entries)
## [2026-09-29] add | decision: readwright as its own stdlib CLI plugin: outline, then sections, then search
## [2026-09-29] index | rebuilt (2 entries)

## 2026-09-29 published
Created the public repo m4bwav/readwright, pushed main, CI passed on all six jobs, tagged and released v0.1.0. Before publishing, book-specific example names were replaced with neutral ones in the README, evals, LEARNINGS and TESTS.

## 2026-09-29 registered and installed
Registered with `evergreen.py register` and added to the mark-local marketplace (`Ai/.claude-plugin/marketplace.json`); installed as readwright@mark-local 0.1.0 (user scope).
## [2026-09-29] index | rebuilt (3 entries)
## [2026-09-29] add | decision: No MCP server and no launcher on PATH for readwright
## [2026-09-29] add | solution: Test every converter route on real files, including KFX
## [2026-09-29] update | solution: Run the readwright eval suite on Windows (full-size case, saving traces)
## [2026-09-29] update | plan: Kickoff prompt: finish readwright, marked done

## 2026-09-29 released 0.2.0
Installed calibre, LibreOffice, poppler, mutool, pandoc, markitdown and Kindle Previewer with the KFX plugins; ran every route on real public-domain books and fixed what broke (tool discovery off PATH, chapters split across files, lost outlines, mutool nesting, XLSX dates, tool errors, markitdown quirks). Added route unit tests, a Linux CI job with the tools, tests/real_files.py, tests/measure_tokens.py and the full-size eval case action-2. Tagged v0.2.0, released, updated readwright@mark-local.
## [2026-09-29] handoff | rewritten for 0.2.0
## [2026-09-29] index | rebuilt (5 entries)

## 2026-10-03 prepared for the Claude plugin directory
Checked the directory's pre-submission list (manifest fields, validate, file sizes and types, names, .gitattributes): all met. Added documentationUrl, supportUrl and privacyPolicyUrl to `.claude-plugin/plugin.json` and a Privacy section to the README (no network calls in the skill, no credentials read; the developer tests download from Project Gutenberg). No launcher packages to pin. Version unchanged at 0.2.0; submission is done by another session.
- 2026-10-04: the plugin icon (icon.png in .claude-plugin) for the Claude directory, chosen from two Z-Image candidates. Z-Image Turbo bf16, 9 steps, cfg 1, res_multistep/simple, seed 605490777, prompt "flat vector app icon, bold simple shapes, minimal, centered single motif, thick clean outlines, high contrast, readable at small size, no text, no letters, no numbers, no words, no logos, square composition, an open book with a magnifying glass over one page, cream book and amber glass on deep teal background"; white corners painted to the background (28, 94, 95)
- 2026-10-04: submitted to the Claude plugin directory, https://claude.ai/directory/manage/plugins/4128fd90-c6f1-41c9-aa8f-c22ad7810d6e (validated main@66a40ec, Scheduled check only, auto-publish on); 1 credential hold (4 findings: env-var reads in rw.py and tests beside XML-namespace and Gutenberg URLs, false positives); status after submit: in review

## 2026-10-23 scanned books say so (books track 10)
L-011 built: info, toc and read print a `no text layer` note on a PDF or EPUB under 10 words a page, naming a same-name copy beside it, OCR and page-image commands. Calibrated on 83 real books (6 scans at 0 words a page, the next 132). Eval outcome-2 3/3 with, 0/3 without (T-20261023-1); outcome-1 marked held out. Decision: [decisions/2026-10-23-scan-note-threshold-and-routes.md](decisions/2026-10-23-scan-note-threshold-and-routes.md).
## [2026-10-23] index | rebuilt (6 entries)

## 2026-11-01 grep offsets for giant sections (0.3.0)
A 1,600-page PDF whose bookmarks stop early left one 1.85M-char section; grep gave no offset to read from. Added `| offset N` to grep hits, `read --at-para P`, and a toc note on giant sections (L-012, C-20261101-1). Verified on the real PDF: the grep offset for a chapter heading reads back as that heading.

## 2026-11-01 context for generic titles, read --max-words (0.4.0)
A recipe cookbook (EPUB from mobi) split each recipe into sections titled only "Getting ready", "How to do it...", "There's more..."; the reader could not tell which recipe a section belonged to, and a loop over ~60 of them printed 50 KB. Titles repeating 3+ times now carry `(in: <nearest distinctive title>)` in read headers, md comments, toc and toc JSON; `read --max-words N` caps each section in a range. C-20261101-2.

## 2026-11-01 toc --depth and chapter numbers (0.5.0)
Distilling a Packt EPUB showed every chapter number as its own empty toc section. toc now merges bare numbers into `Ch. N: Title`, `toc --depth N` rolls up words, SKILL.md has a Distilling a book section. C-20261101-3, L-013.

## 2026-11-01 same-page PDF sections, spaced titles, --strip-boilerplate (0.6.0)
Reading a MEAP PDF exposed: outline titles missing spaces at line joins, same-page outline entries sharing one text (headings run into paragraphs, set order lost), escaped quotes in titles, repeated `--section` keeping only the last, and footers on every page. All fixed with tests (69); `--strip-boilerplate` on read and grep is opt-in, so toc word counts and paragraph numbers stay as before unless asked. C-20261101-5, L-015.

## 2026-11-01 · 0.7.0 from an ML-book reader's friction
One combined advice line per read and `--quiet`; `--max-words` cuts end with an exact `--offset` to resume; `--skip-code` on read and grep drops `<pre>` blocks by structure (not PDFs: no marker); SKILL.md tells readers of technical books to start with troubleshooting and tips sections. 73 tests. See CHANGELOG C-20261101-6 and LEARNINGS L-016 `code-heavy-batch-reads`.

## 2026-11-01 · 0.8.0 from a film-book reader's friction
`read --drop-repeated` drops short paragraphs recurring in 30%+ of sections (whole text or last four words, digits folded); opt-in. "Distilling a book" tells readers to batch chapter ranges with `--section N-M --quiet --max-words N` under 25k characters. Checked on a film-technique EPUB: 212 credit lines dropped, no other text. See L-017 `repeated-credit-lines`.

## 2026-11-01: 0.8.1 endnote back-links

`--drop-repeated` now drops a short line repeated ten or more times inside one section (endnote back-links, found reading Mollick, Co-Intelligence, for everscout). Distilling tip for endnotes added. Other reader-agent reports that run (no word counts in toc, no paging, no snippet width) were wrong: `toc` shows words, `--offset` pages, `grep --width` exists.

## 2026-11-02: 0.10.1 PDF hyphens and running heads

O'Reilly PDFs printed words split with U+2010 (`conven- tions`) and running heads with page numbers (`4 | Chapter 1: ...`) mid-text. `join_lines` rejoins split words (pdftotext had already put both halves on one line with a space, so a mid-line pattern is needed too), `strip_running_heads` drops `N | title` / `title | N` at a page's first or last line, default on for PDFs. Tests added; checked on the reported book.

## 2026-11-02: 0.10.2 PDF pipe-less heads, page-break sentences, vocabulary joins

Reader reports from an O'Reilly PDF. Added running_head_keys (frequency or outline match for number+title edge lines), page-break sentence joins, book-vocabulary rejoins (spaced splits, lost compound hyphens) and caption splits; see CHANGELOG C-20261102-3. Frequency alone is unsafe: prose lines like "Input:" repeat at page edges, hence the punctuation guard. Left: code blocks, tables, definition lists, sidebars (need layout or font data; a candidate route is pdftotext -bbox-layout or -layout for flagged regions).

## 2026-11-02: 0.11.0 image-only EPUB OCR, ALL-CAPS heading split, PDF code blocks

From an everscout run on a film-technique book (image-only EPUB plus a DjVu twin). `rw.py ocr` now takes EPUBs made of page images; one-section books split at ALL-CAPS headings (running heads become chapters); PDF code blocks come back with indentation via a gated `pdftotext -layout` pass. See CHANGELOG C-20261102-4, LEARNINGS L-020 to L-022. Left open: PDF tables, definition lists, sidebars (HANDOFF Open).

## [2026-11-02] update | 0.15.0 reader fixes from a programming-book run

`<pre>` CRLF and no-break-space indents normalised, split one-line listings joined, `grep --after N`, short-selection hint only for title pages and continued sections, cut footer after `--offset` fixed, multi-section `--section` list documented. The reported lost indent was in the EPUB source. CHANGELOG C-20261102-10, LEARNINGS L-025.

## [2026-11-02] update | 0.18.0 running-head chapter split and dot leaders

From reading an Apress PDF whose outline stopped at the Introduction. `run_head_chapters` adds chapter starts from page-top running heads inside an oversized section (opener page `CHAPTER N` preferred); chosen over the printed contents page because that gives printed page numbers and its layout varies. `collapse_leaders` turns U+FFFD and dot leader runs into ` … `. CHANGELOG C-20261102-15, LEARNINGS L-027, L-028.

## [2026-11-02] update | 0.19.0 --drop-epigraphs

From reading a short quote-heavy creativity EPUB: `drop_epigraphs` drops a short wholly-quoted paragraph followed by a dash attribution of 8 words or fewer (both go); a lone quotation stays. 80 paragraphs (40 pairs) dropped on the real book. Skill tip: books under about 30k tokens are read in one `--section A-B --out FILE` pass. CHANGELOG C-20261102-16, LEARNINGS L-029.

## [2026-11-02] update | 0.20.0 read --headings

From an everscout run on a Unity tutorial EPUB, where the reader skimmed a chapter with `awk length<70` and caught captions and code. `heading_lines` prints the `h` paragraphs of the chosen sections by level with paragraph numbers and words to the next heading; no headings gives a note pointing to `toc --group` or grep. Checked on the real book, section 12: 20 headings. CHANGELOG C-20261102-17.

## [2026-11-02] update | 0.23.0 double-spaced PDF pages, glued listings, table cells

From reading a signal-processing textbook PDF. `merge_wrapped` rejoins a page's one-line paragraphs (lower-case continuation, or full-width lines on a double-spaced page) and drops a break hyphen when the joined word is commoner in the book; `split_listing` makes leading code lines of a paragraph a `pre` block (one line after a `Repo N: file.m` marker); `collapse_cells` turns 6+ one-token paragraphs into a ` | ` row. Skill tip for math-heavy textbooks. CHANGELOG C-20261102-20, LEARNINGS L-030, L-031.

## [2026-11-03] update | 0.24.0 rank by BM25, equation pictures marked

From the everscout distill of Manning, Raghavan and Schutze, *Introduction to Information Retrieval* (EPUB). `rw.py rank FILE WORDS` scores sections, or paragraphs with `--paras`, by Okapi BM25 (k1 1.2, b 0.75) over lowercased words with stop words dropped and a light suffix strip; it names query words the book lacks. The EPUB sets its 160 numbered equations and about 900 inline formulas as JPEGs with alt text "image": they now print `[equation 11.32: image]` (from the `eq_` id) or `[formula: image]` mid-sentence, and `<sub>` prints `_` after a letter (`tf_td`, `k_1`). grep and rank say the file goes first when the arguments are swapped. Formula OCR not attempted (HANDOFF). PR #38, released v0.24.0, installed.
## [2026-11-03] handoff | 0.29.0: Cengage PDF fixes (printed pages in outline titles, copyright footers dropped, smart-case grep, symbol-font math warning); math repair left open
## [2026-11-03] update | 0.30.0: collapsed EPUB sections split at a one-line printed contents page (L-039)
## [2026-11-03] update | 0.31.0: read --each-chars (per-section cap for multi-section reads), [image omitted]/[math] markers, isbn in info (reader feedback on an EPUB textbook)
## [2026-11-04] update | 0.41.0: `page` command, scrambled text layer note (L-041), fixed-layout captions by type size (L-042)
## [2026-11-04] update | 0.41.1: UTF-8 before a meta charset hint (L-043), scan note names rw.py page and ocr, markers and folios out of fixed-layout sentences (L-044), two distilling tips
## [2026-11-04] update | 0.41.2: `--skip-code` drops numbered code callout markers; tip on code-heavy books
## [2026-11-04] update | 0.42.0: foot notes out of sentences (L-046), break hyphens by book counts, long lines are paragraphs (L-045), how-to book tip
## [2026-11-05] update | 0.44.1: alternating running heads beside a folio stripped (L-052); distilling tip on thin sections spanning many pages

## [2026-11-05] 0.44.2 cache race

Concurrent first reads could read a half-written pdftotext cache, silently losing most of a book. Fixed with temp file plus atomic move; unit tests cover the helpers, the race itself was not reproduced.

## [2026-11-05] 0.44.4 open items

Short chapter heads, glued caption folios, spread real headings and converter cache atomicity. Old and new compared on 46 cached PDF texts; L-053, L-054.
