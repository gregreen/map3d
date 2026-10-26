// Reddening-vs-distance plot (d3 v7).
const d3 = window.d3;

const WIDTH = 1000;
const HEIGHT = 500;
const MARGIN = { top: 30, right: 28, bottom: 62, left: 82 };
const TRANSITION_MS = 500;
const KPC_TICKS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100];

function kpcFromDistmod(dm) {
  return Math.pow(10, dm / 5 - 2);
}

function distmodFromKpc(kpc) {
  return 5 * Math.log10((kpc * 1000) / 10);
}

function formatKpc(kpc) {
  if (kpc < 1) {
    return `${Math.round(kpc * 1000)} pc`;
  }
  return `${kpc % 1 === 0 ? kpc : kpc.toFixed(1)} kpc`;
}

const asNumber = (value) => (value == null ? NaN : Number(value));

function quantile(values, p) {
  return values.length ? d3.quantileSorted(values, p) : NaN;
}

function perBinStats(samples) {
  if (!samples || samples.length === 0) {
    return null;
  }
  const nBins = samples[0].length;
  const med = new Array(nBins);
  const lo = new Array(nBins);
  const hi = new Array(nBins);

  for (let j = 0; j < nBins; j += 1) {
    const column = samples
      .map((row) => row[j])
      .filter((v) => Number.isFinite(v))
      .sort(d3.ascending);
    if (column.length === 0) {
      med[j] = lo[j] = hi[j] = NaN;
    } else {
      med[j] = quantile(column, 0.5);
      lo[j] = quantile(column, 0.1587);
      hi[j] = quantile(column, 0.8413);
    }
  }
  return { med, lo, hi };
}

/**
 * Distance bins bracketing `dm`, and how far between them `dm` lies.
 *
 * The pointer position is continuous, so the curve is read between bins rather
 * than snapped to the nearest one: `t = 0` is bin `i`, `t = 1` is bin `j`.
 */
function bracket(distmod, dm) {
  const n = distmod.length;
  if (n === 0) {
    return null;
  }
  if (n === 1 || dm <= distmod[0]) {
    return { i: 0, j: 0, t: 0 };
  }
  if (dm >= distmod[n - 1]) {
    return { i: n - 1, j: n - 1, t: 0 };
  }
  const j = d3.bisectLeft(distmod, dm);
  const i = j - 1;
  const span = distmod[j] - distmod[i];
  return { i, j, t: span > 0 ? (dm - distmod[i]) / span : 0 };
}

function interpolate(values, at) {
  const lo = values[at.i];
  const hi = values[at.j];
  if (at.i === at.j) {
    return lo;
  }
  return lo + (hi - lo) * at.t;
}

function buildModel(data, units, seriesLabel) {
  const samples = (data.samples || []).map((row) => (row || []).map(asNumber));
  return {
    distmod: (data.distmod || []).map(Number),
    best: (data.best || []).map(asNumber),
    samples,
    stats: perBinStats(samples),
    units,
    seriesLabel,
    dmMin: data.min_reliable_distmod,
    dmMax: data.max_reliable_distmod,
  };
}

function sameBins(a, b) {
  return (
    a.length === b.length
    && a.every((value, idx) => Math.abs(value - b[idx]) < 1e-9)
  );
}

// One state per <svg>, so that a new query animates the plot it replaces.
const plots = new WeakMap();

