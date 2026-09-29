# Tests: readwright

Test runs for [SKILL.md](SKILL.md). Cases live in `evals/evals.json`. A failure that taught something is a lesson in [LEARNINGS.md](LEARNINGS.md); a fix it caused is logged in [CHANGELOG.md](CHANGELOG.md) with `because: T-...`; research it triggered is in [RESEARCH.md](RESEARCH.md); counts and the failing list are in `evergreen.json` under `tests`. Rules: MAINTENANCE.md (testing section) and the plugin's `protocol/TESTING.md`.

A test passes on evidence (a tool call in the trace, a file, a marker, a log line), never on the transcript's claim that something was done.

Entry shape: `### T-YYYYMMDD-n · date · harness · env · passed/total`, then one line per failing case (`id · kind · class · what the evidence showed`), then `led to:` (L-, C-, R- ids or none). Newest first. Budget 150 lines; archive older runs to `TESTS-ARCHIVE.md`.

## Runs

### T-20260929-4 · 2026-09-29 · claude plugin eval 2.1.281 (default model) · Windows 11 native for trigger and decoy, WSL2 Ubuntu for the Bash cases · 8/8
- New case action-2 (full size): "what happens in chapters 16 and 17 of ./fixture/moby.epub?". The fixture downloads Moby-Dick from Project Gutenberg (215,845 words, about 309,000 tokens); graders: Skill called, `rw.py ... read` in the trace, the answer names the Pequod or Peleg or Bildad and the Ramadan, and no whole-book dump (unzip -p, epr -d, pandoc or markitdown to stdout). Tagged `bash, fullsize`.
- Baseline, `--ablation with-without`, 3 runs per arm after C-20260929-6: with 1.00 in 3 of 3 (4 to 5 tool calls, 12.1k to 12.2k tokens of tool output, $0.29 to $0.30); without 0.67 in 3 of 3, failing only the rw.py grader. Without the skill the model listed the zip, wrote a zipfile-and-regex extractor, pulled the two XHTML files and answered correctly (12.9k to 13.1k tokens, $0.29 to $0.31). No arm dumped the book. On EPUB the skill costs about what a capable model's own code costs (L-010).
- The first baseline pair, before C-20260929-6: with 1.00 ($0.33) but `read --section 24-25 --max-chars 50000` printed 52,000 characters, over Claude Code's 30,000 inline, so the output went to a file and the chapters were read twice more (L-009).
- Rest of the suite after the SKILL.md edits: trigger-1, trigger-2, trigger-3, decoy-1, decoy-2 native 5/5 ($0.48); action-1, outcome-1 and action-2 in WSL2 3/3 ($1.16).
- Token measurement, `tests/measure_tokens.py`, same book and question (tokens are printed characters divided by 4): readwright 12,551 (info 107, toc 1,782, read 10,027, grep 634); whole book printed by `epr -d` 310,364, `pandoc -t plain` 310,848, `markitdown` 317,098; dump to a file then grep and print the range 12,141 to 13,331; by hand (unzip -l, the NCX, the raw XHTML) 39,868. Before C-20260929-5 the toc was 3,829 tokens, over half of it section ids.
- untested elsewhere: the eval ran on this Windows machine and its WSL2 only.
- led to: L-009, L-010, C-20260929-5, C-20260929-6

### T-20260929-3 · 2026-09-29 · unittest, tests/real_files.py, GitHub Actions · Windows 11 (Python 3.14 and 3.11), CI Linux, macOS, Windows · 88/88
- External tools installed for the run (R-20260929-8): calibre 9.15.0, LibreOffice 26.8.0.3, poppler 25.07.0, MuPDF 1.23.0, pandoc 3.12, markitdown 0.1.8 with extras, antiword from Git for Windows, Kindle Previewer 3.107.0 with calibre's KFX Output 2.21.0 and KFX Input 2.34.2.
- `tests/real_files.py`: Pride and Prejudice from Project Gutenberg (EPUB, AZW3, MOBI, text) plus FB2, PDF, DOCX, PDB, LIT, RTF, AZW3, MOBI, PRC and KFX written by calibre, and DOC, ODT, PDF, XLS and PPT written by LibreOffice. 38/38 routes pass: each book route finds 61 chapters and 129,945 to 132,046 words, puts the first sentence in a chapter-I section and reads chapter LXI by title. First conversion 1.4 to 3.7 s, cached 0.17 to 0.23 s; built-in formats 0.17 to 0.28 s. DRM fixtures (an EPUB with ADEPT rights.xml and an AES encryption.xml entry; a MOBI with the encryption field set to 2) are refused; every missing tool is named with PATH hidden.
- Failures on the way, all fixed: chapters split across EPUB files and a bracketed text heading (L-003); tool errors shown as "Traceback", markitdown extras, RTF passthrough (L-004); outline depth (L-005); FB2 and PDB outlines, `CHAPTERXXVII`, `--via pandoc` on FB2 (L-006); XLS dates (L-007); tools off PATH (L-008).
- KFX: a real KFX made from the public-domain EPUB starts `CONT` then `02 00`, confirming the signature (R-20260929-7); calibre with KFX Input reads it (67 sections, 130,184 words).
- 50 unit tests with every tool present, no skips (Python 3.14; 3.11 skips markitdown, installed for 3.14 only). CI: the six-job matrix plus the new `routes` job on Ubuntu 24.04 (calibre 7.6, LibreOffice 24.2, MuPDF 1.23.10, poppler 24.02, pandoc 3.1.3, antiword 0.37, markitdown 0.1.8), 50 tests, no skips. Its first run failed one test, which hid LibreOffice by PATH while it shares `/usr/bin` with antiword (L-008).
- led to: L-003 to L-008, R-20260929-7 to R-20260929-9, C-20260929-4, C-20260929-5

