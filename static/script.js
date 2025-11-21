/************************************************************
 * GASMAN — CLEAN FINAL SCRIPT.JS
 * ----------------------------------------------------------
 * ✓ Device panel removed
 * ✓ Only top-center Start/Stop navigation buttons
 * ✓ Auto-center map on user GPS at login
 * ✓ No floating stop button
 ************************************************************/

/********************************************************************
 * GLOBALS
 ********************************************************************/
let map;
let markers = {};
let devicesCache = [];

let directionsService, directionsRenderer;

let userOverlay = null;
let userPos = null;
let accuracyMeters = 0;
let headingDeg = 0;

let navigating = false;
let navTargetDeviceId = null;
let navAutoRerouteTimer = null;

let fetchTimer = null;

let speakEnabled = true;
let lastInstruction = "";
let lastStepIndex = -1;

/********************************************************************
 * MAIN INIT (CALLED BY home.html CALLBACK)
 ********************************************************************/
window._initMapImpl = function () {

    map = new google.maps.Map(document.getElementById("map"), {
        center: { lat: 12.9716, lng: 77.5946 }, // TEMP until GPS loads
        zoom: 14,
        fullscreenControl: false,
        streetViewControl: false,
        mapTypeControl: false,
        gestureHandling: "greedy"
    });

    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer({
        suppressMarkers: true,
        preserveViewport: true,
        polylineOptions: { strokeWeight: 5, strokeColor: "#1a73e8" }
    });
    directionsRenderer.setMap(map);

    createMapControls();
    createUserOverlay();
    getUserLocation();   // ← Auto-center added here
    fetchAndSchedule();

    console.log("✔ GASMAN map initialized");
};

/********************************************************************
 * MAP CONTROLS  (TOP CENTER + RIGHT)
 ********************************************************************/
function createMapControls() {
    const topCenter = document.createElement("div");
    topCenter.className = "gm-topcenter";

    const startBtn = document.createElement("button");
    startBtn.id = "startNavBtn";
    startBtn.className = "gm-btn gm-btn-primary";
    startBtn.innerHTML = "🚀 Start Navigation";

    const stopBtn = document.createElement("button");
    stopBtn.id = "stopNavBtn";
    stopBtn.className = "gm-btn gm-btn-danger";
    stopBtn.innerHTML = "✋ Stop Navigation";
    stopBtn.style.display = "none";

    startBtn.onclick = () => {
        startBtn.style.display = "none";
        stopBtn.style.display = "inline-block";
        startNavigationToNearest();
    };

    stopBtn.onclick = () => {
        stopNavigation();
        stopBtn.style.display = "none";
        startBtn.style.display = "inline-block";
    };

    topCenter.appendChild(startBtn);
    topCenter.appendChild(stopBtn);
    map.controls[google.maps.ControlPosition.TOP_CENTER].push(topCenter);

    // Right controls (NO STOP BUTTON HERE ANYMORE)
    const right = document.createElement("div");
    right.className = "gm-right-controls";

    const recenter = document.createElement("div");
    recenter.className = "gm-circle-button";
    recenter.innerHTML = `<i class="fa fa-location-arrow"></i>`;
    recenter.onclick = () => userPos && map.panTo(userPos);

    const trafficBtn = document.createElement("div");
    trafficBtn.className = "gm-circle-button";
    trafficBtn.innerHTML = `<i class="fa fa-traffic-light"></i>`;
    let trafficLayer = null;

    trafficBtn.onclick = () => {
        if (trafficLayer) {
            trafficLayer.setMap(null);
            trafficLayer = null;
        } else {
            trafficLayer = new google.maps.TrafficLayer();
            trafficLayer.setMap(map);
        }
    };

    right.appendChild(recenter);
    right.appendChild(trafficBtn);

    map.controls[google.maps.ControlPosition.TOP_RIGHT].push(right);
}

/********************************************************************
 * BLUE DOT OVERLAY
 ********************************************************************/
