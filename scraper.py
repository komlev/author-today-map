#!/usr/bin/env python3
"""
author.today scraper — ID iteration strategy.

author.today uses auto-incremental work IDs starting from 1.
Current maximum is ~614 627. We iterate every ID, skip 404s fast,
and parse full data (including tags) from each valid page in one pass.

Two phases:

  Phase 1 — Work pages  (/work/1 … /work/MAX_ID)
    ~50% return 404 (deleted/unpublished) — skipped instantly, no delay.
    Valid pages yield: title, authors, genres, tags, status, series,
    views, likes, comments, chars, annotation, cover, updated_at.
    Output: books.jsonl

  Phase 2 — Author profiles  (/u/{slug}/works)
    Author URLs collected during Phase 1. Each page yields the full
    author profile. Output: authors.jsonl

Both phases are resumable: restart picks up from last processed ID
(Phase 1) or remaining author queue (Phase 2).

Env vars:
  COOKIES   — full browser Cookie header value (required)
  MAX_ID    — highest work ID to scrape (default 614627)
  MIN_DELAY — seconds between successful fetches (default 1.5)
  MAX_DELAY — seconds between successful fetches (default 4.0)
  DATA_DIR  — output directory (default /data)
  DEBUG     — set to 1 for verbose logging

State files (DATA_DIR):
  progress.json     last processed ID + counters
  author_queue.txt  author works URLs to scrape in Phase 2
  seen_authors.txt  author URLs already scraped
  books.jsonl       one book per line
  authors.jsonl     one author profile per line
"""

import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_URL = "https://author.today"
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))

BOOKS_FILE     = DATA_DIR / "books.jsonl"
AUTHORS_FILE   = DATA_DIR / "authors.jsonl"
PROGRESS_FILE  = DATA_DIR / "progress.json"
AUTHOR_QUEUE   = DATA_DIR / "author_queue.txt"
SEEN_AUTH_FILE = DATA_DIR / "seen_authors.txt"

MAX_ID    = int(os.environ.get("MAX_ID", "614627"))
MIN_DELAY = float(os.environ.get("MIN_DELAY", "1.5"))
MAX_DELAY = float(os.environ.get("MAX_DELAY", "4.0"))


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    raw = os.environ.get("COOKIES", "").strip()
    if not raw:
        log.error("COOKIES env var is not set.")
        sys.exit(1)
    cookies = {}
    for part in raw.split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            cookies[k.strip()] = v.strip()
    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) "
            "Gecko/20100101 Firefox/152.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": BASE_URL + "/",
    })
    return s


def fetch(session: requests.Session, url: str) -> tuple[int, BeautifulSoup | None, str]:
    """Returns (status_code, soup, final_url). soup is None on non-200 or error."""
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 404:
                return 404, None, url
            if resp.status_code == 429:
                wait = 60 * (attempt + 1)
                log.warning("Rate-limited, waiting %ds", wait)
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                log.warning("GET %s → %d", url, resp.status_code)
                return resp.status_code, None, resp.url
            return 200, BeautifulSoup(resp.text, "lxml"), resp.url
        except requests.RequestException as exc:
            log.warning("GET %s attempt %d: %s", url, attempt + 1, exc)
            time.sleep(10)
    return 0, None, url


# ---------------------------------------------------------------------------
# Book page parser
# ---------------------------------------------------------------------------

def _text(el) -> str | None:
    return el.get_text(strip=True) if el else None


def _abs(href: str) -> str:
    return href if href.startswith("http") else BASE_URL + href


def _hint_int(soup, prefix: str) -> int | None:
    el = soup.select_one(f"span[data-hint^='{prefix}']")
    if not el:
        return None
    hint = el.get("data-hint", "")
    part = hint.split("·")[-1] if "·" in hint else hint
    m = re.search(r"[\d\xa0 ]+", part)
    if m:
        try:
            return int(m.group().replace("\xa0", "").replace(" ", "").replace(" ", ""))
        except ValueError:
            pass
    return None


