---
title: Статус и тип текста
theme: dashboard
toc: false
---

# Статус и тип текста

```js
const stats = FileAttachment("data/structure-stats.json").json();
```

```js
const statusCounts = stats.status_counts;
const workTypeCounts = stats.work_type_counts;
const statusByGenre = stats.status_by_genre;
const workTypeStats = stats.work_type_stats;
```

## Завершённость текстов

```js
function statusChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 150,
    x: {grid: true, label: "Книги"},
    y: {label: null},
    marks: [
      Plot.barX(data, {x: "count", y: "status", sort: {y: "-x"}, tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleX([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => statusChart(statusCounts, {width}))}
  </div>
</div>

## Завершённость по жанрам

Доля законченных и незаконченных книг среди 15 самых частых жанров.

```js
// Fixed canonical order (not sorted by frequency) so the status legend and
// stacking order stay stable across genres instead of shuffling based on
// each genre's count breakdown.
const STATUS_ORDER = ["весь текст", "в процессе", "аудиокнига завершена", "не указан"];

function statusByGenreChart(data, {width} = {}) {
  const genreOrder = d3.groupSort(data, (v) => -d3.sum(v, (d) => d.count), (d) => d.genre);
  return Plot.plot({
    width,
    height: 450,
    marginLeft: 220,
    x: {grid: true, label: "Доля книг", percent: true, tickFormat: (d) => `${d}%`},
    y: {label: null, domain: genreOrder},
    color: {legend: true, label: "Статус", domain: STATUS_ORDER},
    marks: [
      Plot.barX(data, Plot.stackX({x: "count", y: "genre", fill: "status", offset: "normalize", order: STATUS_ORDER, tip: true})),
      Plot.ruleX([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => statusByGenreChart(statusByGenre, {width}))}
  </div>
</div>

## Типы произведений

```js
function workTypeChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 250,
    x: {grid: true, label: "Книги"},
    y: {label: null},
    marks: [
      Plot.barX(data, {x: "count", y: "work_type", sort: {y: "-x"}, tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleX([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => workTypeChart(workTypeCounts, {width}))}
  </div>
</div>

## Средний объём и просмотры по типу

```js
Inputs.table(
  workTypeStats
    .toSorted((a, b) => b.count - a.count)
    .map((d) => ({
      "Тип": d.work_type,
      "Книг": d.count,
      "Ср. объём (символов)": d.avg_chars,
      "Ср. просмотров": d.avg_views
    }))
, {select: false})
```
