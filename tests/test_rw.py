#!/usr/bin/env python3
"""Tests for skills/readwright/scripts/rw.py. Standard library only: python tests/test_rw.py

Every fixture is built here at test time from invented text; no real book or document is committed.
"""
import contextlib
import io
import json
import pathlib
import os
import shutil
import re
import subprocess
import sys
import tempfile
import types
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

def make_epub(path, nav=True, ncx=False, encryption=None, extra=None, meta_extra=""):
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
           "<dc:creator>A. Nonymous</dc:creator><dc:language>en</dc:language>" + meta_extra + "</metadata>"
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
            stream = " ".join(f"BT /F1 12 Tf {x} {y[0] if y else 720 - 14 * k} Td ({t}) Tj ET" for k, (x, t, *y) in enumerate(text))
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

    def test_opf_isbn_and_description_entities(self):
        p = self.f("isbn.epub")
        make_epub(p, meta_extra="<dc:identifier>urn:uuid:1234</dc:identifier>"
                                "<dc:identifier>urn:isbn:978-0-00-000000-2</dc:identifier>"
                                "<dc:creator>B. Second</dc:creator><dc:date>2001</dc:date>"
                                "<dc:description>Gulls &amp;#8212; and ledgers</dc:description>")
        code, out, _ = cli("info", p)
        self.assertEqual(code, 0)
        self.assertIn("isbn: 9780000000002", out)
        self.assertIn("author: A. Nonymous; B. Second", out)
        self.assertIn("date: 2001", out)
        self.assertIn("Gulls — and ledgers", out)

    def test_chapter_mini_contents_collapse_to_one_line(self):   # Roads, MIT Press EPUB 2026-11-07
        body = "".join(f"<p class='ctoc'><a href='#s{k}'><b>Head {k}</b></a></p>" for k in range(4))
        body += "".join(f"<h2 id='s{k}'>Head {k}</h2><p>Text {k} with a <a href='#s0'>link</a>.</p>" for k in range(4))
        h = rw.html_paras("<h1>31 Pitch</h1>" + body)
        texts = [p.text for p in h.paras]
        self.assertEqual(texts[1], "[chapter contents: 4 headings; list them with read --headings]")
        self.assertEqual(texts.count("Head 2"), 1)
        self.assertEqual(texts[h.ids["s2"]], "Head 2")
        # two lone links are not a contents run, and links later in the body stay
        h = rw.html_paras("<h1>T</h1><p><a href='#a'>A</a></p><p><a href='#b'>B</a></p><p id='a'>x</p>")
        self.assertEqual([p.text for p in h.paras], ["T", "A", "B", "x"])

    def test_list_in_table_cell_keeps_items_apart(self):
        h = rw.html_paras("<table><tr><td><ol><li>High-yield bonds</li><li>REITs</li><li>Index funds</li></ol></td><td>x</td></tr></table>")
        self.assertEqual(h.paras[-1].text, "High-yield bonds; REITs; Index funds\tx")

    def test_nested_list_items_stay_indented_under_their_parent(self):
        h = rw.html_paras("<ul><li>Top<ul><li>Inner<ul><li>Deep</li></ul></li></ul></li><li>Next</li></ul><p>Body</p><ol><li>One</li></ol>")
        self.assertEqual(rw.render_paras(h.paras), "- Top\n  - Inner\n    - Deep\n- Next\n\nBody\n\n- One")

    def test_block_image_and_math_are_marked(self):
        h = rw.html_paras("<p>We divide one by the other:</p><p class='timage'><img alt='image' src='img/t01.jpg'/></p>"
                          "<p><img alt='A bar chart of gull counts' src='f.png'/></p>"
                          "<p>Area is <math alttext='pi r^2'><mi>r</mi></math> here.</p><p><math><mi>x</mi></math></p>")
        texts = [x.text for x in h.paras]
        self.assertIn("[image omitted: t01.jpg]", texts)
        self.assertIn("[image: A bar chart of gull counts]", texts)
        self.assertIn("Area is [math: pi r^2] here.", texts)
        self.assertIn("[math omitted]", texts)

    def test_read_each_chars_caps_every_section(self):
        p = self.f("each.epub")
        make_epub(p)
        code, out, _ = cli("read", p, "-s", "1-3", "--each-chars", "60")
        self.assertEqual(code, 0)
        for n in (1, 2, 3):
            self.assertIn(f"=== [{n}/3]", out)
        self.assertIn("section 2 cut at chars 0-", out)
        self.assertIn("continue with --section 2 --offset", out)
        self.assertNotIn("ledger listed every ship", out)

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

    def test_lead_in_colon_points_to_the_entries_after_it(self):   # Sound Effects Bible ch. 18: lists live in subsections
        p = self.f("enc.md")
        p.write_text("# Explosions\n\nThey have three parts, and here is the approach:\n\n## Concussion\n\nA blast first.\n\n"
                     "## Debris\n\nThen bits fall.\n\n# Fire\n\nFlames crackle and roar in the night.\n", encoding="utf-8")
        code, out, _ = cli("read", str(p), "--section", "1")
        self.assertIn("lead-in (a colon)", out)
        self.assertIn("read 2-3 with --section", out)
        self.assertNotIn("lead-in", cli("read", str(p), "--section", "1-3")[1])   # entries already selected
        self.assertNotIn("lead-in", cli("read", str(p), "--section", "4")[1])


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

    def test_index_anchor_leaves_no_space_before_punctuation(self):   # O'Reilly EPUB, 2026-11-05
        p = self.f("idx.html")
        p.write_text('<html><body><h1>T</h1><p>Watch cost <a data-type="indexterm" id="i1"></a> <a id="i2"></a>. See <a href="#x">Chapter 4</a> <a id="i3"></a>, (<a href="#y">Figure 1</a>' + chr(10) + ' ) and keep <a id="i4"></a>words apart.</p></body></html>', encoding="utf-8")
        body = rw.render_paras(rw.load(str(p)).sections[0].paras)
        self.assertIn("Watch cost. See Chapter 4, (Figure 1) and keep words apart.", body)

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
        self.assertIn("rw.py page", out)
        self.assertNotIn("mutool draw", out)
        self.assertNotIn("pdftoppm -r", out)
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

    def test_missing_scan_pages_are_flagged(self):   # Detail in Typography: two spreads absent from a 31-image scan
        pages = ["Contents\n7\n63"] + [f"Body\n{n}\nBody\n{n + 1}" for n in range(8, 20, 2)] + \
                [f"Figure\n57\nBody\n{n}\nBody\n{n + 1}" for n in range(22, 30, 2)]
        note = rw.missing_page_note(pages)
        self.assertIn("between p. 19", note)
        self.assertIn("and p. 23", note)
        whole = [f"Body\n{n}\nBody\n{n + 1}" for n in range(8, 30, 2)]
        self.assertIsNone(rw.missing_page_note(whole))
        self.assertIsNone(rw.missing_page_note(["no numbers"] * 12))

    def test_printed_page_offset(self):   # L-019: printed page = PDF page + 1 in a scanned art book
        pages = [f"Body text\n{n + 1}" for n in range(1, 9)] + ["Cover"]
        self.assertEqual(rw.printed_offset(pages), 1)
        self.assertEqual(rw.printed_offset([f"Text\n{n}" for n in range(1, 9)]), 0)
        self.assertEqual(rw.printed_offset(["12\nx", "y"]), 0, "one numbered page is not enough")

    def test_printed_labels_follow_a_drifting_offset(self):   # L-034: a dropped page per chapter moves the offset
        heads = [f"{n - 10} A. STYHRE\nBody" if n % 2 else f"SOCIAL NORMS {n - 10}\nBody" for n in range(11, 21)]
        opener = ["Chapter title\nBody\n© The Author(s) 2020\n12\nA. Styhre, Indie Work,\nhttps://doi.org/x"]
        tail = [f"{n - 9} A. STYHRE\nBody" for n in range(22, 30)]
        pages = ["Cover"] * 10 + heads + opener + tail
        labels = rw.printed_labels(pages)
        self.assertEqual(rw.printed_offset(pages), 0, "no single shift")
        self.assertEqual(labels[11], 1)
        self.assertEqual(labels[20], 10)
        self.assertEqual(labels[22], 13)
        self.assertNotIn(1, labels, "the cover carries no number")
        self.assertEqual(rw.printed_labels(["Body\n3", "Text", "y"]), {}, "too few pages agree")
        doc = rw.Doc("x.pdf", "pdf")
        doc.sections = [rw.Section(f"page {n}", [], 1, f"page{n}") for n in range(1, 30)]
        doc.meta["printed_labels"] = labels
        self.assertEqual(rw.printed_selector(doc, "p10-p13"), "20-22")
        self.assertEqual(rw.printed_selector(doc, "p1-3,25"), "11-13,25")
        with self.assertRaises(rw.RWError):
            rw.printed_selector(doc, "p999")
        doc.meta = {"page_shift": 2}
        self.assertEqual(rw.printed_selector(doc, "p12"), "10")

    def test_printed_pages_with_sub_headings_map_to_all_their_sections(self):
        # An outline with sub-headings gives a page several sections, so section number and page differ.
        doc = rw.Doc("x.pdf", "pdf")
        doc.sections = [rw.Section(f"s{i}", [], 1, sid) for i, sid in enumerate(
            ["page1", "page2", "page2", "page3", "page3", "page3", "page6"], 1)]
        doc.meta = {"page_shift": -1}   # printed N is on PDF page N + 1
        self.assertEqual(rw.printed_selector(doc, "p1"), "2-3")
        self.assertEqual(rw.printed_selector(doc, "p1-p2"), "2-6")
        self.assertEqual(rw.printed_selector(doc, "p4"), "6", "inside a longer section: that section")
        self.assertEqual(rw.select(doc, "p1,p5", None), [2, 3, 7])

    def test_min_para_words_drops_short_body_paragraphs_only(self):
        doc = rw.Doc("x", "txt")
        doc.sections = [rw.Section("s", [rw.Para("h", "Hi"), rw.Para("p", "x y"), rw.Para("p", "one two three four")])]
        self.assertEqual(rw.drop_short_paras(doc, 3), 1)
        self.assertEqual([q.text for q in doc.sections[0].paras], ["Hi", "one two three four"])

    def test_grep_without_i_names_case_hits(self):
        p = self.f("t.md")
        p.write_text("# One\n\nValue keying sets the mood.\n", encoding="utf-8")
        code, out, _ = cli("grep", p, "Value Key")
        self.assertEqual(code, 1)
        self.assertIn("1 matches with -i", out)

    def test_grep_matches_typographic_hyphen_and_apostrophe(self):   # L-057
        p = self.f("t.md")
        p.write_text("# One\n\nThe self‐employment tax is the owner’s cost.\n\nA self-employment note.\n", encoding="utf-8")
        _, out, _ = cli("grep", p, "self-employment", "--count")
        self.assertIn("2", out)
        self.assertEqual(cli("grep", p, "self‐employment")[0], 0)
        self.assertEqual(cli("grep", p, "owner's", "-F")[0], 0)
        self.assertEqual(rw.loose_typography("[a-z]+"), "[a-z]+", "a class range stays a range")
        self.assertEqual(rw.loose_typography("(?-i:x)"), "(?-i:x)", "inline flags stay")
        self.assertTrue(re.search(rw.loose_typography(re.escape("a-b")), "a‐b"))

    def test_grep_names_the_paragraph_read(self):
        p = self.f("t.md")
        p.write_text("# One\n\nFirst para.\n\nA long lead then the needle here.\n", encoding="utf-8")
        _, out, _ = cli("grep", p, "needle")
        para = re.search(r"para (\d+)/", out).group(1)
        self.assertIn(f"--at-para {para}", out)
        _, read, _ = cli("read", p, "--section", "1", "--at-para", para)
        self.assertIn("A long lead", read)

    def test_grep_and_headings_quiet(self):   # Dooley read for multi-agent-grind: grep refused -q
        p = self.f("t.md")
        p.write_text("# One\n\n## Sub\n\nA needle here.\n", encoding="utf-8")
        code, out, _ = cli("grep", p, "needle", "-q")
        self.assertEqual(code, 0)
        self.assertNotIn("[readwright:", out)
        self.assertIn("1 matches", out)
        _, out, _ = cli("read", p, "--section", "1", "--headings", "-q")
        self.assertNotIn("jump to one", out)

    def test_grep_smart_case(self):   # L-038: an all-lower-case pattern matches any case
        p = self.f("t.md")
        p.write_text("# One\n\nThe Consumer Price Index rose.\n", encoding="utf-8")
        code, out, _ = cli("grep", p, "consumer price index")
        self.assertEqual(code, 0)
        self.assertIn("Consumer Price Index", out)
        self.assertEqual(cli("grep", p, "consumer price index", "--case-sensitive")[0], 1)
        self.assertEqual(cli("grep", p, "Consumer price")[0], 1, "a capital keeps grep case-sensitive")
        self.assertTrue(rw.smart_case(r"\Sprice\b"), "regex escapes are not capitals")
        self.assertFalse(rw.smart_case("CPI"))

    def test_page_copyright_footer_dropped(self):   # L-037: a long publisher footer on every page
        P = rw.Para
        foot = ("Copyright 2013 Example Learning. All Rights Reserved. May not be copied, scanned, or duplicated, in whole "
                "or in part. " + "Some third party content may be suppressed. " * 6)
        second = "Editorial review has deemed that any suppressed content does not affect the experience."
        pages = [[P("p", f"Body text of page {n} about lamps."), P("p", foot), P("p", second)] for n in range(10)]
        pages[3].append(P("p", "Copyright law is a topic of this page."))
        self.assertEqual(rw.drop_page_footers(pages), 20)
        self.assertTrue(all(len(pp) == 1 for pp in pages[:3]))
        self.assertIn("Copyright law is a topic of this page.", [q.text for q in pages[3]])
        few = [[P("p", "Body"), P("p", foot)] for _ in range(10)]
        few = few[:2] + [[P("p", "Body")] for _ in range(8)]
        self.assertEqual(rw.drop_page_footers(few), 0, "a footer on two pages of ten stays")
        with unittest.mock.patch.dict(os.environ, {"RW_KEEP_FOOTERS": "1"}):
            self.assertEqual(rw.drop_page_footers([[P("p", foot)] for _ in range(10)]), 0)

    def test_outline_titles_carry_printed_pages(self):   # L-035: outline sections show the printed folio
        self.assertEqual(rw.printed_span(165, 170, -36, {}), ", printed 129-134")
        self.assertEqual(rw.printed_span(5, 5, -36, {}), "", "front matter before page 1 has no printed number")
        self.assertEqual(rw.printed_span(20, 22, 0, {20: 10, 22: 13}), ", printed 10-13")
        self.assertEqual(rw.printed_span(3, 4, 0, {}), "")
        heads = [f"{n - 10} PART 2 Macroeconomic Fundamentals\nBody" if n % 2 else
                 f"Chapter 6 Prices and Unemployment {n - 10}\nBody" for n in range(11, 21)]
        labels = rw.printed_labels(["Cover"] * 10 + heads + [f"{n - 9} PART 2 Fundamentals\nBody" for n in range(22, 30)])
        self.assertEqual(labels[11], 1)
        self.assertEqual(labels[12], 2)
        self.assertEqual(labels[21], 13)

    @unittest.skipUnless(rw.find_tool("pdffonts") and rw.find_tool("pdftotext"), "needs poppler")
    def test_symbol_font_math_warning(self):   # L-036: '=' prints as '5' in a Mathematical Pi font
        p = self.f("m.pdf")
        make_pdf(p, ("Price index 5 100 3 cost", "More text"))
        p.write_bytes(p.read_bytes().replace(b"/Helvetica", b"/MathPiAbc"))
        code, out, _ = cli("info", p)
        self.assertIn("math symbols are likely garbled", out)
        q = self.f("plain.pdf")
        make_pdf(q)
        self.assertNotIn("math symbols", cli("info", q)[1])

    def test_dingbat_bullets_become_list_items(self):   # L-077: Holman's AdvPi bullets read as 'l'
        self.assertEqual(rw.dingbat_bullets("One breakdown:\nl Dialog l Foley l Music\nl Custom recordings. More"),
                         "One breakdown:\n- Dialog\n- Foley\n- Music\n- Custom recordings. More")
        self.assertEqual(rw.dingbat_bullets("l is a letter\nlater l Text"), "l is a letter\nlater l Text")
        p = self.f("b.pdf")
        make_pdf(p, ("l First item", "More text"))
        p.write_bytes(p.read_bytes().replace(b"/Helvetica", b"/AdvPi1"))
        if rw.tools().get("pdffonts"):
            self.assertIn("- First item", cli("read", p, "--section", "1")[1])

    def test_rank_puts_the_dense_short_section_first(self):
        p = self.f("ir.md")
        p.write_text("# Long\n\n" + "Crawlers fetch pages. " * 200 + "One shingle here.\n\n"
                     "# Dupes\n\nNear duplicate pages share shingles; shingling finds near duplicates.\n\n"
                     "# Other\n\nNothing relevant.\n", encoding="utf-8")
        code, out, _ = cli("rank", p, "near", "duplicates", "shingling")
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[0].strip().split("  ")[1].startswith("[2] Dupes"), out)
        self.assertNotIn("Other", out)
        code, out, _ = cli("rank", p, "shingle", "--paras", "--json")
        self.assertEqual(json.loads(out)["results"][0]["section"], 2)
        code, out, _ = cli("rank", p, "zebra")
        self.assertEqual(code, 1)
        self.assertIn("not in the book: zebra", out)

    def test_rank_body_leaves_out_notes_and_bibliography(self):
        p = self.f("hist.md")
        p.write_text("# Prices\n\n" + "Inflation rose with wages. " * 40 + "\n\n# NOTES\n\nInflation inflation inflation.\n\n"
                     "# Chapter notes\n\nInflation inflation sources.\n\n# BIBLIOGRAPHY\n\nInflation works.\n", encoding="utf-8")
        code, out, _ = cli("rank", p, "inflation")
        self.assertIn("Chapter notes", out)
        code, out, _ = cli("rank", p, "inflation", "--body")
        self.assertEqual(code, 0)
        self.assertIn("Prices", out)
        for hidden in ("NOTES", "Chapter notes", "BIBLIOGRAPHY"):
            self.assertNotIn(hidden, out)

    def test_rank_body_keeps_an_early_notes_section(self):
        p = self.f("early.md")
        p.write_text("# Notes\n\nInflation first.\n\n# Prices\n\n" + "Inflation rose. " * 40 + "\n", encoding="utf-8")
        code, out, _ = cli("rank", p, "inflation", "--body")
        self.assertIn("Notes", out)

    def test_rank_terms_fold_endings_and_stop_words(self):
        self.assertEqual(rw.rank_terms("The shingles of shingling"), ["shingl", "shingl"])
        self.assertEqual(rw.rank_terms("queries"), ["query"])
        self.assertEqual(rw.rank_terms("page pages uses use"), ["pag", "pag", "use", "use"])
        self.assertEqual(rw.rank_terms("class"), ["class"])

    def test_grep_with_swapped_arguments_says_file_first(self):
        p = self.f("t.md")
        p.write_text("# One\n\nchampion list\n", encoding="utf-8")
        code, _, err = cli("grep", "champion list", p)
        self.assertEqual(code, rw.EXIT_ERR)
        self.assertIn("the file goes first", err)

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



