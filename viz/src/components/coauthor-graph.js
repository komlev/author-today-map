import * as d3 from "npm:d3";
import * as Plot from "npm:@observablehq/plot";

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
function coauthorTooltip() {
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
}

function enableZoom(plot, {simNodes, simEdges} = {}) {
  const tooltip = coauthorTooltip();
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
      // Some layouts pre-highlight certain nodes (e.g. a found path between
      // two chosen authors) with their own stroke — remember it now so
      // deselecting restores that instead of blanking it.
      el.dataset.originalStroke = el.getAttribute("stroke") ?? "";
      el.dataset.originalStrokeWidth = el.getAttribute("stroke-width") ?? "";
    });
    const paths = Array.from(g.querySelectorAll("path"));
    paths.forEach((el) => {
      const {source, target} = simEdges[el.__data__];
      // d3.forceLink mutates edge.source/target from ids into node refs.
      el.dataset.source = typeof source === "object" ? source.id : source;
      el.dataset.target = typeof target === "object" ? target.id : target;
      // Some layouts (e.g. the tangled tree) color each edge meaningfully
      // rather than a flat gray — remember that color now so deselecting
      // restores it instead of overwriting every edge with a hardcoded gray.
      el.dataset.originalStroke = el.getAttribute("stroke") ?? "var(--theme-foreground-faint)";
      el.dataset.originalStrokeOpacity = el.getAttribute("stroke-opacity") ?? "0.8";
    });

    let selectedId = null;
    const applySelection = (id) => {
      selectedId = id;
      for (const el of paths) {
        const connected = id != null && (el.dataset.source === id || el.dataset.target === id);
        el.setAttribute("stroke", connected ? "black" : el.dataset.originalStroke);
        el.setAttribute("stroke-opacity", id == null ? el.dataset.originalStrokeOpacity : connected ? "1" : "0.15");
      }
      for (const el of circles) {
        if (el.dataset.id === id) {
          el.setAttribute("stroke", "black");
          el.setAttribute("stroke-width", "2");
        } else if (el.dataset.originalStroke) {
          el.setAttribute("stroke", el.dataset.originalStroke);
          el.setAttribute("stroke-width", el.dataset.originalStrokeWidth);
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
      tooltip.style.display = "none";
      return;
    }
    tooltip.textContent = title.textContent;
    tooltip.style.left = `${event.clientX + 14}px`;
    tooltip.style.top = `${event.clientY + 14}px`;
    tooltip.style.display = "block";
  });
  svg.addEventListener("pointerleave", () => (tooltip.style.display = "none"));

  return plot;
}

const nodeRadius = (d) => Math.sqrt(d.book_count ?? 1) + 2;

function degreeMap(nodes, edges) {
  const degree = new Map(nodes.map((d) => [d.id, 0]));
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  return degree;
}

function nodeTitle(degree) {
  return (d) => `${d.name}\n${d.book_count} книг, ${degree.get(d.id) ?? 0} соавторов, ${d.avg_views_per_book} просмотров/книгу${d.ai_generated ? "\nПишет ИИ-книги" : ""}`;
}

// Shared renderer: force-simulates simNodes/simEdges (already prepared by
// the caller — cloned so d3.forceLink can mutate edge.source/target in
// place) and draws them with Plot. Used both for the small per-component
// graphs (Соавторство) and for the reduced "backbone" graph of the giant
// network, which is why radius/title are pluggable per node rather than
// hardcoded to the plain book_count-based look.
function renderForceLayout(simNodes, simEdges, {width, height} = {}, {radius = nodeRadius, title} = {}) {
  // This graph is sparse and hub-dominated (a handful of prolific authors
  // bridging hundreds of degree-1/2 satellites), not a dense hairball — a
  // tight link distance and weak charge leave barely any room for a hub's
  // spokes to fan out, so they collapse into overlapping, crossing tangles.
  // Wide spacing (distance 60, charge -220) gives each hub room to spread
  // its neighbors into a legible star instead of a knot; a collide radius
  // keyed to each node's actual drawn size (rather than a flat number,
  // which can be smaller than some nodes' real radius) stops circles from
  // overlapping regardless of size. More ticks (900) are needed for a
  // sparse graph like this to fully settle at the wider spacing instead of
  // visibly still-drifting into its final shape.
  const simulation = d3.forceSimulation(simNodes)
    .force("link", d3.forceLink(simEdges).id((d) => d.id).distance(60).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-220))
    .force("center", d3.forceCenter(0, 0))
    .force("collide", d3.forceCollide((d) => radius(d) + 3).strength(1))
    .stop();

  for (let i = 0; i < 900; ++i) simulation.tick();

  const plot = Plot.plot({
    width,
    height: height ?? Math.min(width, 900),
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
        strokeDasharray: (d) => (d.bridge ? "3,3" : null),
        stroke: "var(--theme-foreground-faint)",
        strokeOpacity: 0.8
      }),
      Plot.dot(simNodes, {
        x: "x", y: "y",
        r: radius,
        fill: "avg_views_per_book",
        title
      })
    ]
  });

  return enableZoom(plot, {simNodes, simEdges});
}

