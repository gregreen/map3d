// Postage-stamp panels with hover readout and click-to-query.
import { stampPixelToSky } from "./coords.js";

const FOV_DEG = 15;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function formatCoord(value, isLat) {
  const suffix = isLat ? (value >= 0 ? "°" : "°") : "°";
  return `${value.toFixed(2)}${suffix}`;
}

/**
 * Render the three postage stamps.
 *
 * @param {HTMLElement} container
 * @param {object} data Response from the losdata endpoint
 * @param {{onPick?: Function}} options
 */
export function renderStamps(container, data, options = {}) {
  const { onPick = null } = options;
  container.innerHTML = "";

  const panels = [];
  for (let k = 1; k <= 3; k += 1) {
    const src = data[`image${k}`];
    if (!src) continue;
    panels.push({ label: data[`label${k}`] || `Panel ${k}`, src });
  }

  if (panels.length === 0) {
    return;
  }

  const centerL = Number(data.l);
  const centerB = Number(data.b);

  panels.forEach((panel) => {
    const column = el("div", "col-12 col-md-4");
    const card = el("div", "stamp-card");
    const frame = el("div", "stamp-frame");
    frame.tabIndex = 0;

    const img = el("img");
    img.src = panel.src;
    img.alt = `Cumulative reddening within ${FOV_DEG} degrees of the query direction at ${panel.label}`;
    img.loading = "lazy";

    const crosshair = el("div", "crosshair");

    frame.append(img, crosshair);

    const labelRow = el("div", "stamp-label");
    const coords = el("span", "stamp-coords", "");
    labelRow.append(el("span", null, panel.label), coords);

    card.append(frame, labelRow);
    column.append(card);
    container.append(column);

    const update = (event) => {
      const rect = frame.getBoundingClientRect();
      const u = (event.clientX - rect.left) / rect.width;
      const v = (event.clientY - rect.top) / rect.height;
      if (u < 0 || u > 1 || v < 0 || v > 1) return { l: centerL, b: centerB };
      const sky = stampPixelToSky(u, v, centerL, centerB, FOV_DEG);
      coords.textContent = `ℓ ${formatCoord(sky.l, false)}  b ${formatCoord(sky.b, true)}`;
      return sky;
    };

    const reset = () => {
      coords.textContent = "";
    };

    frame.addEventListener("mousemove", update);
    frame.addEventListener("mouseleave", reset);
    frame.addEventListener("click", (event) => {
      const sky = update(event);
      if (onPick) onPick(sky);
    });
    frame.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (onPick) onPick({ l: centerL, b: centerB });
      }
    });
  });
}