function createUserOverlay() {
    const dot = document.createElement("div");
    dot.className = "gm-blue-dot";
    dot.innerHTML = `
        <div class="gm-accuracy"></div>
        <div class="gm-dot"></div>
        <div class="gm-arrow"></div>
    `;

    userOverlay = new google.maps.OverlayView();
    userOverlay.onAdd = function () {
        this.getPanes().overlayMouseTarget.appendChild(dot);
    };

    userOverlay.draw = function () {
        if (!userPos) {
            dot.style.display = "none";
            return;
        }

        const proj = this.getProjection();
        if (!proj) return;

        const px = proj.fromLatLngToDivPixel(
            new google.maps.LatLng(userPos.lat, userPos.lng)
        );

        dot.style.display = "block";
        dot.style.left = (px.x - 24) + "px";
        dot.style.top = (px.y - 24) + "px";

        if (accuracyMeters) {
            const edge = google.maps.geometry.spherical.computeOffset(
                new google.maps.LatLng(userPos.lat, userPos.lng),
                accuracyMeters, 90
            );
            const p2 = proj.fromLatLngToDivPixel(edge);
            const rad = Math.abs(p2.x - px.x);

            const acc = dot.querySelector(".gm-accuracy");
            acc.style.width = rad * 2 + "px";
            acc.style.height = rad * 2 + "px";
            acc.style.left = (24 - rad) + "px";
            acc.style.top = (24 - rad) + "px";
        }

        const arrow = dot.querySelector(".gm-arrow");
        arrow.style.opacity = navigating ? 1 : 0;
        arrow.style.transform = `rotate(${headingDeg}deg)`;
    };

    userOverlay.setMap(map);
}

/********************************************************************
 * GPS + AUTO-CENTER + DEVICE ORIENTATION
 ********************************************************************/
function getUserLocation() {
    // CENTER MAP IMMEDIATELY ON USER
    navigator.geolocation.getCurrentPosition(pos => {
        userPos = {
            lat: pos.coords.latitude,
            lng: pos.coords.longitude
        };
        accuracyMeters = pos.coords.accuracy;

        map.setCenter(userPos);     // ← Auto-center on login
        if (userOverlay) userOverlay.draw();

    }, console.warn, { enableHighAccuracy: true });

    // Continuous tracking
    navigator.geolocation.watchPosition(pos => {
        userPos = {
            lat: pos.coords.latitude,
            lng: pos.coords.longitude
        };
        accuracyMeters = pos.coords.accuracy;

        if (userOverlay) userOverlay.draw();
    }, console.warn, { enableHighAccuracy: true });

    if (window.DeviceOrientationEvent) {
        window.addEventListener("deviceorientation", e => {
            if (e.alpha != null) headingDeg = 360 - e.alpha;
        });
    }
}

/********************************************************************
 * FETCH + POLLING
 ********************************************************************/
function fetchAndSchedule() {
    if (fetchTimer) clearInterval(fetchTimer);
    fetchLocations();
    fetchTimer = setInterval(fetchLocations, 1000);
}

function fetchLocations() {
    fetch("/get_locations")
        .then(r => r.json())
        .then(data => {
            devicesCache = data || [];
            syncMarkers(data);
            if (navigating) scheduleAutoReroute();
        });
}

/********************************************************************
 * MAP MARKERS
 ********************************************************************/
function markerIcon() {
    return {
        url: "https://maps.google.com/mapfiles/ms/icons/red-dot.png",
        scaledSize: new google.maps.Size(38, 38)
    };
}

function syncMarkers(list) {
    const active = new Set();

    list.forEach(d => {
        if (!d.coordinates) return;

        const [lat, lng] = d.coordinates.split(",").map(Number);
        const id = d.device_id;

        active.add(id);

        if (!markers[id]) {
            markers[id] = new google.maps.Marker({
                map,
                position: { lat, lng },
                icon: markerIcon(),
                title: `Low Gas - ${id}`
            });
        } else {
            markers[id].setPosition({ lat, lng });
        }
    });

    Object.keys(markers).forEach(id => {
        if (!active.has(id)) {
            markers[id].setMap(null);
            delete markers[id];
        }
    });
}

/********************************************************************
 * DEVICE MODAL
 ********************************************************************/
function showDeviceModal(id) {
    const d = devicesCache.find(x => x.device_id == id);
    if (!d) return;

    const modalBody = document.getElementById("deviceDetailModalBody");
    const modalTitle = document.getElementById("deviceDetailModalLabel");

    modalTitle.innerText = `Device ${id}`;

    modalBody.innerHTML = `
        <table class="table">
            <tr><th>Device ID</th><td>${d.device_id}</td></tr>
            <tr><th>Gas %</th><td>${d.gas_percentage}</td></tr>
            <tr><th>Threshold %</th><td>${d.threshold_percent}</td></tr>
            <tr><th>Customer</th><td>${d.customer_name}</td></tr>
            <tr><th>Location</th><td>${d.device_location}</td></tr>
            <tr><th>Coordinates</th><td>${d.coordinates}</td></tr>
            <tr><th>Last Log</th><td>${d.last_log_time}</td></tr>
        </table>
    `;

    new bootstrap.Modal(document.getElementById("deviceDetailModal")).show();
}

