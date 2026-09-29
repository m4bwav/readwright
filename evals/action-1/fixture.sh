#!/usr/bin/env bash
# Seeds an eval workspace with fixture/lighthouse.epub: an invented 12-chapter novel (about 18,000 words of
# filler, too big to read whole under rw.py's 40,000-character default) with a few findable facts:
# chapter 3 is the storm that takes the lamp out, and the keeper's dog, Tamsin, is named only in chapter 9.
set -e
mkdir -p fixture
if python3 -c "import sys" >/dev/null 2>&1; then py=python3; else py=python; fi
"$py" - <<'PY'
import zipfile
words = "the sea rolled grey under a low sky and the keeper walked the gallery counting gulls".split()
def filler(n, seed):
    return " ".join(words[(i * 7 + seed) % len(words)] for i in range(n)) + "."
titles = ["Arrival", "The Log", "The Storm", "Repairs", "Supply Boat", "Winter", "Letters", "The Inspector",
          "Visitors", "Fog", "Spring", "Leaving"]
special = {
    3: ["In the third night the storm broke the lantern glass and the lamp went dark for an hour.",
        "Keeper Hale relit it with the spare wick while the relief keeper held the ladder."],
    9: ["The dog that followed Hale up the stairs every evening was called Tamsin."],
}
chapters = []
for i, t in enumerate(titles, 1):
    paras = [filler(120, i * 10 + k) for k in range(12)]
    for j, s in enumerate(special.get(i, [])):
        paras.insert(5 + j, s)
    body = "".join(f"<p>{p}</p>" for p in paras)
    chapters.append((f"ch{i:02d}.xhtml", t, f"<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>Chapter {i}: {t}</h1>{body}</body></html>"))
nav = "".join(f"<li><a href='{f}'>Chapter {i}: {t}</a></li>" for i, (f, t, _) in enumerate(chapters, 1))
opf = ("<package xmlns='http://www.idpf.org/2007/opf' version='3.0'><metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
       "<dc:title>The Lighthouse Year</dc:title><dc:creator>Eval Fixture</dc:creator><dc:language>en</dc:language></metadata><manifest>"
       "<item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/>"
       + "".join(f"<item id='c{i}' href='{f}' media-type='application/xhtml+xml'/>" for i, (f, _, _) in enumerate(chapters, 1))
       + "</manifest><spine>" + "".join(f"<itemref idref='c{i}'/>" for i in range(1, len(chapters) + 1)) + "</spine></package>")
with zipfile.ZipFile("fixture/lighthouse.epub", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
    z.writestr("META-INF/container.xml", "<container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
               "<rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles></container>")
    z.writestr("OEBPS/content.opf", opf)
    z.writestr("OEBPS/nav.xhtml", "<html xmlns='http://www.w3.org/1999/xhtml' xmlns:epub='http://www.idpf.org/2007/ops'>"
               f"<body><nav epub:type='toc'><ol>{nav}</ol></nav></body></html>")
    for f, _, x in chapters:
        z.writestr("OEBPS/" + f, x)
PY
