"""Data loader: platform activity over time.

author.today doesn't expose a book's original publish date — only
`updated_at` (last edit time), which alone would skew any timeline toward
recently-edited books regardless of when they were actually published.

Work IDs are auto-incremental, so id order tracks creation order. That
gives one hard guarantee: updated_at(id) >= true creation date(id), for
every book. Combined with id-monotonic creation order, the earliest
updated_at among all books with that id or any higher id is a valid upper
bound on this book's creation date — and it's tight wherever a nearby-id
book was never edited. So for each book we estimate:

    estimated_created_at(id) = min(updated_at[id'] for id' >= id)

computed as a running minimum over books sorted by id, from the highest
id down. Checked against the actual corpus: id <-> updated_at correlation
is 0.92, 44% of books already sit exactly at this bound (never edited),
and the correction for the rest has a median of 23 days (long tail up to
~9 years for old, heavily-edited books). updated_at strings are fixed-
width ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SS.fffffffZ`), so plain string
comparison already sorts chronologically — no datetime parsing needed.
"""
import json
import os
from collections import defaultdict

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

books = []
with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        updated_at = book.get("updated_at")
        if not updated_at:
            continue
        books.append({
            "id": int(book["id"]),
            "updated_at": updated_at,
            "ai_generated": book.get("ai_generated"),
            "exclusive": book.get("exclusive"),
            "chars": book.get("chars") or 0,
        })

books.sort(key=lambda b: b["id"])

running_min = None
for book in reversed(books):
    if running_min is None or book["updated_at"] < running_min:
        running_min = book["updated_at"]
    book["estimated_created_at"] = running_min

months = defaultdict(lambda: {"count": 0, "ai_generated": 0, "exclusive": 0, "chars": 0})

for book in books:
    month_key = book["estimated_created_at"][:7]  # "YYYY-MM"
    bucket = months[month_key]
    bucket["count"] += 1
    bucket["ai_generated"] += 1 if book["ai_generated"] else 0
    bucket["exclusive"] += 1 if book["exclusive"] else 0
    bucket["chars"] += book["chars"]

rows = [{"month": m, **v} for m, v in sorted(months.items())]

cumulative = 0
for row in rows:
    cumulative += row["count"]
    row["cumulative"] = cumulative

print(json.dumps(rows, ensure_ascii=False))
