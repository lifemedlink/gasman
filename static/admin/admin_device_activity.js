// ADMIN → Device Activity (ALL devices)

(async function () {

  const list = document.getElementById("adminDeviceList");
  if (!list) return;

  async function loadDevices() {
    list.innerHTML = "<div class='small text-muted'>Loading devices…</div>";

    try {
      const res = await fetch("/get_locations");
      const data = await res.json();

      const devices = [
        ...(data.critical || []),
        ...(data.low || []),
        ...(data.normal || []),
        ...(data.offline || [])
      ];

      list.innerHTML = "";

      devices.forEach(d => {
        const badge =
          d.classification === "CRITICAL" ? "danger" :
          d.classification === "LOW" ? "warning text-dark" :
          d.online ? "success" : "dark";

        const el = document.createElement("div");
        el.className = "list-group-item";

        el.innerHTML = `
          <div class="d-flex justify-content-between">
            <div>
              <strong>${d.device_id}</strong>
              <div class="small text-muted">${d.device_location || ""}</div>
              <div class="small">
                Assigned: ${(d.assigned_users || []).join(", ") || "-"}
              </div>
            </div>
            <span class="badge bg-${badge}">
              ${d.classification || "OFFLINE"}
            </span>
          </div>
        `;

        list.appendChild(el);
      });

    } catch (e) {
      console.error(e);
      list.innerHTML =
        "<div class='text-danger small'>Failed to load</div>";
    }
  }

  loadDevices();
  setInterval(loadDevices, 10000);

})();