class TestColonHeads(unittest.TestCase):
    def test_spaced_and_left_hand_heads_go(self):
        pages = [f"T h e B a c k g r o u n d to 1 9 4 5 : {n} wire that ran on {n}" for n in range(11, 16)]
        pages += ["1 6 : The B a c k g r o u n d to 1945 thesis faced a test", "Plain page: 3 of the rest"]
        out = rw.strip_colon_heads(pages)
        self.assertEqual(out[0], "wire that ran on 11")
        self.assertEqual(out[5], "thesis faced a test")
        self.assertEqual(out[6], pages[6])

    def test_few_repeats_stay(self):
        pages = [f"Table of results : {n} was the score" for n in range(4)]
        self.assertEqual(rw.strip_colon_heads(pages), pages)


class TestFixedLayout(unittest.TestCase):
    def test_lines_and_italic_runs_rejoin(self):
        lines = ["PREFACE", "The article covered the design of", "2001: A Space Odyssey,", "posted on my site. It went",
                 "viral and the host billed me. Then", "came the uncer-", "tainty."]
        out = rw.merge_fixed_layout([rw.Para("p", t) for t in lines])
        self.assertEqual(out[0].text, "PREFACE")
        self.assertIn("design of 2001: A Space Odyssey, posted on my site.", out[1].text)
        self.assertIn("uncer-tainty.", out[-1].text)

    def test_capital_title_mid_sentence_stays_inline(self):
        out = rw.merge_fixed_layout([rw.Para("p", t) for t in ["The design of", "WALL-E", ".", "EGGLESTON", ": It was hope."]])
        self.assertEqual(out[0].text, "The design of WALL-E.")
        self.assertEqual(out[1].text, "EGGLESTON: It was hope.")

    def test_line_break_hyphen_goes_when_the_book_has_the_word(self):
        sec = rw.Section("s", [rw.Para("p", "We keep explain-ing a well-known point while explaining it.")], 1, "x")
        rw.unbreak_fixed_layout([sec])
        self.assertEqual(sec.paras[0].text, "We keep explaining a well-known point while explaining it.")

    def test_sentence_end_starts_a_new_paragraph(self):
        out = rw.merge_fixed_layout([rw.Para("p", "One ends here."), rw.Para("p", "Two starts here")])
        self.assertEqual([p.text for p in out], ["One ends here.", "Two starts here"])


