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
