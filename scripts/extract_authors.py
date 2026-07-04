"""Extract unique authors from books.jsonl into authors.jsonl.

Aggregates per-author stats (book count, views, likes) from the books
already scraped. This is a stopgap until Phase 2 (full author profile
scraping) finishes.
"""
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
INPUT = os.path.join(DATA_DIR, "books.jsonl")
OUTPUT = os.path.join(DATA_DIR, "authors_from_books.jsonl")


def main():
    authors = {}

    with open(INPUT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            book = json.loads(line)
            for author in book.get("authors") or []:
                url = author.get("url")
                name = author.get("name")
                if not url:
                    continue
                entry = authors.get(url)
                if entry is None:
                    entry = {
                        "name": name,
                        "url": url,
                        "book_count": 0,
                        "total_views": 0,
                        "total_likes": 0,
                        "genres": set(),
                    }
                    authors[url] = entry
                entry["book_count"] += 1
                entry["total_views"] += book.get("views") or 0
                entry["total_likes"] += book.get("likes") or 0
                entry["genres"].update(book.get("genres") or [])

    with open(OUTPUT, "w", encoding="utf-8") as out:
        for entry in authors.values():
            entry["genres"] = sorted(entry["genres"])
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Extracted {len(authors)} unique authors -> {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
