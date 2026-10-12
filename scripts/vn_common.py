"""Shared helpers for the LawCodex Viet Nam scripts (polite cached HTTP)."""
import hashlib
import os
import time
import threading

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("LAWCODEX_RAW",
                     os.path.join(os.path.dirname(ROOT), "_raw", "vn"))
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"

_session = requests.Session()
_session.headers["User-Agent"] = UA


def _ca_bundle():
    """certifi bundle + intermediates that some .gov.vn / chinhphu.vn servers fail to send
    (e.g. g7.cdnchinhphu.vn omits "GlobalSign RSA OV SSL CA 2018")."""
    import certifi
    out = os.path.join(RAW, "ca-bundle.pem")
    if not os.path.exists(out):
        os.makedirs(RAW, exist_ok=True)
        with open(out, "w") as f:
            f.write(open(certifi.where()).read())
            f.write("\n")
            f.write(open(os.path.join(ROOT, "scripts", "extra-intermediates.pem")).read())
    return out


_session.verify = _ca_bundle()
_lock = threading.Lock()
_last = [0.0]
DELAY = float(os.environ.get("LAWCODEX_DELAY", "1.0"))


def _throttle():
    with _lock:
        wait = _last[0] + DELAY - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def cache_path(url, sub, ext):
    h = hashlib.sha1(url.encode()).hexdigest()
    d = os.path.join(RAW, sub, h[:2])
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, h + ext)


def get(url, sub="http", ext=".html", binary=False, retries=4, timeout=120,
        refresh=False):
    """GET with on-disk cache under _raw/vn/<sub>/. Returns str/bytes or None."""
    p = cache_path(url, sub, ext)
    if os.path.exists(p) and not refresh:
        with open(p, "rb") as f:
            data = f.read()
        return data if binary else data.decode("utf-8", "replace")
    last = None
    for attempt in range(retries):
        _throttle()
        try:
            r = _session.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            data = r.content
            tmp = p + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, p)
            return data if binary else data.decode("utf-8", "replace")
        except Exception as e:  # noqa
            print("retry", attempt, url[:100], repr(e)[:120], flush=True)
            time.sleep(5 * (2 ** attempt))
            last = e
    print("FAILED", url, last, flush=True)
    return None
