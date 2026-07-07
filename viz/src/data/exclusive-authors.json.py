"""Data loader: authors publishing exclusively on author.today.

Reads data/books.jsonl. "Exclusive" here means every single book the author
has published carries the site's own exclusive=true flag — not just some of
their catalog. This is a much stricter (and much rarer) bar than the
per-book exclusive/non-exclusive split already shown on /engagement.
"""
import json
import os
from collections import defaultdict

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

# Platform/contest accounts credited as a book's "author" — not people.
# Same exclusion as scripts/extract_authors.py and sibling loaders.
EXCLUDED_AUTHOR_URLS = {
    "https://author.today/u/contest_audio/works",
    "https://author.today/u/future/works",
    "https://author.today/u/evolution/works",
    "https://author.today/u/contest8/works",
}

per_author = defaultdict(lambda: {"name": None, "book_count": 0, "exclusive_count": 0, "total_views": 0, "total_likes": 0})

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        exclusive = bool(book.get("exclusive"))
        views = book.get("views") or 0
        likes = book.get("likes") or 0

        for author in book.get("authors") or []:
            url = author.get("url")
            if not url or url in EXCLUDED_AUTHOR_URLS:
                continue
            entry = per_author[url]
            entry["name"] = author.get("name")
            entry["book_count"] += 1
            entry["exclusive_count"] += 1 if exclusive else 0
            entry["total_views"] += views
            entry["total_likes"] += likes

exclusive_authors = [
    {
        "name": entry["name"],
        "book_count": entry["book_count"],
        "total_views": entry["total_views"],
        "total_likes": entry["total_likes"],
    }
    for entry in per_author.values()
    # every book by this author is exclusive to the site
    if entry["book_count"] > 0 and entry["exclusive_count"] == entry["book_count"]
]

exclusive_authors.sort(key=lambda d: -d["total_likes"])

print(json.dumps(exclusive_authors, ensure_ascii=False))