### T-20260929-2 · 2026-09-29 · claude plugin eval 2.1.281 (default model, 1 run per case) · Windows 11 native for trigger and decoy, WSL2 Ubuntu for the Bash cases · 7/7
- Suite: the root `evals/` folder (claude plugin eval format), converted from `evals/evals.json`. Native: `claude plugin eval . --ablation none --no-publish -j 4 --tag trigger --trust-plugin`, 5/5, 0.54 USD, 35 s. WSL2, from a copy of the repository in the Linux home: `--tag bash --scaffold --allow-tools Bash Write Edit --trust-plugin`, 2/2, 0.26 USD.
- trigger-1 (epub chapters), trigger-2 (lease.docx), trigger-3 (azw3 search) · trigger · pass · `Skill(readwright:readwright)` called once each; all three then hit the case's 3-turn cap, which is the limit, not a failure.
- decoy-1 (write a Word document), decoy-2 (screenshot) · trigger · pass · readwright not called.
- action-1 · action · pass · Skill, then `rw.py info` and `toc`, then `rw.py read --section 3`; the answer names the storm and the lamp.
- outcome-1 · outcome · pass · `rw.py grep` found Tamsin in chapter 9 (titled Visitors, so the toc does not give it away); no whole-book dump.
- Baseline (`--ablation with-without`, Bash cases): action-1 with 1.00, without 0.50; outcome-1 with 1.00, without 0.80 (mean delta +0.35, 0.55 USD). Without the skill the model still answered both small fixtures, by unzipping the EPUB and writing its own zip-and-regex parser over four Bash calls; with it, two rw.py calls. The fixture is 23k tokens; the gap should grow with a real book, which no case covers yet.
- A first native run before `.claude-plugin/plugin.json` existed loaded no plugin and failed all three triggers: the no-skill route for the docx prompt was a subagent told to `unzip -p word/document.xml`.
- Harness fixes on the way (L-002): graders use `flags: i`, not `(?i)` (JavaScript regex); `tool: Bash`, since `Bash|PowerShell` counted zero calls in this harness version; the fixture EPUB is deflated, because a stored zip let plain Grep read the text.
- led to: L-002, C-20260929-3

### T-20260929-1 · 2026-09-29 · unittest (tests/test_rw.py) + smoke test on a real EPUB · Windows 11, Python 3.14, 3.11, 3.10 · 34/34
- 34 unit tests on fixtures built at test time (EPUB with nav and with NCX, fragment splits, font obfuscation, ADEPT DRM, DOCX with a localised heading style, ODT, ODS with repeated cells, PPTX with notes, XLSX, FB2, RTF, HTML, EML, TXT, Markdown, CSV, JSON, zip with --member, MOBI DRM, Outlook .msg, PDF through pdftotext when present). One skip per environment: the PDF test runs where pdftotext exists (Git Bash) and the missing-tool test where it does not (PowerShell).
- Smoke test, read-only, on a 1.3 MB commercial EPUB novel (80 sections, 202k words, about 303k tokens): info 0.31 s, toc 0.29 s, `read --title <chapter title> --max-chars 2000` 0.29 s, `grep <a proper noun> -C 1 --max 3` 0.28 s (11 matches in 4 sections), `read` with no selector refused in 0.31 s, `dump --out` 0.30 s. It showed the chapter-opener pattern (L-001).
- led to: L-001, C-20260929-2
