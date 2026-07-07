---
title: Продуктивность авторов
theme: dashboard
toc: false
---

# Продуктивность авторов

```js
const authors = FileAttachment("data/author-productivity.json").json();
const graphomaniacs = FileAttachment("data/graphomaniac-stats.json").json();
const exclusiveAuthors = FileAttachment("data/exclusive-authors.json").json();
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
, {select: false})
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
, {select: false})
```

## Эксклюзивные авторы

Авторы, у которых абсолютно все опубликованные книги отмечены как эксклюзив author.today (то есть нигде больше не публикуются) — а не просто часть каталога. Это гораздо более строгий критерий, чем доля эксклюзивных книг: из ${authors.length.toLocaleString("ru-RU")} авторов на платформе таких оказалось всего ${exclusiveAuthors.length}.

```js
Inputs.table(
  exclusiveAuthors.map((d) => ({
    "Автор": d.name,
    "Книг": d.book_count,
    "Всего лайков": d.total_likes,
    "Всего просмотров": d.total_views
  }))
, {select: false})
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
, {select: false})
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
, {select: false})
```

### ИИ-авторы

${graphomaniacs.top_ai.length === 0
  ? html`<p><em>Пока нет ни одного автора с ${graphomaniacs.min_books_for_leaderboard}+ книгами, помеченными как ИИ-сгенерированные — таких книг всего ${graphomaniacs.overall.find((d) => d.ai_generated)?.count ?? 0} на всю платформу.</em></p>`
  : Inputs.table(
      graphomaniacs.top_ai.map((d) => ({
        "Автор": d.name,
        "Книг": d.book_count,
        "Ср. объём (символов)": d.avg_chars,
        "Всего символов": d.total_chars
      }))
    , {select: false})
}
