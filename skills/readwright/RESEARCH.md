# Research: readwright

Findings that back [SKILL.md](SKILL.md), [references/formats.md](references/formats.md) and `scripts/rw.py`. Changes they caused are logged in [CHANGELOG.md](CHANGELOG.md); procedural lessons live in [LEARNINGS.md](LEARNINGS.md); test runs and their evidence in [TESTS.md](TESTS.md); schedule and state in `evergreen.json`. Protocol: [MAINTENANCE.md](MAINTENANCE.md).

Topic: Reading text from ebook and document formats for AI agents: EPUB (W3C spec), MOBI/AZW/KFX, FB2, OOXML, ODF, RTF, HTML, EML, PDF text extraction; the converters readwright shells out to (calibre, poppler, MuPDF, LibreOffice, pandoc, markitdown); DRM markers; agent tools for sectioned document reading. Tier `moderate`. Last refresh 2026-09-29; next due 2026-10-29.

## Current understanding

- **Outline first, then sections, is the right shape for agents.** Anthropic's context-engineering guidance recommends just-in-time retrieval: keep light references (here, a toc with word counts) and let the agent fetch what it needs, over loading whole documents. Whole-book dumps (`epr -d`, `pandoc -t plain`) cost 150k to 300k tokens for a novel. Confident (R-20260929-4).
- **EPUB is stable underneath.** EPUB 3.3 is a W3C Recommendation (the edition dated 13 January 2026); EPUB 3.4 is a Candidate Recommendation Snapshot (21 July 2026, comments until 19 October 2026) whose changes are media types (JPEG XL, AVIF, Opus), not the container. `META-INF/container.xml` names the package document; `mimetype` is the first, stored entry; the nav document has `properties="nav"`; the NCX is a legacy feature kept for EPUB 2 readers, and many books in the wild still rely on it (the smoke-test book does). Confident (R-20260929-1).
- **DRM markers are well known and cheap to check.** EPUB: `encryption.xml` entries other than font obfuscation (`http://www.idpf.org/2008/embedding`, `http://ns.adobe.com/pdf/enc#RC`), plus `rights.xml` (Adobe ADEPT) or `license.lcpl` (Readium LCP). MOBI: record 0 offset 12, encryption type 1 or 2. KFX: the `\xeaDRMION\xee` signature. Treating font obfuscation as DRM is a known bug in other tools. Confident for EPUB and MOBI. The KFX container starts `CONT` then a two-byte little-endian version, checked on a real file (R-20260929-7); KFX DRM detection is still by the `DRMION` signature alone, never seen on a real file here (R-20260929-1, R-20260929-2, R-20260929-7).
- **Converters are current and maintained** (checked 2026-09-29): calibre 9.15 (2026-09-18), pandoc 3.12 (2026-09-29), markitdown 0.1.8 (2026-09-21, reads EPUB), poppler 26.09.0 (2026-09-03), MuPDF 1.27.2 (2026-02-18), LibreOffice 26.8 (2026-08-26). calibre reads KFX only with the third-party KFX Input plugin (2.34.2 works with calibre 9.15). winget's poppler (25.07) and mutool (1.23.0) packages lag those releases. Every route was run on real files with the versions in R-20260929-8. Confident (R-20260929-3, R-20260929-7, R-20260929-8).
- **What each converter does on real files differs from its feature list.** pandoc reads EPUB, DOCX, ODT, FB2 and RTF, and refuses PDF and the legacy Office formats. markitdown needs extras for most formats, returns RTF unchanged and takes 26 s on a 371-page PDF. calibre's FB2 and PDB writers drop the chapter outline. `mutool show outline` nests with tabs. Confident for the versions tested (R-20260929-9).
- **Tooling landscape.** Whole-file converters dominate (markitdown, docling, pandoc). Section-aware readers exist mostly as EPUB-only MCP servers (onebirdrocks/ebook-mcp, kajuberdut/epub-mcp, joshstrange/bookorbit-mcp) and an epub skill. None found covers EPUB, Office, ODF, FB2, RTF and email behind one outline-read-search interface with no dependencies, which is readwright's niche. epr (MIT) and its successor epy (GPL-3.0) are dormant human readers. Fairly confident; the tooling track should re-check each refresh (R-20260929-5).
- **The formats readwright parses itself are frozen or slow.** RTF 1.9.1 (2008, no further updates planned), FB2 2.x, ODF 1.4 (OASIS Standard 2025-12-03), OOXML. Their risk is odd files in the wild, not spec change. Confident (R-20260929-6).

