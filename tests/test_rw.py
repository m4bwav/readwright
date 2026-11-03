#!/usr/bin/env python3
"""Tests for skills/readwright/scripts/rw.py. Standard library only: python tests/test_rw.py

Every fixture is built here at test time from invented text; no real book or document is committed.
"""
import contextlib
import io
import json
import os
import shutil
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "readwright" / "scripts" / "rw.py"
sys.path.insert(0, str(SCRIPT.parent))
import rw  # noqa: E402

BS = chr(92)   # a backslash, kept out of string literals on purpose


def lorem(n, word="lorem"):
    base = [word, "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit"]
    return " ".join(base[i % len(base)] for i in range(n))


# ---------------------------------------------------------------- fixture builders

def make_epub(path, nav=True, ncx=False, encryption=None, extra=None):
    ch1 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><head><title>c1</title>"
           "<style>p{color:red}</style></head><body><h1>Chapter One</h1><p>The lighthouse keeper counted the gulls.</p>"
           "<p>Brannoch walked to the pier at dawn.</p><script>alert('no')</script></body></html>")
    ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
           "<h1 id='c2'>Chapter Two</h1><p>Rain on the slate roofs of Quillmere.</p><p>" + lorem(40) + "</p>"
           "<h1 id='c3'>Chapter Three</h1><p>Brannoch found the ledger under the stairs.</p>"
           "<p>The ledger listed every ship since 1802.</p></body></html>")
    navdoc = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml' "
              "xmlns:epub='http://www.idpf.org/2007/ops'><body><nav epub:type='toc'><ol>"
              "<li><a href='text/ch1.xhtml'>Chapter One</a></li>"
              "<li><a href='text/ch2.xhtml#c2'>Chapter Two</a><ol><li><a href='text/ch2.xhtml#c3'>Chapter Three</a></li></ol></li>"
              "</ol></nav><nav epub:type='landmarks'><ol><li><a href='text/ch1.xhtml'>Start</a></li></ol></nav></body></html>")
    ncxdoc = ("<?xml version='1.0'?><ncx xmlns='http://www.daisy.org/z3986/2005/ncx/' version='2005-1'><navMap>"
              "<navPoint id='n1'><navLabel><text>First Light</text></navLabel><content src='text/ch1.xhtml'/></navPoint>"
              "<navPoint id='n2'><navLabel><text>Second Tide</text></navLabel><content src='text/ch2.xhtml#c2'/>"
              "<navPoint id='n3'><navLabel><text>Third Bell</text></navLabel><content src='text/ch2.xhtml#c3'/></navPoint>"
              "</navPoint></navMap></ncx>")
    items = ["<item id='c1' href='text/ch1.xhtml' media-type='application/xhtml+xml'/>",
             "<item id='c2' href='text/ch2.xhtml' media-type='application/xhtml+xml'/>"]
    if nav:
        items.append("<item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/>")
    if ncx:
        items.append("<item id='ncx' href='toc.ncx' media-type='application/x-dtbncx+xml'/>")
    opf = ("<?xml version='1.0' encoding='utf-8'?><package xmlns='http://www.idpf.org/2007/opf' version='3.0'>"
           "<metadata xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title>The Quillmere Ledger</dc:title>"
           "<dc:creator>A. Nonymous</dc:creator><dc:language>en</dc:language></metadata>"
           "<manifest>" + "".join(items) + "</manifest>"
           "<spine" + (" toc='ncx'" if ncx else "") + "><itemref idref='c1'/><itemref idref='c2'/></spine></package>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                   "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                   "full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/text/ch1.xhtml", ch1)
        z.writestr("OEBPS/text/ch2.xhtml", ch2)
        if nav:
            z.writestr("OEBPS/nav.xhtml", navdoc)
        if ncx:
            z.writestr("OEBPS/toc.ncx", ncxdoc)
        if encryption:
            z.writestr("META-INF/encryption.xml", encryption)
        for name, data in (extra or {}).items():
            z.writestr(name, data)


def enc_xml(alg, uri):
    return ("<encryption xmlns='urn:oasis:names:tc:opendocument:xmlns:container' "
            "xmlns:enc='http://www.w3.org/2001/04/xmlenc#'><enc:EncryptedData>"
            f"<enc:EncryptionMethod Algorithm='{alg}'/><enc:CipherData><enc:CipherReference URI='{uri}'/>"
            "</enc:CipherData></enc:EncryptedData></encryption>")


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(path):
    def p(text, style=None):
        ppr = f"<w:pPr><w:pStyle w:val='{style}'/></w:pPr>" if style else ""
        return f"<w:p>{ppr}<w:r><w:t xml:space='preserve'>{text}</w:t></w:r></w:p>"
    body = (p("Field Notes", "Title") + p("Intro text before any heading.") + p("Harbour", "Heading1")
            + p("The harbour master logged twelve arrivals.") + p("Tides", "Heading2") + p("Spring tides reached the wall.")
            + "<w:tbl><w:tr><w:tc>" + p("Ship") + "</w:tc><w:tc>" + p("Tons") + "</w:tc></w:tr>"
            + "<w:tr><w:tc>" + p("Marigold") + "</w:tc><w:tc>" + p("310") + "</w:tc></w:tr></w:tbl>"
            + p("Weather", "Kop1") + p("Fog every morning in March."))
    doc = f"<?xml version='1.0' encoding='UTF-8'?><w:document xmlns:w='{W_NS}'><w:body>{body}</w:body></w:document>"
    styles = (f"<?xml version='1.0'?><w:styles xmlns:w='{W_NS}'>"
              "<w:style w:styleId='Heading1'><w:name w:val='heading 1'/></w:style>"
              "<w:style w:styleId='Heading2'><w:name w:val='heading 2'/></w:style>"
              "<w:style w:styleId='Title'><w:name w:val='Title'/></w:style>"
              "<w:style w:styleId='Kop1'><w:name w:val='Kop 1'/><w:pPr><w:outlineLvl w:val='0'/></w:pPr></w:style></w:styles>")
    core = ("<?xml version='1.0'?><cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
            "xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title>Field Notes</dc:title><dc:creator>B. Writer</dc:creator></cp:coreProperties>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)
        z.writestr("docProps/core.xml", core)


def make_odt(path):
    content = ("<?xml version='1.0' encoding='UTF-8'?><office:document-content "
               "xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' "
               "xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0'><office:body><office:text>"
               "<text:h text:outline-level='1'>Orchard</text:h><text:p>Apples<text:s text:c='2'/>ripen late here.</text:p>"
               "<text:list><text:list-item><text:p>Bramley</text:p></text:list-item><text:list-item><text:p>Cox</text:p></text:list-item></text:list>"
               "<text:h text:outline-level='1'>Cellar</text:h><text:p>Cider sleeps in oak.</text:p>"
               "</office:text></office:body></office:document-content>")
    meta = ("<?xml version='1.0'?><office:document-meta xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' "
            "xmlns:dc='http://purl.org/dc/elements/1.1/'><office:meta><dc:title>Orchard Diary</dc:title>"
            "<dc:language>en-GB</dc:language></office:meta></office:document-meta>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", content)
        z.writestr("meta.xml", meta)
        z.writestr("META-INF/manifest.xml", "<manifest/>")


def make_ods(path):
    content = ("<?xml version='1.0'?><office:document-content xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0' "
               "xmlns:table='urn:oasis:names:tc:opendocument:xmlns:table:1.0' xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0'>"
               "<office:body><office:spreadsheet><table:table table:name='Stock'>"
               "<table:table-row><table:table-cell><text:p>item</text:p></table:table-cell><table:table-cell><text:p>qty</text:p></table:table-cell></table:table-row>"
               "<table:table-row><table:table-cell><text:p>rope</text:p></table:table-cell><table:table-cell><text:p>4</text:p></table:table-cell>"
               "<table:table-cell table:number-columns-repeated='16000'/></table:table-row>"
               "<table:table-row table:number-rows-repeated='1048000'><table:table-cell table:number-columns-repeated='1024'/></table:table-row>"
               "</table:table></office:spreadsheet></office:body></office:document-content>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", content)
        z.writestr("META-INF/manifest.xml", "<manifest/>")


def make_pptx(path):
    P = "http://schemas.openxmlformats.org/presentationml/2006/main"
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    def slide(title, body):
        return (f"<p:sld xmlns:p='{P}' xmlns:a='{A}'><p:cSld><p:spTree>"
                f"<p:sp><p:nvSpPr><p:cNvPr id='1' name='t'/><p:cNvSpPr/><p:nvPr><p:ph type='title'/></p:nvPr></p:nvSpPr>"
                f"<p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>"
                f"<p:sp><p:nvSpPr><p:cNvPr id='2' name='b'/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
                f"<p:txBody><a:p><a:r><a:t>{body}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", f"<p:presentation xmlns:p='{P}' xmlns:r='{R}'><p:sldIdLst>"
                   "<p:sldId id='256' r:id='rId2'/><p:sldId id='257' r:id='rId3'/></p:sldIdLst></p:presentation>")
        z.writestr("ppt/_rels/presentation.xml.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                   "<Relationship Id='rId3' Target='slides/slide2.xml'/><Relationship Id='rId2' Target='slides/slide1.xml'/></Relationships>")
        z.writestr("ppt/slides/slide1.xml", slide("Quarterly Plan", "Hire two keepers"))
        z.writestr("ppt/slides/slide2.xml", slide("Budget", "Paint the tower"))
        z.writestr("ppt/slides/_rels/slide2.xml.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                   "<Relationship Id='rId1' Target='../notesSlides/notesSlide1.xml'/></Relationships>")
        z.writestr("ppt/notesSlides/notesSlide1.xml", f"<p:notes xmlns:p='{P}' xmlns:a='{A}'><p:cSld><p:spTree><p:sp>"
                   "<p:nvSpPr><p:cNvPr id='1' name='n'/><p:cNvSpPr/><p:nvPr><p:ph type='body'/></p:nvPr></p:nvSpPr>"
                   "<p:txBody><a:p><a:r><a:t>Ask about white paint</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>")


def make_xlsx(path):
    S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", f"<workbook xmlns='{S}' xmlns:r='{R}'><sheets><sheet name='Tides' sheetId='1' r:id='rId1'/></sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                   "<Relationship Id='rId1' Target='worksheets/sheet1.xml'/></Relationships>")
        z.writestr("xl/sharedStrings.xml", f"<sst xmlns='{S}'><si><t>date</t></si><si><t>height</t></si><si><r><t>high </t></r><r><t>water</t></r></si></sst>")
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet xmlns='{S}'><sheetData>"
                   "<row r='1'><c r='A1' t='s'><v>0</v></c><c r='B1' t='s'><v>1</v></c></row>"
                   "<row r='2'><c r='A2'><v>45000</v></c><c r='C2' t='s'><v>2</v></c></row>"
                   "<row r='3'><c r='A3' t='inlineStr'><is><t>note</t></is></c><c r='B3' t='b'><v>1</v></c></row>"
                   "</sheetData></worksheet>")


def make_fb2(path):
    fb2 = ("<?xml version='1.0' encoding='utf-8'?><FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'>"
           "<description><title-info><author><first-name>Ivan</first-name><last-name>Testov</last-name></author>"
           "<book-title>Snow Station</book-title><lang>ru</lang></title-info></description>"
           "<body><title><p>Snow Station</p></title>"
           "<section><title><p>Part One</p></title>"
           "<section><title><p>Arrival</p></title><p>The train stopped at Zimovka.</p><p>Снег шёл всю ночь.</p></section>"
           "<section><title><p>Departure</p></title><p>Nobody waved.</p><poem><stanza><v>A line of verse</v></stanza></poem></section>"
           "</section></body>"
           "<body name='notes'><section id='n1'><title><p>1</p></title><p>A footnote.</p></section></body>"
           "<binary id='x' content-type='image/png'>AAAA</binary></FictionBook>")
    Path(path).write_text(fb2, encoding="utf-8")


def make_rtf(path):
    rtf = ("{|rtf1|ansi|ansicpg1252|deff0{|fonttbl{|f0 Times;}}{|colortbl;|red0|green0|blue0;}"
           "{|info{|title Tide Tables}{|author C. Keeper}}{|*|generator Hand 1.0;}"
           "|pard Caf|'e9 at the pier|par "
           "Long dash|u8212? here|par "
           "{|b bold} and {|i italic}|par "
           "CHAPTER TWO|par "
           "Braces |{ok|} done.|par}")
    Path(path).write_bytes(rtf.replace("|", BS).encode("latin-1"))


def make_html(path):
    Path(path).write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>Lamp Guide</title>"
        "<meta name='author' content='D. Lamplighter'><script>var secret = 'SCRIPTTEXT';</script>"
        "<style>.x{}</style></head><body><nav>Home | About</nav><h1>Lamps</h1><p>Oil lamps need care.</p>"
        "<h2>Wicks</h2><p>Trim the <b>wick</b> daily.</p><ul><li>Cotton</li><li>Linen</li></ul>"
        "<table><tr><th>Part</th><th>Cost</th></tr><tr><td><p>Glass</p></td><td>3</td></tr></table>"
        "<h2>Fuel</h2><p>Paraffin &amp; kerosene.</p></body></html>", encoding="utf-8")


