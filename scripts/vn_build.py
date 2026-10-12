"""Build the Markdown corpus.

Inputs (produced by the other scripts, all under _raw/vn/):
  vbpl_meta.jsonl       document metadata + legal force from vbpl.vn   (vn_vbpl_meta.py)
  congbao/*.jsonl       Công báo listings with download links          (vn_cb_list.py)

For every document in scope that vbpl.vn marks InForce / PartiallyInForce:
  1. use the latest consolidated text (văn bản hợp nhất, VBHN) published in Công báo
     when one exists and verifiably consolidates that document;
  2. otherwise the original text published in Công báo;
  3. otherwise record it as a gap.
Text files are DOCX > DOC > PDF (first available) downloaded from the Công báo CDN.

Usage: python vn_build.py [laws|decrees|all]
"""
import datetime
import json
import os
import re
import sys
import unicodedata

from vn_common import RAW, ROOT, get
import vn_extract
import vn_markdown as M

TODAY = datetime.date.today().isoformat()

CAT = {
    "Hiến pháp": ("constitution", "hien-phap", None),
    "Bộ luật": ("code", "bo-luat", "luat"),
    "Luật": ("law", "luat", "luat"),
    "Pháp lệnh": ("ordinance", "phap-lenh", "phap-lenh"),
    "Nghị quyết": ("resolution", "nghi-quyet", "nghi-quyet"),
    "Nghị định": ("decree", "nghi-dinh", "nghi-dinh"),
}
NA_BODIES = ("quốc hội", "ủy ban thường vụ quốc hội", "uỷ ban thường vụ quốc hội")


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def normnum(s):
    s = nfc(s).upper().replace("Đ", "D")
    s = re.sub(r"\s+", "", s).strip(".")
    s = re.sub(r"(^|/)0+(\d)", r"\1\2", s)
    return s


def loosenum(s):
    """Looser key: drop PL-/NQ-/L- prefixes and fix common typos in vbpl identifiers."""
    s = normnum(s)
    s = re.sub(r"/(PL|NQ|L|ND)-", "/", s)
    s = s.replace("QHH", "QH").replace("UBNVQH", "UBTVQH")
    return s


def shortnum(s):
    m = re.match(r"^(\d+)/(\d{4})/", normnum(s))
    return m.group(1) + "/" + m.group(2) if m else None


def normname(s):
    s = nfc(s).lower()
    s = re.sub(r"^(văn bản hợp nhất|hợp nhất)\s+", "", s.strip())
    s = s.replace("“", "\"").replace("”", "\"")
    s = re.sub(r"[\"'.,;:()\-–]", " ", s)
    s = s.replace("uỷ", "ủy").replace("hoà", "hòa").replace("thoả", "thỏa").replace("khoẻ", "khỏe")
    return re.sub(r"\s+", " ", s).strip()


def dmy(s):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return None


def load_vbpl():
    out = []
    for line in open(os.path.join(RAW, "vbpl_meta.jsonl")):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("legislationType"):
            out.append(d)
    return out


def load_cb():
    seen = {}
    d = os.path.join(RAW, "congbao")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".jsonl"):
            continue
        for line in open(os.path.join(d, fn)):
            e = json.loads(line)
            if e["cb_id"] not in seen:
                seen[e["cb_id"]] = e
    return list(seen.values())


def load_cp():
    """vanban.chinhphu.vn listing rows indexed by normalised number."""
    idx = {}
    d = os.path.join(RAW, "chinhphu")
    if not os.path.isdir(d):
        return idx
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".jsonl"):
            continue
        for line in open(os.path.join(d, fn)):
            r = json.loads(line)
            num = re.sub(r"\s+\d{1,2}/\d{1,2}/\d{4}$", "", r["cells"][0] if r["cells"] else "").strip()
            if num:
                idx.setdefault(normnum(num), {})[r["docid"]] = r
                idx.setdefault(loosenum(num), {})[r["docid"]] = r
    return idx


CP_DETAIL = "https://vanban.chinhphu.vn/?pageid=27160&docid=%s"


