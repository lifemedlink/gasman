/*
USER MAP CORE – FINAL NAVIGATION VERSION (WITH TRAFFIC)
-------------------------------------------------------

✔ Stable GPS tracking
✔ Smooth driver marker animation
✔ Auto follow camera
✔ Navigation style map rotation
✔ Dynamic zoom based on speed
✔ Traffic layer (Google Maps style)
✔ Navigation camera offset (see more road ahead)
✔ Stops follow if user drags map
✔ Recenter button re-enables follow
✔ Safe backend GPS ping
✔ Chrome sleep prevention
✔ First GPS fix centers map automatically
*/

let map = null;
let userMarker = null;
let lastUserPos = null;
let lastPingTime = 0;

let gpsWatcher = null;
let markerAnimation = null;

/* Navigation camera controls */
let followDriver = false;

/* Navigation camera offset */
const NAV_OFFSET = 0.35;

/* First GPS fix detection */
let firstFix = false;

/* =====================================================
GLOBAL MAP API
===================================================== */

window.USER_MAP = {
getMap: () => map,
getUserPos: () => lastUserPos
};

/* =====================================================
INIT MAP
===================================================== */

window.initUserMap = async function () {

map = new google.maps.Map(document.getElementById("userMap"), {

center: { lat: 12.9716, lng: 77.5946 },
zoom: 13,
mapId: "DEMO_MAP_ID",

heading: 0,
tilt: 60,

streetViewControl: false,
mapTypeControl: false,
fullscreenControl: false,
zoomControl: true,
clickableIcons: false

});

/* Traffic layer */

const trafficLayer = new google.maps.TrafficLayer();
trafficLayer.setMap(map);

/* Stop follow if user drags map */

map.addListener("dragstart", () => {
followDriver = false;
});

map.addListener("zoom_changed", () => {
followDriver = false;
});

trackUser();

/* Prevent device sleep */

if ("wakeLock" in navigator) {
try {
navigator.wakeLock.request("screen");
} catch(e){}
}

await loadTaskToggle();

/* Wait until GPS ready */

const waitForGPS = setInterval(() => {

if (!map || !lastUserPos) return;

refreshPins();

clearInterval(waitForGPS);

setInterval(() => {
  refreshPins();
}, 5000);
}, 300);

};

/* =====================================================
USER LOCATION TRACKING
===================================================== */

function trackUser() {

if (!navigator.geolocation) return;

if (gpsWatcher) return;

gpsWatcher = navigator.geolocation.watchPosition(

pos => {

  const newPos = {
    lat: pos.coords.latitude,
    lng: pos.coords.longitude
  };

  lastUserPos = newPos;


  /* First GPS fix */

  if (!firstFix) {

  //  map.setCenter(newPos);
   // map.setZoom(18);

    followDriver = true;
    firstFix = true;

  }


  /* Map rotation */

  const heading = pos.coords.heading;

  if (followDriver && heading !== null && !isNaN(heading)) {

    const currentHeading = map.getHeading() || 0;

    const smoothHeading =
      currentHeading + (heading - currentHeading) * 0.12;

    map.setHeading(smoothHeading);

  }


  /* Dynamic zoom */

const speed = pos.coords.speed || 0;

/* Better zoom levels for navigation */

/*if (speed > 20) {
  map.setZoom(15);
}
else if (speed > 10) {
  map.setZoom(16);
}
else if (speed > 3) {
  map.setZoom(17);
}
else {
  map.setZoom(17);
}*/

  /* GPS ping to backend */

  const now = Date.now();

  if (now - lastPingTime > 4000) {

    lastPingTime = now;

    fetch("/user/task/gps-ping", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newPos)
    }).catch(()=>{});

  }


  /* User marker */

  if (!userMarker) {

    userMarker = new google.maps.Marker({
      map,
      position: newPos,
      zIndex: 9999,
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 7,
        fillColor: "#1a73e8",
        fillOpacity: 1,
        strokeColor: "#ffffff",
        strokeWeight: 2
      }
    });

  } else {

    animateMarker(newPos);

  }


  /* Follow camera */

  if (followDriver) {

    const projection = map.getProjection();

    if (projection) {

      const scale = Math.pow(2, map.getZoom());

      const worldPoint =
        projection.fromLatLngToPoint(
          new google.maps.LatLng(newPos.lat, newPos.lng)
        );

      const pixelOffsetY =
        window.innerHeight * NAV_OFFSET / scale;

      const offsetPoint =
        new google.maps.Point(
          worldPoint.x,
          worldPoint.y - pixelOffsetY
        );

      const offsetLatLng =
        projection.fromPointToLatLng(offsetPoint);

      map.panTo(offsetLatLng);

    } else {

      map.panTo(newPos);

    }

  }

},

err => {
  console.warn("GPS error:", err);
},

{
  enableHighAccuracy: true,
  maximumAge: 5000,
  timeout: 10000
}

);

}

/* =====================================================
SMOOTH MARKER ANIMATION
===================================================== */

function animateMarker(newPos) {

if (!userMarker) return;

const start = userMarker.getPosition();

if (!start) {
userMarker.setPosition(newPos);
return;
}

const startLat = start.lat();
const startLng = start.lng();

const endLat = newPos.lat;
const endLng = newPos.lng;

const frames = 30;
const duration = 800;
const interval = duration / frames;

let step = 0;

clearInterval(markerAnimation);

markerAnimation = setInterval(()=>{

step++;

const progress = step / frames;

const lat = startLat + (endLat - startLat) * progress;
const lng = startLng + (endLng - startLng) * progress;

userMarker.setPosition({lat,lng});

if(step >= frames){

  clearInterval(markerAnimation);
  userMarker.setPosition(newPos);

}
}, interval);

}

/* =====================================================
RECENTER BUTTON
===================================================== */

document.addEventListener("DOMContentLoaded",()=>{

const btn = document.getElementById("btnRecenter");

if(!btn) return;

btn.addEventListener("click",()=>{

if(map && lastUserPos){

  followDriver = true;

  map.panTo(lastUserPos);
  map.setZoom(16);

  btn.style.transform = "scale(0.92)";

  setTimeout(()=>{
    btn.style.transform = "scale(1)";
  },120);

}

});

});

/* =====================================================
TASK TOGGLE SYNC
===================================================== */

async function loadTaskToggle(){

try{

const r = await fetch("/user/settings",{credentials:"include"});

if(!r.ok) return;

const d = await r.json();

const t = document.getElementById("taskToggle");

if(t) t.checked = !!d.task_enabled;

}catch(e){
console.error("Toggle load failed",e);
}

}

document.addEventListener("DOMContentLoaded",()=>{

const t = document.getElementById("taskToggle");

if(!t) return;

t.addEventListener("change",async()=>{

await fetch("/user/settings/task-toggle",{
  method:"POST",
  credentials:"include",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({enabled:t.checked})
});

});

});

/* =====================================================
CHROME TAB KEEP ALIVE
===================================================== */

setInterval(()=>{

fetch("/user/settings",{credentials:"include"}).catch(()=>{});

},20000);
