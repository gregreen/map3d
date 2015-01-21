/*
 * Utility functions
 */

function deg2rad(theta) {
  return Math.PI / 180 * theta;
}

function rad2deg(theta) {
  return 180 / Math.PI * theta;
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
aG_J2000 = deg2rad(192.85948);
dG_J2000 = deg2rad(27.12825);

aB_J2000 = deg2rad(266.4051);
dB_J2000 = deg2rad(-28.9362);

//lOmega_J2000 = deg2rad(32.93192);

cdG_J2000 = Math.cos(dG_J2000);
sdG_J2000 = Math.sin(dG_J2000);

BK_J2000 = Math.acos( Math.sin(dB_J2000) * cdG_J2000 - Math.cos(dB_J2000) * sdG_J2000 * Math.cos(aG_J2000 - aB_J2000) );

//console.log("BK = " + rad2deg(BK_J2000));

function equ2gal_J2000(a, d) {
  return equ2gal(a, d, aG_J2000, cdG_J2000, sdG_J2000, BK_J2000);
}

function gal2equ_J2000(l, b) {
  return gal2equ(l, b, aG_J2000, cdG_J2000, sdG_J2000, BK_J2000);
}
