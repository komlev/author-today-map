#!/usr/bin/env python3
"""Re-fetch and patch books.jsonl entries with phantom authors.

Background: an old version of scraper.py's author selector matched *any*
/u/{slug}/works link on the page, including ones embedded in free-text
annotations (e.g. "совместно с: <link>" dedications/shoutouts to other
authors). Those got scraped as extra phantom co-authors whose "name" is
literally the profile URL instead of a real name. The selector itself is
fixed in scraper.py (parse_authors_list, scoped to div.book-authors), but
books already scraped before the fix keep the bad entries forever —
scraper.py's Phase 1 never revisits an ID it already has.

This script finds books with at least one such phantom author, re-fetches
each page live, and replaces the *entire* authors list with a fresh parse
using today's fixed logic (not just dropping the bad entry — a real author
could also be missing/malformed on the same page). Safe to (re-)run any
time; it only touches entries matching the broken pattern, so it's a no-op
once the data is clean. Same design as fix_series.py — see that script for
the sibling case this mirrors.

Run wherever the data volume lives (e.g. via `docker compose run --rm
fix-authors` on the VPS, or locally against a copied books.jsonl) before
copying data elsewhere, so downstream copies are already clean. Rerunning
scripts/extract_authors.py afterward will pick up the corrected authors.

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
    parse_authors_list,
)


def is_broken(authors: list[dict]) -> bool:
    return any((a.get("name") or "").startswith("http") for a in authors)


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
    bad = [b for b in books if is_broken(b.get("authors") or [])]

    log.info("Scanned %d books, found %d with a phantom author", len(books), len(bad))
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

        new_authors = parse_authors_list(soup)
        old_authors = book.get("authors")
        book["authors"] = new_authors
        fixed += 1
        log.info("ID %s: %r -> %r", book["id"], old_authors, new_authors)

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    tmp_path = str(BOOKS_FILE) + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for book in books:
            f.write(json.dumps(book, ensure_ascii=False) + "\n")
    os.replace(tmp_path, BOOKS_FILE)

    log.info("Done. Patched %d, skipped %d (still broken, retry next run)", fixed, skipped)


if __name__ == "__main__":
    main()