def cp_entry(docid):
    """Turn a vanban.chinhphu.vn document page into a Công báo-like entry."""
    from bs4 import BeautifulSoup
    url = CP_DETAIL % docid
    html = get(url, sub="cpdetail")
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    files = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if re.search(r"\.(pdf|docx?)$", h, re.I) and "datafiles" in h:
            files.append({"name": h.rsplit("/", 1)[-1], "url": h})
    fields = {}
    txt = soup.get_text("\n", strip=True).split("\n")
    for key in ("Số ký hiệu", "Ngày ban hành", "Loại văn bản", "Cơ quan ban hành", "Trích yếu"):
        if key in txt:
            i = txt.index(key)
            if i + 1 < len(txt):
                fields[key] = txt[i + 1]
    return {"cb_id": "cp" + docid, "url": url, "files": files, "fields": fields,
            "gazettes": []}


def cb_num(e):
    return e["fields"].get("Số, ký hiệu") or ""


def is_vbhn(e):
    return "VBHN" in cb_num(e).upper() or e["fields"].get("Loại văn bản") == "Văn bản hợp nhất"


def pick_files(e):
    by = {}
    for f in e["files"]:
        ext = f["name"].rsplit(".", 1)[-1].lower()
        by.setdefault(ext, []).append(f)
    for ext in ("docx", "doc", "pdf"):
        if ext in by:
            return ext, by[ext]
    return None, []


def fetch_text(e):
    """Download + extract the text of a Công báo entry. Returns (blocks, notes, fmt)."""
    ext, files = pick_files(e)
    if not files:
        return None
    blocks, notes = [], {}
    for f in files:
        data = get(f["url"], sub="files", ext="." + ext, binary=True, timeout=300)
        if not data:
            return None
        try:
            b, n = vn_extract.extract(data, ext)
            if not looks_ok(b):
                raise ValueError("conversion produced implausible text")
        except Exception as ex:  # noqa
            print("extract failed", e.get("url"), f["name"], ex, flush=True)
            if ext != "pdf":
                pdfs = [x for x in e["files"] if x["name"].lower().endswith(".pdf")]
                if pdfs:
                    alt = dict(e)
                    alt["files"] = pdfs
                    return fetch_text(alt)
            return None
        # keep footnote ids unique across multiple files
        if len(files) > 1 and n:
            pre = "f%d" % (files.index(f) + 1)
            ren = {k: pre + k for k in n}
            b = [(t, _ren_marks(v, ren) if t == "p" else v) for t, v in b]
            n = {ren[k]: v for k, v in n.items()}
        blocks += b
        notes.update(n)
    if sum(len(v) for t, v in blocks if t == "p") < 200:
        return None
    return blocks, notes, ext


VN_OK = re.compile(r"[A-Za-z0-9\s.,;:()\[\]/%\-–—“”\"'’‘!?^_*+=<>&|…·•ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠ-ỹ°§№\u0300-\u036f]")


def looks_ok(blocks):
    """Reject garbage from a failed conversion (e.g. binary .doc read as plain text)."""
    txt = "".join(v for t, v in blocks if t == "p")[:200000]
    if len(txt) < 200:
        return False
    good = len(VN_OK.findall(txt))
    if good / len(txt) < 0.97:
        return False
    return bool(re.search(r"\b(của|và|các|được|Điều|theo)\b", txt))


def _ren_marks(text, ren):
    return re.sub(r"\[\^(\w+)\]", lambda m: "[^%s]" % ren.get(m.group(1), m.group(1)), text)


def verify_base(blocks, number):
    """Does the consolidated text cite the base document number near its start?"""
    want = normnum(number)
    head = " ".join(v for t, v in blocks[:80] if t == "p")
    head += " ".join(" ".join(" ".join(r) for r in v) for t, v in blocks[:5] if t == "table")
    return re.search(r"(?<![0-9])" + re.escape(want), normnum(head)) is not None


