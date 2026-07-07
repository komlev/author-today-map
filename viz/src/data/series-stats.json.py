"""Data loader: series vs standalone book stats.

Reads data/books.jsonl. `series` is either null or {"name", "url"}.

Some authors use the "series" field as a generic bucket (e.g. "Стихи",
"Юмор") rather than an actual ordered series — these pollute the top-series
leaderboards, so they're excluded and their books counted as standalone.

Remaining series are split into "poetry" and "literary": a handful of real,
distinctly-named poetry series (e.g. "БОСЯ - ЮТУБ", "СТИШКУНЫ") consist of
dozens of very short individual poems each published as its own "book" —
mixed into one leaderboard with novel series, they'd dominate every
book-count ranking purely on the strength of being poems, not because
they're unusually long-running literary series. A series counts as poetry
if at least half of its books carry the "Поэзия" genre.
"""
import json
import os
from collections import defaultdict

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

EXCLUDED_SERIES_NAMES = {
    "сказки", "стихи", "кинообзоры", "фантастика", "юмор",
    "анекдоты -перлы-ахренизмы-юмор",
    "рассказы влада выставного",
}

POETRY_GENRE = "Поэзия"
POETRY_FRACTION_THRESHOLD = 0.5

series_books = defaultdict(lambda: {"name": None, "books": []})
standalone = {"count": 0, "views": 0, "likes": 0}

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        series = book.get("series")

        is_excluded = series and (series.get("name") or "").strip().lower() in EXCLUDED_SERIES_NAMES

        if series and series.get("url") and not is_excluded:
            entry = series_books[series["url"]]
            entry["name"] = series.get("name")
            entry["books"].append(book)
        else:
            standalone["count"] += 1
            standalone["views"] += book.get("views") or 0
            standalone["likes"] += book.get("likes") or 0


def series_category(books):
    poetry_count = sum(1 for b in books if POETRY_GENRE in (b.get("genres") or []))
    return "poetry" if poetry_count / len(books) >= POETRY_FRACTION_THRESHOLD else "literary"


categories = {"literary": {}, "poetry": {}}
for url, entry in series_books.items():
    cat = series_category(entry["books"])
    views = sum(b.get("views") or 0 for b in entry["books"])
    likes = sum(b.get("likes") or 0 for b in entry["books"])
    categories[cat][url] = {
        "name": entry["name"],
        "url": url,
        "count": len(entry["books"]),
        "views": views,
        "likes": likes,
    }


def build_category(series_map):
    book_total = sum(s["count"] for s in series_map.values())
    views_total = sum(s["views"] for s in series_map.values())
    likes_total = sum(s["likes"] for s in series_map.values())

    size_distribution = defaultdict(int)
    for s in series_map.values():
        size_distribution[s["count"]] += 1

    top_by_book_count = sorted(series_map.values(), key=lambda s: -s["count"])[:20]
    top_by_views = sorted(series_map.values(), key=lambda s: -s["views"])[:20]

    return {
        "series_count": len(series_map),
        "book_count": book_total,
        "avg_views_per_book": round(views_total / book_total, 1) if book_total else 0,
        "avg_likes_per_book": round(likes_total / book_total, 1) if book_total else 0,
        "size_distribution": [{"series_length": k, "count": v} for k, v in sorted(size_distribution.items())],
        "top_by_book_count": [
            {"name": s["name"], "url": s["url"], "book_count": s["count"], "total_views": s["views"]} for s in top_by_book_count
        ],
        "top_by_views": [
            {"name": s["name"], "url": s["url"], "book_count": s["count"], "total_views": s["views"]} for s in top_by_views
        ],
    }


literary = build_category(categories["literary"])
poetry = build_category(categories["poetry"])

series_book_total = literary["book_count"] + poetry["book_count"]
series_views_total = sum(s["views"] for s in categories["literary"].values()) + sum(
    s["views"] for s in categories["poetry"].values()
)

summary = {
    "series_books": series_book_total,
    "standalone_books": standalone["count"],
    "series_count": literary["series_count"] + poetry["series_count"],
    "avg_views_series_book": round(series_views_total / series_book_total, 1) if series_book_total else 0,
    "avg_views_standalone_book": round(standalone["views"] / standalone["count"], 1) if standalone["count"] else 0,
}

result = {
    "summary": summary,
    "literary": literary,
    "poetry": poetry,
}

print(json.dumps(result, ensure_ascii=False))
