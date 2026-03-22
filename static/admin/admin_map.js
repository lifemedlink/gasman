/* =========================================================
   GASMAN – ADMIN MAP (ENTERPRISE FLEET VERSION)

   ✔ Device clustering
   ✔ Gas % pinheads
   ✔ Filling pulse animation
   ✔ Offline ⚠ warning
   ✔ Driver live tracking
   ✔ Hover device info
   ✔ Hover driver info
   ✔ Click driver → show route
   ✔ Click map → clear route
   ✔ Distance calculation
   ✔ Status label conversion
   ✔ WebSocket live refresh
   ✔ Auto refresh fallback
   ✔ Memory safe
========================================================= */

let map;
let deviceMarkers = {};
let driverMarkers = {};
let driverInfoWindows = {};
let markerCluster = null;
let liveSocket = null;
let didFitBounds = false;

let directionsService;
let directionsRenderers = {};
let etaTimers = {};
let fillingDevices = {};
const urlParams = new URLSearchParams(window.location.search);
let deviceFilter = urlParams.get("filter");

/* =========================================================
   STATUS LABELS
========================================================= */

const STATUS_LABELS = {
  ASSIGNED: "Task Accepted",
  EN_ROUTE: "On The Way",
  ON_SITE: "Location Reached",
  FILLING: "Gas Filling",
  FILLED: "Gas Filled",
  COMPLETED: "Task Completed",
  CANCELLED: "Task Cancelled",
  REJECTED: "Task Rejected"
};


/* =========================================================
   CLEAR ROUTES
========================================================= */

function clearRoutes() {

  Object.keys(directionsRenderers).forEach(id => {

    if (directionsRenderers[id]) {
      directionsRenderers[id].setMap(null);
      delete directionsRenderers[id];
    }

  });

}


/* =========================================================
   SVG PINHEAD
========================================================= */

function createAdminGasPin(gas, classification, isFilling=false, offline=false){

  const color =
    classification === "CRITICAL" ? "#ff3b30" :
    classification === "LOW" ? "#ffcc00" :
    "#22c55e";

  const baseColor = offline ? "#6b7280" : color;

  const gasText = (gas ?? "-") + "%";

  const svg = `
<svg width="44" height="56" viewBox="0 0 44 56"
xmlns="http://www.w3.org/2000/svg">

<path d="M22 0C10 0 0 10 0 22c0 16 22 34 22 34s22-18 22-34C44 10 34 0 22 0z"
fill="${baseColor}" />

<circle cx="22" cy="22" r="14" fill="#111827"/>

${
offline
? `
<text x="22" y="27"
text-anchor="middle"
font-size="18"
font-weight="700"
fill="#ffffff"
font-family="Segoe UI Emoji, Arial">
⚠
</text>
`
: isFilling
? `
<text x="22" y="22"
text-anchor="middle"
font-size="11"
font-weight="700"
fill="#ffffff">
${gasText}
</text>

<text x="22" y="46"
text-anchor="middle"
font-size="17"
fill="#ffffff"
font-family="Segoe UI Emoji, Arial">
⛽︎
</text>
`
: `
<text x="22" y="27"
text-anchor="middle"
font-size="11"
font-weight="700"
fill="#ffffff">
${gasText}
</text>
`
}

</svg>
`;

  return {
    url:"data:image/svg+xml;charset=UTF-8,"+encodeURIComponent(svg),
    scaledSize:new google.maps.Size(44,60),
    anchor:new google.maps.Point(22,56)
  };

}

/* =========================================================
   INIT MAP
========================================================= */

function initAdminMap(){

  const el=document.getElementById("adminMap");
  if(!el || map) return;

  map=new google.maps.Map(el,{
    center:{lat:12.9716,lng:77.5946},
    zoom:11,
    streetViewControl:false,
    mapTypeControl:false,
    fullscreenControl:true,
    gestureHandling:"greedy"
  });

  directionsService=new google.maps.DirectionsService();

  map.addListener("click",clearRoutes);

  loadAdminMap();
  initAdminLiveSocket();

  setInterval(loadAdminMap,15000);

}


/* =========================================================
   LOAD MAP DATA
========================================================= */

async function loadAdminMap(){

  try{

    const res=await fetch("/admin/map/live",{credentials:"include"});

    if(!res.ok) return;

    const data=await res.json();

    renderTasks(data.tasks || []);
    renderDevices(data.devices || []);

  }catch(e){

    console.error("Admin map error:",e);

  }

}