def base_name(d):
    name = nfc(d.get("name") or "")
    ident = nfc(d.get("legislationIdentifier") or "")
    if ident and ident != "Không số":
        name = re.sub(r"\s*số\s*" + re.escape(ident), "", name, flags=re.I)
    name = re.sub(r"\s+số\s+Không số", "", name)
    return re.sub(r"\s+", " ", name).strip(" .")


def in_scope(d, which):
    t = d.get("legislationType")
    if t not in CAT:
        return False
    if d.get("legislationLegalForce") not in ("InForce", "PartiallyInForce"):
        return False
    body = nfc((d.get("legislationPassedBy") or {}).get("name", "")).lower()
    if t == "Nghị quyết" and body not in NA_BODIES:
        return False
    if t == "Hiến pháp":
        return which in ("laws", "all") and (d.get("legislationDate") or "").startswith("2013")
    if t == "Nghị định":
        return which in ("decrees", "all")
    return which in ("laws", "all")


def out_path(d, cat):
    t = d["legislationType"]
    _, dname, prefix = CAT[t]
    year = (d.get("legislationDate") or "0000")[:4]
    if t == "Hiến pháp":
        return os.path.join("hien-phap", "hien-phap-%s.md" % year)
    ident = d.get("legislationIdentifier") or ""
    num = M.slugify(ident) if ident and ident != "Không số" else "khong-so-" + year
    title = M.slugify(base_name(d), 200)
    fn = "%s-%s-%s" % (prefix, num, title)
    fn = M.slugify(fn, 100)
    if t in ("Luật", "Nghị quyết", "Nghị định"):
        return os.path.join(dname, year, fn + ".md")
    return os.path.join(dname, fn + ".md")


