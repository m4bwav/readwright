# Formats

What `rw.py` reads, how it finds sections, and what each external tool is for. Research behind these facts: [../RESEARCH.md](../RESEARCH.md). Back to [../SKILL.md](../SKILL.md).

## Detection

The format comes from the file's first bytes and, for zip files, from what is inside: `mimetype` (EPUB, ODF), `META-INF/container.xml` with an `.opf` (EPUB), `word/document.xml` (DOCX), `ppt/presentation.xml` (PPTX), `xl/workbook.xml` (XLSX). Other signatures: `%PDF`, `{\rtf`, the OLE2 header `D0 CF 11 E0` (legacy Office; an encrypted DOCX, XLSX or PPTX is also OLE2 and holds an `EncryptedPackage` stream), `BOOKMOBI` or `TEXtREAd` at byte 60 (MOBI, AZW, AZW3, PRC, PDB), `CONT` followed by version 1 or 2 as two little-endian bytes (KFX), `ITOLITLS` (LIT), `AT&TFORM` (DjVu), `ITSF` (CHM). Text files are sorted by content first (a FictionBook root, an HTML root, email headers) and by extension after that. A renamed file still reads correctly.

Encoding: non-ASCII bytes that are valid UTF-8 are read as UTF-8 whatever a meta tag claims, since latin-1 never fails. A UTF-16 or UTF-32 hint still wins, because BOM-less data of those kinds can pass as UTF-8.

## Built in (standard library)

| Format | Sections | Notes |
|---|---|---|
| EPUB 2 and 3 | spine order; titles from the nav document (`properties="nav"`) or the NCX; a nav entry with a `#fragment` splits a file at that element; text with no nav entry and no heading of its own (a long chapter split across files) joins the section before it | fonts obfuscated with the IDPF or Adobe algorithm are fine; any other entry in `META-INF/encryption.xml` is reported as DRM |
| DOCX | heading styles (by style name `heading N`, `Title`, or `outlineLvl`, so localised styles work) | tables as tab-separated rows; list paragraphs as `- ` items |
| ODT | `text:h` with `text:outline-level` | ODS: one section per sheet, repeated empty cells and rows capped; ODP: one section per slide |
| PPTX | one per slide, in presentation order | title placeholder as the title; speaker notes as a `Notes:` paragraph |
| XLSX | one per sheet | cells as TSV; shared and inline strings, booleans; cells with a date or time number format as ISO dates and times (1900 and 1904 date systems), other numbers raw |
| FB2 | every `section` with its title, nested | notes bodies (`body name="notes"`) come after the main text; binary images skipped |
| HTML, XHTML | h1 to h3 | script, style, nav, svg and forms skipped; `<title>`, `lang` and `meta name="author"` as metadata |
| TXT | lines like `CHAPTER 12`, `Part Two`, `Prologue` standing alone, also inside brackets (`Chapter I.]`, the end of a Project Gutenberg illustration caption) or with the numeral glued on (`CHAPTERXXVII`); Project Gutenberg's `*** START OF` and `*** END OF` lines, so the licence is its own section | otherwise parts of about 3,000 words |
| Markdown, reStructuredText | `#` headings, setext and RST underlines; with no heading at all, CHAPTER lines as in TXT | fenced code kept as one block |
| RTF | CHAPTER-style paragraphs, else parts | code page from `\ansicpg`, `\'hh`, `\uN` with `\ucN`, `\info` title and author; destinations (`\*`, font and colour tables, pictures, headers, footnotes) skipped |
| CSV, TSV | 500 rows per section | delimiter sniffed (`,`, `;`, tab, pipe) |
| JSON | one per top-level key, or 50 list items | pretty-printed |
| EML, MHT | one per text part | the plain part wins over its HTML alternative; attachments listed by name, type and size, never opened |
| ZIP | toc lists members | `--member NAME` (a name, a unique suffix or the toc number); a zip with one readable member, such as `book.fb2.zip`, opens it directly |

Every format then gets one more pass: a section of more than 12,000 words, or one with no title, that holds headings or CHAPTER lines is split at them. Converters lose outlines this way: calibre's FB2 output writes chapter titles as plain paragraphs, and its PDB round trip keeps three table-of-contents entries for a whole novel. Well-structured files are not changed by it.

HTML and EPUB lists keep each item's depth when nested; other formats keep flat lists.

## External tools (used when found, never installed)

