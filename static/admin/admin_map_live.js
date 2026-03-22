let map;
let markers = [];

function initAdminMap() {
  map = new google.maps.Map(document.getElementById("adminMap"), {
    center: { lat: 12.9716, lng: 77.5946 },
    zoom: 11
  });

  loadLiveMap();
  setInterval(loadLiveMap, 10000);
}

async function loadLiveMap() {
  const data = await fetch("/admin/map/live").then(r => r.json());

  markers.forEach(m => m.setMap(null));
  markers = [];

  data.forEach(row => {

    // -------- Device Marker --------
    if (row.device_coordinates) {
      const [lat, lng] = row.device_coordinates.split(",").map(Number);

      const color =
        row.classification === "CRITICAL" ? "#f72111" :
        row.classification === "LOW" ? "#f5ed07" :
        "#048a18";

      const deviceMarker = new google.maps.Marker({
        position: { lat, lng },
        map,
        icon: {
          path: "M12 2C7.6 2 4 5.6 4 10c0 6.4 8 14 8 14s8-7.6 8-14c0-4.4-3.6-8-8-8z",
          fillColor: color,
          fillOpacity: 1,
          strokeColor: "#222",
          strokeWeight: 1.5,
          scale: 1.8,
          anchor: new google.maps.Point(12, 24)
        },
        title: `Device: ${row.device_id}`
      });

      markers.push(deviceMarker);
    }

    // -------- Driver Marker --------
    if (row.user_lat && row.user_lng) {
      const driverMarker = new google.maps.Marker({
        position: { lat: row.user_lat, lng: row.user_lng },
        map,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 7,
          fillColor: "#1a73e8",
          fillOpacity: 1,
          strokeColor: "#fff",
          strokeWeight: 2
        },
        title: `Driver: ${row.user_name}`
      });

      markers.push(driverMarker);
    }
  });
}

window.initAdminMap = initAdminMap;
