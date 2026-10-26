// Thin wrapper around the interactive API.

export class ApiError extends Error {
  constructor(message, { status = 0, payload = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function requestJson(url, { signal } = {}) {
  let response;
  try {
    response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") {
      throw err;
    }
    throw new ApiError("Could not reach the server. Check your connection and try again.");
  }

  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message =
      (payload && (payload.error || payload.message)) ||
      `Query failed (HTTP ${response.status}).`;
    throw new ApiError(message, { status: response.status, payload });
  }

  return payload;
}

function params({ lon, lat, coordsys }) {
  return new URLSearchParams({
    lon: String(lon),
    lat: String(lat),
    coordsys,
  });
}

export function losDataUrl({ map, ...rest }) {
  return `/api/v2/interactive/${encodeURIComponent(map)}/losdata?${params(rest)}`;
}

export function losTableUrl({ map, ...rest }) {
  return `/api/v2/interactive/${encodeURIComponent(map)}/lostable?${params(rest)}`;
}

export function fetchLosData(query, options) {
  return requestJson(losDataUrl(query), options);
}

export async function fetchMapMetadata() {
  const payload = await requestJson("/api/v2/maps");
  return payload.maps || {};
}
