---
title: Рост во времени
theme: dashboard
toc: false
---

# Рост во времени

> **Как это посчитано:** author.today не показывает дату первой публикации — только `updated_at` (время последнего редактирования). Но ID произведений выдаются по возрастанию, то есть порядок ID совпадает с порядком создания. А значит `updated_at` любой книги не может быть раньше её реальной даты создания — и то же самое верно для всех книг с большим ID. Поэтому для каждой книги дата создания оценивается как минимальный `updated_at` среди неё самой и всех книг с ID не меньше её собственного — эта оценка точна везде, где рядом по ID нашлась книга, которую ни разу не редактировали. На реальных данных у 44% книг оценка и есть их собственный `updated_at` (книга не редактировалась), а для остальных медианная поправка — всего 23 дня. Последние несколько месяцев на графике всё ещё могут сдвинуться немного раньше по мере того, как скрапинг дойдёт до более высоких ID — оценке пока не с чем сравнить книги на самом краю уже собранных данных.

```js
const rows = FileAttachment("data/growth-timeline.json").json();
```

```js
const parsed = rows.map((d) => ({...d, date: new Date(d.month + "-01")}));
```

## Совокупное число книг по оценённому месяцу создания

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

## Книги, созданные по месяцам

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

Доля книг, созданных за месяц, помеченных как сгенерированные ИИ.

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
