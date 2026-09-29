---
title: "Kickoff prompt: finish readwright (external-tool routes, real-file tests, token-saving evidence, 0.2.0)"
kind: plan
status: done
date: 2026-09-29
tags: [readwright, plan, prompt, testing, release]
entities: [readwright, rw.py, calibre, LibreOffice, poppler, MuPDF, pandoc, markitdown]
summary: Paste into a fresh session to take readwright from 0.1.0 (stdlib formats tested, external-tool routes untested) to a 0.2.0 where every advertised route is exercised on real files and the token saving is measured
---

# Kickoff prompt: finish readwright (2026-09-29)

## Goal
readwright 0.2.0 with every advertised external-tool route run on real files and the token saving measured on a full-size book.

## Status
Done 2026-09-29: released as 0.2.0 (see ../HANDOFF.md). Before that: readwright 0.1.0 is public (github.com/m4bwav/readwright), registered in the evergreen catalog and installed as readwright@mark-local. The stdlib formats are tested: 34 unit tests, 7/7 evals, CI green on Linux, macOS and Windows. Every route through an external tool is written but has never run against the real tool. See [../HANDOFF.md](../HANDOFF.md).

## Next single action
Paste the prompt below into a fresh Claude Code session started in the repository's root folder.

## Prompt

---

Finish readwright (this repo: an evergreen skill plus the stdlib CLI `skills/readwright/scripts/rw.py`) and release 0.2.0. Run commands yourself; installing the tools below with winget and pushing and releasing this public repo are pre-authorised. No AI attribution anywhere. Keep rw.py standard-library only; external tools stay optional and detected at run time.

**Read first:** `AGENTS.md`, `ai-docs/HANDOFF.md`, `ai-docs/INDEX.md`, then `skills/readwright/SKILL.md`, `references/formats.md`, `RESEARCH.md`, `LEARNINGS.md`, `TESTS.md`, `evergreen.json`. Load the `evergreen:evergreen-test` skill before touching the evals and `everwrite` before editing prose.

**1. Install the external tools** (Windows, winget; record each exact package id and version in RESEARCH.md): calibre (`ebook-convert`), LibreOffice (`soffice`), poppler for Windows or MuPDF (`pdftotext`, `mutool`), pandoc, and markitdown (`pip install --user markitdown`, used only through `--via markitdown`). `pdftotext` exists today only in Git Bash (`/mingw64/bin`). Make sure rw.py finds each tool from PowerShell as well as Git Bash, including the usual install folders when the tool is not on PATH (for example `C:\Program Files\Calibre2`, `C:\Program Files\LibreOffice\program`). Test the "tool missing" messages too, by hiding PATH.

**2. Exercise every advertised route on real files** and fix what breaks. Build the test files yourself from free material (Project Gutenberg public-domain texts in EPUB, MOBI and plain text; convert with calibre and LibreOffice to AZW3, DOCX, DOC, XLS, PPT, ODT and PDF with a real outline). Never commit a copyrighted text; commit only small generated fixtures or scripts that download or build them. Cover:
   - PDF: text with `pdftotext`, outline with `mutool show FILE outline`. RESEARCH.md marks the outline parser untested.
   - MOBI, AZW3, PRC and FB2 through calibre, including the temp-folder conversion cache.
   - KFX: its `CONT` signature is unverified, so check it against a real KFX file if one can be made legally, or say plainly that it is unverified.
   - Legacy DOC, XLS and PPT through LibreOffice (and antiword for DOC).
   - `--via pandoc` and `--via markitdown`.
   - DRM detection. Detect only; never remove DRM. Use a fixture that carries a DRM-style `encryption.xml`.
   Add a unittest for each route, skipped when its tool is absent, and have CI install the free tools on at least the Ubuntu job (calibre, poppler-utils, libreoffice, pandoc) so the routes run in CI.

**3. Measure the saving on a full-size book.** The eval book is only about 23k tokens today. Use a public-domain novel of 150k tokens or more, and time and count tokens for three routes answering the same two-chapter question: (a) readwright (info, toc, read the sections, grep), (b) a whole-book dump (`epr -d`, `pandoc -t plain`, or `markitdown`) then grep, (c) no skill (unzip and parse by hand). Write the numbers into TESTS.md and the README. Add a full-size action case to the evals with a `--ablation with-without` baseline, and record the run with `evergreen.py tested`.

**4. Rough edges seen in use on 2026-09-29.**
   - A chapter's title page and its body are often separate sections (L-001). Consider making `read --title` include the following short section automatically, or add `--with-next`.
   - Chapter 15 of the test novel is titled "ANWUR AT" (with a space) in its own table of contents, so title matching could ignore internal whitespace.
   - Decide whether readwright should also offer an MCP server or a `bin/` launcher on PATH. Cowork refuses plugins with a top-level `bin/` (see the ai-docs decision), so weigh that first.

**5. Release.**
   - Update SKILL.md, formats.md, the README, CHANGELOG (C- entries citing R-/L-/T- ids) and LEARNINGS (only what a run confirmed).
   - Run the unit tests, the evals, skill-tidy lint and the everwrite check.
   - Bump plugin.json to 0.2.0, push, let CI pass, then tag v0.2.0 and create a GitHub release.
   - Run `claude plugin marketplace update mark-local`, then `claude plugin update readwright@mark-local`. If the update keeps a stale cache, uninstall and reinstall.
   - Record the refresh: `python <evergreen plugin>/scripts/evergreen.py checked readwright --m <magnitude>`.
   - Finish: rewrite `ai-docs/HANDOFF.md`, append to `ai-docs/log.md`, run `everlast.py index .`, commit and push.