def make_eml(path):
    from email.message import EmailMessage
    m = EmailMessage()
    m["From"] = "keeper@example.org"
    m["To"] = "office@example.org"
    m["Subject"] = "Lamp report"
    m["Date"] = "Mon, 28 Sep 2026 10:00:00 +0000"
    m.set_content("The north lamp is out.\n\nSend two wicks.\n")
    m.add_alternative("<p>The north lamp is <b>out</b>.</p>", subtype="html")
    m.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="invoice.pdf")
    Path(path).write_bytes(bytes(m))


def make_pdf(path, pages=("Hello from page one", "Second page text")):
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        if isinstance(text, str):
            stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        else:   # [(x, line), ...] top down, 14 points apart
            stream = " ".join(f"BT /F1 12 Tf {x} {720 - 14 * k} Td ({t}) Tj ET" for k, (x, t) in enumerate(text))
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(bytes(out))


def make_mobi(path, encryption=0):
    head = bytearray(78)
    head[0:8] = b"Test\x00\x00\x00\x00"
    head[60:68] = b"BOOKMOBI"
    head[76:78] = (1).to_bytes(2, "big")
    rec_list = (86).to_bytes(4, "big") + b"\x00\x00\x00\x00"
    rec0 = bytearray(32)
    rec0[0:2] = (2).to_bytes(2, "big")
    rec0[12:14] = encryption.to_bytes(2, "big")
    rec0[16:20] = b"MOBI"
    Path(path).write_bytes(bytes(head) + rec_list + bytes(rec0))


NUMBERS = ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE"]


def make_novel(path):
    """An invented novel shaped like real ebooks: one file per chapter with a nav entry each, chapter FIVE split
    across two files (the second has no nav entry and no heading, as converters leave long chapters), chapter
    TWELVE's title page and body as separate nav entries (L-001), and chapter ELEVEN titled 'WEST GATE' in the nav
    while its heading reads WESTGATE. Chapter NINE holds the marker 'the Quillmere lamp'."""
    files, nav = [], []

    def xhtml(body):
        return ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><head><title>x</title>"
                f"</head><body>{body}</body></html>")

    for i, n in enumerate(NUMBERS, 1):
        paras = "".join(f"<p>{lorem(60, 'keeper')} {n.lower()} paragraph {k}.</p>" for k in range(6))
        if n == "NINE":
            paras += "<p>That night the Quillmere lamp burned green.</p>"
        head = f"<h2 id='c{i}'>CHAPTER {n}</h2>" if n != "ELEVEN" else f"<h2 id='c{i}'>CHAPTER ELEVEN: WESTGATE</h2>"
        if n == "TWELVE":
            files.append((f"ch{i}.xhtml", xhtml(head + "<p>An epigraph of six short words.</p>")))
            nav.append((f"ch{i}.xhtml", f"CHAPTER {n}"))
            files.append((f"ch{i}b.xhtml", xhtml("<p>Midsummer.</p>" + paras)))
            nav.append((f"ch{i}b.xhtml", "Midsummer"))
            continue
        files.append((f"ch{i}.xhtml", xhtml(head + paras)))
        nav.append((f"ch{i}.xhtml", f"CHAPTER {n}" if n != "ELEVEN" else "CHAPTER ELEVEN: WEST GATE"))
        if n == "FIVE":
            files.append((f"ch{i}x.xhtml", xhtml("<p>The fifth chapter goes on after the file break.</p>" + paras)))
    manifest = "".join(f"<item id='f{k}' href='{f}' media-type='application/xhtml+xml'/>" for k, (f, _) in enumerate(files))
    spine = "".join(f"<itemref idref='f{k}'/>" for k in range(len(files)))
    navdoc = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml' "
              "xmlns:epub='http://www.idpf.org/2007/ops'><body><nav epub:type='toc'><ol>"
              + "".join(f"<li><a href='{f}'>{t}</a></li>" for f, t in nav) + "</ol></nav></body></html>")
    opf = ("<?xml version='1.0' encoding='utf-8'?><package xmlns='http://www.idpf.org/2007/opf' version='3.0' "
           "unique-identifier='id'><metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
           "<dc:identifier id='id'>urn:uuid:12345678-1234-1234-1234-123456789abc</dc:identifier>"
           "<dc:title>The Lamp at Quillmere</dc:title><dc:creator>A. Nonymous</dc:creator><dc:language>en</dc:language>"
           "<meta property='dcterms:modified'>2026-09-29T00:00:00Z</meta></metadata>"
           f"<manifest>{manifest}<item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/>"
           f"</manifest><spine>{spine}</spine></package>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                   "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                   "full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/nav.xhtml", navdoc)
        for f, data in files:
            z.writestr("OEBPS/" + f, data)


def make_outlined_pdf(path):
    """Four pages with an outline: Part One (p1) > Harbour (p2); Part Two (p3) > Tower (p4)."""
    pages = ["Part One begins here", "The harbour held twelve ships", "Part Two begins here", "The tower lamp was lit"]
    objs = {1: "<< /Type /Catalog /Pages 2 0 R /Outlines 3 0 R >>", 4: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    page_ids = []
    for k, text in enumerate(pages):
        cid, pid = 5 + 2 * k, 6 + 2 * k
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objs[cid] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
        objs[pid] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents {cid} 0 R >>"
        page_ids.append(pid)
    objs[2] = f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(pages)} >>"
    o = 13   # outline items: 13 Part One, 14 Harbour, 15 Part Two, 16 Tower
    objs[3] = f"<< /Type /Outlines /First {o} 0 R /Last {o + 2} 0 R /Count 4 >>"
    objs[o] = f"<< /Title (Part One) /Parent 3 0 R /Next {o + 2} 0 R /First {o + 1} 0 R /Last {o + 1} 0 R /Count 1 /Dest [{page_ids[0]} 0 R /XYZ 0 792 0] >>"
    objs[o + 1] = f"<< /Title (Harbour) /Parent {o} 0 R /Dest [{page_ids[1]} 0 R /XYZ 0 792 0] >>"
    objs[o + 2] = f"<< /Title (Part Two) /Parent 3 0 R /Prev {o} 0 R /First {o + 3} 0 R /Last {o + 3} 0 R /Count 1 /Dest [{page_ids[2]} 0 R /XYZ 0 792 0] >>"
    objs[o + 3] = f"<< /Title (Tower) /Parent {o + 2} 0 R /Dest [{page_ids[3]} 0 R /XYZ 0 792 0] >>"
    out = bytearray(b"%PDF-1.4\n")
    offs = {}
    for i in sorted(objs):
        offs[i] = len(out)
        out += f"{i} 0 obj\n{objs[i]}\nendobj\n".encode("latin-1")
    xref = len(out)
    n = max(objs) + 1
    out += f"xref\n0 {n}\n0000000000 65535 f \n".encode()
    for i in range(1, n):
        out += f"{offs[i]:010d} 00000 n \n".encode() if i in offs else b"0000000000 65535 f \n"
    out += f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(bytes(out))


