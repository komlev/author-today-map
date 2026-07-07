"""Data loader: per-author productivity stats.

Reads data/authors_from_books.jsonl (already aggregated by
scripts/extract_authors.py) and adds a couple of derived fields.
"""
import json
import os

AUTHORS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "authors_from_books.jsonl"
)

authors = []
with open(AUTHORS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        a = json.loads(line)
        book_count = a.get("book_count") or 0
        a["avg_views_per_book"] = round(a["total_views"] / book_count, 1) if book_count else 0
        a["avg_likes_per_book"] = round(a["total_likes"] / book_count, 1) if book_count else 0
        authors.append(a)

print(json.dumps(authors, ensure_ascii=False))
