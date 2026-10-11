"""Turn extracted text blocks into structured Markdown (headings for Phần/Chương/Mục/Điều)."""
import re
import unicodedata

import yaml

RE_PHAN = re.compile(r"^(Phần|PHẦN)\s+(thứ\s+\S+|THỨ\s+\S+|[IVXLC]+|\d+)\b(.*)$")
RE_CHUONG = re.compile(r"^(Chương|CHƯƠNG)\s+([IVXLC]+|\d+|[A-Z])\b\.?(.*)$")
RE_MUC = re.compile(r"^(Mục|MỤC)\s+(\d+|[IVXLC]+)\b\.?(.*)$")
RE_TIEUMUC = re.compile(r"^(Tiểu mục|TIỂU MỤC)\s+(\d+)\b\.?(.*)$")
RE_DIEU = re.compile(r"^(Điều|ĐIỀU)\s+(\d+[a-zđ]?)\s*[\.:]?(\s.*|)$")

LEVELS = ["phan", "chuong", "muc", "tieumuc"]


def clean(s):
    s = s.replace("\xa0", " ").replace("​", "").replace("\t", " ")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[ ]{2,}", " ", s)
    return s.strip()


JUNK_RE = re.compile(
    r"^(PAGE\s*\d*\s*)?C[ÔO]NG\s*B[ÁA]O\s*/\s*S[ốỐ].*$|"      # gazette running header
    r"^PAGE\s*\d*$|^\d{1,4}\s+CÔNG BÁO\s*/.*$|"
    r"^Ký bởi:.*(Thời gian ký|Cơ quan:).*$", re.I)


def is_junk(s):
    return bool(JUNK_RE.match(s))


def is_upper_title(s):
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    up = sum(1 for c in letters if c.isupper())
    return up / len(letters) > 0.85


def esc(line):
    """Escape characters that would turn a plain legal paragraph into Markdown syntax."""
    line = re.sub(r"^(\d+)\.(\s)", r"\1\\.\2", line)
    line = re.sub(r"^([-+*>#|])", r"\\\1", line)
    line = line.replace("<", "&lt;")
    return line


def md_table(rows):
    rows = [[clean(c).replace("\n", "<br>").replace("|", "\\|") for c in r] for r in rows]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return ""
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * n]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def kind(text):
    if RE_PHAN.match(text):
        return "phan"
    if RE_CHUONG.match(text):
        return "chuong"
    if RE_TIEUMUC.match(text):
        return "tieumuc"
    if RE_MUC.match(text):
        return "muc"
    if RE_DIEU.match(text):
        return "dieu"
    return None


def build(blocks, notes, h1):
    """Return the Markdown body (H1 + content + footnotes)."""
    # normalise blocks; split paragraphs containing hard line breaks
    items = []
    for t, v in blocks:
        if t == "p":
            for part in v.split("\n"):
                c = clean(part)
                if c and not is_junk(c):
                    items.append(("p", c))
        else:
            items.append(("table", v))
    # header table (issuer | national motto) at the top -> plain paragraphs
    if items and items[0][0] == "table":
        flat = " ".join(" ".join(r) for r in items[0][1])
        if "CỘNG HÒA" in flat.upper() or "Độc lập" in flat:
            cells = []
            for r in items[0][1]:
                for c in r:
                    for part in c.split("\n"):
                        if clean(part):
                            cells.append(("p", clean(part)))
            items = cells + items[1:]
    # which structural levels exist?
    present = set()
    for t, v in items:
        if t == "p":
            k = kind(v)
            if k and k != "dieu":
                present.add(k)
    order = [lv for lv in LEVELS if lv in present]
    hlevel = {lv: min(2 + i, 6) for i, lv in enumerate(order)}
    dieu_level = min(2 + len(order), 6)

    out = ["# " + h1, ""]
    i = 0
    n = len(items)
    while i < n:
        t, v = items[i]
        if t == "table":
            # one-column "tables" are usually framed text boxes: keep as paragraphs
            if all(len(r) <= 1 for r in v):
                for r in v:
                    for c in r:
                        for part in c.split("\n"):
                            if clean(part):
                                out += [esc(clean(part)), ""]
            else:
                tb = md_table(v)
                if tb:
                    out += [tb, ""]
            i += 1
            continue
        k = kind(v)
        if k in hlevel:
            title = v
            # merge following all-caps title lines (e.g. "Chương I" + "NHỮNG QUY ĐỊNH CHUNG")
            j = i + 1
            m = {"phan": RE_PHAN, "chuong": RE_CHUONG, "muc": RE_MUC,
                 "tieumuc": RE_TIEUMUC}[k].match(v)
            rest = m.group(3).strip() if m else ""
            parts = []
            while j < n and items[j][0] == "p" and not kind(items[j][1]) and \
                    is_upper_title(items[j][1]) and len(parts) < 3:
                parts.append(items[j][1])
                j += 1
            if not parts and not rest.strip(" .:-–") and j < n and items[j][0] == "p" and \
                    not kind(items[j][1]) and len(items[j][1]) < 200 and \
                    not items[j][1].endswith((".", ";", ":")):
                parts.append(items[j][1])
                j += 1
            if parts:
                title = v.rstrip(" .:-–") + ". " + " ".join(parts)
            out += ["#" * hlevel[k] + " " + title.replace("#", "\\#"), ""]
            i = j
            continue
        if k == "dieu":
            if dieu_level <= 6:
                out += ["#" * dieu_level + " " + v.replace("#", "\\#"), ""]
            else:
                out += ["**" + v + "**", ""]
            i += 1
            continue
        out += [esc(v), ""]
        i += 1
    if notes:
        out.append("")
        for k2, txt in notes.items():
            lines = [clean(x) for x in txt.split("\n") if clean(x)]
            if not lines:
                lines = [""]
            out.append("[^%s]: %s" % (k2, lines[0].replace("<", "&lt;")))
            for ln in lines[1:]:
                out.append("    " + ln.replace("<", "&lt;"))
            out.append("")
    body = "\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    return body


def front_matter(meta):
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000,
                        default_flow_style=False)
    return "---\n" + fm + "---\n\n"


def slugify(s, maxlen=100):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s
