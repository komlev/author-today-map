---
title: Соавторство
theme: dashboard
toc: false
---

# Соавторство

```js
import {linkCell, identity} from "./components/links.js";
import {coauthorGraph} from "./components/coauthor-graph.js";

const authors = FileAttachment("data/author-productivity.json").json();
const coauthorNetwork = FileAttachment("data/coauthor-network.json").json();
```

У подавляющего большинства книг один автор — совместных книг в текущем срезе данных всего ${coauthorNetwork.edges.length ? d3.sum(coauthorNetwork.edges, (d) => d.count).toLocaleString("ru-RU") : 0} из ${authors.length ? d3.sum(authors, (d) => d.book_count).toLocaleString("ru-RU") : 0}. Большинство соавторств — это устойчивая пара из двух человек: они не образуют сеть, а просто пишут вдвоём (полный список — в таблице дуэтов ниже). Сеть ниже показывает только группы от 4 соавторов — те случаи, где соавторство образует настоящую структуру, а не изолированную пару. Размер узла — сколько книг у автора всего (имена показаны только при наведении); заливка — средние просмотры на книгу у автора (по всем его книгам, не только совместным): от синего (мало просмотров) до красного (много). Колесо мыши — масштаб, перетаскивание — панорамирование. Клик по узлу выделяет его и подсвечивает чёрным все его связи; повторный клик или клик по пустому месту снимает выделение.

<div class="grid grid-cols-1">
  <div class="card">
    ${resize((width) => coauthorGraph(coauthorNetwork, {width}))}
  </div>
</div>

## Самые устойчивые творческие дуэты

```js
Inputs.table(
  coauthorNetwork.edges
    .toSorted((a, b) => b.count - a.count)
    .slice(0, 20)
    .map((d) => {
      const a = coauthorNetwork.nodes.find((n) => n.id === d.source);
      const b = coauthorNetwork.nodes.find((n) => n.id === d.target);
      return {
        "Автор 1": linkCell(a?.name, a?.id),
        "Автор 2": linkCell(b?.name, b?.id),
        "Совместных книг": d.count,
        "Суммарно просмотров": d.views
      };
    })
, {select: false, format: {"Автор 1": identity, "Автор 2": identity}})
```

## Авторы с наибольшим числом соавторов

В отличие от таблицы дуэтов выше (устойчивые пары), здесь — авторы с наибольшим числом *разных* соавторов, независимо от того, сколько книг написано с каждым из них.

```js
Inputs.table(
  coauthorNetwork.nodes
    .toSorted((a, b) => b.degree - a.degree)
    .slice(0, 20)
    .map((d) => ({
      "Автор": linkCell(d.name, d.id),
      "Разных соавторов": d.degree,
      "Книг всего": d.book_count,
      "Ср. просмотров/книгу": d.avg_views_per_book
    }))
, {select: false, format: {"Автор": identity}})
```