function forceGraph(keptNodes, keptEdges, {width, height} = {}) {
  // d3.forceLink mutates its input array's source/target from ids into node
  // object refs in place. Since resize() re-invokes this function on every
  // viewport resize, feeding it the shared nodes/edges arrays directly would
  // corrupt them after the first render — clone both instead.
  const simNodes = keptNodes.map((d) => ({...d}));
  const simEdges = keptEdges.map((d) => ({...d}));
  const degree = degreeMap(simNodes, simEdges);

  return renderForceLayout(simNodes, simEdges, {width, height}, {title: nodeTitle(degree)});
}

function hubPairKey(a, b) {
  return a < b ? `${a} ${b}` : `${b} ${a}`;
}

// Manually-created <path> elements (raw DOM calls, not a Plot/d3 data join)
// don't get __data__ set automatically the way Plot's own marks do —
// enableZoom's click-to-select code reads `simEdges[el.__data__]` for every
// <path> in the chart, so each injected link must have that index attached
// explicitly or click-select throws on the first path it inspects.
function injectTangledLinks(plot, simEdges, positionOf, edgeColor, {pathEdgeKeys} = {}) {
  const svgs = plot.tagName === "svg" ? [plot] : Array.from(plot.querySelectorAll("svg"));
  const svg = svgs[svgs.length - 1];
  if (!svg) return;

  const xScale = plot.scale("x");
  const yScale = plot.scale("y");
  const link = d3.linkHorizontal().x((d) => d[0]).y((d) => d[1]);
  const svgNS = "http://www.w3.org/2000/svg";
  const firstChild = svg.firstChild;

  simEdges.forEach((e, i) => {
    const s = positionOf.get(e.source);
    const t = positionOf.get(e.target);
    const d = link({
      source: [xScale.apply(s.x), yScale.apply(s.y)],
      target: [xScale.apply(t.x), yScale.apply(t.y)]
    });
    // When a path between two chosen authors is highlighted, its edges get
    // pulled fully opaque and thick regardless of branch color so the route
    // reads clearly against everything else, which gets pushed down to
    // near-invisible instead of competing for attention.
    const onPath = pathEdgeKeys?.has(hubPairKey(e.source, e.target));
    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", edgeColor(e));
    path.setAttribute("stroke-opacity", pathEdgeKeys ? (onPath ? "1" : "0.06") : "0.55");
    path.setAttribute("stroke-width", String(onPath ? Math.max(3, Math.sqrt(e.count) * 2) : Math.max(1, Math.sqrt(e.count))));
    path.__data__ = i;
    svg.insertBefore(path, firstChild); // links under the dots layer
  });
}

