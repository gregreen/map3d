// Query page wiring: form state, API calls, rendering.
import { ApiError, fetchLosData, fetchMapMetadata, losDataUrl, losTableUrl } from "./api.js";
import { equ2gal, gal2equ, parseAngle } from "./coords.js";
import { renderPlot } from "./plot.js";
import { renderStamps } from "./stamps.js";

const dom = {
  form: document.getElementById("query-form"),
  lonInput: document.getElementById("lon-input"),
  latInput: document.getElementById("lat-input"),
  lonSymbol: document.getElementById("lon-symbol"),
  latSymbol: document.getElementById("lat-symbol"),
  coordSys: () => document.querySelector('input[name="coordsys"]:checked').value,
  mapSelect: document.getElementById("map-select"),
  submitBtn: document.getElementById("submit-btn"),
  submitSpinner: document.getElementById("submit-spinner"),
  mapNote: document.getElementById("map-note"),
  errorAlert: document.getElementById("error-alert"),
  errorTitle: document.getElementById("error-title"),
  errorMessage: document.getElementById("error-message"),
  errorExamples: document.getElementById("error-examples"),
  results: document.getElementById("results"),
  plotCaption: document.getElementById("plot-caption"),
  plotSvg: document.getElementById("los-plot"),
  readoutKpc: document.getElementById("readout-kpc"),
  readoutEbv: document.getElementById("readout-ebv"),
  readoutUnits: document.getElementById("readout-units"),
  readoutRange: document.getElementById("readout-range"),
  convergence: document.getElementById("convergence-warning"),
  stamps: document.getElementById("stamps"),
  stampsSection: document.getElementById("stamps-section"),
  stampsUnavailable: document.getElementById("stamps-unavailable"),
  stampsUnits: document.getElementById("stamps-units"),
  tableLink: document.getElementById("download-table"),
  jsonLink: document.getElementById("download-json"),
  apiLink: document.getElementById("api-link"),
};

const state = {
  mapMetadata: {},
  controller: null,
  lastData: null,
  plot: null,
  coordsys: "gal",
};

function coordSysLabels(coordsys) {
  if (coordsys === "gal") {
    dom.lonSymbol.innerHTML = "&#8467;";
    dom.latSymbol.textContent = "b";
    dom.lonInput.placeholder = "82.57";
    dom.latInput.placeholder = "-15.5";
  } else {
    dom.lonSymbol.innerHTML = "&alpha;";
    dom.latSymbol.innerHTML = "&delta;";
    dom.lonInput.placeholder = "05h30m17s or 82.57";
    dom.latInput.placeholder = "-15d30m17s or -15.5";
  }
}

function showError(title, message, examples = "") {
  dom.errorTitle.textContent = title;
  dom.errorMessage.textContent = message;
  dom.errorExamples.textContent = examples;
  dom.errorAlert.classList.remove("d-none");
}

function clearError() {
  dom.errorAlert.classList.add("d-none");
}

function setBusy(busy) {
  dom.submitBtn.disabled = busy;
  dom.submitSpinner.classList.toggle("d-none", !busy);
}

function readForm() {
  const coordsys = dom.coordSys();
  const allowHms = coordsys === "equ";
  const lon = parseAngle(dom.lonInput.value, allowHms);
  const lat = parseAngle(dom.latInput.value, allowHms);

  if (lon.value === null) {
    showError(
      "Invalid longitude",
      "Enter decimal degrees, or a value such as 05h30m17s (equatorial) / 82:30:17.",
      "Examples: 82.57 · 05h30m17s · 82d30m17s",
    );
    dom.lonInput.focus();
    return null;
  }
  if (lat.value === null) {
    showError(
      "Invalid latitude",
      "Enter decimal degrees, or a value such as -15d30m17s.",
      "Examples: -15.505 · -15d30m17s",
    );
    dom.latInput.focus();
    return null;
  }
  if (lat.value < -90 || lat.value > 90) {
    showError("Invalid latitude", "Latitude must lie between -90 and +90 degrees.");
    dom.latInput.focus();
    return null;
  }

  clearError();
  return {
    coordsys,
    lon: lon.value,
    lat: lat.value,
    map: dom.mapSelect.value,
  };
}

