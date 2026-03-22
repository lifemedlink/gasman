/**
 * USER MAP PINS – FINAL MODERN VERSION
 * -------------------------------------
 * ✔ Keeps existing SVG style
 * ✔ Keeps pulse + filling icon
 * ✔ Uses AdvancedMarkerElement
 * ✔ Cluster compatible (wrapper marker)
 * ✔ No deprecated google.maps.Marker
 * ✔ No disappearing pins
 */

let deviceMarkers = {};
//let markerCluster = null;
let AdvancedMarkerElement = null;

/* =====================================================
   PIN ICON FACTORY (UNCHANGED SVG STYLE)
===================================================== */
function createGasPinSVG(gas, classification, isFilling = false) {

  const color =
    classification === "CRITICAL" ? "#ff0000" :
    classification === "LOW"      ? "#ffbf00" :
                                   "#28a745";

  const pulse = isFilling
    ? `
      <circle cx="22" cy="22" r="18" fill="${color}" opacity="0.35">
        <animate attributeName="r"
                 from="18" to="26"
                 dur="1.2s"
                 repeatCount="indefinite" />
        <animate attributeName="opacity"
                 from="0.35" to="0"
                 dur="1.2s"
                 repeatCount="indefinite" />
      </circle>
    `
    : "";

  const fillingIcon = isFilling
    ? `
      <text x="22" y="48"
            text-anchor="middle"
            font-size="18"
            font-weight="900"
            fill="#ffffff">
        ⛽︎
      </text>
    `
    : "";

  return {
    url:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(`
        <svg width="44" height="64"
             viewBox="0 0 44 64"
             xmlns="http://www.w3.org/2000/svg">

          ${pulse}

          <path
            d="M22 0C10 0 0 10 0 22c0 16.5 22 38 22 38s22-21.5 22-38C44 10 34 0 22 0z"
            fill="${color}"
          />

          <circle cx="22" cy="22" r="13" fill="#000000"/>

          <text x="22" y="27"
                text-anchor="middle"
                font-size="11"
                font-weight="700"
                fill="#ffffff">
            ${gas}%
          </text>

          ${fillingIcon}

        </svg>
      `),
    scaledSize: new google.maps.Size(44, 64),
    anchor: new google.maps.Point(22, 64)
  };
}

/* =====================================================
   REFRESH MAP PINS
===================================================== */
async function refreshPins() {

  const map = USER_MAP.getMap();
  if (!map) return;

  if (!AdvancedMarkerElement) {
    const markerLib = await google.maps.importLibrary("marker");
    AdvancedMarkerElement = markerLib.AdvancedMarkerElement;
  }

  const res = await fetch("/user/devices/map", {
    credentials: "include"
  });

  if (!res.ok) return;

  const devices = await res.json();
  const alive = new Set();
  const clusterMarkers = [];

  devices.forEach(d => {

    if (!d.coordinates) return;

    const [lat, lng] = d.coordinates.split(",").map(Number);
    if (isNaN(lat) || isNaN(lng)) return;

    const isFilling = d.task_taken === true;

// 🔥 Show device if LOW/CRITICAL OR task is active
const shouldShow =
  d.classification === "LOW" ||
  d.classification === "CRITICAL" ||
  d.task_taken === true;

if (!shouldShow) {
  return;
}
    alive.add(d.device_id);

    const icon = createGasPinSVG(
      Math.round(d.gas_percentage ?? 0),
      d.classification,
      isFilling
    );

    let markerWrapper = deviceMarkers[d.device_id];

    /* =====================================================
       CREATE NEW MARKER
    ===================================================== */
    if (!markerWrapper) {

      const div = document.createElement("div");
      div.innerHTML = `<img src="${icon.url}" width="44" height="64"/>`;

      const advancedMarker = new AdvancedMarkerElement({
        position: { lat, lng },
        content: div,
        map
      });

      // Click handler (AdvancedMarker safe)
      div.addEventListener("click", () => {
        if (typeof window.openDeviceModal === "function") {
          window.openDeviceModal(d);
        }
      });

      // Wrapper object so clustering works
      markerWrapper = {
        advanced: advancedMarker,
        getPosition: () => advancedMarker.position,
        setMap: (m) => advancedMarker.map = m
      };

      deviceMarkers[d.device_id] = markerWrapper;

    }
    /* =====================================================
       UPDATE EXISTING MARKER
    ===================================================== */
    else {

      markerWrapper.advanced.position = { lat, lng };
      markerWrapper.advanced.content.innerHTML =
        `<img src="${icon.url}" width="44" height="64"/>`;
    }

    clusterMarkers.push(markerWrapper);
  });

  /* =====================================================
     REMOVE STALE MARKERS
  ===================================================== */
  Object.keys(deviceMarkers).forEach(id => {
    if (!alive.has(id)) {
      deviceMarkers[id].setMap(null);
      delete deviceMarkers[id];
    }
  });

  /* =====================================================
     CLUSTER REMOVED (AdvancedMarker stable mode)
  ===================================================== */

} // ✅ CLOSE refreshPins FUNCTION

// expose globally (fixes refreshPins not defined)
window.refreshPins = refreshPins;
