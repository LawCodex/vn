"""Crawl the Government portal's legal documents system (vanban.chinhphu.vn,
"Hệ thống văn bản") listing and record docid / number / date / title.

The listing is an ASP.NET GridView paged by form post-back (__doPostBack 'Page$N'), the
same request a browser sends when clicking a page number.

Usage: python vn_cp_list.py orggroupid=1 typegroupid=4
Output: _raw/vn/chinhphu/<query>.jsonl
"""
import json
import os
import re
import sys
import time

from bs4 import BeautifulSoup

from vn_common import RAW, _session, _throttle

BASE = "https://vanban.chinhphu.vn/he-thong-van-ban?classid=1&mode=1&"


def rows(soup):
    out = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"pageid=27160&docid=(\d+)", a["href"])
        if not m:
            continue
        tr = a.find_parent("tr")
        if tr is None:
            continue
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        out.append({"docid": m.group(1), "cells": cells})
    # one entry per docid
    seen, res = set(), []
    for r in out:
        if r["docid"] not in seen:
            seen.add(r["docid"])
            res.append(r)
    return res


def form_data(soup):
    data = {}
    form = soup.find("form", id="form1") or soup.find("form")
    for inp in form.find_all("input"):
        n = inp.get("name")
        if not n or inp.get("type") in ("submit", "button", "image"):
            continue
        data[n] = inp.get("value", "")
    return data


def request(method, url, **kw):
    for attempt in range(5):
        _throttle()
        try:
            r = _session.request(method, url, timeout=120, **kw)
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa
            print("retry", attempt, e, flush=True)
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError("failed " + url)


def crawl(q):
    url = BASE + q
    html = request("GET", url)
    soup = BeautifulSoup(html, "lxml")
    total = re.search(r"\d+ - \d+ \| (\d+)", soup.get_text(" "))
    total = int(total.group(1)) if total else 0
    grid = None
    for a in soup.find_all("a", href=True):
        m = re.search(r"__doPostBack\('([^']+grvDocument)','Page\$", a["href"])
        if m:
            grid = m.group(1)
            break
    os.makedirs(os.path.join(RAW, "chinhphu"), exist_ok=True)
    outp = os.path.join(RAW, "chinhphu", q.replace("=", "-") + ".jsonl")
    allrows = {}
    page = 1
    while True:
        for r in rows(soup):
            allrows.setdefault(r["docid"], r)
        print(q, "page", page, len(allrows), "/", total, flush=True)
        if len(allrows) >= total or not grid:
            break
        page += 1
        data = form_data(soup)
        data["__EVENTTARGET"] = grid
        data["__EVENTARGUMENT"] = "Page$%d" % page
        before = len(allrows)
        html = request("POST", url, data=data)
        soup = BeautifulSoup(html, "lxml")
        if not any(r["docid"] not in allrows for r in rows(soup)):
            print("no new rows on page", page, "- stopping", flush=True)
            break
    with open(outp, "w") as f:
        for r in allrows.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(q, "done", len(allrows), flush=True)


if __name__ == "__main__":
    for q in sys.argv[1:]:
        crawl(q)