class TestFixedLayoutCaptions(Base):
    def book(self, caption_px=40, pages=None):
        """A fixed-layout EPUB made the way PDF converters make one: one block per line, sizes in per-page classes."""
        css = f".b {{ FONT-SIZE: 55px; }} .c {{ font-size: {caption_px}px; }} .f {{ font-size: 30px; }} .l {{ font-size: 20px; }}"
        pages = pages or [
            [("b", "The opening sentence runs across"), ("c", "A ship seen from below."), ("l", "TOP:"), ("c", "A second shot.")],
            [("b", "the page turn and ends here."), ("b", "Another sentence follows."), ("c", "A door in the hull.")],
            [("b", "Third page text ends."), ("c", "A bridge console.")],
            [("b", "Fourth page text ends."), ("c", "A long corridor.")],
        ]
        css += "".join(f" #p{n}f {{ left: 9px; top: 900px; }}" for n in range(len(pages)))
        path = self.f("fixed.epub")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="OEBPS/p.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            items = "".join(f'<item id="p{n}" href="p{n}.xhtml" media-type="application/xhtml+xml"/>' for n in range(len(pages)))
            refs = "".join(f'<itemref idref="p{n}"/>' for n in range(len(pages)))
            z.writestr("OEBPS/p.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                       f'<dc:title>Fixed</dc:title></metadata><manifest><item id="n" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>{items}</manifest>'
                       f'<spine>{refs}</spine></package>')
            z.writestr("OEBPS/nav.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><nav><ol><li><a href="p0.xhtml">One</a></li></ol></nav></body></html>')
            z.writestr("OEBPS/s.css", css)
            for n, runs in enumerate(pages):
                blocks = "".join(f'<div class="container"><div id="p{n}t{k}" class="t {c}">{t}</div></div>' for k, (c, t) in enumerate(runs))
                z.writestr(f"OEBPS/p{n}.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><head><meta name="viewport" content="width=800px;, height=1000px;"/>'
                           f'<link href="s.css" rel="stylesheet"/></head><body><div class="container"><div id="p{n}f" class="t f">{n + 1}</div></div>{blocks}</body></html>')
        return path

    def test_captions_leave_the_body_and_are_marked(self):
        paras = [p.text for p in rw.load_epub(str(self.book())).sections[0].paras]
        self.assertIn("The opening sentence runs across the page turn and ends here.", paras)
        self.assertIn("[caption] A ship seen from below.", paras)
        self.assertIn("[caption] TOP:", paras)
        self.assertIn("1", paras)   # the folio stays, on its own
        self.assertFalse([t for t in paras if "caption" not in t and ("ship" in t or "door" in t.lower())])
        self.assertGreater(paras.index("[caption] A ship seen from below."), paras.index("The opening sentence runs across the page turn and ends here."))

    def test_no_smaller_type_changes_nothing(self):
        paras = [p.text for p in rw.load_epub(str(self.book(caption_px=55))).sections[0].paras]
        self.assertFalse([t for t in paras if "[caption]" in t])
        self.assertTrue(any("ship seen" in t for t in paras))

    def test_rare_small_type_is_not_a_caption_size(self):
        pages = [[("b", "Body text of some length that goes on for a while and then ends.")] for _ in range(11)] + [[("c", "Colophon.")]]
        paras = [p.text for p in rw.load_epub(str(self.book(pages=pages))).sections[0].paras]
        self.assertIn("Colophon.", " ".join(paras))
        self.assertFalse([t for t in paras if "[caption]" in t])

    def test_page_with_no_body_type_is_left_unmarked(self):
        doc_pages = [[("b", "Body text ends."), ("c", "A ship.")] for _ in range(5)] + [[("c", "Thanks to my friends.")]]
        paras = [p.text for p in rw.load_epub(str(self.book(pages=doc_pages))).sections[0].paras]
        self.assertIn("Thanks to my friends.", paras)
        self.assertIn("[caption] A ship.", paras)


class TestCharsetHints(Base):
    META = '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1"/>'

    def book(self, body: bytes):
        path = self.f("meta.epub")
        head = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><head><title>t</title>" + self.META + "</head><body>").encode("ascii")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="p.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            z.writestr("p.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>M</dc:title></metadata>'
                       '<manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/></spine></package>')
            z.writestr("a.xhtml", head + body + b"</body></html>")
        return path

    def test_utf8_beats_a_latin1_meta_in_body_and_titles(self):
        body = "<h1>Schön Don’t</h1><p>Don’t walk to Köln.</p><p> </p><p>End.</p>".encode("utf-8")
        doc = rw.load_epub(str(self.book(body)))
        self.assertEqual(doc.sections[0].title, "Schön Don’t")
        self.assertEqual([p.text for p in doc.sections[0].paras if p.kind == "p"], ["Don’t walk to Köln.", "End."])   # no blank paragraph from the no-break space

    def test_real_latin1_still_reads(self):
        doc = rw.load_epub(str(self.book("<h1>Schön</h1><p>Café in Köln.</p>".encode("latin-1"))))
        self.assertEqual(doc.sections[0].title, "Schön")
        self.assertIn("Café in Köln.", [p.text for p in doc.sections[0].paras])

    def test_decode_order(self):
        self.assertEqual(rw.decode_text("ö".encode("utf-8"), "iso-8859-1"), "ö")
        self.assertEqual(rw.decode_text("ö x".encode("latin-1"), "iso-8859-1"), "ö x")
        self.assertEqual(rw.decode_text("’".encode("cp1252")), "’")
        self.assertEqual(rw.decode_text(b"hi", "no-such-codec"), "hi")
        wide = "ab".encode("utf-16-le")   # no BOM, and also valid UTF-8
        wide.decode("utf-8")
        for hint in ("utf-16-le", "UTF_16LE"):
            self.assertEqual(rw.decode_text(wide, hint), "ab")
        self.assertEqual(rw.decode_text("ab".encode("utf-32-le"), "utf-32-le"), "ab")


class TestFixedLayoutMarkers(Base):
    """Pictures and page numbers set between the lines of a sentence stay out of it, with or without a caption size."""
    book = TestFixedLayoutCaptions.book

    def texts(self, pages, **kw):
        return [p.text for p in rw.load_epub(str(self.book(pages=pages, **kw))).sections[0].paras]

    def test_below_the_caption_rule(self):   # all one size, so no caption plan
        pages = [[("b", "The sentence starts"), ("b", '<img src="a.jpg" alt=""/>'), ("b", "and ends here.")], [("b", "Second page starts")],
                 [("b", "and runs over.")], [("b", "Fourth page.")]]
        paras = self.texts(pages, caption_px=55)
        self.assertIn("The sentence starts and ends here.", paras)
        self.assertIn("[image omitted: a.jpg]", paras)
        self.assertIn("Second page starts and runs over.", paras)
        for n in "1234":
            self.assertIn(n, paras)

    def test_marker_with_alt_text_under_a_caption_plan(self):
        pages = [[("b", "The sentence starts"), ("b", '<img src="a.jpg" alt="A red ship"/>'), ("b", "and ends here."), ("c", "A ship.")],
                 [("b", "Page two."), ("c", "A door.")], [("b", "Page three."), ("c", "A bridge.")], [("b", "Page four."), ("c", "A hall.")]]
        paras = self.texts(pages)
        self.assertIn("The sentence starts and ends here.", paras)
        self.assertIn("[image: A red ship]", paras)

    def test_a_number_that_is_not_the_folio_stays_in_the_sentence(self):
        pages = [[("b", "It was the year"), ("b", "1984"), ("b", "and it rained.")], [("b", "Page two.")], [("b", "Page three.")], [("b", "Page four.")]]
        self.assertIn("It was the year 1984 and it rained.", self.texts(pages, caption_px=55))

    def test_numbers_that_do_not_rise_are_not_folios(self):
        self.assertEqual(rw.fixed_folio_lines([(i, [rw.Para("p", "7")]) for i in range(6)]), set())
        self.assertEqual(len(rw.fixed_folio_lines([(i, [rw.Para("p", str(i + 9))]) for i in range(6)])), 6)

    def test_spread_of_two_pages_a_file(self):
        pages = [(i, [rw.Para("p", "Some text."), rw.Para("p", str(2 * i + 4)), rw.Para("p", str(2 * i + 5))]) for i in range(6)]
        self.assertEqual(len(rw.fixed_folio_lines(pages)), 12)

    def test_roman_front_matter(self):
        romans = ["v", "vi", "vii", "viii", "ix", "x"]
        pages = [(i, [rw.Para("p", "Text."), rw.Para("p", r)]) for i, r in enumerate(romans)]
        pages += [(i + 6, [rw.Para("p", "Text."), rw.Para("p", str(i + 1))]) for i in range(30)]
        found = rw.fixed_folio_lines(pages)
        self.assertEqual(len(found), 36)
        self.assertIn((5, "x"), found)
        self.assertEqual(rw.roman_value("xiv"), 14)

    def test_a_lone_letter_i_is_not_a_folio(self):
        pages = [(i, [rw.Para("p", "i")]) for i in range(6)]
        self.assertEqual(rw.fixed_folio_lines(pages), set())


class TestPageCommand(Base):
    def setUp(self):
        super().setUp()
        self.pdf = self.f("three.pdf")
        make_pdf(self.pdf, ("one", "two", "three"))

    def need_renderer(self):
        if not (rw.tools()["mutool"] or rw.find_tool("pdftoppm")) or not (rw.tools()["pdftotext"] or rw.tools()["mutool"]):
            self.skipTest("no PDF renderer")

    def test_renders_listed_pages(self):
        self.need_renderer()
        code, out, err = cli("page", str(self.pdf), "1,3", "--out-dir", str(self.f("o")))
        self.assertEqual(code, 0, err)
        paths = out.split()
        self.assertEqual([Path(p).name for p in paths], ["three-p1.png", "three-p3.png"])
        for p in paths:
            self.assertEqual(Path(p).read_bytes()[:4], b"\x89PNG")

    def test_range_and_out_of_range(self):
        self.need_renderer()
        code, out, _ = cli("page", str(self.pdf), "2-3", "--out-dir", str(self.f("o")))
        self.assertEqual((code, len(out.split())), (0, 2))
        code, _, err = cli("page", str(self.pdf), "4", "--out-dir", str(self.f("o")))
        self.assertNotEqual(code, 0)
        self.assertIn("out of range", err)

    def test_not_a_pdf(self):
        t = self.f("a.txt")
        t.write_text("plain", encoding="utf-8")
        code, _, err = cli("page", str(t), "1")
        self.assertNotEqual(code, 0)
        self.assertIn("PDF", err)

    def test_no_renderer_says_so(self):
        with unittest.mock.patch.object(rw, "tools", return_value={"mutool": None}), unittest.mock.patch.object(rw, "find_tool", return_value=None):
            code, _, err = cli("page", str(self.pdf), "1")
        self.assertNotEqual(code, 0)
        self.assertIn("mutool", err)

    def test_bad_list(self):
        self.assertRaises(rw.RWError, rw.page_numbers, "x", 3)
        self.assertRaises(rw.RWError, rw.page_numbers, "3-2", 3)
        self.assertEqual(rw.page_numbers("3,1-2,2", 3), [1, 2, 3])


class TestScrambledNote(unittest.TestCase):
    def doc(self, text, fmt="pdf", notes=()):
        return rw.Doc("x.pdf", fmt, sections=[rw.Section("s", [rw.Para("p", text)])], notes=list(notes))

    def test_glued_words_are_noted(self):
        text = " ".join(["plain words here"] * 300 + ["rememberthatwhateverthey", "populationforeveryone"] * 3)
        note = rw.scrambled_note(self.doc(text))
        self.assertIn("scrambled", note)
        self.assertIn("rw.py ocr", note)
        self.assertIn("rw.py page", note)

    def test_clean_text_and_lone_long_words_are_not(self):
        self.assertIsNone(rw.scrambled_note(self.doc(" ".join(["plain words here"] * 300))))
        self.assertIsNone(rw.scrambled_note(self.doc(" ".join(["plain words here"] * 9000 + ["internationalization"] * 6))))

    def test_urls_and_identifiers_do_not_count(self):
        text = " ".join(["plain words"] * 50 + ["example.com/averyveryverylongpathsegment", "averyveryverylongidentifiername_x"] * 9)
        self.assertIsNone(rw.scrambled_note(self.doc(text)))

    def test_only_for_a_pdf_not_yet_ocrd(self):
        glued = " ".join(["rememberthatwhateverthey"] * 9)
        self.assertIsNone(rw.scrambled_note(self.doc(glued, "epub")))
        self.assertIsNone(rw.scrambled_note(self.doc(glued, notes=["text from OCR (`rw.py ocr`)"])))

    def test_read_text_is_untouched(self):
        d = self.doc(" ".join(["rememberthatwhateverthey"] * 9))
        before = d.sections[0].paras[0].text
        rw.scrambled_note(d)
        self.assertEqual(d.sections[0].paras[0].text, before)
        self.assertFalse(d.notes)


class TestCommands(Base):
    def big_text(self):
        t = self.f("big.txt")
        t.write_text("\n\n".join(f"CHAPTER {i}\n\n" + "\n\n".join(lorem(400, "Brannoch" if i == 7 else "lorem") for _ in range(5))
                                 for i in range(1, 11)), encoding="utf-8")
        return t

    def test_read_chapter_uses_printed_numbers(self):
        t = self.f("big.txt")
        t.write_text("\n\n".join(f"CHAPTER {i}\n\n" + "\n\n".join(lorem(400, f"word{i}") for _ in range(3))
                                 for i in range(1, 11)), encoding="utf-8")
        out = cli("read", t, "--chapter", "7")[1]
        self.assertIn("word7", out)
        self.assertNotIn("word6", out)
        self.assertNotEqual(cli("read", t, "--chapter", "77")[0], 0)

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
        self.assertEqual(cli("read", t, "--section", "2", "--compact", "--at-para", "1")[0], 0)

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

    def test_grep_per_section_spreads_hits(self):
        t = self.big_text()
        code, all_out, _ = cli("grep", t, "e", "--max", "500")
        code, out, _ = cli("grep", t, "e", "--per-section", "1", "--max", "500")
        self.assertEqual(code, 0)
        heads = re.findall(r"--- \[(\d+)\]", out)
        self.assertEqual(len(heads), len(set(heads)))
        self.assertGreater(len(set(heads)), 1)
        self.assertIn("past --per-section 1 not shown", out)
        self.assertLess(out.count("--- ["), all_out.count("--- ["))

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

    def test_read_from_skips_the_header_line(self):   # --from on a word in the chapter title cut into the header, 2026-11-06
        import tempfile
        t = os.path.join(tempfile.mkdtemp(), "b.md")
        with open(t, "w", encoding="utf-8") as f:
            f.write("# Plan and design documents\n\nOpening words.\n\nThe design documents come later.\n")
        code, got, _ = cli("read", t, "--title", "Plan", "--from", "design documents")
        self.assertEqual(code, 0)
        self.assertNotIn("| id ", got)
        self.assertIn("come later", got)

    def test_read_from_regex(self):
        t = self.big_text()
        code, got, _ = cli("read", t, "--section", "7", "--from", "Brannoch", "--max-chars", "200")
        self.assertEqual(code, 0)
        self.assertIn("Brannoch", got.split("\n")[1][:8])
        self.assertEqual(cli("read", t, "--section", "7", "--from", "no such words xyz")[0], 1)
        self.assertEqual(cli("read", t, "--section", "7", "--from", "(")[0], 1)
        self.assertEqual(cli("read", t, "--section", "7", "--from", "Brannoch", "--at-para", "1")[0], 1)

    def test_read_until_regex(self):
        t = self.big_text()
        whole = cli("read", t, "--section", "7")[1]
        word = "Brannoch"
        code, got, _ = cli("read", t, "--section", "7", "--until", word)
        self.assertEqual(code, 0)
        self.assertNotIn(word, got)
        self.assertTrue(whole.startswith(got.rstrip()), got[-80:])
        self.assertLess(len(got), len(whole))
        # no match: whole, with a note
        code, got, _ = cli("read", t, "--section", "7", "--until", "no such words xyz")
        self.assertEqual(code, 0)
        self.assertTrue(got.startswith(whole.split("[readwright")[0].rstrip()), got[:80])
        self.assertIn("no match in 1 section(s) (7)", got)
        self.assertEqual(cli("read", t, "--section", "7", "--until", "(")[0], 1)

    def test_read_until_keeps_the_section_title_and_combines(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        f = os.path.join(d, "book.md")
        chap = ("# Chapter {n}\n\nOpening of {n}.\n\n## Summary {n}\n\nPoint {n} stands.\n\nSecond point {n}.\n\n"
                "Exercises\n\nDo task {n}.\n\n")
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(chap.format(n=n) for n in (1, 2)) + "# Chapter 3\n\nNo drills here.\n")
        # --title with --until: each section cut on its own, and a pattern naming the title does not empty it
        code, got, _ = cli("read", f, "--title", "Summary", "--until", "^Exercises")
        self.assertEqual(code, 0)
        for n in (1, 2):
            self.assertIn(f"Second point {n}.", got)
            self.assertNotIn(f"Do task {n}", got)
        code, got, _ = cli("read", f, "--title", "Summary 1", "--until", "Summary")
        self.assertIn("Point 1 stands", got)
        code, got, _ = cli("read", f, "--title", "Summary 1", "--until", "Summary", "--format", "md")
        self.assertIn("Point 1 stands", got)
        # --from then --until, searched after the --from match
        code, got, _ = cli("read", f, "--title", "Summary", "--from", "Second", "--until", "Exercises")
        self.assertIn("Second point 2.", got)
        self.assertNotIn("Point 1 stands", got)
        self.assertNotIn("Exercises", got)
        code, got, _ = cli("read", f, "--title", "Summary 1", "--from", "Point", "--until", "Second|Do task")
        self.assertIn("Point 1 stands", got)
        self.assertNotIn("Second point", got)
        # --each-chars: the cut comes first, and the resume line keeps --until
        code, got, _ = cli("read", f, "--title", "Summary", "--until", "Exercises", "--each-chars", "40", "--compact")
        self.assertIn("--until Exercises", got)
        self.assertNotIn("Do task", got)
        m = re.search(r"--section (\d+) --offset (\d+)", got)
        code, rest, _ = cli("read", f, "--section", m.group(1), "--offset", m.group(2), "--until", "Exercises", "--compact")
        self.assertNotIn("Do task", rest)
        # --max-chars caps the total and its footer resumes inside the cut text
        whole = cli("read", f, "--title", "Summary", "--until", "Exercises")[1]
        code, got, _ = cli("read", f, "--title", "Summary", "--until", "Exercises", "--max-chars", "60")
        self.assertIn("shown chars 0-", got)
        self.assertNotIn("Do task", got)
        self.assertTrue(whole.startswith(got.split("[readwright")[0].rstrip()))
        # a section without a match prints whole beside cut ones
        code, got, _ = cli("read", f, "--title", "Summary 1|Chapter 3", "--until", "Exercises")
        self.assertNotIn("Do task", got)
        self.assertIn("No drills here.", got)
        self.assertIn("no match in", got)
        # --out-dir files are cut too; --at-para past the cut says so
        out = os.path.join(d, "parts")
        self.assertEqual(cli("read", f, "--title", "Summary", "--until", "Exercises", "--out-dir", out)[0], 0)
        for name in os.listdir(out):
            with open(os.path.join(out, name), encoding="utf-8") as fh:
                self.assertNotIn("Do task", fh.read())
        sec = re.search(r"=== \[(\d+)", cli("read", f, "--title", "Summary 1")[1]).group(1)
        self.assertEqual(cli("read", f, "--section", sec, "--until", "Exercises", "--at-para", "4")[0], 1)

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

    def test_read_at_para_with_compact_and_out(self):
        # --at-para was refused with --compact and ignored with --out (Pirkle run, 2026-11-07)
        t = self.big_text()
        _, out, _ = cli("grep", t, "Brannoch", "--max", "2")
        para = re.findall(r"\| para (\d+)/\d+ \| offset (\d+)", out)[1][0]
        code, got, _ = cli("read", t, "--section", "7", "--compact", "--at-para", para, "--max-chars", "8")
        self.assertEqual(code, 0)
        self.assertTrue(got.startswith("Brannoch"), got[:40])
        dest = self.f("at-para.txt")
        for extra in ([], ["--compact"]):
            code, msg, _ = cli("read", t, "--section", "7", *extra, "--at-para", para, "--out", dest)
            self.assertEqual(code, 0, msg)
            with open(dest, encoding="utf-8") as fh:
                self.assertTrue(fh.read().startswith("Brannoch"), extra)

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

    def test_clean_cut_drops_a_section_header_with_no_body(self):
        body = "=== [1/2] A ===\nA\n" + "Sentence here.\n\n" * 50
        out = rw.clean_cut(body + "=== [2/2] B | 9 words ===\nB\n\n")
        self.assertNotIn("[2/2]", out)
        self.assertTrue(out.endswith("Sentence here.\n\n"))
        kept = body + "=== [2/2] B | 9 words ===\nB\nA real first line.\n\n"
        self.assertIn("[2/2]", rw.clean_cut(kept))

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
        self.assertIn("short of --max-chars", out)
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

    def test_max_words_with_at_para_counts_from_that_paragraph(self):
        # the cap used to apply from the section top, so a later --at-para or --offset printed nothing (2026-11-07)
        t = self.f("longsec.md")
        t.write_text("## Only\n\n" + "\n\n".join(f"Para{i} " + lorem(60) for i in range(1, 40)), encoding="utf-8")
        for extra in ((), ("--quiet",)):
            code, out, _ = cli("read", t, "--section", "1", "--at-para", "30", "--max-words", "100", *extra)
            self.assertEqual(code, 0)
            self.assertTrue(out.startswith("Para29") or out.startswith("Para30"), out[:40])
            body, hint = out.rsplit("[readwright:", 1)
            self.assertEqual(len(body.split()), 100)
            self.assertIn("cut at --max-words 100", hint)
            self.assertIn("continue with --offset", hint)
        code, out, _ = cli("read", t, "--section", "1", "--offset", "5000", "--max-words", "50", "--quiet")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.rsplit("[readwright:", 1)[0].split()), 50)

    def test_big_section_note_suggests_headings_first(self):
        P = lambda t: rw.Para("p", t)
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("Front", [P("short")]),
                                                rw.Section("Part", [P(lorem(300)) for _ in range(60)])])
        old = rw.BIG_SECTION_CHARS
        try:
            rw.BIG_SECTION_CHARS = 10_000
            notes = rw.big_section_notes(doc)
        finally:
            rw.BIG_SECTION_CHARS = old
        self.assertTrue(notes, notes)
        self.assertIn("read --section 2 --headings", notes[0])
        self.assertLess(notes[0].index("--headings"), notes[0].index("grep"))

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

    def table_epub(self):
        src, dst = self.f("plain.epub"), self.f("turns.epub")
        make_epub(src)
        reply = " ".join(f"word{i}" for i in range(40))
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>Prose before the turns.</p>"
               "<table><tr><td><img src='me.png' alt=''/></td><td><p>Ask for a tide table</p></td></tr>"
               "<tr><td><img src='ai.png' alt=''/></td><td><pre class='programlisting'>import tide\nprint(tide)</pre></td></tr>"
               f"<tr><td><img src='ai.png' alt=''/></td><td><p>{reply}</p></td></tr>"
               "<tr><td>Lead words</td><td>Before <pre>x = 1</pre> after</td></tr></table>"
               "<h1 id='c3'>Chapter Three</h1><p>The ledger listed every ship.</p></body></html>")
        with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
            for info in zi.infolist():
                zo.writestr(info, ch2 if info.filename.endswith("ch2.xhtml") else zi.read(info))
        return dst

    def test_skip_code_finds_code_set_in_classed_divs(self):
        src, dst = self.f("plain.epub"), self.f("springer.epub")
        make_epub(src)
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>Prose before.</p><div class='Para'>Lead words.\n"
               "<div class='ProgramCode'><div class='LineGroup'><div class='FixedLine'>\n   <span>res &lt;- tide(1,</span>\n</div>"
               "<div class='FixedLine'><span>\u00a0\u00a0plot=TRUE)</span></div></div></div></div>"
               "<div class='Para'>Prose after.</div>"
               "<h1 id='c3'>Chapter Three</h1><p>The ledger.</p></body></html>")
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
            for i in zin.infolist():
                zout.writestr(i, ch2.encode() if i.filename.endswith("ch2.xhtml") else zin.read(i.filename))
        _, full, _ = cli("read", dst, "--section", "2")
        self.assertIn("res <- tide(1,\n  plot=TRUE)", full)   # one listing, lines and indent intact
        _, out, _ = cli("read", dst, "--section", "2", "--skip-code")
        self.assertNotIn("tide", out)
        self.assertIn("Prose before", out)
        self.assertIn("Lead words", out)
        self.assertIn("Prose after", out)
        self.assertIn("in 1 code blocks", out)

    def test_skip_code_finds_monospace_blockquotes(self):   # calibre's MOBI conversion sets <pre> as <blockquote><tt>
        src, dst = self.f("plain2.epub"), self.f("mobi.epub")
        make_epub(src)
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>Prose before.</p><ol><li>Enter these lines:</li></ol>"
               "<blockquote><span><tt>a.pitch = 1.0f;</tt></span><br/><span><tt>a.volume\u00a0=\u00a00.5f;</tt></span></blockquote>"
               "<p>Run <tt>Play()</tt> now.</p><p><tt>config.json</tt></p><blockquote><p>A real quotation.</p></blockquote>"
               "<h1 id='c3'>Chapter Three</h1><p>The ledger.</p></body></html>")
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
            for i in zin.infolist():
                zout.writestr(i, ch2.encode() if i.filename.endswith("ch2.xhtml") else zin.read(i.filename))
        _, full, _ = cli("read", dst, "--section", "2")
        self.assertIn("a.pitch = 1.0f;\na.volume = 0.5f;", full)   # one listing, one line each
        _, out, _ = cli("read", dst, "--section", "2", "--skip-code")
        self.assertNotIn("pitch", out)
        self.assertNotIn("Enter these lines", out)
        for kept in ("Prose before", "Run Play() now.", "config.json", "A real quotation."):
            self.assertIn(kept, out)
        self.assertIn("in 1 code blocks", out)

    def test_skip_code_finds_pre_in_a_table_cell(self):
        e = self.table_epub()
        _, full, _ = cli("read", e, "--section", "2")
        self.assertIn("import tide\nprint(tide)", full)   # lines intact, not flattened into a row
        _, out, _ = cli("read", e, "--section", "2", "--skip-code")
        self.assertNotIn("import tide", out)
        self.assertNotIn("x = 1", out)
        self.assertIn("Ask for a tide table", out)
        self.assertIn("Before", out)                       # the prose beside a listing stays
        self.assertIn("after", out)
        self.assertIn("Lead words", out)

    def test_max_row_words_cuts_long_rows_only(self):
        e = self.table_epub()
        _, out, _ = cli("read", e, "--section", "2", "--max-row-words", "5")
        self.assertIn("word4 [row cut: 35 more words]", out)
        self.assertNotIn("word5", out)
        self.assertIn("Prose before the turns.", out)
        self.assertIn("--max-row-words cut 1 long table row(s)", out)
        self.assertIn("word39", cli("read", e, "--section", "2")[1])

    def test_toc_code_counts_code_words(self):
        e = self.code_epub()
        plain = cli("toc", e)[1]
        self.assertNotIn(" code)", plain)
        out = cli("toc", e, "--code")[1]
        self.assertIn(", 7 code)", out)
        self.assertIn(", 3 code)", out)

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

    def test_skip_code_drops_captions_and_legends_only(self):
        src, dst = self.f("plain.epub"), self.f("legend.epub")
        make_epub(src)
        c1, c2 = chr(0x2776), chr(0x2777)
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>Listing 2.1 shows the idea in prose.</p><p>Middle.</p>"
               "<p>Listing 2.2 Loading the tide</p><pre>import tide</pre>"
               f"<p>{c1} Loads it</p><p>{c2} Stores it</p><p>Prose after.</p><p>{c1} A stray mark stays.</p>"
               "</body></html>")
        with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
            for info in zi.infolist():
                zo.writestr(info, ch2 if info.filename.endswith("ch2.xhtml") else zi.read(info))
        _, out, _ = cli("read", dst, "--section", "2", "--skip-code")
        self.assertNotIn("Loading the tide", out)
        self.assertNotIn("Loads it", out)
        self.assertNotIn("Stores it", out)
        self.assertIn("Listing 2.1 shows", out)   # not before a block
        self.assertIn("A stray mark stays.", out)  # not after code
        self.assertIn("3 captions and legends", out)

    def test_skip_code_drops_numbered_callouts_only(self):
        src, dst = self.f("plain.epub"), self.f("callout.epub")
        make_epub(src)
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>Set the flag first.</p>"
               "<pre>import tide</pre><p><img src='1.png'/></p><p>Loads the tide.</p>"
               "<p><img src='chart.png'/></p>"
               "<h1 id='c3'>Chapter Three</h1><p>No listing here.</p><p><img src='2.png'/></p></body></html>")
        with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
            for info in zi.infolist():
                zo.writestr(info, ch2 if info.filename.endswith("ch2.xhtml") else zi.read(info))
        _, out, _ = cli("read", dst, "--section", "2-3", "--skip-code")
        self.assertNotIn("1.png", out)
        self.assertIn("Loads the tide.", out)
        self.assertIn("chart.png", out)      # a named picture is not a callout
        self.assertIn("2.png", out)          # no code in that section, so the marker stays

    def test_skip_code_drops_colon_lead_ins(self):
        src, dst = self.f("plain.epub"), self.f("leadin.epub")
        make_epub(src)
        ch2 = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
               "<h1 id='c2'>Chapter Two</h1><p>To count the gulls, open a fresh shell:</p>"
               "<pre>gulls --count</pre>"
               "<ul><li>We load the tide table:</li></ul><pre>load(tide)</pre>"
               "<p>The keeper notes three things:</p><p>Wind, rain and fog.</p>"
               "<p>The harbour wakes early.</p></body></html>")
        with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
            for info in zi.infolist():
                zo.writestr(info, ch2 if info.filename.endswith("ch2.xhtml") else zi.read(info))
        _, out, _ = cli("read", dst, "--section", "2", "--skip-code")
        self.assertNotIn("fresh shell", out)
        self.assertNotIn("tide table", out)
        self.assertIn("three things:", out)   # a colon line before prose stays
        self.assertIn("harbour wakes", out)
        self.assertIn("left out 3 words in 2 code blocks and 2 lead-in lines", out)
        _, full, _ = cli("read", dst, "--section", "2")
        self.assertIn("fresh shell", full)

    def test_untitled_contents_page_stays_one_section(self):
        # L-070: 'Introduction' and the last 'Chapter 9' repeat no later line, so they used to open false sections
        lines = ["Table of Contents", "Title Page", "Introduction"] + [f"Chapter {n} - Topic {n}" for n in range(1, 10)] \
            + ["Appendix: Track Listing", "Index"]
        doc = rw.Doc("x", "txt", {}, [rw.Section("(untitled: Table of Contents)", [rw.Para("p", t) for t in lines], 1, "c")])
        self.assertEqual(len(rw.refine(doc).sections), 1)

    def test_epub_section_splits_at_oneline_contents(self):
        # L-039: one spine file, no headings, an outline with one entry; the contents page has one line a chapter
        # ('1 BRASS LANTERNS') and each chapter opens with a paragraph holding just its number, then the title
        d = lambda t: f"<div class='paragraph'><strong>{t}</strong></div>"
        names = ["BRASS LANTERNS", "SALT ROADS", "QUIET PILOTS", "LAST LIGHT"]
        body = d("CONTENTS") + d("INTRODUCTION") + "".join(d(f"{n}\u2002{t}") for n, t in enumerate(names, 1)) \
            + d("EPILOGUE: THE LONG WATCH") + d("INDEX") + d("INTRODUCTION") + f"<p>{lorem(400)}</p>"
        for n, t in enumerate(names, 1):
            body += d(str(n)) + d(t) + "".join(f"<p>{lorem(300, 'harbour')}</p>" for _ in range(25))
        body += d("EPILOGUE") + f"<p>{lorem(300, 'tide')}</p>"
        x = ("<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'><body>"
             + body + "</body></html>")
        opf = ("<?xml version='1.0' encoding='utf-8'?><package xmlns='http://www.idpf.org/2007/opf' version='2.0'>"
               "<metadata xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title>Lanterns</dc:title></metadata>"
               "<manifest><item id='a' href='a.xhtml' media-type='application/xhtml+xml'/>"
               "<item id='ncx' href='toc.ncx' media-type='application/x-dtbncx+xml'/></manifest>"
               "<spine toc='ncx'><itemref idref='a'/></spine></package>")
        ncx = ("<?xml version='1.0'?><ncx xmlns='http://www.daisy.org/z3986/2005/ncx/' version='2005-1'><navMap>"
               "<navPoint id='n1'><navLabel><text>Start</text></navLabel><content src='a.xhtml'/></navPoint>"
               "</navMap></ncx>")
        path = self.tmp / "lanterns.epub"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
            z.writestr("META-INF/container.xml", "<?xml version='1.0'?><container version='1.0' "
                       "xmlns='urn:oasis:names:tc:opendocument:xmlns:container'><rootfiles><rootfile "
                       "full-path='content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
            z.writestr("content.opf", opf)
            z.writestr("toc.ncx", ncx)
            z.writestr("a.xhtml", x)
        old = rw.BIG_SECTION_CHARS
        try:
            rw.BIG_SECTION_CHARS = 10_000
            titles = [t.title for t in rw.load(str(path)).sections]
        finally:
            rw.BIG_SECTION_CHARS = old
        self.assertEqual(titles[1:], ["INTRODUCTION", "1. BRASS LANTERNS", "2. SALT ROADS", "3. QUIET PILOTS",
                                      "4. LAST LIGHT", "EPILOGUE"])
        doc = rw.load(str(path))
        ch = doc.sections[-2].paras
        self.assertEqual(ch[0].text, "4. LAST LIGHT")
        self.assertTrue(all(p.text.strip() != "4" for p in ch))

    def test_giant_section_splits_at_printed_contents(self):
        P = lambda t: rw.Para("p", t)
        contents = [P("1"), P("Brass Lanterns and Tides"), P("3"), P("Harbour charts"), P("4"),
                    P("2"), P("Salt Roads of the"), P("north coast"), P("21"),
                    P("3"), P("Case study - a ferry log 40"),   # a section entry, not chapter 3
                    P("4"), P("Last Light"), P("60")]
        opener = P("This part has the following chapters: • Chapter 3, Quiet Pilots: The Night Shift • Chapter 4, Last Light")
        body = [P("Brass Lanterns and Tides " + lorem(200))] + [P(lorem(300)) for _ in range(20)] \
            + [P("Salt Roads of the North Coast: " + lorem(200))] + [P(lorem(300)) for _ in range(20)] \
            + [P("Quiet Pilots - The Night Shift " + lorem(200))] + [P(lorem(300)) for _ in range(20)] \
            + [P("Last Light " + lorem(300))] + [P(lorem(300)) for _ in range(20)]
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("Contents", contents + [opener]),
                                                rw.Section("Preface", [P("A short preface.")] + body)])
        old = rw.BIG_SECTION_CHARS
        try:
            rw.BIG_SECTION_CHARS = 10_000
            rw.split_at_contents(doc)
            notes = rw.big_section_notes(doc)
        finally:
            rw.BIG_SECTION_CHARS = old
        self.assertEqual([s.title for s in doc.sections],
                         ["Contents", "Preface", "1. Brass Lanterns and Tides", "2. Salt Roads of the north coast",
                          "3. Quiet Pilots: The Night Shift", "4. Last Light"])
        self.assertEqual(doc.sections[1].paras[0].text, "A short preface.")
        self.assertTrue(doc.sections[3].paras[1].text.startswith("lorem ipsum"))
        self.assertNotIn("Salt Roads", doc.sections[3].paras[1].text)
        self.assertFalse([n for n in notes if "section 2 " in n])   # the preface no longer holds the book

    def test_giant_pdf_section_splits_at_running_heads(self):
        intro = ["Introduction\n" + lorem(50)] + ["■ Introduction\n" + lorem(50)] * 2
        ch = lambda n, t: ([f"CHAPTER {n}\n{t}\n" + lorem(300)]
                           + [f"Chapter {n} ■ {t}\n" + lorem(300) for _ in range(4)])
        pages = ["Front matter"] + intro + ch(1, "Brass Lanterns") + ch(2, "Salt Roads") + ch(3, "Last Light")
        # chapter 3 has no opener; its first page carries no head either
        pages[14] = lorem(300)
        chars = [len(p) for p in pages]
        old = rw.BIG_SECTION_CHARS
        try:
            rw.BIG_SECTION_CHARS = 1_000
            got = rw.run_head_chapters([(2, "Introduction", 1, 0)], pages, chars)
            plain = rw.run_head_chapters([(2, "Introduction", 1, 0)], [lorem(300)] * 18, [1800] * 18)
        finally:
            rw.BIG_SECTION_CHARS = old
        self.assertEqual([(p, t) for p, t, _, _ in got],
                         [(2, "Introduction"), (5, "Chapter 1: Brass Lanterns"), (10, "Chapter 2: Salt Roads"),
                          (15, "Chapter 3: Last Light")])
        self.assertEqual(plain, [(2, "Introduction", 1, 0)])

    def test_contents_dot_leaders_collapse(self):
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("Contents", [
            rw.Para("p", "About the Author" + "�" * 40 + " xiii Chapter 1: Lanterns" + "�" * 30 + " 1"),
            rw.Para("p", "Salt Roads ........ 21 Tides ····· 40 Wait... no 3")])])
        rw.collapse_leaders(doc)
        self.assertEqual(doc.sections[0].paras[0].text, "About the Author … xiii Chapter 1: Lanterns … 1")
        self.assertEqual(doc.sections[0].paras[1].text, "Salt Roads … 21 Tides … 40 Wait... no 3")

    def test_giant_section_stays_whole_without_contents(self):
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("One", [rw.Para("p", "short text")]),
                                                rw.Section("Two", [rw.Para("p", lorem(300)) for _ in range(150)])])
        old = rw.BIG_SECTION_CHARS
        try:
            rw.BIG_SECTION_CHARS = 10_000
            rw.split_at_contents(doc)
        finally:
            rw.BIG_SECTION_CHARS = old
        self.assertEqual(len(doc.sections), 2)

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

    def test_chapters_from_page_heads(self):   # L-078 `chapter-heads-on-pages`
        def pg(n, head, w=40):
            return rw.Section(f"page {n}: {head}" if head else f"page {n}", [rw.Para("p", lorem(w))], 1, f"page{n}")
        doc = rw.Doc("x.pdf", "pdf", sections=[pg(1, "Title page"), pg(2, "The Chapter l Empowerment of Sound"),
            pg(3, "Chapterl \u2022 The Empowerment of Sound"), pg(4, "Chapter 2 Our Beginnings"),
            pg(5, "Chapter 2 \u2022 Our Beginnings"), pg(6, "see Chapter 13 for more"), pg(7, "Chapter 3 Mixing"),
            pg(8, "Book title")])
        runs = rw.chapter_runs(doc)
        self.assertEqual([(f, l, n) for f, l, n, _, _ in runs], [(2, 3, 1), (4, 6, 2), (7, 8, 3)])
        self.assertEqual(runs[0][3], "The Empowerment of Sound")
        self.assertEqual(runs[2][4], 80)
        self.assertEqual(rw.chapter_runs(rw.Doc("x.pdf", "pdf", sections=[pg(1, "Chapter 1 A")])), [])

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

    def test_page_join_moves_only_the_run_on_sentence(self):   # L-033 `page-join-empties-page`
        P = rw.Para
        pages = [[P("p", "We showed it to people and")], [P("p", "they sent us feedback. Then " + lorem(30))]]
        rw.join_split_pages(pages)
        self.assertEqual(pages[0][0].text, "We showed it to people and they sent us feedback.")
        self.assertTrue(pages[1] and pages[1][0].text.startswith("Then lorem"))

    def test_group_reads_runon_leader_contents_and_page_labels(self):   # L-040 `group-labelled-pages`
        P = rw.Para
        def pg(n, text, label=None):
            lab = f" (p. {label})" if label else ""
            return rw.Section(f"page {n}{lab}: {text[:20]}", [P("p", text)], 1, f"page{n}")
        secs = [pg(1, "Title page"), pg(2, "Reading … 1 Line length . . . . 3 Fonts … 5")]
        secs += [pg(n, f"body {n} " + lorem(20), n - 2) for n in range(3, 10)]
        doc = rw.Doc("x.pdf", "pdf", sections=secs)
        doc.meta["printed_labels"] = {n: n - 2 for n in range(3, 10)}
        self.assertEqual([(f, l, t) for f, l, t, _ in rw.leader_groups(doc)],
                         [(1, 2, "(front matter)"), (3, 4, "Reading"), (5, 6, "Line length"), (7, 9, "Fonts")])
        self.assertTrue(any("5-6. Line length" in l for l in rw.group_lines(doc)))

    def test_group_uses_printed_contents(self):   # L-032 `contents-title-then-page`
        P = rw.Para
        def pg(n, *paras):
            return rw.Section(f"page {n}: {paras[0][:20]}" if paras else f"page {n}", [P("p", t) for t in paras], 1, f"page{n}")
        secs = [pg(1, "Title page"), pg(2, "Contents", "Foreword", "3", "1 Money", "4", "2 Press", "6")]
        secs += [pg(n, f"body {n} " + lorem(20)) for n in range(3, 9)]
        doc = rw.Doc("x.pdf", "pdf", sections=secs)
        self.assertEqual([(f, l, t) for f, l, t, _ in rw.contents_groups(doc)],
                         [(1, 2, "(front matter)"), (3, 3, "Foreword"), (4, 5, "1 Money"), (6, 8, "2 Press")])
        self.assertTrue(any("4-5. 1 Money" in l for l in rw.group_lines(doc)))
        doc.meta["page_shift"] = -1   # printed page 3 is PDF page 4
        self.assertEqual(rw.contents_groups(doc)[1][:3], (4, 4, "Foreword"))

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

    def test_outline_named_dests_get_their_pages(self):
        sample = ('+\t"7 Retrieval"\t#page=389&zoom=100,0,0\n'
                  '|\t\t"7.1 Matching"\t#nameddest=section.7.1\n'
                  '|\t\t"7.2 Unknown"\t#nameddest=section.7.2\n')
        dests = rw.parse_dests('Page  Destination                 Name\n'
                               ' 405 [ XYZ  135  696 null      ] "section.7.1"\n')
        self.assertEqual(dests, {"section.7.1": 405})
        self.assertEqual(rw.parse_outline(sample, dests), [("7 Retrieval", 389, 1), ("7.1 Matching", 405, 2)])
        self.assertEqual(rw.parse_outline(sample), [("7 Retrieval", 389, 1)])

    def test_outline_percent_encoded_named_dests(self):
        # InDesign PDFs: MuPDF percent-encodes the name, pdfinfo prints it plain; 664 of 710 entries were lost (Pirkle, L-076)
        sample = ('+\t"Chapter 1: Introduction"\t#nameddest=15031-FM-Ch5.indd%3APage%201%3A3914\n'
                  '|\t\t"1.2.1 Acquisition"\t#nameddest=15031-FM-Ch5.indd%3A1.2.1%E2%80%82Acquisition%3A3917\n')
        dests = rw.parse_dests(' 50 [ FitH  666 ] "15031-FM-Ch5.indd:Page 1:3914"\n'
                               ' 52 [ FitH  666 ] "15031-FM-Ch5.indd:1.2.1 Acquisition:3917"\n')
        self.assertEqual(rw.parse_outline(sample, dests), [("Chapter 1: Introduction", 50, 1), ("1.2.1 Acquisition", 52, 2)])

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

    def test_same_page_names_run_into_one_paragraph_split(self):   # L-073: Foley Grail ch. 15 gave six 0-word entries
        P = rw.Para
        paras = [P("p", "Parting words follow. Ann Lee (mixer) Keep it quiet. Bo Ray (editor) Cut less, listen more.")]
        out = rw.place_on_pages([(1, "Ann Lee", 2), (1, "Bo Ray", 2)], [paras])
        js = [j for _, _, _, j in out]
        self.assertEqual([paras[j].text[:7] for j in js], ["Ann Lee", "Bo Ray "])
        one = [P("p", "Words by Ann Lee here. Ann Lee (mixer) said it.")]   # a lone entry never splits running text
        self.assertEqual(rw.place_on_pages([(1, "Ann Lee", 2)], [one])[0][3], 0)
        self.assertEqual(len(one), 1)

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

    def test_split_thousands_rejoin(self):
        self.assertEqual(rw.join_lines(["3, 097Hz and 1, 000 through 50, 000RPM, 7, 060kW"]), "3,097Hz and 1,000 through 50,000RPM, 7,060kW")
        self.assertEqual(rw.join_lines(["pages 3, 100 and 12, 140 to 2026, 097"]), "pages 3, 100 and 12, 140 to 2026, 097")

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

    def test_running_heads_with_roman_page_numbers_strip(self):   # "xxx | Introduction" stayed in the text, Generative AI on Kubernetes
        out = rw.strip_running_heads("xxx | Introduction\n\nBody text.\n\nIntroduction | xxxi\n")
        self.assertEqual(out.split(), ["Body", "text."])

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

    def folio_book(self):
        """Alternating two-line heads: "NNN" over the part name on even pages, the chapter over "NNN" on odd ones."""
        pages = []
        for n in range(30):
            head = ["Chapter 2 Salt Roads", str(n + 100)] if n % 2 else [str(n + 100), "Part One Field Notes"]
            pages.append("\n\n".join(head + [f"Body words of page {n} run on and on here."]) + "\n\n")
        return pages

    def stripped(self, pages, titles=None):
        shifts = rw.folio_shifts(pages)
        keys = rw.beside_folio_keys(pages, shifts)
        first = rw.first_near_edge(pages, keys)
        return [rw.strip_folio_heads(p, n, shifts, keys, first, (titles or {}).get(n, ())) for n, p in enumerate(pages)]

    def test_alternating_heads_and_folios_drop(self):   # L-052 `alternating-folio-heads`
        out = "".join(self.stripped(self.folio_book()))
        self.assertNotIn("Part One Field Notes", out)
        self.assertNotIn("Chapter 2 Salt Roads", out)
        self.assertNotRegex(out, r"(?m)^1\d\d\s*$")
        self.assertEqual(out.count("Body words"), 30)
        crlf = "".join(self.stripped([p.replace("\n", "\r\n") for p in self.folio_book()]))   # xpdf on Windows
        self.assertNotIn("Part One Field Notes", crlf)

    def test_folio_head_openers_stay(self):
        pages = ["Part One Field Notes\n\nThis part opens here.\n\n"] + self.folio_book()[1:]
        pages[1] = "Chapter 2 Salt Roads\n\n101\n\nThe chapter opens here.\n\n"
        out = self.stripped(pages, {1: ["2. Salt Roads"]})
        self.assertIn("Part One Field Notes", out[0])      # first copy, no number beside it
        self.assertIn("Chapter 2 Salt Roads", out[1])      # names this page's outline entry
        self.assertNotIn("101", out[1])
        self.assertNotIn("Chapter 2 Salt Roads", "".join(out[2:]))

    def test_head_below_a_sidebar_drops(self):
        pages = self.folio_book()
        pages[4] = "104\n\nExhibit 2-1 A Sidebar\n\nPart One Field Notes\n\nBody text of the page.\n\n"
        out = self.stripped(pages)[4]
        self.assertIn("Exhibit 2-1 A Sidebar", out)
        self.assertNotIn("Part One Field Notes", out)
        self.assertNotIn("104", out)

    def test_folio_heads_do_not_over_strip(self):
        pages = self.folio_book()
        for n in (4, 8, 12):   # a heading that recurs a few times by a number
            pages[n] = f"{n + 100}\n\nField Repairs\n\nBody text.\n\n"
        for n in range(14, 30, 2):   # numbered captions differ, though each sits by a number
            pages[n] = f"{n + 100}\n\nExhibit 2-{n}\n\nBody text.\n\n"
        pages[6] = "Part One Field Notes\n\n" + "\n\n".join(f"Line {k} of a long page." for k in range(9)) + "\n\nPart One Field Notes in the middle\n\n"
        pages[20] = "Total Assets\n\n7\n\nBody text.\n\n"   # a table figure, not this page's number
        out = self.stripped(pages)
        self.assertEqual("".join(out).count("Field Repairs"), 3)
        self.assertEqual("".join(out).count("Exhibit 2-"), 7)
        self.assertIn("Total Assets\n\n7", out[20])
        self.assertIn("Part One Field Notes in the middle", out[6])
        pages = ["\n\n".join((str(n), "a", "b c d")) for n in range(9)]
        self.assertEqual(rw.beside_folio_keys(pages, {0}), set())   # one letter is no head

    @unittest.skipUnless(rw.tools()["pdftotext"], "no pdftotext")
    def test_alternating_heads_keep_a_section_whole(self):
        pages = [[(72, "Part One Field Notes", 720), (72, "The part opener speaks.", 660)],
                 [(72, "Chapter 2 Salt Roads", 720), (72, "The chapter opener speaks.", 660)]]
        for n in range(2, 30):
            head = ["Chapter 2 Salt Roads", str(n + 100)] if n % 2 else [str(n + 100), "Part One Field Notes"]
            first = "wall stood firm and" if n == 16 else "Reading the Tides" if n == 2 else f"mark{n} comes first and"
            last = "of the harbour" if n == 15 else "ends the page here."
            pages.append([(72, head[0], 740), (72, head[1], 700), (72, first, 640), (72, f"mark{n} comes first and", 626),
                          (72, lorem(10, "tide"), 612), (72, last, 598)])
        p = self.f("heads.pdf")
        make_pdf(p, pages)
        outline = [("Part One", 1, 1), ("2. Salt Roads", 2, 2), ("Reading the Tides", 3, 3)]
        tl = dict(rw.tools(), mutool="mutool")
        with unittest.mock.patch.object(rw, "tools", lambda: tl), unittest.mock.patch.object(rw, "pdf_outline", lambda *a: outline), \
                unittest.mock.patch.object(rw, "pdf_math_fonts", lambda *a: None):
            doc = rw.load(str(p))
        self.assertEqual([s.title.split(" (p.")[0] for s in doc.sections], ["Part One", "2. Salt Roads", "Reading the Tides"])
        tides = rw.render_paras(doc.sections[2].paras)
        self.assertTrue(all(f"mark{n} " in tides for n in range(2, 30)))
        self.assertNotIn("Part One Field Notes", tides)
        self.assertNotIn("Chapter 2 Salt Roads", tides)
        self.assertIn("the harbour wall stood firm", " ".join(tides.split()))
        self.assertIn("Part One Field Notes", rw.render_paras(doc.sections[0].paras))
        self.assertIn("Chapter 2 Salt Roads", rw.render_paras(doc.sections[1].paras))

    def test_short_chapter_head_drops(self):   # L-054 `short-chapter-heads`
        pages = self.folio_book()
        for n in (11, 13, 15):
            pages[n] = f"Chapter 3 Short Tide\n\n{n + 100}\n\nBody words of page {n}.\n\n"
        out = self.stripped(pages)
        self.assertNotIn("Chapter 3 Short Tide", "".join(out))
        self.assertEqual("".join(out).count("Body words"), 30)
        self.assertIn("Chapter 3 Short Tide", self.stripped(pages, {11: ["Chapter 3 Short Tide"]})[11])   # the opener

    def test_short_run_needs_the_books_rhythm(self):
        pages = self.folio_book()
        pages[11] = "Field Repairs\n\n111\n\nBody.\n\n"       # same text, but three pages apart
        pages[17] = "Field Repairs\n\n117\n\nBody.\n\n"
        pages[20] = "120\n\nCrew List\n\nBody.\n\n"          # on the part head's side, two pages apart but
        pages[22] = "122\n\nCrew List\n\nBody.\n\n"          # the page between has no head by a number
        pages[21] = "Nothing beside\n\nthe number here.\n\n"
        pages[3] = "Lower line\n\n103\n\nBody.\n\n"
        pages[5] = "Body.\n\nlower words here\n\n105\n\n"     # at the foot, where these heads never are
        pages[7] = "Body.\n\nlower words here\n\n107\n\n"
        out = "".join(self.stripped(pages))
        self.assertEqual(out.count("Field Repairs"), 2)
        self.assertEqual(out.count("Crew List"), 2)
        self.assertEqual(out.count("lower words here"), 2)

    def test_spread_headings_stay(self):   # L-053 `spread-headings-stay`
        pages = self.folio_book()
        pages += [f"{n + 100}\n\nBody words of page {n}.\n\n" if n % 2 == 0 else f"Body {n}.\n\n" for n in range(30, 80)]
        for n in range(30, 80, 10):    # five copies by a number, one a chapter
            pages[n] = f"{n + 100}\n\nKey Takeaways\n\nBody words of page {n}.\n\n"
        self.assertEqual("".join(self.stripped(pages)).count("Key Takeaways"), 5)
        spread = [f"Key Takeaways\n\nBody {n}.\n" if n % 5 == 0 else f"Body {n}.\n\nMore.\n" for n in range(30)]
        self.assertNotIn("key takeaways", rw.running_head_keys(spread))
        dense = [f"Key Takeaways\n\nBody {n}.\n" if n % 2 == 0 else f"Body {n}.\n\nMore.\n" for n in range(30)]
        self.assertIn("key takeaways", rw.running_head_keys(dense))
        footer = [f"Body {n}.\n\nAcme Press 2014\n" if n % 5 == 0 else f"Body {n}.\n\nMore {n}.\n" for n in range(200)]
        self.assertIn("acme press", rw.running_head_keys([f.replace(" 2014", "") for f in footer]))   # a fifth of a long book

    def test_recurring_chapter_label_stays_a_numbered_head_does_not(self):
        openers = ["Chapter %d\n\nBody of the book.\n" % (n // 20 + 1) if n % 20 == 0 else f"Body {n}.\n\nMore {n}.\n" for n in range(100)]
        self.assertNotIn("chapter #", rw.running_head_keys(openers))
        spread = [f"{n + 7} Salt Roads\n\nBody {n}.\n" if n % 9 == 0 else f"Body {n}.\n\nMore {n}.\n" for n in range(60)]
        self.assertIn("# salt roads", rw.running_head_keys(spread))   # spread, but the number keeps the page's shift

    def test_glued_folio_leaves_the_caption(self):   # L-054 `glued-folio-caption`
        self.assertEqual(rw.strip_glued_folio("122 Exhibit 4-3\n\nBody.\n", 22, {100}), "Exhibit 4-3\n\nBody.\n")
        self.assertEqual(rw.strip_glued_folio("Body.\n\nFigure 5.14 Bias too low. 112", 12, {100}), "Body.\n\nFigure 5.14 Bias too low.")
        for page, n in (("122 people came to the harbour\n\nBody.", 22),     # prose beginning with the number
                        ("99 Exhibit 4-3\n\nBody.", 22),                     # not this page's number
                        ("Body.\n\n122 Exhibit 4-3\n\nMore body.", 22)):    # not at the edge
            self.assertEqual(rw.strip_glued_folio(page, n, {100}), page)
        self.assertEqual(rw.strip_glued_folio("122 Exhibit 4-3", 22, set()), "122 Exhibit 4-3")
        self.assertEqual(rw.strip_glued_folio("122 Table of Contents\n\nBody.", 22, {100}), "122 Table of Contents\n\nBody.")
        pages = [f"{n + 100} Exhibit {n}-1\n\nBody {n}.\n" for n in range(9)]
        self.assertEqual(rw.running_head_keys(pages), set())   # never the whole caption

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

    def test_stray_hyphens_healed_only_when_the_book_prints_the_word(self):
        p = rw.Para("p", "An ex-ample of in-formation. A re-sign and a well-known cat. "
                         "example example example information information information resign resign resign sign known well")
        rw.heal_stray_hyphens([rw.Section("c", [p])])
        self.assertIn("An example of information.", p.text)
        self.assertIn("A re-sign and a well-known cat.", p.text)

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

    def test_drop_images(self):
        P = rw.Para
        paras = [P("p", "[image omitted: 00027.jpg]"), P("p", "Compare the two. [image omitted: a.jpg] See?"),
                 P("p", "[image: A Brief History]"), P("p", "Body.")]
        doc = rw.Doc("x.epub", "epub", sections=[rw.Section("Ten", paras, 1, "s1")])
        self.assertEqual(rw.drop_images(doc), 2)
        self.assertEqual([p.text for p in doc.sections[0].paras], ["Compare the two. See?", "[image: A Brief History]", "Body."])

    def test_drop_epigraphs(self):
        P = rw.Para
        paras = [P("h", "Ten", 1),
                 P("p", "\u201cCreativity is a habit of small invented steps.\u201d"), P("p", "\u2014Ada Example"),
                 P("p", "Body text about making things in public every day."),
                 P("p", '"A straight-quoted line here."'), P("p", "-- Bo Sample, Invented Poet"),
                 P("p", "\u201cA quotation with no attribution after it.\u201d"),
                 P("p", "More body text follows the lone quotation."),
                 P("p", "\u201cShort quote.\u201d"), P("p", "\u2013 " + "word " * 12)]
        doc = rw.Doc("x.epub", "epub", sections=[rw.Section("Ten", paras, 1, "s1")])
        self.assertEqual(rw.drop_epigraphs(doc), 4)
        texts = [p.text for p in doc.sections[0].paras]
        self.assertEqual(len(texts), 6)
        self.assertNotIn("\u2014Ada Example", texts)
        self.assertIn("\u201cA quotation with no attribution after it.\u201d", texts)
        self.assertIn("\u201cShort quote.\u201d", texts)   # attribution too long to be a name

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


    def test_fix_chapter_openers(self):   # drop-cap digits and running heads glued into PDF text
        P, S = rw.Para, rw.Section
        doc = rw.Doc("x", "pdf", sections=[
            S("16. Text Summarization (p. 338-349, printed 317-328)", [P("p", "1Text Su6mmarization Text summarization is hard."),
                                         P("p", "16.2 Extractive Text Summarization 319"),
                                         P("p", "16.3 Abstractive Text Summarization 321 si = max"),
                                         P("p", "7.2 Other Chapter 99 stays, wrong chapter")]),
            S("8. Scorer", [P("p", "154 Chapter 8 Scorer and return the top k"), P("p", "8Scorer in 2 parts")]),
            S("Preface", [P("p", "1Preface stays")])])
        self.assertEqual(rw.fix_chapter_openers(doc), 4)
        self.assertEqual([p.text for p in doc.sections[0].paras],
                         ["Text Summarization Text summarization is hard.", "si = max", "7.2 Other Chapter 99 stays, wrong chapter"])
        self.assertEqual(doc.sections[1].paras[0].text, "and return the top k")
        self.assertEqual(doc.sections[2].paras[0].text, "1Preface stays")

    def test_strip_glued_heads_rejoins_the_split_sentence(self):
        P = rw.Para
        head = "Chapter 5 # Equalization"
        paras = [P("h", "5.1 Filters", 2)]
        for n in range(5):
            paras += [P("p", f"Page {n} text."), P("p", head)]
        paras += [P("p", "The filter can be"), P("p", head + " patched between the two."),
                  P("p", head + " Capital text stays as written."), P("p", "Chapter 5 was short and clear, as noted.")]
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("5.1 Filters", paras, 1, "s1")])
        self.assertEqual(rw.strip_glued_heads(doc), 1)
        texts = [p.text for p in doc.sections[0].paras]
        self.assertIn("The filter can be patched between the two.", texts)
        self.assertIn(head + " Capital text stays as written.", texts)
        self.assertIn("Chapter 5 was short and clear, as noted.", texts)

    def test_strip_glued_heads_keeps_a_new_paragraph_after_a_full_stop(self):
        P = rw.Para
        head = "Running Head Here"
        paras = [P("h", "One", 2)] + [P("p", head) for _ in range(5)] + [P("p", "Done."), P("p", head + " and then more.")]
        doc = rw.Doc("x.pdf", "pdf", sections=[rw.Section("One", paras, 1, "s1")])
        self.assertEqual(rw.strip_glued_heads(doc), 1)
        self.assertEqual(doc.sections[0].paras[-1].text, "and then more.")

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


