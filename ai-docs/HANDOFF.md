# Handoff

## Current state
readwright 0.1.0 is built and committed locally on `main`; there is no GitHub repository and no remote yet. One evergreen skill (`skills/readwright/`, tier moderate, next due 2026-10-29) and the stdlib CLI `scripts/rw.py` (info, toc, read, grep, dump, formats). `python tests/test_rw.py`: 34 tests pass on Python 3.10, 3.11 and 3.14 (one skip per environment, depending on whether pdftotext is on PATH). Eval suite 7/7 (TESTS.md T-20260929-2). Smoke test on a real 1.3 MB EPUB: every command about 0.3 s.

## In progress
Nothing half-done. Not yet exercised on real files: PDF outline via mutool, calibre conversions (MOBI, AZW3, KFX), LibreOffice conversions (DOC, XLS, PPT), `--via pandoc|markitdown`. None of those tools is installed on the development machine except pdftotext and antiword (Git Bash mingw64 only).

## Decisions made this session
See [INDEX.md](INDEX.md): readwright as its own stdlib CLI plugin, outline then sections then search.

## Dead ends hit
Eval harness details (JavaScript regex, literal tool names, deflated fixtures, WSL for Bash cases): see the solution entry in INDEX.md and LEARNINGS L-002.

## Next single action
Owner decisions before going public: the name, the licence (MIT like the siblings), and whether to register readwright in the evergreen catalog. Then create m4bwav/readwright, push `main`, let CI run on the three systems, tag v0.1.0 with a GitHub Release, and add it to the local marketplace if wanted.
