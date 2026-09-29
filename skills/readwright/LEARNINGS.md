# Learnings: readwright

Procedural lessons for [SKILL.md](SKILL.md). Research findings live in [RESEARCH.md](RESEARCH.md); every change is logged in [CHANGELOG.md](CHANGELOG.md); test runs in [TESTS.md](TESTS.md); state in `evergreen.json`. Format and write-time gate: MAINTENANCE.md (LEARNINGS-FORMAT). Retired entries go to LEARNINGS-ARCHIVE.md with a reason.

Write an entry the moment a real signal happens: a user correction, the same error twice, a discovered workaround, an environment fact, a stated preference, a failed test or a failure in use. Check existing entries first, by meaning (`evergreen.py search "<the lesson>" --kinds learnings` finds near-duplicates in every registered unit): add / update / retire / none. Trigger and Hypothesis are required. Promote after three confirmations; retire when harmful > helpful.

## Active

### L-001 · 2026-09-29 · A chapter's title page and its body are often separate sections
- Trigger: smoke test on a real EPUB novel, 2026-09-29: `read --title <chapter title>` returned a 72-word section (chapter number, title, epigraph); the chapter's 6,330 words were the next spine file, titled by its date line in the NCX.
- Hypothesis: publishers and calibre split each chapter's opener into its own XHTML file, and the NCX gives the body its own entry, so a title match lands on the opener.
- Rule: when a selection is short, read the next section too; rw.py now says so at the end of the output (C-20260929-2).
- Evidence: T-20260929-1, C-20260929-2, confirmed 2026-09-29
- Scope: skill
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

### L-002 · 2026-09-29 · claude plugin eval graders: JavaScript regex, one tool name, a compressed fixture
- Trigger: first WSL2 run of action-1 and outcome-1, 2026-09-29: `(?i)` threw "Invalid regular expression"; `tool: Bash|PowerShell` counted zero calls although the trace held three Bash calls to rw.py; and a stored (uncompressed) fixture EPUB could be read by plain Grep.
- Hypothesis: the harness compiles patterns as JavaScript RegExp (flags go in `flags:`), matches `tool` as a literal name in 2.1.281, and a stored zip keeps the XHTML as plain text.
- Rule: write `flags: i`, one literal tool name per grader, and build fixture archives with ZIP_DEFLATED.
- Evidence: T-20260929-2, C-20260929-3, confirmed 2026-09-29
- Scope: skill (applies to any plugin eval suite on this harness)
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29

<!-- Example (delete once you have a real entry):
### L-001 · 2026-09-29 · One-line lesson in plain words
- Trigger: what happened, with dates or counts
- Hypothesis: why
- Rule: the shortest instruction that prevents the trigger
- Evidence: C-20260929-1, T-20260929-1, confirmed 2026-09-29
- Scope: skill | repo:<slug> | env:<name> | global
- Status: active · helpful 1 · harmful 0 · last_confirmed 2026-09-29
-->
