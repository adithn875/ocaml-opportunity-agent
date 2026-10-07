"""Milestone 1 helper: for every source, check robots.txt and whether the page loads.

Run from the repo root, inside the venv:
    python scripts/check_sources.py
Prints one line per source. Nothing is saved; this is just a health check.

robots column:
  yes      robots.txt was read and allows this URL
  NO       robots.txt was read and DISALLOWS this URL  -> do not scrape it
  no-file  site has no robots.txt (404)                -> allowed
  unclear  robots.txt itself was blocked/unreadable    -> check by hand
"""
import time
from urllib.parse import urlparse

import yaml
from protego import Protego            # robots.txt parser (installed with Scrapling)
from scrapling.fetchers import Fetcher

DELAY_SECONDS = 2          # polite pause between requests
BOT_NAME = "*"             # we check the generic rules that apply to everyone

def robots_status(url: str) -> str:
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        # Use the same fetcher as the real scraper. (Python's urllib gets
        # blocked by some sites and then wrongly reports "disallowed".)
        resp = Fetcher.get(robots_url, timeout=15)
    except Exception:
        return "unclear"
    if resp.status == 404:
        return "no-file"
    if resp.status != 200:
        return "unclear"
    rules = Protego.parse(resp.body.decode("utf-8", errors="ignore"))
    return "yes" if rules.can_fetch(url, BOT_NAME) else "NO"

def main() -> None:
    cfg = yaml.safe_load(open("config/sources.yaml"))
    for e in cfg["aggregators"] + cfg["companies"]:
        url = e.get("api") or e["url"]
        robots = robots_status(url)
        try:
            page = Fetcher.get(url, timeout=20)
            moved = "" if page.url.rstrip("/") == url.rstrip("/") else f" -> redirected to {page.url}"
            result = f"HTTP {page.status}, {len(page.body)} bytes{moved}"
        except Exception as exc:
            result = f"FAILED ({type(exc).__name__})"
        print(f"{e['name']:<26} robots={robots:<8} {result}")
        time.sleep(DELAY_SECONDS)

if __name__ == "__main__":
    main()