// A genealogy-style "tangled tree": author position is x = hop-distance
// from the network's hub (BFS level, i.e. how many co-author "handshakes"
// from the most-connected author) and y = a within-level slot chosen so
// each node sits near its BFS-tree parent's row — so the columns read left
// to right as "closer to the hub" to "further out", exactly like the
// generation columns in a family-tree diagram. Every real edge (not just
// the spanning tree) is drawn as a smooth horizontal curve; edges are
// colored by which of the hub's ~20 direct co-authors ("branch") the
// deeper endpoint descends from, so a single lineage stays visually
// traceable as it threads across levels, the way each mythological
// lineage keeps one color in the reference tangled-tree diagrams. Nodes
// keep the same avg-views-per-book fill as every other page here — only
// the edges carry the branch color, so the legend stays meaningful.
function tangledTreeGraph(keptNodes, keptEdges, {width, height} = {}, {highlightPath} = {}) {
  const degree = degreeMap(keptNodes, keptEdges);
  const rootId = keptNodes.toSorted((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))[0]?.id;

  const adjacency = new Map(keptNodes.map((d) => [d.id, []]));
  for (const e of keptEdges) {
    adjacency.get(e.source).push(e.target);
    adjacency.get(e.target).push(e.source);
  }

  const levelOf = new Map([[rootId, 0]]);
  const parentOf = new Map([[rootId, null]]);
  const queue = [rootId];
  while (queue.length) {
    const id = queue.shift();
    for (const neighbor of adjacency.get(id)) {
      if (!levelOf.has(neighbor)) {
        levelOf.set(neighbor, levelOf.get(id) + 1);
        parentOf.set(neighbor, id);
        queue.push(neighbor);
      }
    }
  }
  const maxLevel = Math.max(...levelOf.values());

  const branchOf = new Map();
  for (const id of levelOf.keys()) {
    let cur = id;
    while (levelOf.get(cur) > 1) cur = parentOf.get(cur);
    branchOf.set(id, cur);
  }

  const nodesByLevel = new Map(d3.range(maxLevel + 1).map((l) => [l, []]));
  for (const id of levelOf.keys()) nodesByLevel.get(levelOf.get(id)).push(id);

  // Order each level by its members' parent's already-assigned slot (so
  // siblings stay grouped under their parent instead of scattered), then by
  // degree as a stable tiebreaker — a lightweight stand-in for full
  // crossing-minimization, in the same spirit as the standard tangled-tree
  // recipe's simplified ordering pass.
  const slotOf = new Map();
  for (let l = 0; l <= maxLevel; ++l) {
    const members = nodesByLevel.get(l);
    const ordered = members.toSorted((a, b) => {
      const pa = l === 0 ? 0 : slotOf.get(parentOf.get(a));
      const pb = l === 0 ? 0 : slotOf.get(parentOf.get(b));
      if (pa !== pb) return pa - pb;
      return (degree.get(b) ?? 0) - (degree.get(a) ?? 0);
    });
    ordered.forEach((id, i) => slotOf.set(id, i));
  }

  const positionOf = new Map();
  for (const [l, members] of nodesByLevel) {
    for (const id of members) positionOf.set(id, {x: l, y: slotOf.get(id) - members.length / 2});
  }

  const branchIds = [...new Set(branchOf.values())];
  const palette = d3.schemeTableau10;
  const colorOf = new Map(branchIds.map((id, i) => [id, palette[i % palette.length]]));
  const edgeColor = (e) => {
    const deeper = levelOf.get(e.source) >= levelOf.get(e.target) ? e.source : e.target;
    return colorOf.get(branchOf.get(deeper));
  };

  const pathNodeIds = highlightPath?.length ? new Set(highlightPath) : null;
  const pathEdgeKeys = highlightPath?.length > 1
    ? new Set(highlightPath.slice(1).map((id, i) => hubPairKey(highlightPath[i], id)))
    : null;

  const simNodes = keptNodes.map((d) => ({...d, ...positionOf.get(d.id)}));
  const tangledNodeRadius = (d) => (pathNodeIds?.has(d.id) ? 5.5 : 3.5);

  const maxColumnPopulation = Math.max(...[...nodesByLevel.values()].map((a) => a.length));

  const plot = Plot.plot({
    width,
    height: height ?? Math.max(500, maxColumnPopulation * 12 + 80),
    margin: 10,
    inset: 20,
    x: {axis: null, domain: [-0.5, maxLevel + 0.5]},
    y: {axis: null},
    color: {type: "log", scheme: "RdBu", reverse: true, legend: true, label: "Ср. просмотров/книгу"},
    marks: [
      Plot.dot(simNodes, {
        x: "x", y: "y",
        r: tangledNodeRadius,
        fill: "avg_views_per_book",
        stroke: (d) => (pathNodeIds?.has(d.id) ? "black" : "none"),
        strokeWidth: (d) => (pathNodeIds?.has(d.id) ? 2 : 0),
        title: nodeTitle(degree)
      })
    ]
  });

  injectTangledLinks(plot, keptEdges, positionOf, edgeColor, {pathEdgeKeys});

  return enableZoom(plot, {simNodes, simEdges: keptEdges});
}

