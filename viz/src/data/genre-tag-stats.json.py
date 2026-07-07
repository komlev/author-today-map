"""Data loader: genre and tag frequency + tag co-occurrence.

Reads data/books.jsonl (repo root) and emits pre-aggregated JSON so the
browser never has to touch the raw 90MB+ file.
"""
import json
import math
import os
from collections import Counter
from itertools import combinations

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

TOP_TAGS_FOR_COOCCURRENCE = 50

# Generic format tags that just restate work_type rather than describe
# content — not useful in a genre/tag landscape.
EXCLUDED_TAGS = {"рассказ", "короткий рассказ"}

genre_counts = Counter()
tag_counts = Counter()
cooccurrence = Counter()

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        genre_counts.update(book.get("genres") or [])
        tags = [t for t in (book.get("tags") or []) if t.strip().lower() not in EXCLUDED_TAGS]
        tag_counts.update(tags)
        for a, b in combinations(sorted(set(tags)), 2):
            cooccurrence[(a, b)] += 1

top_tags = {tag for tag, _ in tag_counts.most_common(TOP_TAGS_FOR_COOCCURRENCE)}

# Raw co-occurrence count is dominated by tag frequency alone (two very common
# tags will co-occur a lot just by chance). Normalize with a cosine-like score
# (count / sqrt(freq_a * freq_b)) so the network highlights tags that pair up
# *more than expected* given how common each one is, not just popular tags.
tag_cooccurrence = []
for (a, b), c in cooccurrence.items():
    if a in top_tags and b in top_tags:
        score = c / math.sqrt(tag_counts[a] * tag_counts[b])
        tag_cooccurrence.append({"a": a, "b": b, "count": c, "score": round(score, 4)})

result = {
    "genres": [{"genre": g, "count": c} for g, c in genre_counts.most_common()],
    "tags": [{"tag": t, "count": c} for t, c in tag_counts.most_common(200)],
    "tag_cooccurrence": tag_cooccurrence,
}

print(json.dumps(result, ensure_ascii=False))
