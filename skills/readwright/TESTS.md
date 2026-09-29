# Tests: readwright

Test runs for [SKILL.md](SKILL.md). Cases live in `evals/evals.json`. A failure that taught something is a lesson in [LEARNINGS.md](LEARNINGS.md); a fix it caused is logged in [CHANGELOG.md](CHANGELOG.md) with `because: T-...`; research it triggered is in [RESEARCH.md](RESEARCH.md); counts and the failing list are in `evergreen.json` under `tests`. Rules: MAINTENANCE.md (testing section) and the plugin's `protocol/TESTING.md`.

A test passes on evidence (a tool call in the trace, a file, a marker, a log line), never on the transcript's claim that something was done.

Entry shape: `### T-YYYYMMDD-n · date · harness · env · passed/total`, then one line per failing case (`id · kind · class · what the evidence showed`), then `led to:` (L-, C-, R- ids or none). Newest first. Budget 150 lines; archive older runs to `TESTS-ARCHIVE.md`.

## Runs

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
- Smoke test, read-only, on a 1.3 MB commercial EPUB novel (80 sections, 202k words, about 303k tokens): info 0.31 s, toc 0.29 s, `read --title ANWURAT --max-chars 2000` 0.29 s, `grep Swazond -C 1 --max 3` 0.28 s (11 matches in 4 sections), `read` with no selector refused in 0.31 s, `dump --out` 0.30 s. It showed the chapter-opener pattern (L-001).
- led to: L-001, C-20260929-2
