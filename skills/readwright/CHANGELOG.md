# Changelog: readwright

Every change to [SKILL.md](SKILL.md) and its companions, newest first, each with the reason. Reasons cite findings in [RESEARCH.md](RESEARCH.md) (`R-`), lessons in [LEARNINGS.md](LEARNINGS.md) (`L-`), and test runs in [TESTS.md](TESTS.md) (`T-`). State in `evergreen.json`. Protocol: MAINTENANCE.md.

Entry shape: `### C-YYYYMMDD-n · date · one-line summary`, then `because:` (IDs or "user request"), `files:` (file and section), and a sentence on what changed. Cite section headings, not line numbers.

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
