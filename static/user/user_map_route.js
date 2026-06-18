/**
 * =========================================================
 * USER MAP LIVE LINE ENGINE
 * ---------------------------------------------------------
 * ✔ Draws straight line driver → device
 * ✔ Live updates every second
 * ✔ No Google Directions API
 * ✔ No polyline recreation
 * ✔ Smooth tracking
 * ✔ Route lock when ON_SITE
 * ✔ Fully compatible with GASMAN
 * =========================================================
 */

let routePolyline = null;

let currentDestination = null;
let routeMonitorInterval = null;


/* =========================================================
   DRAW / UPDATE LINE
========================================================= */
async function drawRoute(origin, destinationCoords) {

  if (window.routeLocked) return;

  const map = USER_MAP.getMap();
  if (!map || !origin || !destinationCoords) return;

  let lat, lng;

  if (typeof destinationCoords === "string") {

    [lat, lng] = destinationCoords
      .split(",")
      .map(v => Number(v.trim()));

  } else {

    lat = Number(destinationCoords.lat);
    lng = Number(destinationCoords.lng);

  }

  if (isNaN(lat) || isNaN(lng)) return;

  currentDestination = { lat, lng };

  const linePath = [
    {
      lat: Number(origin.lat),
      lng: Number(origin.lng)
    },
    {
      lat,
      lng
    }
  ];

  /* Create once */
  if (!routePolyline) {

    routePolyline = new google.maps.Polyline({
      path: linePath,
      geodesic: true,
      strokeColor: "#0d6efd",
      strokeOpacity: 1,
      strokeWeight: 5,
      clickable: false,
      map
    });

  } else {

    /* Update existing line */
    routePolyline.setPath(linePath);

  }

  /* Update distance */
  const distanceMeters = getDistanceMeters(
    origin.lat,
    origin.lng,
    lat,
    lng
  );

  let distanceText;

  if (distanceMeters >= 1000) {

    distanceText =
      (distanceMeters / 1000).toFixed(2) + " km";

  } else {

    distanceText =
      Math.round(distanceMeters) + " m";

  }

  updateRouteInfo(distanceText);

  if (!routeMonitorInterval) {
    startRouteMonitor();
  }

}


/* =========================================================
   LIVE MONITOR
========================================================= */
function startRouteMonitor() {

  routeMonitorInterval = setInterval(() => {

    if (window.routeLocked) return;

    if (!currentDestination) return;

    const userPos = USER_MAP.getUserPos();

    if (!userPos) return;

    drawRoute(
      userPos,
      currentDestination
    );

  }, 1000);

}


/* =========================================================
   DISTANCE CALCULATION
========================================================= */
function getDistanceMeters(
  lat1,
  lon1,
  lat2,
  lon2
) {

  const R = 6371000;

  const toRad = deg =>
    deg * Math.PI / 180;

  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);

  const a =
    Math.sin(dLat / 2) *
      Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) *
      Math.sin(dLon / 2);

  const c =
    2 *
    Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a)
    );

  return R * c;

}


/* =========================================================
   CLEAR LINE
========================================================= */
window.clearRoute = function () {

  if (routeMonitorInterval) {

    clearInterval(routeMonitorInterval);

    routeMonitorInterval = null;

  }

  if (routePolyline) {

    routePolyline.setMap(null);

    routePolyline = null;

  }

  currentDestination = null;

};


/* =========================================================
   UPDATE ETA / DISTANCE
========================================================= */
function updateRouteInfo(distanceText) {

  window.currentRouteInfo = {
    distance_text: distanceText,
    duration_text: "--"
  };

  const activeEta =
    document.getElementById("a_eta");

  const suggestionEta =
    document.getElementById("t_eta");

  const text = distanceText;

  if (activeEta) {
    activeEta.innerHTML = text;
  }

  if (suggestionEta) {
    suggestionEta.innerHTML = text;
  }

}


/* =========================================================
   OPTIONAL: LOCK ROUTE
========================================================= */
window.lockRoute = function () {

  window.routeLocked = true;

};


/* =========================================================
   OPTIONAL: UNLOCK ROUTE
========================================================= */
window.unlockRoute = function () {

  window.routeLocked = false;

};


/* =========================================================
   EXPORT
========================================================= */
window.drawRoute = drawRoute;