## Open questions

- `mutool show FILE outline` output on MuPDF 1.24 to 1.27: checked on 1.23.0 and 1.23.10 only (L-005).
- Whether pdftotext's new `-remove-hyphens` (poppler 26.05) should be used by default for PDFs of prose; the winget poppler (25.07) does not have it yet.
- What a DRM-protected KFX looks like on disk: the `DRMION` check has only been read in source code, never matched on a file.
- Whether the arXiv paper "Is Progressive Disclosure All You Need for Long-Context Agents?" (2607.17598) supports or qualifies the outline-first design; only its title was seen.

## Search plan

Four tracks; every refresh runs at least one query on each (scope each to the period since the last refresh; add the year). Protocol §4 explains the tracks and how tooling, practice and testing findings are judged.

Subject (the goal and the latest thinking on reaching it):

- `site:w3.org epub 3.4` (CR to Recommendation; any change to OCF, nav or encryption); `https://www.w3.org/TR/epub-34/`
- calibre `https://calibre-ebook.com/whats-new` (input formats, ebook-convert options); `https://github.com/jgm/pandoc/releases`; `https://pypi.org/project/markitdown/`; `https://poppler.freedesktop.org/releases.html` (pdftotext options); MuPDF release notes; LibreOffice release notes (`--convert-to`, headless)
- `new ebook format <year>` and `kindle kfx format change <year>` (new Kindle formats, DRM changes)
- `https://api.github.com/repos/wustho/epr` and `/wustho/epy` (archived? new release?)

Tooling (skills, plugins, MCP servers, scripts built for this subject):

- `path:SKILL.md epub OR ebook OR "read document"` on GitHub code search, sorted by recently updated; `npx skills find "epub"` and skills.sh for install counts
- `https://registry.modelcontextprotocol.io/v0/servers?search=epub` and `?search=document`; `"ebook" OR "epub" mcp server site:github.com <year>`
- Supersession sweep: does markitdown, docling or Claude Code's Read tool gain outline or section reading for EPUB or DOCX? (`markitdown epub chapters`, Claude Code changelog "Read tool" formats)
- Practitioner test on every candidate: commit in the last 90 days, issues answered, author has other work in the area, ships tests

Practice (how others use AI agents on this goal):

- `"claude code" OR codex OR cursor epub OR ebook "read" chapter <year>` on r/ClaudeAI, r/ClaudeCode, hn.algolia.com
- `site:arxiv.org long document agent progressive disclosure OR "table of contents" navigation <year>`
- `site:anthropic.com/engineering context <year>`

Testing (how work on this subject is verified, and how skills for it are tuned):

- `document text extraction benchmark <year>` (OmniDocBench, olmOCR-Bench style unit-test facts: known strings present, order kept, no header or footer junk)
- `path:SKILL.md epub eval OR evals` on GitHub; `claude plugin eval` docs for trigger and tool-use graders

Best sources (primary first): the W3C EPUB specs, the MobileRead wiki for MOBI and FB2, the Microsoft RTF 1.9.1 spec, OASIS ODF, the release pages of calibre, pandoc, markitdown, poppler, MuPDF and LibreOffice, the GitHub API for repository status. Noisy: SEO "best ebook converter" lists, DRM-removal forums (used only to learn what DRM looks like, never how to remove it).

## Findings log

Newest first. One entry per material finding; a quiet refresh gets one entry saying so. `Track` is subject, tooling, practice, or testing. R-20260929-1 to R-20260929-6 came from one research pass on 2026-09-29 (about 30 searches and fetches, run by a research subagent) plus the author's reading of the specs while writing the parsers; R-20260929-7 to R-20260929-9 from running the tools on real files the same day.

