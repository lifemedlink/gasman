// static/admin/admin_live.js

async function api(url) {
  try {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/* =====================================================
   STATUS DISPLAY MAP
===================================================== */

const statusMap = {
  "ASSIGNED": "ACCEPTED",
  "EN_ROUTE": "ON THE WAY",
  "ON_SITE": "LOCATION REACHED",
  "FILLING": "GAS FILLING",
  "FILLED": "GAS FILLED",
  "COMPLETED": "COMPLETED"
};

function getBadgeClass(classification) {
  if (classification === "CRITICAL") return "bg-danger";
  if (classification === "LOW") return "bg-warning text-dark";
  return "bg-success";
}

function openMap(coordinates) {
  if (!coordinates) return;
  const url = `https://www.google.com/maps?q=${coordinates}`;
  window.open(url, "_blank");
}

/* =====================================================
   LOAD LIVE TASKS
===================================================== */

async function loadLiveTasks() {

  const tbody = document.getElementById("liveTaskTable");
  if (!tbody) return;

  const data = await api("/admin/tasks/live");

  if (!data || !data.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center text-muted">
          No active driver tasks
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = data.map(t => {

    const displayStatus = statusMap[t.status] || t.status;
    const badgeClass = getBadgeClass(t.classification);

    const gasPercent = Math.round(t.gas_percentage ?? 0);

    const mapBtn = t.coordinates
      ? `<button class="btn btn-sm btn-outline-primary"
           onclick="openMap('${t.coordinates}')">
           View Map
         </button>`
      : "-";

    return `
      <tr>
        <td>${t.driver ?? "-"}</td>

        <td>
          <strong>${t.device_id}</strong>
        </td>

        <td>
          ${t.device_location ?? "-"}
        </td>

        <td>
          <span class="badge ${badgeClass}">
            ${displayStatus}
          </span>
        </td>

        <td>
          ${gasPercent}%
        </td>

        <td>
          ${t.tracking_id ?? "-"}
        </td>

        <td>
          ${t.accepted_at ?? "-"}
        </td>

        <td>
          ${mapBtn}
        </td>
      </tr>
    `;
  }).join("");
}

/* =====================================================
   AUTO REFRESH
===================================================== */

loadLiveTasks();
setInterval(loadLiveTasks, 15000);
