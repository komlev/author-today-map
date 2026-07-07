---
title: Соавторство
theme: dashboard
toc: false
---

# Соавторство

```js
import {linkCell, identity} from "./components/links.js";

const authors = FileAttachment("data/author-productivity.json").json();
const coauthorNetwork = FileAttachment("data/coauthor-network.json").json();
```

У подавляющего большинства книг один автор — совместных книг в текущем срезе данных всего ${coauthorNetwork.edges.length ? d3.sum(coauthorNetwork.edges, (d) => d.count).toLocaleString("ru-RU") : 0} из ${authors.length ? d3.sum(authors, (d) => d.book_count).toLocaleString("ru-RU") : 0}. Большинство соавторств — это устойчивая пара из двух человек: они не образуют сеть, а просто пишут вдвоём (полный список — в таблице дуэтов ниже). Сеть ниже показывает только группы от 4 соавторов — те случаи, где соавторство образует настоящую структуру, а не изолированную пару. Размер узла — сколько книг у автора всего (имена показаны только при наведении); заливка — средние просмотры на книгу у автора (по всем его книгам, не только совместным): от синего (мало просмотров) до красного (много). Колесо мыши — масштаб, перетаскивание — панорамирование. Клик по узлу выделяет его и подсвечивает чёрным все его связи; повторный клик или клик по пустому месту снимает выделение.