def parse_book_page(soup: BeautifulSoup, work_id: str, final_url: str) -> dict | None:
    # Confirm it's actually a book page (not a redirect/error page)
    if not soup.select_one("h1.book-title, div.book-meta-panel"):
        return None

    content_type = "audiobook" if "/audiobook/" in final_url else "ebook"

    try:
        # Audiobooks wrap the title in span[itemprop='name']; books put it directly in h1
        title_el = (
            soup.select_one("h1.book-title span[itemprop='name']")
            or soup.select_one("h1.book-title")
        )

        # Audiobook author hrefs have ?format=audiobook suffix, so use *= not $=
        authors = [
            {"name": _text(a), "url": _abs(a["href"].split("?")[0])}
            for a in soup.select("a[href*='/u/'][href*='/works']")
            if _text(a)
        ]

        genre_links = soup.select("div.book-genres a")
        work_type = _text(genre_links[0]) if genre_links else None
        genres    = [_text(a) for a in genre_links[1:]]

        tags = [
            a.get("title") or _text(a)
            for a in soup.select("span.tags a[href*='/work/tag/']")
            if a.get("title") or _text(a)
        ]

        cover_el  = soup.select_one("img.cover-image")
        status_i  = soup.select_one("i.book-status-icon")
        # Exclude the "buy series" button which also matches /work/series/
        series_a  = soup.select_one("a[href*='/work/series/']:not([href*='/buy/'])")
        time_el   = soup.select_one("span[data-time]")
        ann_el    = soup.select_one("div.annotation[itemprop='description']")

        # Char count — strip non-digits
        chars_el  = soup.select_one("span[data-hint*='знак']")
        chars_raw = _text(chars_el)
        chars     = int(re.sub(r"[^\d]", "", chars_raw)) if chars_raw else None

        # Comments count is JS-rendered on detail pages — not available in static HTML
        comments = None

        # Likes — in KnockoutJS component comment
        likes_m = re.search(r"likeCount:\s*(\d+)", str(soup))
        likes   = int(likes_m.group(1)) if likes_m else None

        exclusive   = bool(soup.select_one("div.ribbon"))
        ai_generated = bool(soup.select_one(".text-neural-networks, .icon-neural-networks"))

        return {
            "id":           work_id,
            "url":          f"{BASE_URL}/work/{work_id}",
            "content_type": content_type,
            "title":        _text(title_el),
            "authors":      authors,
            "work_type":    work_type,
            "genres":       genres,
            "tags":         tags,
            "status":       _text(status_i.parent) if status_i else None,
            "series":       {"name": _text(series_a), "url": _abs(series_a["href"])} if series_a else None,
            "updated_at":   time_el["data-time"] if time_el else None,
            "views":        _hint_int(soup, "Просмотры"),
            "likes":        likes,
            "comments":     comments,
            "chars":        chars,
            "exclusive":    exclusive,
            "ai_generated": ai_generated,
            "cover_url":    cover_el.get("src") if cover_el else None,
            "annotation":   ann_el.get_text(separator=" ", strip=True) if ann_el else None,
            "scraped_at":   datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        log.debug("Book parse error for %s: %s", work_id, exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Author profile parser  (same page as /u/{slug}/works)
# ---------------------------------------------------------------------------

def _nav_count(soup: BeautifulSoup, href_suffix: str) -> int | None:
    el = soup.select_one(f"a[href*='{href_suffix}'] .nav-value")
    if not el:
        return None
    try:
        return int(re.sub(r"[^\d]", "", el.get_text()))
    except ValueError:
        return None


def parse_author_profile(soup: BeautifulSoup, works_url: str) -> dict | None:
    try:
        slug = works_url.rstrip("/").split("/u/")[1].split("/")[0]

        name_el  = soup.select_one(".profile-name h1 a, .profile-name h1")
        photo_el = soup.select_one("img.avatar")
        motto_el = soup.select_one(".profile-status span")
        uid_m    = re.search(r"userId:\s*(\d+)", str(soup))

        last_active = None
        act = soup.select_one(".activity-status")
        if act:
            el = act.find_next("span", attrs={"data-time": True})
            if el:
                last_active = el.get("data-time")

        def _stat(prefix):
            el = soup.select_one(f"span[data-hint^='{prefix}']")
            if el:
                m = re.search(r"[\d\xa0  ]+$", el.get("data-hint", ""))
                if m:
                    try: return int(re.sub(r"[^\d]", "", m.group()))
                    except: pass
            return None

        return {
            "slug":                slug,
            "user_id":             uid_m.group(1) if uid_m else None,
            "url":                 works_url,
            "name":                _text(name_el),
            "photo_url":           photo_el.get("src") if photo_el else None,
            "motto":               _text(motto_el),
            "reputation_dynamic":  _stat("Динамическая репутация"),
            "reputation_absolute": _stat("Абсолютная репутация"),
            "rating_dynamic":      _stat("Динамический рейтинг автора"),
            "rating_absolute":     _stat("Абсолютный рейтинг автора"),
            "series_count":        _nav_count(soup, "/series"),
            "followers":           _nav_count(soup, "/followers"),
            "following":           _nav_count(soup, "/following"),
            "friends":             _nav_count(soup, "/friends"),
            "achievements":        _nav_count(soup, "/awards"),
            "comments_count":      _nav_count(soup, "/comments"),
            "last_active_at":      last_active,
            "scraped_at":          datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        log.debug("Author parse error for %s: %s", works_url, exc)
        return None


# ---------------------------------------------------------------------------
# Queue / progress helpers
# ---------------------------------------------------------------------------

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"last_id": 0, "books_scraped": 0, "skipped": 0}


def save_progress(p: dict):
    PROGRESS_FILE.write_text(json.dumps(p, indent=2))


def queue_load(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text().splitlines() if l.strip()]


def queue_pop(path: Path) -> str | None:
    items = queue_load(path)
    if not items:
        return None
    path.write_text("\n".join(items[1:]) + "\n")
    return items[0]


def queue_extend(path: Path, new_items: list[str]):
    existing = set(queue_load(path))
    to_add = [u for u in new_items if u not in existing]
    if to_add:
        with open(path, "a") as f:
            f.write("\n".join(to_add) + "\n")


def seen_load(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(path.read_text().split())


def seen_add(path: Path, item: str):
    with open(path, "a") as f:
        f.write(item + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session   = make_session()
    progress  = load_progress()
    seen_auth = seen_load(SEEN_AUTH_FILE)

    start_id      = progress["last_id"] + 1
    books_scraped = progress["books_scraped"]
    skipped       = progress["skipped"]

    log.info(
        "Phase 1: IDs %d → %d  (%d books so far, %d skipped)",
        start_id, MAX_ID, books_scraped, skipped,
    )

    # ── Phase 1: Iterate work IDs ────────────────────────────────────────────

    author_urls_batch: list[str] = []

    for work_id in range(start_id, MAX_ID + 1):
        url = f"{BASE_URL}/work/{work_id}"
        status, soup, final_url = fetch(session, url)

        if status == 404:
            skipped += 1
            # No delay for 404 — cheap for both sides
            if work_id % 1000 == 0:
                log.info("ID %d — %d books, %d skipped", work_id, books_scraped, skipped)
            save_progress({"last_id": work_id, "books_scraped": books_scraped, "skipped": skipped})
            continue

        if status != 200 or soup is None:
            log.warning("ID %d → status %d, skipping", work_id, status)
            save_progress({"last_id": work_id, "books_scraped": books_scraped, "skipped": skipped})
            time.sleep(5)
            continue

        book = parse_book_page(soup, str(work_id), final_url)
        if not book:
            log.debug("ID %d — parsed no data (not a book page?)", work_id)
            save_progress({"last_id": work_id, "books_scraped": books_scraped, "skipped": skipped})
            continue

        with open(BOOKS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(book, ensure_ascii=False) + "\n")

        books_scraped += 1
        author_urls_batch.extend(a["url"] for a in book["authors"] if a.get("url"))

        # Flush new author URLs every 100 books
        if len(author_urls_batch) >= 100:
            new = [u for u in set(author_urls_batch) if u not in seen_auth]
            queue_extend(AUTHOR_QUEUE, new)
            author_urls_batch = []

        if books_scraped % 500 == 0:
            log.info("ID %d — %d books scraped, %d skipped", work_id, books_scraped, skipped)

        save_progress({"last_id": work_id, "books_scraped": books_scraped, "skipped": skipped})
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    # Flush remaining author URLs
    if author_urls_batch:
        new = [u for u in set(author_urls_batch) if u not in seen_auth]
        queue_extend(AUTHOR_QUEUE, new)

    log.info("Phase 1 complete. Books: %d, Skipped: %d", books_scraped, skipped)

    # ── Phase 2: Author profiles ─────────────────────────────────────────────

    author_total = len(queue_load(AUTHOR_QUEUE))
    log.info("Phase 2: %d author profiles to scrape", author_total)

    while True:
        author_url = queue_pop(AUTHOR_QUEUE)
        if not author_url:
            break
        if author_url in seen_auth:
            continue

        status, soup, _ = fetch(session, author_url)
        if status == 200 and soup:
            profile = parse_author_profile(soup, author_url)
            if profile:
                with open(AUTHORS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(profile, ensure_ascii=False) + "\n")
                log.debug("Author saved: %s (%d followers)", profile.get("name"), profile.get("followers") or 0)

        seen_add(SEEN_AUTH_FILE, author_url)
        seen_auth.add(author_url)

        remaining = len(queue_load(AUTHOR_QUEUE))
        if remaining % 500 == 0:
            log.info("Authors remaining: %d", remaining)

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("All done. Books: %d, Authors: %d", books_scraped, len(seen_auth))


if __name__ == "__main__":
    main()
