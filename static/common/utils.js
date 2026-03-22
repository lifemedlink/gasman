/**
 * GASMAN – Common Utilities (FINAL)
 * --------------------------------
 * ✔ Admin / User shared
 * ✔ Session-safe
 * ✔ Map-safe
 * ✔ Production hardened
 */

/* ============================================================
   TIME
============================================================ */

function formatTime(ts) {
  if (!ts) return "-";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function diffMinutes(start, end) {
  if (!start || !end) return null;
  return Math.round((new Date(end) - new Date(start)) / 60000);
}

/* ============================================================
   GAS LOGIC
============================================================ */

function classifyGas(percent, lowLimit, highLimit) {
  if (percent == null) return "NORMAL";
  if (percent < lowLimit) return "CRITICAL";
  if (percent < highLimit) return "LOW";
  return "NORMAL";
}

function mvToPercent(mv, minMv, maxMv) {
  if (mv == null) return 0;
  if (mv <= minMv) return 0;
  if (mv >= maxMv) return 100;
  return Math.round(((mv - minMv) / (maxMv - minMv)) * 100);
}

/* ============================================================
   UI HELPERS
============================================================ */

function escapeHtml(text) {
  if (!text) return "";
  return text.toString().replace(/[&<>"']/g, m =>
    ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[m])
  );
}

/**
 * Status → CSS class (MATCHES styles.css)
 */
function badgeClass(status) {
  switch ((status || "").toUpperCase()) {
    case "CRITICAL": return "badge-critical";
    case "LOW": return "badge-low";
    case "NORMAL": return "badge-normal";

    case "COMPLETED": return "bg-success";
    case "IN_PROGRESS": return "bg-primary";
    case "ACCEPTED": return "bg-info";
    case "CANCELLED": return "bg-secondary";
    default: return "bg-secondary";
  }
}

/* ============================================================
   GEO
============================================================ */

function distanceMeters(lat1, lon1, lat2, lon2) {
  if (
    isNaN(lat1) || isNaN(lon1) ||
    isNaN(lat2) || isNaN(lon2)
  ) return Infinity;

  const R = 6371000;
  const toRad = d => d * Math.PI / 180;

  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) *
    Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) ** 2;

  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

/* ============================================================
   DEVICE HELPERS
============================================================ */

function nearestDevice(devices, lat, lng) {
  let min = Infinity;
  let nearest = null;

  devices.forEach(d => {
    if (!d.coordinates) return;

    const parts = d.coordinates.split(",");
    if (parts.length !== 2) return;

    const dLat = Number(parts[0]);
    const dLng = Number(parts[1]);

    const dist = distanceMeters(lat, lng, dLat, dLng);
    if (dist < min) {
      min = dist;
      nearest = { ...d, distance_m: dist };
    }
  });

  return nearest;
}

/* ============================================================
   NETWORK (SESSION SAFE)
============================================================ */

async function safeFetch(url, opts = {}) {
  try {
    const r = await fetch(url, {
      credentials: "include",
      ...opts
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.warn("Fetch failed:", url, e);
    return null;
  }
}

/* ============================================================
   EXPORT (GLOBAL)
============================================================ */

window.GASMAN_UTILS = {
  formatTime,
  diffMinutes,
  classifyGas,
  mvToPercent,
  escapeHtml,
  badgeClass,
  distanceMeters,
  nearestDevice,
  safeFetch
};
