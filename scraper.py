#!/usr/bin/env python3
"""
author.today scraper — collects books with authors, genres, and metadata.

Two-phase design:
  Phase 1 (always): scrape listing pages → genres, authors, stats, annotation
  Phase 2 (opt-in): visit each book page → tags (not present on listing cards)
                    Enable with env: DEEP_SCRAPE=1

Output:
  /data/books.jsonl        one JSON object per line
  /data/progress.json      resume state (restart-safe)
  /data/deep_queue.txt     work IDs pending deep scrape (one per line)

Scale note:
  Listing pagination is capped at 400 pages × 25 = 10 000 books per sort/filter.
  To get full coverage (311 492 ebooks), run multiple passes over each genre URL:
    /work/genre/all/ebook
    /work/genre/sf-fantasy
    /work/genre/sf-history  ... etc
  Deduplication is done by work ID.

Usage:
  docker compose run --rm scraper
  docker compose run --rm scraper https://author.today/work/genre/sf-fantasy
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
from bs4 import BeautifulSoup, Comment

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
OUTPUT_FILE = DATA_DIR / "books.jsonl"
PROGRESS_FILE = DATA_DIR / "progress.json"
SEEN_FILE = DATA_DIR / "seen_ids.txt"
DEEP_QUEUE_FILE = DATA_DIR / "deep_queue.txt"

MIN_DELAY = float(os.environ.get("MIN_DELAY", "1.5"))
MAX_DELAY = float(os.environ.get("MAX_DELAY", "4.0"))
DEEP_SCRAPE = os.environ.get("DEEP_SCRAPE", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def parse_cookie_string(raw: str) -> dict:
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            cookies[k.strip()] = v.strip()
    return cookies


def make_session() -> requests.Session:
    raw = os.environ.get("COOKIES", "").strip()
    if not raw:
        log.error("COOKIES env var is not set. Copy the full Cookie: header value into cookies.env.")
        sys.exit(1)
    s = requests.Session()
    s.cookies.update(parse_cookie_string(raw))
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


def fetch(session: requests.Session, url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as exc:
        log.error("GET %s → %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Parsing: listing card  (div.book-row)
# ---------------------------------------------------------------------------

def _text(el) -> str | None:
    return el.get_text(strip=True) if el else None


def _abs(href: str) -> str:
    return href if href.startswith("http") else BASE_URL + href


def parse_listing_cards(soup: BeautifulSoup) -> list[dict]:
    cards = soup.select("div.book-row")
    if not cards:
        log.warning("No div.book-row found on page")
    return [r for c in cards if (r := _parse_card(c)) is not None]


def _parse_card(card) -> dict | None:
    try:
        # Work URL / ID  — from cover link
        cover_a = card.select_one("div.book-cover-wrapper a[href^='/work/']")
        if not cover_a:
            return None
        work_href = cover_a["href"]                         # e.g. /work/607216
        work_id = work_href.strip("/").split("/")[-1]       # 607216
        work_url = _abs(work_href)

        # Title
        title_a = card.select_one("div.book-title > a")
        title = _text(title_a) if title_a else None

        # Authors  (one or more <a> inside div.book-author)
        authors = [
            {"name": _text(a), "url": _abs(a["href"])}
            for a in card.select("div.book-author a[href*='/u/']")
        ]

        # Genres  — first link in book-genres is the form type (Роман etc.), rest are real genres
        genre_links = card.select("div.book-genres a")
        work_type = _text(genre_links[0]) if genre_links else None   # Роман / Рассказ / …
        genres = [_text(a) for a in genre_links[1:]]

        # Cover image
        img = card.select_one("div.cover-image img")
        cover_url = img.get("src") if img else None

        # Exclusive badge
        exclusive = bool(card.select_one("div.ribbon"))

        # Status  ("в процессе" | "завершена" | …)
        status_i = card.select_one("i.book-status-icon")
        status = status_i.parent.get_text(strip=True) if status_i else None

        # Series
        series_a = card.select_one("a[href*='/work/series/']")
        series = {"name": _text(series_a), "url": _abs(series_a["href"])} if series_a else None

        # Updated at  — ISO timestamp in data-time attribute
        time_el = card.select_one("span[data-time]")
        updated_at = time_el["data-time"] if time_el else None

        # Stats: exact numbers are in data-hint attribute
        views = _stat_from_hint(card, "Просмотры")
        likes = _stat_from_hint(card, "Понравилось")
        comments = _stat_from_hint(card, "Комментарии")
        reviews = _stat_from_hint(card, "Рецензии")

        # Character count
        chars_el = card.select_one("span[data-hint*='кол-во знаков']")
        chars_raw = _text(chars_el)

        # Price / access type
        price_el = card.select_one("span.text-bold.text-success")
        price = _text(price_el)
        access_el = card.select_one("span.text-success:not(.text-bold)")
        access = _text(access_el)   # e.g. "Подписка", "Бесплатно"

        # Annotation (short, truncated in listing)
        ann_el = card.select_one("div.annotation, div[data-bind*='read-more'].rich-text-content")
        annotation = ann_el.get_text(separator=" ", strip=True) if ann_el else None

        return {
            "id": work_id,
            "url": work_url,
            "title": title,
            "authors": authors,
            "work_type": work_type,
            "genres": genres,
            "tags": [],                 # filled in by deep scrape if DEEP_SCRAPE=1
            "status": status,
            "series": series,
            "updated_at": updated_at,
            "views": views,
            "likes": likes,
            "comments": comments,
            "reviews": reviews,
            "chars": chars_raw,
            "price": price,
            "access": access,
            "exclusive": exclusive,
            "cover_url": cover_url,
            "annotation": annotation,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        log.debug("Card parse error: %s", exc, exc_info=True)
        return None


def _stat_from_hint(card, label: str) -> int | None:
    """Parse exact count from data-hint like 'Просмотры · 185 784'."""
    for span in card.select("span[data-hint]"):
        hint = span.get("data-hint", "")
        if hint.startswith(label):
            m = re.search(r"[\d\s]+$", hint)
            if m:
                try:
                    return int(m.group().replace("\xa0", "").replace(" ", ""))
                except ValueError:
                    pass
    return None


# ---------------------------------------------------------------------------
# Parsing: individual book page  (for tags)
# ---------------------------------------------------------------------------

def scrape_book_tags(session: requests.Session, work_id: str) -> list[str]:
    url = f"{BASE_URL}/work/{work_id}"
    soup = fetch(session, url)
    if not soup:
        return []
    # <span class="tags"> contains <a title="tag text"> links
    return [
        a.get("title") or _text(a)
        for a in soup.select("span.tags a[href*='/work/tag/']")
        if a.get("title") or _text(a)
    ]


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def next_page_url(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("a[rel='next']")
    if el and el.get("href"):
        return _abs(el["href"])
    return None


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"next_url": None, "pages_done": 0, "books_scraped": 0}


def save_progress(p: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(p, f, indent=2)


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(SEEN_FILE.read_text().split())
    return set()


def mark_seen(ids: list[str], seen: set[str]):
    seen.update(ids)
    with open(SEEN_FILE, "a") as f:
        for i in ids:
            f.write(i + "\n")


def append_books(books: list[dict]):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for b in books:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


def enqueue_deep(ids: list[str]):
    with open(DEEP_QUEUE_FILE, "a") as f:
        for i in ids:
            f.write(i + "\n")


# ---------------------------------------------------------------------------
# Deep scrape phase (optional)
# ---------------------------------------------------------------------------

def run_deep_scrape(session: requests.Session):
    if not DEEP_QUEUE_FILE.exists():
        log.info("Deep queue is empty, skipping.")
        return

    ids = DEEP_QUEUE_FILE.read_text().split()
    if not ids:
        return

    log.info("Deep scrape: %d books to enrich with tags", len(ids))

    # Load existing books into memory, keyed by ID
    books: dict[str, dict] = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    b = json.loads(line)
                    books[b["id"]] = b

    enriched = 0
    for i, work_id in enumerate(ids, 1):
        if work_id not in books:
            log.warning("ID %s not in books.jsonl, skipping", work_id)
            continue

        tags = scrape_book_tags(session, work_id)
        books[work_id]["tags"] = tags
        enriched += 1

        if i % 50 == 0:
            log.info("  deep: %d / %d enriched", i, len(ids))

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    # Rewrite output file
    log.info("Rewriting books.jsonl with tags (%d enriched)", enriched)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for b in books.values():
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    DEEP_QUEUE_FILE.unlink(missing_ok=True)
    log.info("Deep scrape complete.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def scrape(start_url: str):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    session = make_session()
    progress = load_progress()
    seen = load_seen()

    url = progress["next_url"] or start_url
    pages_done = progress["pages_done"]
    total = progress["books_scraped"]

    log.info(
        "Starting at page %d: %s%s",
        pages_done + 1,
        url,
        " [DEEP_SCRAPE enabled]" if DEEP_SCRAPE else "",
    )

    while url:
        log.info("[page %d] %s", pages_done + 1, url)
        soup = fetch(session, url)
        if soup is None:
            log.error("Fetch failed, stopping.")
            break

        books = parse_listing_cards(soup)
        if not books:
            log.warning("No books parsed — check selectors or cookies.")
            break

        # Deduplicate
        new_books = [b for b in books if b["id"] not in seen]
        dup_count = len(books) - len(new_books)
        if dup_count:
            log.debug("  skipped %d duplicates", dup_count)

        if new_books:
            if DEEP_SCRAPE:
                enqueue_deep([b["id"] for b in new_books])
            append_books(new_books)
            mark_seen([b["id"] for b in new_books], seen)
            total += len(new_books)

        pages_done += 1
        log.info("  -> %d new books (total: %d)", len(new_books), total)

        nxt = next_page_url(soup)
        save_progress({"next_url": nxt, "pages_done": pages_done, "books_scraped": total})

        if not nxt:
            log.info("Last page reached.")
            break

        url = nxt
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("Listing scrape done. Total books: %d", total)

    if DEEP_SCRAPE:
        run_deep_scrape(session)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else f"{BASE_URL}/work/genre/all/ebook"
    scrape(target)
