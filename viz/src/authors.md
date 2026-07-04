---
title: Продуктивность авторов
theme: dashboard
toc: false
---

# Продуктивность авторов

```js
const authors = FileAttachment("data/author-productivity.json").json();
const graphomaniacs = FileAttachment("data/graphomaniac-stats.json").json();
const coauthorNetwork = FileAttachment("data/coauthor-network.json").json();
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Авторов</h2>
    <span class="big">${authors.length.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Медиана книг на автора</h2>
    <span class="big">${d3.median(authors, (d) => d.book_count)}</span>
  </div>
  <div class="card">
    <h2>Больше всего книг у одного автора</h2>
    <span class="big">${d3.max(authors, (d) => d.book_count).toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Авторов с 1 книгой</h2>
    <span class="big">${authors.filter((d) => d.book_count === 1).length.toLocaleString("ru-RU")}</span>
  </div>
</div>

## Сколько книг пишут авторы?

```js
function bookCountHistogram(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {label: "Опубликовано книг", domain: [1, 50], clamp: true},
    y: {grid: true, label: "Авторов"},
    marks: [
      Plot.rectY(data, Plot.binX({y: "count"}, {x: "book_count", thresholds: 50, tip: true, fill: "var(--theme-foreground-focus)"})),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => bookCountHistogram(authors, {width}))}
  </div>
</div>

## Объём публикаций и популярность

Каждая точка — это автор: сколько книг он опубликовал против среднего числа просмотров на книгу. Обе оси логарифмические, так как и объём, и популярность распределены очень неравномерно.