function createStructure(state) {
  const { svg, model, innerWidth, innerHeight } = state;
  const root = svg.append("g").attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);
  state.root = root;

  const reliable = root.append("g").attr("class", "reliable-group");
  state.layers.reliableRect = reliable.append("rect").attr("class", "reliable-range");
  state.layers.reliableEdges = [
    reliable.append("line").attr("class", "reliable-edge"),
    reliable.append("line").attr("class", "reliable-edge"),
  ];

  state.xAxis = d3.axisBottom(state.x).ticks(6).tickFormat(d3.format(".1f"));
  state.yAxis = d3.axisLeft(state.y).ticks(6).tickFormat(d3.format(".2f"));

  state.layers.xAxis = root
    .append("g")
    .attr("class", "axis x-axis")
    .attr("transform", `translate(0,${innerHeight})`);
  state.layers.xAxisTop = root.append("g").attr("class", "axis x-axis-top");
  state.layers.yAxis = root.append("g").attr("class", "axis y-axis");

  root
    .append("text")
    .attr("class", "axis-label")
    .attr("x", innerWidth / 2)
    .attr("y", innerHeight + 48)
    .attr("text-anchor", "middle")
    .text("Distance modulus (mag)");

  root
    .append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -innerHeight / 2)
    .attr("y", -56)
    .attr("text-anchor", "middle")
    .text(model.units);

  const series = root.append("g").attr("class", "series");
  state.layers.band = series.append("g").attr("class", "band-layer");
  state.layers.samples = series.append("g").attr("class", "sample-layer");
  state.layers.median = series.append("g").attr("class", "median-layer");
  state.layers.best = series.append("g").attr("class", "best-layer");

  const legendItems = [{ label: model.seriesLabel, cls: "best-line" }];
  if (model.stats) {
    legendItems.push({ label: "Median", cls: "median-line" });
    legendItems.push({ label: "16\u201384th pct.", cls: "band-swatch" });
  }

  const legendWidth = 168;
  const legendHeight = 20 * legendItems.length + 14;
  const legend = root
    .append("g")
    .attr("class", "legend")
    .attr("transform", `translate(${innerWidth - legendWidth - 12},12)`);

  legend
    .append("rect")
    .attr("class", "legend-frame")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .attr("rx", 4);

  legendItems.forEach((item, idx) => {
    const row = legend.append("g").attr("transform", `translate(10,${16 + idx * 20})`);
    if (item.cls === "band-swatch") {
      row
        .append("rect")
        .attr("width", 26)
        .attr("height", 10)
        .attr("y", -8)
        .style("fill", "#2f6f5e")
        .style("fill-opacity", 0.22);
    } else {
      row
        .append("line")
        .attr("x1", 0)
        .attr("x2", 26)
        .attr("y1", -3)
        .attr("y2", -3)
        .attr("class", item.cls);
    }
    row
      .append("text")
      .attr("x", 34)
      .attr("y", 0)
      .attr("font-size", 12)
      .attr("fill", "#5b6770")
      .text(item.label);
  });

  const hover = root.append("g").attr("class", "hover").style("display", "none");
  state.layers.hover = hover;
  state.layers.hoverLine = hover
    .append("line")
    .attr("class", "hover-line")
    .attr("y1", 0)
    .attr("y2", innerHeight);
  state.layers.hoverDot = hover.append("circle").attr("class", "hover-dot").attr("r", 4.5);

  const overlay = root
    .append("rect")
    .attr("width", innerWidth)
    .attr("height", innerHeight)
    .attr("fill", "transparent")
    .style("cursor", "crosshair");

  overlay
    .on("mousemove", (event) => {
      const [mx] = d3.pointer(event);
      const model = state.model;
      if (model.distmod.length === 0) return;

      const first = model.distmod[0];
      const last = model.distmod[model.distmod.length - 1];
      const dmValue = Math.min(Math.max(state.x.invert(mx), first), last);
      const at = bracket(model.distmod, dmValue);
      const stats = model.stats;
      const value = interpolate(stats ? stats.med : model.best, at);
      const px = state.x(dmValue);

      state.layers.hover.style("display", null);
      state.layers.hoverLine.attr("x1", px).attr("x2", px);
      state.layers.hoverDot
        .attr("cx", px)
        .attr("cy", state.y(value))
        .style("display", Number.isFinite(value) ? null : "none");

      if (state.onHover) {
        state.onHover({
          distmod: dmValue,
          kpc: kpcFromDistmod(dmValue),
          value,
          lo: stats ? interpolate(stats.lo, at) : NaN,
          hi: stats ? interpolate(stats.hi, at) : NaN,
          best: interpolate(model.best, at),
        });
      }
    })
    .on("mouseleave", () => {
      state.layers.hover.style("display", "none");
      if (state.onHover) state.onHover(null);
    });

  state.layers.overlay = overlay;
}

/** Join `values` onto the single path in `group` and draw it. */
function drawSinglePath(group, values, className, pathFor, duration) {
  const sel = group.selectAll("path").data(values.length ? [values] : []);
  sel.exit().remove();
  const merged = sel
    .enter()
    .append("path")
    .attr("class", className)
    .merge(sel);
  if (duration > 0) {
    merged.transition().duration(duration).attr("d", pathFor);
  } else {
    merged.attr("d", pathFor);
  }
  return merged;
}