def main(which="laws"):
    vbpl = load_vbpl()
    cb = load_cb()
    cp_idx = load_cp()
    cb_by_num = {}
    cb_by_short = {}
    vbhn_by_name = {}
    for e in cb:
        if is_vbhn(e):
            key = normname(e["fields"].get("Trích yếu") or "")
            if key:
                vbhn_by_name.setdefault(key, []).append(e)
        else:
            cb_by_num.setdefault(normnum(cb_num(e)), []).append(e)
            if loosenum(cb_num(e)) != normnum(cb_num(e)):
                cb_by_num.setdefault(loosenum(cb_num(e)), []).append(e)
            sn = shortnum(cb_num(e))
            if sn:
                cb_by_short.setdefault((sn, e["fields"].get("Loại văn bản")), []).append(e)
    for k in vbhn_by_name:
        vbhn_by_name[k].sort(key=lambda e: (dmy(e["fields"].get("Ngày ban hành")) or "",
                                            int(e["cb_id"])), reverse=True)
    # de-duplicate vbpl records (same type + number): prefer in force, then newest id
    docs = {}
    for d in vbpl:
        if not in_scope(d, which):
            continue
        ident = d.get("legislationIdentifier") or ""
        key = (d["legislationType"], normnum(ident) if ident != "Không số" else d["vbpl_url"])
        if key in docs:
            old = docs[key]
            if (old.get("legislationLegalForce") == "InForce") >= (d.get("legislationLegalForce") == "InForce"):
                continue
        docs[key] = d
    print(len(docs), "documents in scope", flush=True)

    manifest_p = os.path.join(RAW, "manifest-%s.json" % which)
    manifest = []
    used_paths = set()
    for key, d in sorted(docs.items(), key=lambda kv: kv[1].get("legislationDate") or ""):
        t = d["legislationType"]
        ident = d.get("legislationIdentifier") or ""
        rec = {"type": t, "identifier": ident, "name": d.get("name"),
               "vbpl_url": d["vbpl_url"], "legal_force": d.get("legislationLegalForce")}
        text = None
        used = None
        consolidated = None
        # 1. consolidated text
        cands = []
        if t == "Hiến pháp":
            cands = [e for e in cb if is_vbhn(e) and "hiến pháp" in normname(e["fields"].get("Trích yếu") or "")]
            cands.sort(key=lambda e: dmy(e["fields"].get("Ngày ban hành")) or "", reverse=True)
        elif t in ("Bộ luật", "Luật", "Pháp lệnh", "Nghị định", "Nghị quyết"):
            cands = vbhn_by_name.get(normname(base_name(d)), [])
        base_date = (d.get("legislationDate") or "")[:10]
        for e in cands[:4]:
            vd = dmy(e["fields"].get("Ngày ban hành")) or ""
            if vd and base_date and vd < base_date:
                continue
            r = fetch_text(e)
            if not r:
                continue
            if t == "Hiến pháp" or verify_base(r[0], ident):
                text, used, consolidated = r, e, e
                break
        # 2. original text
        if text is None and ident and ident != "Không số":
            cands2 = cb_by_num.get(normnum(ident)) or cb_by_num.get(loosenum(ident)) or []
            if not cands2:
                sn = shortnum(ident)
                c3 = cb_by_short.get((sn, "Luật" if t == "Bộ luật" else t), []) if sn else []
                if len(c3) == 1:
                    cands2 = c3
            for e in cands2:
                r = fetch_text(e)
                if r:
                    text, used = r, e
                    break
        # 3. vanban.chinhphu.vn (Government portal) attachments
        if text is None and ident and ident != "Không số":
            for docid in (cp_idx.get(normnum(ident)) or cp_idx.get(loosenum(ident)) or {}):
                e = cp_entry(docid)
                if e and e["files"]:
                    r = fetch_text(e)
                    if r:
                        text, used = r, e
                        break
        if text is None:
            rec["status"] = "missing"
            manifest.append(rec)
            print("MISSING", t, ident, (d.get("name") or "")[:80], flush=True)
            continue
        blocks, notes, fmt = text
        rel = out_path(d, CAT[t])
        if rel in used_paths:
            rel = rel[:-3] + "-" + d["vbpl_id"][:12] + ".md"
        used_paths.add(rel)
        title = nfc(d.get("name") or base_name(d))
        if t == "Hiến pháp":
            title = "Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam năm 2013"
        fm = {
            "title": title,
            "identifier": ident if ident != "Không số" else None,
            "type": CAT[t][0],
            "document_type": t,
            "jurisdiction": "vn",
            "language": "vi",
            "issuer": (d.get("legislationPassedBy") or {}).get("name"),
            "date": base_date or None,
        }
        eff = None
        for e in cb_by_num.get(normnum(ident), []):
            eff = dmy(e["fields"].get("Ngày hiệu lực"))
            if eff:
                break
        if eff:
            fm["effective"] = eff
        if consolidated:
            fm["last_amended"] = dmy(consolidated["fields"].get("Ngày ban hành"))
            fm["consolidated"] = True
            fm["consolidated_text"] = cb_num(consolidated)
        else:
            fm["consolidated"] = False
        fm["status"] = "in_force"
        fm["legal_force"] = d.get("legislationLegalForce")
        fm["source"] = used["url"]
        if used["cb_id"].startswith("cp"):
            fm["source_files"] = [f["url"] for f in pick_files(used)[1]]
        fm["source_format"] = fmt
        fm["gazette"] = "; ".join(used.get("gazettes") or []) or None
        fm["vbpl_url"] = d["vbpl_url"]
        fm["retrieved"] = TODAY
        fm = {k: v for k, v in fm.items() if v is not None}
        md = M.front_matter(fm) + M.build(blocks, notes, title)
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        rec.update({"status": "ok", "path": rel, "consolidated": bool(consolidated),
                    "source": used["url"], "format": fmt})
        manifest.append(rec)
        print("OK", rel, "VBHN" if consolidated else "", fmt, flush=True)
        if len(manifest) % 25 == 0:
            json.dump(manifest, open(manifest_p, "w"), ensure_ascii=False, indent=0)
    json.dump(manifest, open(manifest_p, "w"), ensure_ascii=False, indent=0)
    ok = sum(1 for r in manifest if r["status"] == "ok")
    print("done", ok, "written", len(manifest) - ok, "missing", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "laws")
