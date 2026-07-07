"""Data loader: gap between a book's (estimated) posting date and its last edit.

Reads data/books.jsonl. Reuses growth-timeline.json.py's estimated_created_at
technique (running min of updated_at by id — a valid, if sometimes loose,
upper bound on true creation date; see that file's docstring for the proof).

gap_days = updated_at - estimated_created_at, per book. Two things follow
directly from how estimated_created_at is defined:
  - gap_days is always >= 0.
  - gap_days == 0 exactly means "self-anchored": no book with a higher id
    ever had an earlier updated_at, which only happens if this book's own
    updated_at was never pushed forward by an edit — i.e. never touched
    after publishing. ~42% of the corpus falls here (matches the /growth
    and /velocity docstrings' corpus-wide figures).
  - For everything else, gap_days is a LOWER bound on the true revision gap
    (since estimated_created_at is itself an upper bound on true creation,
    the real gap could be larger, never smaller) — caveated on the page.

Unlike /velocity (removed 2026-07-07 — that page needed a *reliable*
per-book creation-time proxy, which only the self-anchored subset provides,
so non-self-anchored books were unusable there), this page's whole point is
the gap itself, so every book contributes: gap == 0 is its own bucket
("never touched"), gap > 0 feeds the edit-gap distribution and leaderboards.

Same platform/contest-account exclusion as graphomaniac-stats.json.py,
coauthor-network.json.py, velocity-bursts.json.py, etc.
"""
import json
import os
import re
import statistics as st
from collections import defaultdict
from datetime import datetime

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

EXCLUDED_AUTHOR_URLS = {
    "https://author.today/u/contest_audio/works",
    "https://author.today/u/future/works",
    "https://author.today/u/evolution/works",
    "https://author.today/u/contest8/works",
}

MIN_BOOKS_FOR_LEADERBOARD = 5
TOP_N = 25


def canonical(url: str) -> str:
    url = url.replace("http://", "https://", 1) if url.startswith("http://") else url
    return re.sub(r"(/works).*$", r"\1", url)


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


books = []
with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        if not book.get("updated_at"):
            continue
        books.append(book)

books.sort(key=lambda b: int(b["id"]))

running_min = None
for book in reversed(books):
    updated_at = book["updated_at"]
    if running_min is None or updated_at < running_min:
        running_min = updated_at
    book["estimated_created_at"] = running_min

for book in books:
    gap_days = (parse(book["updated_at"]) - parse(book["estimated_created_at"])).total_seconds() / 86400
    book["gap_days"] = gap_days

never_touched = [b for b in books if b["gap_days"] <= 0]
updated = [b for b in books if b["gap_days"] > 0]
updated_gap_values = [b["gap_days"] for b in updated]

per_author = defaultdict(lambda: {"name": None, "url": None, "book_count": 0, "never_touched_count": 0, "gap_sum": 0.0, "gap_count": 0})
for book in books:
    for author in book.get("authors") or []:
        url = author.get("url")
        if not url:
            continue
        url = canonical(url)
        if url in EXCLUDED_AUTHOR_URLS:
            continue
        entry = per_author[url]
        entry["name"] = author.get("name")
        entry["url"] = url
        entry["book_count"] += 1
        if book["gap_days"] <= 0:
            entry["never_touched_count"] += 1
        else:
            entry["gap_sum"] += book["gap_days"]
            entry["gap_count"] += 1

never_touch_authors = [
    {"name": e["name"], "url": e["url"], "book_count": e["book_count"]}
    for e in per_author.values()
    if e["book_count"] >= MIN_BOOKS_FOR_LEADERBOARD and e["never_touched_count"] == e["book_count"]
]
never_touch_authors.sort(key=lambda d: -d["book_count"])

long_revisers = [
    {
        "name": e["name"],
        "url": e["url"],
        "book_count": e["book_count"],
        "updated_count": e["gap_count"],
        "avg_gap_days": round(e["gap_sum"] / e["gap_count"], 1),
    }
    for e in per_author.values()
    if e["gap_count"] >= MIN_BOOKS_FOR_LEADERBOARD
]
long_revisers.sort(key=lambda d: -d["avg_gap_days"])

result = {
    "total_books": len(books),
    "never_touched_count": len(never_touched),
    "updated_count": len(updated),
    "median_gap_days": round(st.median(updated_gap_values), 1),
    "mean_gap_days": round(st.mean(updated_gap_values), 1),
    "max_gap_days": round(max(updated_gap_values), 1),
    # Not rounded: gap_days > 0 is guaranteed here, but rounding to 2 decimals
    # would collapse sub-minute gaps to exactly 0.0, and the page's log-scaled
    # histogram takes log10() of every value — log10(0) is -Infinity, which
    # breaks the log-threshold computation (same class of bug as the
    # /engagement Plot.bin-on-a-log-scale gotcha, just from the data side
    # this time instead of Plot's side).
    "gap_days_points": updated_gap_values,
    "min_books_for_leaderboard": MIN_BOOKS_FOR_LEADERBOARD,
    "top_never_touch_authors": never_touch_authors[:TOP_N],
    "top_long_revisers": long_revisers[:TOP_N],
}

print(json.dumps(result, ensure_ascii=False))
