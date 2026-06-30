#!/usr/bin/env python3
"""
author.today full-catalog scraper.

Three phases, all mandatory:

  Phase 1 — Genre listings
    71 genre URLs × up to 400 pages × 25 books = up to 710K raw entries.
    After deduplication this covers the full ~311K catalog.

  Phase 2 — Author works pages
    Every book card exposes /u/{slug}/works.
    Scraping each author page catches books that fell below every genre's
    top-10K pagination cap.

  Phase 3 — Tags
    Individual book pages (/work/{id}) carry the full tag list.
    Tags are not present on listing cards — only genres are.
    This phase visits every discovered work page and saves tags to
    tags_cache.jsonl, then merges everything into books.jsonl.
    It is resumable: a restart skips IDs already in tags_cache.jsonl.

State files (all in /data):
  genre_queue.txt     genre listing URLs still to process
  author_queue.txt    author works URLs still to process
  seen_ids.txt        work IDs already in books.jsonl
  seen_authors.txt    author URLs already scraped
  tags_cache.jsonl    {id, tags} written progressively during phase 3
  books.jsonl         final output (tags merged in at end of phase 3)
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

OUTPUT_FILE    = DATA_DIR / "books.jsonl"
TAGS_CACHE     = DATA_DIR / "tags_cache.jsonl"
GENRE_QUEUE    = DATA_DIR / "genre_queue.txt"
AUTHOR_QUEUE   = DATA_DIR / "author_queue.txt"
SEEN_IDS_FILE  = DATA_DIR / "seen_ids.txt"
SEEN_AUTH_FILE = DATA_DIR / "seen_authors.txt"

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
            log.warning("GET %s attempt %d: %s", url, attempt + 1, exc)
            time.sleep(10)
    log.error("GET %s failed after 3 attempts", url)
    return None


# ---------------------------------------------------------------------------
# Queue / seen helpers
# ---------------------------------------------------------------------------

def queue_load(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text().splitlines() if l.strip()]


def queue_save(path: Path, items: list[str]):
    path.write_text("\n".join(items) + ("\n" if items else ""))


def queue_pop(path: Path) -> str | None:
    items = queue_load(path)
    if not items:
        return None
    queue_save(path, items[1:])
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


def seen_add(path: Path, items: list[str]):
    with open(path, "a") as f:
        for i in items:
            f.write(i + "\n")


# ---------------------------------------------------------------------------
# Genre discovery
# ---------------------------------------------------------------------------

def fetch_genre_urls(session: requests.Session) -> list[str]:
    soup = fetch(session, f"{BASE_URL}/work/genres")
    if not soup:
        return []
    seen: set[str] = set()
    urls: list[str] = []
    for a in soup.select("a[href*='/work/genre/']"):
        href = a.get("href", "")
        if "/genre/all" in href or not href:
            continue
        slug = href.split("/work/genre/")[1].split("/")[0].split("?")[0]
        if slug and slug not in seen:
            seen.add(slug)
            urls.append(f"{BASE_URL}/work/genre/{slug}")
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
    """Returns (books, author_works_urls)."""
    cards = soup.select("div.book-row")
    books, author_urls = [], []
    for card in cards:
        book = _parse_card(card)
        if book:
            books.append(book)
            author_urls.extend(a["url"] for a in book["authors"] if a.get("url"))
    return books, author_urls


def _parse_card(card) -> dict | None:
    try:
        cover_a = card.select_one("div.book-cover-wrapper a[href^='/work/']")
        if not cover_a:
            return None
        work_href = cover_a["href"]
        work_id   = work_href.strip("/").split("/")[-1]

        title_a    = card.select_one("div.book-title > a")
        authors    = [
            {"name": _text(a), "url": _abs(a["href"])}
            for a in card.select("div.book-author a[href*='/u/']")
        ]
        genre_links = card.select("div.book-genres a")
        work_type   = _text(genre_links[0]) if genre_links else None
        genres      = [_text(a) for a in genre_links[1:]]
        img         = card.select_one("div.cover-image img")
        status_i    = card.select_one("i.book-status-icon")
        series_a    = card.select_one("a[href*='/work/series/']")
        time_el     = card.select_one("span[data-time]")
        chars_el    = card.select_one("span[data-hint*='кол-во знаков']")
        price_el    = card.select_one("span.text-bold.text-success")
        access_el   = card.select_one("span.text-success:not(.text-bold)")
        ann_el      = card.select_one(
            "div.annotation, div[data-bind*='read-more'].rich-text-content"
        )

        return {
            "id":         work_id,
            "url":        _abs(work_href),
            "title":      _text(title_a),
            "authors":    authors,
            "work_type":  work_type,
            "genres":     genres,
            "tags":       [],           # filled in Phase 3
            "status":     _text(status_i.parent) if status_i else None,
            "series":     {"name": _text(series_a), "url": _abs(series_a["href"])} if series_a else None,
            "updated_at": time_el["data-time"] if time_el else None,
            "views":      _stat_from_hint(card, "Просмотры"),
            "likes":      _stat_from_hint(card, "Понравилось"),
            "comments":   _stat_from_hint(card, "Комментарии"),
            "reviews":    _stat_from_hint(card, "Рецензии"),
            "chars":      _text(chars_el),
            "price":      _text(price_el),
            "access":     _text(access_el),
            "exclusive":  bool(card.select_one("div.ribbon")),
            "cover_url":  img.get("src") if img else None,
            "annotation": ann_el.get_text(separator=" ", strip=True) if ann_el else None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        log.debug("Card parse error: %s", exc, exc_info=True)
        return None


def next_page_url(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("a[rel='next']")
    if el and el.get("href"):
        return _abs(el["href"])
    return None


def fetch_tags(session: requests.Session, work_id: str) -> list[str]:
    soup = fetch(session, f"{BASE_URL}/work/{work_id}")
    if not soup:
        return []
    return [
        a.get("title") or _text(a)
        for a in soup.select("span.tags a[href*='/work/tag/']")
        if a.get("title") or _text(a)
    ]


# ---------------------------------------------------------------------------
# Output helpers
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
# Core listing loop  (shared by genre and author pages)
# ---------------------------------------------------------------------------

def scrape_listing(
    session: requests.Session,
    start_url: str,
    seen_ids: set[str],
    label: str,
) -> list[str]:
    """Paginate a listing URL. Returns all author_urls discovered."""
    url = start_url
    all_author_urls: list[str] = []
    page = 0

    while url:
        page += 1
        soup = fetch(session, url)
        if not soup:
            break
        books, author_urls = parse_cards(soup)
        if not books:
            log.warning("[%s] p%d — no cards, stopping", label, page)
            break
        new = save_new_books(books, seen_ids)
        all_author_urls.extend(author_urls)
        log.info("[%s] p%d — %d new books (total: %d)", label, page, len(new), len(seen_ids))
        url = next_page_url(soup)
        if url:
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    return all_author_urls


# ---------------------------------------------------------------------------
# Phase 3 — Tag scraping
# ---------------------------------------------------------------------------

def run_tag_scrape(session: requests.Session, seen_ids: set[str]):
    # Load already-fetched tags from the cache (restart-safe)
    tags_map: dict[str, list[str]] = {}
    if TAGS_CACHE.exists():
        with open(TAGS_CACHE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    tags_map[entry["id"]] = entry["tags"]

    remaining = [wid for wid in seen_ids if wid not in tags_map]
    log.info(
        "Phase 3: %d books need tags (%d already cached)",
        len(remaining), len(tags_map),
    )

    with open(TAGS_CACHE, "a", encoding="utf-8") as cache_f:
        for i, work_id in enumerate(remaining, 1):
            tags = fetch_tags(session, work_id)
            tags_map[work_id] = tags
            cache_f.write(json.dumps({"id": work_id, "tags": tags}, ensure_ascii=False) + "\n")
            cache_f.flush()

            if i % 500 == 0:
                log.info("  tags: %d / %d fetched", i, len(remaining))

            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("All tags fetched. Merging into books.jsonl …")

    tmp = OUTPUT_FILE.with_suffix(".tmp")
    with open(OUTPUT_FILE, encoding="utf-8") as fin, \
         open(tmp, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            book = json.loads(line)
            book["tags"] = tags_map.get(book["id"], [])
            fout.write(json.dumps(book, ensure_ascii=False) + "\n")

    tmp.replace(OUTPUT_FILE)
    log.info("Phase 3 complete. books.jsonl now includes tags.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session   = make_session()
    seen_ids  = seen_load(SEEN_IDS_FILE)
    seen_auth = seen_load(SEEN_AUTH_FILE)

    log.info("State: %d books, %d authors already done", len(seen_ids), len(seen_auth))

    # ── Phase 1: Genre listings ──────────────────────────────────────────────

    if not GENRE_QUEUE.exists():
        log.info("Seeding genre queue …")
        queue_save(GENRE_QUEUE, fetch_genre_urls(session))
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("Phase 1: %d genres to scrape", len(queue_load(GENRE_QUEUE)))

    while True:
        genre_url = queue_pop(GENRE_QUEUE)
        if not genre_url:
            break
        log.info("Genre: %s  (%d left)", genre_url, len(queue_load(GENRE_QUEUE)))
        author_urls = scrape_listing(session, genre_url, seen_ids, label="genre")

        new_authors = [u for u in set(author_urls) if u not in seen_auth]
        if new_authors:
            queue_extend(AUTHOR_QUEUE, new_authors)
            log.info("  → queued %d new authors", len(new_authors))

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("Phase 1 complete. Books: %d", len(seen_ids))

    # ── Phase 2: Author works pages ──────────────────────────────────────────

    log.info("Phase 2: %d author pages to scrape", len(queue_load(AUTHOR_QUEUE)))

    while True:
        author_url = queue_pop(AUTHOR_QUEUE)
        if not author_url:
            break
        if author_url in seen_auth:
            continue
        log.info("Author: %s  (%d left)", author_url, len(queue_load(AUTHOR_QUEUE)))
        scrape_listing(session, author_url, seen_ids, label="author")
        seen_add(SEEN_AUTH_FILE, [author_url])
        seen_auth.add(author_url)
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log.info("Phase 2 complete. Books: %d", len(seen_ids))

    # ── Phase 3: Tags ────────────────────────────────────────────────────────

    run_tag_scrape(session, seen_ids)

    log.info("All done. Total books with tags: %d", len(seen_ids))


if __name__ == "__main__":
    main()