/* =========================================================
   RENDER DEVICES
========================================================= */

function renderDevices(devices){

  if(!map) return;

  const markers=[];

  Object.values(deviceMarkers).forEach(m=>m.setMap(null));
  deviceMarkers={};

devices.forEach(d=>{

  const activeFilter = window.deviceFilter || deviceFilter;

  if(activeFilter){

    // Offline filter
    if(activeFilter === "OFFLINE" && !d.offline) return;

    // Active tasks filter
    if(activeFilter === "TASKS" && !fillingDevices[d.device_id]) return;

    // Classification filters
    if(
      activeFilter !== "OFFLINE" &&
      activeFilter !== "TASKS" &&
      d.classification !== activeFilter
    ) return;

  }
    if(!d.coordinates) return;

    const [lat,lng]=d.coordinates.split(",").map(Number);
    if(isNaN(lat)||isNaN(lng)) return;

    const gasValue =
      d.gas_percent != null && !isNaN(d.gas_percent)
      ? Math.round(parseFloat(d.gas_percent))
      : "-";

    const isFilling=fillingDevices[d.device_id]===true;

    const marker=new google.maps.Marker({

      position:{lat,lng},

      icon:createAdminGasPin(
        gasValue,
        d.classification,
        isFilling,
        d.offline
      )

    });


/* DEVICE INFO */

const info=new google.maps.InfoWindow({

content:`
<div style="font-family:Inter;font-size:13px;min-width:220px">

<div style="font-weight:600;margin-bottom:6px">
Device: ${d.device_id}
</div>

<div>Customer: ${d.customer_name || "-"}</div>

<div>Location: ${d.device_location || "-"}</div>

<div>Gas Level: ${gasValue}%</div>

<div>Status: ${d.offline ? "OFFLINE":"ONLINE"}</div>

</div>
`
});

marker.addListener("mouseover",()=>info.open(map,marker));
marker.addListener("mouseout",()=>info.close());

markers.push(marker);
deviceMarkers[d.device_id]=marker;

  });


  if(markerCluster) markerCluster.clearMarkers();

  if(window.markerClusterer?.MarkerClusterer){

    markerCluster=new markerClusterer.MarkerClusterer({
      map,
      markers
    });

  }else{

    markers.forEach(m=>m.setMap(map));

  }

}


/* =========================================================
   RENDER DRIVER TASKS
========================================================= */

