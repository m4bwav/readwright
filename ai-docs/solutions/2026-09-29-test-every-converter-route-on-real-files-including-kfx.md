---
title: Test every converter route on real files, including KFX
kind: solution
status: active
date: 2026-09-29
verified: 2026-09-29
stale_after: 2027-03-29
tags: [testing, calibre, kfx, libreoffice, windows, tools]
aliases: [real_files.py, measure_tokens.py, KFX Output, Kindle Previewer]
summary: read before re-testing the calibre, LibreOffice, PDF or --via routes, or making a KFX file
---

# Test every converter route on real files, including KFX

## Problem

rw.py's routes through calibre, LibreOffice, poppler, MuPDF, pandoc and markitdown were written in 0.1.0 without ever running against the real tools, and KFX detection rested on an unverified signature.

## Dead ends

- Installing with winget and expecting the running shell to find the tools: a shell keeps the PATH it started with. rw.py now also reads the registry PATH and the install folders (LEARNINGS L-008); to use the tools by hand in an old shell, call them by full path.
- `curl` to code.calibre-ebook.com (calibre's plugin index): Windows schannel rejects its certificate chain. Do not switch verification off; fetch through calibre's own TLS (below).
- Hiding one tool by trimming PATH to another tool's folder: on Linux both live in `/usr/bin`. Use `RW_HIDE_TOOLS`.
- Saving `claude plugin eval --keep-temp` traces with a second `wsl` call: the `/tmp/claude-eval-*` folders were already gone. Copy them in the same call.
- Asking LibreOffice to convert the unit tests' minimal PPTX or XLSX: "source file could not be loaded". Make PPT by importing a PDF into Impress (`--infilter=impress_pdf_import`) and XLS from a CSV.

## Fix

Tools (winget ids and versions in skills/readwright/RESEARCH.md, R-20260929-8): `calibre.calibre`, `TheDocumentFoundation.LibreOffice`, `oschwartz10612.Poppler`, `ArtifexSoftware.mutool`, `JohnMacFarlane.Pandoc`, `pip install --user "markitdown[docx,pdf,pptx,xlsx,xls]"`; antiword comes with Git for Windows.

KFX, legally, from a public-domain EPUB: `winget install Amazon.KindlePreviewer`, then fetch calibre's KFX Output and KFX Input plugins through calibre's TLS and add them:

```
calibre-debug kfxget.py      # get_https_resource_securely('https://code.calibre-ebook.com/plugins/272407.zip') and 291290.zip
calibre-customize -a "KFX Output.zip"
calibre-customize -a "KFX Input.zip"
ebook-convert pp.epub pp.kfx   # about 50 s; the file starts CONT 02 00
```

## Verified by

```
python tests/test_rw.py                      # 50 tests; route tests skip when a tool is absent
python tests/real_files.py --json out.json   # downloads Pride and Prejudice, builds every format, 38 routes
python tests/measure_tokens.py               # Moby-Dick, tokens by route
```

2026-09-29 on Windows 11 with every tool: 50/50, 38/38, and the measurement in TESTS.md T-20260929-4. CI's `routes` job installs the tools on Ubuntu with `RW_REQUIRE_TOOLS=1`, so a missing tool fails instead of skipping.

Related: see also [2026-09-29-run-the-readwright-eval-suite-on-windows-native-triggers-wsl.md](2026-09-29-run-the-readwright-eval-suite-on-windows-native-triggers-wsl.md)
