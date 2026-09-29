# AGENTS.md

Rules for any AI agent (Claude Code, Copilot, Cursor, Codex, Gemini CLI) working in this repository. `CLAUDE.md` imports this file and `.github/copilot-instructions.md` points here.

## What this is

A cross-agent plugin with one skill, `skills/readwright/`: SKILL.md (when to use the tool and in what order), `references/formats.md` (per-format behaviour, external tools, DRM checks, caps), the single-file CLI `scripts/rw.py` with launchers `rw.sh` and `rw.ps1`, and the evergreen companions (RESEARCH, CHANGELOG, LEARNINGS, TESTS, MAINTENANCE, `evergreen.json`, `evals/evals.json`). Unit tests are in `tests/`; the runnable eval cases are in the root `evals/` folder (`claude plugin eval` format). Handoff notes, decisions and the log are under `ai-docs/` (start with `ai-docs/HANDOFF.md`).

## Rules

- `rw.py` stays one standard-library Python file (3.10 or newer) that runs on Windows, macOS and Linux and prints UTF-8 with LF line endings. It never installs anything, never removes DRM, never runs macros or scripts from a document, and never writes to stdout more than `--max-chars` unless the user asked for a file.
- Every change to the script has a test in `tests/test_rw.py`; run `python tests/test_rw.py` from the repository root before committing. Fixtures are built at test time from invented text. Never commit a real book, a real document or text copied from one, and never paste copyrighted text into an issue, log or test.
- External tools (pdftotext, mutool, ebook-convert, soffice, antiword, pandoc, markitdown) are found at run time with `shutil.which` or known install folders; a missing tool is a clear message naming what to install, never a crash.
- The skill is an evergreen unit. Before editing it read `skills/readwright/evergreen.json`; if `next_due` has passed or `contradiction` is set, say so and refresh after the task (`evergreen-refresh`, or `skills/readwright/MAINTENANCE.md`). Every change is logged in `skills/readwright/CHANGELOG.md` with its reason; lessons from real files go to `LEARNINGS.md` with a code name.
- Research beats recall: format facts and converter options carry an `R-` entry in RESEARCH.md with the date they were checked.
- A release bumps the version in `.claude-plugin/plugin.json`, `plugin.json`, `VERSION` in `rw.py`, `metadata.version` in SKILL.md and `version` in `evergreen.json` together, then tags `vX.Y.Z` and publishes a GitHub Release with the CHANGELOG entry as notes.
- No top-level `bin/` folder: Cowork refuses to install a plugin that has one. Launchers live next to `rw.py`.
- Eval graders: JavaScript regex (`flags: i`, never `(?i)`), one literal tool name per `tool_used` grader, fixture archives written with ZIP_DEFLATED (LEARNINGS L-002). The Bash cases run under WSL2 or Linux, not native Windows.
- Prose people read (README, SKILL.md, references) is checked with the everwrite checker when it is available: `python <everwrite>/scripts/tells.py <files>`, zero strong findings.
- This is a public repository. Nothing in it names a person other than the author credit and the authors of credited public projects, a machine, an absolute path on someone's machine, a private project, or a credential.
- No AI attribution anywhere: no Co-Authored-By trailers, no "generated with" lines in commits, pull requests, releases or files.

## everlast (session knowledge, load on demand)

- `ai-docs/INDEX.md` lists what past sessions learned here (solutions with verified commands, decisions with reasons, plans). At the start of a task, scan it and open only the entries whose title or tags match; no line matches: `everlast.py search "<key terms>"` before concluding nothing was recorded. Read `ai-docs/HANDOFF.md` when continuing unfinished work (everlast-resume skill).
- Before acting on an entry marked `(recheck due)`, run `everlast.py recheck <entry>`, re-run its Verified-by command only when that is read-only or safe (a build, a test, a version query), then record `everlast.py verify <entry>` or `verify <entry> --failed "what broke"`; a fix that changed is superseded, never reused blindly.
- Before finishing a task that hit a dead end, verified a non-obvious command, made a design choice, or taught you something about the user, record it (everlast-capture skill, or `everlast.py note` / `handoff`); rewrite `HANDOFF.md` when work is left unfinished. Say "nothing to record" when that is true.
- Anything naming a person, an internal host or name, a credential, or an opinion about people goes to the private sidecar (`--private`), never here. Lessons about the user or this machine go to the user tier (`--user`).
- Rules go in this file, system layout in CODEMAP.md; the doc set holds only what could not be re-derived from the code in a minute.
- Link documents together with relative markdown links: every markdown folder is reachable from an index whose lines say when to read each file (`ai-docs/INDEX.md` is generated from frontmatter; give entries a one-line `summary`), and an entry links the entries it relates to on a typed `Related:` line (`supersedes`, `contradicts`, `builds on`, `see also`). The set then reads as a graph for people in Obsidian and for agents alike. No wikilinks in the repo.
