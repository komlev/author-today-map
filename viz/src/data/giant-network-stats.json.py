"""Data loader: book/genre footprint of the platform's largest co-authorship network.

Reads data/books.jsonl (repo root) twice: once to find which authors belong
to the single largest connected component of the co-authorship graph (same
algorithm as coauthor-network.json.py — duplicated rather than imported,
since data loaders in this project are self-contained), then again to count
the *distinct* books credited to any of those authors and the genres those
books carry. Distinct book count matters because summing each author's own
book_count (as coauthor-network.json does per node) double-counts every book
they wrote together with another network member.
"""
import json
import os
import re
from collections import Counter, deque
from itertools import combinations

BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "books.jsonl")
AUTHORS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "authors_from_books.jsonl")

# Same exclusion as coauthor-network.json.py — platform/contest accounts
# aren't real co-authors and would otherwise merge unrelated authors into
# one giant fake component.
EXCLUDED_AUTHOR_URLS = {
    "https://author.today/u/contest_audio/works",
    "https://author.today/u/future/works",
    "https://author.today/u/evolution/works",
    "https://author.today/u/contest8/works",
}


def canonical(url: str) -> str:
    url = url.replace("http://", "https://", 1) if url.startswith("http://") else url
    return re.sub(r"(/works).*$", r"\1", url)


# --- Pass 1: rebuild the co-authorship graph, find the largest component ---

edge_pairs = set()
collab_nodes = set()

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        urls = set()
        for a in book.get("authors") or []:
            url = a.get("url")
            if not url:
                continue
            url = canonical(url)
            if url in EXCLUDED_AUTHOR_URLS:
                continue
            urls.add(url)
        if len(urls) >= 2:
            collab_nodes |= urls
            for x, y in combinations(sorted(urls), 2):
                edge_pairs.add((x, y))

adjacency: dict[str, set[str]] = {url: set() for url in collab_nodes}
for x, y in edge_pairs:
    adjacency[x].add(y)
    adjacency[y].add(x)

largest_component: set[str] = set()
unvisited = set(collab_nodes)
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
    if len(component) > len(largest_component):
        largest_component = component

# --- Pass 2: distinct books/genres for the network, plus platform-wide
# totals (from the same pass, so both use identical book-record parsing) to
# compare the network's footprint against the whole site.

seen_book_ids: set[str] = set()
genre_counts = Counter()
total_views = 0
platform_book_count = 0
platform_total_views = 0

with open(BOOKS_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        book = json.loads(line)
        platform_book_count += 1
        platform_total_views += book.get("views") or 0
        urls = {canonical(a["url"]) for a in (book.get("authors") or []) if a.get("url")}
        if urls.isdisjoint(largest_component):
            continue
        book_id = book.get("id") or book.get("url")
        if book_id in seen_book_ids:
            continue
        seen_book_ids.add(book_id)
        total_views += book.get("views") or 0
        genre_counts.update(book.get("genres") or [])

with open(AUTHORS_PATH, encoding="utf-8") as f:
    platform_author_count = sum(1 for line in f if line.strip())

# --- "Six degrees of separation": exact shortest-path distance between every
# pair of authors in the giant component. 584 nodes means ~170K pairs, each
# reachable via a plain BFS from every node (O(V+E) per node) — trivial to
# compute exactly rather than sample/estimate.
component_adjacency: dict[str, set[str]] = {url: set() for url in largest_component}
for x, y in edge_pairs:
    if x in largest_component and y in largest_component:
        component_adjacency[x].add(y)
        component_adjacency[y].add(x)

nodes_sorted = sorted(largest_component)
total_distance = 0
pair_count = 0
diameter = 0
diameter_pair = None
distance_counts: Counter[int] = Counter()

for i, source in enumerate(nodes_sorted):
    dist = {source: 0}
    queue = deque([source])
    while queue:
        cur = queue.popleft()
        for neighbor in component_adjacency[cur]:
            if neighbor not in dist:
                dist[neighbor] = dist[cur] + 1
                queue.append(neighbor)
    for target in nodes_sorted[i + 1:]:
        d = dist[target]
        total_distance += d
        pair_count += 1
        distance_counts[d] += 1
        if d > diameter:
            diameter = d
            diameter_pair = (source, target)

result = {
    "author_count": len(largest_component),
    "book_count": len(seen_book_ids),
    "total_views": total_views,
    "genres": [{"genre": g, "count": c} for g, c in genre_counts.most_common()],
    "platform_author_count": platform_author_count,
    "platform_book_count": platform_book_count,
    "platform_total_views": platform_total_views,
    "avg_distance": round(total_distance / pair_count, 2) if pair_count else 0,
    "diameter": diameter,
    "diameter_pair": list(diameter_pair) if diameter_pair else None,
    "distance_distribution": [{"distance": d, "pairs": c} for d, c in sorted(distance_counts.items())],
}

print(json.dumps(result, ensure_ascii=False))
