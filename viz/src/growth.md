---
title: Рост во времени
theme: dashboard
toc: false
---

# Рост во времени

> **Оговорка:** author.today не показывает дату первой публикации на странице книги — `updated_at` это время последнего редактирования. Поэтому график отражает *активность редактирования*, а не даты первой публикации. Последние месяцы завышены за счёт книг, которые просто недавно отредактировали, а старые книги, которые давно не трогали, наоборот недоучтены.

```js
const rows = FileAttachment("data/growth-timeline.json").json();
```

```js
const parsed = rows.map((d) => ({...d, date: new Date(d.month + "-01")}));
```

## Совокупное число книг по месяцу последнего обновления

```js
function cumulativeChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {label: null},
    y: {grid: true, label: "Книг всего"},
    marks: [
      Plot.areaY(data, {x: "date", y: "cumulative", fillOpacity: 0.2, fill: "var(--theme-foreground-focus)"}),
      Plot.lineY(data, {x: "date", y: "cumulative", stroke: "var(--theme-foreground-focus)"}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => cumulativeChart(parsed, {width}))}
  </div>
</div>

## Книги, обновлённые по месяцам

```js
function monthlyChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {label: null},
    y: {grid: true, label: "Книг"},
    marks: [
      Plot.rectY(data, {x: "date", y: "count", interval: "month", tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => monthlyChart(parsed, {width}))}
  </div>
</div>

## Рост доли ИИ-контента

Доля книг, обновлённых за месяц, помеченных как сгенерированные ИИ.

```js
function aiShareChart(data, {width} = {}) {
  const withShare = data
    .filter((d) => d.count >= 20)
    .map((d) => ({...d, share: d.ai_generated / d.count}));
  return Plot.plot({
    width,
    height: 300,
    x: {label: null},
    y: {grid: true, label: "Доля ИИ-контента (%)", percent: true, tickFormat: (d) => `${d}%`},
    marks: [
      Plot.lineY(withShare, {x: "date", y: "share", stroke: "var(--theme-foreground-focus)", tip: true}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => aiShareChart(parsed, {width}))}
  </div>
</div>