| Format | Tool | Install |
|---|---|---|
| PDF | `pdftotext` from poppler (pages split on form feeds; `pdfinfo` adds metadata), else `mutool draw -F txt` from MuPDF; `mutool show FILE outline` groups pages by the outline, nested as in the PDF, when mutool is present | Windows `winget install oschwartz10612.Poppler` and `winget install ArtifexSoftware.mutool`, or scoop or choco; macOS `brew install poppler mupdf-tools`; Debian/Ubuntu `apt install poppler-utils mupdf-tools`. Or use the agent's Read tool with page ranges |
| MOBI, AZW, AZW3, PRC, PDB, LIT, KFX, DjVu, CHM, LRF and more | calibre `ebook-convert FILE out.epub`, then the EPUB reader | Windows `winget install calibre.calibre`; macOS `brew install --cask calibre`; Linux `apt install calibre`. KFX also needs the third-party KFX Input plugin (`calibre-customize -a "KFX Input.zip"`, from calibre's plugin index) |
| DOC, XLS, PPT | LibreOffice `soffice --headless --convert-to docx/xlsx/pptx` with a throwaway profile, then the matching reader | Windows `winget install TheDocumentFoundation.LibreOffice`; libreoffice.org/download. For DOC only, `antiword` works too (plain text, no headings; it refuses very short documents) |
| any | `--via pandoc` (`pandoc FILE -t markdown --wrap=none -o TMP`) or `--via markitdown` (`markitdown FILE -o TMP`), then the Markdown reader | Windows `winget install JohnMacFarlane.Pandoc`; pandoc.org/installing; `pip install --user "markitdown[all]"` or `pipx install "markitdown[all]"` |

What `--via` reads, checked on real files: pandoc reads EPUB, DOCX, ODT, FB2 and RTF, and refuses PDF, DOC, XLS and PPT. markitdown with its extras reads EPUB, DOCX, PDF, XLSX and XLS; it refuses ODT and PPT, and returns RTF unchanged, which readwright reports as an error. markitdown on a PDF is slow (26 seconds for a 371-page novel, against under a second for pdftotext). Neither is needed for a format readwright reads itself.

Conversions are cached in the system temp folder (`readwright-cache`), keyed by path, size, modification time and tool, so the second command on a large MOBI or PDF is fast (2 seconds, then 0.23). `--no-cache` forces a fresh conversion.

Tools are looked for on PATH, then in their usual install folders: `Calibre2` and `LibreOffice\program` under Program Files, `%LOCALAPPDATA%\Pandoc`, winget's poppler package under `%LOCALAPPDATA%\Microsoft\WinGet\Packages`, winget's `Links` folders, Git for Windows' `mingw64\bin` (pdftotext, pdfinfo, antiword), scoop shims, Chocolatey's `bin`, pip's user scripts folder (markitdown), `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and the macOS application bundles. On Windows the PATH stored in the registry is searched too, since a tool installed after the agent's shell started is on that PATH and not the shell's. Two environment variables change this: `RW_HIDE_TOOLS=soffice,pdftotext` treats the named tools as absent (to force antiword for DOC, or mutool for PDF), and `RW_PATH_ONLY=1` looks on PATH only.

`info` also notes a PDF text layer that looks scrambled (5 or more lowercase runs of 18+ letters, at 0.5 or more per 1,000 words). `page FILE N-M` renders PDF pages to PNG files. In a fixed-layout EPUB, a smaller type size that recurs through the book is read from the CSS as captions: they move after the body paragraph, marked `[caption] `.

A PDF or EPUB with fewer than 10 words a page (an EPUB counts sections) gets a `no text layer` note from `info`, `toc` and `read`: it is page images. The note names a same-name copy in another format in the same folder, ocrmypdf when installed, and a `rw.py page` line that renders the first pages as pictures. On 83 real PDFs and EPUBs, the 6 scans had 0 words a page and the thinnest text book 132, so the note fired on exactly the 6. When an OCR engine is available the note names `rw.py ocr FILE` first: it renders each page with mutool (or pdftoppm) at 200 dpi, runs Windows' built-in OCR through Windows PowerShell 5.1 (`Windows.Media.Ocr`, no install) or tesseract, and keeps one text per page, form-feed separated, in `~/.readwright/ocr/` (or `READWRIGHT_OCR_DIR`), keyed by the file's path, size and modification time. `load_pdf` reads that text in place of the empty layer. Paragraphs are split where the gap between OCR lines is over 0.9 of a line height. `RW_HIDE_TOOLS=windows-ocr,tesseract` hides the engines. An EPUB whose spine shows page images (`<img>`, SVG `<image>`, or an image as a spine item) is OCR'd the same way from those images, without rendering (0.11.0); its text replaces the EPUB's sections, split at ALL-CAPS headings when it is one long run, else one section a page.

A section over 12,000 words with no headings (calibre's DjVu output, plain text, OCR) is split at ALL-CAPS headings, inline ones too: a caps phrase opening many pages is a running head (the book's title, dropped, or a chapter, a level-1 section), other caps runs of 1-8 words after a sentence end are topic headings (level 2). Fewer than 3 headings: unchanged.

PDF lines as paragraphs: when at least half the characters sit on lines over 200 characters, no page could print them, so each line on a page holding such a line is a paragraph. Marked code blocks and pages of only short lines stay as they were.

When a tool fails, the message is its last exception line, since a Python traceback's first lines say nothing. pandoc and markitdown run with `-o FILE`, because console output uses the console code page on Windows.

PDF page-foot notes: a `N. text` paragraph at the foot, with a call to N in the body above, moves after the interrupted paragraph as `[note N: text]`, and the sentence, including a word split by a hyphen, rejoins. Numbered lists have no call and stay. A note carried over onto the next page keeps its tail there. When most characters sit on lines over 200 characters, each line of a page holding one is read as a paragraph; paragraph numbers from before 0.42.0 no longer match.

PDF code blocks: when the text hints at code, a second `pdftotext -layout` pass (cached) finds runs of 3+ code-shaped lines and puts them back, with indentation, as `pre` paragraphs in place of their flattened words. Tables, definition lists and sidebars are not handled.

## DRM and safety

- EPUB: `META-INF/rights.xml` (Adobe ADEPT), `META-INF/license.lcpl` (Readium LCP) or `META-INF/sinf.xml` (Apple FairPlay) together with encrypted resources in `encryption.xml`; or any encrypted resource whose algorithm is not font obfuscation.
- MOBI family: the encryption field at offset 12 of record 0 (1 or 2 means DRM), checked before calibre is called. KFX: the `DRMION` signature.
- Password-protected Office files and encrypted PDFs are reported as such.
- The message says the file is protected and that readwright does not remove DRM. There is no flag to try anyway.
- Nothing in a document is executed: XML is parsed with ElementTree (no external entities; expat refuses entity-expansion bombs), HTML with `html.parser`, and LibreOffice conversions run headless, where macros do not run.

## Caps

- One file or zip member: 512 MB (`RW_MAX_MB` changes it). A zip member's declared size is checked before it is read.
- Spreadsheets: 200,000 rows per sheet and 1,000 columns; repeated ODS rows and cells are capped too.
- External tools time out (PDF and Office 10 minutes, calibre 15).

## Heading and furniture rules

Each is code in rw.py with a test; LEARNINGS-ARCHIVE.md has the book that prompted it.

- Hyphens and apostrophes: grep treats U+2010 and the typed hyphen, and apostrophe forms, as one; en and em dashes stay distinct (L-057).
- Repeats at a book's end under half the first copy's words are titled as notes (L-058). A cap never ends on a bare section title (L-059).
- LaTeX outlines give `#nameddest=`; pages come from `pdfinfo -dests` (L-061). Fixed-layout viewport meta matches in either attribute order (L-062).
- `--section pN` maps through `pageN` ids; check `printed N` in the header when citing (L-063).
- Caps runs ending in a comma, or one word used in sentences, are not headings; `--headings` falls back to rules of dots (L-064). Whole-caps lines (3+, 2 to 10 words, each before a 20+ word paragraph) are headings (L-068).
- A div or p whose class names code becomes one pre block for `--skip-code` (L-065).
- Five or more short numbered lines count as headings (L-066); bare-number heads (`1 Variable Tempo`) count across the whole selection when they run 1, 2, 3 (L-089).
- Two img tags with one src give one picture marker, never a formula (L-067).
- A side-margin folio is removed only when one shift holds on a quarter of pages, twice the runner-up (L-069).
- A short-line block naming itself contents, or losing three or more cuts, keeps none of its lines (L-070). A caps run closing a paragraph of 150 words or fewer stays in the caption (L-071).
- Three or more one-link blocks at a chapter start become `[chapter contents: N headings]` (L-072). Several outline entries on one page split a paragraph at an exact-case unnumbered title after a sentence end (L-073).