class TestMetaSwapped(unittest.TestCase):
    def test_swapped(self):
        name = "Deborah Tannen - Conversational Style_ Analyzing Talk among Friends.epub"
        note = rw.meta_swapped({"title": "Deborah Tannen", "author": "Conversational Style: Analyzing Talk among Friends"}, name)
        self.assertIn("swapped", note)
        self.assertEqual(rw.meta_swapped({"title": "Show Your Work!", "author": "Austin Kleon"}, "Show Your Work - Austin Kleon.epub"), "")
        self.assertEqual(rw.meta_swapped({"title": "Deborah Tannen", "author": "Another Long Title Here"}, name), "")


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
    def test_trailing_sections_repeating_chapter_titles_become_notes(self):
        doc = type("D", (), {})()
        mk = lambda t, n: rw.Section(t, [rw.Para("p", "w " * n)])  # noqa: E731
        doc.sections = [mk("Chapter 1", 500), mk("Chapter 2", 500), mk("Chapter 3", 500),
                        mk("Chapter 1", 40), mk("Chapter 2", 40), mk("Chapter 3", 40)]
        rw.title_repeated_notes(doc)
        self.assertEqual([s.title for s in doc.sections][:3], ["Chapter 1", "Chapter 2", "Chapter 3"])
        self.assertEqual([s.title for s in doc.sections][3:], ["Notes: Chapter 1", "Notes: Chapter 2", "Notes: Chapter 3"])

    def test_one_repeated_or_long_title_stays(self):
        doc = type("D", (), {})()
        mk = lambda t, n: rw.Section(t, [rw.Para("p", "w " * n)])  # noqa: E731
        doc.sections = [mk("Interlude", 100), mk("Chapter 1", 100), mk("Interlude", 90), mk("Chapter 1", 10)]
        rw.title_repeated_notes(doc)
        self.assertEqual([s.title for s in doc.sections], ["Interlude", "Chapter 1", "Interlude", "Chapter 1"])

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

    def test_figure_link_lines_and_repeated_alt_go(self):   # Web Form Design EPUB, 2026-11-03
        p = self.f("fig.epub")
        alt = "In the sign-up form, people bounce back and forth."
        make_epub_pages(p, {"a.xhtml": f"<h1>Forms</h1><p>Before.</p><div><img src='b.jpg' alt='{alt}'/></div><div><img src='b.jpg' alt='{alt}'/>"
                            "<p>top image: <img src='i.jpg' alt=''/> <a href='http://example.com/1'>http://example.com/1</a></p>"
                            "<p><img src='i.jpg' alt=''/> <a href='http://example.com/2'>http://example.com/2</a></p></div>"
                            f"<p>Figure 9-1. {alt}</p><p>Then <img src='f.jpg' alt=''/> holds.</p>"},
                        {"b.jpg": b"x", "i.jpg": b"x", "f.jpg": b"x"})
        code, out, _ = cli("read", p, "--section", "1", "--no-cache")
        self.assertNotIn("example.com", out)
        self.assertNotIn("[image:", out)
        self.assertIn(f"Figure 9-1. {alt}", out)
        self.assertIn("Then [formula: image] holds", out)

    def test_second_copy_of_a_picture_is_no_formula(self):   # Random House EPUB ornaments, 2026-11-07
        p = self.f("orn.epub")
        make_epub_pages(p, {"a.xhtml": "<h1>Intro</h1><div><img src='o.jpg' alt=''/><img src='o.jpg' alt=''/></div>"
                            "<p>Then <img src='f.jpg' alt=''/> holds.</p>"},
                        {"o.jpg": b"x", "f.jpg": b"x"})
        code, out, _ = cli("read", p, "--section", "1", "--no-cache")
        self.assertEqual(out.count("[image omitted: o.jpg]"), 1)
        self.assertEqual(out.count("[formula: image]"), 1)
        self.assertIn("Then [formula: image] holds", out)

    def test_equation_pictures_and_subscripts_are_marked(self):   # Manning IR EPUB, 2026-11-03
        p = self.f("ir.epub")
        make_epub_pages(p, {"a.xhtml": "<h1>BM25</h1><p>We improve on it by length:</p>"
                            "<p id='eq_11_32' class='image'><img src='e.jpg' alt='image'/></p>"
                            "<p>Here, tf<sub><em>td</em></sub> is the frequency, and k<sub>1</sub> a parameter. "
                            "In positions k1 and k2, then <img src='f.jpg' alt='image'/> holds.</p>"},
                        {"e.jpg": b"x", "f.jpg": b"x"})
        code, out, _ = cli("read", p, "--section", "1", "--no-cache")
        self.assertIn("[equation 11.32: image]", out)
        self.assertIn("tf_td is the frequency", out)
        self.assertIn("k_1 a parameter", out)
        self.assertIn("then [formula: image] holds", out)

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

    def test_caps_split_keeps_caption_credit_in_its_caption(self):
        body = " ".join(["word"] * 300) + "."
        paras = []
        for h in ("FIRST TOPIC", "SECOND TOPIC", "THIRD TOPIC"):
            paras += [rw.Para("p", h), rw.Para("p", body)]
        paras.insert(2, rw.Para("p", "The stage at night. Lighting by someone. JANE PHOTOGRAPHER"))
        titles = [x.title for x in rw.split_caps(rw.Section("x", paras))]
        self.assertIn("FIRST TOPIC", " ".join(titles).upper())
        self.assertNotIn("JANE PHOTOGRAPHER", " ".join(titles).upper())

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
        # Python comments and whole-line calls with spaces inside (Hands-On LLMs, LangChain listings)
        py = ["Using this memory, we can try out a sequence of questions:", "# Retain only the last 2 conversations in memory",
              "from langchain.memory import ConversationBufferWindowMemory", "# Ask two questions and keep both in the chat history",
              'llm_chain.predict(input_prompt="What is 3 + 3?")', "The interaction so far is kept in the chat history for the next turn."]
        self.assertEqual(rw.code_blocks(py), [(1, 5)])
        self.assertTrue(rw.CODE_HINT.search("from langchain.memory import ConversationBufferWindowMemory"))
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