// 584 authors in one static node-link picture is unreadable regardless of
// layout — the fix isn't a cleverer layout, it's drawing fewer nodes. Only
// the well-connected "backbone" authors (degree >= hubDegree) are rendered
// individually; everyone else is folded into whichever hub(s) they're
// structurally attached to. A satellite isn't always one hop from a hub —
// chains of degree-1/2 co-authors can run several hops before reaching one
// — so we remove the hubs and look at the connected "satellite clusters"
// left over in the non-hub remainder: a cluster touching exactly one hub is
// that hub's folded tail (counted in its tooltip, not drawn); a cluster
// touching two or more hubs represents a real bridge between them and gets
// its own dashed backbone edge instead of being dropped.
function backboneGraph(keptNodes, keptEdges, {width, height} = {}, {hubDegree = 4} = {}) {
  const degree = degreeMap(keptNodes, keptEdges);
  const hubIds = new Set(keptNodes.filter((d) => (degree.get(d.id) ?? 0) >= hubDegree).map((d) => d.id));

  const adjacency = new Map(keptNodes.map((d) => [d.id, []]));
  for (const e of keptEdges) {
    adjacency.get(e.source).push(e.target);
    adjacency.get(e.target).push(e.source);
  }

  const satelliteCount = new Map();
  const bridgeWeight = new Map();
  const visited = new Set();
  for (const node of keptNodes) {
    if (hubIds.has(node.id) || visited.has(node.id)) continue;
    const cluster = [];
    const borderingHubs = new Set();
    const stack = [node.id];
    visited.add(node.id);
    while (stack.length) {
      const id = stack.pop();
      cluster.push(id);
      for (const neighbor of adjacency.get(id)) {
        if (hubIds.has(neighbor)) {
          borderingHubs.add(neighbor);
        } else if (!visited.has(neighbor)) {
          visited.add(neighbor);
          stack.push(neighbor);
        }
      }
    }
    if (borderingHubs.size === 0) {
      // No hub anywhere nearby — only possible for a stray cluster with no
      // member reaching hubDegree at all. Promote its best-connected member
      // so this handful of authors isn't silently dropped from the picture.
      const fallbackHub = cluster.toSorted((a, b) => (degree.get(b) ?? 0) - (degree.get(a) ?? 0))[0];
      hubIds.add(fallbackHub);
      satelliteCount.set(fallbackHub, (satelliteCount.get(fallbackHub) ?? 0) + cluster.length - 1);
      continue;
    }
    for (const hub of borderingHubs) {
      satelliteCount.set(hub, (satelliteCount.get(hub) ?? 0) + cluster.length);
    }
    if (borderingHubs.size >= 2) {
      const hubs = [...borderingHubs];
      for (let i = 0; i < hubs.length; ++i) {
        for (let j = i + 1; j < hubs.length; ++j) {
          const key = hubPairKey(hubs[i], hubs[j]);
          bridgeWeight.set(key, (bridgeWeight.get(key) ?? 0) + cluster.length);
        }
      }
    }
  }

  const backboneNodes = keptNodes
    .filter((d) => hubIds.has(d.id))
    .map((d) => ({...d, satelliteCount: satelliteCount.get(d.id) ?? 0}));

  const directEdges = keptEdges
    .filter((e) => hubIds.has(e.source) && hubIds.has(e.target))
    .map((e) => ({...e}));
  const directKeys = new Set(directEdges.map((e) => hubPairKey(e.source, e.target)));
  const bridgeEdges = Array.from(bridgeWeight, ([key, weight]) => {
    const [source, target] = key.split(" ");
    return {source, target, count: weight, views: 0, bridge: true};
  }).filter((e) => !directKeys.has(hubPairKey(e.source, e.target)));

  const degreeInBackbone = degreeMap(backboneNodes, [...directEdges, ...bridgeEdges]);
  const title = (d) => {
    const base = nodeTitle(degreeInBackbone)(d);
    return d.satelliteCount > 0 ? `${base}\n+${d.satelliteCount} менее активных соавторов рядом` : base;
  };
  const radius = (d) => nodeRadius(d) + Math.sqrt(d.satelliteCount) * 0.6;

  return renderForceLayout(backboneNodes, [...directEdges, ...bridgeEdges], {width, height}, {radius, title});
}

export function coauthorGraph({nodes, edges}, {width, height} = {}, {minGroupSize = 4, componentId, layout = "force", hubDegree, highlightPath} = {}) {
  const keptNodes = componentId != null
    ? nodes.filter((d) => d.component_id === componentId)
    : nodes.filter((d) => d.component_size >= minGroupSize);
  const keptIds = new Set(keptNodes.map((d) => d.id));
  const keptEdges = edges.filter((d) => keptIds.has(d.source) && keptIds.has(d.target));

  if (layout === "backbone") return backboneGraph(keptNodes, keptEdges, {width, height}, {hubDegree});
  if (layout === "tangled") return tangledTreeGraph(keptNodes, keptEdges, {width, height}, {highlightPath});
  return forceGraph(keptNodes, keptEdges, {width, height});
}