function draw(state, duration) {
  const { model, innerWidth, innerHeight } = state;
  const { x, y } = state;
  const move = (selection) => (duration > 0 ? selection.transition().duration(duration) : selection);

  let xDomain = d3.extent(model.distmod);
  if (!Number.isFinite(xDomain[0]) || xDomain[0] === xDomain[1]) {
    xDomain = [Number.isFinite(xDomain[0]) ? xDomain[0] : 4, 0];
    xDomain[1] = xDomain[0] + 1;
  }
  x.domain(xDomain).nice();

  const finite = model.best.concat(model.samples.flat()).filter((v) => Number.isFinite(v));
  const yMax = finite.length ? d3.max(finite) : 1;
  y.domain([0, yMax > 0 ? yMax * 1.15 : 1]).nice();

  move(state.layers.xAxis).call(state.xAxis);
  move(state.layers.yAxis).call(state.yAxis);

  const kpcTicks = KPC_TICKS.map((kpc) => ({ kpc, dm: distmodFromKpc(kpc) })).filter(
    (tick) => tick.dm >= xDomain[0] && tick.dm <= xDomain[1],
  );
  if (kpcTicks.length) {
    const labelByDm = new Map(kpcTicks.map((tick) => [tick.dm, formatKpc(tick.kpc)]));
    move(state.layers.xAxisTop).call(
      d3
        .axisTop(x)
        .tickValues(kpcTicks.map((tick) => tick.dm))
        .tickFormat((value) => labelByDm.get(value) ?? ""),
    );
  } else {
    state.layers.xAxisTop.selectAll("*").remove();
  }

  const dmMin = model.dmMin;
  const dmMax = model.dmMax;
  const hasReliable =
    Number.isFinite(dmMin)
    && Number.isFinite(dmMax)
    && dmMax > dmMin
    && Math.abs(dmMin) < 100
    && Math.abs(dmMax) < 100
    && dmMin >= xDomain[0] - 0.001
    && dmMax <= xDomain[1] + 0.001;

  state.layers.reliableRect
    .style("display", hasReliable ? null : "none")
    .call((sel) =>
      move(sel)
        .attr("x", hasReliable ? x(dmMin) : 0)
        .attr("width", hasReliable ? Math.max(1, x(dmMax) - x(dmMin)) : 0)
        .attr("y", 0)
        .attr("height", innerHeight),
    );
  [dmMin, dmMax].forEach((dm, idx) => {
    move(state.layers.reliableEdges[idx])
      .style("display", hasReliable ? null : "none")
      .attr("x1", hasReliable ? x(dm) : 0)
      .attr("x2", hasReliable ? x(dm) : 0)
      .attr("y1", 0)
      .attr("y2", innerHeight);
  });

  const line = d3
    .line()
    .defined((d) => Number.isFinite(d[1]))
    .x((d) => x(d[0]))
    .y((d) => y(d[1]));

  const points = (values) => model.distmod.map((dm, j) => [dm, values[j]]);

  const bandData = model.stats
    ? model.distmod.map((dm, j) => ({ dm, lo: model.stats.lo[j], hi: model.stats.hi[j] }))
    : [];
  const bandPath = d3
    .area()
    .defined((d) => Number.isFinite(d.lo) && Number.isFinite(d.hi))
    .x((d) => x(d.dm))
    .y0((d) => y(d.lo))
    .y1((d) => y(d.hi));

  drawSinglePath(
    state.layers.band,
    bandData.length > 1 ? bandData : [],
    "band",
    bandPath,
    duration,
  );
  drawSinglePath(
    state.layers.median,
    model.stats ? points(model.stats.med) : [],
    "median-line",
    line,
    duration,
  );

  const sampleSel = state.layers.samples.selectAll("path.sample-line").data(model.samples);
  sampleSel.exit().remove();
  const samplePaths = sampleSel
    .enter()
    .append("path")
    .attr("class", "sample-line")
    .merge(sampleSel);
  const sampleFor = (row) => line(points(row));
  if (duration > 0) {
    samplePaths.transition().duration(duration).attr("d", sampleFor);
  } else {
    samplePaths.attr("d", sampleFor);
  }

  drawSinglePath(state.layers.best, points(model.best), "best-line", line, duration);
}

/**
 * Render, or smoothly update, the line-of-sight curve.
 *
 * Successive queries for the same map reuse the existing SVG: paths, axes and
 * the reliable-distance shading then animate to their new values instead of
 * being torn down and redrawn.
 *
 * @param {SVGElement} svgElement
 * @param {object} data  Response from /api/v2/interactive/<map>/losdata
 * @param {{units?: string, onHover?: Function, seriesLabel?: string}} options
 */
export function renderPlot(svgElement, data, options = {}) {
  const { units = "Reddening", onHover = null, seriesLabel = "Best fit" } = options;
  const model = buildModel(data, units, seriesLabel);

  const previous = plots.get(svgElement);
  const reusable =
    previous !== undefined
    && previous.model.units === model.units
    && previous.model.seriesLabel === model.seriesLabel
    && previous.model.samples.length === model.samples.length
    && sameBins(previous.model.distmod, model.distmod);

  let state = previous;
  if (reusable) {
    state.model = model;
    state.onHover = onHover;
    state.layers.hover.style("display", "none");
    draw(state, TRANSITION_MS);
  } else {
    svgElement.textContent = "";
    const svg = d3.select(svgElement);
    svg.attr("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
    state = {
      svg,
      model,
      onHover,
      innerWidth: WIDTH - MARGIN.left - MARGIN.right,
      innerHeight: HEIGHT - MARGIN.top - MARGIN.bottom,
      x: d3.scaleLinear().range([0, WIDTH - MARGIN.left - MARGIN.right]),
      y: d3.scaleLinear().range([HEIGHT - MARGIN.top - MARGIN.bottom, 0]),
      layers: {},
    };
    createStructure(state);
    draw(state, 0);
    plots.set(svgElement, state);
  }

  return {
    destroy() {
      state.layers.overlay.on("mousemove", null).on("mouseleave", null);
      state.svg.selectAll("*").interrupt();
      state.svg.selectAll("*").remove();
      plots.delete(svgElement);
    },
  };
}

export { kpcFromDistmod };
