#!/usr/bin/env python3
"""
author.today full-catalog scraper.

Two-phase strategy to reach all ~311K books:

  Phase 1 — Genre listings
    Fetch every genre slug from /work/genres.
    For each genre, paginate through all pages (up to 400 pages × 25 books).
    ~70 genres × 10K cap = up to 700K raw entries → ~311K unique books after dedup.

  Phase 2 — Author works pages
    Every book card exposes the author's /u/{slug}/works URL.
    After Phase 1, scrape each unique author page to catch books that
    fell below every genre's top-10K.

State files (all in /data, restart-safe):
  genre_queue.txt   — genre listing URLs still to process
  author_queue.txt  — author works URLs still to process
  seen_ids.txt      — work IDs already saved (dedup)
  seen_authors.txt  — author URLs already scraped (dedup)
  books.jsonl       — output: one JSON object per line

Optional Phase 3 — Tags (DEEP_SCRAPE=1):
  Visit each individual work page to add the full tag list.
  ~311K extra requests; ~173 h at default rate — use sparingly.

Usage:
  docker compose run --rm scraper
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

OUTPUT_FILE     = DATA_DIR / "books.jsonl"
GENRE_QUEUE     = DATA_DIR / "genre_queue.txt"
AUTHOR_QUEUE    = DATA_DIR / "author_queue.txt"
SEEN_IDS_FILE   = DATA_DIR / "seen_ids.txt"
SEEN_AUTH_FILE  = DATA_DIR / "seen_authors.txt"

MIN_DELAY   = float(os.environ.get("MIN_DELAY",   "1.5"))
MAX_DELAY   = float(os.environ.get("MAX_DELAY",   "4.0"))
DEEP_SCRAPE = os.environ.get("DEEP_SCRAPE", "").lower() in ("1", "true", "yes")


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


def fetch(session: requests.Session, url: str) -> BeautifulSoup | None:
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 429:
                wait = 60 * (attempt + 1)
                log.warning("Rate-limited, waiting %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            log.warning("GET %s attempt %d failed: %s", url, attempt + 1, exc)
            time.sleep(10)
    log.error("GET %s failed after 3 attempts", url)
    return None


# ---------------------------------------------------------------------------
# Queue helpers  (simple flat text files, one URL per line)
# ---------------------------------------------------------------------------

def queue_load(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    return [l.strip() for l in lines if l.strip()]


def queue_save(path: Path, items: list[str]):
    path.write_text("\n".join(items) + ("\n" if items else ""))


def queue_pop(path: Path) -> str | None:
    items = queue_load(path)
    if not items:
        return None
    url = items[0]
    queue_save(path, items[1:])
    return url


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


def seen_add(path: Path, items: list[str]):
    with open(path, "a") as f:
        for i in items:
            f.write(i + "\n")


# ---------------------------------------------------------------------------
# Genre discovery
# ---------------------------------------------------------------------------

def fetch_genre_urls(session: requests.Session) -> list[str]:
    """Scrape /work/genres and return unique genre listing URLs."""
    soup = fetch(session, f"{BASE_URL}/work/genres")
    if not soup:
        return []
    slugs_seen: set[str] = set()
    urls = []
    for a in soup.select("a[href*='/work/genre/']"):
        href = a.get("href", "")
        # Drop the /all catch-all; we collect per-genre for better coverage
        if "/genre/all" in href or not href:
            continue
        # Normalise to bare genre slug URL (no sub-type filter)
        slug = href.split("/work/genre/")[1].split("/")[0].split("?")[0]
        if slug and slug not in slugs_seen:
            slugs_seen.add(slug)
            urls.append(f"{BASE_URL}/work/genre/{slug}")
    # Always include the all-ebook listing as an extra seed
    urls.append(f"{BASE_URL}/work/genre/all/ebook")
    log.info("Discovered %d genre URLs", len(urls))
    return urls


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _text(el) -> str | None:
    return el.get_text(strip=True) if el else None


def _abs(href: str) -> str:
    return href if href.startswith("http") else BASE_URL + href


def _stat_from_hint(card, label: str) -> int | None:
    for span in card.select("span[data-hint]"):
        hint = span.get("data-hint", "")
        if hint.startswith(label):
            m = re.search(r"[\d\xa0 ]+$", hint)
            if m:
                try:
                    return int(m.group().replace("\xa0", "").replace(" ", ""))
                except ValueError:
                    pass
    return None


def parse_cards(soup: BeautifulSoup) -> tuple[list[dict], list[str]]:
    """
    Returns (books, author_urls).
    author_urls are /u/{slug}/works links found in the cards.
    """
    cards = soup.select("div.book-row")
    books, author_urls = [], []
    for card in cards:
        book = _parse_card(card)
        if book:
            books.append(book)
            author_urls.extend(a["url"] for a in book["authors"] if a["url"])
    return books, author_urls


def _parse_card(card) -> dict | None:
    try:
        cover_a = card.select_one("div.book-cover-wrapper a[href^='/work/']")
        if not cover_a:
            return None
        work_href = cover_a["href"]
        work_id = work_href.strip("/").split("/")[-1]
        work_url = _abs(work_href)

        title_a = card.select_one("div.book-title > a")

        authors = [
            {"name": _text(a), "url": _abs(a["href"])}
            for a in card.select("div.book-author a[href*='/u/']")
        ]

        genre_links = card.select("div.book-genres a")
        work_type = _text(genre_links[0]) if genre_links else None
        genres    = [_text(a) for a in genre_links[1:]]

        img     = card.select_one("div.cover-image img")
        status_i = card.select_one("i.book-status-icon")
        series_a = card.select_one("a[href*='/work/series/']")
        time_el  = card.select_one("span[data-time]")
        chars_el = card.select_one("span[data-hint*='кол-во знаков']")
        price_el = card.select_one("span.text-bold.text-success")
        access_el = card.select_one("span.text-success:not(.text-bold)")
        ann_el   = card.select_one(
            "div.annotation, div[data-bind*='read-more'].rich-text-content"
        )

        return {
            "id":          work_id,
            "url":         work_url,
            "title":       _text(title_a),
            "authors":     authors,
            "work_type":   work_type,
            "genres":      genres,
            "tags":        [],
            "status":      _text(status_i.parent) if status_i else None,
            "series":      {
                "name": _text(series_a),
                "url":  _abs(series_a["href"])
            } if series_a else None,
            "updated_at":  time_el["data-time"] if time_el else None,
            "views":       _stat_from_hint(card, "Просмотры"),
            "likes":       _stat_from_hint(card, "Понравилось"),
            "comments":    _stat_from_hint(card, "Комментарии"),
            "reviews":     _stat_from_hint(card, "Рецензии"),
            "chars":       _text(chars_el),
            "price":       _text(price_el),
            "access":      _text(access_el),
            "exclusive":   bool(card.select_one("div.ribbon")),
            "cover_url":   img.get("src") if img else None,
            "annotation":  ann_el.get_text(separator=" ", strip=True) if ann_el else None,
            "scraped_at":  datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        log.debug("Card parse error: %s", exc, exc_info=True)
        return None


def next_page_url(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("a[rel='next']")
    if el and el.get("href"):
        return _abs(el["href"])
    return None


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def save_new_books(books: list[dict], seen_ids: set[str]) -> list[dict]:
    new = [b for b in books if b["id"] not in seen_ids]
    if new:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for b in new:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
        ids = [b["id"] for b in new]
        seen_add(SEEN_IDS_FILE, ids)
        seen_ids.update(ids)
    return new


# ---------------------------------------------------------------------------
# Tags (optional deep scrape)
# ---------------------------------------------------------------------------

def fetch_tags(session: requests.Session, work_id: str) -> list[str]:
    soup = fetch(session, f"{BASE_URL}/work/{work_id}")
    if not soup:
        return []
    return [
        a.get("title") or _text(a)
        for a in soup.select("span.tags a[href*='/work/tag/']")
        if a.get("title") or _text(a)
    ]


def run_deep_scrape(session: requests.Session, seen_ids: set[str]):
    log.info("Deep scrape: enriching %d books with tags", len(seen_ids))
    books: dict[str, dict] = {}
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        for line in f:
            b = json.loads(line)
            books[b["id"]] = b

    for i, (work_id, book) in enumerate(books.items(), 1):
        if book.get("tags"):
            continue
        book["tags"] = fetch_tags(session, work_id)
        if i % 100 == 0:
            log.info("  tags: %d / %d", i, len(books))
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for b in books.values():
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    log.info("Deep scrape complete.")


# ---------------------------------------------------------------------------
# Core scrape loop  (shared by genre listings and author works pages)
# ---------------------------------------------------------------------------

def scrape_listing(
    session: requests.Session,
    start_url: str,
    seen_ids: set[str],
    label: str,
) -> tuple[int, list[str]]:
    """
    Paginate through all pages of a listing URL.
    Returns (new_books_count, discovered_author_urls).
    """
    url = start_url
    total_new = 0
    all_author_urls: list[str] = []
    page = 0

    while url:
        page += 1
        soup = fetch(session, url)
        if not soup:
            break

        books, author_urls = parse_cards(soup)
        if not books:
            log.warning("[%s] p%d — no cards found, stopping", label, page)
            break

        new = save_new_books(books, seen_ids)
        total_new += len(new)
        all_author_urls.extend(author_urls)

        log.info("[%s] p%d — %d new (total saved: %d)", label, page, len(new), total_new)

        url = next_page_url(soup)
        if url:
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    return total_new, all_author_urls


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session  = make_session()
    seen_ids  = seen_load(SEEN_IDS_FILE)
    seen_auth = seen_load(SEEN_AUTH_FILE)

    log.info("Resuming with %d known books, %d known authors", len(seen_ids), len(seen_auth))

    # ── Phase 1: Genre listings ──────────────────────────────────────────────

    if not GENRE_QUEUE.exists():
        log.info("Seeding genre queue from /work/genres …")
        genre_urls = fetch_genre_urls(session)
        queue_save(GENRE_QUEUE, genre_urls)
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    genre_total = len(queue_load(GENRE_QUEUE))
    log.info("Phase 1: %d genres to scrape", genre_total)

    while True:
        genre_url = queue_pop(GENRE_QUEUE)
        if not genre_url:
            break
        remaining = len(queue_load(GENRE_QUEUE))
        log.info("Genre: %s  (%d remaining)", genre_url, remaining)
        _, author_urls = scrape_listing(session, genre_url, seen_ids, label="genre")

        # Enqueue new authors discovered from this genre
        new_authors = [u for u in set(author_urls) if u not in seen_auth]
        if new_authors:
            queue_extend(AUTHOR_QUEUE, new_authors)
            log.info("  → queued %d new author URLs", len(new_authors))

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("Phase 1 complete. Books saved: %d", len(seen_ids))

    # ── Phase 2: Author works pages ──────────────────────────────────────────

    author_total = len(queue_load(AUTHOR_QUEUE))
    log.info("Phase 2: %d author pages to scrape", author_total)

    while True:
        author_url = queue_pop(AUTHOR_QUEUE)
        if not author_url:
            break
        if author_url in seen_auth:
            continue
        remaining = len(queue_load(AUTHOR_QUEUE))
        log.info("Author: %s  (%d remaining)", author_url, remaining)
        scrape_listing(session, author_url, seen_ids, label="author")
        seen_add(SEEN_AUTH_FILE, [author_url])
        seen_auth.add(author_url)
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("Phase 2 complete. Books saved: %d", len(seen_ids))

    # ── Phase 3: Tags (optional) ─────────────────────────────────────────────

    if DEEP_SCRAPE:
        run_deep_scrape(session, seen_ids)

    log.info("All done. Total books: %d", len(seen_ids))


if __name__ == "__main__":
    main()