### R-20260929-9 · 2026-09-29 · Converter behaviour on real files
- Summary: run on Pride and Prejudice in every format (T-20260929-3). pandoc 3.12 reads EPUB, DOCX, ODT, FB2 and RTF, and stops with "Unknown input format" on PDF, XLS and PPT (no reader for them). markitdown 0.1.8 without extras fails on DOCX, PDF and XLS with MissingDependencyException (`markitdown[docx]` and so on); with `[docx,pdf,pptx,xlsx,xls]` it reads EPUB, DOCX, PDF, XLSX and XLS, raises UnsupportedFormatException on ODT and PPT, and passes RTF through as raw RTF text. Its CLI encodes stdout with `sys.stdout.encoding` (the console code page on Windows) but writes `-o FILE` as UTF-8 (source: `markitdown/__main__.py`, `_handle_output`). On the 371-page calibre PDF it took 26 s, pdftotext 0.84 s. calibre 9.15's FB2 writer keeps one `<title>` for a whole novel; its PDB (eReader) round trip leaves four toc entries. MuPDF 1.23 prints the outline as a marker, one tab per level, the quoted title, a tab and `#page=N&zoom=...`, with CRLF on Windows. LibreOffice writes a CSV date into XLS as a date-formatted serial. antiword 0.37 refuses a document whose text stream is too small. LibreOffice's Windows `soffice.com` waits for the conversion; its bundled Python prints "Could not find platform independent libraries" on every run, harmlessly.
- Track: testing
- Sources: the tools' own output on the test files; https://github.com/microsoft/markitdown (`__main__.py`)
- Magnitude: minor (behaviour of tools already used; fixes in rw.py, no change to the approach)
- Applied: C-20260929-4 (tool_error, load_via, parse_outline, refine, xlsx_date_styles), references/formats.md (external tools)

### R-20260929-8 · 2026-09-29 · Installing the tools: package ids, versions, where they land
- Summary: Windows 11 with winget: `calibre.calibre` 9.15.0 (MSI, adds `C:\Program Files\Calibre2\` to the machine PATH), `TheDocumentFoundation.LibreOffice` 26.8.0.3 (MSI, nothing on PATH; `soffice.com` and `soffice.exe` in `Program Files\LibreOffice\program`), `oschwartz10612.Poppler` 25.07.0 (portable zip under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\oschwartz10612.Poppler_...\poppler-25.07.0\Library\bin`, added to the user PATH), `ArtifexSoftware.mutool` 1.23.0 (portable, same Packages folder), `JohnMacFarlane.Pandoc` 3.12 (per-user MSI, `%LOCALAPPDATA%\Pandoc`), `Amazon.KindlePreviewer` 3.107.0 (for KFX output only). markitdown 0.1.8 by `pip install --user "markitdown[docx,pdf,pptx,xlsx,xls]"` lands in `%APPDATA%\Python\Python314\Scripts`, off PATH. Git for Windows already ships pdftotext, pdfinfo and antiword in `mingw64\bin`. MuPDF has no newer winget package than 1.23.0. Ubuntu 24.04 (CI) apt: calibre 7.6.0, libreoffice 24.2.7, mupdf-tools 1.23.10, poppler-utils 24.02.0, pandoc 3.1.3, antiword 0.37; markitdown 0.1.8 from pip. calibre's plugin index at code.calibre-ebook.com failed certificate verification with Windows schannel; calibre's own `get_https_resource_securely` (run with `calibre-debug`) fetched it.
- Track: tooling
- Sources: `winget search` and `winget install` output; `apt-get` log of CI run 36641739649; `pip show markitdown`
- Magnitude: minor
- Applied: C-20260929-4 (tool_dirs, windows_path_dirs), references/formats.md (install lines), .github/workflows/tests.yml (routes job)

### R-20260929-7 · 2026-09-29 · KFX container signature verified
- Summary: Kindle Previewer 3.107.0 with calibre's KFX Output plugin 2.21.0 (by jhowell, from calibre's plugin index, updated 2026-09-28) converted the public-domain Pride and Prejudice EPUB to a 1.2 MB KFX in 52 s. Its first bytes are `43 4F 4E 54 02 00` (`CONT`, version 2 little-endian). calibre 9.15 with KFX Input 2.34.2 (updated 2026-08-27) converts it back to EPUB; readwright reads 67 sections and 130,184 words from it. Both plugins are free and neither handles DRM. The `DRMION` signature of an encrypted KFX was not seen on a file.
- Track: subject
- Sources: the file itself; `calibre-customize -l`; https://code.calibre-ebook.com/plugins/plugins.json.bz2 (KFX Input 291290, KFX Output 272407)
- Magnitude: minor (confirms an unverified claim)
- Applied: C-20260929-4 (detect: `CONT` plus version, any extension), references/formats.md (Detection, KFX install)