function renderTasks(tasks){

  fillingDevices={};
Object.keys(etaTimers).forEach(id=>{
  if(!tasks.find(t => t.task_id == id)){
    clearInterval(etaTimers[id]);
    delete etaTimers[id];
  }
});
  tasks.forEach(t=>{
const activeFilter = window.deviceFilter || deviceFilter;

  // If filter is not TASKS, hide drivers
  if(activeFilter && activeFilter !== "TASKS") return;
if(
  t.status === "ASSIGNED" ||
  t.status === "EN_ROUTE" ||
  t.status === "ON_SITE" ||
  t.status === "FILLING"
){
  fillingDevices[t.device_id] = true;
}

    if(!t.device_coordinates||t.user_lat==null) return;

    const [dlat,dlng]=t.device_coordinates.split(",").map(Number);

    if(isNaN(dlat)||isNaN(dlng)) return;

    const distance=calculateDistance(
      t.user_lat,
      t.user_lng,
      dlat,
      dlng
    );
let eta = "-";
    if(!driverMarkers[t.task_id]){

      const marker=new google.maps.Marker({

        position:{lat:t.user_lat,lng:t.user_lng},

        map,

        icon:{
          path:google.maps.SymbolPath.CIRCLE,
          scale:8,
          fillColor:"#0d6efd",
          fillOpacity:1,
          strokeColor:"#fff",
          strokeWeight:2
        }

      });


/* DRIVER INFO */

const info=new google.maps.InfoWindow({

content:`
<div style="font-family:Inter;font-size:13px;min-width:230px">

<div style="font-weight:600;margin-bottom:6px">
Driver: ${t.user_name}
</div>

<div>
Track ID: 
<span style="font-weight:600;color:#0d6efd">
${t.tracking_id || "-"}
</span>
</div>

<div>Device: ${t.device_id}</div>

<div>Customer: ${t.customer_name || "-"}</div>

<div>Location: ${t.device_location || "-"}</div>

<div>Status: ${STATUS_LABELS[t.status] || t.status}</div>

<div id="eta-${t.task_id}">ETA: calculating...</div>
</div>
`
});
driverInfoWindows[t.task_id] = info;

marker.addListener("mouseover",()=>info.open(map,marker));
marker.addListener("mouseout",()=>info.close());

marker.addListener("click",()=>{

clearRoutes();

const renderer=new google.maps.DirectionsRenderer({
suppressMarkers:true,
polylineOptions:{strokeColor:"#0d6efd",strokeWeight:5}
});

renderer.setMap(map);

directionsRenderers[t.task_id]=renderer;

directionsService.route(
{
origin:{lat:t.user_lat,lng:t.user_lng},
destination:{lat:dlat,lng:dlng},
travelMode:google.maps.TravelMode.DRIVING
},
(result,status)=>{
if(status==="OK"){

renderer.setDirections(result);

const etaText = result.routes[0].legs[0].duration.text;

// Update popup ETA
const el = document.getElementById(`eta-${t.task_id}`);
if(el) el.innerText = "ETA: " + etaText;

}
}
);

});

driverMarkers[t.task_id]=marker;
if(!etaTimers[t.task_id]){

  etaTimers[t.task_id] = setInterval(()=>{

    const marker = driverMarkers[t.task_id];
    if(!marker) return;

    const pos = marker.getPosition();

    updateDriverETA(
      t.task_id,
      {lat:pos.lat(), lng:pos.lng()},
      {lat:dlat, lng:dlng}
    );

  },10000);

}
    }else{

  driverMarkers[t.task_id].setPosition({
    lat:t.user_lat,
    lng:t.user_lng
  });

  const popupContent = `
<div style="font-family:Inter;font-size:13px;min-width:230px">

<div style="font-weight:600;margin-bottom:6px">
Driver: ${t.user_name}
</div>

<div>
Track ID:
<span style="font-weight:600;color:#0d6efd">
${t.tracking_id || "-"}
</span>
</div>

<div>Device: ${t.device_id}</div>

<div>Customer: ${t.customer_name || "-"}</div>

<div>Location: ${t.device_location || "-"}</div>

<div>Status: ${STATUS_LABELS[t.status] || t.status}</div>

<div id="eta-${t.task_id}">ETA: calculating...</div>
</div>
`;

  if(driverInfoWindows[t.task_id]){
    driverInfoWindows[t.task_id].setContent(popupContent);
  }

}

  });

}


/* =========================================================
   DISTANCE
========================================================= */

function calculateDistance(lat1,lon1,lat2,lon2){

const R=6371;

const dLat=(lat2-lat1)*Math.PI/180;
const dLon=(lon2-lon1)*Math.PI/180;

const a=
Math.sin(dLat/2)*Math.sin(dLat/2)+
Math.cos(lat1*Math.PI/180)*
Math.cos(lat2*Math.PI/180)*
Math.sin(dLon/2)*Math.sin(dLon/2);

const c=2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));

return (R*c).toFixed(2);

}

function updateDriverETA(taskId, origin, destination){

  directionsService.route(
  {
    origin,
    destination,
    travelMode: google.maps.TravelMode.DRIVING
  },
  (result,status)=>{

    if(status === "OK"){

      const etaText = result.routes[0].legs[0].duration.text;

      const el = document.getElementById(`eta-${taskId}`);
      if(el){
        el.innerText = "ETA: " + etaText;
      }

    }

  });

}
/* =========================================================
   WEBSOCKET LIVE
========================================================= */

function initAdminLiveSocket(){

if(liveSocket) return;

const protocol=location.protocol==="https:"?"wss":"ws";

liveSocket=new WebSocket(
`${protocol}://${location.host}/ws/devices?role=admin`
);

liveSocket.onmessage=()=>{
loadAdminMap();
};

}


/* =========================================================
   WAIT GOOGLE MAP
========================================================= */

(function waitForGoogle(){

if(window.google && window.google.maps){
initAdminMap();
}else{
setTimeout(waitForGoogle,100);
}

})();
/* =========================================================
   AUTO PAGE REFRESH (every 5 minutes)
========================================================= */

setInterval(()=>{
  location.reload();
},300000);
