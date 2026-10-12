"""Extract a list of text blocks from official DOCX / DOC / PDF files.

Each block is either ("p", text) for a paragraph or ("table", rows) where rows is a list of
lists of cell strings. Footnotes (used in văn bản hợp nhất to cite amending acts) are
returned separately as {id: text}.

- DOCX: parsed directly (word/document.xml + word/footnotes.xml). Some Công báo DOCX files are
  zipped with Windows back-slash paths; they are normalised first.
- DOC (Word 97-2003): converted with macOS `textutil` to DOCX, then parsed as above.
- PDF: `pdftotext` (poppler); running gazette headers / page numbers are removed.
"""
import io
import os
import re
import subprocess
import tempfile
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _norm_zip(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    files = {}
    for i in z.infolist():
        n = i.filename.replace("\\", "/")
        if n.startswith("[trash]") or n.endswith("/"):
            continue
        files[n] = z.read(i)
    return files


def _run_text(r, fn_marks):
    out = []
    for el in r:
        tag = el.tag
        if tag == W + "t":
            out.append(el.text or "")
        elif tag == W + "tab":
            out.append(" ")
        elif tag in (W + "br", W + "cr"):
            out.append("\n")
        elif tag == W + "noBreakHyphen":
            out.append("-")
        elif tag == W + "sym":
            ch = el.get(W + "char")
            try:
                c = int(ch, 16)
                if 0xF000 <= c <= 0xF0FF:
                    c -= 0xF000
                out.append(chr(c) if c >= 32 else "")
            except Exception:
                pass
        elif tag in (W + "footnoteReference", W + "endnoteReference"):
            fid = el.get(W + "id")
            pre = "fn" if tag == W + "footnoteReference" else "en"
            fn_marks.append(pre + fid)
            out.append("[^%s%s]" % (pre, fid))
    return "".join(out)


def _para_text(p, fn_marks):
    parts = []
    for el in p.iter(W + "r"):
        if True:
            # skip runs inside deleted revisions
            anc = el.getparent()
            skip = False
            while anc is not None and anc is not p:
                if anc.tag in (W + "del", W + "moveFrom") or \
                        str(anc.tag).endswith("}Fallback"):
                    skip = True
                    break
                anc = anc.getparent()
            if skip:
                continue
            # skip text inside drawings/textboxes alternate content duplicates
            parts.append(_run_text(el, fn_marks))
    return "".join(parts)


def _table(tbl, fn_marks):
    rows = []
    for tr in tbl.iterchildren(W + "tr"):
        row = []
        for tc in tr.iterchildren(W + "tc"):
            texts = []
            for child in tc.iterchildren():
                if child.tag == W + "p":
                    texts.append(_para_text(child, fn_marks).strip())
                elif child.tag == W + "tbl":
                    for r in _table(child, fn_marks):
                        texts.append(" | ".join(r))
            span = 1
            tcpr = tc.find(W + "tcPr")
            if tcpr is not None:
                gs = tcpr.find(W + "gridSpan")
                if gs is not None:
                    try:
                        span = int(gs.get(W + "val"))
                    except Exception:
                        span = 1
            cell = "\n".join(t for t in texts if t)
            row.append(cell)
            for _ in range(span - 1):
                row.append("")
        rows.append(row)
    return rows


def _body_blocks(body, fn_marks):
    blocks = []
    for el in body.iterchildren():
        if el.tag == W + "p":
            blocks.append(("p", _para_text(el, fn_marks)))
        elif el.tag == W + "tbl":
            blocks.append(("table", _table(el, fn_marks)))
        elif el.tag == W + "sdt":
            c = el.find(W + "sdtContent")
            if c is not None:
                blocks += _body_blocks(c, fn_marks)
    return blocks


def from_docx_bytes(data):
    files = _norm_zip(data)
    doc = files.get("word/document.xml")
    if doc is None:
        raise ValueError("no word/document.xml")
    root = etree.fromstring(doc)
    body = root.find(W + "body")
    fn_marks = []
    blocks = _body_blocks(body, fn_marks)
    notes = {}
    for name, pre, tag in (("word/footnotes.xml", "fn", "footnote"),
                           ("word/endnotes.xml", "en", "endnote")):
        if name in files:
            fr = etree.fromstring(files[name])
            for fn in fr.iterchildren(W + tag):
                fid = fn.get(W + "id")
                if fn.get(W + "type") in ("separator", "continuationSeparator",
                                          "continuationNotice"):
                    continue
                txt = "\n".join(_para_text(p, []).strip()
                                for p in fn.iter(W + "p")).strip()
                notes[pre + fid] = txt
    # keep only notes actually referenced
    notes = {k: v for k, v in notes.items() if k in fn_marks}
    return blocks, notes


def from_doc_bytes(data):
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as td:
        src = os.path.join(td, "in.doc")
        dst = os.path.join(td, "out.docx")
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run(["textutil", "-convert", "docx", "-output", dst, src],
                       check=True, capture_output=True, timeout=600)
        with open(dst, "rb") as f:
            return from_docx_bytes(f.read())


HEADER_RE = re.compile(
    r"^\s*(CÔNG BÁO|C[ÔO]NG\s*B[ÁA]O)\s*/?\s*(Số|SỐ)?.*$|^\s*\d+\s+CÔNG BÁO.*$|"
    r"^\s*CÔNG BÁO\s*/\s*Số.*\d+\s*$")


def from_pdf_bytes(data):
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as td:
        src = os.path.join(td, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", src, "-"],
                           capture_output=True, timeout=600)
        txt = r.stdout.decode("utf-8", "replace")
    pages = txt.split("\f")
    lines = []
    for pg in pages:
        pl = pg.split("\n")
        # digital-signature stamp printed on the first page
        if any(x.strip().startswith("Thời gian ký") for x in pl[:12]):
            k = max(i for i, x in enumerate(pl[:12]) if x.strip().startswith("Thời gian ký"))
            pl = pl[k + 1:]
        pl = [x for x in pl if not re.match(r"^\s*(Ký bởi:|Email:\s*\S+@chinhphu|Cơ quan:\s*Văn phòng Chính phủ)", x)]
        # drop running headers ("CÔNG BÁO/Số 993 + 994/Ngày 26-12-2019") and bare page numbers
        cleaned = []
        for i, ln in enumerate(pl):
            s = ln.strip()
            if i < 6 and (re.match(r"^CÔNG\s*BÁO", s) or re.match(r"^\d{1,4}$", s)
                          or re.match(r"^\d{1,4}\s+CÔNG\s*BÁO", s)
                          or re.match(r"^CÔNG BÁO.*\d{1,4}$", s)
                          or re.match(r"^Số\s*[\d+ ]+/?\s*Ngày", s)):
                continue
            cleaned.append(ln)
        while cleaned and re.match(r"^\s*\d{0,4}\s*$", cleaned[-1] or ""):
            cleaned.pop()
        while cleaned and not cleaned[0].strip():
            cleaned.pop(0)
        lines += cleaned
    # join wrapped lines into paragraphs: a line much shorter than the typical full line
    # ends a paragraph; structural markers (Điều/Chương/1./a)) always start one.
    lens = sorted(len(x.strip()) for x in lines if len(x.strip()) > 20)
    full = lens[int(len(lens) * 0.8)] if lens else 80
    blocks = []
    cur = ""
    start_re = re.compile(r"^(Điều\s+\d+|Chương\s+[IVXLC\d]+|Mục\s+\d+|Phần\s+thứ|"
                          r"PHẦN\s+THỨ|CHƯƠNG\s+[IVXLC\d]+|MỤC\s+\d+|\d+\.\s|[a-zđ]\)\s|[-–+]\s)")
    prev_short = True
    for ln in lines:
        s2 = ln.strip()
        if not s2:
            if cur:
                blocks.append(("p", cur))
                cur = ""
            prev_short = True
            continue
        if cur and (start_re.match(s2) or prev_short):
            blocks.append(("p", cur))
            cur = s2
        else:
            cur = (cur + " " + s2) if cur else s2
        prev_short = len(s2) < 0.75 * full or (start_re.match(s2) and s2.startswith(("Điều", "Chương", "CHƯƠNG", "Mục", "MỤC", "Phần", "PHẦN")) and len(s2) < 0.9 * full)
    if cur:
        blocks.append(("p", cur))
    # re-join paragraphs split by a page break in mid-sentence
    merged = []
    for t, v in blocks:
        if merged and v[:1].islower() and not merged[-1][1].endswith((".", ":", ";", "!", "?", "”", "\"")):
            merged[-1] = ("p", merged[-1][1] + " " + v)
        else:
            merged.append((t, v))
    return merged, {}


def extract(data, ext):
    ext = ext.lower().lstrip(".")
    if ext == "docx" or data[:2] == b"PK":
        return from_docx_bytes(data)
    if ext == "doc" or data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return from_doc_bytes(data)
    if ext == "pdf" or data[:4] == b"%PDF":
        return from_pdf_bytes(data)
    raise ValueError("unknown format " + ext)
