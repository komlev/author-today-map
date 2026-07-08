"""Data loader: co-authorship network.

Reads data/books.jsonl (repo root) and emits pairwise co-authorship counts
for books with 2+ credited authors. Most books on the platform have a
single author, so this is a sparse but real graph, not the full corpus.
"""
import json
import os
import re
from collections import Counter
from itertools import combinations

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")

# Platform/contest accounts credited as a book's "author" — not people. Left
# in, these would show up as a single hub "co-authoring" with hundreds of
# unrelated real authors (e.g. contest_audio is credited on 679 books across
# every genre on the platform). Same exclusion in
# scripts/extract_authors.py and graphomaniac-stats.json.py.
EXCLUDED_AUTHOR_URLS = {
    "https://author.today/u/contest_audio/works",
    "https://author.today/u/future/works",
    "https://author.today/u/evolution/works",
    "https://author.today/u/contest8/works",
}


def canonical(url: str) -> str:
    # A handful of scraped author URLs use http:// instead of https://, or
    # carry trailing punctuation bled in from surrounding annotation text
    # (e.g. ".../works." or ".../works),") — same author, different dict
    # key. Normalize both so they don't split into separate graph nodes.
    url = url.replace("http://", "https://", 1) if url.startswith("http://") else url
    return re.sub(r"(/works).*$", r"\1", url)


edge_counts = Counter()
edge_views = Counter()
name_counts = {}
book_counts = Counter()
view_totals = Counter()
ai_authors = set()

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        authors = book.get("authors") or []
        urls = []
        for a in authors:
            url = a.get("url")
            name = a.get("name")
            if not url:
                continue
            url = canonical(url)
            if url in EXCLUDED_AUTHOR_URLS:
                continue
            # On some collaboration widgets the co-author link's visible text
            # is the raw href rather than a display name — track all names
            # seen per author and pick the most common one later, so one
            # mislabeled appearance doesn't corrupt the node's display name.
            name_counts.setdefault(url, Counter())[name] += 1
            book_counts[url] += 1
            view_totals[url] += book.get("views") or 0
            if book.get("ai_generated"):
                ai_authors.add(url)
            urls.append(url)

        urls = sorted(set(urls))
        if len(urls) >= 2:
            views = book.get("views") or 0
            for x, y in combinations(urls, 2):
                edge_counts[(x, y)] += 1
                edge_views[(x, y)] += views

collab_nodes = set()
for x, y in edge_counts:
    collab_nodes.add(x)
    collab_nodes.add(y)


def best_name(counter: Counter) -> str | None:
    non_url = [(n, c) for n, c in counter.items() if n and not n.startswith("http")]
    pool = non_url or list(counter.items())
    return max(pool, key=lambda nc: nc[1])[0] if pool else None


# Co-authorship splits into many small connected components rather than one
# big graph: most collaborations are a single recurring duo. A force layout
# over all of them just packs ~600 indistinguishable pairs into a disk —
# component_size lets the page render only the handful of larger, actually
# structured groups as a network, while pairs stay in the leaderboard table.
adjacency: dict[str, set[str]] = {url: set() for url in collab_nodes}
for x, y in edge_counts:
    adjacency[x].add(y)
    adjacency[y].add(x)

component_size: dict[str, int] = {}
component_id: dict[str, int] = {}
unvisited = set(collab_nodes)
next_component_id = 0
while unvisited:
    start = next(iter(unvisited))
    stack = [start]
    component = set()
    while stack:
        node = stack.pop()
        if node in component:
            continue
        component.add(node)
        stack.extend(adjacency[node] - component)
    unvisited -= component
    for node in component:
        component_size[node] = len(component)
        component_id[node] = next_component_id
    next_component_id += 1

nodes = [
    {
        "id": url,
        "name": best_name(name_counts.get(url, Counter())),
        "book_count": book_counts.get(url, 0),
        "component_id": component_id[url],
        "component_size": component_size[url],
        "degree": len(adjacency[url]),  # distinct co-authors, regardless of component size
        "avg_views_per_book": round(view_totals[url] / book_counts[url], 1) if book_counts[url] else 0,
        "ai_generated": url in ai_authors,
    }
    for url in collab_nodes
]

edges = [
    {"source": x, "target": y, "count": c, "views": edge_views[(x, y)]}
    for (x, y), c in edge_counts.items()
]

result = {"nodes": nodes, "edges": edges}

print(json.dumps(result, ensure_ascii=False))
