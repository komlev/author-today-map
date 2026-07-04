---
title: Серии и одиночные книги
theme: dashboard
toc: false
---

# Серии и одиночные книги

> **Оговорка:** длина серии здесь — это сколько книг серии уже попало в скрапинг, а не заявленная авторами длина. Пока скрапинг не завершён, длинные серии могут быть недосчитаны.

```js
const stats = FileAttachment("data/series-stats.json").json();
```

```js
const summary = stats.summary;
const sizeDistribution = stats.size_distribution;
const topByBookCount = stats.top_by_book_count;
const topByViews = stats.top_by_views;
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Книг в сериях</h2>
    <span class="big">${summary.series_books.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Отдельных книг</h2>
    <span class="big">${summary.standalone_books.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Ср. просмотров книги в серии</h2>
    <span class="big">${summary.avg_views_series_book.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Ср. просмотров отдельной книги</h2>
    <span class="big">${summary.avg_views_standalone_book.toLocaleString("ru-RU")}</span>
  </div>
</div>

Книги в сериях набирают в среднем **${Math.round(summary.avg_views_series_book / summary.avg_views_standalone_book)}×** больше просмотров, чем отдельные книги — вероятно, это эффект того, что уже вовлечённые читатели переходят от книги к книге внутри полюбившейся серии.

## Сколько книг в сериях

```js
function sizeDistributionChart(data, {width} = {}) {
  return Plot.plot({
    width,
    height: 300,
    x: {label: "Книг в серии", domain: [1, 30], clamp: true},
    y: {grid: true, label: "Серий"},
    marks: [
      Plot.rectY(data, {x: "series_length", y: "count", interval: 1, tip: true, fill: "var(--theme-foreground-focus)"}),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => sizeDistributionChart(sizeDistribution, {width}))}
  </div>
</div>

## Самые длинные серии

```js
Inputs.table(
  topByBookCount.map((d) => ({
    "Серия": d.name,
    "Книг": d.book_count,
    "Всего просмотров": d.total_views
  }))
)
```

## Самые просматриваемые серии

```js
Inputs.table(
  topByViews.map((d) => ({
    "Серия": d.name,
    "Книг": d.book_count,
    "Всего просмотров": d.total_views
  }))
)
```