class TestGlossaryTerms(Base):
    """0.16.0: `terms` lists a glossary's headwords, run-together or with a colon."""

    def test_glossary_term_split(self):
        self.assertEqual(rw.glossary_term("Backlight A process by which the primary light comes from behind.")[0], "Backlight")
        self.assertEqual(rw.glossary_term("Anamorphic lens A lens used to create a widescreen image.")[0], "Anamorphic lens")
        self.assertEqual(rw.glossary_term("Dolly: a wheeled platform that carries the camera.")[0], "Dolly")
        self.assertIsNone(rw.glossary_term("Short."))

    def test_terms_finds_glossary_section(self):
        p = self.f("gloss.epub")
        make_epub_pages(p, {"a.xhtml": "<h1>Gulls</h1><p>" + lorem(40) + "</p>",
                            "g.xhtml": "<h1>Glossary</h1><p>Backlight A process by which the light comes from behind the subject.</p>"
                                       "<p>Bleach bypass A process in which the bleach stage is skipped in processing.</p>"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rw.main(["terms", str(p)])
        self.assertIn("Backlight  |", out.getvalue())
        self.assertIn("Bleach bypass  |", out.getvalue())
        self.assertIn("2 terms", out.getvalue())


class TestHeadings(Base):
    """0.20.0: `read --headings` lists a chapter's subheadings with paragraph numbers for --at-para."""

    def test_numbered_headings_in_a_flat_pdf(self):   # L-066 `numbered-headings`
        heads = ["1.1 Introduction", "1.2 Sound generation", "1.2.1 Frequency", "2.1 Loudness", "5.2 Annoyance"]
        noise = ["1.4 | 1.2 | 1 | 0.8", "3.5 Hz is the value we measured here.", "Body words."]
        paras = [rw.Para("p", x) for x in noise + heads]
        self.assertEqual(rw.numbered_headings(paras), [(3, 1), (4, 1), (5, 2), (6, 1), (7, 1)])
        self.assertEqual(rw.numbered_headings([rw.Para("p", "1.1 Lone heading")]), [])

    def test_bare_numbered_heads_across_page_sections(self):   # L-069 `bare-numbered-heads`
        doc = rw.Doc("x.pdf", "pdf", {}, [
            rw.Section("page 1", [rw.Para("p", "Intro words."), rw.Para("p", "1 Variable Tempo"), rw.Para("p", "Body.")]),
            rw.Section("page 2", [rw.Para("p", "2 Variable Pitch"), rw.Para("p", "Body."), rw.Para("p", "3 Variable Rhythm")]),
            rw.Section("page 3", [rw.Para("p", "7 Stray number line"), rw.Para("p", "4 Variable Volume")])])
        self.assertEqual(rw.bare_numbered_heads(doc, [1, 2, 3]), {(1, 1), (2, 0), (2, 2), (3, 1)})
        self.assertEqual(rw.bare_numbered_heads(doc, [1]), set())   # one head alone is not a run
        lines = rw.heading_lines(doc, [1, 2, 3])
        self.assertIn("  2 Variable Pitch  (para 1, 1 words)", lines)

    def test_caps_headings_in_a_flat_pdf(self):   # L-068 `caps-headings`
        body = "Words of the book run on here for a while and keep going so the paragraph is long enough to count as body text."
        paras = [rw.Para("p", x) for x in ("THE REAL AND THE RENDERED", "THE UNITY ILLUSION", body, "NASA", body,
                                            "QUESTIONS OF SOUND REPRODUCTION", body, "RED", "GREEN BLUE", "MATERIALIZING SOUND INDICES (MSIs)", body)]
        self.assertEqual(rw.caps_headings(paras), [(1, 1), (5, 1), (9, 1)])
        self.assertEqual(rw.caps_headings(paras[:5]), [])   # one heading alone is not trusted
        caps_list = [rw.Para("p", x) for x in ("ONE TWO", "THREE FOUR", "FIVE SIX", "SEVEN EIGHT", "Short.")]
        self.assertEqual(rw.caps_headings(caps_list), [])

    def test_ruled_headings_and_caps_names(self):   # L-064 `caps-list-acronym`
        paras = [rw.Para("p", x) for x in ("chapter 1", "." * 40, "Some opening words.", "1. THE APPEAL", "." * 40,
                                            "A. For Musicians", "Body words here.")]
        self.assertEqual(rw.ruled_headings(paras), [(0, 1), (3, 1), (5, 2)])
        self.assertEqual(rw.ruled_headings([rw.Para("p", "A. Not a heading"), rw.Para("p", "Body.")]), [])
        filler = "Words of the book run on here for a while."
        s = rw.Section("Big", [rw.Para("p", x) for x in (
            f"{filler} We used FORTRAN daily, and FORTRAN again later.",
            f"{filler} DEC, IBM, Hewlett-Packard made them.",
            f"FORTRAN Formula Translation. {filler}",
            f"{filler} EARLY MACHINES Then came more.",
            f"{filler} LATER MACHINES Then came more.",
            f"{filler} NEWER SYSTEMS Then came more.",
            f"{filler} OTHER SYSTEMS Then came more.",
            f"{filler} FINAL THOUGHTS Then came more.",
            f"{filler} LAST WORDS Then came more.")], 1, "x")
        titles = [p.title for p in (rw.split_caps(s) or [])]
        self.assertIn("EARLY MACHINES", titles)
        self.assertNotIn("FORTRAN", titles)
        self.assertFalse([t for t in titles if "IBM" in t])

    def test_read_headings(self):
        p = self.f("tut.epub")
        make_epub_pages(p, {
            "a.xhtml": "<h1>Building the Raft</h1><p>Intro words for the raft.</p><h2>Gathering logs</h2>"
                       "<p>one two three four</p><p>Figure 3-1. A short caption</p><h3>Cutting rope</h3>"
                       "<p>five six</p><pre>tie(knot)</pre><h2>Launching</h2><p>seven</p>",
            "b.xhtml": "<h1>Plain Chapter</h1><p>" + lorem(30) + "</p>"})
        code, out, _ = cli("read", p, "--section", "1-", "--headings")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("  Gathering logs  (para 3, 9 words)", lines)
        self.assertIn("    Cutting rope  (para 6, 3 words)", lines)
        self.assertIn("  Launching  (para 9, 1 words)", lines)
        self.assertNotIn("Figure", out)
        self.assertNotIn("tie(knot)", out)
        self.assertIn("no headings under the title", out)
        code, got, _ = cli("read", p, "--section", "1", "--at-para", "6", "--max-chars", "12")
        self.assertTrue(got.startswith("Cutting rope"))


class TestPdfDoubleSpaced(Base):   # L-030 `pdf-double-spaced`, L-031 `pdf-table-cells`
    def test_double_spaced_lines_merge_and_hyphen_rejoins(self):
        lines = ["The lantern keepers counted every ship that passed the harbour wall at night",
                 "and wrote the tally in a ledger kept beside the great brass lamp of the tower.",
                 "Most keepers used a slate or a similar",
                 "board-like surface.",
                 "While the keepers differed in the number of lan-",
                 "tern wicks they trimmed, their main habit was the same each evening at dusk",
                 "when the tide turned and the gulls settled on the stones below the lamp room.",
                 "Short last line."] * 2
        pp = rw.text_paras("\n\n".join(lines), "txt")
        rw.VOCAB.update({"lantern": 5})
        try:
            rw.merge_wrapped(pp)
        finally:
            rw.VOCAB.clear()
        texts = [p.text for p in pp]
        self.assertIn("Most keepers used a slate or a similar board-like surface.", texts)
        self.assertTrue(any("number of lantern wicks they trimmed" in t for t in texts))
        self.assertTrue(any(t.startswith("The lantern keepers") and "brass lamp of the tower." in t for t in texts))

    def test_listing_after_repo_marker_is_code(self):
        page = ("A variant is shown in Listing 4.2.\n\nRepo 1: Tally.m Repo 2: Tally.py\n\n"
                "% count the ships tally = sum(ships, 2);\n% clip negatives tally(tally<0) = 0;\n"
                "Listing 4.2 Counting ships.\nMany keepers kept other tallies as well.")
        pp = rw.text_paras(page, "txt")
        kinds = [(p.kind, p.text[:12]) for p in pp]
        self.assertIn(("pre", "% count the "), kinds)
        self.assertIn(("p", "Listing 4.2 "), kinds)
        self.assertEqual(pp[-1].text, "Many keepers kept other tallies as well.")

    def test_table_cells_collapse_to_one_row(self):
        page = "Table 3.1 Lamp hours.\n\n" + "\n\n".join(["w(0)", "1", "w(1)", "0", "w(2)", "0", "w(3)", "0"]) \
               + "\n\nThe table lists the hours."
        pp = rw.text_paras(page, "txt")
        rw.collapse_cells(pp)
        self.assertEqual([p.kind for p in pp], ["p", "row", "p"])
        self.assertEqual(pp[1].text, "w(0) | 1 | w(1) | 0 | w(2) | 0 | w(3) | 0")


class ImageAndSuperscript(unittest.TestCase):
    def test_image_writes_named_picture_and_superscript_reads_as_power(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.epub")
            make_epub_pages(p, {"a.xhtml": "<h1>Value</h1><p>Today is 749/1.1021<sup>5</sup> and the 1<sup>st</sup> try.</p><div><img src='img/t1.jpg'/></div>"},
                            {"img/t1.jpg": b"JPEGDATA"})
            code, out, _ = cli("read", p, "--section", "1")
            self.assertIn("1.1021^5", out)
            self.assertIn("1st", out)
            self.assertIn("[image omitted: t1.jpg]", out)
            code, out, _ = cli("image", p, "t1.jpg", "--out-dir", d)
            self.assertEqual(code, 0)
            with open(os.path.join(d, "t1.jpg"), "rb") as f:
                self.assertEqual(f.read(), b"JPEGDATA")
            code, _, err = cli("image", p, "none.jpg", "--out-dir", d)
            self.assertNotEqual(code, 0)

    def test_both_plugin_manifests_agree_with_the_script(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        for m in ("plugin.json", ".claude-plugin/plugin.json"):
            self.assertEqual(json.loads((root / m).read_text(encoding="utf-8"))["version"], rw.VERSION, m)


EN_PARA = "The harbour clerk and the keeper of the light were in the tower that was built for the ships of the bay, and it is said that they have not left."
DE_PARA = "Der Hafenmeister und die Frau von dem Turm sind nicht auf der Insel, aber sie wird mit dem Boot nach dem Sturm auch wieder bei den Leuten sein."
FR_PARA = "Le gardien et la femme du phare sont dans une maison qui est sur les rochers, et ils ne sont pas avec les marins pour la nuit dans le port."
ES_PARA = "El guardia y la mujer del faro son de una casa que por los barcos para el puerto no se va con sus amigos, pero como lo dijo al alba."
IT_PARA = "Il guardiano e la donna del faro sono in una casa che per le navi della baia non si muove, ma anche gli amici come il mare sono nel porto."
PT_PARA = "Os guardas do farol e as mulheres da casa em uma ilha que para os barcos não se move, mas como os amigos nos portos são mais do mar."
NL_PARA = "De wachter en het meisje van de toren zijn op een eiland dat niet aan de haven is, maar die ook voor het schip met de storm naar huis door de nacht."


class TestReadLang(Base):
    """--lang keeps one language's paragraphs from an edition printing several; every sample here is invented."""

    def book(self, body):
        path = self.tmp / "polyglot.md"
        path.write_text("# Chapter\n\n" + body, encoding="utf-8")
        return str(path)

    def test_each_language_wins_its_own_paragraph(self):
        for code, para in (("en", EN_PARA), ("de", DE_PARA), ("fr", FR_PARA), ("es", ES_PARA), ("it", IT_PARA), ("pt", PT_PARA), ("nl", NL_PARA)):
            self.assertEqual(rw.para_lang(para), code, para)

    def test_glued_words_still_count_at_their_edges(self):
        glued = "thekeeperofthelight wasinthetowerand thelightofthebayand thehouseofthekeeperand oftheshipsandthe"
        self.assertEqual(rw.para_lang(glued), "en")

    def test_tie_and_fragment_decide_nothing(self):
        self.assertIsNone(rw.para_lang("Lorem ipsum dolor sit amet consectetur"))
        self.assertIsNone(rw.para_lang("the and"))

    def test_read_keeps_one_language_and_says_how_many_went(self):
        f = self.book("\n\n".join([EN_PARA, DE_PARA, FR_PARA, "xyz 12", EN_PARA]))
        code, out, _ = cli("read", f, "--lang", "en")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("harbour clerk"), 2)
        self.assertNotIn("Hafenmeister", out)
        self.assertNotIn("gardien", out)
        self.assertIn("--lang en dropped 3 paragraph(s)", out)

    def test_heading_stays_unless_it_favours_another_language(self):
        f = self.book(EN_PARA + "\n\n## Rhythm\n\n" + EN_PARA + "\n\n## Der Hafen und die Stadt von dem Meer\n\n" + EN_PARA)
        code, out, _ = cli("read", f, "--lang", "en")
        self.assertIn("Rhythm", out)
        self.assertEqual(out.count("Der Hafen"), 1)   # the section header keeps its title; the paragraph goes

    def test_max_chars_counts_after_the_filter(self):
        f = self.book("\n\n".join([DE_PARA] * 40 + [EN_PARA]))
        whole = cli("read", f, "--max-chars", "1000")[1]
        self.assertNotIn("harbour clerk", whole)
        kept = cli("read", f, "--lang", "en", "--max-chars", "1000")[1]
        self.assertIn("harbour clerk", kept)
        self.assertNotIn("shown chars", kept)

    def test_cut_footer_repeats_the_flag(self):
        f = self.book("\n\n".join([EN_PARA] * 30))
        out = cli("read", f, "--section", "1", "--lang", "en", "--max-words", "20")[1]
        self.assertIn("--lang en", out)

    def test_bad_code_refused(self):
        with self.assertRaises(SystemExit):
            rw.main(["read", self.book(EN_PARA), "--lang", "xx"])

    def test_grep_filters_too(self):
        f = self.book("\n\n".join([EN_PARA, DE_PARA]))
        self.assertEqual(cli("grep", f, "Hafenmeister", "--lang", "en")[0], 1)

    def test_info_names_lang_on_a_polyglot_book(self):
        f = self.book("\n\n".join([EN_PARA, DE_PARA, FR_PARA] * 25))
        out = cli("info", f)[1]
        self.assertIn("--lang", out)
        self.assertIn("languages", out)

    def test_info_quiet_on_one_language_with_some_quotation(self):
        f = self.book("\n\n".join([EN_PARA] * 200 + [DE_PARA] * 5 + [FR_PARA] * 3))
        self.assertNotIn("--lang", cli("info", f)[1])


class TestFootNoteCarried(unittest.TestCase):
    """A note left open at a page foot goes on over the page (HANDOFF open item from 0.42.0)."""

    def run_it(self, pages):
        notes = [rw.lift_foot_notes(pp) for pp in pages]
        rw.carry_foot_notes(pages, notes)
        return notes

    def test_tail_at_top_of_next_page(self):
        pages = [[rw.Para("p", "The clerk filed it.1"), rw.Para("p", "1. Tide Tables, a long note that")],
                 [rw.Para("p", "runs over the page."), rw.Para("p", "New paragraph here.")]]
        notes = self.run_it(pages)
        self.assertEqual(notes[0][0].text, "[note 1: Tide Tables, a long note that runs over the page.]")
        self.assertEqual([p.text for p in pages[1]], ["New paragraph here."])

    def test_tail_at_foot_of_next_page(self):
        pages = [[rw.Para("p", "The clerk filed it.1"), rw.Para("p", "1. Tide Tables, a long note that")],
                 [rw.Para("p", "New paragraph here."), rw.Para("p", "runs over the page."), rw.Para("p", "8")]]
        notes = self.run_it(pages)
        self.assertEqual(notes[0][0].text, "[note 1: Tide Tables, a long note that runs over the page.]")
        self.assertEqual([p.text for p in pages[1]], ["New paragraph here.", "8"])

    def test_open_body_keeps_its_own_top_paragraph(self):
        pages = [[rw.Para("p", "The clerk filed it.1 Then he went"), rw.Para("p", "1. Tide Tables, a long note that")],
                 [rw.Para("p", "home by the road."), rw.Para("p", "Next one.")]]
        notes = self.run_it(pages)
        self.assertEqual(notes[0][0].text, "[note 1: Tide Tables, a long note that]")
        self.assertEqual(pages[1][0].text, "home by the road.")

    def test_closed_note_takes_nothing(self):
        pages = [[rw.Para("p", "The clerk filed it.1"), rw.Para("p", "1. Tide Tables.")],
                 [rw.Para("p", "lower case start of a page."), rw.Para("p", "Next one.")]]
        notes = self.run_it(pages)
        self.assertEqual(notes[0][0].text, "[note 1: Tide Tables.]")
        self.assertEqual(len(pages[1]), 2)


class TestPdfNotesAndUnfolding(Base):
    """L-045, L-046: synthetic book pages; the long lines are what pdftotext prints for a block it has already joined."""

    def setUp(self):
        super().setUp()
        rw.VOCAB.clear()
        self.addCleanup(rw.VOCAB.clear)

    def test_foot_note_leaves_sentence_and_split_word_rejoins(self):
        pages = [[rw.Para("p", "The harbour clerk filed a report.1 He then saved the wrong ver-"),
                  rw.Para("p", "1. Tide Tables, vol. 2, page 9."), rw.Para("p", "7")],
                 [rw.Para("p", "sion over the right one.")]]
        rw.VOCAB.update({"version": 3})
        notes = [rw.lift_foot_notes(pp) for pp in pages]
        rw.join_split_pages(pages)
        for pp, n in zip(pages, notes):
            pp.extend(n)
        self.assertEqual([p.text for p in pages[0]],
                         ["The harbour clerk filed a report.1 He then saved the wrong version over the right one.",
                          "[note 1: Tide Tables, vol. 2, page 9.]"])

    def test_numbered_list_without_call_stays(self):
        pp = [rw.Para("p", "Three steps follow."), rw.Para("p", "1. Ask first."), rw.Para("p", "2. Check in.")]
        self.assertEqual(rw.lift_foot_notes(pp), [])
        self.assertEqual(len(pp), 3)

    def test_list_item_above_real_note_stays(self):
        pp = [rw.Para("p", "Body with a call.1"), rw.Para("p", "2. A list item."), rw.Para("p", "1. The note.")]
        self.assertEqual([n.text for n in rw.lift_foot_notes(pp)], ["[note 1: The note.]"])
        self.assertEqual(pp[-1].text, "2. A list item.")

    def test_list_that_goes_on_is_not_notes(self):
        call = rw.Para("p", "Body text with a stray call.1 and.2")
        pp = [call, rw.Para("p", "1. First."), rw.Para("p", "2. Second.")]
        self.assertEqual(rw.lift_foot_notes(pp, nxt=[rw.Para("p", "3. Third.")]), [])
        pp = [call, rw.Para("p", "1. First."), rw.Para("p", "2. Second.")]
        self.assertEqual(len(rw.lift_foot_notes(pp, nxt=[rw.Para("p", "More text.")])), 2)

    def test_section_number_and_math_are_not_calls(self):
        for body in ("See section 2.1 of the guide.", "Let x1 be the first value."):
            pp = [rw.Para("p", body), rw.Para("p", "1. An item.")]
            self.assertEqual(rw.lift_foot_notes(pp), [], body)

    def test_break_hyphen_rules(self):
        rw.VOCAB.update({"deadlines": 4, "dead": 3, "lines": 3, "well": 9, "documented": 1, "in": 40, "evitably": 1,
                         "pol": 1, "ish": 1, "post": 5, "war": 5, "re": 2, "sign": 1, "self-esteem": 2, "self": 3,
                         "esteem": 2})
        for a, b, want in (("dead-", "lines", "deadlines"), ("in-", "evitably", "inevitably"), ("pol-", "ish", "polish"),
                           ("well-", "documented", "well-documented"), ("post-", "war", "post-war"),
                           ("re-", "sign", "re-sign"), ("self-", "esteem", "self-esteem")):
            self.assertEqual(rw.join_broken(a, b), want)

    def test_long_lines_mean_paragraphs(self):
        long = "word " * 60
        page = f"{long}\nwho goes there?\n{long}\n"
        self.assertTrue(rw.unfolded_text([page]))
        self.assertFalse(rw.unfolded_text(["a printed line of ordinary width\n" * 40]))
        paras = rw.text_paras(rw.unfold_page(page), "txt")
        self.assertEqual(len(paras), 3)
        self.assertEqual(paras[1].text, "who goes there?")
        code = f"{long}\n{rw.PRE_OPEN}\nx = 1\ny = 2\n{rw.PRE_CLOSE}\n"
        self.assertEqual(rw.text_paras(rw.unfold_page(code), "txt")[1].text, "x = 1\ny = 2")
        short = "Smith, A printed entry\nthat wraps here\n"
        self.assertEqual(rw.unfold_page(short), short)

    @unittest.skipUnless(rw.tools()["pdftotext"], "no pdftotext")
    def test_pdf_end_to_end(self):
        long = ("The clerk counted crates at the quay all day long and wrote the figures down " * 4).strip()
        p = self.f("foot.pdf")
        make_pdf(p, pages=("one", "two"))
        cached = rw.cache_path(p, "pdftotext", ".txt")   # a synthetic PDF cannot print a line this long, so seed the text
        self.addCleanup(cached.unlink, missing_ok=True)
        cached.write_text("\n".join(["CHAPTER ONE", long + ".1", "who keeps count?", long + " and then the clerk went",
                                     "1. Quay Ledger, page 3.", "\f" + "home to sleep. " + long, ""]), encoding="utf-8")
        with unittest.mock.patch.object(rw, "CACHE_OFF", False):
            texts = [x.text for s in rw.load_pdf(p).sections for x in s.paras]
        self.assertIn("who keeps count?", texts)
        self.assertIn("[note 1: Quay Ledger, page 3.]", texts)
        joined = [t for t in texts if "clerk went home to sleep." in t]
        self.assertEqual(len(joined), 1)
        self.assertEqual(texts[texts.index(joined[0]) + 1], "[note 1: Quay Ledger, page 3.]")


class CacheWriteTests(unittest.TestCase):
    def converter(self, tag, ext, writes):
        """A fake tool that checks the cache name is still absent while it writes, and writes to the path WRITES picks."""
        seen = []

        def fake(cmd, timeout=600):
            seen.append(pathlib.Path(writes(cmd)))
            self.assertFalse(rw.cache_path(self.src, tag, ext).exists())
            seen[-1].write_bytes(b"made")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        return fake, seen

    def run_converter(self, tag, ext, writes, call, loader):
        with tempfile.TemporaryDirectory() as d:
            self.src = str(pathlib.Path(d) / "book.bin")
            pathlib.Path(self.src).write_bytes(b"\0" * 100)
            cp = rw.cache_path(self.src, tag, ext)
            fake, seen = self.converter(tag, ext, writes)
            doc = rw.Doc(self.src, "x", [], [])
            tl = dict(rw.tools(), soffice="soffice")
            try:
                with unittest.mock.patch.object(rw, "run", fake), unittest.mock.patch.object(rw, loader, lambda *a: doc), \
                        unittest.mock.patch.object(rw, "need", lambda *a: "tool"), unittest.mock.patch.object(rw, "tools", lambda: tl), \
                        unittest.mock.patch.object(rw, "CACHE_OFF", False):
                    call(self.src)
                self.assertEqual(cp.read_bytes(), b"made")
                self.assertEqual(list(cp.parent.glob(cp.stem + ".*.tmp*")), [])
                failing = unittest.mock.Mock(return_value=subprocess.CompletedProcess([], 1, b"", b"boom"))
                cp.unlink()
                with unittest.mock.patch.object(rw, "run", failing), unittest.mock.patch.object(rw, "need", lambda *a: "tool"), \
                        unittest.mock.patch.object(rw, "tools", lambda: tl), unittest.mock.patch.object(rw, "CACHE_OFF", False):
                    with self.assertRaises(rw.RWError):
                        call(self.src)
                self.assertFalse(cp.exists())
            finally:
                cp.unlink(missing_ok=True)

    def test_calibre_cache_is_atomic(self):
        self.run_converter("calibre", ".epub", lambda c: c[2], lambda p: rw.load_via_calibre(p, "azw3"), "load_epub")

    def test_soffice_cache_is_atomic(self):
        self.run_converter("soffice", ".docx", lambda c: pathlib.Path(c[c.index("--outdir") + 1]) / "made.docx",
                           lambda p: rw.load_via_office(p, "doc"), "load_docx")

    def test_pandoc_cache_is_atomic(self):
        self.run_converter("pandoc", ".md", lambda c: c[c.index("-o") + 1], lambda p: rw.load_via(p, "pandoc"), "load_text")

    def test_reader_never_sees_a_partial_cache(self):
        with tempfile.TemporaryDirectory() as d:
            cp = pathlib.Path(d) / "x.txt"
            cp.write_text("whole")
            tmp = rw.tmp_cache(cp)
            self.assertNotEqual(tmp, cp)
            tmp.write_text("half")
            self.assertEqual(cp.read_text(), "whole")
            rw.publish_cache(tmp, cp)
            self.assertEqual(cp.read_text(), "half")
            self.assertFalse(tmp.exists())

    def test_held_cache_keeps_the_existing_copy(self):
        with tempfile.TemporaryDirectory() as d:
            cp = pathlib.Path(d) / "x.txt"
            cp.write_text("whole")
            tmp = rw.tmp_cache(cp)
            tmp.write_text("other")
            with unittest.mock.patch.object(rw.os, "replace", side_effect=PermissionError):
                rw.publish_cache(tmp, cp)
            self.assertEqual(cp.read_text(), "whole")
            self.assertFalse(tmp.exists())


class ViewportOrderTests(unittest.TestCase):
    def test_pattern_takes_either_attribute_order(self):
        self.assertTrue(rw.FIXED_VIEWPORT.search('<meta content="width=818, height=1065" name="viewport"/>'))
        self.assertTrue(rw.FIXED_VIEWPORT.search('<meta name="viewport" content="width=818, height=1065"/>'))
        self.assertFalse(rw.FIXED_VIEWPORT.search('<meta content="width=818, height=1065" name="other"/>'))

    def test_offset_past_end_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.txt"
            f.write_text("Short text.", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPT), "read", str(f), "--offset", "9999"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("past the end", r.stdout + r.stderr)


class MarginFolioTests(unittest.TestCase):
    def test_margin_number_leaves_the_sentence(self):
        pages = [f"Words about sound {i + 5} more words here.\nFigure 3 and plain text." for i in range(40)]
        self.assertEqual(rw.margin_folio_shift(pages), 5)
        self.assertEqual(rw.strip_margin_folio(pages[0], 0, 5), "Words about sound more words here.\nFigure 3 and plain text.")

    def test_no_shift_without_a_leader(self):
        self.assertIsNone(rw.margin_folio_shift(["Born in 1900 with 3 cats."] * 40))
        self.assertEqual(rw.strip_margin_folio("in 65 frequency", 60, None), "in 65 frequency")

    def test_references_stay(self):
        for s in ("See Figure 65 now", "lines 65 to 70", "Contents .... 65 next", "both 64 and 65 here"):
            self.assertEqual(rw.strip_margin_folio(s, 60, 5), s)

    def test_two_occurrences_stay(self):
        s = "take 65 then 65 again"
        self.assertEqual(rw.strip_margin_folio(s, 60, 5), s)


class SymbolFontAndGluedHeadTests(unittest.TestCase):
    def test_symbol_font_operators(self):
        self.assertEqual(rw.repair_symbol_font("3þ3þ2 and 12Â7"), "3+3+2 and 12×7")
        self.assertEqual(rw.repair_symbol_font("Root (C) þ Third; Cþ denotes"), "Root (C) + Third; C+ denotes")

    def test_icelandic_thorn_stays(self):
        self.assertEqual(rw.repair_symbol_font("þetta er það"), "þetta er það")

    def test_glued_head_leaves_title(self):
        def para(t):
            return types.SimpleNamespace(text=t)
        doc = types.SimpleNamespace(sections=[
            types.SimpleNamespace(title="The Mixolydian Mode (p. 237-237)", paras=[para("220 Some Book Title The Mixolydian Mode")]),
            types.SimpleNamespace(title="Japanese Scales (p. 266)", paras=[para("Chapter 22 Exotic Scales 249 Japanese Scales")]),
            types.SimpleNamespace(title="The Blues", paras=[para("He sang all night about The Blues")]),
        ])
        self.assertEqual(rw.fix_glued_section_heads(doc), 2)
        self.assertEqual(doc.sections[0].paras[0].text, "The Mixolydian Mode")
        self.assertEqual(doc.sections[2].paras[0].text, "He sang all night about The Blues")

    def test_split_word_head_counts_as_known_title(self):
        pages = [f"Chapter 14 Addi tive Rhythms {n}\nbody text {n}" for n in (169, 171)] + ["other page\nmore"] * 3
        self.assertIn("chapter # addi tive rhythms #", rw.running_head_keys(pages, ["Chapter 14 Additive Rhythms"]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