function updateMapNote() {
  const entry = state.mapMetadata[dom.mapSelect.value];
  if (!entry) {
    dom.mapNote.textContent = "";
    return;
  }
  const bits = [entry.display_units || entry.units];
  bits.push(entry.supports_samples ? "posterior samples available" : "mean curve only");
  dom.mapNote.textContent = `${entry.description} · ${bits.join(" · ")}`;
}

function updateReadout(hover) {
  dom.readoutUnits.textContent = (state.lastData && state.lastData.units) || "Reddening";
  if (!hover) {
    dom.readoutKpc.textContent = "–";
    dom.readoutEbv.textContent = "–";
    dom.readoutRange.textContent = "";
    return;
  }

  const kpc = hover.kpc;
  dom.readoutKpc.textContent =
    kpc < 1 ? `${(kpc * 1000).toFixed(0)} pc` : `${kpc.toFixed(2)} kpc`;

  if (!Number.isFinite(hover.value)) {
    dom.readoutEbv.textContent = "not covered";
    dom.readoutRange.textContent = "";
    return;
  }

  dom.readoutEbv.textContent = hover.value.toFixed(3);
  if (Number.isFinite(hover.lo) && Number.isFinite(hover.hi)) {
    const plus = hover.hi - hover.value;
    const minus = hover.value - hover.lo;
    dom.readoutRange.textContent = `(+${plus.toFixed(3)} / −${minus.toFixed(3)}, 16th–84th pct.)`;
  } else {
    dom.readoutRange.textContent = "";
  }
}

function updateLinks(query) {
  dom.tableLink.href = losTableUrl(query);
  dom.jsonLink.href = losDataUrl(query);
  dom.jsonLink.setAttribute(
    "download",
    `${query.map}_l_${query.lon.toFixed(4)}_b_${query.lat.toFixed(4)}.json`,
  );
  dom.apiLink.href = "/usage#API";
}

function pushUrl(query) {
  const params = new URLSearchParams({
    lon: query.lon.toFixed(5),
    lat: query.lat.toFixed(5),
    coordsys: query.coordsys,
    mapname: query.map,
  });
  const url = `${window.location.pathname}?${params}`;
  window.history.pushState({ query }, "", url);
}

async function runQuery(query, { updateHistory = true } = {}) {
  if (state.controller) {
    state.controller.abort();
  }
  const controller = new AbortController();
  state.controller = controller;
  setBusy(true);

  try {
    const data = await fetchLosData(query, { signal: controller.signal });
    state.lastData = data;

    dom.results.classList.remove("d-none");
    dom.plotCaption.textContent =
      `Map: ${data.map} · ℓ = ${data.l.toFixed(2)}°, b = ${data.b.toFixed(2)}°` +
      (data.has_samples ? "" : " · mean curve (no posterior samples for this map)");
    dom.stampsUnits.textContent = data.units ? `(${data.units})` : "";

    dom.convergence.classList.toggle("d-none", data.converged !== false);

    // The single curve is the map's best fit where it has one, and its mean
    // otherwise; a posterior alone does not tell us which.
    const modes = (state.mapMetadata[data.map] || {}).modes || [];
    state.plot = renderPlot(dom.plotSvg, data, {
      units: data.units,
      seriesLabel: modes.includes("best") ? "Best fit" : "Mean",
      onHover: updateReadout,
    });
    updateReadout(null);

    if (data.images_available) {
      dom.stampsSection.classList.remove("d-none");
      dom.stampsUnavailable.classList.add("d-none");
      renderStamps(dom.stamps, data, {
        onPick: ({ l, b }) => {
          const picked = { ...query, coordsys: "gal", lon: l, lat: b };
          setInputs(picked);
          runQuery(picked);
        },
      });
    } else {
      dom.stamps.innerHTML = "";
      dom.stampsUnavailable.classList.remove("d-none");
      dom.stampsSection.classList.remove("d-none");
    }

    updateLinks(query);
    if (updateHistory) {
      pushUrl(query);
    }
    clearError();
  } catch (err) {
    if (err.name === "AbortError") {
      return;
    }
    if (err instanceof ApiError && err.status === 429) {
      const wait = (err.payload && err.payload.retry_after) || 60;
      showError(
        "Rate limit reached",
        `${err.message} Try again in about ${wait} seconds, or query fewer directions.`,
      );
    } else if (err instanceof ApiError) {
      showError("Query failed", err.message);
    } else {
      showError("Query failed", String(err));
    }
    dom.results.classList.add("d-none");
  } finally {
    if (state.controller === controller) {
      state.controller = null;
    }
    setBusy(false);
  }
}

