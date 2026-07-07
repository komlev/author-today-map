#!/usr/bin/env python3
"""Re-fetch and patch books.jsonl entries with a broken `series` field.

Background: an old version of scraper.py's series selector matched *any*
/work/series/ link on the page, including ones embedded in free-text
annotations (e.g. a fanfic's annotation linking to the original work's
series page). Those got scraped with `series.name` literally equal to the
URL instead of a title. The selector itself is fixed in scraper.py
(parse_series_link), but books already scraped before the fix keep the bad
value forever — scraper.py's Phase 1 never revisits an ID it already has.

This script finds those already-scraped bad entries, re-fetches each page
live, and patches the record in place using the same (fixed) parsing logic
scraper.py uses today. Safe to (re-)run any time, including on a fresh
Phase 1 run at a higher MAX_ID — it only ever touches entries matching the
broken pattern, so it's a no-op once the data is clean.

Run wherever the data volume lives (e.g. via `docker compose run --rm
fix-series` on the VPS, or locally against a copied books.jsonl) before
copying data elsewhere, so downstream copies are already clean.

Env vars: same as scraper.py (COOKIES required; DATA_DIR, MIN_DELAY,
MAX_DELAY optional).
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scraper import (  # noqa: E402
    BOOKS_FILE,
    MIN_DELAY,
    MAX_DELAY,
    BASE_URL,
    books_file_lock,
    fetch,
    log,
    make_session,
    parse_series_link,
)


def is_broken(series: dict | None) -> bool:
    if not series:
        return False
    name = series.get("name") or ""
    return name.startswith("http")


def main():
    if not BOOKS_FILE.exists():
        log.error("%s not found", BOOKS_FILE)
        sys.exit(1)

    # Held for the whole read+patch+write pass — see books_file_lock's
    # docstring. In particular this must wrap the *read* too, not just the
    # write: reading before a concurrent fix script's write has landed is
    # exactly what caused the silent clobber this lock prevents.
    with books_file_lock():
        _run()


def _run():
    with open(BOOKS_FILE, encoding="utf-8") as f:
        lines = f.readlines()

    books = [json.loads(line) for line in lines if line.strip()]
    bad = [b for b in books if is_broken(b.get("series"))]

    log.info("Scanned %d books, found %d with a broken series field", len(books), len(bad))
    if not bad:
        return

    session = make_session()
    fixed = skipped = 0

    for book in bad:
        url = f"{BASE_URL}/work/{book['id']}"
        status, soup, _ = fetch(session, url)
        if status != 200 or soup is None:
            log.warning("ID %s → status %d, leaving as-is for a future retry", book["id"], status)
            skipped += 1
            continue

        new_series = parse_series_link(soup)
        old_series = book.get("series")
        book["series"] = new_series
        fixed += 1
        log.info("ID %s: %r -> %r", book["id"], old_series, new_series)

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    tmp_path = str(BOOKS_FILE) + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for book in books:
            f.write(json.dumps(book, ensure_ascii=False) + "\n")
    os.replace(tmp_path, BOOKS_FILE)

    log.info("Done. Patched %d, skipped %d (still broken, retry next run)", fixed, skipped)


if __name__ == "__main__":
    main()
