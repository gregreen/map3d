/*
 * Utility functions
 */

var astrocoords = (function() {
"use strict"

function deg2rad(theta) {
  return Math.PI / 180 * theta;
}

function rad2deg(theta) {
  return 180 / Math.PI * theta;
}

function hms2deg(hh, mm, ss) {
  var theta = 0.;

  if ($.isNumeric(hh)) {
    theta += hh * 15.;
  }
  if ($.isNumeric(mm)) {
    theta += mm / 4.;
  }
  if ($.isNumeric(ss)) {
    theta += ss / 240.;
  }

  return theta;
}

function dms2deg(dd, mm, ss) {
  var theta = 0.;

  if ($.isNumeric(dd)) {
    theta += dd * 1.;
  }
  if ($.isNumeric(mm)) {
    theta += mm / 60.;
  }
  if ($.isNumeric(ss)) {
    theta += ss / 3600.;
  }

  return theta;
}


/*
 * Parse angle specification
 */

function parse_angle(s, hms) {
  // Reject empty string
  if(s === "") {
    return {"val": null, "format": null};
  }

  // Try to read the angle as a number
  if($.isNumeric(s)) {
    return {"val": s, "format": "deg"};
  }

  if (hms) {
    // Try to parse as an hour angle (e.g., "10h5m3.45s" or "10:5:3.45")
    var re = /^([-]?)(?:\s*)(\d*[.]?\d*(?=[h:\s]|$))(?:[h:\s]\s*|$)(\d*[.]?\d*(?=[m:\s]|$))(?:[m:\s]\s*|$)(\d*[.]?\d*(?=[s:\s]|$))(?:[s:\s]\s*|\s*$)$/i;
    var matches = s.match(re);

    if (matches !== null) {
      var val = hms2deg(matches[2], matches[3], matches[4]);
      if (matches[1] == '-') {
        val *= -1.;
      }
      return {"val": val, "format": "hms"};
    }
  } else {
    // Try to parse as degrees - arcmin - arcsec (e.g., "15d43m15.8s")
    re = /^([-]?)(?:\s*)(\d*[.]?\d*(?=[d:\s]|$))(?:[d:\s]\s*|$)(\d*[.]?\d*(?=[m':\s]|$))(?:[m':\s]\s*|$)(\d*[.]?\d*(?=[s":\s]|''\s*|$))(?:[s":\s]\s*|''\s*|\s*$)$/i;
    var matches = s.match(re);

    if (matches !== null) {
      var val = dms2deg(matches[2], matches[3], matches[4]);
      if (matches[1] == '-') {
        val *= -1.;
      }
      return {"val": val, "format": "dms"};
    }
  }

  return {"val": null, "format": null};
}


function deg2hms(theta) {
  if (theta < 0) {
    theta = theta + 360. * math.Ceil(-theta/360.);
  }

  var hh = Math.floor(theta / 15.);
  theta = theta - 15.*hh;

  var mm = Math.floor(theta * 4.);
  theta = theta - mm/4.;

  var ss = theta * 240.;

  return {"h": parseInt(hh), "m": parseInt(mm), "s": ss};
}


/*
 * Equatorial - Galactic
 */

function equ2gal(a, d, aG, cdG, sdG, BK) {
  var Da = deg2rad(a) - aG;
  var dr = deg2rad(d);

  var cd = Math.cos(dr);
  var sd = Math.sin(dr);
  var b = Math.asin(sd*sdG + cd*cdG * Math.cos(Da));

  var inv_cb = 1. / Math.cos(b);

  var sDl = cd * Math.sin(Da) * inv_cb;
  var cDl = (sd*cdG - cd*sdG * Math.cos(Da)) * inv_cb;
  var l = BK - Math.atan2(sDl, cDl);

  l = rad2deg(l);
  b = rad2deg(b);

  if (l > 360) {
    l -= 360;
  } else if (l < 0) {
    l += 360;
  }

  return {"l": l, "b": b};
}

function gal2equ(l, b, aG, cdG, sdG, BK) {
  var br = deg2rad(b);
  var Dl = BK - deg2rad(l);

  var cb = Math.cos(br);
  var sb = Math.sin(br);

  var d = Math.asin(sdG*sb + cdG*cb * Math.cos(Dl));

  var inv_cd = Math.cos(d);

  var sDa = cb * Math.sin(Dl) * inv_cd;
  var cDa = (sb*cdG - cb*sdG * Math.cos(Dl))*inv_cd;
  var a = Math.atan2(sDa, cDa) + aG;

  a = rad2deg(a);
  d = rad2deg(d);

  if (a > 360) {
    a -= 360;
  } else if (a < 0) {
    a += 360;
  }

  return {"a": a, "d": d};
}


// J2000 - Galactic conversion constants
var aG_J2000 = deg2rad(192.85948);
var dG_J2000 = deg2rad(27.12825);

var aB_J2000 = deg2rad(266.4051);
var dB_J2000 = deg2rad(-28.9362);

//lOmega_J2000 = deg2rad(32.93192);

var cdG_J2000 = Math.cos(dG_J2000);
var sdG_J2000 = Math.sin(dG_J2000);

var BK_J2000 = Math.acos( Math.sin(dB_J2000) * cdG_J2000 - Math.cos(dB_J2000) * sdG_J2000 * Math.cos(aG_J2000 - aB_J2000) );

//console.log("BK = " + rad2deg(BK_J2000));

function equ2gal_J2000(a, d) {
  return equ2gal(a, d, aG_J2000, cdG_J2000, sdG_J2000, BK_J2000);
}

function gal2equ_J2000(l, b) {
  return gal2equ(l, b, aG_J2000, cdG_J2000, sdG_J2000, BK_J2000);
}

// Projections

// Gnomonic projection
function proj_gnomonic(lon, lat, lon0, cos_lat0, sin_lat0) {
  var cos_lat = Math.cos(lat);
  var sin_lat = Math.sin(lat);

  var cos_Dlon = Math.cos(lon - lon0);
  var sin_Dlon = Math.sin(lon - lon0);

  var a = 1. / (sin_lat0 * sin_lat + cos_lat0 * cos_lat * cos_Dlon);

  var x = a * cos_lat * sin_Dlon;
  var y = a * (cos_lat0 * sin_lat - sin_lat0 * cos_lat * cos_Dlon);

  return {"x": x, "y": y};
}

// Inverse Gnomonic projection
function proj_gnomonic_inv(x, y, lon0, cos_lat0, sin_lat0) {
  var rho = Math.sqrt(x*x + y*y);
  var c = Math.atan(rho);

  var cos_c = Math.cos(c);
  var sin_c = Math.sin(c);

  var lat = Math.asin(
    cos_c * sin_lat0 + y * sin_c * cos_lat0 / rho
  );
  var lon = lon0 + Math.atan2(
    (x * sin_c),
    (rho * cos_lat0 * cos_c - y * sin_lat0 * sin_c)
  );

  if (lon > 2*Math.PI) {
    lon -= 2*Math.PI;
  } else if (lon < 0) {
    lon += 2*Math.PI;
  }

  return {"lon": lon, "lat": lat};
}

// Expose some functions to the outside under
// the namespace "astrocoords"
var namespace = {
  "deg2rad": deg2rad,
  "rad2deg": rad2deg,
  "deg2hms": deg2hms,
  "parse_angle": parse_angle,
  "gal2equ_J2000": gal2equ_J2000,
  "equ2gal_J2000": equ2gal_J2000,
  "proj_gnomonic": proj_gnomonic,
  "proj_gnomonic_inv": proj_gnomonic_inv
};

return namespace;
})();
