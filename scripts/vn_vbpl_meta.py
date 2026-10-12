"""Fetch document metadata (incl. legal force / hiệu lực) from vbpl.vn detail pages.

vbpl.vn (Cơ sở dữ liệu quốc gia về pháp luật, Ministry of Justice) server-renders a
schema.org `Legislation` JSON-LD block on every detail page; the full text itself is loaded
client-side from an API host (vbpl-bientap-gateway.moj.gov.vn, /api/ is disallowed by
robots.txt on vbpl.vn and the gateway is not reachable from outside Viet Nam), so only the
metadata is used from here.

Usage: python vn_vbpl_meta.py            # uses _raw/vn/sitemap/*.xml (downloads if missing)
Output: _raw/vn/vbpl_meta.jsonl (resumable)
"""
import json
import os
import re
import sys

from vn_common import RAW, cache_path, get

PREFIXES = ("hien-phap", "bo-luat", "luat-", "phap-lenh", "nghi-quyet",
            "van-ban-hop-nhat", "nghi-dinh", "sac-luat")


def sitemap_urls():
    urls = []
    idx = get("https://vbpl.vn/sitemap.xml", sub="sitemap_cache", ext=".xml")
    # central-government sitemaps are listed before the "Địa phương" comment
    central = idx.split("Địa phương")[0]
    for sm in re.findall(r"<loc>([^<]+)</loc>", central):
        if sm.endswith("/0.xml"):
            continue
        x = get(sm, sub="sitemap_cache", ext=".xml")
        if x:
            urls += re.findall(r"<url><loc>([^<]+)</loc>", x)
    return urls


def rsc_payload(html):
    """Concatenate the Next.js RSC flight chunks (self.__next_f.push([1,"..."]))."""
    parts = []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html):
        try:
            parts.append(json.loads(m.group(1)))
        except Exception:
            pass
    return "".join(parts)


def parse(html):
    out = {}
    for raw in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            j = json.loads(raw)
        except Exception:
            continue
        if isinstance(j, dict) and j.get("@type") == "Legislation":
            out = j
            break
    payload = "" if out else rsc_payload(html)
    for m in re.finditer(r'"__html":("(?:[^"\\]|\\.)*")', payload):
        try:
            j = json.loads(json.loads(m.group(1)))
        except Exception:
            continue
        if isinstance(j, dict) and j.get("@type") == "Legislation":
            out = j
            break
    t = re.search(r"<title>([^<]*)</title>", html)
    if t:
        out["page_title"] = t.group(1).replace(" | CSDL quốc gia về pháp luật", "").strip()
    for k in ("article:published_time", "article:modified_time"):
        m = re.search(r'property="%s" content="([^"]+)"' % k, html)
        if m:
            out[k] = m.group(1)
    return out


def main():
    urls = sitemap_urls()
    cand = [u for u in urls if u.split("/chi-tiet/")[-1].startswith(PREFIXES)]
    if len(sys.argv) > 1:
        cand = [u for u in cand if any(u.split("/chi-tiet/")[-1].startswith(p) for p in sys.argv[1:])]
    outp = os.path.join(RAW, "vbpl_meta.jsonl")
    done = set()
    if os.path.exists(outp):
        for line in open(outp):
            try:
                done.add(json.loads(line)["vbpl_url"])
            except Exception:
                pass
    todo = [u for u in cand if u not in done]
    # laws, ordinances, resolutions and consolidated texts first, decrees last
    todo.sort(key=lambda u: u.split("/chi-tiet/")[-1].startswith("nghi-dinh"))
    print(len(cand), "candidates", len(todo), "to fetch", flush=True)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    wlock = threading.Lock()

    def one(u):
        # the HTML is ~80 KB and only the metadata is kept: cache in a throwaway dir
        html = get(u, sub="vbpl_tmp")
        if html is None:
            return None
        meta = parse(html)
        meta["vbpl_url"] = u
        meta["vbpl_id"] = u.rsplit("--", 1)[-1]
        try:
            os.remove(cache_path(u, "vbpl_tmp", ".html"))
        except OSError:
            pass
        return meta

    with open(outp, "a") as fo, ThreadPoolExecutor(4) as ex:
        for n, meta in enumerate(ex.map(one, todo)):
            if meta is None:
                continue
            with wlock:
                fo.write(json.dumps(meta, ensure_ascii=False) + "\n")
                fo.flush()
            if n % 200 == 0:
                print(n, meta["vbpl_url"][:120], meta.get("legislationLegalForce"), flush=True)

if __name__ == "__main__":
    main()
