"""Data loader: "накрутка" (metric inflation) outliers — book level.

Reads data/books.jsonl. Ships raw views/likes points for a client-side
density heatmap (same "let Plot bin them" approach as
engagement-stats.json.py's chars/views heatmap), plus a server-computed
median-likes-by-view-range trend line and leaderboards of the most extreme
outliers in each direction. Classifying all ~280k books here rather than
shipping them to the browser to bin/classify client-side (as the much
smaller ~55k-row author-level version does) keeps the page payload to the
points needed for the heatmap plus a couple hundred leaderboard rows.
"""
import json
import math
import os
from bisect import bisect_right
from statistics import median

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

STEP = 0.2
MIN_BIN_SIZE = 5  # bins smaller than this give a noisy median, skip them
OUTLIER_RATIO = 3  # 3x above/below the bin's median likes counts as an outlier
TOP_N = 25

books = []
with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        views = book.get("views") or 0
        likes = book.get("likes") or 0
        if views > 0 and likes > 0:
            authors = book.get("authors") or []
            books.append({
                "title": book.get("title"),
                "author": authors[0]["name"] if authors else None,
                "author_url": authors[0]["url"] if authors else None,
                "url": book.get("url"),
                "views": views,
                "likes": likes,
                "ai_generated": bool(book.get("ai_generated")),
                "exclusive": bool(book.get("exclusive")),
            })

view_values = [b["views"] for b in books]
lo, hi = min(view_values), max(view_values)
start = math.floor(math.log10(lo) / STEP) * STEP
end = math.ceil(math.log10(hi) / STEP) * STEP
thresholds = []
e = start
while e <= end + STEP:
    thresholds.append(10 ** e)
    e += STEP

bins = {}
for b in books:
    idx = bisect_right(thresholds, b["views"]) - 1
    bins.setdefault(idx, []).append(b)

median_line = []
outliers = []
for idx, members in sorted(bins.items()):
    if len(members) < MIN_BIN_SIZE:
        continue
    bin_views = median(m["views"] for m in members)
    bin_likes = median(m["likes"] for m in members)
    median_line.append({"views": bin_views, "likes": bin_likes})
    if bin_likes == 0:
        continue
    for m in members:
        ratio = m["likes"] / bin_likes
        if ratio >= OUTLIER_RATIO:
            outliers.append({**m, "expected_likes": round(bin_likes), "ratio": ratio, "deviation": "накрутка лайков"})
        elif ratio <= 1 / OUTLIER_RATIO:
            outliers.append({**m, "expected_likes": round(bin_likes), "ratio": ratio, "deviation": "накрутка просмотров"})

top_view_inflation = sorted(
    (o for o in outliers if o["deviation"] == "накрутка просмотров"), key=lambda o: o["ratio"]
)[:TOP_N]
top_like_inflation = sorted(
    (o for o in outliers if o["deviation"] == "накрутка лайков"), key=lambda o: -o["ratio"]
)[:TOP_N]

result = {
    "points": [{"views": b["views"], "likes": b["likes"]} for b in books],
    "median_line": median_line,
    "top_view_inflation": top_view_inflation,
    "top_like_inflation": top_like_inflation,
    # Small enough sets (low thousands) to overlay as individual dots on top
    # of the density heatmap, unlike the full ~280k-book corpus above.
    "ai_points": [
        {"views": b["views"], "likes": b["likes"], "title": b["title"], "author": b["author"]}
        for b in books if b["ai_generated"]
    ],
    "exclusive_points": [
        {"views": b["views"], "likes": b["likes"], "title": b["title"], "author": b["author"]}
        for b in books if b["exclusive"]
    ],
}

print(json.dumps(result, ensure_ascii=False))