```js
function productivityScatter(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 500,
    x: {type: "log", label: "Опубликовано книг", grid: true},
    y: {type: "log", label: "Ср. просмотров на книгу", grid: true},
    marks: [
      Plot.dot(data, {
        x: "book_count",
        y: "avg_views_per_book",
        r: 2,
        fill: "var(--theme-foreground-focus)",
        fillOpacity: 0.4,
        tip: true,
        title: (d) => `${d.name}\n${d.book_count} книг, ${d.avg_views_per_book} просмотров в среднем`
      })
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => productivityScatter(authors.filter((d) => d.avg_views_per_book > 0), {width}))}
  </div>
</div>

## Самые продуктивные авторы

```js
Inputs.table(
  authors
    .toSorted((a, b) => b.book_count - a.book_count)
    .slice(0, 25)
    .map((d) => ({
      "Автор": d.name,
      "Книг": d.book_count,
      "Всего просмотров": d.total_views,
      "Ср. просмотров/книгу": d.avg_views_per_book
    }))
)
```

## Самые популярные авторы

```js
Inputs.table(
  authors
    .toSorted((a, b) => b.total_views - a.total_views)
    .slice(0, 25)
    .map((d) => ({
      "Автор": d.name,
      "Книг": d.book_count,
      "Всего просмотров": d.total_views,
      "Ср. просмотров/книгу": d.avg_views_per_book
    }))
)
```

## Графоманы: у кого самые длинные книги

Средний объём одной книги (в символах) у авторов минимум с ${graphomaniacs.min_books_for_leaderboard} книгами — то есть не разовый длинный роман, а систематическая привычка писать очень много. Для справки: средний роман (Роман) на платформе — около 388 000 символов.

Метка ai_generated — свойство книги, а не автора, поэтому здесь автор считается отдельно по его ИИ- и не-ИИ-книгам.

```js
Inputs.table(
  graphomaniacs.overall.map((d) => ({
    "Тип": d.ai_generated ? "ИИ-сгенерированные" : "Написанные людьми",
    "Книг": d.count,
    "Ср. объём (символов)": d.avg_chars
  }))
)
```

### Не-ИИ авторы

```js
Inputs.table(
  graphomaniacs.top_non_ai.map((d) => ({
    "Автор": d.name,
    "Книг": d.book_count,
    "Ср. объём (символов)": d.avg_chars,
    "Всего символов": d.total_chars
  }))
)
```

### ИИ-авторы

${graphomaniacs.top_ai.length === 0
  ? html`<p><em>Пока нет ни одного автора с ${graphomaniacs.min_books_for_leaderboard}+ книгами, помеченными как ИИ-сгенерированные — на момент последнего скрапинга таких книг всего ${graphomaniacs.overall.find((d) => d.ai_generated)?.count ?? 0} на всю платформу. Таблица заполнится по мере продолжения скрапинга.</em></p>`
  : Inputs.table(
      graphomaniacs.top_ai.map((d) => ({
        "Автор": d.name,
        "Книг": d.book_count,
        "Ср. объём (символов)": d.avg_chars,
        "Всего символов": d.total_chars
      }))
    )
}

## Соавторство

У подавляющего большинства книг один автор — совместных книг в текущем срезе данных всего ${coauthorNetwork.edges.length ? d3.sum(coauthorNetwork.edges, (d) => d.count).toLocaleString("ru-RU") : 0} из ${authors.length ? d3.sum(authors, (d) => d.book_count).toLocaleString("ru-RU") : 0}. Большинство соавторств — это устойчивая пара из двух человек: они не образуют сеть, а просто пишут вдвоём (полный список — в таблице дуэтов ниже). Сеть ниже показывает только группы от 4 соавторов — те случаи, где соавторство образует настоящую структуру, а не изолированную пару. Размер узла — сколько книг у автора всего, толщина связи — сколько книг написано этой парой вместе.

```js
function coauthorGraph({nodes, edges}, {width} = {}, {minGroupSize = 4} = {}) {
  const keptNodes = nodes.filter((d) => d.component_size >= minGroupSize);
  const keptIds = new Set(keptNodes.map((d) => d.id));
  const keptEdges = edges.filter((d) => keptIds.has(d.source) && keptIds.has(d.target));

  // d3.forceLink mutates its input array's source/target from ids into node
  // object refs in place. Since resize() re-invokes this function on every
  // viewport resize, feeding it the shared coauthorNetwork.edges/nodes arrays
  // directly would corrupt them after the first render — clone both instead.
  const simNodes = keptNodes.map((d) => ({...d}));
  const simEdges = keptEdges.map((d) => ({...d}));
  const degree = new Map(simNodes.map((d) => [d.id, 0]));
  for (const e of simEdges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }

  const simulation = d3.forceSimulation(simNodes)
    .force("link", d3.forceLink(simEdges).id((d) => d.id).distance(30).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-90))
    .force("center", d3.forceCenter(0, 0))
    .force("collide", d3.forceCollide(14))
    .stop();

  for (let i = 0; i < 400; ++i) simulation.tick();

  const labelNodes = simNodes.filter((d) => (degree.get(d.id) ?? 0) >= 2);

  return Plot.plot({
    width,
    height: Math.min(width, 900),
    margin: 10,
    inset: 30,
    x: {axis: null},
    y: {axis: null},
    marks: [
      Plot.link(simEdges, {
        x1: (d) => d.source.x, y1: (d) => d.source.y,
        x2: (d) => d.target.x, y2: (d) => d.target.y,
        strokeWidth: (d) => Math.sqrt(d.count),
        stroke: "var(--theme-foreground-faint)",
        strokeOpacity: 0.8
      }),
      Plot.dot(simNodes, {
        x: "x", y: "y",
        r: (d) => Math.sqrt(d.book_count ?? 1) + 2,
        fill: "var(--theme-foreground-focus)",
        tip: true,
        title: (d) => `${d.name}\n${d.book_count} книг, ${degree.get(d.id) ?? 0} соавторов`
      }),
      Plot.text(labelNodes, {x: "x", y: "y", text: "name", dy: -8, fontSize: 9})
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => coauthorGraph(coauthorNetwork, {width}))}
  </div>
</div>

### Самые устойчивые творческие дуэты

```js
Inputs.table(
  coauthorNetwork.edges
    .toSorted((a, b) => b.count - a.count)
    .slice(0, 20)
    .map((d) => {
      const a = coauthorNetwork.nodes.find((n) => n.id === d.source);
      const b = coauthorNetwork.nodes.find((n) => n.id === d.target);
      return {
        "Автор 1": a?.name,
        "Автор 2": b?.name,
        "Совместных книг": d.count,
        "Суммарно просмотров": d.views
      };
    })
)
```
