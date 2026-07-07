"""Data loader: completion status and work-type breakdowns.

Reads data/books.jsonl and emits overall + per-genre status/work_type
counts, plus avg length/views by work_type.
"""
import json
import os
from collections import Counter, defaultdict

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

TOP_GENRES_FOR_STATUS = 15

status_counts = Counter()
work_type_counts = Counter()
genre_counts = Counter()
status_by_genre = defaultdict(Counter)
work_type_agg = defaultdict(lambda: {"count": 0, "chars": 0, "views": 0})

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        status = book.get("status") or "не указан"
        work_type = book.get("work_type") or "не указан"
        genres = book.get("genres") or []

        status_counts[status] += 1
        work_type_counts[work_type] += 1
        genre_counts.update(genres)
        for genre in genres:
            status_by_genre[genre][status] += 1

        agg = work_type_agg[work_type]
        agg["count"] += 1
        agg["chars"] += book.get("chars") or 0
        agg["views"] += book.get("views") or 0

top_genres = [g for g, _ in genre_counts.most_common(TOP_GENRES_FOR_STATUS)]

result = {
    "status_counts": [{"status": s, "count": c} for s, c in status_counts.most_common()],
    "work_type_counts": [{"work_type": w, "count": c} for w, c in work_type_counts.most_common()],
    "status_by_genre": [
        {"genre": genre, "status": status, "count": count}
        for genre in top_genres
        for status, count in status_by_genre[genre].items()
    ],
    "work_type_stats": [
        {
            "work_type": w,
            "count": agg["count"],
            "avg_chars": round(agg["chars"] / agg["count"]) if agg["count"] else 0,
            "avg_views": round(agg["views"] / agg["count"]) if agg["count"] else 0,
        }
        for w, agg in work_type_agg.items()
    ],
}

print(json.dumps(result, ensure_ascii=False))