```js
// Plot has no built-in pan/zoom, so we wrap its output SVG with d3.zoom:
// move all rendered children into a <g> and let d3 update that <g>'s
// transform on wheel/drag. Plot's own tip:true tooltip tracks the pointer
// using pixel coordinates baked in at render time, which drift out of sync
// once the content is panned/zoomed underneath it.
//
// A plain <g transform="scale(k)"> is a *geometric* zoom: node radii and
// edge widths grow along with the spacing between them, so a dense cluster
// just becomes a bigger blob of fully-overlapping circles — no more
// legible than before, and with only the topmost circle left reachable by
// the mouse. Counter-scaling each mark's r / stroke-width by 1/k keeps
// their on-screen pixel size constant while the *distance* between node
// centers keeps growing with the zoom, which is what actually separates an
// overlapping cluster into distinguishable points — the standard "map pin"
// style of zoom.
//
// For the tooltip itself: the chart below still carries a plain `title`
// channel (native SVG <title>), which stays correctly positioned under any
// transform — but browsers only show that after ~1s of holding perfectly
// still, which is unusable on a 2px dot. So we drive our own instant
// tooltip off the same <title> text via pointermove, reusing one tooltip
// element across re-renders (module scope, guarded by id) so repeated
// resize() calls don't leak DOM nodes.
const coauthorTooltip = (() => {
  const existing = document.getElementById("coauthor-tooltip");
  if (existing) return existing;
  const el = document.createElement("div");
  el.id = "coauthor-tooltip";
  el.style.cssText = [
    "position: fixed", "pointer-events: none", "z-index: 1000",
    "background: var(--theme-background)", "color: var(--theme-foreground)",
    "border: 1px solid var(--theme-foreground-faint)", "border-radius: 4px",
    "padding: 4px 8px", "font-size: 12px", "line-height: 1.4",
    "white-space: pre", "display: none"
  ].join(";");
  document.body.appendChild(el);
  return el;
})();

function enableZoom(plot, {simNodes, simEdges} = {}) {
  const svgs = plot.tagName === "svg" ? [plot] : Array.from(plot.querySelectorAll("svg"));
  const svg = svgs[svgs.length - 1]; // the color-ramp legend is its own small svg rendered before the chart
  if (!svg) return plot;

  const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
  while (svg.firstChild) g.appendChild(svg.firstChild);
  svg.appendChild(g);
  svg.style.overflow = "hidden";
  svg.style.cursor = "grab";

  // Nodes carry no stroke, so only their radius needs counter-scaling.
  // Edges (rendered as <path>, not <line>) do have a real per-element
  // stroke-width (Plot.link's width channel is data-driven via sqrt(count),
  // so it's written on each path directly rather than hoisted to a shared
  // ancestor) and get the same treatment so they don't balloon into thick
  // bands at high zoom.
  const scalableRadii = Array.from(g.querySelectorAll("circle")).map((el) => ({
    el,
    r: parseFloat(el.getAttribute("r")) || 0
  }));
  const scalableStrokes = Array.from(g.querySelectorAll("path")).map((el) => ({
    el,
    strokeWidth: parseFloat(el.getAttribute("stroke-width")) || 0
  }));

  // Click-to-select: pair each rendered <circle>/<path> with its source
  // datum via the element's own __data__ (Plot's underlying d3 data-join
  // sets this to the row's original index into simNodes/simEdges). DOM
  // order itself is NOT reliable for this: Plot.dot auto-sorts marks by
  // descending r before rendering (so small dots paint on top of large
  // ones), which reshuffles circle order relative to simNodes — pairing by
  // plain index silently attached the wrong id to most circles.
  if (simNodes && simEdges) {
    const circles = Array.from(g.querySelectorAll("circle"));
    circles.forEach((el) => {
      el.dataset.id = simNodes[el.__data__].id;
      el.style.cursor = "pointer";
    });
    const paths = Array.from(g.querySelectorAll("path"));
    paths.forEach((el) => {
      const {source, target} = simEdges[el.__data__];
      // d3.forceLink mutates edge.source/target from ids into node refs.
      el.dataset.source = typeof source === "object" ? source.id : source;
      el.dataset.target = typeof target === "object" ? target.id : target;
    });

    let selectedId = null;
    const applySelection = (id) => {
      selectedId = id;
      for (const el of paths) {
        const connected = id != null && (el.dataset.source === id || el.dataset.target === id);
        el.setAttribute("stroke", connected ? "black" : "var(--theme-foreground-faint)");
        el.setAttribute("stroke-opacity", id == null ? "0.8" : connected ? "1" : "0.15");
      }
      for (const el of circles) {
        if (el.dataset.id === id) {
          el.setAttribute("stroke", "black");
          el.setAttribute("stroke-width", "2");
        } else {
          el.removeAttribute("stroke");
          el.removeAttribute("stroke-width");
        }
      }
    };

    svg.addEventListener("click", (event) => {
      const circle = event.target.closest?.("circle");
      const id = circle?.dataset.id ?? null;
      applySelection(id != null && id === selectedId ? null : id);
    });
  }

  d3.select(svg).call(
    d3.zoom()
      .scaleExtent([0.5, 12])
      .on("start", () => (svg.style.cursor = "grabbing"))
      .on("end", () => (svg.style.cursor = "grab"))
      .on("zoom", (event) => {
        g.setAttribute("transform", event.transform);
        const k = event.transform.k;
        for (const {el, r} of scalableRadii) el.setAttribute("r", r / k);
        for (const {el, strokeWidth} of scalableStrokes) {
          if (strokeWidth) el.setAttribute("stroke-width", strokeWidth / k);
        }
      })
  );

  svg.addEventListener("pointermove", (event) => {
    const title = event.target.closest?.("circle")?.querySelector("title");
    if (!title) {
      coauthorTooltip.style.display = "none";
      return;
    }
    coauthorTooltip.textContent = title.textContent;
    coauthorTooltip.style.left = `${event.clientX + 14}px`;
    coauthorTooltip.style.top = `${event.clientY + 14}px`;
    coauthorTooltip.style.display = "block";
  });
  svg.addEventListener("pointerleave", () => (coauthorTooltip.style.display = "none"));

  return plot;
}

function coauthorGraph({nodes, edges}, {width} = {}, {minGroupSize = 4} = {}) {
  const keptNodes = nodes.filter((d) => d.component_size >= minGroupSize);
  const keptIds = new Set(keptNodes.map((d) => d.id));
  const keptEdges = edges.filter((d) => keptIds.has(d.source) && keptIds.has(d.target));

  // d3.forceLink mutates its input array's source/target from ids into node
  // object refs in place. Since resize() re-invokes this function on every
  // viewport resize, feeding it the shared coauthorNetwork.edges/nodes arrays
  // directly would corrupt them after the first render — clone both instead.
  const simNodes = keptNodes.map((d) => ({...d}));
  const simEdges = keptEdges.map((d) => ({...d}));
  const degree = new Map(simNodes.map((d) => [d.id, 0]));
  for (const e of simEdges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }

  const simulation = d3.forceSimulation(simNodes)
    .force("link", d3.forceLink(simEdges).id((d) => d.id).distance(30).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-90))
    .force("center", d3.forceCenter(0, 0))
    .force("collide", d3.forceCollide(14))
    .stop();

  for (let i = 0; i < 400; ++i) simulation.tick();

  const plot = Plot.plot({
    width,
    height: Math.min(width, 900),
    margin: 10,
    inset: 30,
    x: {axis: null},
    y: {axis: null},
    color: {type: "log", scheme: "RdBu", reverse: true, legend: true, label: "Ср. просмотров/книгу"},
    marks: [
      Plot.link(simEdges, {
        x1: (d) => d.source.x, y1: (d) => d.source.y,
        x2: (d) => d.target.x, y2: (d) => d.target.y,
        strokeWidth: (d) => Math.sqrt(d.count),
        stroke: "var(--theme-foreground-faint)",
        strokeOpacity: 0.8
      }),
      Plot.dot(simNodes, {
        x: "x", y: "y",
        r: (d) => Math.sqrt(d.book_count ?? 1) + 2,
        fill: "avg_views_per_book",
        title: (d) => `${d.name}\n${d.book_count} книг, ${degree.get(d.id) ?? 0} соавторов, ${d.avg_views_per_book} просмотров/книгу${d.ai_generated ? "\nПишет ИИ-книги" : ""}`
      })
    ]
  });

  return enableZoom(plot, {simNodes, simEdges});
}
```

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
