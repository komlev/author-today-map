"""Data loader: engagement quality — length vs popularity, ratio leaderboard, exclusivity.

Reads data/books.jsonl. Ships chars/views as raw points (one per book with
both > 0); Plot's client-side bin transform handles the 2D histogram, which
plays more nicely with log-scaled ticks than pre-computed log bins would.
"""
import json
import os
from collections import defaultdict

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

MIN_VIEWS_FOR_RATIO = 1000
TOP_N_RATIO = 25

points = []
exclusive_agg = {
    True: {"count": 0, "views": 0, "likes": 0},
    False: {"count": 0, "views": 0, "likes": 0},
}
ratio_candidates = []

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        chars = book.get("chars") or 0
        views = book.get("views") or 0
        likes = book.get("likes") or 0
        exclusive = bool(book.get("exclusive"))

        agg = exclusive_agg[exclusive]
        agg["count"] += 1
        agg["views"] += views
        agg["likes"] += likes

        if chars > 0 and views > 0:
            points.append({"chars": chars, "views": views, "exclusive": exclusive})

        if views >= MIN_VIEWS_FOR_RATIO:
            authors = book.get("authors") or []
            ratio_candidates.append({
                "title": book.get("title"),
                "author": authors[0]["name"] if authors else None,
                "author_url": authors[0]["url"] if authors else None,
                "url": book.get("url"),
                "views": views,
                "likes": likes,
                "ratio": likes / views,
            })

ratio_candidates.sort(key=lambda d: -d["ratio"])

result = {
    "chars_views_points": points,
    "top_by_ratio": ratio_candidates[:TOP_N_RATIO],
    "exclusive_summary": [
        {
            "exclusive": exclusive,
            "count": agg["count"],
            "avg_views": round(agg["views"] / agg["count"], 1) if agg["count"] else 0,
            "avg_likes": round(agg["likes"] / agg["count"], 1) if agg["count"] else 0,
        }
        for exclusive, agg in exclusive_agg.items()
    ],
}

print(json.dumps(result, ensure_ascii=False))
