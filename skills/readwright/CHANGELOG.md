# Changelog: readwright

Every change to [SKILL.md](SKILL.md) and its companions, newest first, each with the reason. Reasons cite findings in [RESEARCH.md](RESEARCH.md) (`R-`), lessons in [LEARNINGS.md](LEARNINGS.md) (`L-`), and test runs in [TESTS.md](TESTS.md) (`T-`). State in `evergreen.json`. Protocol: MAINTENANCE.md.

Entry shape: `### C-YYYYMMDD-n · date · one-line summary`, then `because:` (IDs or "user request"), `files:` (file and section), and a sentence on what changed. Cite section headings, not line numbers.

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
