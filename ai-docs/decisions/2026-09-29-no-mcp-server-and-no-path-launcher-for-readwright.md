---
title: "No MCP server and no launcher on PATH for readwright"
kind: decision
status: active
date: 2026-09-29
verified: 2026-09-29
stale_after: 2027-03-29
tags: [design, mcp, launcher, cowork]
summary: read before adding an MCP server, a bin/ folder or a PATH launcher to readwright
---

# No MCP server and no launcher on PATH for readwright

## Context

The kickoff plan for 0.2.0 asked whether readwright should also ship an MCP server or a `bin/` launcher on PATH, so agents could call it without the long `python .../scripts/rw.py` path.

## Decision

Neither, for now. The skill keeps calling `rw.py` through the shell, with the launchers `rw.sh` and `rw.ps1` next to it.

## Reasons

- Cowork refuses to install a plugin with a top-level `bin/` folder (research R-20260927-1 in the everlast plugin, restated in AGENTS.md), and readwright is meant to install there too.
- An MCP server puts its tool definitions into every session whether or not a document is read; the CLI costs nothing until the skill loads. The earlier decision already rejected one for this reason, and EPUB-only MCP servers exist for agents without a shell.
- The long path costs one line in SKILL.md (`RW` is defined once), and the evals show agents use it without trouble: in T-20260929-4 every run with the skill called `rw.py` directly.
- The full-size eval (T-20260929-4) found no call-overhead problem to solve. The costs that mattered were output size (fixed by the 25,000-character default) and the toc's ids.

## Rejected

- `bin/rw` in the plugin: breaks Cowork installs.
- An MCP server wrapping info, toc, read and grep: always-on definitions, a second code path to test, and no agent in the evals needed it.
- Asking users to put `scripts/` on PATH: a manual step per machine, and the skill cannot rely on it.

## Consequences

Agents without a shell (some chat-only surfaces) cannot use readwright. Revisit if Cowork accepts `bin/`, or if a host appears where skills load but shells do not.

Related: builds on [2026-09-29-readwright-as-its-own-stdlib-cli-plugin-outline-then-section.md](2026-09-29-readwright-as-its-own-stdlib-cli-plugin-outline-then-section.md)
