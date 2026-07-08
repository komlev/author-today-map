---
title: 6 рукопожатий
theme: dashboard
toc: false
---

# 6 рукопожатий

```js
import {coauthorGraph} from "./components/coauthor-graph.js";

const coauthorNetwork = FileAttachment("data/coauthor-network.json").json();
const networkStats = FileAttachment("data/giant-network-stats.json").json();
```

```js
// Соавторство only renders components of 4+ people, and even then shows
// every qualifying component side by side. Here we pick out just the single
// largest connected component — the one real "network" on the platform,
// as opposed to the ~1800 isolated pairs and small groups that never link
// up with it or each other.
const components = Array.from(
  d3.group(coauthorNetwork.nodes, (d) => d.component_id),
  ([id, members]) => ({id, size: members[0].component_size})
).toSorted((a, b) => b.size - a.size);

const giant = components[0];
const giantNodes = coauthorNetwork.nodes.filter((d) => d.component_id === giant.id);
const giantIds = new Set(giantNodes.map((d) => d.id));
const giantEdges = coauthorNetwork.edges.filter((d) => giantIds.has(d.source) && giantIds.has(d.target));
const nameOf = new Map(giantNodes.map((d) => [d.id, d.name]));

function pluralHandshakes(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "рукопожатие";
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return "рукопожатия";
  return "рукопожатий";
}

const authorShare = (100 * giant.size) / networkStats.platform_author_count;
const bookShare = (100 * networkStats.book_count) / networkStats.platform_book_count;
const networkAvgViews = networkStats.total_views / networkStats.book_count;
const platformAvgViews = networkStats.platform_total_views / networkStats.platform_book_count;
const viewsMultiplier = networkAvgViews / platformAvgViews;
```

Самая большая сеть соавторства на платформе — ${giant.size} авторов, связанных цепочкой совместных книг (все остальные ${(components.length - 1).toLocaleString("ru-RU")} сетей — разрозненные пары и небольшие группы, не связанные ни с этой сетью, ни друг с другом). Это всего ${authorShare.toFixed(1)}% авторов платформы, но они написали ${bookShare.toFixed(1)}% всех книг на сайте — и эти книги набирают в среднем в ${viewsMultiplier.toFixed(1)} раза больше просмотров, чем типичная книга на платформе.

