#!/usr/bin/env python3
"""Backfill rewards_count, reviews_count, downloads_count, library_stats, and comments
onto books.jsonl entries scraped before scraper.py added those fields.

Background: these 5 fields were added to parse_book_page/fetch_comment_count/
fetch_library_stats after the full 334K-book corpus was already scraped, so
scraper.py's Phase 1 (which never revisits an ID it already has) will never fill
them in on its own. This script finds books missing any of the 5 keys, re-fetches
each live page plus the two extra async endpoints (comments, library stats), and
patches just those 5 fields in place — leaving every other field (authors, series,
tags, annotation, ...) untouched, even if the live page has since changed.

Costs 3 requests per stale book (page + comment count + library stats), same as a
normal Phase 1 fetch under the current scraper.py. Safe to (re-)run any time —
only touches entries missing one of the 5 keys, so it's a no-op once the data is
current.

Run wherever the data volume lives (e.g. via `docker compose run --rm
backfill-stats` on the VPS, or locally against a copied books.jsonl) before
copying data elsewhere, so downstream copies are already up to date.

Env vars: same as scraper.py (COOKIES required; DATA_DIR, MIN_DELAY, MAX_DELAY
optional).
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
    fetch_comment_count,
    fetch_library_stats,
    log,
    make_session,
    parse_book_page,
)

BACKFILL_FIELDS = ["rewards_count", "reviews_count", "downloads_count", "library_stats", "comments"]


def is_stale(book: dict) -> bool:
    return any(field not in book for field in BACKFILL_FIELDS)


def main():
    if not BOOKS_FILE.exists():
        log.error("%s not found", BOOKS_FILE)
        sys.exit(1)

    # Held for the whole read+patch+write pass — see books_file_lock's docstring.
    # In particular this must wrap the *read* too, not just the write: reading
    # before a concurrent fix script's write has landed is exactly what caused
    # the silent clobber this lock prevents.
    with books_file_lock():
        _run()


def _run():
    with open(BOOKS_FILE, encoding="utf-8") as f:
        lines = f.readlines()

    books = [json.loads(line) for line in lines if line.strip()]
    stale = [b for b in books if is_stale(b)]

    log.info("Scanned %d books, found %d missing one of %s", len(books), len(stale), BACKFILL_FIELDS)
    if not stale:
        return

    session = make_session()
    fixed = skipped = 0

    for i, book in enumerate(stale, start=1):
        url = f"{BASE_URL}/work/{book['id']}"
        status, soup, final_url = fetch(session, url)
        if status != 200 or soup is None:
            log.warning("ID %s → status %d, leaving as-is for a future retry", book["id"], status)
            skipped += 1
            continue

        fresh = parse_book_page(soup, book["id"], final_url)
        if not fresh:
            log.warning("ID %s → parsed no data (not a book page?), leaving as-is", book["id"])
            skipped += 1
            continue

        book["rewards_count"]   = fresh["rewards_count"]
        book["reviews_count"]   = fresh["reviews_count"]
        book["downloads_count"] = fresh["downloads_count"]

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY) / 2)
        book["comments"] = fetch_comment_count(session, book["id"])

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY) / 2)
        book["library_stats"] = fetch_library_stats(session, book["id"])

        fixed += 1
        if fixed % 100 == 0:
            log.info("Backfilled %d/%d (ID %s)", i, len(stale), book["id"])

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    tmp_path = str(BOOKS_FILE) + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for book in books:
            f.write(json.dumps(book, ensure_ascii=False) + "\n")
    os.replace(tmp_path, BOOKS_FILE)

    log.info("Done. Backfilled %d, skipped %d (still stale, retry next run)", fixed, skipped)


if __name__ == "__main__":
    main()
