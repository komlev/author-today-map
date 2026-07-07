---
title: Правки после публикации
theme: dashboard
toc: false
---

# Правки после публикации

Точная дата публикации книги на author.today не хранится напрямую — `updated_at` это дата *последнего* изменения. Используя ту же оценку предполагаемой даты публикации, что и на странице «Рост во времени» (`estimated_created_at` — минимум `updated_at` среди книг с таким же или большим id, так как id растёт по мере создания книг), можно посчитать промежуток между предполагаемой публикацией и последней правкой для каждой книги. Если этот промежуток равен нулю — книгу, скорее всего, ни разу не трогали после публикации; если больше нуля — автор возвращался и что-то менял.

*Промежуток для отредактированных книг — это оценка снизу: `estimated_created_at` сам является оценкой сверху на реальную дату публикации, поэтому настоящий промежуток может быть больше показанного, но не меньше.*

```js
const data = FileAttachment("data/edit-gap-stats.json").json();
```

```js
const neverPct = (data.never_touched_count / data.total_books * 100).toFixed(1);
const updatedPct = (data.updated_count / data.total_books * 100).toFixed(1);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Никогда не редактировались</h2>
    <span class="big">${neverPct}%</span>
  </div>
  <div class="card">
    <h2>Хотя бы раз отредактированы</h2>
    <span class="big">${updatedPct}%</span>
  </div>
  <div class="card">
    <h2>Медианный промежуток (среди отредактированных)</h2>
    <span class="big">${data.median_gap_days.toFixed(0)} дн.</span>
  </div>
  <div class="card">
    <h2>Самый долгий промежуток</h2>
    <span class="big">${(data.max_gap_days / 365).toFixed(1)} лет</span>
  </div>
</div>

## Через сколько после публикации авторы правят книги

Распределение промежутка между предполагаемой публикацией и последней правкой — только для книг, которые редактировались хоть раз, округлено до целых дней (0 — правка в тот же день, дальше ось X логарифмическая). Горб на «0» — в основном мгновенные исправления опечаток сразу после выкладывания; горб справа — недели-месяцы, то есть авторы, которые возвращаются к тексту спустя реальное время.

```js
// gap_days_points has continuous values down to fractions of a second
// (updated_at precision noise, not a meaningful "came back and edited"
// event) — nobody thinks in nanodays, so floor to whole days first. That
// puts everything under 24h into a real "0" bucket instead of smearing it
// across sub-day log ticks.
function dayThresholds(wholeDays, step = 0.15) {
  const positive = wholeDays.filter((d) => d >= 1);
  const end = Math.ceil(Math.log10(d3.max(positive)) / step) * step;
  return [0, ...d3.range(0, end + step, step).map((e) => 10 ** e)];
}
```

```js
function gapHistogram(values, {width} = {}) {
  const wholeDays = values.map((d) => Math.floor(d));
  const thresholds = dayThresholds(wholeDays);
  return Plot.plot({
    width,
    height: 300,
    // symlog (not log) so "0 days" has a real position on the axis instead
    // of being undefined at log(0) — linear near zero, logarithmic beyond,
    // which matches the bin layout above (one bin for [0,1), log-spaced
    // bins for [1, max]).
    x: {type: "symlog", label: "Дней между публикацией и последней правкой", grid: true, ticks: [0, 1, 10, 100, 1000]},
    y: {grid: true, label: "Книг"},
    marks: [
      Plot.rectY(wholeDays, Plot.binX({y: "count"}, {x: (d) => d, thresholds, tip: true, fill: "var(--theme-foreground-focus)"})),
      Plot.ruleY([0])
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => gapHistogram(data.gap_days_points, {width}))}
  </div>
</div>

## Авторы, которые никогда не правят свои книги

Авторы минимум с ${data.min_books_for_leaderboard} книгами, у которых абсолютно ни одна книга ни разу не редактировалась после публикации — то есть не разовая забытая книга, а систематическая привычка выкладывать и не возвращаться.

```js
import {linkCell, identity} from "./components/links.js";
```

```js
Inputs.table(
  data.top_never_touch_authors.map((d) => ({
    "Автор": linkCell(d.name, d.url),
    "Книг": d.book_count
  }))
, {select: false, format: {"Автор": identity}})
```

## Авторы, которые дольше всех возвращаются к своим книгам

Авторы минимум с ${data.min_books_for_leaderboard} отредактированными книгами, отсортированные по среднему промежутку между публикацией и последней правкой — то есть те, кто годами продолжает дорабатывать уже выложенные тексты.

```js
Inputs.table(
  data.top_long_revisers.map((d) => ({
    "Автор": linkCell(d.name, d.url),
    "Книг всего": d.book_count,
    "Из них отредактировано": d.updated_count,
    "Ср. промежуток (дней)": d.avg_gap_days
  }))
, {select: false, format: {"Автор": identity}})
```