<div class="grid grid-cols-3">
  <div class="card">
    <h2>Авторов в сети</h2>
    <span class="big">${giant.size.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Книг написано</h2>
    <span class="big">${networkStats.book_count.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Суммарно просмотров</h2>
    <span class="big">${networkStats.total_views.toLocaleString("ru-RU")}</span>
  </div>
</div>

<div class="grid grid-cols-3">
  <div class="card">
    <h2>Доля авторов платформы</h2>
    <span class="big">${authorShare.toFixed(1)}%</span>
  </div>
  <div class="card">
    <h2>Доля всех книг платформы</h2>
    <span class="big">${bookShare.toFixed(1)}%</span>
  </div>
  <div class="card">
    <h2>Просмотров/книгу vs платформа</h2>
    <span class="big">${viewsMultiplier.toFixed(1)}×</span>
  </div>
</div>

## Жанры этой сети

```js
function genreChart(data, {width} = {}) {
  const top = data.toSorted((a, b) => b.count - a.count).slice(0, 15);
  return Plot.plot({
    width,
    height: 380,
    marginLeft: 200,
    x: {grid: true, label: "Книг"},
    y: {label: null, domain: top.map((d) => d.genre)},
    marks: [
      Plot.barX(top, {x: "count", y: "genre", sort: {y: "-x"}, tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleX([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => genreChart(networkStats.genres, {width}))}
  </div>
</div>

## Сколько на самом деле рукопожатий

Название страницы — это отсылка к теории «шести рукопожатий», но для настоящей сети соавторства на этой платформе цифра другая: между двумя случайными авторами в среднем ${networkStats.avg_distance.toFixed(1)} рукопожатий, а рекорд — целых **${networkStats.diameter}**, между ${nameOf.get(networkStats.diameter_pair[0]) ?? "неизвестным автором"} и ${nameOf.get(networkStats.diameter_pair[1]) ?? "неизвестным автором"}. Ниже — распределение: сколько пар авторов разделяет каждое конкретное число рукопожатий.

```js
function distanceHistogram(data, {width} = {}, {average} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {grid: true, label: "Рукопожатий между парой авторов"},
    y: {grid: true, label: "Пар авторов"},
    marks: [
      Plot.rectY(data, {
        x1: (d) => d.distance - 0.4, x2: (d) => d.distance + 0.4,
        y: "pairs", tip: true, fill: "var(--theme-foreground-focus)"
      }),
      Plot.ruleX([average], {stroke: "var(--theme-foreground-alt)", strokeDasharray: "4,4"}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => distanceHistogram(networkStats.distance_distribution, {width}, {average: networkStats.avg_distance}))}
  </div>
</div>

## Путь между двумя авторами

Начните вводить имя — появятся подсказки; как только оба поля заполнены существующим автором, ниже построится кратчайший путь соавторства между ними (не обязательно по дереву на графике, а по реальным связям) и подсветится на диаграмме.

```js
const authorOptions = new Map(giantNodes.map((d) => [d.name, d.id]));
const authorNames = giantNodes.toSorted((a, b) => a.name.localeCompare(b.name, "ru")).map((d) => d.name);

// Built as plain elements (not view()'d immediately) so the "Очистить"
// button below can reach into their actual <input> and blank it — view()
// only hands back a reactive *value*, not a way to reset the control that
// produced it.
const author1Input = Inputs.text({label: "Автор 1", datalist: authorNames, placeholder: "Начните вводить имя автора…", submit: false});
const author2Input = Inputs.text({label: "Автор 2", datalist: authorNames, placeholder: "Начните вводить имя автора…", submit: false});

function clearAuthors() {
  for (const el of [author1Input, author2Input]) {
    const input = el.querySelector("input");
    input.value = "";
    input.dispatchEvent(new Event("input", {bubbles: true}));
  }
}
```

```js
const author1Name = view(author1Input);
```

```js
const author2Name = view(author2Input);
```

```js
view(Inputs.button("Очистить выбор", {reduce: clearAuthors}));
```

```js
// datalist only *suggests* names — nothing stops someone from typing a
// partial or misspelled one (or leaving the field untouched), so an
// exact-match lookup here can legitimately come back empty and needs its
// own message rather than silently computing a path from `undefined`.
const author1 = authorOptions.get(author1Name);
const author2 = authorOptions.get(author2Name);
```

```js
function shortestPath(nodes, edges, sourceId, targetId) {
  if (sourceId === targetId) return [sourceId];
  const adjacency = new Map(nodes.map((d) => [d.id, []]));
  for (const e of edges) {
    adjacency.get(e.source).push(e.target);
    adjacency.get(e.target).push(e.source);
  }
  const parentOf = new Map([[sourceId, null]]);
  const queue = [sourceId];
  while (queue.length) {
    const id = queue.shift();
    if (id === targetId) break;
    for (const neighbor of adjacency.get(id)) {
      if (!parentOf.has(neighbor)) {
        parentOf.set(neighbor, id);
        queue.push(neighbor);
      }
    }
  }
  if (!parentOf.has(targetId)) return null;
  const path = [];
  for (let cur = targetId; cur != null; cur = parentOf.get(cur)) path.push(cur);
  return path.reverse();
}

const path = author1 && author2 ? shortestPath(giantNodes, giantEdges, author1, author2) : null;
```

${!author1Name.trim() && !author2Name.trim()
  ? "Выберите двух авторов, чтобы увидеть путь между ними."
  : !author1Name.trim() || !author2Name.trim()
    ? "Выберите второго автора."
    : author1 === undefined || author2 === undefined
      ? "Введите точное имя автора из подсказок — оба поля должны совпасть с автором сети."
      : path
        ? `**${path.length - 1} ${pluralHandshakes(path.length - 1)}**: ${path.map((id) => nameOf.get(id)).join(" → ")}`
        : "Между этими авторами нет пути (не должно происходить внутри одной сети)."}

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => coauthorGraph(coauthorNetwork, {width, height: 900}, {componentId: giant.id, layout: "tangled", highlightPath: path}))}
  </div>
</div>