/********************************************************************
 * NAVIGATION ENGINE
 ********************************************************************/
function startNavigationToNearest() {
    if (!userPos) return alert("Waiting for GPS…");
    if (!devicesCache.length) return alert("No low-gas devices.");

    let best = null;
    let bestDist = Infinity;

    devicesCache.forEach(d => {
        const [lat, lng] = d.coordinates.split(",").map(Number);

        const dist = google.maps.geometry.spherical.computeDistanceBetween(
            new google.maps.LatLng(userPos.lat, userPos.lng),
            new google.maps.LatLng(lat, lng)
        );

        if (dist < bestDist) {
            bestDist = dist;
            best = d;
        }
    });

    if (!best) return;

    navTargetDeviceId = best.device_id;
    navigating = true;
    calculateRoute();
}

function stopNavigation() {
    navigating = false;
    navTargetDeviceId = null;
    directionsRenderer.set("directions", null);

    const banner = document.getElementById("navBanner");
    if (banner) banner.style.display = "none";

    lastInstruction = "";
    lastStepIndex = -1;
}

function scheduleAutoReroute() {
    if (navAutoRerouteTimer) clearTimeout(navAutoRerouteTimer);
    navAutoRerouteTimer = setTimeout(() => {
        if (navigating) calculateRoute();
    }, 2000);
}

function calculateRoute() {
    const t = devicesCache.find(d => d.device_id === navTargetDeviceId);
    if (!t) return;

    const [lat, lng] = t.coordinates.split(",").map(Number);

    const req = {
        origin: new google.maps.LatLng(userPos.lat, userPos.lng),
        destination: new google.maps.LatLng(lat, lng),
        travelMode: google.maps.TravelMode.DRIVING
    };

    directionsService.route(req, (res, status) => {
        if (status === "OK") {
            directionsRenderer.setDirections(res);
            updateBanner(res);
        }
    });
}

/********************************************************************
 * TURN-BY-TURN BANNER + TTS
 ********************************************************************/
function updateBanner(result) {
    if (!result.routes.length) return;

    const leg = result.routes[0].legs[0];
    const steps = leg.steps;

    if (!steps.length) return;

    let nearest = 0;
    let minDist = Infinity;

    const user = new google.maps.LatLng(userPos.lat, userPos.lng);

    steps.forEach((step, i) => {
        const dist =
            google.maps.geometry.spherical.computeDistanceBetween(
                user,
                step.start_location
            );

        if (dist < minDist) {
            minDist = dist;
            nearest = i;
        }
    });

    if (nearest === lastStepIndex) return;
    lastStepIndex = nearest;

    const step = steps[nearest];

    const text = step.instructions.replace(/<[^>]+>/g, "");
    const icon = turnIcon(step.maneuver);
    const distTxt = step.distance.text;
    const totalDist = leg.distance.text;
    const totalTime = leg.duration.text;

    const banner = document.getElementById("navBanner");
    banner.style.display = "block";

    document.getElementById("navTurnIcon").innerText = icon;
    document.getElementById("navTextMain").innerText = text;
    document.getElementById("navTextSub").innerText =
        `${distTxt} • ${totalDist} • ${totalTime}`;

    if (speakEnabled && text !== lastInstruction) {
        speak(text);
        lastInstruction = text;
    }
}

function turnIcon(m) {
    if (!m) return "⬆";

    m = m.toLowerCase();

    if (m.includes("right")) return "➡";
    if (m.includes("left")) return "⬅";
    if (m.includes("uturn")) return "⟲";
    if (m.includes("slight right")) return "↗";
    if (m.includes("slight left")) return "↖";
    if (m.includes("sharp right")) return "⤳";
    if (m.includes("sharp left")) return "⤶";

    return "⬆";
}

function speak(text) {
    try {
        const msg = new SpeechSynthesisUtterance(text);
        msg.lang = "en-IN";
        window.speechSynthesis.speak(msg);
    } catch {}
}

/********************************************************************
 * CLEANUP
 ********************************************************************/
window.addEventListener("beforeunload", () => {
    if (fetchTimer) clearInterval(fetchTimer);
});
