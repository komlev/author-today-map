---
title: Серии и одиночные книги
theme: dashboard
toc: false
---

# Серии и одиночные книги

```js
const stats = FileAttachment("data/series-stats.json").json();
```

```js
const summary = stats.summary;
const literary = stats.literary;
const poetry = stats.poetry;
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

> **Проза и поэзия считаются раздельно.** Несколько поэтических серий (например «БОСЯ - ЮТУБ», «СТИШКУНЫ») состоят из десятков коротких стихотворений, каждое из которых опубликовано как отдельная «книга» — в общем зачёте они забивали бы все рейтинги по числу книг просто в силу формата, а не потому что это необычно длинные серии. Серия считается поэтической, если минимум половина её книг относится к жанру «Поэзия».

## Проза

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Серий</h2>
    <span class="big">${literary.series_count.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Книг в сериях</h2>
    <span class="big">${literary.book_count.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Ср. просмотров/книгу</h2>
    <span class="big">${literary.avg_views_per_book.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Ср. лайков/книгу</h2>
    <span class="big">${literary.avg_likes_per_book.toLocaleString("ru-RU")}</span>
  </div>
</div>

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
    ${resize((width) => sizeDistributionChart(literary.size_distribution, {width}))}
  </div>
</div>

### Самые длинные серии

```js
Inputs.table(
  literary.top_by_book_count.map((d) => ({
    "Серия": d.name,
    "Книг": d.book_count,
    "Всего просмотров": d.total_views
  }))
, {select: false})
```

### Самые просматриваемые серии

```js
Inputs.table(
  literary.top_by_views.map((d) => ({
    "Серия": d.name,
    "Книг": d.book_count,
    "Всего просмотров": d.total_views
  }))
, {select: false})
```

## Поэзия

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Серий</h2>
    <span class="big">${poetry.series_count.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Книг в сериях</h2>
    <span class="big">${poetry.book_count.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Ср. просмотров/книгу</h2>
    <span class="big">${poetry.avg_views_per_book.toLocaleString("ru-RU")}</span>
  </div>
  <div class="card">
    <h2>Ср. лайков/книгу</h2>
    <span class="big">${poetry.avg_likes_per_book.toLocaleString("ru-RU")}</span>
  </div>
</div>

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => sizeDistributionChart(poetry.size_distribution, {width}))}
  </div>
</div>

### Самые длинные поэтические серии

```js
Inputs.table(
  poetry.top_by_book_count.map((d) => ({
    "Серия": d.name,
    "Книг": d.book_count,
    "Всего просмотров": d.total_views
  }))
, {select: false})
```

### Самые просматриваемые поэтические серии

```js
Inputs.table(
  poetry.top_by_views.map((d) => ({
    "Серия": d.name,
    "Книг": d.book_count,
    "Всего просмотров": d.total_views
  }))
, {select: false})
```
