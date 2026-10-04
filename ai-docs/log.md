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

## 2026-09-29 registered and installed
Registered with `evergreen.py register` and added to the mark-local marketplace (`Ai/.claude-plugin/marketplace.json`); installed as readwright@mark-local 0.1.0 (user scope).
## [2026-09-29] index | rebuilt (3 entries)
## [2026-09-29] add | decision: No MCP server and no launcher on PATH for readwright
## [2026-09-29] add | solution: Test every converter route on real files, including KFX
## [2026-09-29] update | solution: Run the readwright eval suite on Windows (full-size case, saving traces)
## [2026-09-29] update | plan: Kickoff prompt: finish readwright, marked done

## 2026-09-29 released 0.2.0
Installed calibre, LibreOffice, poppler, mutool, pandoc, markitdown and Kindle Previewer with the KFX plugins; ran every route on real public-domain books and fixed what broke (tool discovery off PATH, chapters split across files, lost outlines, mutool nesting, XLSX dates, tool errors, markitdown quirks). Added route unit tests, a Linux CI job with the tools, tests/real_files.py, tests/measure_tokens.py and the full-size eval case action-2. Tagged v0.2.0, released, updated readwright@mark-local.
## [2026-09-29] handoff | rewritten for 0.2.0
## [2026-09-29] index | rebuilt (5 entries)

## 2026-10-03 prepared for the Claude plugin directory
Checked the directory's pre-submission list (manifest fields, validate, file sizes and types, names, .gitattributes): all met. Added documentationUrl, supportUrl and privacyPolicyUrl to `.claude-plugin/plugin.json` and a Privacy section to the README (no network calls in the skill, no credentials read; the developer tests download from Project Gutenberg). No launcher packages to pin. Version unchanged at 0.2.0; submission is done by another session.
- 2026-10-04: the plugin icon (icon.png in .claude-plugin) for the Claude directory, chosen from two Z-Image candidates. Z-Image Turbo bf16, 9 steps, cfg 1, res_multistep/simple, seed 605490777, prompt "flat vector app icon, bold simple shapes, minimal, centered single motif, thick clean outlines, high contrast, readable at small size, no text, no letters, no numbers, no words, no logos, square composition, an open book with a magnifying glass over one page, cream book and amber glass on deep teal background"; white corners painted to the background (28, 94, 95)
- 2026-10-04: submitted to the Claude plugin directory, https://claude.ai/directory/manage/plugins/4128fd90-c6f1-41c9-aa8f-c22ad7810d6e (validated main@66a40ec, Scheduled check only, auto-publish on); 1 credential hold (4 findings: env-var reads in rw.py and tests beside XML-namespace and Gutenberg URLs, false positives); status after submit: in review