### R-20260929-6 · 2026-09-29 · Frozen formats: RTF, FB2, ODF
- Summary: RTF 1.9.1 is dated 19 March 2008 and Microsoft plans no further updates. `\uN` is a signed 16-bit code unit (negative values plus 65536; surrogate pairs as two escapes), `\ucN` sets how many fallback characters follow, `\'hh` is a byte in the `\ansicpg` code page, and a `{\*\word` group whose word is unknown must be skipped whole. FB2: root `FictionBook` in namespace `http://www.gribuser.ru/xml/fictionbook/2.0`, with `description`, `body` (nested `section` with `title`, `p`, `poem`, `cite`) and base64 `binary`; often shipped as `.fb2.zip`; notes bodies as `body name="notes"` unverified. ODF 1.4 became an OASIS Standard on 2025-12-03; `text:h`/`text:outline-level` and the mimetype-first rule were not re-fetched.
- Track: subject
- Sources: https://en.wikipedia.org/wiki/Rich_Text_Format, https://www.biblioscape.com/rtf15_spec.htm, https://wiki.mobileread.com/wiki/FB2, https://github.com/gribuser/fb2, https://www.oasis-open.org/2025/12/03/oasis-approves-open-document-format-odf-v1-4-standard-marking-20-years-of-interoperable-document-innovation/
- Magnitude: n/a (initial)
- Applied: C-20260929-1 (rtf_to_text, load_fb2, load_odf)

### R-20260929-5 · 2026-09-29 · Tooling: whole-file converters dominate; section readers are EPUB-only
- Summary: markitdown (MIT, very widely starred, 0.1.8) and docling (MIT, active) convert whole files to Markdown with no outline-then-section reading. Section-aware tools found: onebirdrocks/ebook-mcp (Apache-2.0, EPUB and PDF, toc and per-chapter tools, last push 2026-01-10), kajuberdut/epub-mcp (toc then chapter), joshstrange/bookorbit-mcp (sections sliced by anchor range), and an epub skill listed on claudemarketplaces.com (metadata, toc, chapter reading, dump, search). None covers Office, ODF, FB2, RTF and email with no dependencies. epr (MIT, last push 2023-02-08, 1,411 stars, `-d` dumps each paragraph as one line) and epy (GPL-3.0, last push 2024-03-17) are dormant; readwright borrows no code from either. Decision: build on the standard library and point at markitdown and pandoc through `--via` rather than re-implement them.
- Track: tooling
- Sources: https://github.com/microsoft/markitdown, https://api.github.com/repos/docling-project/docling, https://github.com/onebirdrocks/ebook-mcp, https://github.com/kajuberdut/epub-mcp, https://github.com/joshstrange/bookorbit-mcp, https://api.github.com/repos/wustho/epr, https://github.com/wustho/epy
- Magnitude: n/a (initial)
- Applied: C-20260929-1 (`--via`, README credits)

### R-20260929-4 · 2026-09-29 · Practice and testing: just-in-time retrieval; unit-test facts for extraction
- Summary: Anthropic's "Effective context engineering for AI agents" recommends light references plus tools to fetch on demand, and its long-context tips put long documents first and ask for quotes before answering. For verifying extraction, olmOCR-Bench checks machine-checkable facts per page (a string present, order kept, no junk) instead of edit distance; OmniDocBench uses edit distance against ground truth. readwright's tests use the first style on generated fixtures. arXiv 2607.17598 ("Is Progressive Disclosure All You Need for Long-Context Agents?") is directly relevant and not yet read.
- Track: practice, testing
- Sources: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents, https://docs.anthropic.com/en/docs/long-context-window-tips, https://huggingface.co/papers/2412.07626, https://github.com/opendatalab/OmniDocBench, https://arxiv.org/html/2607.17598v1
- Magnitude: n/a (initial)
- Applied: C-20260929-1 (SKILL.md Steps 1 to 5; tests/test_rw.py)

