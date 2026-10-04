# Changelog: readwright

Every change to [SKILL.md](SKILL.md) and its companions, newest first, each with the reason. Reasons cite findings in [RESEARCH.md](RESEARCH.md) (`R-`), lessons in [LEARNINGS.md](LEARNINGS.md) (`L-`), and test runs in [TESTS.md](TESTS.md) (`T-`). State in `evergreen.json`. Protocol: MAINTENANCE.md.

Entry shape: `### C-YYYYMMDD-n · date · one-line summary`, then `because:` (IDs or "user request"), `files:` (file and section), and a sentence on what changed. Cite section headings, not line numbers.

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