function setInputs({ lon, lat, coordsys, map }) {
  document.getElementById(coordsys === "gal" ? "coordsys-gal" : "coordsys-equ").checked = true;
  state.coordsys = coordsys;
  coordSysLabels(coordsys);
  dom.lonInput.value = Number(lon).toFixed(4);
  dom.latInput.value = Number(lat).toFixed(4);
  if (map && state.mapMetadata[map]) {
    dom.mapSelect.value = map;
    updateMapNote();
  }
}

function convertCurrentCoordinates(from, to) {
  if (from === to) {
    return;
  }
  const lon = parseAngle(dom.lonInput.value, from === "equ");
  const lat = parseAngle(dom.latInput.value, from === "equ");
  if (lon.value === null || lat.value === null) {
    return;
  }
  const converted = from === "gal" ? gal2equ(lon.value, lat.value) : equ2gal(lon.value, lat.value);
  if (to === "equ") {
    dom.lonInput.value = converted.ra.toFixed(5);
    dom.latInput.value = converted.dec.toFixed(5);
  } else {
    dom.lonInput.value = converted.l.toFixed(5);
    dom.latInput.value = converted.b.toFixed(5);
  }
}

function readUrl() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has("lon") || !params.has("lat")) {
    return null;
  }
  const coordsys = params.get("coordsys") === "equ" ? "equ" : "gal";
  const lon = parseAngle(params.get("lon"), coordsys === "equ");
  const lat = parseAngle(params.get("lat"), coordsys === "equ");
  if (lon.value === null || lat.value === null) {
    return null;
  }
  const map = params.get("mapname");
  return {
    coordsys,
    lon: lon.value,
    lat: lat.value,
    map: map && state.mapMetadata[map] ? map : dom.mapSelect.value,
  };
}

async function init() {
  state.coordsys = dom.coordSys();
  coordSysLabels(state.coordsys);

  try {
    state.mapMetadata = await fetchMapMetadata();
  } catch {
    state.mapMetadata = {};
  }
  updateMapNote();

  dom.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = readForm();
    if (query) {
      runQuery(query);
    }
  });

  document.querySelectorAll('input[name="coordsys"]').forEach((input) => {
    input.addEventListener("change", () => {
      const next = dom.coordSys();
      convertCurrentCoordinates(state.coordsys, next);
      state.coordsys = next;
      coordSysLabels(next);
    });
  });

  dom.mapSelect.addEventListener("change", () => {
    updateMapNote();
    const query = readForm();
    if (query && state.lastData) {
      runQuery(query);
    }
  });

  window.addEventListener("popstate", () => {
    const query = readUrl();
    if (query) {
      setInputs(query);
      runQuery(query, { updateHistory: false });
    }
  });

  const initial = readUrl();
  if (initial) {
    setInputs(initial);
    runQuery(initial, { updateHistory: false });
  }
}

init();