### R-20260929-3 · 2026-09-29 · Converter versions and command lines
- Summary: calibre 9.15 (2026-09-18); `ebook-convert input output [options]` reads AZW4, CHM, comics, DJVU, DOCX, EPUB, FB2, HTML, LIT, LRF, MOBI (also AZW and AZW3), ODT, PDB, PDF, PML, RB, RTF, SNB, TCR, TXT; KFX needs the third-party KFX Input plugin. pandoc 3.12 (2026-09-29). markitdown 0.1.8 (2026-09-21): `markitdown FILE` prints Markdown, EPUB supported, optional extras per format. poppler 26.09.0 (2026-09-03) added pdftotext `-urls`; 26.05.0 added `-remove-hyphens`. MuPDF 1.27.2 (2026-02-18); the `mutool draw -F txt` flag text was not quoted and is partly unverified. LibreOffice 26.8 (2026-08-26). pandoc `-t plain`/`-t markdown` usage not re-fetched.
- Track: subject
- Sources: https://calibre-ebook.com/whats-new, https://manual.calibre-ebook.com/generated/en/ebook-convert.html, https://github.com/jgm/pandoc/releases, https://pypi.org/project/markitdown/, https://poppler.freedesktop.org/releases.html, https://mupdf.readthedocs.io/en/latest/tools/mutool-draw.html
- Magnitude: n/a (initial)
- Applied: C-20260929-1 (load_pdf, load_via_calibre, load_via_office, load_via, references/formats.md)

### R-20260929-2 · 2026-09-29 · MOBI, AZW and KFX signatures
- Summary: PDB header type `BOOK` at offset 60 and creator `MOBI` at 64 (`BOOKMOBI`); `TEXtREAd` is plain PalmDOC. Record 0 (its offset is the first entry of the record list at byte 78): compression at 0, encryption type at 12 (0 none, 1 old Mobipocket, 2 Mobipocket), `MOBI` at 16. KFX DRM: DeDRM's source checks `\xeaDRMION\xee` for encrypted blocks. The `CONT` container signature is widely cited but unverified.
- Track: subject
- Sources: https://wiki.mobileread.com/wiki/MOBI, https://raw.githubusercontent.com/noDRM/DeDRM_tools/master/DeDRM_plugin/kfxdedrm.py (read to learn the signature only)
- Magnitude: n/a (initial)
- Applied: C-20260929-1 (detect, mobi_drm)

### R-20260929-1 · 2026-09-29 · EPUB container, navigation and encryption
- Summary: EPUB 3.3 W3C Recommendation (edition of 13 January 2026); EPUB 3.4 Candidate Recommendation Snapshot of 21 July 2026, implementations invited, comments until 19 October 2026 (new core media types only). OCF: `META-INF/container.xml`, optional `encryption.xml`, `signatures.xml`, `metadata.xml`, `rights.xml`, `manifest.xml`; `mimetype` first and stored. `encryption.xml` uses XML-ENC and is required whenever fonts are obfuscated; the IDPF algorithm `http://www.idpf.org/2008/embedding` and Adobe's `http://ns.adobe.com/pdf/enc#RC` are font obfuscation, not DRM. Adobe ADEPT adds `META-INF/rights.xml`; Readium LCP puts its licence at `META-INF/license.lcpl`. Nav document: manifest `properties="nav"`; NCX (`application/x-dtbncx+xml`) is legacy. The rootfile media type `application/oebps-package+xml` was not re-fetched.
- Track: subject
- Sources: https://www.w3.org/TR/epub-33/, https://www.w3.org/TR/2026/CR-epub-34-20260721/, https://www.w3.org/news/2026/w3c-invites-implementations-of-epub-3-4-epub-reading-systems-3-4-and-epub-accessibility-1-2/, https://readium.org/lcp-specs/releases/lcp/latest, https://github.com/readium/readium-js/issues/66
- Magnitude: n/a (initial)
- Applied: C-20260929-1 (load_epub, epub_drm, nav_entries, ncx_entries)
