# Handoff

## Current state
readwright 0.2.0 is public at https://github.com/m4bwav/readwright (tag v0.2.0, GitHub release published 2026-09-29; CI green on the six-job matrix and the new Linux `routes` job, which installs calibre, LibreOffice, poppler, MuPDF, pandoc, antiword and markitdown and runs every route). Installed as readwright@mark-local 0.2.0. Every route through an external tool has been run on real files: `tests/real_files.py` 38/38 on Pride and Prejudice in every format, KFX included (TESTS.md T-20260929-3). `python tests/test_rw.py`: 50 tests. Eval suite 8/8 with the full-size case action-2 on Moby-Dick (T-20260929-4). Evergreen refresh recorded, next due 2026-11-03.

## In progress
Nothing half-done.

## Findings worth knowing
- Token cost for two chapters of Moby-Dick (309k tokens): readwright 12.6k; whole book printed 310k to 317k; by hand 40k; dump to a file then grep 12k to 13k. In the eval, the model without the skill wrote its own zip extractor and matched readwright's cost on EPUB (LEARNINGS L-010). The README says so.
- `read` defaults to 25,000 characters because Claude Code shows 30,000 of a command's output (L-009).
- This machine now has all the tools, plus Kindle Previewer and calibre's KFX Input and Output plugins; how to make a KFX: [solutions/2026-09-29-test-every-converter-route-on-real-files-including-kfx.md](solutions/2026-09-29-test-every-converter-route-on-real-files-including-kfx.md).

## Decisions made this session
No MCP server and no launcher on PATH (decision entry in [INDEX.md](INDEX.md)).

## Open
- MuPDF 1.24 to 1.27 outline format unchecked (only 1.23); a DRM-protected KFX never seen on disk; pdftotext `-remove-hyphens` undecided (RESEARCH.md, Open questions).
- ubuntu-latest moves to Ubuntu 26 from 2026-10-19; the `routes` job's apt package names may need a look then.

## Next single action
None owed. Next scheduled work is the evergreen refresh due 2026-11-03 (or the EPUB 3.4 event after 2026-10-19).