def convert(tool, *args, timeout=600):
    r = subprocess.run([str(a) for a in (tool, *args)], capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode == 0


def soffice_convert(src, fmt, outdir, extra=()):
    so = rw.tools()["soffice"]
    with tempfile.TemporaryDirectory() as td:
        convert(so, f"-env:UserInstallation={Path(td).as_uri()}", "--headless", "--norestore", *extra,
                "--convert-to", fmt, "--outdir", outdir, src)
    made = Path(outdir) / (Path(src).stem + "." + fmt.split(":")[0])
    return made if made.exists() else None


# ---------------------------------------------------------------- helpers

def cli(*args):
    """Run rw.main in-process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rw.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rw-test-"))
        rw.CACHE_OFF = True

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def f(self, name):
        return self.tmp / name


# ---------------------------------------------------------------- tests

class TestEpub(Base):
    def test_nav_titles_and_fragment_split(self):
        p = self.f("book.epub")
        make_epub(p)
        doc = rw.load(str(p))
        self.assertEqual(doc.fmt, "epub")
        self.assertEqual([s.title for s in doc.sections], ["Chapter One", "Chapter Two", "Chapter Three"])
        self.assertEqual(doc.sections[2].level, 2)
        self.assertEqual(doc.meta["title"], "The Quillmere Ledger")
        self.assertEqual(doc.meta["author"], "A. Nonymous")
        text = rw.render_paras(doc.sections[1].paras)
        self.assertIn("Rain on the slate roofs", text)
        self.assertNotIn("ledger under the stairs", text)
        self.assertNotIn("alert", rw.render_paras(doc.sections[0].paras))

    def test_ncx_titles(self):
        p = self.f("book2.epub")
        make_epub(p, nav=False, ncx=True)
        doc = rw.load(str(p))
        self.assertEqual([s.title for s in doc.sections], ["First Light", "Second Tide", "Third Bell"])

    def test_detect_by_content_not_extension(self):
        p = self.f("mystery.bin")
        make_epub(p)
        self.assertEqual(rw.detect(str(p)), "epub")

    def test_font_obfuscation_is_not_drm(self):
        p = self.f("fonts.epub")
        make_epub(p, encryption=enc_xml("http://www.idpf.org/2008/embedding", "OEBPS/fonts/a.otf"))
        self.assertEqual(len(rw.load(str(p)).sections), 3)

    def test_drm_is_reported_not_broken(self):
        p = self.f("drm.epub")
        make_epub(p, encryption=enc_xml("http://www.w3.org/2001/04/xmlenc#aes128-cbc", "OEBPS/text/ch1.xhtml"),
                  extra={"META-INF/rights.xml": "<adept:rights xmlns:adept='http://ns.adobe.com/adept'/>"})
        code, out, err = cli("info", p)
        self.assertEqual(code, 1)
        self.assertIn("DRM", err)
        self.assertIn("Adobe ADEPT", err)
        self.assertIn("does not remove DRM", err)

    def test_title_selector_and_header(self):
        p = self.f("book.epub")
        make_epub(p)
        code, out, _ = cli("read", p, "--title", "three")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("=== [3/3] Chapter Three | id text/ch2.xhtml#c3"), out[:120])
        self.assertIn("ledger under the stairs", out)
        self.assertNotIn("Rain on the slate", out)

    def test_short_selection_points_to_next_section(self):
        p = self.f("book.epub")
        make_epub(p)
        code, out, _ = cli("read", p, "--section", "1")
        self.assertIn("may continue in section 2: Chapter Two", out)
        self.assertNotIn("may continue", cli("read", p, "--section", "3")[1])


class TestFormats(Base):
    def test_docx_headings_table_and_localised_style(self):
        p = self.f("notes.docx")
        make_docx(p)
        doc = rw.load(str(p))
        titles = [s.title for s in doc.sections]
        self.assertEqual(titles, ["Field Notes", "Harbour", "Tides", "Weather"])
        self.assertEqual(doc.meta["author"], "B. Writer")
        tides = rw.render_paras(doc.sections[2].paras)
        self.assertIn("Ship\tTons\nMarigold\t310", tides)
        self.assertEqual(doc.sections[2].level, 2)

    def test_odt(self):
        p = self.f("diary.odt")
        make_odt(p)
        doc = rw.load(str(p))
        self.assertEqual([s.title for s in doc.sections], ["Orchard", "Cellar"])
        text = rw.render_paras(doc.sections[0].paras)
        self.assertIn("Apples ripen late here.", text)
        self.assertIn("- Bramley\n- Cox", text)
        self.assertEqual(doc.meta["title"], "Orchard Diary")

    def test_ods_repeated_cells_are_capped(self):
        p = self.f("stock.ods")
        make_ods(p)
        doc = rw.load(str(p))
        self.assertEqual(doc.sections[0].title, "sheet: Stock")
        self.assertEqual(rw.render_paras(doc.sections[0].paras), "item\tqty\nrope\t4")

    def test_pptx_order_titles_notes(self):
        p = self.f("deck.pptx")
        make_pptx(p)
        doc = rw.load(str(p))
        self.assertEqual([s.title for s in doc.sections], ["slide 1: Quarterly Plan", "slide 2: Budget"])
        self.assertIn("Notes: Ask about white paint", rw.render_paras(doc.sections[1].paras))

    def test_xlsx(self):
        p = self.f("tides.xlsx")
        make_xlsx(p)
        doc = rw.load(str(p))
        self.assertEqual(rw.render_paras(doc.sections[0].paras), "date\theight\n45000\t\thigh water\nnote\tTRUE")

    def test_fb2(self):
        p = self.f("snow.fb2")
        make_fb2(p)
        doc = rw.load(str(p))
        titles = [s.title for s in doc.sections]
        self.assertIn("Arrival", titles)
        self.assertIn("Departure", titles)
        self.assertEqual(doc.meta["author"], "Ivan Testov")
        arrival = doc.sections[titles.index("Arrival")]
        self.assertIn("Снег шёл всю ночь.", rw.render_paras(arrival.paras))
        self.assertLess(titles.index("Arrival"), titles.index("Departure"))
        self.assertNotIn("AAAA", "".join(rw.render_paras(s.paras) for s in doc.sections))

    def test_rtf(self):
        p = self.f("tides.rtf")
        make_rtf(p)
        doc = rw.load(str(p))
        text = "\n\n".join(rw.render_paras(s.paras) for s in doc.sections)
        self.assertIn("Café at the pier", text)
        self.assertIn("Long dash— here", text)
        self.assertIn("bold and italic", text)
        self.assertIn("Braces {ok} done.", text)
        self.assertNotIn("Times", text)
        self.assertNotIn("Hand 1.0", text)
        self.assertEqual(doc.meta.get("title"), "Tide Tables")
        self.assertIn("CHAPTER TWO", [s.title for s in doc.sections])

    def test_html(self):
        p = self.f("lamps.html")
        make_html(p)
        doc = rw.load(str(p))
        self.assertEqual([s.title for s in doc.sections], ["Lamps", "Wicks", "Fuel"])
        body = "\n\n".join(rw.render_paras(s.paras) for s in doc.sections)
        self.assertNotIn("SCRIPTTEXT", body)
        self.assertIn("Trim the wick daily.", body)
        self.assertIn("Part\tCost\nGlass\t3", body)
        self.assertIn("Paraffin & kerosene.", body)
        self.assertEqual(doc.meta["author"], "D. Lamplighter")

    def test_html_noterefs_bracketed(self):
        # note numbers glued to the sentence ("after that.40 Uber") misread as figures; they print as [40]
        html = ('<p>They raised $1.4 billion after that.<sup><a href="notes.xhtml#n40" role="doc-noteref">40</a></sup> Uber grew.'
                ' Area is x<sup>2</sup>; see<a epub:type="noteref" href="#n7">7</a>.</p>')
        text = rw.render_paras(rw.html_paras(html).paras)
        self.assertIn("after that.[40] Uber grew.", text)
        self.assertIn("x2;", text)
        self.assertIn("see[7].", text)

    def test_outline_alias(self):
        # the skills say "outline"; a reader agent's first call was rw.py outline
        p = self.f("lamps.html")
        make_html(p)
        r = subprocess.run([sys.executable, str(SCRIPT), "outline", str(p)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Wicks", r.stdout)

    def test_eml(self):
        p = self.f("report.eml")
        make_eml(p)
        doc = rw.load(str(p))
        text = rw.render_paras(doc.sections[0].paras)
        self.assertEqual(doc.meta["subject"], "Lamp report")
        self.assertIn("The north lamp is out.", text)
        self.assertIn("invoice.pdf (application/pdf", text)
        self.assertEqual(text.count("north lamp"), 1)   # plain part chosen, html alternative skipped

    def test_text_chapters_and_markdown(self):
        t = self.f("story.txt")
        t.write_text("CHAPTER I\n\nIt began " + lorem(30) + "\n\nChapter II: The Road\n\nThen " + lorem(20) + "\n", encoding="utf-8")
        self.assertEqual([s.title for s in rw.load(str(t)).sections], ["CHAPTER I", "Chapter II: The Road"])
        m = self.f("readme.md")
        m.write_text("# Top\n\nintro\n\n```\n# not a heading\n```\n\n## Usage\n\n- one\n- two\n", encoding="utf-8")
        doc = rw.load(str(m))
        self.assertEqual([s.title for s in doc.sections], ["Top", "Usage"])
        self.assertIn("# not a heading", rw.render_paras(doc.sections[0].paras))

    def test_unstructured_text_is_chunked(self):
        t = self.f("wall.txt")
        t.write_text("\n\n".join(lorem(100) for _ in range(100)), encoding="utf-8")
        doc = rw.load(str(t))
        self.assertGreater(len(doc.sections), 2)
        self.assertTrue(doc.sections[0].title.startswith("part 1:"))

    def test_csv_and_json(self):
        c = self.f("t.csv")
        c.write_text("a;b\n1;2\n", encoding="utf-8")
        self.assertEqual(rw.render_paras(rw.load(str(c)).sections[0].paras), "a\tb\n1\t2")
        j = self.f("t.json")
        j.write_text(json.dumps({"alpha": [1, 2], "beta": {"x": "ü"}}), encoding="utf-8")
        doc = rw.load(str(j))
        self.assertEqual([s.title for s in doc.sections], ["alpha", "beta"])

    def test_zip_single_member_and_member_flag(self):
        fb = self.f("snow.fb2")
        make_fb2(fb)
        one = self.f("snow.fb2.zip")
        with zipfile.ZipFile(one, "w") as z:
            z.write(fb, "snow.fb2")
        self.assertEqual(rw.load(str(one)).fmt, "fb2")
        two = self.f("bundle.zip")
        h = self.f("lamps.html")
        make_html(h)
        with zipfile.ZipFile(two, "w") as z:
            z.write(fb, "books/snow.fb2")
            z.write(h, "web/lamps.html")
        code, out, _ = cli("toc", two)
        self.assertIn("books/snow.fb2", out)
        self.assertIn("web/lamps.html", out)
        code, out, err = cli("read", two)
        self.assertEqual(code, 1)
        self.assertIn("--member", err)
        code, out, _ = cli("read", two, "--member", "lamps.html", "--title", "wicks")
        self.assertEqual(code, 0)
        self.assertIn("Trim the wick daily.", out)

    def test_mobi_drm_detected_without_calibre(self):
        p = self.f("locked.azw3")
        make_mobi(p, encryption=2)
        code, _, err = cli("info", p)
        self.assertEqual(code, 1)
        self.assertIn("DRM", err)


    def test_outlook_msg_and_unknown_binary(self):
        p = self.f("mail.msg")
        p.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
        self.assertIn(".eml", cli("info", p)[2])
        q = self.f("blob.dat")
        q.write_bytes(b"\x00\x01\x02" * 100)
        self.assertIn("unrecognised", cli("info", q)[2])

    @unittest.skipUnless(rw.tools()["pdftotext"] or rw.tools()["mutool"], "no pdftotext or mutool")
    def test_pdf_pages(self):
        p = self.f("two.pdf")
        make_pdf(p)
        doc = rw.load(str(p))
        self.assertEqual(len(doc.sections), 2)
        self.assertIn("Second page text", rw.render_paras(doc.sections[1].paras))

    @unittest.skipUnless(rw.tools()["pdftotext"] or rw.tools()["mutool"], "no pdftotext or mutool")
    def test_scanned_pdf_says_so(self):   # L-011: page images gave `words: 0` and no hint
        p = self.f("plates.pdf")
        make_pdf(p, pages=("", "", ""))
        self.f("plates.djvu").write_bytes(b"AT&TFORM")
        code, out, _ = cli("info", p)
        self.assertIn("no text layer", out)
        self.assertIn("plates.djvu", out)
        self.assertIn("next: no text to read", out)
        code, out, _ = cli("read", p)
        self.assertIn("no text layer", out)
        self.assertIn("(no text found)", out)
        q = self.f("prose.pdf")
        make_pdf(q, pages=(lorem(30), lorem(30)))
        self.assertNotIn("no text layer", cli("info", q)[1])

    @unittest.skipUnless(rw.tools()["pdftotext"] or rw.tools()["mutool"], "no pdftotext or mutool")
    def test_ocr_text_replaces_an_empty_layer(self):   # L-018 `scans-need-ocr`: a kept OCR text is read like a text layer
        p = self.f("plates.pdf")
        make_pdf(p, pages=("", ""))
        with unittest.mock.patch.dict(os.environ, {"READWRIGHT_OCR_DIR": str(self.f("ocr"))}):
            c = rw.ocr_cache(str(p))
            c.parent.mkdir(parents=True)
            c.write_bytes(("Warm light casts cool shadows " * 3 + "\f" + "Value matters more than hue " * 3).encode())
            code, out, _ = cli("info", p)
            self.assertNotIn("no text layer", out)
            self.assertIn("text from OCR", out)
            self.assertIn("Value matters more", cli("read", p, "--section", "2")[1])

    def test_printed_page_offset(self):   # L-019: printed page = PDF page + 1 in a scanned art book
        pages = [f"Body text\n{n + 1}" for n in range(1, 9)] + ["Cover"]
        self.assertEqual(rw.printed_offset(pages), 1)
        self.assertEqual(rw.printed_offset([f"Text\n{n}" for n in range(1, 9)]), 0)
        self.assertEqual(rw.printed_offset(["12\nx", "y"]), 0, "one numbered page is not enough")

    def test_grep_without_i_names_case_hits(self):
        p = self.f("t.md")
        p.write_text("# One\n\nValue keying sets the mood.\n", encoding="utf-8")
        code, out, _ = cli("grep", p, "value key")
        self.assertEqual(code, 1)
        self.assertIn("1 matches with -i", out)

    def test_ocr_without_an_engine_says_how(self):
        p = self.f("plates.pdf")
        make_pdf(p, pages=("",))
        with hide_tools("windows-ocr", "tesseract"):
            code, _, err = cli("ocr", p)
        self.assertEqual(code, rw.EXIT_ERR)
        self.assertIn("no OCR engine", err)

    @unittest.skipUnless(rw.ocr_engine() and (rw.tools()["mutool"] or rw.find_tool("pdftoppm")), "no OCR engine or renderer")
    def test_ocr_reads_a_rendered_page(self):
        p = self.f("scan.pdf")
        make_pdf(p, pages=("", ""))
        with unittest.mock.patch.dict(os.environ, {"READWRIGHT_OCR_DIR": str(self.f("ocr"))}):
            self.assertIn("rw.py ocr", cli("info", p)[1])
            q = self.f("text.pdf")
            make_pdf(q)
            code, out, _ = cli("ocr", q)
            self.assertEqual(code, rw.EXIT_OK, out)
            self.assertIn("Hello", rw.ocr_cache(str(q)).read_text(encoding="utf-8"))
            self.assertIn("already OCR'd", cli("ocr", q)[1])

    def test_image_only_epub_says_so(self):
        p = self.f("pictures.epub")
        page = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
                "<img src='p1.jpg'/><img src='p2.jpg'/></body></html>")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
            z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                       "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                       "full-path='content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
            z.writestr("content.opf", "<?xml version='1.0'?><package xmlns='http://www.idpf.org/2007/opf' version='3.0'>"
                       "<metadata/><manifest><item id='a' href='a.xhtml' media-type='application/xhtml+xml'/></manifest>"
                       "<spine><itemref idref='a'/></spine></package>")
            z.writestr("a.xhtml", page)
        code, out, _ = cli("info", p)
        self.assertIn("no text layer", out)
        self.assertIn("inside the EPUB", out)
        self.assertNotIn("no text layer", cli("info", self.epub_with_text())[1])

    def epub_with_text(self):
        q = self.f("book.epub")
        make_epub(q)
        return q



class TestCommands(Base):
    def big_text(self):
        t = self.f("big.txt")
        t.write_text("\n\n".join(f"CHAPTER {i}\n\n" + "\n\n".join(lorem(400, "Brannoch" if i == 7 else "lorem") for _ in range(5))
                                 for i in range(1, 11)), encoding="utf-8")
        return t

    def test_info_json(self):
        p = self.f("book.epub")
        make_epub(p)
        code, out, _ = cli("info", p, "--json")
        d = json.loads(out)
        self.assertEqual(d["format"], "epub")
        self.assertEqual(d["sections"], 3)
        self.assertEqual(d["tokens_approx"], d["chars"] // 4)

    def test_toc_lines(self):
        p = self.f("book.epub")
        make_epub(p)
        code, out, _ = cli("toc", p)
        self.assertIn("   2. Chapter Two", out)
        self.assertIn("   3.   Chapter Three", out)   # nested one level
        self.assertNotIn("[text/ch2.xhtml#c3]", out)   # ids cost tokens; they are opt-in
        self.assertIn("[text/ch2.xhtml#c3]", cli("toc", p, "--ids")[1])

    def test_read_refuses_large_without_selector(self):
        t = self.big_text()
        code, out, _ = cli("read", t)
        self.assertEqual(code, rw.EXIT_REFUSED)
        self.assertIn("REFUSED", out)
        self.assertIn("--out", out)
        self.assertIn("CHAPTER 7", out)     # the toc is printed instead
        self.assertLess(len(out), 5000)

    def test_read_section_range_and_max_chars(self):
        t = self.big_text()
        code, out, _ = cli("read", t, "--section", "2-3", "--max-chars", "500")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("=== [2/10] CHAPTER 2"))
        self.assertIn("--offset", out)
        self.assertLess(len(out), 800)
        code, out2, _ = cli("read", t, "--section", "2-3", "--max-chars", "500", "--offset", "500")
        self.assertNotEqual(out[:200], out2[:200])
        self.assertEqual(cli("read", t, "--section", "11")[0], 1)

    def test_read_compact_drops_blank_lines(self):
        t = self.big_text()
        _, full, _ = cli("read", t, "--section", "2")
        code, out, _ = cli("read", t, "--section", "2", "--compact")
        self.assertEqual(code, 0)
        self.assertIn("\n\n", full)
        self.assertNotIn("\n\n", out)
        self.assertEqual(full.split(), out.split())
        self.assertNotEqual(cli("read", t, "--section", "2", "--compact", "--at-para", "1")[0], 0)

    def test_read_out_writes_utf8_lf(self):
        p = self.f("snow.fb2")
        make_fb2(p)
        o = self.f("out/snow.txt")
        code, out, _ = cli("read", p, "--out", o)
        self.assertEqual(code, 0)
        data = o.read_bytes()
        self.assertNotIn(b"\r\n", data)
        self.assertIn("Снег".encode("utf-8"), data)

    def test_read_out_cut_says_where_to_resume(self):   # a reader could not tell --out had cut the section
        t = self.big_text()
        o = self.f("out/cut.txt")
        code, out, _ = cli("read", t, "--section", "2", "--max-chars", "300", "--out", o)
        self.assertEqual(code, 0)
        self.assertIn("cut at chars 0-", out)
        end = int(out.split("--offset ")[1].split(",")[0].replace(",", ""))
        self.assertEqual(end, len(o.read_text(encoding="utf-8")))
        self.assertLessEqual(end, 300)
        code, out, _ = cli("read", t, "--section", "2", "--out", o)
        self.assertNotIn("cut at", out)

    def test_read_out_dir_one_file_per_section(self):
        t = self.big_text()
        d = self.f("secs")
        code, out, _ = cli("read", t, "--section", "2,7", "--out-dir", d)
        self.assertEqual(code, 0)
        files = sorted(x.name for x in d.iterdir())
        self.assertEqual(len(files), 2)
        self.assertTrue(files[0].startswith("002-") and files[1].startswith("007-chapter-7"))
        self.assertIn("Brannoch", (d / files[1]).read_text(encoding="utf-8"))
        self.assertIn("wrote 2 section file(s)", out)

    def test_grep_context_and_max(self):
        t = self.big_text()
        code, out, _ = cli("grep", t, "brannoch", "-i", "-C", "1", "--max", "2", "--width", "80")
        self.assertEqual(code, 0)
        self.assertIn("--- [7] CHAPTER 7 | para", out)
        self.assertEqual(out.count("--- ["), 2)
        self.assertIn("raise --max", out)
        code, out, _ = cli("grep", t, "Brannoch", "--count")
        self.assertIn("CHAPTER 7:", out)
        self.assertEqual(cli("grep", t, "zzzz-nothing")[0], 1)

    def test_dump_to_file_with_markers(self):
        t = self.big_text()
        o = self.f("dump.md")
        code, out, _ = cli("dump", t, "--out", o, "--format", "md")
        self.assertEqual(code, 0)
        text = o.read_text(encoding="utf-8")
        self.assertEqual(text.count("<!-- readwright section "), 10)
        code, _, err = cli("dump", t)
        self.assertEqual(code, 1)
        self.assertIn("--out", err)

    def test_formats(self):
        code, out, _ = cli("formats")
        self.assertIn("epub", out)
        self.assertIn("tools:", out)

    def test_subprocess_utf8_stdout(self):
        p = self.f("snow.fb2")
        make_fb2(p)
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        r = subprocess.run([sys.executable, str(SCRIPT), "read", str(p), "--title", "Arrival"], capture_output=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Снег шёл всю ночь.".encode("utf-8"), r.stdout)
        self.assertNotIn(b"\r\n", r.stdout)


    def test_grep_offset_matches_read_offset(self):
        t = self.big_text()
        for fmt in ("txt", "md"):
            code, out, _ = cli("grep", t, "Brannoch", "--max", "3", "--format", fmt)
            m = re.search(r"--- \[7\] CHAPTER 7 \| para (\d+)/\d+ \| offset (\d+)", out)
            self.assertTrue(m, out)
            code, got, _ = cli("read", t, "--section", "7", "--offset", m.group(2), "--max-chars", "8", "--format", fmt)
            self.assertTrue(got.startswith("Brannoch"), (fmt, got[:40]))
            code, got, _ = cli("grep", t, "Brannoch", "--json", "--max", "1", "--format", fmt)
            self.assertEqual(json.loads(got)["hits"][0]["offset"], int(m.group(2)))

    def test_read_at_para(self):
        t = self.big_text()
        code, out, _ = cli("grep", t, "Brannoch", "--max", "2")
        para = re.findall(r"\| para (\d+)/\d+ \| offset (\d+)", out)[1]
        code, got, _ = cli("read", t, "--section", "7", "--at-para", para[0], "--max-chars", "8")
        self.assertEqual(code, 0)
        self.assertTrue(got.startswith("Brannoch"), got[:40])
        self.assertIn(f"chars {rw.fmt_n(int(para[1]))}-", got)
        self.assertEqual(cli("read", t, "--section", "7", "--at-para", "999")[0], 1)
        self.assertEqual(cli("read", t, "--title", "CHAPTER 7", "--at-para", "2")[0], 1)

    def cookbook(self):
        """Recipes split into sections with the same generic titles, as Packt-style cookbooks are."""
        t = self.f("cookbook.md")
        parts = []
        for r in ("Following a path", "Baking the map", "Tuning the swarm"):
            parts.append(f"## {r}\n\n{lorem(20, 'intro')}")
            for g in ("Getting ready", "How to do it...", "There's more..."):
                parts.append(f"### {g}\n\n{lorem(120, 'step')}")
        t.write_text("\n\n".join(parts), encoding="utf-8")
        return t

    def test_generic_titles_get_context(self):
        t = self.cookbook()
        doc = rw.load(str(t))
        ctx = rw.context_titles(doc)
        n = next(i for i, s in enumerate(doc.sections, 1) if s.title == "There's more..." and ctx.get(i) == "Tuning the swarm")
        self.assertNotIn(n - 3, ctx)   # the recipe heading itself is distinctive
        code, out, _ = cli("read", t, "--section", str(n))
        self.assertEqual(code, 0)
        self.assertIn("There's more... (in: Tuning the swarm) |", out.splitlines()[0])
        _, md, _ = cli("read", t, "--section", str(n), "--format", "md")
        self.assertIn("in='Tuning the swarm'", md.splitlines()[0])
        _, toc, _ = cli("toc", t)
        self.assertIn("How to do it... (in: Following a path)", toc)
        _, js, _ = cli("toc", t, "--json")
        self.assertEqual(json.loads(js)["sections"][n - 1]["in"], "Tuning the swarm")

    def test_read_max_words_per_section(self):
        t = self.cookbook()
        _, full, _ = cli("read", t, "--section", "1-")
        code, out, _ = cli("read", t, "--section", "1-", "--max-words", "10")
        self.assertEqual(code, 0)
        self.assertLess(len(out), len(full) // 3)
        self.assertEqual(out.count("=== ["), full.count("=== ["))
        self.assertIn("[readwright: cut at 10 of 122 words; continue with --section 2 --offset ", out)
        self.assertEqual(cli("read", t, "--section", "1", "--max-words", "0")[0], 1)

    def test_char_cut_footer_offers_max_chars_for_the_rest(self):
        t = self.cookbook()
        _, out, _ = cli("read", t, "--section", "2", "--max-chars", "30", "--quiet")
        m = re.search(r"show it all with --max-chars ([0-9]+)", out)
        self.assertTrue(m, out)
        _, rest, _ = cli("read", t, "--section", "2", "--max-chars", m.group(1), "--quiet")
        self.assertNotIn("[readwright: shown chars", rest)

    def test_char_cut_ends_at_a_paragraph_and_offset_resumes(self):
        t = self.cookbook()
        _, full, _ = cli("read", t, "--section", "2", "--quiet")
        body = full.split("[readwright:")[0]
        limit = len(body) - 40
        _, out, _ = cli("read", t, "--section", "2", "--max-chars", str(limit), "--quiet")
        m = re.search(r"shown chars 0-([0-9,]+) of", out)
        self.assertTrue(m, out)
        end = int(m.group(1).replace(",", ""))
        self.assertLess(end, limit)
        self.assertTrue(body[:end].endswith(("\n", " ")), repr(body[end - 20:end]))
        _, rest, _ = cli("read", t, "--section", "2", "--offset", str(end), "--quiet")
        self.assertEqual(body[:end] + rest.split("[readwright:")[0], body)

    def test_clean_cut_prefers_paragraph_then_sentence(self):
        self.assertEqual(rw.clean_cut("aaaa aaaa.\n\nbbbb bb. cc"), "aaaa aaaa.\n\nbbbb bb. ")
        self.assertEqual(rw.clean_cut("a" * 30 + "\n\nbbbb. cc dd"), "a" * 30 + "\n\nbbbb. ")
        self.assertEqual(rw.clean_cut("x" * 40), "x" * 40)

    def test_max_words_offset_continues_where_the_cut_fell(self):
        t = self.cookbook()
        for fmt in ("txt", "md"):
            _, out, _ = cli("read", t, "--section", "2", "--max-words", "7", "--format", fmt, "--quiet")
            m = re.search(r"cut at 7 of 122 words; continue with --section 2 --offset ([0-9]+)", out)
            self.assertTrue(m, out)
            if fmt == "md":
                self.assertIn("--format md]", out)
            _, rest, _ = cli("read", t, "--section", "2", "--offset", m.group(1), "--format", fmt, "--quiet")
            self.assertTrue(rest.startswith(" consectetur adipiscing"), rest[:40])

    def test_multi_section_read_prints_one_hint(self):
        t = self.f("short.md")
        t.write_text("\n\n".join(f"## Part {i}\n\n{lorem(5)}" for i in range(1, 7)), encoding="utf-8")
        _, out, _ = cli("read", t, "--section", "1-4")
        self.assertEqual(out.count("[readwright:"), 1)
        self.assertIn("continue in section 5", out.splitlines()[-1])
        _, out, _ = cli("read", t, "--section", "1-6")
        self.assertNotIn("[readwright:", out)   # nothing comes after the selection
        _, out, _ = cli("read", t, "--section", "1-2", "--quiet")
        self.assertNotIn("[readwright:", out)

    def code_epub(self):
        src, dst = self.f("plain.epub"), self.f("code.epub")
        make_epub(src)
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>Set the flag before the run starts.</p>"
               "<pre data-type='programlisting'><code>import tide\nfor gull in tide.count(): print(gull)</code></pre>"
               "<p>Then check the import log for gulls.</p>"
               "<p>A line of prose can look like code = yes; it stays.</p>"
               "<h1 id='c3'>Chapter Three</h1><p>The ledger listed every ship.</p>"
               "<pre>import ledger\nledger.open()</pre></body></html>")
        with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
            for info in zi.infolist():
                zo.writestr(info, ch2 if info.filename.endswith("ch2.xhtml") else zi.read(info))
        return dst

    def test_skip_code_on_read_and_grep(self):
        e = self.code_epub()
        _, full, _ = cli("read", e, "--section", "2-3")
        self.assertIn("tide.count()", full)
        _, out, _ = cli("read", e, "--section", "2-3", "--skip-code")
        self.assertNotIn("tide.count()", out)
        self.assertNotIn("ledger.open()", out)
        self.assertIn("code = yes; it stays", out)   # structure decides, not how a line looks
        self.assertIn("--skip-code left out 10 words in 2 code blocks", out)
        _, out, _ = cli("read", e, "--section", "2", "--skip-code")
        self.assertIn("left out 7 words in 1 code blocks", out)
        _, g, _ = cli("grep", e, "import", "--skip-code")
        self.assertIn("import log", g)
        self.assertIn("1 matches in 1 paragraphs", g)
        self.assertIn("left out 10 words in 2 code blocks", g)
        self.assertIn("3 matches", cli("grep", e, "import")[1])

    def test_skip_code_says_pdf_has_no_marker(self):
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("One", [rw.Para("p", "def run(): pass")])])
        self.assertIn("no structural code marker", rw.code_note(doc, rw.skip_code(doc), [1]))
        self.assertEqual(doc.sections[0].words(), 3)

    def test_toc_flags_giant_section(self):
        doc = rw.Doc("x.pdf", "pdf", sections=[
            rw.Section("One", [rw.Para("p", "short text")]),
            rw.Section("Two", [rw.Para("p", lorem(300)) for _ in range(150)])])
        old = rw.BIG_SECTION_CHARS
        try:
            rw.BIG_SECTION_CHARS = 10_000
            notes = rw.big_section_notes(doc)
        finally:
            rw.BIG_SECTION_CHARS = old
        self.assertEqual(len(notes), 1)
        self.assertIn("section 2 holds", notes[0])
        self.assertIn("--at-para", notes[0])
        self.assertNotIn("note: section", cli("toc", self.big_text())[1])

    def test_subprocess_cp1252_console(self):
        t = self.f("arrow.txt")
        t.write_text("Go left \u2192 then right \u2190 and on.", encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        env.pop("PYTHONUTF8", None)
        for args in (["read", str(t)], ["grep", str(t), "left"]):
            r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(b"UnicodeEncodeError", r.stderr)


def make_packt_epub(path):
    """Packt layout: a Part heading, then per chapter a bare-number nav entry, the chapter title and nested sections."""
    chapters = [("Part 1 Foundations", 2, None), ("1", 0, None),
                ("Chapter Title Alpha", 20, [("Alpha one", 30), ("Alpha two", 40)]),
                ("2", 0, None), ("Chapter Title Beta", 25, [("Beta one", 50)]), ("Index", 10, None)]
    body, nav = [], []
    for k, (title, n, subs) in enumerate(chapters):
        hid = f"s{k}"
        body.append(f"<h1 id='{hid}'>{title}</h1>" + (f"<p>{lorem(n)}</p>" if n else ""))
        li = f"<li><a href='c.xhtml#{hid}'>{title}</a>"
        if subs:
            li += "<ol>"
            for j, (st, sn) in enumerate(subs):
                body.append(f"<h2 id='{hid}_{j}'>{st}</h2><p>{lorem(sn)}</p>")
                li += f"<li><a href='c.xhtml#{hid}_{j}'>{st}</a></li>"
            li += "</ol>"
        nav.append(li + "</li>")
    xh = "<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>" + "".join(body) + "</body></html>"
    navdoc = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml' "
              "xmlns:epub='http://www.idpf.org/2007/ops'><body><nav epub:type='toc'><ol>" + "".join(nav) + "</ol></nav></body></html>")
    opf = ("<?xml version='1.0' encoding='utf-8'?><package xmlns='http://www.idpf.org/2007/opf' version='3.0'>"
           "<metadata xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title>Invented Handbook</dc:title><dc:language>en</dc:language></metadata>"
           "<manifest><item id='c' href='c.xhtml' media-type='application/xhtml+xml'/>"
           "<item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/></manifest>"
           "<spine><itemref idref='c'/></spine></package>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                   "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                   "full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/c.xhtml", xh)
        z.writestr("OEBPS/nav.xhtml", navdoc)


class TestTocChapters(Base):
    def book(self):
        p = self.f("packt.epub")
        make_packt_epub(p)
        return p

    def wcount(self, line):
        return int(re.search(r"\(([\d,]+) w\)", line).group(1).replace(",", ""))

    def test_bare_number_merges_with_title(self):
        p = self.book()
        titles = [s.title for s in rw.load(str(p)).sections]
        n1 = titles.index("1") + 1          # the number section keeps its number
        _, out, _ = cli("toc", p)
        self.assertIn(f"{n1 + 1:>4}. Ch. 1: Chapter Title Alpha", out)
        self.assertIn("Ch. 2: Chapter Title Beta", out)
        self.assertNotRegex(out, r"(?m)^\s*%d\. 1 " % n1)
        self.assertIn("Alpha one", out)     # subsections still listed without --depth
        self.assertIn("Part 1 Foundations", out)
        self.assertNotIn("Ch. 3", out)
        self.assertEqual(cli("read", p, "--section", str(n1))[0], 0)   # still addressable

    def test_depth_one_lists_chapters_with_rolled_up_words(self):
        p = self.book()
        _, out, _ = cli("toc", p, "--depth", "1")
        self.assertNotIn("Alpha one", out)
        self.assertNotIn("Beta one", out)
        lines = [l for l in out.splitlines() if re.match(r"\s*\d+\. ", l)]
        self.assertEqual(len(lines), 4)     # part, two chapters, index
        words = self.wcount(next(l for l in lines if "Chapter Title Alpha" in l))
        self.assertGreaterEqual(words, 20 + 30 + 40)
        _, full, _ = cli("toc", p)
        own = self.wcount(next(l for l in full.splitlines() if "Chapter Title Alpha" in l))
        self.assertLess(own, words)         # without --depth the line shows only its own text

    def test_depth_json_and_limit(self):
        p = self.book()
        secs = json.loads(cli("toc", p, "--json", "--depth", "1")[1])["sections"]
        self.assertTrue(all(s["level"] == 1 for s in secs))
        self.assertEqual([s["chapter"] for s in secs if "chapter" in s], [1, 2])
        self.assertTrue(all(s["words_total"] >= s["words"] for s in secs))
        self.assertIn("2 more sections", cli("toc", p, "--depth", "1", "--limit", "2")[1])

    def test_numbers_that_are_not_chapter_openers_stay(self):
        doc = rw.Doc("x.txt", "txt", sections=[
            rw.Section("7", [rw.Para("p", lorem(400))]),    # a long section titled "7": real content
            rw.Section("Next", [rw.Para("p", "words")]),
            rw.Section("Chapter 9", []),
            rw.Section("12", []),                            # number followed by number: no merge
            rw.Section("Real Title", [rw.Para("p", "words")])])
        self.assertEqual(rw.chapter_numbers(doc), {5: (12, 4)})
        lines = rw.toc_lines(doc, 100)
        self.assertTrue(any("Ch. 12: Real Title" in l for l in lines))
        self.assertTrue(any(l.strip().startswith("1. 7") for l in lines))

    def test_group_folds_pages_by_running_head(self):   # L-023 `pdf-pages-by-running-head`
        def pg(n, head, w=50):
            return rw.Section(f"page {n}: {head}" if head else f"page {n}", [rw.Para("p", lorem(w))], 1, f"page{n}")
        doc = rw.Doc("x.pdf", "pdf", sections=[pg(1, ""), pg(2, "Preface"), pg(3, "Preface"),
            pg(4, "Testimonial Injustice In the film she"), pg(5, "Testimonial Injustice"), pg(6, "Testimonial Injustice"),
            pg(7, "Hermeneutical Injustice")])
        self.assertEqual([(f, l, h) for f, l, h, _ in rw.page_groups(doc)],
                         [(1, 1, ""), (2, 3, "Preface"), (4, 6, "Testimonial Injustice"), (7, 7, "Hermeneutical Injustice")])
        self.assertEqual(rw.page_groups(doc)[2][3], 150)
        self.assertTrue(any("4-6. Testimonial Injustice  (150 w)" in l for l in rw.group_lines(doc)))
        self.assertEqual(rw.page_groups(rw.Doc("x.epub", "epub", sections=[rw.Section("Chapter 1")])), [])

    def test_strip_drops_repeated_running_head_on_pages(self):   # L-024 `page-running-head`
        P = rw.Para
        doc = rw.Doc("x.pdf", "pdf", sections=[
            rw.Section("page 4: Testimonial Injustice In the film", [P("p", "Testimonial Injustice In the film she"), P("p", "4")]),
            rw.Section("page 5: Testimonial Injustice", [P("p", "Testimonial Injustice"), P("p", "body five"), P("p", "5")]),
            rw.Section("page 6: Testimonial Injustice", [P("p", "Testimonial Injustice"), P("p", "body six")])],
            furniture={"testimonial injustice", "#"})
        rw.strip_furniture(doc)
        self.assertEqual([[p.text for p in s.paras] for s in doc.sections],
                         [["Testimonial Injustice In the film she"], ["body five"], ["body six"]])


class TestRealWorldShapes(Base):
    """Shapes seen in real files on 2026-09-29 (LEARNINGS L-001, L-003, L-005, L-006), rebuilt from invented text."""

    def novel(self):
        p = self.f("novel.epub")
        make_novel(p)
        return p

    def test_chapter_split_across_files_is_one_section(self):
        doc = rw.load(str(self.novel()))
        titles = [s.title for s in doc.sections]
        self.assertEqual(len(titles), 13, titles)
        five = doc.sections[titles.index("CHAPTER FIVE")]
        self.assertIn("goes on after the file break", rw.render_paras(five.paras))

    def test_title_match_ignores_spaces(self):
        p = self.novel()
        code, out, _ = cli("read", p, "--title", "westgate", "--max-chars", "300")
        self.assertEqual(code, 0)
        self.assertIn("WEST GATE", out.splitlines()[0])

    def test_short_title_match_adds_the_next_section(self):
        p = self.novel()
        code, out, _ = cli("read", p, "--title", "chapter twelve")
        self.assertEqual(code, 0)
        self.assertIn("Midsummer.", out)
        self.assertIn("the section after it was added (13)", out)
        code, out, _ = cli("read", p, "--section", "12")
        self.assertNotIn("Midsummer.", out)
        self.assertIn("may continue in section 13", out)
        code, out, _ = cli("read", p, "--section", "3", "--with-next")
        self.assertIn("=== [4/13] CHAPTER FOUR", out)

    def test_bracketed_heading_and_gutenberg_markers(self):
        t = self.f("pg.txt")
        t.write_text("Title: An Invented Book\n\n*** START OF THE PROJECT GUTENBERG EBOOK AN INVENTED BOOK ***\n\n"
                     "[Illustration: THE COVER\n\n\n\nChapter I.]\n\n\n" + lorem(200) + "\n\nCHAPTER II.\n\n" + lorem(200)
                     + "\n\n*** END OF THE PROJECT GUTENBERG EBOOK AN INVENTED BOOK ***\n\n" + lorem(50, "licence"),
                     encoding="utf-8")
        titles = [s.title for s in rw.load(str(t)).sections]
        self.assertIn("Chapter I.", titles)
        self.assertIn("CHAPTER II.", titles)
        self.assertIn("END OF THE PROJECT GUTENBERG EBOOK AN INVENTED BOOK", titles)

    def test_glued_chapter_number_is_a_heading(self):
        self.assertEqual(rw.heading_line("CHAPTERXXVII."), "CHAPTERXXVII.")
        self.assertIsNone(rw.heading_line("Chapterhouse"))
        self.assertIsNone(rw.heading_line("chapterize this"))

    def test_untitled_blocks_split_at_chapter_lines(self):
        body = lambda n: "".join(f"<p>{lorem(80)} {n} {k}.</p>" for k in range(4))   # noqa: E731
        fb2 = ("<?xml version='1.0' encoding='utf-8'?><FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'>"
               "<description><title-info><book-title>Converted</book-title></title-info></description><body>"
               f"<section><p>CHAPTER I.</p>{body('one')}<p>CHAPTER II.</p>{body('two')}</section>"
               f"<section><p>The second chapter carries on here.</p>{body('two-b')}<p>CHAPTER III.</p>{body('three')}</section>"
               "</body></FictionBook>")
        p = self.f("conv.fb2")
        p.write_text(fb2, encoding="utf-8")
        doc = rw.load(str(p))
        self.assertEqual([s.title for s in doc.sections], ["CHAPTER I.", "CHAPTER II.", "CHAPTER III."])
        self.assertIn("carries on here", rw.render_paras(doc.sections[1].paras))

    def test_kfx_detected_by_container_header(self):
        p = self.f("book.bin")
        p.write_bytes(b"CONT\x02\x00\x1a\x00" + b"\x00" * 64)
        self.assertEqual(rw.detect(str(p)), "kfx")
        q = self.f("contents")
        q.write_text("CONTENTS\n\nOne\n", encoding="utf-8")
        self.assertEqual(rw.detect(str(q)), "txt")

    def test_mutool_outline_format(self):
        sample = ('|\t"PRIDE. and PREJUDICE"\t#page=6&zoom=100,4.5,102\r\n'
                  '-\t"Table of Contents"\t#page=2&zoom=100,219.25,95.4\r\n'
                  '|\t\t"The Project"\t#page=4&zoom=100,172.95,102.7\r\n'
                  '  "Old style" #12\n')
        self.assertEqual(rw.parse_outline(sample), [("PRIDE. and PREJUDICE", 6, 1), ("Table of Contents", 2, 1),
                                                   ("The Project", 4, 2), ("Old style", 12, 2)])

    def test_pdf_section_starts_at_its_heading(self):
        P = rw.Para
        page = [P("p", "end of the section before."), P("p", "14.5 SUMMARY"), P("p", "In this chapter...")]
        self.assertEqual(rw.heading_at(page, "14.5 Summary"), 1)
        run_in = [P("p", "tail of 14.1. 14.2 ACTIONS An action is an output from an agent.")]
        self.assertEqual(rw.heading_at(run_in, "14.2 Actions"), 1)
        self.assertEqual([p.text for p in run_in], ["tail of 14.1.", "14.2 ACTIONS An action is an output from an agent."])
        prose = [P("p", "We take actions every day.")]
        self.assertEqual(rw.heading_at(prose, "Actions"), 0)  # an unnumbered title is never found inside prose
        self.assertEqual(len(prose), 1)

    def test_outline_title_unescapes_quotes(self):   # L-015: MuPDF prints \" inside a quoted title
        sample = '|\t\t"What is a \\"good\\" lamp? A\\\\B"\t#page=3&view=FitH,1\n'
        self.assertEqual(rw.parse_outline(sample), [('What is a "good" lamp? A\\B', 3, 2)])

    def test_outline_title_drops_escaped_line_breaks_and_ligatures(self):   # Essentials of Economics 2026-11-02: "Model?\r", "Diﬃcult"
        sample = '|\t\t"Why Are Cycles So Diﬃcult to Predict?\\r"\t#page=9&view=FitH,1\n'
        self.assertEqual(rw.parse_outline(sample), [("Why Are Cycles So Difficult to Predict?", 9, 2)])
        self.assertEqual(rw.clean("eﬀect of a ﬁrm"), "effect of a firm")

    def test_outline_title_takes_spacing_from_the_page(self):   # L-015: "approachto" from a wrapped heading
        text = "Running head\n\nThe lighthouse keeper is a careful\nwatcher of ships\nbody text follows here.\n"
        t = rw.isolate_headings(text, ["The lighthouse keeper is a carefulwatcher of ships"])
        paras = rw.text_paras(t, "txt")
        self.assertIn("The lighthouse keeper is a careful watcher of ships", [p.text for p in paras])
        out = rw.place_on_pages([(1, "The lighthouse keeper is a carefulwatcher of ships", 2)], [paras])
        self.assertEqual(out[0][1], "The lighthouse keeper is a careful watcher of ships")
        self.assertEqual(rw.respace_title("Lamp problem scan glow", "Lamp problems can glow"), "Lamp problems can glow")
        self.assertEqual(rw.respace_title("Lamps", "Ships"), "Lamps")

    def test_same_page_outline_entries_get_their_own_text(self):   # L-015: siblings on one page shared one text
        page = ("Harbour chapter\n\nHarbour chapter\nIntro words about the harbour.\nTides and moorings\n"
                "The tide rose twice.\nLamps on the quay\nEvery lamp was trimmed.\n")
        titles = ["Harbour chapter", "Lamps on the quay", "Tides and moorings"]   # outline order differs from the page
        paras = rw.text_paras(rw.isolate_headings(page, titles), "txt")
        out = rw.place_on_pages([(1, t, 2) for t in titles], [paras])
        self.assertEqual([t for _, t, _, _ in out], ["Harbour chapter", "Tides and moorings", "Lamps on the quay"])
        js = [j for _, _, _, j in out]
        self.assertEqual(len(set(js)), 3)
        self.assertEqual(paras[js[1] + 1].text, "The tide rose twice.")
        self.assertEqual(paras[js[2] + 1].text, "Every lamp was trimmed.")

    def test_page_furniture_by_frequency(self):
        P = rw.Para
        pages = [[P("p", "Lamp book"), P("p", "Body text " + " ".join(["lamp", "ship", "quay", "tide"][: n % 4 + 1]) + "x" * n),
                  P("p", "(c) Invented Press. Comment at the quay"), P("p", str(n))] for n in range(1, 9)]
        fur = rw.page_furniture(pages)
        self.assertIn(rw.furniture_key("(c) Invented Press. Comment at the quay"), fur)
        self.assertIn(rw.furniture_key("7"), fur)
        self.assertFalse(any(k.startswith("body text") for k in fur))
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("Lamp book", sum(pages, []), 1, "page1")], furniture=fur)
        self.assertEqual(rw.strip_furniture(doc), 8 * 3 - 1)   # the heading line stays
        self.assertTrue(all("Body text" in p.text for p in doc.sections[0].paras[1:]))

    def test_line_end_hyphens_rejoin(self):
        H = "‐"
        paras = rw.text_paras(f"The conven{H}\ntions of Lang{H}\nChain and soft­\nhyphens, a well-\nknown fact,\nnot a dash -\nOkay.", "txt")
        self.assertEqual(paras[0].text, "The conventions of LangChain and softhyphens, a well-known fact, not a dash - Okay.")
        self.assertEqual(rw.join_lines([f"story{H} telling and pre{H} and post-war"]), f"storytelling and pre{H} and post-war")
        P = rw.Para
        pages = [[P("p", "Some prob" + H)], [P("p", "lems remain."), P("p", "Next.")]]
        rw.join_split_pages(pages)
        self.assertEqual(pages[0][0].text, "Some problems remain.")
        self.assertEqual([p.text for p in pages[1]], ["Next."])

    def test_running_heads_strip_only_at_page_edges(self):
        page = ("4 | Chapter 1: The Five Principles\n\nBody text here.\n\nName | Age | 3\n\nA | 7\n\n"
                "More text.\n\nOverview of the Principles | 5\n")
        out = rw.strip_running_heads(page)
        self.assertNotIn("Chapter 1", out)
        self.assertNotIn("Overview", out)
        self.assertIn("Name | Age | 3", out)
        self.assertIn("A | 7", out)   # not at a page edge
        self.assertIn("Body text here.", out)
        self.assertEqual(rw.strip_running_heads("Name | Age | 3\nrow\nx | y | 9"), "Name | Age | 3\nrow\nx | y | 9")

    def test_pipeless_running_heads_drop(self):
        pages = [f"{n}  Chapter 3: Doing Things\n\nBody {n} text.\n\nInput:\n" if n % 2 else
                 f"Input:\n\nBody {n} text.\n\nSection Title {n}\n" for n in range(1, 13)]
        pages.append("Figure 3-1 shows the output.\n\nOne-off Topic 99\n")
        keys = rw.running_head_keys(pages, ["One-off Topic"])
        out = [rw.strip_running_heads(p, keys) for p in pages]
        joined = "\n".join(out)
        self.assertNotIn("Chapter 3", joined)
        self.assertNotIn("Section Title", joined)
        self.assertNotIn("One-off Topic", joined)   # matches an outline title
        self.assertIn("Input:", joined)              # prose ending in ":" stays, however often
        self.assertIn("Figure 3-1 shows the output.", joined)
        self.assertEqual(joined.count("Body"), 12)
        self.assertEqual(rw.strip_running_heads("7\n\nText.\n", {"#"}), "\n\nText.\n")

    def test_sentence_split_across_page_rejoins(self):
        P = rw.Para
        pages = [[P("p", "you would pass the current user")], [P("p", "message to a store."), P("p", "Next.")],
                 [P("p", "Ends here.")], [P("p", "lower start stays apart.")]]
        rw.join_split_pages(pages)
        self.assertEqual(pages[0][0].text, "you would pass the current user message to a store.")
        self.assertEqual(len(pages[3]), 1)

    def test_book_vocabulary_fixes_splits_and_captions(self):
        rw.VOCAB.update({"tiktoken": 5, "tikto": 1, "ken": 1, "comma": 4, "separated": 4, "commaseparated": 1,
                         "comma-separated": 2, "conven": 1, "tions": 1, "shivam": 1, "shrirao": 1})
        rw.EXACT.update({"tiktoken": 5, "ShivamShrirao": 2})
        rw.COMPOUNDS["commaseparated"] = "comma-separated"
        try:
            self.assertEqual(rw.rejoin_spaced_words("pip install tikto ken now, a commaseparated list"),
                             "pip install tiktoken now, a comma-separated list")
            self.assertEqual(rw.rejoin_spaced_words("by Shivam Shrirao and x.com/commaseparated"),
                             "by Shivam Shrirao and x.com/commaseparated")
            self.assertTrue(rw.keep_break_hyphen("a comma", "separated list"))
            self.assertFalse(rw.keep_break_hyphen("conven", "tions"))
        finally:
            rw.VOCAB.clear(); rw.EXACT.clear(); rw.COMPOUNDS.clear()
        self.assertEqual(rw.CAPTION_SPLIT.split("Some text. Figure 4-6. Refine chain"),
                         ["Some text.", "Figure 4-6. Refine chain"])

    def test_drop_repeated_note_backlinks_in_one_section(self):
        P = rw.Para
        notes = [P("h", "Notes", 1)]
        for n in range(12):
            notes += [P("p", f"claim {n}: A. Author, Paper on " + "lamps quays tides ships ropes sails nets oars masts keels decks hulls".split()[n] + " (2023)."), P("p", "GO TO NOTE REFERENCE IN TEXT")]
        body = rw.Section("One", [P("h", "One", 1), P("p", "Go to the store."), P("p", "Text " * 30)], 1, "s1")
        doc = rw.Doc("x.epub", "epub", sections=[body, rw.Section("Notes", notes, 1, "s2")])
        self.assertEqual(rw.drop_repeated(doc), 12)
        self.assertEqual(len(doc.sections[1].paras), 13)
        self.assertEqual(len(doc.sections[0].paras), 3)


    def test_drop_repeated_credit_lines(self):
        P = rw.Para
        secs = []
        for n in range(10):
            paras = [P("h", f"Shot {n}", 2), P("p", f"Body of shot {n} about " + ["lamps", "quays", "tides", "ships", "ropes"][n % 5] + " and " + "x" * (n + 1) + "."),
                     P("p", "Remember to light the quay."),
                     P("p", f"Invented Film {n}. Directed by Person {n}. Example Studio Video, {1990 + n}. Every Right Kept Here.")]
            if n < 2:
                paras.append(P("p", "A note that appears twice only."))
            secs.append(rw.Section(f"Shot {n}", paras, 1, f"s{n}"))
        doc = rw.Doc("x.epub", "epub", sections=secs)
        self.assertEqual(rw.drop_repeated(doc), 20)   # the credit line (same ending) and the verbatim reminder
        for s in doc.sections:
            texts = [p.text for p in s.paras]
            self.assertEqual(texts[0], s.title)
            self.assertTrue(texts[1].startswith("Body of shot"))
            self.assertFalse(any("Right Kept" in t or "Remember" in t for t in texts))
        self.assertIn("A note that appears twice only.", [p.text for p in doc.sections[0].paras])
        self.assertEqual(rw.repeat_keys(" ".join(["word"] * 50)), [])   # long paragraphs never count

    def test_repeated_section_flags_add_up(self):
        p = self.f("lamps.md")
        p.write_text("# One\n\nAlpha lamp.\n\n# Two\n\nBeta lamp.\n\n# Three\n\nGamma lamp.\n", encoding="utf-8")
        code, out, _ = cli("read", p, "--section", "1", "--section", "3")
        self.assertEqual(code, 0)
        self.assertIn("Alpha", out)
        self.assertIn("Gamma", out)
        self.assertNotIn("Beta", out)
        code, out, _ = cli("grep", p, "lamp", "-s", "2", "-s", "3", "--count")
        self.assertIn("2 matches in 2 sections", out)

    def test_grep_context_widens_over_short_lines(self):   # a boxed callout: one paragraph per PDF line
        p = self.f("box.md")
        words = ["Tip", "keep", "the", "lamp", "trimmed", "before", "dusk", "falls"]
        p.write_text("# Box\n\n" + "\n\n".join(words) + "\n", encoding="utf-8")
        code, out, _ = cli("grep", p, "dusk", "-C", "1")
        self.assertIn("Tip", out)
        self.assertIn("falls", out)

    def test_tool_error_keeps_the_exception_line(self):
        err = b"Traceback (most recent call last):\n  File x, line 1\n    boom()\nsome.module.MissingDependencyException: install markitdown[docx]\n"
        r = subprocess.CompletedProcess([], 1, b"", err)
        self.assertEqual(rw.tool_error(r), "some.module.MissingDependencyException: install markitdown[docx]")


def hidden_path():
    """os.environ patch that hides every external tool: an empty PATH and no install-folder search."""
    return unittest.mock.patch.dict(os.environ, {"PATH": "", "RW_PATH_ONLY": "1"})


def hide_tools(*names):
    return unittest.mock.patch.dict(os.environ, {"RW_HIDE_TOOLS": ",".join(names)})


class TestToolDiscovery(Base):
    def test_missing_tools_are_named(self):
        pdf, mobi, doc, epub = self.f("a.pdf"), self.f("a.mobi"), self.f("a.doc"), self.f("a.epub")
        make_pdf(pdf)
        make_mobi(mobi)
        doc.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
        make_epub(epub)
        with hidden_path():
            for args, needles in (([pdf], ["pdftotext", "Read tool", "Nothing was installed"]),
                                  ([mobi], ["ebook-convert", "calibre"]),
                                  ([doc], ["LibreOffice", "antiword"]),
                                  ([epub, "--via", "pandoc"], ["pandoc"]),
                                  ([epub, "--via", "markitdown"], ["markitdown"])):
                with self.subTest(args=args[1:] or args[0].suffix):
                    code, _, err = cli("info", *args)
                    self.assertEqual(code, 1)
                    for n in needles:
                        self.assertIn(n, err)

    def test_install_folder_found_when_not_on_path(self):
        folder = self.tmp / "Pandoc"
        folder.mkdir()
        exe = folder / ("pandoc.exe" if os.name == "nt" else "pandoc")
        exe.write_bytes(b"")
        exe.chmod(0o755)
        with unittest.mock.patch.dict(os.environ, {"PATH": "", "LOCALAPPDATA": str(self.tmp)}):
            os.environ.pop("RW_PATH_ONLY", None)
            self.assertEqual(os.path.normcase(rw.find_tool("pandoc")), os.path.normcase(str(exe)))


T = rw.tools()


class TestRoutes(unittest.TestCase):
    """Every route through an external tool, on files the tool itself writes from invented text. Skipped when
    the tool is absent; CI installs them on Linux (.github/workflows/tests.yml)."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("RW_REQUIRE_TOOLS") == "1":   # CI's routes job: a missing tool fails instead of skipping
            absent = [k for k, v in T.items() if not v]
            if absent:
                raise AssertionError(f"RW_REQUIRE_TOOLS=1 but these tools are missing: {', '.join(absent)}")
        cls.tmp = Path(tempfile.mkdtemp(prefix="rw-routes-"))
        cls.novel = cls.tmp / "novel.epub"
        make_novel(cls.novel)
        rw.CACHE_OFF = True

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def assert_novel(self, doc, min_chapters=11):
        titles = [s.title for s in doc.sections]
        chapters = [t for t in titles if "CHAPTER" in t.upper()]
        self.assertGreaterEqual(len(chapters), min_chapters, titles)
        words = sum(s.words() for s in doc.sections)
        self.assertGreater(words, 4000)
        hit = [s.title for s in doc.sections if "Quillmere lamp" in rw.render_paras(s.paras)]
        self.assertTrue(hit and "NINE" in hit[0].upper(), (hit, titles))

    @unittest.skipUnless(T["ebook-convert"], "no calibre")
    def test_calibre_kindle_formats(self):
        for ext in ("azw3", "mobi", "lit"):
            with self.subTest(ext=ext):
                out = self.tmp / f"novel.{ext}"
                self.assertTrue(convert(T["ebook-convert"], self.novel, out, timeout=900), ext)
                doc = rw.load(str(out))
                self.assertIn("calibre", doc.notes[-1])
                self.assert_novel(doc)
        prc = self.tmp / "novel.prc"
        shutil.copyfile(self.tmp / "novel.mobi", prc)
        self.assert_novel(rw.load(str(prc)))

    @unittest.skipUnless(T["ebook-convert"], "no calibre")
    def test_calibre_fb2_and_pdb_keep_the_text(self):
        for ext in ("fb2", "pdb"):
            with self.subTest(ext=ext):
                out = self.tmp / f"novel.{ext}"
                r = subprocess.run([str(T["ebook-convert"]), str(self.novel), str(out)], capture_output=True,
                                   timeout=900, stdin=subprocess.DEVNULL)
                err = r.stderr[-1500:].decode("utf-8", "replace")
                if r.returncode and "use_alt_text_for_images" in err:   # calibre's own PDB writer bug (Ubuntu package, 2026-11)
                    continue
                self.assertEqual(r.returncode, 0, (ext, err))
                doc = rw.load(str(out))
                self.assertIn("Quillmere lamp", "".join(rw.render_paras(s.paras) for s in doc.sections))
                self.assertGreater(sum(s.words() for s in doc.sections), 4000)

    @unittest.skipUnless(T["ebook-convert"], "no calibre")
    def test_calibre_conversion_is_cached(self):
        out = self.tmp / "cached.azw3"
        self.assertTrue(convert(T["ebook-convert"], self.novel, out, timeout=900))
        rw.CACHE_OFF = False
        try:
            with unittest.mock.patch.object(rw, "run", wraps=rw.run) as spy:
                rw.load(str(out))
                rw.load(str(out))
            self.assertEqual(sum(1 for c in spy.call_args_list if "ebook-convert" in Path(c.args[0][0]).name.lower()), 1)
        finally:
            rw.CACHE_OFF = True
            rw.cache_path(str(out), "calibre", ".epub").unlink(missing_ok=True)

    @unittest.skipUnless(T["mutool"], "no mutool")
    def test_pdf_outline_from_mutool(self):
        p = self.tmp / "outlined.pdf"
        make_outlined_pdf(p)
        doc = rw.load(str(p))
        self.assertEqual([(s.title, s.level) for s in doc.sections],
                         [("Part One (p. 1-1)", 1), ("Harbour (p. 2-2)", 2), ("Part Two (p. 3-3)", 1), ("Tower (p. 4-4)", 2)])
        self.assertIn("twelve ships", rw.render_paras(doc.sections[1].paras))
        with hide_tools("pdftotext", "pdfinfo"), unittest.mock.patch.object(rw, "run", wraps=rw.run) as spy:
            doc = rw.load(str(p))   # mutool draws the text too
            self.assertIn("tower lamp", rw.render_paras(doc.sections[3].paras))
        self.assertIn("draw", [a for c in spy.call_args_list for a in c.args[0]])

    @unittest.skipUnless(T["soffice"], "no LibreOffice")
    def test_libreoffice_legacy_office(self):
        src = self.tmp / "notes.html"
        src.write_text("<html><body><h1>Harbour</h1><p>The harbour master logged twelve arrivals.</p>"
                       f"<p>{lorem(400)}</p><h1>Weather</h1><p>Fog every morning in March.</p>"   # antiword refuses tiny files
                       "</body></html>", encoding="utf-8")
        doc_file = soffice_convert(src, "doc:MS Word 97", self.tmp)
        self.assertIsNotNone(doc_file)
        doc = rw.load(str(doc_file))
        self.assertEqual(doc.fmt, "doc")
        self.assertEqual([s.title for s in doc.sections], ["Harbour", "Weather"])
        csv_file = self.tmp / "tides.csv"
        csv_file.write_text("date,height\n2026-09-29,4.2\n", encoding="utf-8")
        xls = soffice_convert(csv_file, "xls", self.tmp)
        self.assertIn("2026-09-29\t4.2", rw.render_paras(rw.load(str(xls)).sections[0].paras))
        pdf = self.tmp / "deck.pdf"
        make_pdf(pdf, pages=("Quarterly plan", "Paint the tower"))
        ppt = soffice_convert(pdf, "ppt", self.tmp, ["--infilter=impress_pdf_import"])
        doc = rw.load(str(ppt))
        self.assertEqual(len(doc.sections), 2)
        self.assertIn("Paint the tower", rw.render_paras(doc.sections[1].paras))
        if T["antiword"]:
            with hide_tools("soffice"):
                doc = rw.load(str(doc_file))
                self.assertIn("antiword", doc.notes[-1])
                self.assertIn("twelve arrivals", rw.render_paras(doc.sections[0].paras))

    @unittest.skipUnless(T["pandoc"], "no pandoc")
    def test_via_pandoc(self):
        doc = rw.load(str(self.novel), via="pandoc")
        self.assertEqual(doc.fmt, "epub via pandoc")
        self.assert_novel(doc)
        rtf = self.tmp / "tides.rtf"
        make_rtf(rtf)
        self.assertIn("Café at the pier", "".join(rw.render_paras(s.paras) for s in rw.load(str(rtf), via="pandoc").sections))

    @unittest.skipUnless(T["markitdown"], "no markitdown")
    def test_via_markitdown(self):
        doc = rw.load(str(self.novel), via="markitdown")
        self.assertEqual(doc.fmt, "epub via markitdown")
        self.assert_novel(doc)
        rtf = self.tmp / "tides2.rtf"
        make_rtf(rtf)
        with self.assertRaisesRegex(rw.RWError, "unchanged"):
            rw.load(str(rtf), via="markitdown")


class TestNotesParts(Base):
    def test_untocced_notes_file_after_endnotes_is_titled_as_notes(self):
        x = lambda body: ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"  # noqa: E731
                          + body + "</body></html>")
        notes = "".join(f"<p>{n} https://example.org/source/{n}</p>" for n in range(1, 8))
        navdoc = x("<nav epub:type='toc' xmlns:epub='http://www.idpf.org/2007/ops'><ol>"
                   "<li><a href='ch1.xhtml'>Chapter 1: Tides</a></li><li><a href='notes.xhtml'>Endnotes</a></li>"
                   "<li><a href='index.xhtml'>Index</a></li></ol></nav>")
        files = {"ch1.xhtml": x("<h1>Chapter 1: Tides</h1><p>" + lorem(60) + "</p>"),
                 "notes.xhtml": x("<h1>Endnotes</h1><h2>Chapter 1</h2>" + notes),
                 "notes2.xhtml": x("<h2>Chapter 2</h2>" + notes),
                 "index.xhtml": x("<h1>Index</h1><p>tides, 4</p>"),
                 "nav.xhtml": navdoc}
        ids = ["ch1", "notes", "notes2", "index"]
        opf = ("<?xml version='1.0'?><package xmlns='http://www.idpf.org/2007/opf' version='3.0'><metadata/><manifest>"
               + "".join(f"<item id='{i}' href='{i}.xhtml' media-type='application/xhtml+xml'/>" for i in ids)
               + "<item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/></manifest><spine>"
               + "".join(f"<itemref idref='{i}'/>" for i in ids) + "</spine></package>")
        p = self.f("notes.epub")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                       "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                       "full-path='content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
            z.writestr("content.opf", opf)
            for name, data in files.items():
                z.writestr(name, data)
        titles = [s.title for s in rw.load(str(p)).sections]
        self.assertEqual(titles, ["Chapter 1: Tides", "Endnotes", "Endnotes: Chapter 2", "Index"])
        code, out, _ = cli("note", p, "3", "--section", "1")
        self.assertEqual(code, 0)
        self.assertIn("[chapter 1, note 3] 3 https://example.org/source/3", out)
        code, _, err = cli("note", p, "99", "--section", "1")
        self.assertNotEqual(code, 0)
        self.assertIn("chapter 1, chapter 2", err)


