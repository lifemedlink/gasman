/**
 * =========================================================
 * USER MAP ROUTE ENGINE – INDUSTRIAL VERSION
 * ---------------------------------------------------------
 * ✔ Draws route driver → device
 * ✔ Redraw ONLY when driver moves >30m
 * ✔ Prevents Google API spam
 * ✔ Smooth ETA updates
 * ✔ Route lock when ON_SITE
 * ✔ Fully compatible with GASMAN system
 * =========================================================
 */

let directionsService = null;
let routePolyline = null;

let currentDestination = null;
let lastUserPosition = null;

let routeMonitorInterval = null;
let routeRequestRunning = false;


/* =========================================================
   DRAW ROUTE
========================================================= */
async function drawRoute(origin, destinationCoords) {

  if (window.routeLocked) return;

  const map = USER_MAP.getMap();
  if (!map || !origin || !destinationCoords) return;

  let lat, lng;

  /* destination format safe */
  if (typeof destinationCoords === "string") {
    [lat, lng] = destinationCoords.split(",").map(v => Number(v.trim()));
  } else {
    lat = Number(destinationCoords.lat);
    lng = Number(destinationCoords.lng);
  }

  if (isNaN(lat) || isNaN(lng)) return;

  currentDestination = { lat, lng };

  if (!directionsService) {
    directionsService = new google.maps.DirectionsService();
  }

  /* Prevent duplicate API requests */
  if (routeRequestRunning) return;
  routeRequestRunning = true;

  directionsService.route({
    origin,
    destination: currentDestination,
    travelMode: google.maps.TravelMode.DRIVING
  }, (result, status) => {

    routeRequestRunning = false;

    if (status !== "OK") {
      console.warn("Route error:", status);
      return;
    }

    const path = result.routes[0].overview_path;

    if (routePolyline) {
      routePolyline.setMap(null);
    }

    routePolyline = new google.maps.Polyline({
      path,
      strokeColor: "#0d6efd",
      strokeWeight: 5,
      map
    });

    const leg = result.routes[0].legs[0];

    updateRouteInfo(
      leg.distance.text,
      leg.duration.text
    );

  });

  if (!routeMonitorInterval) {
    startRouteMonitor();
  }

}


/* =========================================================
   ROUTE MONITOR
   Redraw only if driver moves >30m
========================================================= */
function startRouteMonitor() {

  routeMonitorInterval = setInterval(() => {

    if (window.routeLocked) return;
    if (!currentDestination) return;

    const userPos = USER_MAP.getUserPos();
    if (!userPos) return;

    if (!lastUserPosition) {
      lastUserPosition = userPos;
      return;
    }

    const distance = getDistanceMeters(
      lastUserPosition.lat,
      lastUserPosition.lng,
      userPos.lat,
      userPos.lng
    );

    if (distance > 30) {

      lastUserPosition = userPos;

      drawRoute(
        userPos,
        `${currentDestination.lat},${currentDestination.lng}`
      );

    }

  }, 2500);

}


/* =========================================================
   DISTANCE CALCULATION
========================================================= */
function getDistanceMeters(lat1, lon1, lat2, lon2) {

  const R = 6371000;
  const toRad = x => x * Math.PI / 180;

  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);

  const a =
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(toRad(lat1)) *
    Math.cos(toRad(lat2)) *
    Math.sin(dLon/2) *
    Math.sin(dLon/2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

  return R * c;

}


/* =========================================================
   CLEAR ROUTE
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
  lastUserPosition = null;

};


/* =========================================================
   UPDATE ETA
========================================================= */
function updateRouteInfo(distanceText, durationText) {

  window.currentRouteInfo = {
    distance_text: distanceText,
    duration_text: durationText
  };

  const activeEta = document.getElementById("a_eta");
  const suggestionEta = document.getElementById("t_eta");

  const text = `🚗 ${distanceText} • ⏱ ${durationText}`;

  if (activeEta) activeEta.innerHTML = text;
  if (suggestionEta) suggestionEta.innerHTML = text;

}


/* =========================================================
   EXPORT GLOBAL
========================================================= */
window.drawRoute = drawRoute;
