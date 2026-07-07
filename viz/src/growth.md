---
title: Рост во времени
theme: dashboard
toc: false
---

# Рост во времени

```js
const timeline = FileAttachment("data/growth-timeline.json").json();
```

```js
const parsed = timeline.months.map((d) => ({...d, date: new Date(d.month + "-01")}));
const dailyParsed = timeline.days.map((d) => ({...d, date: new Date(d.date)}));
const dailyStats = timeline.daily_stats;
```

## Сколько книг появляется в день

Самый последний день в данных — неполный (скрейпинг остановился в середине дня), поэтому он исключён из статистики ниже.

<div class="grid grid-cols-4">
  <div class="card">
    <h2>В среднем за 30 дней</h2>
    <span class="big">${dailyStats.mean_last_30d.toFixed(0)}</span>
  </div>
  <div class="card">
    <h2>В среднем за 90 дней</h2>
    <span class="big">${dailyStats.mean_last_90d.toFixed(0)}</span>
  </div>
  <div class="card">
    <h2>В среднем за год</h2>
    <span class="big">${dailyStats.mean_last_365d.toFixed(0)}</span>
  </div>
  <div class="card">
    <h2>Медиана за всю историю</h2>
    <span class="big">${dailyStats.median_all_time.toFixed(0)}</span>
  </div>
</div>

Медиана за всю историю (${dailyStats.median_all_time.toFixed(0)} книг/день) намного ниже недавних показателей — платформа выросла примерно втрое с первых лет, поэтому старые дни тянут общую медиану вниз. Сейчас типичный день — это **${dailyStats.mean_last_90d.toFixed(0)}–${dailyStats.mean_last_30d.toFixed(0)} книг**.

```js
function rollingAverage(data, windowSize) {
  return data.map((d, i) => {
    const slice = data.slice(Math.max(0, i - windowSize + 1), i + 1);
    return {...d, avg: d3.mean(slice, (s) => s.count)};
  });
}
```

```js
// Drop the last (partial) day, same as the Python loader, so the trend
// line doesn't dip at the very end.
const dailyFull = dailyParsed.slice(0, -1);
const rolling30 = rollingAverage(dailyFull, 30);
```

```js
function rollingChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {label: null},
    y: {grid: true, label: "Книг в день (скользящее среднее за 30 дней)"},
    marks: [
      Plot.areaY(data, {x: "date", y: "avg", fillOpacity: 0.15, fill: "var(--theme-foreground-focus)"}),
      Plot.lineY(data, {x: "date", y: "avg", stroke: "var(--theme-foreground-focus)", tip: true}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => rollingChart(rolling30, {width}))}
  </div>
</div>

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

## Книги, созданные по дням: ИИ vs не-ИИ

Каждая точка на оси X — оценённый день создания книги. ИИ-сгенерированных книг пока мало, поэтому их линия выглядит гораздо более рваной, чем линия обычных книг.

```js
const dailySeries = dailyParsed.flatMap((d) => [
  {date: d.date, type: "Не-ИИ", count: d.non_ai},
  {date: d.date, type: "ИИ", count: d.ai_generated}
]);
```

```js
function dailyAiChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {label: null},
    y: {grid: true, label: "Книг в день"},
    color: {
      legend: true,
      domain: ["Не-ИИ", "ИИ"],
      range: ["#2a78d6", "rgb(227, 73, 72)"]
    },
    marks: [
      Plot.lineY(data, {x: "date", y: "count", stroke: "type", tip: true}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => dailyAiChart(dailySeries, {width}))}
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