def make_epub_pages(path, bodies, images=None):
    """One EPUB whose spine is `bodies` {name: HTML body}, plus image members {name: bytes}."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                   "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                   "full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
        items = "".join(f"<item id='f{k}' href='{n}' media-type='text/html'/>" for k, n in enumerate(bodies))
        spine = "".join(f"<itemref idref='f{k}'/>" for k in range(len(bodies)))
        z.writestr("OEBPS/content.opf", "<?xml version='1.0'?><package xmlns='http://www.idpf.org/2007/opf' version='2.0'>"
                   f"<metadata/><manifest>{items}</manifest><spine>{spine}</spine></package>")
        for n, body in bodies.items():
            z.writestr("OEBPS/" + n, "<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml' "
                       f"xmlns:xlink='http://www.w3.org/1999/xlink'><body>{body}</body></html>")
        for n, data in (images or {}).items():
            z.writestr("OEBPS/" + n, data)


def caps_book(pages=120):
    """Invented page-long paragraphs the way calibre writes a DjVu's OCR: running heads, inline caps headings."""
    out = []
    chapters = ["HARBOUR LIGHTS", "TIDE TABLES", "ROPE WORK"]
    for n in range(pages):
        ch = chapters[n * len(chapters) // pages]
        head = f"{ch} THE QUILLMERE MANUAL" if n % 2 else f"THE QUILLMERE MANUAL {ch}"
        topic = f"KNOTS FOR WET WEATHER {chr(65 + n // 4) * 2} " if n % 4 == 0 else ""
        out.append(f"{head} {topic}Brannoch coiled the line twice before dawn. " + lorem(110, "gull") + ".")
    return out


NL, FF = chr(10), chr(12)


class TestFiveCs(Base):
    """0.11.0: image-only EPUBs through `rw.py ocr`, inline ALL-CAPS headings, PDF code blocks."""

    def test_epub_page_images_in_spine_order(self):   # L-020 `image-only-epub-ocr`
        p = self.f("scan.epub")
        make_epub_pages(p, {"b.xhtml": "<p><img src='img/p2.jpg'/></p><p><img src='img/p3.jpg'/></p>",
                            "a.xhtml": "<svg><image xlink:href='img/cover.jpg'/></svg>"},
                        {"img/cover.jpg": b"x", "img/p2.jpg": b"x", "img/p3.jpg": b"x"})
        self.assertEqual(rw.epub_page_images(str(p)), ["OEBPS/img/p2.jpg", "OEBPS/img/p3.jpg", "OEBPS/img/cover.jpg"])
        self.assertEqual(rw.epub_page_images(str(self.f("missing.epub"))), [])

    def test_image_only_epub_note_offers_ocr(self):
        p = self.f("scan.epub")
        make_epub_pages(p, {"a.xhtml": "<p><img src='p1.jpg'/></p>"}, {"p1.jpg": b"x"})
        with unittest.mock.patch.object(rw, "ocr_engine", return_value="windows"):
            out = cli("info", p)[1]
        self.assertIn("rw.py ocr", out)
        self.assertNotIn("none is available", out)
        with hide_tools("windows-ocr", "tesseract"):
            out = cli("info", p)[1]
            self.assertIn("neither is available", out)
            code, _, err = cli("ocr", p)
            self.assertIn("no OCR engine", err)
        q = self.f("words.epub")
        make_epub_pages(q, {"a.xhtml": "<p>No pictures at all here.</p>"})
        code, _, err = cli("ocr", q)
        self.assertEqual(code, rw.EXIT_ERR)
        self.assertIn("shows no images", err)

    def test_ocr_cache_feeds_an_image_only_epub(self):
        p = self.f("scan.epub")
        make_epub_pages(p, {"a.xhtml": "".join(f"<p><img src='p{n}.jpg'/></p>" for n in range(3))},
                        {f"p{n}.jpg": b"x" for n in range(3)})
        with unittest.mock.patch.dict(os.environ, {"READWRIGHT_OCR_DIR": str(self.f("ocr"))}):
            c = rw.ocr_cache(str(p))
            c.parent.mkdir(parents=True)
            c.write_bytes(FF.join(["Warm light on the pier. " + lorem(30), "The triple-take of the keeper. " + lorem(30), "Gulls. " + lorem(30)]).encode())
            out = cli("info", p)[1]
            self.assertIn("text from OCR", out)
            self.assertNotIn("no text layer", out)
            code, out, _ = cli("grep", p, "triple-take")
            self.assertEqual(code, rw.EXIT_OK)
            self.assertIn("triple-take of the keeper", out)
            self.assertIn("page 2", cli("toc", p)[1])

    @unittest.skipUnless(rw.ocr_engine() and rw.tools()["mutool"], "no OCR engine or mutool")
    def test_ocr_reads_epub_page_images(self):
        pdf = self.f("one.pdf")
        make_pdf(pdf, pages=("Hello from page one",))
        subprocess.run([rw.tools()["mutool"], "draw", "-q", "-r", "150", "-o", str(self.f("p.png")), str(pdf), "1"], check=True)
        p = self.f("scan.epub")
        make_epub_pages(p, {"a.xhtml": "<p><img src='p.jpg'/></p>"}, {"p.jpg": self.f("p.png").read_bytes()})
        with unittest.mock.patch.dict(os.environ, {"READWRIGHT_OCR_DIR": str(self.f("ocr"))}):
            code, out, err = cli("ocr", p)
            self.assertEqual(code, rw.EXIT_OK, err)
            self.assertIn("on the EPUB now use", out)
            self.assertIn("Hello", cli("grep", p, "Hello")[1])

    def test_inline_caps_headings_split_one_huge_section(self):   # L-021 `inline-caps-headings`
        p = self.f("djvu.epub")
        make_epub_pages(p, {"index.html": "".join(f"<p>{t}</p>" for t in caps_book())})
        doc = rw.load(str(p))
        titles = [(s.title, s.level) for s in doc.sections]
        for ch in ("HARBOUR LIGHTS", "TIDE TABLES", "ROPE WORK"):
            self.assertIn((ch, 1), titles)
            self.assertEqual(sum(1 for t, _ in titles if t == ch), 1, "a running head opens its chapter once")
        self.assertIn(("KNOTS FOR WET WEATHER AA", 2), titles)
        self.assertFalse(any("QUILLMERE" in t for t, _ in titles), "the book's own running title is no section")
        body = rw.render_paras(sum((s.paras for s in doc.sections), []), "txt")
        self.assertNotIn("TIDE TABLES THE", body)
        k = next(i for i, s in enumerate(doc.sections, 1) if s.title == "KNOTS FOR WET WEATHER BB")
        out = cli("read", p, "--section", str(k))[1]
        self.assertIn("Brannoch coiled the line", out)
        self.assertIn("KNOTS FOR WET WEATHER BB", cli("toc", p)[1])

    def test_topic_head_on_facing_pages_is_no_chapter(self):   # OCR'd film book: ACTION AXIS inside CONTINUITY
        pages = caps_book()
        for n in range(48, 64, 2):   # a topic running head on the facing pages, inside TIDE TABLES
            pages[n] = "SPLICE GRADES " + pages[n].split(" ", 3)[3]
        p = self.f("facing.epub")
        make_epub_pages(p, {"index.html": "".join(f"<p>{t}</p>" for t in pages)})
        top = [s.title for s in rw.load(str(p)).sections if s.level == 1]
        self.assertIn("TIDE TABLES", top)
        self.assertNotIn("SPLICE GRADES", top)

    def test_caps_split_leaves_ordinary_text_alone(self):
        paras = [rw.Para("p", "Brannoch went to the NATO office and said OK. " + lorem(150)) for _ in range(40)]
        self.assertIsNone(rw.split_caps(rw.Section("x", paras)))
        txt = self.f("plain.txt")
        txt.write_text((NL + NL).join(caps_book()), encoding="utf-8")
        self.assertIn("TIDE TABLES", [s.title for s in rw.load(str(txt)).sections])

    def test_code_blocks_found_and_kept_as_lines(self):   # L-022 `pdf-code-layout`
        lines = ["The function below returns an area and nothing else at all.", "def area(r):",
                 "return 3.14 * r * r", "x = area(2)", "print(x)", "Then the text goes on as prose for a while."]
        self.assertEqual(rw.code_blocks(lines), [(1, 5)])
        self.assertEqual(rw.code_blocks(["Plain prose line one.", "Another line of prose."]), [])
        layout = NL.join(["  The function below returns an area and nothing else at all.", "      def area(r):",
                          "          return 3.14 * r * r", "      x = area(2)", "      print(x)",
                          "  Then the text goes on as prose for a while."])
        plain = NL.join(["The function below returns an area and nothing else at all. def area(r):",
                         "return 3.14 * r * r x = area(2)", "print(x) Then the text goes on as prose for a while."])
        out = rw.mark_code(plain, layout)
        self.assertIn(NL.join([rw.PRE_OPEN, "def area(r):", "    return 3.14 * r * r", "x = area(2)"]), out)
        self.assertEqual([p.kind for p in rw.text_paras(out, "txt")], ["p", "pre", "p"])

    @unittest.skipUnless(rw.tools()["pdftotext"], "no pdftotext")
    def test_pdf_code_block_keeps_indentation(self):
        p = self.f("code.pdf")
        make_pdf(p, pages=([(72, "Here is a small function for the harbour log."), (72, ""), (72, "def tide(h):"),
                            (100, "if h > 2:"), (128, "return h * 2"), (100, "return h;"), (72, ""),
                            (72, "The keeper then wrote the result down.")],))
        out = cli("read", p)[1]
        self.assertRegex(out, r"def tide.h.:\n\s+if h > 2:\n\s+return h \* 2")


class TestReaderFixes(Base):
    """0.15.0: code listings, the cut footer after --offset, multi-section selectors, grep --after, the continue hint."""

    def code_book(self):
        p = self.f("code.epub")
        nb = chr(0xA0) * 4
        crlf = chr(13) + chr(10)
        listing = f"<pre>{crlf}for gull in harbour.gulls:{crlf}{nb}if gull.wet:{crlf}{nb}{nb}gull.dry(){crlf}{nb}count += 1</pre>"
        split = (f"<pre>{crlf}def tide(h):</pre><pre>{crlf}{nb}if h &gt; 2:</pre><pre>{crlf}{nb}{nb}return h</pre>")
        make_epub_pages(p, {"a.xhtml": "<h1>Gulls</h1><p>The keeper counts gulls with this loop:</p>" + listing
                            + "<p>And a tide helper:</p>" + split + "<p>" + lorem(30) + "</p>"})
        return p

    def test_pre_with_crlf_and_nbsp_keeps_indentation_in_compact_read(self):
        p = self.code_book()
        for extra in ((), ("--compact",)):
            out = cli("read", p, "--section", "1", *extra)[1]
            self.assertNotIn(chr(13), out)
            self.assertNotIn(chr(0xA0), out)
            self.assertIn("for gull in harbour.gulls:" + NL + "    if gull.wet:" + NL + "        gull.dry()" + NL + "    count", out)
            self.assertIn("def tide(h):" + NL + "    if h > 2:" + NL + "        return h", out)

    def test_cut_footer_after_offset_says_how_to_show_the_rest(self):
        p = self.code_book()
        _, full, _ = cli("read", p, "--section", "1", "--quiet")
        _, out, _ = cli("read", p, "--section", "1", "--offset", "20", "--max-chars", "60", "--quiet")
        m = re.search(r"show the rest with --offset 20 --max-chars ([0-9]+)", out)
        self.assertTrue(m, out)
        _, rest, _ = cli("read", p, "--section", "1", "--offset", "20", "--max-chars", m.group(1), "--quiet")
        self.assertNotIn("[readwright: shown chars", rest)
        self.assertEqual(rest, full[20:])
        self.assertNotIn("show it all", out)

    def test_section_list_and_ranges_in_one_call(self):
        t = self.f("big.txt")
        t.write_text("\n\n".join(f"CHAPTER {i}\n\n" + lorem(400, f"word{i}") for i in range(1, 11)), encoding="utf-8")
        out = cli("read", t, "--section", "2,5,8-9", "--quiet")[1]
        self.assertEqual(re.findall(r"=== \[(\d+)/10\]", out), ["2", "5", "8", "9"])

    def test_grep_after_shows_the_code_block_after_a_prose_hit(self):
        p = self.code_book()
        out = cli("grep", p, "counts gulls")[1]
        self.assertNotIn("gull.dry()", out)
        out = cli("grep", p, "counts gulls", "--after", "1")[1]
        self.assertIn("gull.dry()", out)
        self.assertNotIn("tide helper", out)

    def test_short_hint_only_when_the_next_section_continues(self):
        body = "<p>" + lorem(120) + "</p>"
        p = self.f("subs.epub")
        make_epub_pages(p, {"a.xhtml": "<h1>Setup</h1>" + body, "b.xhtml": "<h1>Running</h1>" + body,
                            "c.xhtml": "<h1>Running (continued)</h1>" + body, "d.xhtml": "<h1>Opener</h1><p>An epigraph.</p>",
                            "e.xhtml": "<h1>Body</h1>" + body})
        toc = cli("toc", p)[1]
        self.assertIn("Running (continued)", toc)
        self.assertNotIn("may continue", cli("read", p, "--section", "1")[1])
        self.assertIn("may continue in section 3", cli("read", p, "--section", "2")[1])
        self.assertIn("may continue in section 5", cli("read", p, "--section", "4")[1])


if __name__ == "__main__":
    unittest.main(verbosity=1)
