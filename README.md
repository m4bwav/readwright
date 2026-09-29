# readwright

An agent skill and a small command-line tool for reading text out of ebooks and documents a section at a time. The agent asks for an outline first, then only the chapters it needs, then searches, and the whole book never lands in its context.

A novel runs to 150,000 to 300,000 tokens. Converters that turn a book into text in one go are built for people or pipelines, so an agent that uses them loads the entire book to answer a question about two chapters. readwright answers the same question with a table of contents, two sections and a search.

## What it reads

With nothing but Python 3.10 or newer: EPUB 2 and 3, FB2, DOCX, ODT, ODS, ODP, PPTX, XLSX, HTML and XHTML, plain text, Markdown, reStructuredText, RTF, CSV, TSV, JSON, EML, and zip archives of any of these.

With an external tool, when it is installed (readwright never installs anything):

- PDF: `pdftotext` from poppler, or `mutool` from MuPDF. Agents whose Read tool takes PDF page ranges can often skip this.
- MOBI, AZW, AZW3, PRC, PDB, LIT, DjVu, CHM and other ebook formats: calibre's `ebook-convert`.
- Legacy DOC, XLS and PPT: LibreOffice (`soffice`), or `antiword` for DOC.
- Anything pandoc or markitdown reads, through `--via pandoc` or `--via markitdown`.

Formats are detected from the file's bytes, not its extension. DRM-protected books (Adobe ADEPT, Readium LCP, Apple FairPlay, Mobipocket, Kindle KFX) and password-protected Office files are reported as such and left alone. Nothing in a document is executed. [skills/readwright/references/formats.md](skills/readwright/references/formats.md) has the details per format.

## Commands

```
python skills/readwright/scripts/rw.py info  book.epub
python skills/readwright/scripts/rw.py toc   book.epub
python skills/readwright/scripts/rw.py read  book.epub --section 43-44
python skills/readwright/scripts/rw.py read  book.epub --title "anwurat" --max-chars 2000
python skills/readwright/scripts/rw.py grep  book.epub "Swazond" -C 1 --max 3
python skills/readwright/scripts/rw.py dump  book.epub --out scratch/book.txt
python skills/readwright/scripts/rw.py formats
```

- `info`: format, size, title, author, language, section count, words and approximate tokens.
- `toc`: numbered sections with titles, word counts and ids, indented by level. EPUB titles come from the book's own navigation, DOCX and ODT titles from heading styles, HTML titles from h1 to h3, and text files from their headings or CHAPTER lines.
- `read`: the chosen sections (`--section N`, `N-M`, `N,M`, or `--title REGEX`), each under a header line with its position in the book. Output stops at `--max-chars` (40,000 by default) and says how to continue. With no selector and a text over the limit, `read` refuses, exits with code 2 and prints the table of contents instead.
- `grep`: matching paragraphs with section and paragraph numbers, trimmed around the match, with `-C` paragraphs of context, `-i`, `-F`, `--max` and `--count`.
- `dump`: the whole text to a file with section markers, so an agent can use its own search tools on it. Dump writes to stdout only for texts under 40,000 characters.
- `formats`: what is built in and which external tools this machine has.

`info`, `toc`, `grep` and `formats` also take `--json`. Output is UTF-8 with LF line endings on every platform, including Windows consoles. `scripts/rw.sh` and `scripts/rw.ps1` are launchers for macOS/Linux and Windows. Conversions through external tools are cached in the system temp folder, so a second command on the same MOBI or PDF is fast.

On a 1.3 MB EPUB novel (80 sections, 202,000 words) each command takes about 0.3 seconds on a 2026 Windows desktop.

## The skill

[skills/readwright/SKILL.md](skills/readwright/SKILL.md) tells the agent when to use the tool and in what order: size the file up, read the outline, read only the needed sections, search for names, dump long books to a scratch file, and quote briefly. It triggers on requests to read, quote, summarise, search or extract text from those formats ("read chapter 14 of this book", "what does this document say about"). It stays out of images, notebooks, PDFs the agent reads well already, and writing Office files.

## Install

Claude Code, from a clone:

```
git clone https://github.com/m4bwav/readwright
claude plugin marketplace add ./readwright
claude plugin install readwright@readwright
```

Other agents that read Agent Skills (`SKILL.md`): link or copy `skills/readwright` into their skills folder (`~/.claude/skills/`, `~/.agents/skills/`). The tool alone needs only Python: `python skills/readwright/scripts/rw.py --help`.

## Tests

`python tests/test_rw.py` runs the unit tests. They build every fixture (EPUB, DOCX, ODT, FB2, RTF, HTML, EML, zip and more) from invented text at test time, so no book or document is stored in the repository. The eval suite in `evals/` (trigger prompts, decoys, and cases proven by the `rw.py` calls in the trace) runs with `claude plugin eval`; the latest results are in [TESTS.md](skills/readwright/TESTS.md).

## Credits

[epr](https://github.com/wustho/epr) by wustho (MIT) is a good terminal EPUB reader for people, and `epr -d` dumps a whole book as text. That dump, sent into an agent's context, is the problem readwright was written to avoid. Its successor is [epy](https://github.com/wustho/epy). readwright shares no code with either.

## Evergreen

The skill keeps its research current on a schedule (tier moderate, every 30 days to start): the EPUB specs, the converters it calls (calibre, poppler, MuPDF, LibreOffice, pandoc, markitdown), DRM markers and other tools for agents are re-checked from primary sources. Every change is logged with its reason in [CHANGELOG.md](skills/readwright/CHANGELOG.md). The research is in [RESEARCH.md](skills/readwright/RESEARCH.md) and the lessons from real use in [LEARNINGS.md](skills/readwright/LEARNINGS.md).

## Licence

MIT, see [LICENSE](LICENSE). Semantic versions; tags `vX.Y.Z`.
