---
title: Жанры и теги
theme: dashboard
toc: false
---

# Жанры и теги

```js
const stats = FileAttachment("data/genre-tag-stats.json").json();
```

```js
const genres = stats.genres;
const tags = stats.tags;
const cooccurrence = stats.tag_cooccurrence;
```

## Топ жанров

```js
function genreChart(data, {width} = {}) {
  const top = data.slice(0, 50);
  return Plot.plot({
    width,
    height: 900,
    marginLeft: 220,
    x: {grid: true, label: "Книги"},
    y: {label: null},
    marks: [
      Plot.barX(top, {x: "count", y: "genre", sort: {y: "-x"}, tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleX([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => genreChart(genres, {width}))}
  </div>
</div>

## Топ тегов

```js
function tagChart(data, {width} = {}) {
  const top = data.slice(0, 30);
  return Plot.plot({
    width,
    height: 550,
    marginLeft: 220,
    x: {grid: true, label: "Книги"},
    y: {label: null},
    marks: [
      Plot.barX(top, {x: "count", y: "tag", sort: {y: "-x"}, tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleX([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => tagChart(tags, {width}))}
  </div>
</div>

## Какие теги встречаются вместе

Совместная встречаемость 50 самых частых тегов — чем темнее ячейка, тем чаще эта пара тегов встречается в одной книге.

```js
function tagHeatmap(data, {width} = {}) {
  const order = tags.slice(0, 50).map((d) => d.tag);
  // co-occurrence is stored one-directional (a < b); mirror it for a full matrix
  const cells = [];
  for (const {a, b, count} of data) {
    cells.push({x: a, y: b, count});
    cells.push({x: b, y: a, count});
  }
  return Plot.plot({
    width,
    height: width,
    marginLeft: 160,
    marginBottom: 160,
    padding: 0,
    x: {domain: order, label: null, tickRotate: -90},
    y: {domain: order, label: null},
    color: {type: "log", scheme: "blues", legend: true, label: "Общих книг"},
    marks: [
      Plot.cell(cells, {x: "x", y: "y", fill: "count", tip: true})
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => tagHeatmap(cooccurrence, {width: Math.min(width, 1100)}))}
  </div>
</div>

## Карта связей тегов

Те же теги в виде сети связей.

```js
function tagNetwork(tagsData, cooccurrenceData, {width} = {}, {edgesPerNode = 4} = {}) {
  const nodes = tagsData.slice(0, 30).map((d) => ({id: d.tag, count: d.count}));
  const nodeIds = new Set(nodes.map((d) => d.id));
  const pairs = cooccurrenceData.filter((d) => nodeIds.has(d.a) && nodeIds.has(d.b));

  // Keep only each node's strongest few connections (by normalized score),
  // not every pair — otherwise the most-frequent tags all link to each other.
  const bestForNode = new Map(nodes.map((d) => [d.id, []]));
  for (const pair of pairs) {
    bestForNode.get(pair.a).push(pair);
    bestForNode.get(pair.b).push(pair);
  }
  const keep = new Set();
  for (const list of bestForNode.values()) {
    list.sort((x, y) => y.score - x.score);
    for (const pair of list.slice(0, edgesPerNode)) keep.add(pair);
  }
  const links = [...keep].map((d) => ({source: d.a, target: d.b, count: d.count, score: d.score}));

  const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.id).distance(70).strength((d) => d.score))
    .force("charge", d3.forceManyBody().strength(-150))
    .force("center", d3.forceCenter(0, 0))
    .force("collide", d3.forceCollide(16))
    .stop();

  for (let i = 0; i < 300; ++i) simulation.tick();

  return Plot.plot({
    width,
    height: width,
    margin: 10,
    inset: 40,
    x: {axis: null},
    y: {axis: null},
    marks: [
      Plot.link(links, {
        x1: (d) => d.source.x, y1: (d) => d.source.y,
        x2: (d) => d.target.x, y2: (d) => d.target.y,
        strokeWidth: (d) => d.score * 6,
        stroke: "var(--theme-foreground-faint)",
        strokeOpacity: 0.8
      }),
      Plot.dot(nodes, {
        x: "x", y: "y",
        r: (d) => Math.sqrt(d.count) / 4 + 3,
        fill: "var(--theme-foreground-focus)",
        tip: true,
        title: (d) => `${d.id}\n${d.count} книг`
      }),
      Plot.text(nodes, {x: "x", y: "y", text: "id", dy: -10, fontSize: 10})
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => tagNetwork(tags, cooccurrence, {width: Math.min(width, 900)}))}
  </div>
</div>
