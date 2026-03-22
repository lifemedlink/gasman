/**
 * GASMAN – Admin Core Script (FINAL)
 * ---------------------------------
 * ✔ Page-based admin UI (NOT SPA)
 * ✔ Device modal support
 * ✔ Dashboard map init
 * ✔ WebSocket live updates
 * ✔ Safe with PM2 + Gunicorn
 */

(function () {

  if (!window.GASMAN_UTILS) {
    console.error("GASMAN_UTILS missing");
    return;
  }

  const deviceCache = {};

  /* ============================================================
     DASHBOARD MAP INIT (ONLY ON /admin)
  ============================================================ */
  document.addEventListener("DOMContentLoaded", () => {
    if (window.location.pathname === "/admin") {
      if (window.GASMAN_ADMIN_MAP_INIT) {
        setTimeout(() => window.GASMAN_ADMIN_MAP_INIT(), 150);
      }
    }
    bindWS();
  });

  /* ============================================================
     DEVICE MODAL (USED BY MAP + DEVICES PAGE)
  ============================================================ */
  window.GASMAN_ADMIN_OPEN_DEVICE = async function (deviceId, focusMap = false) {
    if (!deviceId) return;

    let d = deviceCache[deviceId];

    // Lazy load if not cached
    if (!d) {
      d = await GASMAN_UTILS.safeFetch(`/devices/list`);
      if (Array.isArray(d)) {
        d = d.find(x => x.device_id === deviceId);
      }
      if (!d) return;
      deviceCache[deviceId] = d;
    }

    const modal = document.getElementById("deviceModal");
    if (!modal) return;

    document.getElementById("m_id").innerText = d.device_id;
    document.getElementById("m_status").innerText = d.status || d.classification || "-";
    document.getElementById("m_gas").innerText = `${d.gas_percent ?? "-"}%`;
    document.getElementById("m_location").innerText = d.device_location || "-";
    document.getElementById("m_time").innerText =
      d.seconds_since != null ? `${d.seconds_since}s ago` : "-";

    if (d.coordinates) {
      document.getElementById("m_navigate").href =
        `https://www.google.com/maps?q=${d.coordinates}`;
    }

    new bootstrap.Modal(modal).show();

    // Optional map focus
    if (focusMap && window.location.pathname !== "/admin") {
      window.location.href = "/admin";
    }
  };

  /* ============================================================
     LIVE UPDATES (WebSocket)
  ============================================================ */
  function bindWS() {
    if (!window.GASMAN_WS) return;

    GASMAN_WS.subscribe("device_updates", msg => {
      if (!msg?.device_id) return;

      // Invalidate cache
      delete deviceCache[msg.device_id];

      // Reload devices page automatically
      if (window.location.pathname.startsWith("/admin/devices")) {
        if (window.loadDevices) {
          window.loadDevices();
        }
      }

      // Reload dashboard map
      if (window.location.pathname === "/admin") {
        if (window.GASMAN_ADMIN_MAP_INIT) {
          GASMAN_ADMIN_MAP_INIT();
        }
      }
    });
  }

})();
