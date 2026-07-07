---
title: Накрутка
theme: dashboard
toc: false
---

# Накрутка

Эта страница ищет книги и авторов, чья статистика отклоняется от типичного соотношения просмотров и лайков: либо просмотров подозрительно много относительно лайков (возможная накрутка просмотров), либо наоборот (возможная накрутка лайков). Ориентир в обоих графиках — медиана лайков среди книг/авторов со сопоставимым охватом просмотров.

```js
const authors = FileAttachment("data/author-productivity.json").json();
const books = FileAttachment("data/nakrutka-books.json").json();
```

## По авторам

Каждая точка — автор: суммарные просмотры против суммарных лайков по всем его книгам (обе оси логарифмические). Линия — медиана лайков для авторов с таким охватом просмотров. Синие точки набрали заметно больше просмотров, чем обычно бывает при таком числе лайков. Красные — наоборот, заметно больше лайков, чем обычно бывает при таком охвате.

```js
function logThresholdsFor(values, step = 0.2) {
  const [lo, hi] = d3.extent(values);
  const start = Math.floor(Math.log10(lo) / step) * step;
  const end = Math.ceil(Math.log10(hi) / step) * step;
  return d3.range(start, end + step, step).map((e) => 10 ** e);
}

const OUTLIER_RATIO = 3; // 3x above/below the typical likes for that view range counts as накрутка

const nakrutkaAuthors = authors.filter((d) => d.total_views > 0 && d.total_likes > 0);
const authorViewThresholds = logThresholdsFor(nakrutkaAuthors.map((d) => d.total_views));
const authorViewBins = d3.bin().thresholds(authorViewThresholds).value((d) => d.total_views)(nakrutkaAuthors);

// Bins with few authors give a noisy median, so skip them for both the trend
// line and the outlier classification rather than flagging against a
// two-point "typical" value.
const authorMedianLine = authorViewBins
  .filter((b) => b.length >= 5)
  .map((b) => ({views: d3.median(b, (d) => d.total_views), likes: d3.median(b, (d) => d.total_likes)}));

const nakrutkaClassifiedAuthors = authorViewBins.flatMap((bin) => {
  if (bin.length < 5) return bin.map((d) => ({...d, deviation: "обычно"}));
  const expectedLikes = d3.median(bin, (d) => d.total_likes);
  return bin.map((d) => {
    const ratio = d.total_likes / expectedLikes;
    const deviation = ratio >= OUTLIER_RATIO ? "накрутка лайков" : ratio <= 1 / OUTLIER_RATIO ? "накрутка просмотров" : "обычно";
    return {...d, expected_likes: expectedLikes, ratio, deviation};
  });
});
```

