---
title: Качество вовлечённости
theme: dashboard
toc: false
---

# Качество вовлечённости

```js
const stats = FileAttachment("data/engagement-stats.json").json();
```

```js
const points = stats.chars_views_points;
const topByRatio = stats.top_by_ratio;
const exclusiveSummary = stats.exclusive_summary;
```

```js
// Plot's automatic bin thresholds are computed linearly even when the
// associated scale is log — on this heavily right-skewed data that silently
// drops most short books into a single near-zero bin that log scales can't
// render. Compute log-spaced thresholds explicitly instead.
function logThresholds(values, step = 0.15) {
  const [lo, hi] = d3.extent(values);
  const start = Math.floor(Math.log10(lo) / step) * step;
  const end = Math.ceil(Math.log10(hi) / step) * step;
  return d3.range(start, end + step, step).map((e) => 10 ** e);
}
```

## Сколько символов в книгах

```js
const medianChars = d3.median(points, (d) => d.chars);
```

Распределение объёма текста (ось логарифмическая, так как объём сильно скошен: от коротких рассказов до многотомных романов). Медиана — **${medianChars.toLocaleString("ru-RU")} символов** (пунктирная линия на графике).

```js
function charsHistogram(data, {width} = {}, {median} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {type: "log", label: "Объём (символов)", grid: true},
    y: {grid: true, label: "Книг"},
    marks: [
      Plot.rectY(data, Plot.binX({y: "count"}, {x: "chars", thresholds: logThresholds(data.map((d) => d.chars)), tip: true, fill: "var(--theme-foreground-focus)"})),
      Plot.ruleX([median], {stroke: "var(--theme-foreground-alt)", strokeDasharray: "4,4"}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => charsHistogram(points, {width}, {median: medianChars}))}
  </div>
</div>

## Объём книги и число просмотров

Плотность книг по объёму текста и числу просмотров (обе оси логарифмические). Более тёмные клетки — больше книг с такими параметрами. Оранжевая рамка отмечает ячейки, где есть эксклюзивные (доступные только на author.today) книги.

```js
function charsViewsHeatmap(data, {width} = {}) {
  const charsThresholds = logThresholds(data.map((d) => d.chars));
  const viewsThresholds = logThresholds(data.map((d) => d.views));
  const exclusivePoints = data.filter((d) => d.exclusive);
  return Plot.plot({
    width,
    height: 500,
    x: {type: "log", label: "Объём (символов)", grid: true},
    y: {type: "log", label: "Просмотров", grid: true},
    color: {type: "log", scheme: "blues", legend: true, label: "Книг"},
    marks: [
      Plot.rect(data, Plot.bin({fill: "count"}, {
        x: {value: "chars", thresholds: charsThresholds},
        y: {value: "views", thresholds: viewsThresholds}
      })),
      Plot.rect(exclusivePoints, Plot.bin({}, {
        x: {value: "chars", thresholds: charsThresholds},
        y: {value: "views", thresholds: viewsThresholds},
        fill: "none",
        stroke: "orange",
        strokeWidth: 1.5
      }))
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => charsViewsHeatmap(points, {width}))}
  </div>
</div>

## Эксклюзивный контент

Книги, доступные только на author.today (эксклюзив), в среднем набирают заметно больше просмотров и лайков — вероятнее всего, потому что платформа сама продвигает эксклюзивный контент, а не потому что эксклюзивность сама по себе делает книгу популярнее.

```js
Inputs.table(
  exclusiveSummary.map((d) => ({
    "Эксклюзив": d.exclusive ? "Да" : "Нет",
    "Книг": d.count,
    "Ср. просмотров": d.avg_views,
    "Ср. лайков": d.avg_likes
  }))
)
```

## Самые "любимые" книги

Топ книг по отношению лайков к просмотрам (среди книг с 1000+ просмотров) — то есть книги, которые меньше просмотров конвертировали в непропорционально много лайков.

```js
Inputs.table(
  topByRatio.map((d) => ({
    "Книга": d.title,
    "Автор": d.author,
    "Просмотров": d.views,
    "Лайков": d.likes,
    "Лайки/просмотры": (d.ratio * 100).toFixed(1) + "%"
  }))
)
```
