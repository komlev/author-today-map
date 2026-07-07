"""Data loader: authors with the highest average book length ("графоманы").

Reads data/books.jsonl. Splits by ai_generated since a book's AI flag is
per-book, not per-author — an author's AI and human works are tracked as
separate entries here.

Note: as of this writing only a handful of books are flagged ai_generated,
so the AI leaderboard will be sparse/empty until more of the scrape with
AI-flagged content completes.
"""
import json
import os
from collections import defaultdict

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

# Platform/contest accounts credited as a book's "author" — not people, and
# with high enough book counts (e.g. contest_audio: 679) to otherwise land
# in this leaderboard. Same exclusion in scripts/extract_authors.py and
# coauthor-network.json.py.
EXCLUDED_AUTHOR_URLS = {
    "https://author.today/u/contest_audio/works",
    "https://author.today/u/future/works",
    "https://author.today/u/evolution/works",
    "https://author.today/u/contest8/works",
}

MIN_BOOKS_FOR_LEADERBOARD = 5
TOP_N = 20

per_author = defaultdict(lambda: {"name": None, "count": 0, "chars": 0})
overall = {
    True: {"count": 0, "chars": 0},
    False: {"count": 0, "chars": 0},
}

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        chars = book.get("chars") or 0
        ai_generated = bool(book.get("ai_generated"))

        agg = overall[ai_generated]
        agg["count"] += 1
        agg["chars"] += chars

        for author in book.get("authors") or []:
            url = author.get("url")
            if not url or url in EXCLUDED_AUTHOR_URLS:
                continue
            entry = per_author[(url, ai_generated)]
            entry["name"] = author.get("name")
            entry["count"] += 1
            entry["chars"] += chars

leaderboard = defaultdict(list)
for (url, ai_generated), entry in per_author.items():
    if entry["count"] >= MIN_BOOKS_FOR_LEADERBOARD:
        leaderboard[ai_generated].append({
            "name": entry["name"],
            "book_count": entry["count"],
            "total_chars": entry["chars"],
            "avg_chars": round(entry["chars"] / entry["count"]),
        })

result = {
    "overall": [
        {
            "ai_generated": ai_generated,
            "count": agg["count"],
            "avg_chars": round(agg["chars"] / agg["count"]) if agg["count"] else 0,
        }
        for ai_generated, agg in overall.items()
    ],
    "min_books_for_leaderboard": MIN_BOOKS_FOR_LEADERBOARD,
    "top_non_ai": sorted(leaderboard[False], key=lambda d: -d["avg_chars"])[:TOP_N],
    "top_ai": sorted(leaderboard[True], key=lambda d: -d["avg_chars"])[:TOP_N],
}

print(json.dumps(result, ensure_ascii=False))
