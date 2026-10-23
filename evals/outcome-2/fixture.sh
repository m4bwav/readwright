#!/usr/bin/env bash
# Seeds an eval workspace with fixture/harbour.epub, a scanned book: three pages that are only pictures, no text
# layer. Beside it is fixture/harbour.docx, the same invented book as text, about 6,000 words, where the harbour
# master's cat is named once (Pellwick). Both are written with ZIP_DEFLATED so plain Grep cannot read them.
set -e
mkdir -p fixture
if python3 -c "import sys" >/dev/null 2>&1; then py=python3; else py=python; fi
"$py" - <<'PY'
import base64, zipfile
gif = base64.b64decode("R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==")
pages = [f"<html xmlns='http://www.w3.org/1999/xhtml'><body><img src='p{i}.gif' alt=''/></body></html>" for i in (1, 2, 3)]
opf = ("<package xmlns='http://www.idpf.org/2007/opf' version='3.0'><metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
       "<dc:title>Harbour Days</dc:title><dc:language>en</dc:language></metadata><manifest>"
       + "".join(f"<item id='p{i}' href='p{i}.xhtml' media-type='application/xhtml+xml'/>"
                 f"<item id='g{i}' href='p{i}.gif' media-type='image/gif'/>" for i in (1, 2, 3))
       + "</manifest><spine>" + "".join(f"<itemref idref='p{i}'/>" for i in (1, 2, 3)) + "</spine></package>")
with zipfile.ZipFile("fixture/harbour.epub", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
    z.writestr("META-INF/container.xml", "<container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
               "<rootfiles><rootfile full-path='content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
    z.writestr("content.opf", opf)
    for i, x in enumerate(pages, 1):
        z.writestr(f"p{i}.xhtml", x)
        z.writestr(f"p{i}.gif", gif)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
words = "boats came in on the evening tide and the harbour master wrote each one in the ledger by lamplight".split()
def filler(n, seed):
    return " ".join(words[(i * 5 + seed) % len(words)] for i in range(n)) + "."
def p(text, style=None):
    ppr = f"<w:pPr><w:pStyle w:val='{style}'/></w:pPr>" if style else ""
    return f"<w:p>{ppr}<w:r><w:t xml:space='preserve'>{text}</w:t></w:r></w:p>"
body = ""
for c, title in enumerate(["The Quay", "Ledgers", "Winter Moorings"], 1):
    body += p(f"Chapter {c}: {title}", "Heading1")
    for k in range(20):
        body += p(filler(100, c * 30 + k))
        if c == 2 and k == 11:
            body += p("The harbour master's cat, a grey tom called Pellwick, slept on the ledger every night.")
doc = f"<?xml version='1.0' encoding='UTF-8'?><w:document xmlns:w='{W}'><w:body>{body}</w:body></w:document>"
styles = f"<?xml version='1.0'?><w:styles xmlns:w='{W}'><w:style w:styleId='Heading1'><w:name w:val='heading 1'/></w:style></w:styles>"
with zipfile.ZipFile("fixture/harbour.docx", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
    z.writestr("word/document.xml", doc)
    z.writestr("word/styles.xml", styles)
PY
