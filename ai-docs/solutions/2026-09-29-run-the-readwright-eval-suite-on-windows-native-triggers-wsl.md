---
title: Run the readwright eval suite on Windows (native triggers, WSL2 for Bash cases)
kind: solution
status: active
date: 2026-09-29
verified: 2026-09-29
stale_after: 2026-12-28
tags: [evals, wsl, testing]
aliases: [claude plugin eval, graders]
summary: read before running or editing the evals/ cases
---

# Run the readwright eval suite on Windows (native triggers, WSL2 for Bash cases)

## Problem

Running the eval suite in `evals/` with `claude plugin eval` on this Windows machine: the Bash cases (action-1, outcome-1) need a Bash grant, which native Windows refuses (no Windows sandbox), and several grader details failed on the first run.

## Dead ends

- Running before `.claude-plugin/plugin.json` existed: the plugin did not load and every trigger failed (the run is still useful as a no-skill baseline).
- `(?i)` inside a grader pattern: "Invalid regular expression" (the harness uses JavaScript RegExp).
- `tool: Bash|PowerShell`: counted zero calls although the trace held three Bash calls (harness 2.1.281).
- A fixture EPUB written with ZIP_STORED: plain Grep can read the text, so the case does not prove the tool was needed.
- `python3` in Git Bash on this machine is the Microsoft Store stub; probe with `python3 -c "import sys"` before using it.

## Fix

Graders use `flags: i` and one literal tool name; fixtures are written with ZIP_DEFLATED. Trigger and decoy cases run natively; the Bash cases run in WSL2 from a copy of the repository in the Linux home.

## Verified by

```
claude plugin eval . --ablation none --no-publish -j 4 --tag trigger --trust-plugin
wsl -e bash -lc 'rm -rf ~/rw-eval && mkdir -p ~/rw-eval && cd "$REPO" && tar --exclude=evals/results -cf - . | tar -xf - -C ~/rw-eval && cd ~/rw-eval && claude plugin eval . --ablation none --no-publish -j 2 --tag bash --scaffold --allow-tools Bash Write Edit --trust-plugin'
```

`REPO` is the repository as WSL sees it (`/mnt/<drive>/...`). 2026-09-29: 5/5 native, 2/2 in WSL2 (TESTS.md T-20260929-2); later 8/8 with the full-size case action-2 (T-20260929-4), whose fixture downloads Moby-Dick unless `RW_EVAL_BOOKS` names a folder holding `moby.epub` (export it before the eval). `--tag fullsize` runs only that case. Add `--ablation with-without` for the no-skill baseline arm. To read the traces, copy `/tmp/claude-eval-*/out/trace.jsonl` in the same `wsl` call that ran the eval (after `chmod 700` on the folder and its `sealed` subfolder); a later call finds them gone. Clean up after `--keep-temp` runs: `chmod -R u+rwx /tmp/claude-eval-*; rm -rf /tmp/claude-eval-*` in WSL, and remove `%TEMP%\claude-eval-*` folders on Windows.

Related: builds on [../../skills/readwright/LEARNINGS.md](../../skills/readwright/LEARNINGS.md)
