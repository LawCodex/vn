"""Crawl Công báo (congbao.chinhphu.vn) listing pages and extract document metadata.

Usage: python vn_cb_list.py <listing-slug> [<listing-slug> ...]
  e.g. quoc-hoi-c31 uy-ban-thuong-vu-quoc-hoi-c28 van-phong-quoc-hoi-c47 nghi-dinh-l1

Writes _raw/vn/congbao/<slug>.jsonl (one JSON object per document).
Listing pages are always re-fetched (they change); nothing else is downloaded here.
"""
import json
import os
import sys

from bs4 import BeautifulSoup

from vn_common import RAW, get

BASE = "https://congbao.chinhphu.vn"


def parse_items(html):
    s = BeautifulSoup(html, "lxml")
    out = []
    for it in s.select("div.item--vb"):
        d = {"cb_id": it.get("data-id"), "fields": {}, "files": [], "gazettes": []}
        for a in it.find_all("a", href=True):
            h = a["href"]
            if h.startswith("/van-ban/") and "#" not in h and "url" not in d:
                d["url"] = BASE + h
                d["title"] = a.get("title") or a.get_text(" ", strip=True)
            elif "cdnchinhphu.vn/api/download" in h:
                f = {"name": a.get("title") or a.get_text(strip=True), "url": h}
                if f not in d["files"]:
                    d["files"].append(f)
            elif h.startswith("/cong-bao/"):
                g = a.get_text(" ", strip=True)
                if g not in d["gazettes"]:
                    d["gazettes"].append(g)
        for row in it.select("div.row"):
            n = row.select_one(".name")
            v = row.select_one(".value")
            if n and v:
                d["fields"][n.get_text(" ", strip=True)] = v.get_text(" ", strip=True)
        out.append(d)
    return out


def crawl(slug):
    os.makedirs(os.path.join(RAW, "congbao"), exist_ok=True)
    outp = os.path.join(RAW, "congbao", slug + ".jsonl")
    seen = set()
    n = 0
    with open(outp + ".tmp", "w") as fo:
        page = 1
        empty = 0
        while True:
            url = f"{BASE}/van-ban-dang-cong-bao/{slug}.htm" if page == 1 else \
                f"{BASE}/van-ban-dang-cong-bao/{slug}/trang-{page}.htm"
            html = get(url, sub="cblist", refresh=True)
            items = parse_items(html) if html else []
            new = [i for i in items if i["cb_id"] not in seen]
            if not new:
                empty += 1
                if empty >= 2:
                    break
            else:
                empty = 0
            for i in new:
                seen.add(i["cb_id"])
                i["list"] = slug
                fo.write(json.dumps(i, ensure_ascii=False) + "\n")
                n += 1
            if page % 20 == 0:
                print(slug, "page", page, "docs", n, flush=True)
            page += 1
    os.replace(outp + ".tmp", outp)
    print(slug, "done", page - 1, "pages", n, "docs", flush=True)


if __name__ == "__main__":
    for sl in sys.argv[1:]:
        crawl(sl)