```js
function nakrutkaAuthorsChart(data, medianLine, {width} = {}) {
  return Plot.plot({
    width,
    height: 550,
    x: {type: "log", label: "Просмотров", grid: true},
    y: {type: "log", label: "Лайков", grid: true},
    color: {
      legend: true,
      label: "Отклонение от медианы",
      domain: ["накрутка просмотров", "обычно", "накрутка лайков"],
      range: ["#2a78d6", "var(--theme-foreground-faint)", "#e34948"]
    },
    marks: [
      Plot.dot(data, {
        x: "total_views",
        y: "total_likes",
        r: 2.5,
        fill: "deviation",
        fillOpacity: (d) => (d.deviation === "обычно" ? 0.25 : 0.75),
        tip: true,
        title: (d) => `${d.name}\n${d.total_views.toLocaleString("ru-RU")} просмотров, ${d.total_likes.toLocaleString("ru-RU")} лайков\n${d.book_count} книг`
      }),
      Plot.line(medianLine, {x: "views", y: "likes", stroke: "var(--theme-foreground)", strokeWidth: 2})
    ]
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => nakrutkaAuthorsChart(nakrutkaClassifiedAuthors, authorMedianLine, {width}))}
  </div>
</div>

### Подозрительно много просмотров

```js
Inputs.table(
  nakrutkaClassifiedAuthors
    .filter((d) => d.deviation === "накрутка просмотров")
    .toSorted((a, b) => a.ratio - b.ratio)
    .slice(0, 20)
    .map((d) => ({
      "Автор": d.name,
      "Просмотров": d.total_views,
      "Лайков": d.total_likes,
      "Обычно лайков при таком охвате": Math.round(d.expected_likes),
      "Во сколько раз меньше": (1 / d.ratio).toFixed(1) + "x"
    }))
, {select: false})
```

### Подозрительно много лайков

```js
Inputs.table(
  nakrutkaClassifiedAuthors
    .filter((d) => d.deviation === "накрутка лайков")
    .toSorted((a, b) => b.ratio - a.ratio)
    .slice(0, 20)
    .map((d) => ({
      "Автор": d.name,
      "Просмотров": d.total_views,
      "Лайков": d.total_likes,
      "Обычно лайков при таком охвате": Math.round(d.expected_likes),
      "Во сколько раз больше": d.ratio.toFixed(1) + "x"
    }))
, {select: false})
```

## По книгам

То же самое на уровне отдельных книг, а не авторов. Точек здесь на порядки больше (280 000+), поэтому вместо точечной диаграммы — плотность (тёмные клетки — много книг с такими показателями), а медиана и выбросы посчитаны заранее на сервере. Фиолетовые точки — книги, сгенерированные ИИ; оранжевые — эксклюзивные (доступные только на author.today); эти две группы небольшие, поэтому показаны как есть, поверх плотности.

```js
const bookOverlays = view(Inputs.checkbox(
  ["Эксклюзив", "ИИ-сгенерированные"],
  {value: ["Эксклюзив", "ИИ-сгенерированные"]}
));
```

```js
function nakrutkaBooksChart(data, medianLine, aiPoints, exclusivePoints, {width} = {}, {showExclusive = true, showAi = true} = {}) {
  const viewThresholds = logThresholdsFor(data.map((d) => d.views));
  const likeThresholds = logThresholdsFor(data.map((d) => d.likes));
  const marks = [
    Plot.rect(data, Plot.bin({fill: "count"}, {
      x: {value: "views", thresholds: viewThresholds},
      y: {value: "likes", thresholds: likeThresholds}
    })),
    Plot.line(medianLine, {x: "views", y: "likes", stroke: "var(--theme-foreground)", strokeWidth: 2})
  ];
  if (showExclusive) {
    marks.push(Plot.dot(exclusivePoints, {
      x: "views", y: "likes", r: 2, fill: "orange", fillOpacity: 0.6,
      tip: true, title: (d) => `${d.title}\n${d.author}\nЭксклюзив`
    }));
  }
  if (showAi) {
    marks.push(Plot.dot(aiPoints, {
      x: "views", y: "likes", r: 2, fill: "#4a3aa7", fillOpacity: 0.6,
      tip: true, title: (d) => `${d.title}\n${d.author}\nИИ-сгенерированная`
    }));
  }
  return Plot.plot({
    width,
    height: 550,
    x: {type: "log", label: "Просмотров", grid: true},
    y: {type: "log", label: "Лайков", grid: true},
    color: {type: "log", scheme: "blues", legend: true, label: "Книг"},
    marks
  });
}
```

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => nakrutkaBooksChart(books.points, books.median_line, books.ai_points, books.exclusive_points, {width}, {showExclusive: bookOverlays.includes("Эксклюзив"), showAi: bookOverlays.includes("ИИ-сгенерированные")}))}
  </div>
</div>

### Подозрительно много просмотров (книги)

```js
Inputs.table(
  books.top_view_inflation.map((d) => ({
    "Книга": d.title,
    "Автор": d.author,
    "Просмотров": d.views,
    "Лайков": d.likes,
    "Обычно лайков при таком охвате": d.expected_likes,
    "Во сколько раз меньше": (1 / d.ratio).toFixed(1) + "x"
  }))
, {select: false})
```

### Подозрительно много лайков (книги)

```js
Inputs.table(
  books.top_like_inflation.map((d) => ({
    "Книга": d.title,
    "Автор": d.author,
    "Просмотров": d.views,
    "Лайков": d.likes,
    "Обычно лайков при таком охвате": d.expected_likes,
    "Во сколько раз больше": d.ratio.toFixed(1) + "x"
  }))
, {select: false})
```
