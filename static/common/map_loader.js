/**
 * GASMAN – Google Maps Loader (FINAL – STABLE)
 * -------------------------------------------
 * ✔ Loads Google Maps exactly once
 * ✔ Handles async safely
 * ✔ Auto-initializes Admin/User map
 * ✔ Shows clear error if API fails
 */

(function (window, document) {

  if (window.loadGoogleMaps) return;

  let loading = false;
  let loaded = false;
  let queue = [];

  window.loadGoogleMaps = function (callback) {

    // Already loaded
    if (loaded && window.google && google.maps) {
      callback && callback();
      return;
    }

    if (callback) queue.push(callback);
    if (loading) return;

    if (!window.GOOGLE_MAPS_API_KEY) {
      console.error("❌ GOOGLE_MAPS_API_KEY missing");
      showMapError("Google Maps API key missing");
      return;
    }

    loading = true;

    window.__GASMAN_MAP_READY = function () {
      loaded = true;
      loading = false;

      queue.forEach(fn => {
        try { fn(); } catch (e) { console.error(e); }
      });
      queue = [];

      autoInit();
    };

    const s = document.createElement("script");
    s.src =
      "https://maps.googleapis.com/maps/api/js" +
      "?key=" + encodeURIComponent(window.GOOGLE_MAPS_API_KEY) +
      "&callback=__GASMAN_MAP_READY&v=weekly";

    s.async = true;
    s.defer = true;

    s.onerror = () => {
      loading = false;
      console.error("❌ Google Maps failed to load");
      showMapError("Google Maps failed to load");
    };

    document.head.appendChild(s);
  };

  function autoInit() {
    if (window.GASMAN_ADMIN_MAP_INIT && document.getElementById("adminMap")) {
      window.GASMAN_ADMIN_MAP_INIT();
      return;
    }
    if (window.GASMAN_USER_MAP_INIT && document.getElementById("userMap")) {
      window.GASMAN_USER_MAP_INIT();
    }
  }

  function showMapError(msg) {
    const el =
      document.getElementById("adminMap") ||
      document.getElementById("userMap");

    if (el) {
      el.innerHTML = `
        <div class="d-flex align-items-center justify-content-center h-100 text-muted">
          <div class="text-center">
            <div style="font-size:28px">⚠️</div>
            <div>${msg}</div>
          </div>
        </div>`;
    }
  }

})(window, document);
