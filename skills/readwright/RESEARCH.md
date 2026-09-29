# Research: readwright

Findings that back [SKILL.md](SKILL.md), [references/formats.md](references/formats.md) and `scripts/rw.py`. Changes they caused are logged in [CHANGELOG.md](CHANGELOG.md); procedural lessons live in [LEARNINGS.md](LEARNINGS.md); test runs and their evidence in [TESTS.md](TESTS.md); schedule and state in `evergreen.json`. Protocol: [MAINTENANCE.md](MAINTENANCE.md).

Topic: Reading text from ebook and document formats for AI agents: EPUB (W3C spec), MOBI/AZW/KFX, FB2, OOXML, ODF, RTF, HTML, EML, PDF text extraction; the converters readwright shells out to (calibre, poppler, MuPDF, LibreOffice, pandoc, markitdown); DRM markers; agent tools for sectioned document reading. Tier `moderate`. Last refresh 2026-09-29; next due 2026-10-29.

## Current understanding

- **Outline first, then sections, is the right shape for agents.** Anthropic's context-engineering guidance recommends just-in-time retrieval: keep light references (here, a toc with word counts) and let the agent fetch what it needs, over loading whole documents. Whole-book dumps (`epr -d`, `pandoc -t plain`) cost 150k to 300k tokens for a novel. Confident (R-20260929-4).
- **EPUB is stable underneath.** EPUB 3.3 is a W3C Recommendation (the edition dated 13 January 2026); EPUB 3.4 is a Candidate Recommendation Snapshot (21 July 2026, comments until 19 October 2026) whose changes are media types (JPEG XL, AVIF, Opus), not the container. `META-INF/container.xml` names the package document; `mimetype` is the first, stored entry; the nav document has `properties="nav"`; the NCX is a legacy feature kept for EPUB 2 readers, and many books in the wild still rely on it (the smoke-test book does). Confident (R-20260929-1).
- **DRM markers are well known and cheap to check.** EPUB: `encryption.xml` entries other than font obfuscation (`http://www.idpf.org/2008/embedding`, `http://ns.adobe.com/pdf/enc#RC`), plus `rights.xml` (Adobe ADEPT) or `license.lcpl` (Readium LCP). MOBI: record 0 offset 12, encryption type 1 or 2. KFX: the `\xeaDRMION\xee` signature. Treating font obfuscation as DRM is a known bug in other tools. Confident for EPUB and MOBI; the KFX `CONT` container signature is unverified (R-20260929-1, R-20260929-2).
- **Converters are current and maintained** (checked 2026-09-29): calibre 9.15 (2026-09-18), pandoc 3.12 (2026-09-29), markitdown 0.1.8 (2026-09-21, reads EPUB), poppler 26.09.0 (2026-09-03), MuPDF 1.27.2 (2026-02-18), LibreOffice 26.8 (2026-08-26). calibre reads KFX only with the third-party KFX Input plugin. Confident (R-20260929-3).
- **Tooling landscape.** Whole-file converters dominate (markitdown, docling, pandoc). Section-aware readers exist mostly as EPUB-only MCP servers (onebirdrocks/ebook-mcp, kajuberdut/epub-mcp, joshstrange/bookorbit-mcp) and an epub skill. None found covers EPUB, Office, ODF, FB2, RTF and email behind one outline-read-search interface with no dependencies, which is readwright's niche. epr (MIT) and its successor epy (GPL-3.0) are dormant human readers. Fairly confident; the tooling track should re-check each refresh (R-20260929-5).
- **The formats readwright parses itself are frozen or slow**: RTF 1.9.1 (2008, no further updates planned), FB2 2.x, ODF 1.4 (OASIS Standard 2025-12-03), OOXML. Their risk is odd files in the wild, not spec change. Confident (R-20260929-6).

## Open questions

- KFX container signature (`CONT` at byte 0) and whether calibre's KFX Input plugin still works on calibre 9.x.
- `mutool show FILE outline` output format across MuPDF versions: `pdf_outline` parses it best-effort and is untested on a real outline (no mutool on the development machine).
- Whether pdftotext's new `-remove-hyphens` (poppler 26.05) should be used by default for PDFs of prose.
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

Newest first. One entry per material finding; a quiet refresh gets one entry saying so. `Track` is subject, tooling, practice, or testing. All entries below came from one research pass on 2026-09-29 (about 30 searches and fetches, run by a research subagent) plus the author's reading of the specs while writing the parsers.

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
