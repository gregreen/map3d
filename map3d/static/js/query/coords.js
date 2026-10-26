// Coordinate parsing and spherical helpers (no dependencies).
const DEG = Math.PI / 180;
const RAD = 180 / Math.PI;

export { DEG, RAD };

export function deg2rad(theta) {
  return theta * DEG;
}

export function rad2deg(theta) {
  return theta * RAD;
}

export function wrap360(theta) {
  return ((theta % 360) + 360) % 360;
}

function isNumeric(text) {
  return text !== "" && Number.isFinite(Number(text));
}

/**
 * Parse an angle written as decimal degrees, "12h34m56s", or "12d34m56s".
 * Returns {value, format}, with value === null when the text is not an angle.
 */
export function parseAngle(text, allowHms) {
  const raw = (text || "").trim();
  if (raw === "") {
    return { value: null, format: null };
  }
  if (isNumeric(raw)) {
    return { value: Number(raw), format: "deg" };
  }

  const re = allowHms
    ? /^([-+]?)\s*(\d*\.?\d*)[h:\s]\s*(\d*\.?\d*)[m:\s]\s*(\d*\.?\d*)[s"]?\s*$/i
    : /^([-+]?)\s*(\d*\.?\d*)[d:\s]\s*(\d*\.?\d*)[m':\s]\s*(\d*\.?\d*)[s"]?\s*$/i;

  const match = raw.match(re);
  if (!match) {
    return { value: null, format: null };
  }

  const sign = match[1] === "-" ? -1 : 1;
  const whole = Number(match[2] || 0);
  const minutes = Number(match[3] || 0);
  const seconds = Number(match[4] || 0);
  const scale = allowHms ? 15 : 1; // hours -> degrees for right ascension

  const value = sign * (whole * scale + (minutes * scale) / 60 + (seconds * scale) / 3600);
  return { value, format: allowHms ? "hms" : "dms" };
}

export function formatSexagesimal(value, asHours) {
  const scale = asHours ? 1 / 15 : 1;
  let theta = value * scale;
  const sign = theta < 0 ? "-" : "+";
  theta = Math.abs(theta);
  const whole = Math.floor(theta);
  const minutes = Math.floor((theta - whole) * 60);
  const seconds = ((theta - whole) * 60 - minutes) * 60;
  return `${sign}${whole}°${String(minutes).padStart(2, "0")}′${seconds
    .toFixed(1)
    .padStart(4, "0")}″`;
}

// J2000 equatorial <-> galactic (same constants as astropy)
const RA_NGP = deg2rad(192.85948);
const DEC_NGP = deg2rad(27.12825);
const LON_NCP = deg2rad(122.93192);

export function equ2gal(ra, dec) {
  const a = deg2rad(ra);
  const d = deg2rad(dec);

  const sd = Math.sin(d);
  const cd = Math.cos(d);
  const sdp = Math.sin(DEC_NGP);
  const cdp = Math.cos(DEC_NGP);
  const da = a - RA_NGP;

  const b = Math.asin(sd * sdp + cd * cdp * Math.cos(da));
  const y = cd * Math.sin(da);
  const x = sd * cdp - cd * sdp * Math.cos(da);
  const l = LON_NCP - Math.atan2(y, x);

  return { l: wrap360(rad2deg(l)), b: rad2deg(b) };
}

export function gal2equ(l, b) {
  const lr = deg2rad(l);
  const br = deg2rad(b);

  const sb = Math.sin(br);
  const cb = Math.cos(br);
  const sdp = Math.sin(DEC_NGP);
  const cdp = Math.cos(DEC_NGP);
  const dl = LON_NCP - lr;

  const dec = Math.asin(sb * sdp + cb * cdp * Math.cos(dl));
  const y = cb * Math.sin(dl);
  const x = sb * cdp - cb * sdp * Math.cos(dl);
  const ra = RA_NGP + Math.atan2(y, x);

  return { ra: wrap360(rad2deg(ra)), dec: rad2deg(dec) };
}

/**
 * Convert a normalized position in a gnomonic stamp image to (l, b) in degrees.
 * The stamps are 15-degree-wide gnomonic projections centered on the query
 * direction; longitude decreases to the right in the rendered image.
 */
export function stampPixelToSky(u, v, l0, b0, fovDeg) {
  const half = Math.tan(deg2rad(fovDeg) / 2);
  const x = -(u - 0.5) * 2 * half;
  const y = (0.5 - v) * 2 * half;

  const rho = Math.hypot(x, y);
  const lat0 = deg2rad(b0);
  const lon0 = deg2rad(l0);

  if (rho < 1e-12) {
    return { l: l0, b: b0 };
  }

  const c = Math.atan(rho);
  const cosC = Math.cos(c);
  const sinC = Math.sin(c);

  const lat = Math.asin(cosC * Math.sin(lat0) + (y * sinC * Math.cos(lat0)) / rho);
  const lon =
    lon0 +
    Math.atan2(x * sinC, rho * Math.cos(lat0) * cosC - y * Math.sin(lat0) * sinC);

  return { l: wrap360(rad2deg(lon)), b: rad2deg(lat) };
}
