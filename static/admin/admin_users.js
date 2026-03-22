/**
 * GASMAN – Admin Users (Fleet View)
 * ✔ Online / Offline indicator
 * ✔ Device modal
 * ✔ Device navigation
 * ✔ Force logout
 * ✔ Auto refresh (5 sec)
 */

(function () {

  const driverTable = document.getElementById("driverTable");
  const sessionTable = document.getElementById("sessionTable");

  if (!driverTable) return;

  const deviceModalEl = document.getElementById("deviceModal");
  const deviceList = document.getElementById("deviceList");
  const deviceModal = deviceModalEl
    ? new bootstrap.Modal(deviceModalEl)
    : null;

  /* =====================================================
     LOAD DRIVERS
  ===================================================== */
  async function loadDrivers() {

    const res = await GASMAN_UTILS.safeFetch("/admin/users/list");

    if (!res || !res.length) {
      driverTable.innerHTML =
        `<tr>
          <td colspan="4" class="text-center text-muted p-3">
            No drivers found
          </td>
        </tr>`;
      return;
    }

    driverTable.innerHTML = res.map(d => {

      const onlineBadge = d.is_online
        ? `<span class="badge bg-success">Online</span>`
        : `<span class="badge bg-danger">Offline</span>`;

      return `
        <tr>
          <td>${d.user_name}</td>
          <td>${d.contact_no || "-"}</td>
          <td>
            <span class="badge bg-info"
                  style="cursor:pointer"
                  onclick="showDevices(${d.user_id})">
              ${d.devices_assigned}
            </span>
          </td>
          <td>${onlineBadge}</td>
        </tr>
      `;
    }).join("");
  }

  /* =====================================================
     SHOW DEVICES
  ===================================================== */
  window.showDevices = async function (userId) {

    if (!deviceModal || !deviceList) return;

    deviceList.innerHTML =
      `<li class="list-group-item text-muted">Loading...</li>`;

    deviceModal.show();

    const res = await GASMAN_UTILS.safeFetch(
      `/admin/users/devices/${userId}`
    );

    if (!res || !res.length) {
      deviceList.innerHTML =
        `<li class="list-group-item text-muted">
          No devices assigned
        </li>`;
      return;
    }

    deviceList.innerHTML = res.map(d => `
      <li class="list-group-item d-flex justify-content-between">
        <span>
          <strong>${d.device_id}</strong>
          <div class="small text-muted">
            ${d.customer_name || ""}
          </div>
        </span>
        <button class="btn btn-sm btn-outline-primary"
                onclick="openDevice('${d.device_id}')">
          Open
        </button>
      </li>
    `).join("");
  };

  /* =====================================================
     OPEN DEVICE PAGE
  ===================================================== */
  window.openDevice = function (deviceId) {
    window.location.href =
      `/admin/devices?device_id=${deviceId}`;
  };

  /* =====================================================
     LOAD SESSIONS
  ===================================================== */
  async function loadSessions() {

    if (!sessionTable) return;

    const res = await GASMAN_UTILS.safeFetch(
      "/admin/users/sessions"
    );

    if (!res || !res.length) {
      sessionTable.innerHTML =
        `<tr>
          <td colspan="5" class="text-center text-muted p-3">
            No active sessions
          </td>
        </tr>`;
      return;
    }

    sessionTable.innerHTML = res.map(s => {

      const lastSeen = s.last_seen
        ? new Date(s.last_seen).toLocaleString()
        : "-";

      return `
        <tr>
          <td>${s.user_name}</td>
          <td>${s.device || "-"}</td>
          <td>${lastSeen}</td>
          <td>
            <button class="btn btn-sm btn-danger"
                    onclick="forceLogout('${s.user_name}')">
              Logout
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  /* =====================================================
     FORCE LOGOUT
  ===================================================== */
  window.forceLogout = async function (username) {

    if (!confirm(`Force logout ${username}?`)) return;

    await GASMAN_UTILS.safeFetch(
      `/admin/users/sessions/force/${username}`,
      { method: "DELETE" }
    );

    loadDrivers();
    loadSessions();
  };

  /* =====================================================
     AUTO REFRESH (5 sec)
  ===================================================== */
  let refreshInterval = null;

  function startAutoRefresh() {

    if (refreshInterval) {
      clearInterval(refreshInterval);
    }

    refreshInterval = setInterval(() => {
      loadDrivers();
      loadSessions();
    }, 5000);
  }

  /* =====================================================
     INIT
  ===================================================== */
  loadDrivers();
  loadSessions();
  startAutoRefresh();

})();
