# Formats

What `rw.py` reads, how it finds sections, and what each external tool is for. Research behind these facts: [../RESEARCH.md](../RESEARCH.md). Back to [../SKILL.md](../SKILL.md).

## Detection

The format comes from the file's first bytes and, for zip files, from what is inside: `mimetype` (EPUB, ODF), `META-INF/container.xml` with an `.opf` (EPUB), `word/document.xml` (DOCX), `ppt/presentation.xml` (PPTX), `xl/workbook.xml` (XLSX). Other signatures: `%PDF`, `{\rtf`, the OLE2 header `D0 CF 11 E0` (legacy Office; an encrypted DOCX, XLSX or PPTX is also OLE2 and holds an `EncryptedPackage` stream), `BOOKMOBI` or `TEXtREAd` at byte 60 (MOBI, AZW, AZW3, PRC, PDB), `ITOLITLS` (LIT), `AT&TFORM` (DjVu), `ITSF` (CHM). Text files are sorted by content first (a FictionBook root, an HTML root, email headers) and by extension after that. A renamed file still reads correctly.

## Built in (standard library)

| Format | Sections | Notes |
|---|---|---|
| EPUB 2 and 3 | spine order; titles from the nav document (`properties="nav"`) or the NCX; a nav entry with a `#fragment` splits a file at that element | fonts obfuscated with the IDPF or Adobe algorithm are fine; any other entry in `META-INF/encryption.xml` is reported as DRM |
| DOCX | heading styles (by style name `heading N`, `Title`, or `outlineLvl`, so localised styles work) | tables as tab-separated rows; list paragraphs as `- ` items |
| ODT | `text:h` with `text:outline-level` | ODS: one section per sheet, repeated empty cells and rows capped; ODP: one section per slide |
| PPTX | one per slide, in presentation order | title placeholder as the title; speaker notes as a `Notes:` paragraph |
| XLSX | one per sheet | cells as TSV; shared and inline strings, booleans; raw numbers (dates stay serial numbers) |
| FB2 | every `section` with its title, nested | notes bodies (`body name="notes"`) come after the main text; binary images skipped |
| HTML, XHTML | h1 to h3 | script, style, nav, svg and forms skipped; `<title>`, `lang` and `meta name="author"` as metadata |
| TXT | lines like `CHAPTER 12`, `Part Two`, `Prologue` standing alone | otherwise parts of about 3,000 words |
| Markdown, reStructuredText | `#` headings, setext and RST underlines | fenced code kept as one block |
| RTF | CHAPTER-style paragraphs, else parts | code page from `\ansicpg`, `\'hh`, `\uN` with `\ucN`, `\info` title and author; destinations (`\*`, font and colour tables, pictures, headers, footnotes) skipped |
| CSV, TSV | 500 rows per section | delimiter sniffed (`,`, `;`, tab, pipe) |
| JSON | one per top-level key, or 50 list items | pretty-printed |
| EML, MHT | one per text part | the plain part wins over its HTML alternative; attachments listed by name, type and size, never opened |
| ZIP | toc lists members | `--member NAME` (a name, a unique suffix or the toc number); a zip with one readable member, such as `book.fb2.zip`, opens it directly |

## External tools (used when found, never installed)

| Format | Tool | Install |
|---|---|---|
| PDF | `pdftotext` from poppler (pages split on form feeds; `pdfinfo` adds metadata), else `mutool draw -F txt` from MuPDF; `mutool show FILE outline` groups pages by the outline when mutool is present | Windows `scoop install poppler` or `choco install poppler`; macOS `brew install poppler`; Debian/Ubuntu `apt install poppler-utils`. Or use the agent's Read tool with page ranges |
| MOBI, AZW, AZW3, PRC, PDB, LIT, DjVu, CHM, LRF and more | calibre `ebook-convert FILE out.epub`, then the EPUB reader | calibre-ebook.com/download; macOS `brew install --cask calibre`; Linux `apt install calibre`. KFX also needs the third-party KFX Input plugin for calibre |
| DOC, XLS, PPT | LibreOffice `soffice --headless --convert-to docx/xlsx/pptx` with a throwaway profile, then the matching reader | libreoffice.org/download. For DOC only, `antiword` works too (plain text, no headings) |
| any | `--via pandoc` (`pandoc FILE -t markdown --wrap=none`) or `--via markitdown` (`markitdown FILE`), then the Markdown reader | pandoc.org/installing; `pipx install "markitdown[all]"` |

Conversions are cached in the system temp folder (`readwright-cache`), keyed by path, size, modification time and tool, so the second command on a large MOBI or PDF is fast. `--no-cache` forces a fresh conversion. The Windows and macOS default install folders of calibre and LibreOffice are checked when the tools are not on PATH.

## DRM and safety

- EPUB: `META-INF/rights.xml` (Adobe ADEPT), `META-INF/license.lcpl` (Readium LCP) or `META-INF/sinf.xml` (Apple FairPlay) together with encrypted resources in `encryption.xml`; or any encrypted resource whose algorithm is not font obfuscation.
- MOBI family: the encryption field at offset 12 of record 0 (1 or 2 means DRM). KFX: the `DRMION` signature.
- Password-protected Office files and encrypted PDFs are reported as such.
- The message says the file is protected and that readwright does not remove DRM. There is no flag to try anyway.
- Nothing in a document is executed: XML is parsed with ElementTree (no external entities; expat refuses entity-expansion bombs), HTML with `html.parser`, and LibreOffice conversions run headless, where macros do not run.

## Caps

- One file or zip member: 512 MB (`RW_MAX_MB` changes it). A zip member's declared size is checked before it is read.
- Spreadsheets: 200,000 rows per sheet and 1,000 columns; repeated ODS rows and cells are capped too.
- External tools time out (PDF and Office 10 minutes, calibre 15).
